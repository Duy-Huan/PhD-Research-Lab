"""Experiments = VS Code: code projects (code/<name>/, own git + Python venv), open in VS Code, bring results back,
and the experiment jobs that research runs start (logs, metrics, files)."""
from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from backend.api.common import call, sse, stream
from backend.core import bus
from backend.execution import code_projects as CP

router = APIRouter()


@router.get("/api/code")
async def code_list():
    return await call(CP.list_projects)


@router.post("/api/code")
async def code_create(body: dict = Body(...)):
    """New code project {name, description?} — git repo, Python venv and .vscode settings are created with it."""
    out = await call(CP.create, str(body.get("name", "")), str(body.get("description", "")), bool(body.get("git", True)),
                     True, None, bool(body.get("seed", True)))
    bus.publish("code_project.created", name=out["name"])
    return out


@router.post("/api/code/open")
async def code_open(body: dict = Body(...)):
    out = await call(CP.open_project, str(body.get("name", "")))
    bus.publish("code_project.opened", name=out["name"])
    return out


@router.post("/api/code/close")
async def code_close():
    return await call(CP.close)


@router.post("/api/code/delete")
async def code_delete(body: dict = Body(...)):
    return await call(CP.delete, str(body.get("name", "")), str(body.get("confirm", "")), False)


@router.get("/api/code/environment")
async def code_env():
    return await call(CP.environment)


@router.post("/api/code/vscode")
async def code_vscode():
    """Open the active code project in VS Code (its interpreter = the project's venv)."""
    from backend.execution import vscode
    from backend.execution.tools import IntegrationError

    def run():
        CP.sync_vscode()
        try:
            return vscode.open_folder("code")
        except IntegrationError as e:
            raise ValueError(str(e))
    return await call(run)


@router.post("/api/code/sync")
async def code_sync(body: dict = Body(...)):
    """Bring VS Code work back: changed files → 'Commit code', new metrics → 'Ghim kết quả' (proposals in the chat)."""
    from backend.execution import sync
    return await call(sync.propose, str(body.get("session_id", "")))


@router.get("/api/code/scan")
async def code_scan():
    from backend.execution import sync
    return await call(sync.scan)


# ------------------------------------------------------------------ experiment jobs
@router.get("/api/jobs")
async def jobs(limit: int = 50):
    from backend.execution.sandbox import list_runs
    return {"jobs": await call(list_runs, max(1, min(500, limit)))}


@router.get("/api/jobs/{job_id}")
async def job(job_id: str):
    from backend.execution.sandbox import get_run
    return await call(get_run, job_id)


@router.post("/api/jobs/{job_id}/stop")
async def job_stop(job_id: str):
    from backend.execution.sandbox import stop_job
    return await call(stop_job, job_id)


@router.get("/api/jobs/{job_id}/file")
def job_file(job_id: str, path: str):
    from backend.execution.sandbox import runs_dir
    if not re.fullmatch(r"[\w-]{6,60}", job_id):
        raise HTTPException(400, "Invalid job id")
    root = (runs_dir() / job_id).resolve()
    p = (root / path).resolve()
    if root not in p.parents or not p.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(p)


@router.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: str, request: Request, after: int = 0):
    """Live log of a running job: {type: line, seq, stream, text} … {type: end, status}."""
    from backend.execution.sandbox import JOBS
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job is not running in this session — read its log with GET /api/jobs/{id}")

    async def gen():
        last = after
        while True:
            for seq, st, text in await run_in_threadpool(job.since, last):
                last = seq
                yield sse({"type": "line", "seq": seq, "stream": st, "text": text})
            if job.status not in ("running", "queued"):
                yield sse({"type": "end", "status": job.status, "exit_code": job.exit_code})
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.3)
    return stream(gen())
