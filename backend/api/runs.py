"""Research runs: background work started from the chat (or here directly), its timeline and the researcher's decisions."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Request
from fastapi.concurrency import run_in_threadpool

from backend.agent import runs
from backend.api.common import call, sse, stream

router = APIRouter()


@router.get("/api/runs")
async def runs_list(status: str = "", session: str = "", limit: int = 100):
    return {"runs": await call(runs.list_runs, status, session, max(1, min(500, limit)))}


@router.post("/api/runs")
async def runs_create(body: dict = Body(...)):
    """{skill, input, session_id?} — the same path as "/skill input" in the chat."""
    from backend.agent import launch, sessions
    sid = str(body.get("session_id") or "")
    sess = await call(sessions.get, sid) if sid else None
    return await call(launch.from_skill, str(body.get("skill", "")), str(body.get("input", "")), sess,
                      engine_mode=str(body.get("engine_mode") or ""))


@router.get("/api/runs/{rid}")
async def runs_get(rid: str):
    return await call(runs.get, rid)


@router.post("/api/runs/{rid}/approve")
async def runs_approve(rid: str):
    return await call(runs.approve, rid)


@router.post("/api/runs/{rid}/cancel")
async def runs_cancel(rid: str):
    return await call(runs.cancel, rid)


@router.post("/api/runs/{rid}/resume")
async def runs_resume(rid: str, body: dict = Body(default={})):
    """Answer to NEEDS_USER_ACTION: {accept: true} applies the recovery proposal; {patch: {command | provider …}}."""
    return await call(runs.resume, rid, bool(body.get("accept", True)), body.get("patch") or None)


@router.post("/api/runs/{rid}/provider")
async def runs_provider(rid: str, body: dict = Body(...)):
    """Move a pending / failed step to another provider (completed steps and their outputs stay)."""
    return await call(runs.swap_provider, rid, str(body.get("step", "")), str(body.get("provider", "")))


@router.get("/api/runs/{rid}/events")
async def runs_events(rid: str, after: int = 0):
    return {"events": await call(runs.events, rid, max(0, after))}


@router.get("/api/runs/{rid}/stream")
async def runs_stream(rid: str, request: Request, after: int = 0, timeout: float = 3600):
    await call(runs.get, rid)

    async def gen():
        last, end = max(0, after), asyncio.get_running_loop().time() + max(1.0, min(86400.0, timeout))
        while asyncio.get_running_loop().time() < end:
            for e in await run_in_threadpool(runs.wait_events, rid, last, 1.0):
                last = e["seq"]
                yield sse(e)
            if await request.is_disconnected():
                return
    return stream(gen())


# ------------------------------------------------------------------ acceptance evidence
@router.get("/api/acceptance")
async def acceptance():
    from backend.agent import acceptance as A
    return await call(lambda: {**A.evaluate(), "gaps": A.gaps()})
