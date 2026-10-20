"""Automated memory compression (CONTEXT_MEMORY.md §4) — the single WRITER of long-term memory.

1. Token Watermark Monitor  — Tier 1 (uncompressed chat turns + run logs) is measured by the background worker; at the
   HIGH watermark (memory.high_watermark_tokens, 16 000) the oldest material is compressed until what is left is at the
   LOW watermark (memory.low_watermark_tokens, 2 000), always keeping the last memory.min_keep_messages of each chat raw.
   Small working context = short prompts = small KV cache on the 12 GB RTX 3060.
2. Hierarchical Reduce      — the selected turns are cut into chunks of memory.chunk_tokens (3 500); every chunk is
   summarised into a strict JSON memo by the local summarizer model (parallel, bounded by memory.parallel_summaries,
   each call under memory.summary_timeout_s); when one chat produced several memos they are reduced again into one
   episode (a two-level tree, TREEFRAG-style). If a model cannot produce JSON the Markdown answer is kept.
3. Graph Entity Wiring      — run ids, ClearML task ids, git SHAs and HYPE/EXP/FAIL ids found in the raw chunk and in the
   memo become `links` of the episode, so the context graph and graph retrieval connect it to the experiments.

Write isolation (after GAM): raw turns are first snapshotted into the immutable page-store; episodes only point to
pages. "Purging" old logs means advancing the Tier-1 pointer (they are no longer injected) — chat files are never deleted.
"""
from __future__ import annotations

import asyncio
import json
import re
import secrets

from . import (SUMMARY_SYS, _consolidate, _running, _sessions, _split_title, _summarize_runs, load, refresh_tier3,
               tier1, tokens, update)
from .pages import add_page
from .store import now

MEMO_SYS = """You are the Memory Summarization Agent of a long-running PhD research project. Compress the excerpt into a
memo another AI can rely on months later. Keep every concrete fact: decisions (chosen AND rejected directions), hypotheses
and their status, numbers/metrics with their setting, dataset/model names, parameters, bugs and fixes, run ids, ClearML
task ids, git commits, open questions and next steps. Never invent anything; omit greetings and repetition.
Return ONLY one JSON object (no Markdown fences):
{"title": "one line",
 "summary": "<= 180 words, plain prose",
 "facts": ["..."], "decisions": ["..."],
 "metrics": [{"name": "...", "value": "...", "context": "..."}],
 "hypotheses": [{"ref": "HYPE-001 or H2 or empty", "text": "...", "status": "proposed|testing|supported|refuted|inconclusive"}],
 "failures": ["..."], "open_questions": ["..."], "next_steps": ["..."]}"""

REDUCE_SYS = MEMO_SYS.replace("Compress the excerpt", "Merge these consecutive memos of ONE conversation (oldest first) "
                                                   "into a single memo; later memos override earlier ones")

ENTITY_RES = {
    "run": re.compile(r"\b\d{8}-\d{6}-[0-9a-f]{4}\b"),
    "clearml": re.compile(r"\b[0-9a-f]{32}\b"),
    "research": re.compile(r"\b(?:HYPE|EXP|FAIL)-\d{3,6}\b"),
    "git": re.compile(r"(?i)(?:commit|sha|git)[\s:=#@`]*([0-9a-f]{7,40})\b"),
}
LISTS = ("facts", "decisions", "failures", "open_questions", "next_steps")


def entities(text: str) -> list:
    """Deterministic links found in text: run:<id>, clearml:<task>, git:<sha>, HYPE-/EXP-/FAIL- ids."""
    t = text or ""
    out = [f"run:{m}" for m in ENTITY_RES["run"].findall(t)]
    out += [f"clearml:{m}" for m in ENTITY_RES["clearml"].findall(t)]
    out += ENTITY_RES["research"].findall(t)
    out += [f"git:{m[:12]}" for m in ENTITY_RES["git"].findall(t) if re.search(r"[a-f]", m) and re.search(r"\d", m)]
    return list(dict.fromkeys(out))


