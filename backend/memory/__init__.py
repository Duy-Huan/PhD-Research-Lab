"""Hierarchical project memory (v3.0) — <project data>/memory/project_state.json

Tier 1  Working memory    recent chat turns of every tool + latest sandbox logs (computed live, not copied)
Tier 2  Episodic memory   rolling summaries written by the background Summarization Agent (local model by default)
Tier 3  Long-term store   goals, hypotheses, constraints, locked decisions, validated references, best metrics

The summarizer runs in the background when Tier 1 exceeds a token threshold (or on demand). It compresses old
chat turns and finished runs into structured episodes, so local 14B models never overflow their context while the
whole multi-month history stays available to every agent.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone

from ..config import data_dir, load_config, workspace

_lock = threading.Lock()
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
         "decisions": [], "summarized": {}, "runs_summarized": [], "stats": {}}


def load() -> dict:
    f = mem_dir() / "project_state.json"
    st = json.loads(json.dumps(EMPTY))
    if f.exists():
        try:
            d = json.loads(f.read_text("utf-8"))
            st.update({k: v for k, v in d.items() if k in st})
            st["tier3"] = {**EMPTY["tier3"], **(d.get("tier3") or {})}
        except Exception:
            pass
    return st


def save(st: dict) -> dict:
    with _lock:
        f = mem_dir() / "project_state.json"
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, f)
    return st


def update(fn) -> dict:
    with _lock:
        st = load()
        fn(st)
        f = mem_dir() / "project_state.json"
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, f)
    return st


# ------------------------------------------------------------------ decisions (locked research directions)
KINDS = ("direction", "hypothesis", "gap", "constraint", "rejected", "other")


def add_decision(text: str, kind: str = "direction", source: str = "", locked: bool = True) -> dict:
    d = {"id": "D" + secrets.token_hex(3), "text": text.strip()[:4000], "kind": kind if kind in KINDS else "other",
         "locked": bool(locked), "source": source[:200], "created": _now()}
    update(lambda st: st["decisions"].append(d))
    return d


def edit_decision(did: str, patch: dict) -> dict:
    out = {}

    def fn(st):
        for d in st["decisions"]:
            if d["id"] == did:
                for k in ("text", "kind", "locked"):
                    if k in patch:
                        d[k] = (patch[k] if k != "kind" or patch[k] in KINDS else d[k])
                d["updated"] = _now()
                out.update(d)
    update(fn)
    return out


def delete_decision(did: str):
    update(lambda st: st.__setitem__("decisions", [d for d in st["decisions"] if d["id"] != did]))


def decisions_block(st: dict | None = None, purged: set | None = None) -> str:
    st = st or load()
    purged = purged or set()
    ds = [d for d in st["decisions"] if d.get("locked") and d["id"] not in purged]
    if not ds:
        return ""
    icon = {"direction": "✅ CHOSEN DIRECTION", "hypothesis": "🧪 HYPOTHESIS", "gap": "🎯 TARGET GAP", "constraint": "📏 CONSTRAINT",
            "rejected": "🚫 REJECTED (do not propose again)", "other": "📌 DECISION"}
    return "\n".join(f"- [{d['id']}] {icon.get(d['kind'], 'DECISION')}: {d['text']}" for d in ds)


# ------------------------------------------------------------------ tier 1 (computed)
def _sessions():
    from ..chat_store import _sess_dir
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
        from ..sandbox import list_runs, runs_dir
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


async def summarize(force: bool = False, max_sessions: int = 6) -> dict:
    """Compress old chat turns and finished runs into Tier-2 episodes; refresh Tier 3. Returns a report.
    v3.2: with memory.v2_pipeline (default) the watermark compressor (memory/compressor.py) does the work."""
    from ..llm import call_agent
    if load_config()["memory"].get("v2_pipeline", True):
        from .compressor import compress
        return await compress(force=force)
    if _running["busy"]:
        return {"skipped": "already running"}
    _running["busy"] = True
    report = {"episodes": 0, "sessions": [], "runs": 0, "errors": []}
    try:
        cfg = load_config()["memory"]
        keep = int(cfg["keep_recent_turns"])
        st = load()
        t1 = tier1(st)
        if not force and t1["tokens"] < int(cfg["tier1_threshold_tokens"]):
            refresh_tier3()
            return {**report, "skipped": "below threshold", "tier1_tokens": t1["tokens"]}
        sess_by_id = {s["id"]: s for s in _sessions()}
        for info in [x for x in t1["sessions"] if x["compressible"] > 0][:max_sessions]:
            s = sess_by_id.get(info["id"])
            if not s:
                continue
            done = info["summarized"]
            upto = len(s["messages"]) - keep
            chunk, used = [], 0
            for i in range(done, upto):
                m = s["messages"][i]
                line = f"{m['role'].upper()}: {m['content'][:6000]}"
                if used + len(line) > SUMMARY_CHARS and chunk:
                    upto = i
                    break
                chunk.append(line)
                used += len(line)
            if not chunk:
                continue
            try:
                r = await call_agent("summarizer", SUMMARY_SYS,
                                     f"TOOL: {s.get('tool')} · SESSION: {s.get('title', '')}\n\nCONVERSATION EXCERPT (turns {done + 1}-{upto}):\n\n" + "\n\n".join(chunk),
                                     max_tokens=900, temperature=0.1)
            except Exception as e:
                report["errors"].append(f"{s.get('title', s['id'])}: {e}")
                continue
            title, body = _split_title(r["text"], f"{s.get('tool')} · {s.get('title', '')}")
            ep = {"id": "E" + secrets.token_hex(3), "created": _now(), "source": f"chat:{s.get('tool')}:{s['id']}", "tool": s.get("tool"),
                  "session": s["id"], "title": title, "summary": body, "turns": [done + 1, upto], "engine": r.get("engine"),
                  "compressed_tokens": tokens(used)}

            def put(st2, ep=ep, sid=s["id"], upto=upto):
                st2["tier2"].append(ep)
                st2["summarized"][sid] = upto
            update(put)
            report["episodes"] += 1
            report["sessions"].append(s.get("title", s["id"]))
        report["runs"] = await _summarize_runs(force)
        report["episodes"] += 1 if report["runs"] else 0
        await _consolidate()
        refresh_tier3()
        update(lambda st2: st2["stats"].update(last_summary=_now(), last_report={k: v for k, v in report.items() if k != "sessions"}))
        return report
    finally:
        _running["busy"] = False


async def _summarize_runs(force: bool) -> int:
    from ..llm import call_agent
    from ..sandbox import list_runs
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
        from .pages import add_page
        from .compressor import entities
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
    from ..llm import call_agent
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
    merged = {"id": "E" + secrets.token_hex(3), "created": _now(), "source": "consolidated", "title": title, "summary": body,
              "period": [old[0]["created"], old[-1]["created"]], "merged": [e["id"] for e in old], "engine": r.get("engine")}
    ids = {e["id"] for e in old}

    def put(st2):
        st2["tier2"] = [merged] + [e for e in st2["tier2"] if e["id"] not in ids]
    update(put)


# ------------------------------------------------------------------ tier 3
def _plan_sections(md: str) -> dict:
    out = {"goals": [], "hypotheses": []}
    m = re.search(r"##\s*1\.[^\n]*\n(.+?)(?=\n##\s)", md, re.S)
    if m:
        first = re.split(r"\n\s*\n", m.group(1).strip())[0]
        out["goals"] = [re.sub(r"\s+", " ", first)[:600]]
    m = re.search(r"##\s*5\.[^\n]*\n(.+?)(?=\n##\s|\Z)", md, re.S)
    if m:
        hs = re.findall(r"(?:^|\n)\s*(?:[-*]\s*)?\**(H\d+)\**[:.)\s-]+(.+)", m.group(1))
        out["hypotheses"] = [f"{h}: {re.sub(r'[*`]', '', t).strip()[:300]}" for h, t in hs][:8]
    return out


def refresh_tier3() -> dict:
    """Fill the automatic parts of Tier 3 (best metrics, references, goals/hypotheses from Lit2Plan when not set by hand)."""
    try:
        from ..sandbox import best_metrics
        bm = best_metrics()
    except Exception:
        bm = {}
    try:
        from ..library import included
        refs = [e["key"] for e in included()]
    except Exception:
        refs = []
    plan = ""
    f = workspace() / "lit2plan.md"
    if f.exists():
        plan = f.read_text("utf-8")

    def fn(st):
        t3 = st["tier3"]
        t3["best_metrics"] = bm
        t3["references"] = refs
        if plan:
            ps = _plan_sections(plan)
            if not t3.get("goals_manual") and ps["goals"]:
                t3["goals"] = ps["goals"]
            if not t3.get("hypotheses_manual") and ps["hypotheses"]:
                t3["hypotheses"] = ps["hypotheses"]
    st = update(fn)
    try:  # v3.2: every plan hypothesis gets a stable HYPE-NNN id in Research Memory (customer scenario 1)
        from .research import sync_from_plan
        sync_from_plan(st["tier3"].get("hypotheses") or [])
    except Exception:
        pass
    return st


def set_tier3(patch: dict) -> dict:
    def fn(st):
        for k in ("goals", "hypotheses", "constraints"):
            if k in patch and isinstance(patch[k], list):
                st["tier3"][k] = [str(x).strip()[:1000] for x in patch[k] if str(x).strip()]
                st["tier3"][f"{k}_manual"] = True
        if "notes" in patch:
            st["tier3"]["notes"] = str(patch["notes"])[:8000]
    return update(fn)


# ------------------------------------------------------------------ context for agents
def memory_block(tool: str = "", session_id: str = "", budget: int = 9000, purged: set | None = None) -> str:
    """Tier 3 + relevant Tier 2 episodes, ready to append to an agent's system prompt."""
    st = load()
    purged = purged or set()
    t3 = st["tier3"]
    parts = []
    if t3.get("goals"):
        parts.append("Research goals:\n" + "\n".join(f"- {g}" for g in t3["goals"]))
    if t3.get("hypotheses"):
        parts.append("Hypotheses:\n" + "\n".join(f"- {h}" for h in t3["hypotheses"]))
    if t3.get("constraints"):
        parts.append("Constraints:\n" + "\n".join(f"- {c}" for c in t3["constraints"]))
    bm = {k: v for k, v in (t3.get("best_metrics") or {}).items() if f"metric:{k}" not in purged}
    if bm:
        parts.append("Best metrics so far: " + ", ".join(f"{k}={v['value']:.4g} ({v['direction']})" for k, v in list(bm.items())[:20]))
    eps = [e for e in st["tier2"] if e["id"] not in purged]
    mine = [e for e in eps if session_id and e.get("session") == session_id]
    others = [e for e in reversed(eps) if e not in mine]
    used, chosen = 0, []
    for e in mine + others:
        txt = f"### {e['title']} ({e['created'][:10]}, {e.get('source', '')})\n{e['summary']}"
        if used + len(txt) > budget:
            break
        chosen.append(txt)
        used += len(txt)
    if chosen:
        parts.append("Episodic memory (summaries of earlier work; the earlier turns of THIS conversation are summarized first):\n\n" + "\n\n".join(chosen))
    return "\n\n".join(parts)


