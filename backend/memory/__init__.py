"""Hierarchical project memory — <project data>/memory/project_state.json

Tier 1  Working memory    recent chat turns + latest run logs (computed live, not copied)
Tier 2  Episodic memory   rolling summaries written by the background compressor (memory/compressor.py)
Tier 3  Long-term store   goals, hypotheses, constraints, locked decisions, validated references, best metrics

The background worker compresses old chat turns and finished runs into episodes when Tier 1 passes the high watermark,
so local 14B models never overflow their context while the whole multi-month history stays available to every agent.
"""
from __future__ import annotations

import asyncio
import json
import re
import secrets
import threading
from datetime import datetime, timezone

from backend.core.config import data_dir, load_config
from backend.memory.store import bump as _bump, replace_retry as _replace

_lock = threading.RLock()  # v3.3: re-entrant — load() takes it too (update() → load())
SUMMARY_CHARS = 30_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tokens(text_or_len) -> int:
    n = text_or_len if isinstance(text_or_len, int) else len(text_or_len or "")
    return (n + 3) // 4


def mem_dir():
    d = data_dir() / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


EMPTY = {"version": 1, "tier2": [], "tier3": {"goals": [], "hypotheses": [], "constraints": [], "best_metrics": {},
                                             "references": [], "notes": ""},
         "decisions": [], "summarized": {}, "runs_summarized": [], "stats": {}, "tier2_archive": []}


def load() -> dict:
    from backend.memory.store import read_retry
    f = mem_dir() / "project_state.json"
    st = json.loads(json.dumps(EMPTY))
    with _lock:
        return _load_into(f, st, read_retry)


def _load_into(f, st, read_retry) -> dict:
    if f.exists():
        try:
            d = json.loads(read_retry(f))
            st.update({k: v for k, v in d.items() if k in st})
            st["tier3"] = {**EMPTY["tier3"], **(d.get("tier3") or {})}
        except ValueError:
            from backend.memory.store import quarantine
            quarantine(f)  # v3.3: keep the damaged file instead of overwriting it with an empty state
        except Exception:
            pass
    return st


def save(st: dict) -> dict:
    with _lock:
        f = mem_dir() / "project_state.json"
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), "utf-8")
        _replace(tmp, f)
        _bump()
    return st


def update(fn) -> dict:
    with _lock:
        st = load()
        fn(st)
        f = mem_dir() / "project_state.json"
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), "utf-8")
        _replace(tmp, f)
        _bump()
    return st


# ------------------------------------------------------------------ decisions (locked research directions)
KINDS = ("direction", "hypothesis", "gap", "constraint", "rejected", "other")


def add_decision(text: str, kind: str = "direction", source: str = "", locked: bool = True, evidence_ids=None,
                 origin: str = "human", provider: str = "", session: str = "", supersedes: str = "") -> dict:
    """v3.3: a decision may cite evidence (EVID-/EXP-/CLM- ids), carries who made it (origin/provider/session) and may
    supersede an older decision — the old one is unlocked and marked, never deleted (temporal correctness)."""
    refs = [str(e).strip()[:20] for e in (evidence_ids or []) if str(e).strip()][:20]
    d = {"id": "D" + secrets.token_hex(3), "text": text.strip()[:4000], "kind": kind if kind in KINDS else "other",
         "locked": bool(locked), "source": source[:200], "created": _now(), "evidence_ids": refs, "origin": origin[:60],
         "provider": provider[:40], "session": session[:80]}

    def fn(st):
        if supersedes:
            old = next((x for x in st["decisions"] if x["id"] == supersedes), None)
            if not old:
                raise ValueError(f"Decision {supersedes} not found")
            old.update(locked=False, superseded_by=d["id"], updated=_now())
            d["supersedes"] = supersedes
        st["decisions"].append(d)
    update(fn)
    return d


# ------------------------------------------------------------------ tier 1 (computed)
def _sessions():
    from backend.agent.sessions import _dir as _sess_dir
    out = []
    for f in _sess_dir().glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            d = json.loads(f.read_text("utf-8"))
            out.append(d)
        except Exception:
            continue
    return out


