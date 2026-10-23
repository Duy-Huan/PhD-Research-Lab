"""Module D — Smart Engine & Skill Router (v6.4.2).

Policy-driven routing layer over PhD Lab's capability registry:
1. Deterministic non-LLM action first (`paper.discover`, `paper.download`, `figure.*`, `experiment.*`).
2. Local/free or subscription-backed CLI runtime when compatible and healthy.
3. Never silently activate metered/billable API endpoints on quota exhaustion.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from backend.agent import capabilities as CAP
from backend.agent.mission_contracts import Task
from backend.intelligence import observability
from backend.knowledge import research_store as S
from backend.research_engines import registry


class RoutePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(min_length=1, max_length=120)
    mission_id: str = Field(default="", max_length=120)
    task_id: str = Field(default="preview-task", max_length=120)
    capability: str = Field(min_length=1, max_length=80)
    preferred_engine: str = Field(default="deterministic", max_length=40)
    fallback_engines: list[str] = Field(default_factory=list, max_length=4)
    allow_metered_api: bool = False
    simulate_quota_exhausted: bool = False


def preview_route(req: RoutePreviewRequest, persist: bool = True) -> dict:
    """Evaluate capability, cost policy, circuit breakers, and runtime health for a task."""
    S.get_topic(req.topic_id)
    if req.capability not in CAP.META:
        raise ValueError(f"Unknown capability: {req.capability}")

    desc, is_deterministic, perms, compatible = CAP.META[req.capability]

    # Rule 1: Deterministic operations ALWAYS route to deterministic executor (0 LLM calls)
    if is_deterministic:
        decision = {
            "task_id": req.task_id,
            "topic_id": req.topic_id,
            "mission_id": req.mission_id,
            "capability": req.capability,
            "selected_engine": "deterministic",
            "status": "ready",
            "deterministic": True,
            "llm_calls": 0,
            "cost_policy": "zero_cost_deterministic",
            "metered_api_fallback": "disabled",
            "rationale": f"Capability '{req.capability}' is a deterministic non-LLM operation; routed directly to local executor.",
            "evaluated_candidates": [{"engine": "deterministic", "eligible": True, "ready": True}],
            "session_portability": "not_applicable",
            "decided_at": S.now(),
        }
    else:
        if req.simulate_quota_exhausted:
            decision = {
                "task_id": req.task_id,
                "topic_id": req.topic_id,
                "mission_id": req.mission_id,
                "capability": req.capability,
                "selected_engine": "none",
                "status": "quota_limited",
                "deterministic": False,
                "llm_calls": 0,
                "cost_policy": "metered_api_fallback_disabled",
                "metered_api_fallback": "disabled",
                "rationale": "Subscription/local quota exhausted; task paused cleanly. Metered API fallback is strictly disabled.",
                "evaluated_candidates": [],
                "session_portability": "not_portable",
                "decided_at": S.now(),
            }
        else:
            candidates = [req.preferred_engine, *req.fallback_engines]
            if not candidates or candidates == ["deterministic"]:
                candidates = list(compatible)
            evaluated = []
            selected = None
            with S.db() as c:
                breakers = {
                    r["provider"]: r["until_at"]
                    for r in c.execute("SELECT provider, until_at FROM provider_breakers")
                    if datetime.fromisoformat(r["until_at"]) > datetime.now(timezone.utc)
                }

            for eng in candidates:
                if eng not in compatible:
                    evaluated.append({"engine": eng, "eligible": False, "ready": False, "reason": "Incompatible capability"})
                    continue
                if eng in breakers:
                    evaluated.append({"engine": eng, "eligible": True, "ready": False, "reason": f"Circuit breaker open until {breakers[eng]}"})
                    continue
                if eng == "app":
                    ready = True
                    reason = "Configured local/subscription application provider ready"
                else:
                    try:
                        h = registry.get(eng).health()
                        ready = bool(h.get("ready"))
                        reason = h.get("detail") or ("Ready" if ready else "Engine not ready")
                    except Exception as exc:
                        ready = False
                        reason = str(exc)
                evaluated.append({"engine": eng, "eligible": True, "ready": ready, "reason": reason})
                if ready and selected is None:
                    selected = eng

            decision = {
                "task_id": req.task_id,
                "topic_id": req.topic_id,
                "mission_id": req.mission_id,
                "capability": req.capability,
                "selected_engine": selected or "none",
                "status": "ready" if selected else "blocked_no_healthy_engine",
                "deterministic": False,
                "llm_calls": 1 if selected else 0,
                "cost_policy": "subscription_or_local_only",
                "metered_api_fallback": "disabled",
                "rationale": (
                    f"Selected '{selected}' based on capability eligibility, circuit-breaker health, and zero-metered-API policy."
                    if selected
                    else "No eligible healthy runtime available; pausing task without implicit paid fallback."
                ),
                "evaluated_candidates": evaluated,
                "session_portability": "not_portable",
                "decided_at": S.now(),
            }

    if persist:
        with S.db() as c:
            c.execute(
                "INSERT INTO routing_decisions VALUES(?,?,?,?,?,?,?,?)",
                (
                    S.uid(),
                    req.topic_id,
                    req.mission_id,
                    req.task_id,
                    decision["selected_engine"],
                    decision["cost_policy"],
                    S.dumps(decision),
                    decision["decided_at"],
                ),
            )
        observability.emit_trace_event(
            topic_id=req.topic_id,
            mission_id=req.mission_id,
            task_id=req.task_id,
            runtime_id=decision["selected_engine"],
            event_type="ROUTING_DECISION",
            span_name="engine_route.decide",
            payload={
                "capability": req.capability,
                "selected_engine": decision["selected_engine"],
                "status": decision["status"],
                "cost_policy": decision["cost_policy"],
            },
        )
    return decision
