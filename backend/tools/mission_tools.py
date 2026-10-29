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
    from backend.execution.protocol_contracts import AgentCodeProtocol
    schema = AgentCodeProtocol.model_json_schema()  # `kind` is set by the tool, not by the agent
    schema["properties"].pop("kind")
    schema["required"] = [r for r in schema["required"] if r != "kind"]
    out.append(ToolSpec(
        id="experiment.propose_protocol", version="1.0.0", kind="native", source="builtin",
        description="Freeze your experiment code in the open code project as a protocol for the researcher to approve "
                    "(v6.6.4). Every condition x seed runs once in a fresh process with PHDLAB_CONDITION, PHDLAB_SEED and "
                    "PHDLAB_OUT set; the code must write $PHDLAB_OUT/metrics.json = {\"metrics\": {name: number}} with "
                    "every registered metric. Later edits never change a frozen protocol: propose a new one.",
        capabilities=["mission", "experiment", "protocol", "deterministic"], permissions=["workspace_write"],
        mutates=True, idempotent=False, input_schema=schema,
        execution={"callable": "backend.tools.mission_tools:propose_protocol"}))
    out.append(ToolSpec(
        id="experiment.protocol_status", version="1.0.0", kind="native", source="builtin",
        description="Approval state of a protocol; once the researcher approved it, the protocol reference to pass to "
                    "mission.experiment.run",
        capabilities=["mission", "experiment", "protocol"], permissions=[], mutates=False, idempotent=True,
        input_schema={"type": "object", "required": ["topic_id", "protocol_id"], "properties": {
            "topic_id": {"type": "string", "maxLength": 120}, "protocol_id": {"type": "string", "maxLength": 120}}},
        execution={"callable": "backend.tools.mission_tools:protocol_status"}))
    return out


def propose_protocol(args: dict, ctx) -> dict:
    from pydantic import ValidationError
    from backend.execution import code_projects, protocols
    from backend.execution.protocol_contracts import AgentCodeProtocol
    try:
        p = protocols.create(AgentCodeProtocol.model_validate({**args, "kind": "agent_code_v1"}),
                             by=getattr(ctx, "principal", "") or "agent:unknown")  # B2: the ledger records who proposed it
    except code_projects.NoCodeProject as e:
        raise ToolError("unavailable", str(e), hint="Ask the researcher to create or open a code project") from e
    except KeyError as e:
        raise ToolError("not_found", f"Unknown topic: {e}", hint="Use an existing research topic id") from e
    except (ValidationError, ValueError) as e:
        raise ToolError("invalid_input", str(e)[:600], hint="Check the protocol fields with describe") from e
    snap = p["payload"]
    return {"protocol_id": p["id"], "digest": p["digest"], "code_digest": snap["code_digest"],
            "files": len(snap["code_manifest"]), "trials": len(snap["trials"]), "status": "awaiting_approval",
            "next": "The researcher reviews and approves this frozen protocol; then check experiment.protocol_status"}


def protocol_status(args: dict, ctx) -> dict:
    from backend.execution import protocols
    try:
        p = protocols.get(str(args["topic_id"]), str(args["protocol_id"]))
    except (KeyError, ValueError) as e:
        raise ToolError("not_found", "Protocol not found in this topic") from e
    if not p["approval"]:
        return {"protocol_id": p["id"], "status": "awaiting_approval"}
    used = any(r["approval_nonce"] == p["approval"]["nonce"] for r in protocols.runs(str(args["topic_id"])))
    return {"protocol_id": p["id"], "status": "approval_used" if used else "approved",
            "experiment_run_args": None if used else {"protocol_id": p["id"], "protocol_digest": p["digest"],
                                                      "approval_nonce": p["approval"]["nonce"]},
            "next": "Ask the researcher for a new approval to run it again" if used else
                    "Propose mission.experiment.run with experiment_run_args, then mission.experiment.verify"}


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