def tier1(st: dict | None = None) -> dict:
    st = st or load()
    keep = int(load_config()["memory"]["keep_recent_turns"])
    per, total = [], 0
    for s in _sessions():
        msgs = s.get("messages") or []
        done = int(st["summarized"].get(s["id"], 0))
        pending = msgs[done:]
        t = tokens(sum(len(m.get("content", "")) for m in pending))
        compressible = max(0, len(msgs) - keep - done)
        per.append({"id": s["id"], "tool": s.get("tool", "data"), "title": s.get("title", ""), "messages": len(msgs),
                    "summarized": done, "pending_tokens": t, "compressible": compressible})
        total += t
    runs_tok = 0
    try:
        from backend.execution.sandbox import list_runs, runs_dir
        for r in list_runs(30):
            if r["id"] in st["runs_summarized"]:
                continue
            p = runs_dir() / r["id"] / "stdout.log"
            runs_tok += tokens(min(p.stat().st_size, 20000)) if p.exists() else 0
    except Exception:
        pass
    return {"tokens": total + runs_tok, "chat_tokens": total, "log_tokens": runs_tok,
            "sessions": sorted(per, key=lambda x: -x["pending_tokens"])}


# ------------------------------------------------------------------ summarization agent
SUMMARY_SYS = """You are the Memory Summarization Agent of a long-running PhD research project.
Compress the conversation excerpt into an EPISODIC MEMORY entry that another AI can rely on months later.
Keep every concrete fact: decisions taken, directions chosen or rejected, hypotheses, numbers/metrics, dataset and model
names, parameter settings, bugs found and their fixes, open questions and next steps. Drop greetings and repetition.
Never invent anything. Output Markdown, at most ~350 words:
TITLE: <one line>
## Context
## Key facts & decisions
## Metrics / numbers
## Open questions & next steps"""

RUNS_SYS = """You are the Memory Summarization Agent. Summarize this batch of experiment runs (commands, status, metrics)
into an EPISODIC MEMORY entry: what was tried, what worked, metric trajectories (best/worst, trends), failures and their
causes. Never invent numbers. Output Markdown, at most ~250 words, starting with a line 'TITLE: <one line>'."""


def _split_title(text: str, fallback: str) -> tuple[str, str]:
    m = re.match(r"\s*TITLE:\s*(.+)", text)
    if m:
        return m.group(1).strip()[:160], text[m.end():].strip()
    return fallback, text.strip()


_running = {"busy": False}


async def summarize(force: bool = False) -> dict:
    """Compress old chat turns and finished runs into Tier-2 episodes; refresh Tier 3 (memory/compressor.py)."""
    from backend.memory.compressor import compress
    return await compress(force=force)


async def _summarize_runs(force: bool) -> int:
    from backend.providers.models import call_agent
    from backend.execution.sandbox import list_runs
    st = load()
    pend = [r for r in list_runs(60) if r["id"] not in st["runs_summarized"] and r.get("status") in ("done", "failed", "stopped")]
    if len(pend) < (1 if force else 3):
        return 0
    lines = [f"- {r['id']} · {r['status']} (exit {r.get('exit_code')}) · {r.get('duration')} s · `{(r.get('cmd') or '')[:120]}` · "
             f"metrics: {json.dumps(r.get('metrics') or {})[:400]}" for r in reversed(pend)]
    try:
        r = await call_agent("summarizer", RUNS_SYS, "RUNS (oldest first):\n" + "\n".join(lines), max_tokens=700, temperature=0.1)
    except Exception:
        return 0
    title, body = _split_title(r["text"], f"Experiment runs ({len(pend)})")
    links = [f"run:{x['id']}" for x in pend]
    pages = []
    try:  # v3.2: raw run list snapshotted into the page-store + entity links (task ids, commits) for graph retrieval
        from backend.memory.pages import add_page
        from backend.memory.compressor import entities
        raw = "\n".join(lines)
        pages = [add_page("runs", "runs", [pend[-1]["id"], pend[0]["id"]], raw, header=title)["id"]]
        links = list(dict.fromkeys(links + entities(raw + "\n" + r["text"])))
    except Exception:
        pass
    ep = {"id": "E" + secrets.token_hex(3), "created": _now(), "source": "runs", "tool": "ide", "title": title, "summary": body,
          "runs": [x["id"] for x in pend], "engine": r.get("engine"), "compressed_tokens": tokens(sum(len(l) for l in lines)),
          "links": links, "pages": pages}

    def put(st2):
        st2["tier2"].append(ep)
        st2["runs_summarized"] = (st2["runs_summarized"] + [x["id"] for x in pend])[-2000:]
    update(put)
    return len(pend)


