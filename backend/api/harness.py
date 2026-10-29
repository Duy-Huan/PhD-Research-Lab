"""HTTP API for Custom Research Harness Studio and Workflow IDE."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.execution import harness as H
from backend.execution.workflow_nodes import NODE_REGISTRY, validate_workflow_graph
from backend.execution.workflow_templates import RESEARCH_TEMPLATES
from backend.agent.workflow_architect import (
    list_agent_profiles,
    save_agent_profile,
    auto_generate_team,
    generate_workflow_from_objective,
)
from backend.execution import workflow_runtime as WR

router = APIRouter(prefix="/api/harness", tags=["harness"])


# ---------------------------------------------------------------------------
# 1. Node Registry & Metadata
# ---------------------------------------------------------------------------

@router.get("/tools")
async def get_harness_tools():
    """List legacy open-source benchmark harness tools."""
    return {"tools": H.OPEN_SOURCE_HARNESS_TOOLS}


@router.get("/nodes")
async def get_workflow_nodes():
    """List all 17 registered node types with their input/output ports, schemas, and icons."""
    serialized = [meta.model_dump() for meta in NODE_REGISTRY.values()]
    return {"nodes": serialized}


# ---------------------------------------------------------------------------
# 2. Template Library
# ---------------------------------------------------------------------------

@router.get("/templates")
async def get_workflow_templates():
    """List all 7 pre-built scientific research workflow templates."""
    return {"templates": RESEARCH_TEMPLATES}


# ---------------------------------------------------------------------------
# 3. Dynamic Agent Team Builder
# ---------------------------------------------------------------------------

@router.get("/agents")
async def get_agents():
    """List all preset and custom research agent profiles."""
    profiles = await run_in_threadpool(list_agent_profiles)
    return {"agents": profiles}


@router.post("/agents")
async def create_or_update_agent(body: dict = Body(...)):
    """Create or update a custom agent profile."""
    saved = await run_in_threadpool(save_agent_profile, body)
    return saved


@router.post("/architect/team")
async def build_dynamic_team(body: dict = Body(...)):
    """Automatically synthesize a specialized multi-agent research team for an objective."""
    objective = str(body.get("objective", ""))
    desired_roles = body.get("roles")
    team = await run_in_threadpool(auto_generate_team, objective, desired_roles)
    return {"team": team}


# v6.6.4 (A9): the team comes from a model of the model list, and the canvas runs as a governed mission.
@router.get("/models")
async def team_models():
    """Models a team agent may be bound to (Settings → Models & AI connections), with availability."""
    from backend.agent import team_agents
    return {"models": await run_in_threadpool(team_agents.model_choices)}


@router.post("/team/propose")
async def propose_team(body: dict = Body(...)):
    """The chosen architect model proposes the team; the app validates tools and models (no substitution)."""
    from backend.agent import harness_compile as HC
    try:
        return await run_in_threadpool(HC.propose_team, str(body.get("objective") or ""), str(body.get("architect_model") or ""),
                                       bool(body.get("allow_api_billing")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:600]) from exc


@router.post("/compile")
async def compile_to_mission(body: dict = Body(...)):
    """Compile the canvas into a mission: preview (create=false) or a draft mission for plan approval in Missions."""
    from backend.agent import harness_compile as HC
    fn = HC.create_mission if body.get("create") else HC.compile_workflow
    try:
        return await run_in_threadpool(fn, body.get("workflow") or {}, str(body.get("topic_id") or ""), str(body.get("level") or "L3"),
                                       body.get("team") or [], str(body.get("objective") or ""))
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:600]) from exc


# ---------------------------------------------------------------------------
# 4. AI Workflow Architect
# ---------------------------------------------------------------------------

@router.post("/architect/generate")
async def architect_generate_workflow(body: dict = Body(...)):
    """Generate an editable research workflow graph from a natural language objective."""
    objective = str(body.get("objective", "")).strip()
    if not objective:
        raise HTTPException(status_code=400, detail="Research objective cannot be empty.")
    level = str(body.get("level", "L3"))
    wf = await run_in_threadpool(generate_workflow_from_objective, objective, level)
    return wf


# ---------------------------------------------------------------------------
# 5. Workflow Validation & Graph Integrity
# ---------------------------------------------------------------------------

@router.post("/validate")
async def validate_workflow(body: dict = Body(...)):
    """Validate graph connectivity, ports, acyclicity, and configuration schemas."""
    workflow = body.get("workflow") or body
    result = await run_in_threadpool(validate_workflow_graph, workflow)
    return result


# ---------------------------------------------------------------------------
# 6. Workflow CRUD
# ---------------------------------------------------------------------------

@router.get("/workflows")
async def get_workflows(topic_id: str = ""):
    """List all saved workflows and preset research templates."""
    saved = await run_in_threadpool(H.list_workflows, topic_id)
    # Merge preset templates into workflow list if not already present
    saved_ids = {w.get("id") for w in saved}
    merged: list[dict[str, Any]] = list(saved)
    for tpl in RESEARCH_TEMPLATES:
        if tpl.get("id") not in saved_ids:
            merged.append(tpl)
    return {"workflows": merged}


@router.get("/workflows/{wid}")
async def get_single_workflow(wid: str):
    """Get a specific workflow by ID from saved storage or template registry."""
    wf = await run_in_threadpool(H.get_workflow, wid)
    if wf:
        return wf
    # Check template registry
    for tpl in RESEARCH_TEMPLATES:
        if tpl.get("id") == wid:
            return tpl
    raise HTTPException(status_code=404, detail="Harness workflow or template not found")


@router.post("/workflows")
async def create_or_save_workflow(body: dict = Body(...)):
    """Create or save a custom harness workflow."""
    wf = await run_in_threadpool(H.save_workflow, body)
    return wf


@router.put("/workflows/{wid}")
async def update_workflow(wid: str, body: dict = Body(...)):
    """Update an existing custom harness workflow."""
    body["id"] = wid
    wf = await run_in_threadpool(H.save_workflow, body)
    return wf


@router.delete("/workflows/{wid}")
async def delete_workflow(wid: str):
    """Delete a custom harness workflow."""
    ok = await run_in_threadpool(H.delete_workflow, wid)
    if not ok:
        raise HTTPException(status_code=404, detail="Workflow not found or cannot be deleted")
    return {"ok": True, "id": wid}


# ---------------------------------------------------------------------------
# 7. Workflow Execution & Debugger Runtime
# ---------------------------------------------------------------------------

@router.post("/execute")
async def run_workflow(body: dict = Body(...)):
    """Execute a workflow graph with support for 17 node types, conditions, loops, and debugger."""
    workflow = body.get("workflow") or body
    topic_id = str(body.get("topic_id", ""))
    level = str(body.get("level", "L3"))
    step_mode = bool(body.get("step_mode", False))
    resume_from = body.get("resume_from")

    # If modern graph workflow with nodes/edges, run using WR (Workflow Runtime)
    if "nodes" in workflow and isinstance(workflow["nodes"], list):
        report = await run_in_threadpool(
            WR.execute_workflow_graph,
            workflow=workflow,
            topic_id=topic_id,
            level=level,
            step_mode=step_mode,
            resume_from=resume_from,
        )
        return report

    # Legacy benchmark harness fallback
    report = await run_in_threadpool(H.execute_workflow, workflow, topic_id)
    return report


@router.post("/execute/action")
async def workflow_execution_action(body: dict = Body(...)):
    """Debugger and governance actions: approve, reject, pause, resume, cancel."""
    eid = str(body.get("execution_id", ""))
    action = str(body.get("action", ""))
    node_id = str(body.get("node_id", ""))
    feedback = str(body.get("feedback", ""))

    record = await run_in_threadpool(WR.get_execution_record, eid)
    if not record:
        raise HTTPException(status_code=404, detail="Execution record not found")

    if action in ("approve", "reject"):
        node_status = "completed" if action == "approve" else "failed"
        for st in record.get("node_statuses", []):
            if st.get("node_id") == node_id:
                st["status"] = node_status
                st["feedback"] = feedback
                st["output"] = {"decision": action, "feedback": feedback}
                break
        record["status"] = "running" if action == "approve" else "failed"
        await run_in_threadpool(WR.save_execution_record, record)
        return {"ok": True, "action": action, "execution": record}

    if action == "cancel":
        record["status"] = "cancelled"
        await run_in_threadpool(WR.save_execution_record, record)
        return {"ok": True, "action": "cancel", "execution": record}

    return {"ok": True, "status": record.get("status")}


@router.get("/executions")
async def get_executions(workflow_id: str = ""):
    """List execution history reports for modern workflows and legacy harness."""
    modern = await run_in_threadpool(WR.list_all_executions, workflow_id)
    legacy = await run_in_threadpool(H.list_executions, workflow_id)
    seen = {m.get("execution_id") for m in modern}
    combined = list(modern)
    for l in legacy:
        if l.get("execution_id") not in seen:
            combined.append(l)
    return {"executions": combined}


@router.get("/executions/{eid}")
async def get_single_execution(eid: str):
    """Get execution report by ID."""
    report = await run_in_threadpool(WR.get_execution_record, eid)
    if not report:
        report = await run_in_threadpool(H.get_execution, eid)
    if not report:
        raise HTTPException(status_code=404, detail="Execution report not found")
    return report
