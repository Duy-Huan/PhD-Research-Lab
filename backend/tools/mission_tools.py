"""Mission capabilities as registry tools (v6.6.2: one tool system for agents).

Every capability of backend.agent.capabilities becomes `mission.<capability>` with its real argument schema and
permissions, so agents find it through search/describe like any other tool. A call creates a governed single-task
mission in the given topic through the existing mission engine (validation, source checks, decision ledger). Mission
plan approval stays with the researcher, so the result reports `awaiting_approval` with what to approve; the agent
observes the mission later instead of claiming its outcome.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.tools.spec import ToolError, ToolSpec

PREFIX = "mission."


def specs() -> list[ToolSpec]:
    from backend.agent import capabilities as CAP
    out = []
    for cap in CAP.catalog():
        perms = sorted(set(cap["permissions"]) | {"workspace_write"})  # creating a mission writes project state
        out.append(ToolSpec(
            id=PREFIX + cap["id"], version="1.0.0", kind="native", source="builtin",
            description=f"{cap['description']} (creates a governed mission task; the researcher approves its plan)",
            capabilities=["mission", *cap["id"].split(".")[:2], "deterministic" if cap["deterministic"] else "reasoning"],
            permissions=perms, mutates=True, idempotent=False,
            input_schema={"type": "object", "required": ["topic_id", "objective"], "properties": {
                "topic_id": {"type": "string", "maxLength": 120},
                "objective": {"type": "string", "minLength": 1, "maxLength": 8000},
                "args": cap["input_schema"]}},
            execution={"callable": "backend.tools.mission_tools:propose", "pass_spec": True}))
    return out


def propose(args: dict, ctx, spec) -> dict:
    from backend.agent import capabilities as CAP, missions
    from backend.agent.mission_contracts import MissionSpec, Task
    capability = spec.id[len(PREFIX):]
    meta = CAP.META[capability]
    task = Task(id="task", capability=capability, args=dict(args.get("args") or {}),
                preferred_engine="deterministic" if meta[1] else meta[3][0])
    try:
        mission_spec = MissionSpec(topic_id=str(args["topic_id"]), objective=str(args["objective"]),
                                   permissions=[p for p in meta[2] if p in ("network", "workspace_write", "reasoning", "compute")],
                                   owner=ctx.principal[:100], tasks=[task])
        mission = missions.create(mission_spec)
    except KeyError as e:
        raise ToolError("not_found", f"Unknown topic or record: {e}", hint="Use an existing research topic id") from e
    except ValueError as e:
        raise ToolError("invalid_input", str(e)[:600], hint="Check the capability arguments with describe") from e
    return {"mission_id": mission["id"], "topic_id": mission_spec.topic_id, "capability": capability,
            "status": "awaiting_approval" if mission.get("status") in ("draft", "awaiting_approval") else mission.get("status"),
            "status_detail": mission.get("status"),
            "next": "The researcher approves this mission plan in Missions; observe its status before citing results"}

