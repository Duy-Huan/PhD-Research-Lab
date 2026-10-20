"""Research State (v3.3 §5, Phase 2): the structured "where are we" of a project, derived live from the stores.

    objective            Tier-3 goals
    active_hypotheses    status testing (then proposed); the researcher's focus (working.json "focus") comes first
    current_experiment   focus experiment, else the latest experiment of the active hypothesis, else the latest one
    constraints          Tier-3 constraints (+ hardware lines extracted from them)
    recent_decisions     locked, not superseded, newest first
    known_failures       failures of the active hypothesis first, then the newest
    best_results         validated evidence metrics + best sandbox metrics
    datasets / models    seen in experiments (active hypothesis first)

Nothing is copied: the state is recomputed from Research/Evidence/Tier-3 memory on every call (cheap, cached by the
memory fingerprint), so it can never drift from the records. It survives restarts, context resets and provider changes
because it lives in the project files, not in a conversation.
"""
from __future__ import annotations

import re

from . import cache

HW_RE = re.compile(r"(?i)\b(gpu|vram|cuda|rtx|gb|ram|cpu|a100|h100|memory)\b")
_cache = cache.LRU(8)


def _ts(x: dict) -> str:
    return x.get("updated") or x.get("created") or ""


def current(purged: set | None = None) -> dict:
    purged = set(purged or ())
    key = (cache.fingerprint(), tuple(sorted(purged)), _focus_key())
    hit = _cache.get(key)
    if hit is not None:
        return hit
    return _cache.put(key, _compute(purged))


def _focus_key() -> tuple:
    try:
        from .working import get
        f = get().get("focus") or {}
        return (f.get("hypothesis_id", ""), f.get("experiment_id", ""))
    except Exception:
        return ("", "")


def _compute(purged: set) -> dict:
    from . import evidence, load, research
    st, rs = load(), research.load()
    t3 = st["tier3"]
    focus_h, focus_e = _focus_key()
    hyps = [h for h in rs["hypotheses"] if h["id"] not in purged]
    # active = the focus hypothesis + those under test; proposed ones only when nothing is being tested
    testing = [h for h in hyps if h["status"] == "testing" or h["id"] == focus_h]
    pool = testing or [h for h in hyps if h["status"] == "proposed"]
    active = sorted(pool, key=lambda h: (h["id"] != focus_h, h["status"] != "testing", _neg(_ts(h)), h["id"]))
    exps = [e for e in rs["experiments"] if e["id"] not in purged]
    act_ids = {h["id"] for h in active[:2]}
    cur = next((e for e in exps if e["id"] == focus_e), None) \
        or next(iter(sorted([e for e in exps if e.get("hypothesis_id") in act_ids], key=lambda e: (_neg(_ts(e)), _neg(e["id"])))), None) \
        or next(iter(sorted(exps, key=lambda e: (_neg(_ts(e)), _neg(e["id"])))), None)  # same second → the later id
    fails = [f for f in rs["failures"] if f["id"] not in purged]
    fails.sort(key=lambda f: (f.get("hypothesis_id") not in act_ids, _neg(f.get("created", "")), _neg(f["id"])))
    linked = [f for f in fails if f.get("hypothesis_id") in act_ids]
    fails = linked + [f for f in fails if f not in linked][:max(0, 3 - len(linked))]
    # decision ids are random and timestamps have 1-s resolution: the write order (list position) breaks ties
    order_of = {d["id"]: i for i, d in enumerate(st["decisions"])}
    decs = [d for d in st["decisions"] if d.get("locked") and not d.get("superseded_by") and d["id"] not in purged]
    decs.sort(key=lambda d: (_neg(d.get("created", "")), -order_of[d["id"]]))
    cons = [c for i, c in enumerate(t3.get("constraints") or []) if f"con:{i}" not in purged]
    best = {}
    try:
        for ev in evidence.load()["evidence"]:
            m = ev.get("metric") or {}
            if ev.get("status") != "validated" or not m.get("name") or ev["id"] in purged:
                continue
            k = m["name"]
            if k not in best or m["value"] > best[k]["value"]:
                best[k] = {"value": m["value"], "source": ev.get("experiment_id") or ev["id"], "evidence_id": ev["id"]}
    except Exception:
        pass
    for k, v in (t3.get("best_metrics") or {}).items():
        if f"metric:{k}" not in purged and k not in best:
            best[k] = {"value": v["value"], "source": f"run:{v['run']}", "direction": v.get("direction", "")}
    # current baseline: the newest experiment the researcher called a baseline (title/conclusion), what new results are
    # compared against when planning (v3.3 §5: "previous experiments … current baseline")
    bl = next(iter(sorted([e for e in exps if re.search(r"(?i)\bbaseline\b", f"{e.get('title', '')} {e.get('conclusion', '')}")],
                          key=lambda e: (_neg(_ts(e)), _neg(e["id"])))), None)
    order = [e for e in exps if e.get("hypothesis_id") in act_ids] + exps
    datasets = list(dict.fromkeys(e["dataset_version"] for e in order if e.get("dataset_version")))
    models = list(dict.fromkeys(e["model_id"] for e in order if e.get("model_id")))
    return {
        "objective": [g for i, g in enumerate(t3.get("goals") or []) if f"goal:{i}" not in purged],
        "active_hypotheses": [{"id": h["id"], "text": h["text"], "status": h["status"]} for h in active[:4]],
        "current_experiment": ({k: cur.get(k, "") for k in ("id", "title", "hypothesis_id", "dataset_version", "git_sha",
                                                            "clearml_task_id", "verdict", "conclusion")} if cur else None),
        "baseline": ({k: bl.get(k, "") for k in ("id", "title", "dataset_version", "conclusion")} if bl else None),
        "constraints": cons,
        "hardware": [c for c in cons if HW_RE.search(c)],
        "recent_decisions": [{"id": d["id"], "kind": d.get("kind", ""), "text": d["text"]} for d in decs[:6]],
        "known_failures": [{"id": f["id"], "text": f["text"], "lesson": f.get("lesson") or f.get("avoidance_rule") or f.get("reason", ""),
                            "hypothesis_id": f.get("hypothesis_id", "")} for f in fails[:8]],
        "best_results": best,
        "datasets": datasets[:8],
        "models": models[:8],
        "focus": {"hypothesis_id": focus_h, "experiment_id": focus_e},
        "context_version": cache.version(),
    }


