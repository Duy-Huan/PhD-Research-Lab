"""Memory lifecycle (v3.3 §11, v3.4 §13): candidate → classification → deduplication → review → persistent memory.

States of research information in this app
    ephemeral   current task / agent runtime state            working.json (overwritten freely)
    working     raw chat turns + run logs not yet compressed  chat sessions, Tier 1
    episodic    compressed memos with raw-page pointers       Tier 2 (+ tier2_archive after consolidation)
    research    hypotheses, experiments, failures, decisions  research.json, project_state.json decisions
    knowledge   papers (live from the library)                library.json
    evidence    claims and evidence with provenance           evidence.json
    candidate   proposed but NOT yet memory                   candidates.json (this module)

Nothing an AI model or an external provider says becomes memory on its own: provider output, MCP record_* tools and
agent suggestions are written here as candidates, classified (ai_suggestion | ai_claim | verified_observation |
experiment_result | human_decision | validated_evidence), checked against existing records for duplicates, and only
committed to the real store by approve() — an explicit researcher action — with origin, provider, session and request
kept on the committed record. Rejected and duplicate candidates are kept (audit), never silently dropped.
"""
from __future__ import annotations

import re

from backend.memory import mem_dir
from backend.memory.embeddings import tokenize
from backend.memory.store import JsonStore, now

_store = JsonStore(lambda: mem_dir() / "candidates.json", {"seq": {}, "candidates": []}, versioned=False)
KINDS = ("observation", "decision", "experiment_result", "failure", "claim", "note")
STATUS = ("pending", "approved", "rejected", "duplicate")
ID_RE = re.compile(r"^CAND-\d{3,6}$")
DUP = 0.85


class LifecycleError(ValueError):
    pass


def _norm_tokens(t: str) -> set:
    return {x for x in tokenize(t) if len(x) > 2}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def classify(kind: str, origin: str, payload: dict) -> str:
    human = origin == "human"
    if kind == "decision":
        return "human_decision" if human else "ai_suggestion"
    if kind == "experiment_result":
        return "experiment_result" if (payload.get("experiment_id") or payload.get("run_id")) else "ai_claim"
    if kind == "observation":
        return "verified_observation" if human or payload.get("run_id") else "ai_claim"
    if kind == "claim":
        return "ai_claim" if not human else "validated_evidence"
    return "ai_suggestion" if not human else "verified_observation"


def _existing_texts(kind: str) -> list:
    from backend.memory import evidence, load, research
    if kind == "decision":
        return [(d["id"], d["text"]) for d in load()["decisions"]]
    if kind == "failure":
        return [(f["id"], f["text"]) for f in research.load()["failures"]]
    if kind == "claim":
        return [(c["id"], c["text"]) for c in evidence.load()["claims"]]
    if kind in ("observation", "experiment_result"):
        return [(e["id"], e.get("text", "")) for e in evidence.load()["evidence"] if e.get("text")]
    from backend.memory.notes import load_notes  # v4.2: approved notes (memory types knowledge / open question / hypothesis)
    return [(f"note:{n['id']}", n["text"]) for n in load_notes()]


def _validate(kind: str, payload: dict) -> dict:
    if kind not in KINDS:
        raise LifecycleError(f"kind must be one of {', '.join(KINDS)}")
    p = {k: v for k, v in (payload or {}).items() if v not in (None, "")}
    text = str(p.get("text") or "").strip()
    if not text:
        raise LifecycleError("text is required")
    p["text"] = text[:4000]
    for k in ("experiment_id", "hypothesis_id", "claim_id"):
        if p.get(k) and not re.fullmatch(r"(EXP|HYPE|CLM)-\d{3,6}", str(p[k])):
            raise LifecycleError(f"invalid {k}")
    if p.get("evidence_ids"):
        if not isinstance(p["evidence_ids"], list) or not all(re.fullmatch(r"(EVID|EXP|CLM|FAIL|HYPE)-\d{3,6}", str(x)) for x in p["evidence_ids"]):
            raise LifecycleError("evidence_ids must be a list of EVID-/EXP-/CLM-/FAIL-/HYPE- ids")
    if p.get("metric"):
        m = p["metric"]
        if not isinstance(m, dict) or not m.get("name"):
            raise LifecycleError("metric needs a name and a numeric value")
        try:
            p["metric"] = {"name": str(m["name"])[:60], "value": float(m["value"]), "unit": str(m.get("unit") or "")[:20]}
        except (KeyError, TypeError, ValueError):
            raise LifecycleError("metric value must be a number")
    if p.get("stance") and p["stance"] not in ("supports", "refutes", "neutral"):
        raise LifecycleError("stance must be supports, refutes or neutral")
    if p.get("verdict") and p["verdict"] not in ("supports", "refutes", "inconclusive"):
        raise LifecycleError("verdict must be supports, refutes or inconclusive")
    return p


