"""HTTP API for Custom Research Harness Studio and Open-Source Harness Tools."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.execution import harness as H

router = APIRouter(prefix="/api/harness", tags=["harness"])


@router.get("/tools")
async def get_harness_tools():
    """List all available open-source harness tools."""
    return {"tools": H.OPEN_SOURCE_HARNESS_TOOLS}


@router.get("/workflows")
async def get_workflows(topic_id: str = ""):
    """List all preset and custom saved harness workflows."""
    workflows = await run_in_threadpool(H.list_workflows, topic_id)
    return {"workflows": workflows}


@router.get("/workflows/{wid}")
async def get_single_workflow(wid: str):
    """Get a specific harness workflow by ID."""
    wf = await run_in_threadpool(H.get_workflow, wid)
    if not wf:
        raise HTTPException(status_code=404, detail="Harness workflow not found")
    return wf


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


@router.post("/execute")
async def run_harness_workflow(body: dict = Body(...)):
    """Execute a custom harness workflow and return structured results."""
    workflow = body.get("workflow") or body
    topic_id = str(body.get("topic_id", ""))
    report = await run_in_threadpool(H.execute_workflow, workflow, topic_id)
    return report


@router.get("/executions")
async def get_executions(workflow_id: str = ""):
    """List execution history reports for harness workflows."""
    runs = await run_in_threadpool(H.list_executions, workflow_id)
    return {"executions": runs}


@router.get("/executions/{eid}")
async def get_single_execution(eid: str):
    """Get execution report by ID."""
    report = await run_in_threadpool(H.get_execution, eid)
    if not report:
        raise HTTPException(status_code=404, detail="Execution report not found")
    return report