def _neg(ts: str) -> str:
    """Sort key that orders ISO timestamps newest first inside an ascending sort."""
    return "".join(chr(0x10FFFF - ord(c)) for c in (ts or ""))


def ids(state: dict) -> set:
    """Every record id the state refers to (used for state-aware retrieval and to protect them in the compiler)."""
    out = {h["id"] for h in state["active_hypotheses"]} | {d["id"] for d in state["recent_decisions"]} \
        | {f["id"] for f in state["known_failures"]}
    for k in ("current_experiment", "baseline"):
        if state.get(k):
            out.add(state[k]["id"])
    return out


def lines(state: dict, max_failures: int = 4) -> list:
    """Compact bullet lines of the state (deterministic) — the RESEARCH STATE section of the compiled context."""
    out = []
    for g in state["objective"][:2]:
        out.append(f"- Objective: {_one(g, 300)}")
    for h in state["active_hypotheses"][:2]:
        out.append(f"- Active hypothesis [{h['id']}] ({h['status']}): {_one(h['text'], 220)}")
    e = state.get("current_experiment")
    if e:
        bits = [x for x in (e.get("dataset_version") and f"dataset {e['dataset_version']}", e.get("git_sha") and f"git {e['git_sha'][:10]}",
                             e.get("clearml_task_id") and f"ClearML `{e['clearml_task_id']}`") if x]
        out.append(f"- Current experiment [{e['id']}]: {_one(e['title'], 140)}" + (f" ({', '.join(bits)})" if bits else "")
                   + (f" → {_one(e['conclusion'], 160)}" if e.get("conclusion") else ""))
    b = state.get("baseline")
    if b and b["id"] != (e or {}).get("id"):
        out.append(f"- Baseline [{b['id']}]: {_one(b['title'], 120)}" + (f" → {_one(b['conclusion'], 140)}" if b.get("conclusion") else ""))
    for c in state["constraints"][:4]:
        out.append(f"- Constraint: {_one(c, 220)}")
    for d in state["recent_decisions"][:4]:
        out.append(f"- Decision [{d['id']}] ({d['kind']}): {_one(d['text'], 200)}")
    for f in state["known_failures"][:max_failures]:
        out.append(f"- Known failure [{f['id']}]: {_one(f['text'], 160)}" + (f" — lesson: {_one(f['lesson'], 160)}" if f.get("lesson") else ""))
    if state["best_results"]:
        out.append("- Best results: " + ", ".join(f"{k}={v['value']:.4g} ({v['source']})" for k, v in list(state["best_results"].items())[:6]))
    return out


def _one(t: str, n: int) -> str:
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"