def propose(kind: str, payload: dict, origin: str = "human", provider: str = "", session: str = "", request_id: str = "",
            agent: str = "") -> dict:
    """Write a candidate (never memory). Returns it with its classification and duplicate check."""
    p = _validate(kind, payload)
    toks = _norm_tokens(p["text"])
    dup_of = next((rid for rid, t in _existing_texts(kind) if _jaccard(toks, _norm_tokens(t)) >= DUP), "")
    conf = 0.4 + (0.2 if p.get("experiment_id") or p.get("run_id") else 0) + (0.2 if p.get("metric") else 0) \
        + (0.2 if origin == "human" else 0)

    def put(st):
        pend = next((c for c in st["candidates"] if c["status"] == "pending" and c["kind"] == kind
                     and _jaccard(toks, _norm_tokens(c["payload"]["text"])) >= DUP), None)
        n = int(st["seq"].get("CAND", 0)) + 1
        st["seq"]["CAND"] = n
        c = {"id": f"CAND-{n:03d}", "kind": kind, "payload": p, "classification": classify(kind, origin, p),
             "origin": {"type": origin[:20], "provider": provider[:40], "session": session[:80], "request_id": request_id[:40],
                        "agent": agent[:40]},
             "confidence": round(min(1.0, conf), 2), "status": "pending", "duplicate_of": dup_of or (pend["id"] if pend else ""),
             "created": now(), "reviewed": ""}
        if c["duplicate_of"]:
            c["status"] = "duplicate"
        st["candidates"].append(c)
        return c
    return _store.update(put)


def list_candidates(status: str = "", limit: int = 200) -> list:
    cs = _store.load()["candidates"]
    return [c for c in cs if not status or c["status"] == status][-limit:]


def get(cid: str) -> dict:
    if not ID_RE.match(cid or ""):
        raise LifecycleError("Invalid candidate id")
    c = next((x for x in _store.load()["candidates"] if x["id"] == cid), None)
    if not c:
        raise LifecycleError(f"{cid} not found")
    return c


def _commit(c: dict) -> dict:
    from backend.memory import add_decision, evidence, research
    p, o = c["payload"], c["origin"]
    via = f"{o.get('provider') or o.get('type')} via {c['id']}"
    if c["kind"] == "decision":
        d = add_decision(p["text"], p.get("decision_kind") or "direction", source=f"proposed by {via}", locked=True,
                         evidence_ids=p.get("evidence_ids"), origin="human", provider=o.get("provider", ""),
                         session=o.get("session", ""), supersedes=p.get("supersedes", ""))
        return {"type": "decision", "id": d["id"]}
    if c["kind"] == "failure":
        f = research.add_failure(p["text"], hypothesis_id=p.get("hypothesis_id", ""), run_id=p.get("run_id", ""),
                                 reason=p.get("cause", ""), origin=f"approved:{via}",
                                 **{k: p[k] for k in research.FAIL_FIELDS if p.get(k)})
        return {"type": "failure", "id": f["id"]}
    if c["kind"] == "claim":
        cl = evidence.add_claim(p["text"], hypothesis_id=p.get("hypothesis_id", ""), source_refs=p.get("source_refs"),
                                origin=f"approved:{via}")
        return {"type": "claim", "id": cl["id"]}
    if c["kind"] == "note":
        from backend.memory.notes import add_note
        n = add_note(p.get("tool") or "data", p["text"], source=f"approved {via}")
        return {"type": "note", "id": f"note:{n['id']}"}
    # observation / experiment_result → (experiment update) + validated evidence (researcher approved it)
    out = {}
    if c["kind"] == "experiment_result" and p.get("experiment_id"):
        patch = {k: p[k] for k in ("observation", "conclusion", "verdict") if p.get(k)}
        patch.setdefault("observation", p["text"])
        research.update_experiment(p["experiment_id"], patch)
        out["experiment"] = p["experiment_id"]
    ev = evidence.add_evidence({"claim_id": p.get("claim_id", ""), "experiment_id": p.get("experiment_id", ""),
                                "source_type": "experiment" if p.get("experiment_id") else "observation",
                                "stance": p.get("stance") or "neutral", "metric": p.get("metric"), "text": p["text"],
                                "run_id": p.get("run_id", ""), "status": "validated"}, origin="human")
    return {**out, "type": "evidence", "id": ev["id"]}


def approve(cid: str, edits: dict | None = None, reviewer: str = "researcher") -> dict:
    """Explicit researcher action: commit the candidate (optionally edited) to the real store."""
    c = get(cid)
    if c["status"] not in ("pending", "duplicate"):
        raise LifecycleError(f"{cid} is already {c['status']}")
    if edits:
        c = {**c, "payload": _validate(c["kind"], {**c["payload"], **edits})}
    committed = _commit(c)

    def put(st):
        for x in st["candidates"]:
            if x["id"] == cid:
                x.update(status="approved", reviewed=now(), reviewer=reviewer[:60], committed=committed, payload=c["payload"])
                return x
    return _store.update(put)


def reject(cid: str, reason: str = "", reviewer: str = "researcher") -> dict:
    get(cid)

    def put(st):
        for x in st["candidates"]:
            if x["id"] == cid:
                if x["status"] == "approved":
                    raise LifecycleError(f"{cid} was already approved")
                x.update(status="rejected", reviewed=now(), reviewer=reviewer[:60], reason=reason[:500])
                return x
    return _store.update(put)


def annotate(cid: str, **fields) -> dict:
    """v4.2: attach review metadata (conflicts_with, review_reason) to a candidate — never changes its status."""
    get(cid)

    def put(st):
        x = next(c for c in st["candidates"] if c["id"] == cid)
        x.update({k: v for k, v in fields.items() if k in ("conflicts_with", "review_reason")})
        return x
    return _store.update(put)