async def _consolidate(max_episodes: int = 40, batch: int = 12):
    """Rolling memory: when Tier 2 grows too long, merge the oldest episodes into one period summary."""
    from backend.providers.models import call_agent
    st = load()
    eps = [e for e in st["tier2"] if not e.get("pinned")]
    if len(eps) <= max_episodes:
        return
    old = eps[:batch]
    text = "\n\n".join(f"### {e['title']} ({e['created'][:10]})\n{e['summary']}" for e in old)
    try:
        r = await call_agent("summarizer", SUMMARY_SYS.replace("conversation excerpt", "set of older memory entries"),
                             "OLDER EPISODES TO MERGE:\n\n" + text[:SUMMARY_CHARS], max_tokens=1000, temperature=0.1)
    except Exception:
        return
    title, body = _split_title(r["text"], f"Period summary {old[0]['created'][:10]} → {old[-1]['created'][:10]}")
    # v3.3: the period summary inherits the raw-page pointers and entity links of what it merges (provenance survives),
    # and the merged episodes move to tier2_archive (kept, no longer injected) instead of being dropped.
    merged = {"id": "E" + secrets.token_hex(3), "created": _now(), "source": "consolidated", "title": title, "summary": body,
              "period": [old[0]["created"], old[-1]["created"]], "merged": [e["id"] for e in old], "engine": r.get("engine"),
              "pages": list(dict.fromkeys(p for e in old for p in (e.get("pages") or []))),
              "links": list(dict.fromkeys([l for e in old for l in (e.get("links") or [])] + [e["id"] for e in old]))}
    ids = {e["id"] for e in old}

    def put(st2):
        st2["tier2_archive"] = (st2.get("tier2_archive") or []) + [e for e in st2["tier2"] if e["id"] in ids]
        st2["tier2"] = [merged] + [e for e in st2["tier2"] if e["id"] not in ids]
    update(put)


# ------------------------------------------------------------------ tier 3
def refresh_tier3() -> dict:
    """Fill the automatic parts of Tier 3: best measured metrics and the validated references of the library."""
    try:
        from backend.execution.sandbox import best_metrics
        bm = best_metrics()
    except Exception:
        bm = {}
    try:
        from backend.knowledge.library import included
        refs = [e["key"] for e in included()]
    except Exception:
        refs = []

    def fn(st):
        st["tier3"]["best_metrics"] = bm
        st["tier3"]["references"] = refs
    st = update(fn)
    return st


# ------------------------------------------------------------------ background worker
async def worker(stop_event: asyncio.Event):
    """Started with the app: checks Tier 1 periodically and summarizes the active project when it is too big."""
    await asyncio.sleep(20)
    while not stop_event.is_set():
        try:
            cfg = load_config()["memory"]
            if cfg.get("auto_summarize", True):
                if tier1()["tokens"] >= int(cfg["high_watermark_tokens"]):
                    await summarize(force=False)
                update(lambda st: st["stats"].update(last_check=_now()))
            delay = max(30, int(cfg.get("interval_s", 180)))
        except Exception as e:
            try:
                update(lambda st: st["stats"].update(last_error=f"{type(e).__name__}: {e}"[:300], last_check=_now()))
            except Exception:
                pass
            delay = 300
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass


def set_tier3(patch: dict) -> dict:
    """Long-term project memory (goals, hypotheses, constraints, notes). The research outline writes its topic and
    direction here, so every agent and the research state see the current goal (agent/outline.py)."""
    def fn(st):
        for k in ("goals", "hypotheses", "constraints"):
            if k in patch and isinstance(patch[k], list):
                st["tier3"][k] = [str(x).strip()[:1000] for x in patch[k] if str(x).strip()]
                st["tier3"][f"{k}_manual"] = True
        if "notes" in patch:
            st["tier3"]["notes"] = str(patch["notes"])[:8000]
    return update(fn)
