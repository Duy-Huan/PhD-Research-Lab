"""Working Memory (CONTEXT_MEMORY.md tier "Working"): the live state of the current session — what the researcher is
doing right now (current_task) and the runtime state of the agents. Short-lived, overwritten freely; long-term facts
live in research.py / knowledge.py and the legacy Tier 2/3 store."""
from __future__ import annotations

from . import mem_dir, tier1
from .store import JsonStore, now

_store = JsonStore(lambda: mem_dir() / "working.json", {"current_task": {}, "agents": {}, "focus": {}}, versioned=False)
MAX_TASK = 1200


def note_task(tool: str, text: str, session_id: str = "") -> None:
    """Remember the latest request the researcher made (called when an agent receives a new request)."""
    text = (text or "").strip()
    if not text:
        return

    def put(st):
        st["current_task"] = {"tool": tool, "text": text[:MAX_TASK], "session": session_id, "updated": now()}
    _store.update(put)


def set_focus(hypothesis_id: str = "", experiment_id: str = "") -> dict:
    """v3.3: the researcher's explicit focus (active hypothesis / current experiment) of the Research State."""
    from . import research
    rs = research.load()
    if hypothesis_id and not any(h["id"] == hypothesis_id for h in rs["hypotheses"]):
        raise research.ResearchError(f"Hypothesis {hypothesis_id} not found")
    if experiment_id and not any(e["id"] == experiment_id for e in rs["experiments"]):
        raise research.ResearchError(f"Experiment {experiment_id} not found")

    def put(st):
        st["focus"] = {"hypothesis_id": hypothesis_id, "experiment_id": experiment_id, "updated": now()}
        return st["focus"]
    return _store.update(put)


def set_agent_state(agent: str, state: str, detail: str = "") -> None:
    def put(st):
        st["agents"][agent] = {"state": state[:40], "detail": detail[:300], "updated": now()}
    _store.update(put)


def get() -> dict:
    return _store.load()


def _jobs_lines(limit: int = 3) -> list:
    out = []
    try:
        from ..sandbox import JOBS, list_runs
        running = [j for j in JOBS.values() if j.status == "running"]
        for j in running[:limit]:
            out.append(f"- RUNNING {j.kind} `{j.cmd[:100]}` ({j.mode}, id {j.id})")
        for r in list_runs(limit):
            if any(j.id == r["id"] for j in running):
                continue
            ms = ", ".join(f"{k}={v:.4g}" for k, v in list((r.get("metrics") or {}).items())[:5] if isinstance(v, (int, float)))
            out.append(f"- run {r['id']} {r.get('status')} (exit {r.get('exit_code')}) `{(r.get('cmd') or '')[:80]}`" + (f" → {ms}" if ms else ""))
    except Exception:
        pass
    return out[: limit * 2]


def state_lines(tool: str = "") -> list:
    """Bullet lines of the current working state (deterministic order)."""
    st = get()
    lines = []
    t = st.get("current_task") or {}
    if t.get("text"):
        lines.append(f"- Current task ({t.get('tool') or tool}, {t.get('updated', '')[:16]}): {t['text'][:600]}")
    for a, s in sorted((st.get("agents") or {}).items()):
        if s.get("state") not in ("", "idle", "done"):
            lines.append(f"- Agent {a}: {s['state']}" + (f" — {s['detail']}" if s.get("detail") else ""))
    lines += _jobs_lines()
    try:
        t1 = tier1()
        lines.append(f"- Uncompressed short-term memory: {t1['tokens']:,} tokens")
    except Exception:
        pass
    return lines
