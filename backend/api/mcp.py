"""MCP endpoint (JSON-RPC over HTTP, localhost only): research tools for CLI providers (Claude Code …) with per-session
grants — the provider sees only the tools its chat session allows; write tools only create review candidates."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from backend.providers import mcp_server

async def bind_project():
    from backend.core.config import data_dir, project_scope
    with project_scope(data_dir()):
        yield


router = APIRouter(dependencies=[Depends(bind_project)])


@router.post("/mcp")
async def mcp(request: Request):
    hdrs = {k.lower(): v for k, v in request.headers.items()}
    code, why = mcp_server.guard(hdrs, request.client.host if request.client else "?")
    if code:
        mcp_server.audit({"denied": code, "reason": why})
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": why}}, code)
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}, 400)
    sess = hdrs.get("mcp-session-id", "")[:80]
    from backend.agent.mcp_policy import lookup
    auth = hdrs.get("authorization", "")
    grant = lookup(auth[7:].strip()) if auth.lower().startswith("bearer ") else None
    if auth.lower().startswith('bearer phg_') and not grant:
        return JSONResponse({'error': 'Project grant expired or was revoked'}, status_code=401)
    meta: dict = {"grant": grant} if grant else {}
    if isinstance(payload, list):
        res = [r for r in [await run_in_threadpool(mcp_server.handle, m, sess, meta) for m in payload if isinstance(m, dict)] if r]
        out = JSONResponse(res) if res else Response(status_code=202)
    elif isinstance(payload, dict):
        r = await run_in_threadpool(mcp_server.handle, payload, sess, meta)
        out = JSONResponse(r) if r else Response(status_code=202)
    else:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}, 400)
    if meta.get("session_id"):
        out.headers["Mcp-Session-Id"] = meta["session_id"]
    return out


@router.get("/mcp")
def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})
