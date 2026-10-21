"""Remote compute handoff and verified ClearML run cards (no notebook-owned state)."""
from fastapi import APIRouter, Body
from fastapi.responses import FileResponse
from backend.api.common import call
from backend.execution import remote_compute as RC

router = APIRouter()


@router.get("/api/compute/runs")
async def listing():
    return {"runs": await call(RC.list_runs), "targets": list(RC.TARGETS)}


@router.post("/api/compute/runs")
async def create(body: dict = Body(...)):
    return await call(RC.create, body)


@router.get("/api/compute/runs/{rid}")
async def get(rid: str):
    return await call(RC.get, rid)


@router.post("/api/compute/runs/{rid}/approve")
async def approve(rid: str):
    return await call(RC.approve, rid)


@router.get("/api/compute/runs/{rid}/bundle")
async def bundle(rid: str):
    return FileResponse(await call(RC.bundle, rid), media_type="application/zip", filename=rid + ".zip")


@router.post("/api/compute/runs/{rid}/sync")
async def sync(rid: str, body: dict = Body(default={})):
    from backend.execution.tools import IntegrationError
    from fastapi import HTTPException
    from backend.core.telemetry import redact
    try:
        return await call(RC.sync, rid, str(body.get("task_id") or ""), bool(body.get("collect")))
    except IntegrationError as e:
        raise HTTPException(502, redact(str(e))) from e