def parse_memo(text: str, fallback_title: str) -> dict:
    """Strict JSON memo → normalised dict; free text → {title, summary} (kept verbatim, never re-invented)."""
    from ..llm import extract_json
    try:
        d = extract_json(text)
        if not isinstance(d, dict) or not str(d.get("summary") or "").strip():
            raise ValueError("no summary")
    except Exception:
        title, body = _split_title(text, fallback_title)
        return {"title": title, "summary": body.strip(), "structured": False}
    memo = {"title": str(d.get("title") or fallback_title).strip()[:160], "summary": str(d["summary"]).strip()[:4000], "structured": True}
    for k in LISTS:
        memo[k] = [str(x).strip()[:600] for x in (d.get(k) or []) if str(x).strip()][:20]
    memo["metrics"] = [{"name": str(m.get("name", ""))[:80], "value": str(m.get("value", ""))[:60], "context": str(m.get("context", ""))[:200]}
                       for m in (d.get("metrics") or []) if isinstance(m, dict) and m.get("name")][:20]
    memo["hypotheses"] = [{"ref": str(h.get("ref", ""))[:20], "text": str(h.get("text", ""))[:400], "status": str(h.get("status", ""))[:20]}
                          for h in (d.get("hypotheses") or []) if isinstance(h, dict) and h.get("text")][:12]
    return memo


def memo_markdown(m: dict) -> str:
    """Markdown body of an episode (what memory_block() and the UI show)."""
    if not m.get("structured"):
        return m["summary"]
    out = [m["summary"]]
    labels = {"facts": "Key facts", "decisions": "Decisions", "failures": "Failures", "open_questions": "Open questions",
              "next_steps": "Next steps"}
    for k, lab in labels.items():
        if m.get(k):
            out.append(f"**{lab}:**\n" + "\n".join(f"- {x}" for x in m[k]))
    if m.get("metrics"):
        out.append("**Metrics:**\n" + "\n".join(f"- {x['name']} = {x['value']}" + (f" ({x['context']})" if x["context"] else "")
                                                for x in m["metrics"]))
    if m.get("hypotheses"):
        out.append("**Hypotheses:**\n" + "\n".join(f"- {(x['ref'] + ' ') if x['ref'] else ''}{x['text']}"
                                                   + (f" [{x['status']}]" if x["status"] else "") for x in m["hypotheses"]))
    return "\n\n".join(out)


def plan(cfg: dict, force: bool = False) -> dict:
    """Which turns to compress: [{sid, tool, title, start, end}] (oldest chats first) — pure function of the stores."""
    mc = cfg["memory"]
    st = load()
    t1 = tier1(st)
    pending, low, high = t1["tokens"], int(mc["low_watermark_tokens"]), int(mc["high_watermark_tokens"])
    out = {"pending_tokens": pending, "high": high, "low": low, "trigger": force or pending >= high, "spans": [], "tokens": 0}
    if not out["trigger"]:
        return out
    need = max(0, pending - low) if not force else pending
    keep = max(0, int(mc.get("min_keep_messages", 2)))
    sessions = sorted(_sessions(), key=lambda s: (s.get("updated") or "", s.get("id", "")))
    taken = 0
    for s in sessions:
        if taken >= need:
            break
        msgs = s.get("messages") or []
        done = int(st["summarized"].get(s["id"], 0))
        stop = len(msgs) - keep
        end = done
        for i in range(done, max(done, stop)):
            if taken >= need:
                break
            taken += tokens(msgs[i].get("content", ""))
            end = i + 1
        if end > done:
            out["spans"].append({"sid": s["id"], "tool": s.get("tool", "data"), "title": s.get("title", ""), "start": done, "end": end})
    out["tokens"] = taken
    return out


def _chunks(msgs: list, start: int, end: int, chunk_tokens: int) -> list:
    """Cut turns [start, end) into chunks: (a, b, llm_text, raw_text). One very long message is truncated for the LLM only."""
    budget = chunk_tokens * 4
    out, a, cur, raw, used = [], start, [], [], 0
    for i in range(start, end):
        m = msgs[i]
        full = f"{m.get('role', '').upper()}: {m.get('content', '')}"
        line = full if len(full) <= budget else full[:budget - 40] + " …[truncated for the summarizer]"
        if cur and used + len(line) > budget:
            out.append((a, i, "\n\n".join(cur), "\n\n".join(raw)))
            a, cur, raw, used = i, [], [], 0
        cur.append(line)
        raw.append(full)
        used += len(line)
    if cur:
        out.append((a, end, "\n\n".join(cur), "\n\n".join(raw)))
    return out


async def _llm(agent_sys: str, user: str, timeout: float, sem: asyncio.Semaphore) -> dict:
    from ..llm import call_agent
    async with sem:
        return await asyncio.wait_for(call_agent("summarizer", agent_sys, user, max_tokens=1100, temperature=0.1), timeout)