def status() -> dict:
    st = load()
    cfg = load_config()["memory"]
    t1 = tier1(st)
    t2_tok = sum(tokens(e.get("summary", "")) for e in st["tier2"])
    out = {"tier1": t1, "tier2": {"count": len(st["tier2"]), "tokens": t2_tok, "episodes": list(reversed(st["tier2"]))},
           "tier3": st["tier3"], "decisions": st["decisions"], "settings": cfg, "stats": st.get("stats", {}),
           "busy": _running["busy"]}
    try:  # v3.2 additions (page-store, research memory counts, active watermark)
        from . import pages, research
        rs = research.load()
        out["v2"] = {"enabled": bool(cfg.get("v2_pipeline", True)), "pages": len(pages.list_pages(100000)),
                     "high": cfg["high_watermark_tokens"], "low": cfg["low_watermark_tokens"], "chunk": cfg["chunk_tokens"],
                     "hypotheses": len(rs["hypotheses"]), "experiments": len(rs["experiments"]), "failures": len(rs["failures"])}
    except Exception as e:
        out["v2"] = {"error": str(e)}
    return out


def delete_episode(eid: str):
    update(lambda st: st.__setitem__("tier2", [e for e in st["tier2"] if e["id"] != eid]))


def edit_episode(eid: str, patch: dict) -> dict:
    out = {}

    def fn(st):
        for e in st["tier2"]:
            if e["id"] == eid:
                for k in ("title", "summary", "pinned"):
                    if k in patch:
                        e[k] = patch[k]
                out.update(e)
    update(fn)
    return out


# ------------------------------------------------------------------ background worker
async def worker(stop_event: asyncio.Event):
    """Started with the app: checks Tier 1 periodically and summarizes the active project when it is too big."""
    await asyncio.sleep(20)
    while not stop_event.is_set():
        try:
            cfg = load_config()["memory"]
            if cfg.get("auto_summarize", True):
                limit = int(cfg["high_watermark_tokens"] if cfg.get("v2_pipeline", True) else cfg["tier1_threshold_tokens"])
                if tier1()["tokens"] >= limit:
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
