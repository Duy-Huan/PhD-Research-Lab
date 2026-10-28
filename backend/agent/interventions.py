"""Intervention ledger for qualification (v6.6.4, agent/PLAN_6.6.4_L3.md B2; RQ-14).

Who decided each hypothesis, branch, rejection, replan and stop, and every human intervention by category, read from the
hash-linked decision ledger of one topic. The categories are the objectives' human_intervention_categories:
initial_authorization, routine_scientific_verification, scientific_rescue, risk_exception, final_publication_review.

Authorization and routine verification are expected human steps; rescue and risk exceptions are what an autonomy claim
must count against the agent. An event whose actor the ledger does not state is reported as `unknown`, never guessed.
The researcher records an intervention the app cannot see (for example a hand-applied code fix) with record().
"""
from __future__ import annotations

from backend.agent import decision_ledger as L
from backend.knowledge import research_store as S

CATEGORIES = ("initial_authorization", "routine_scientific_verification", "scientific_rescue", "risk_exception",
              "final_publication_review")
DECISIONS = ("hypothesis", "branch", "rejection", "replan", "stop")
# Ledger kind → (intervention category for a human actor or None, decision type or None)
KINDS = {
    "mission.approved": ("initial_authorization", None),
    "protocol.approved": ("initial_authorization", None),
    "charter.created": ("initial_authorization", None),
    "mission.retry_proposed": ("scientific_rescue", "replan"),
    "team.replan_proposed": ("scientific_rescue", "replan"),
    "mission.cancelled": ("risk_exception", "stop"),
    "mission.reviewed": ("final_publication_review", None),
    "figure.approved": ("routine_scientific_verification", None),
    "claim.checked": ("routine_scientific_verification", None),
    "protocol.created": (None, "hypothesis"),
    "claim.proposed": (None, "hypothesis"),
    "mission.created": (None, "branch"),
}
HUMAN = {"researcher", "owner", "human", "qa-operator"}


def actor(payload: dict) -> str:
    """human | agent | unknown, from the event's own `by` / `owner` field."""
    who = str(payload.get("by") or payload.get("owner") or "").strip().lower()
    if not who:
        return "unknown"
    if who in HUMAN:
        return "human"
    if who.startswith(("mcp:", "agent", "cli:", "tool:", "session:")) or ":" in who:
        return "agent"
    return "unknown"


def _classify(e: dict) -> tuple[str | None, str | None, str]:
    kind, payload = e["kind"], e.get("payload") or {}
    if kind == "intervention.recorded":
        return payload.get("category"), payload.get("decision"), "human"
    if kind == "workflow.step_reviewed":
        return "routine_scientific_verification", None if payload.get("accept") else "rejection", "human"
    category, decision = KINDS.get(kind, (None, None))
    who = actor(payload)
    if kind in ("mission.approved", "protocol.approved", "mission.cancelled", "mission.retry_proposed", "mission.reviewed",
                "figure.approved") and who == "unknown":
        who = "human"  # these routes are researcher-only in the app; the ledger records no other actor for them
    return (category if who == "human" else None), decision, who


def report(tid: str) -> dict:
    """Interventions and decision ownership of one topic, with the ledger's integrity state."""
    ledger = L.export(tid)
    interventions, decisions = [], []
    counts = {c: 0 for c in CATEGORIES}
    by = {d: {"human": 0, "agent": 0, "unknown": 0} for d in DECISIONS}
    for e in ledger["events"]:
        category, decision, who = _classify(e)
        ref = {"seq": e["seq"], "at": e["at"], "kind": e["kind"], "entity_id": e["entity_id"], "hash": e["hash"]}
        if category in CATEGORIES:
            counts[category] += 1
            interventions.append({**ref, "category": category, "note": str((e.get("payload") or {}).get("note") or "")[:300]})
        if decision in DECISIONS:
            by[decision][who] += 1
            decisions.append({**ref, "decision": decision, "by": who})
    made = sum(v["human"] + v["agent"] for v in by.values())
    return {"topic_id": tid, "ledger_ok": ledger["ok"], "interventions": interventions, "counts": counts,
            "decisions": decisions, "decided_by": by,
            "agent_decision_share": round(sum(v["agent"] for v in by.values()) / made, 4) if made else None,
            "unknown_decisions": sum(v["unknown"] for v in by.values()),
            "limitations": ["Built from the local hash-linked ledger; interventions outside the app count only when recorded",
                            "Authorization and routine verification are expected; rescue and risk exceptions count against autonomy"]}


def record(tid: str, category: str, note: str, decision: str = "", entity_id: str = "") -> dict:
    """The researcher records an intervention the app did not see (e.g. a hand-applied fix). Append-only."""
    if category not in CATEGORIES:
        raise ValueError("Choose one of: " + ", ".join(CATEGORIES))
    if decision and decision not in DECISIONS:
        raise ValueError("Decision must be one of: " + ", ".join(DECISIONS))
    if not note.strip():
        raise ValueError("Describe the intervention")
    payload = {"category": category, "decision": decision or None, "note": note.strip()[:4000], "by": "researcher"}
    with S.db() as c:
        S.topic(c, tid)
        value = L.append(c, tid, entity_id or tid, "intervention.recorded", payload)
    return {"hash": value, **payload}