async def compress(force: bool = False, cfg: dict | None = None) -> dict:
    """Run one compression pass. Returns a report; never raises for a single failed chunk."""
    from ..config import load_config
    cfg = cfg or load_config()
    mc = cfg["memory"]
    if _running["busy"]:
        return {"skipped": "already running"}
    _running["busy"] = True
    report = {"episodes": 0, "chunks": 0, "pages": 0, "sessions": [], "runs": 0, "errors": [], "pipeline": "v2"}
    try:
        p = plan(cfg, force)
        report.update(pending_tokens=p["pending_tokens"], high=p["high"], low=p["low"])
        if not p["trigger"]:
            refresh_tier3()
            return {**report, "skipped": "below high watermark"}
        sem = asyncio.Semaphore(max(1, int(mc.get("parallel_summaries", 2))))
        timeout = max(30, int(mc.get("summary_timeout_s", 240)))
        by_id = {s["id"]: s for s in _sessions()}
        jobs = []
        for sp in p["spans"]:
            s = by_id.get(sp["sid"])
            if not s:
                continue
            for a, b, text, raw in _chunks(s["messages"], sp["start"], sp["end"], int(mc["chunk_tokens"])):
                user = (f"TOOL: {sp['tool']} · SESSION: {sp['title']}\nCONVERSATION EXCERPT (turns {a + 1}-{b}):\n\n{text}")
                jobs.append((sp, a, b, raw, asyncio.ensure_future(_llm(MEMO_SYS, user, timeout, sem))))
        results = []
        for sp, a, b, raw, fut in jobs:
            try:
                r = await fut
                results.append((sp, a, b, raw, r, None))
            except Exception as e:
                results.append((sp, a, b, raw, None, f"{sp['title'] or sp['sid']} turns {a + 1}-{b}: {type(e).__name__}: {e}"[:300]))
        report["chunks"] = len(results)
        for sp in p["spans"]:
            mine = [x for x in results if x[0] is sp]
            ok = []
            for item in mine:  # commit only the contiguous successful prefix: the Tier-1 pointer must never skip turns
                if item[5]:
                    report["errors"].append(item[5])
                    break
                ok.append(item)
            if not ok:
                continue
            pages, memos, links, engine = [], [], [], ""
            for _sp, a, b, raw, r, _ in ok:
                memo = parse_memo(r["text"], f"{sp['tool']} · {sp['title']}")
                page = add_page("chat", f"chat:{sp['tool']}:{sp['sid']}", [a + 1, b], raw, header=memo["title"])
                pages.append(page["id"])
                memos.append(memo)
                links += entities(raw) + entities(r["text"])
                engine = r.get("engine", engine)
            report["pages"] += len(pages)
            memo = memos[0]
            if len(memos) > 1:  # level-2 node of the memory tree: reduce the chunk memos of this conversation
                try:
                    joined = "\n\n".join(f"MEMO {i + 1}:\n{json.dumps(m, ensure_ascii=False)}" for i, m in enumerate(memos))
                    r2 = await _llm(REDUCE_SYS, joined[:60000], timeout, sem)
                    memo = parse_memo(r2["text"], memos[0]["title"])
                    links += entities(r2["text"])
                except Exception as e:
                    report["errors"].append(f"reduce {sp['title'] or sp['sid']}: {type(e).__name__}: {e}"[:300])
                    memo = {"title": memos[0]["title"], "structured": False,
                            "summary": "\n\n".join(f"### Part {i + 1}: {m['title']}\n{memo_markdown(m)}" for i, m in enumerate(memos))}
            upto = ok[-1][2]
            ep = {"id": "E" + secrets.token_hex(3), "created": now(), "source": f"chat:{sp['tool']}:{sp['sid']}",
                  "tool": sp["tool"], "session": sp["sid"], "title": memo["title"], "summary": memo_markdown(memo),
                  "structured": {k: memo.get(k) for k in LISTS + ("metrics", "hypotheses") if memo.get(k)},
                  "turns": [sp["start"] + 1, upto], "pages": pages, "links": list(dict.fromkeys(links))[:60], "engine": engine,
                  "compressed_tokens": tokens(sum(len(x[3]) for x in ok)), "pipeline": "v2"}

            def put(st2, ep=ep, sid=sp["sid"], upto=upto):
                if int(st2["summarized"].get(sid, 0)) <= ep["turns"][0] - 1:  # no concurrent writer moved the pointer
                    st2["tier2"].append(ep)
                    st2["summarized"][sid] = upto
            update(put)
            report["episodes"] += 1
            report["sessions"].append(sp["title"] or sp["sid"])
        report["runs"] = await _summarize_runs(force)
        report["episodes"] += 1 if report["runs"] else 0
        await _consolidate()
        refresh_tier3()
        update(lambda st2: st2["stats"].update(last_summary=now(), last_report={k: v for k, v in report.items() if k != "sessions"}))
        return report
    finally:
        _running["busy"] = False
