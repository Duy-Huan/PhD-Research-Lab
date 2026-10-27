"""v6.6.0 native tool capability system: registry discovery, unified invocation, jobs/streaming, provenance and
agent-proposed tool lifecycle. Specific routes are declared before /api/tools/{tool_id}."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from backend.api.common import sse, stream
from backend.tools import proposals as P
from backend.tools import registry as R
from backend.tools.runtime import RUNTIME, Grant, provenance, verify_provenance
from backend.tools.spec import ToolError

router = APIRouter()
STATUS = {"not_found": 404, "permission_denied": 403, "budget_exceeded": 429, "unavailable": 503,
          "incompatible_version": 409}


async def _call(fn, *a, **k):
    try:
        return await run_in_threadpool(fn, *a, **k)
    except ToolError as e:
        raise HTTPException(STATUS.get(e.code, 400), e.as_dict())
    except ValueError as e:
        raise HTTPException(400, {"code": "invalid_input", "message": str(e)[:1000]})


@router.get("/api/tools")
async def listing(kind: str = "", capability: str = "", include_unavailable: bool = True):
    return await _call(R.REGISTRY.listing, kind=kind, capability=capability, include_unavailable=include_unavailable)


@router.get("/api/tools/search")
async def search(q: str = "", capability: str = "", kind: str = "", available_only: bool = False, limit: int = 10):
    return {"results": await _call(R.REGISTRY.search, q, capability=capability, kind=kind,
                                   available_only=available_only, limit=max(1, min(50, limit)))}


@router.get("/api/tools/provenance")
async def provenance_rows(job_id: str = "", limit: int = 200):
    return {"records": await _call(provenance, job_id, max(1, min(2000, limit)))}


@router.get("/api/tools/provenance/verify")
async def provenance_verify():
    return await _call(verify_provenance)


@router.get("/api/tools/jobs/{job_id}")
async def job(job_id: str):
    return await _call(RUNTIME.get, job_id)


@router.get("/api/tools/jobs/{job_id}/events")
async def job_events(job_id: str, after: int = 0, timeout: float = 0):
    return await _call(RUNTIME.events, job_id, after, max(0.0, min(30.0, timeout)))


@router.get("/api/tools/jobs/{job_id}/stream")
async def job_stream(job_id: str, request: Request):
    await _call(RUNTIME.get, job_id)

    async def gen():
        after = 0
        while not await request.is_disconnected():
            batch = await run_in_threadpool(RUNTIME.events, job_id, after, 10.0)
            for o in batch["observations"]:
                after = o["seq"]
                yield sse({"type": "observation", **o})
            if batch["status"] in ("succeeded", "failed", "cancelled", "timed_out", "denied") and not batch["observations"]:
                yield sse({"type": "done", "status": batch["status"]})
                return
            await asyncio.sleep(0)
    return stream(gen())


@router.post("/api/tools/jobs/{job_id}/cancel")
async def job_cancel(job_id: str):
    return await _call(RUNTIME.cancel, job_id)


@router.get("/api/tools/mcp-servers")
async def mcp_servers():
    return {"servers": await _call(R.mcp_servers)}


@router.post("/api/tools/mcp-servers")
async def mcp_server_add(body: dict = Body(...)):
    return await _call(R.add_mcp_server, str(body.get("name", "")), str(body.get("url", "")))


@router.post("/api/tools/mcp-servers/{name}/discover")
async def mcp_server_discover(name: str):
    return await _call(R.discover_mcp, name)


@router.get("/api/tools/google")
async def google_status():
    from backend.tools import google_mcp
    return await _call(google_mcp.status)


@router.post("/api/tools/google/settings")
async def google_settings(body: dict = Body(...)):
    from backend.tools import google_mcp
    return await _call(google_mcp.save_settings, body)


@router.post("/api/tools/google/drive/oauth-client")
async def google_oauth_client(body: dict = Body(...)):
    from backend.tools import google_mcp
    return await _call(google_mcp.save_oauth_client, str(body.get("client_id", "")), str(body.get("client_secret", "")))


@router.post("/api/tools/google/drive/oauth/start")
async def google_oauth_start(request: Request):
    from backend.tools import google_mcp
    redirect = str(request.base_url).rstrip("/") + "/api/tools/google/drive/oauth/callback"
    return await _call(google_mcp.oauth_start, redirect)


@router.get("/api/tools/google/drive/oauth/callback")
async def google_oauth_callback(code: str = "", state: str = "", error: str = ""):
    from fastapi.responses import HTMLResponse
    from backend.tools import google_mcp
    if error or not code:
        return HTMLResponse("<p>Google Drive authorization was not granted. You can close this tab.</p>", status_code=400)
    await _call(google_mcp.oauth_finish, code, state)
    return HTMLResponse("<p>Google Drive is connected to PhD Research Lab. You can close this tab.</p>")


@router.post("/api/tools/google/{server}/discover")
async def google_discover(server: str):
    from backend.tools import google_mcp
    return await _call(google_mcp.discover, server)


@router.post("/api/tools/google/stop")
async def google_stop():
    from backend.tools import google_mcp
    return {"stopped": await _call(google_mcp.stop_servers)}


@router.get("/api/tools/clients")
async def clients_status():
    from backend.tools import mcp_clients
    return await _call(mcp_clients.status)


@router.post("/api/tools/clients/antigravity/register")
async def clients_register_antigravity(request: Request):
    from backend.tools import mcp_clients
    return await _call(mcp_clients.register_antigravity, str(request.base_url).rstrip("/") + "/mcp")


@router.post("/api/tools/clients/antigravity/unregister")
async def clients_unregister_antigravity():
    from backend.tools import mcp_clients
    return await _call(mcp_clients.unregister_antigravity)


# v6.6.2 ChatGPT connector: local (loopback) owner controls for the public gateway.
@router.get("/api/tools/clients/chatgpt")
async def chatgpt_status():
    from backend.tools import chatgpt_gateway
    return chatgpt_gateway.status()


@router.post("/api/tools/clients/chatgpt/{action}")
async def chatgpt_action(action: str, body: dict = Body(default={})):
    from backend.tools import chatgpt_gateway as G
    if action == "enable":
        return await _call(G.enable)
    if action in ("disable", "kill"):
        return G.kill_switch()
    if action == "refresh-ranges":
        return await _call(G.refresh_ranges)
    if action in ("approve", "deny"):
        return await _call(G.approve if action == "approve" else G.deny, str(body.get("request_id", "")))
    raise HTTPException(404, "Unsupported ChatGPT connector action")


@router.get("/api/tools/proposals")
async def proposal_list():
    return {"proposals": await _call(P.listing)}


@router.post("/api/tools/proposals")
async def proposal_create(body: dict = Body(...)):
    return await _call(P.propose, body.get("manifest") or {}, body.get("files") or {},
                       proposer=str(body.get("proposer") or "agent")[:80])


@router.post("/api/tools/proposals/{tool_id}/{version}/validate")
async def proposal_validate(tool_id: str, version: str):
    return await _call(P.validate, tool_id, version)


@router.post("/api/tools/proposals/{tool_id}/{version}/promote")
async def proposal_promote(tool_id: str, version: str, body: dict = Body(...)):
    return await _call(P.promote, tool_id, version, str(body.get("approved_by", "")))


@router.post("/api/tools/{tool_id}/rollback")
async def tool_rollback(tool_id: str, body: dict = Body(...)):
    return await _call(P.rollback, tool_id, str(body.get("to_version", "")), str(body.get("approved_by", "")))


@router.post("/api/tools/{tool_id}/invoke")
async def invoke(tool_id: str, request: Request, body: dict = Body(default={})):
    """The researcher (UI/CLI) invokes a tool directly. The request states the permissions it grants for THIS call;
    `wait` returns the finished job, otherwise the queued job (poll/stream it)."""
    grant = await _call(Grant, principal="api:" + (request.headers.get("X-PhDLab-Client") or "ui")[:20],
                        tools=[tool_id], permissions=list(body.get("permissions") or ["read"]),
                        allow_mutation=bool(body.get("allow_mutation")), max_calls=1,
                        max_wall_s=float(body.get("max_wall_s") or 600))
    args = body.get("args") or {}
    if body.get("wait", True):
        return await _call(RUNTIME.run, tool_id, args, grant, version=str(body.get("version") or ""))
    return await _call(RUNTIME.submit, tool_id, args, grant, version=str(body.get("version") or ""))


@router.get("/api/tools/{tool_id}")
async def describe(tool_id: str, version: str = ""):
    return await _call(R.REGISTRY.describe, tool_id, version)


# v6.6.2 one live roster of every agent (3D Lab, Harness, status views)
@router.get("/api/agents/roster")
async def agents_roster():
    from backend.agent import roster
    return await run_in_threadpool(roster.roster)


@router.get("/api/agents/roster/stream")
async def agents_roster_stream(once: int = 0):
    """SSE: `event: roster` with the full snapshot now and whenever it changes (checked every second)."""
    from backend.agent import roster
    import json as _json

    async def gen():
        last = ""
        while True:
            snap = await run_in_threadpool(roster.roster)
            if snap["digest"] != last:
                last = snap["digest"]
                yield "event: roster\ndata: " + _json.dumps(snap, ensure_ascii=False, default=str) + "\n\n"
            if once:
                return
            await asyncio.sleep(1)
    return stream(gen())
