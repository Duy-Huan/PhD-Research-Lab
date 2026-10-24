"""HTTP API for v6.4.1 OpenCode Parallel Core Integration."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from backend.api.common import call
from backend.core.config import data_dir, project_scope
from backend.research_engines import opencode as OC


async def bind_project():
    with project_scope(data_dir()):
        yield


router = APIRouter(dependencies=[Depends(bind_project)])


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/opencode/status")
async def opencode_status():
    return await call(OC.health)


@router.post("/api/opencode/server/launch")
async def launch_opencode_server():
    return await call(OC.ensure_server_running)


@router.post("/api/research/topics/{tid}/opencode/workspace")
async def ensure_opencode_workspace(tid: str, body: dict = Body(default={})):
    wid = str(body.get("workspace_id") or "")
    enable_plugin = bool(body.get("enable_bridge_plugin", True))
    return await call(_safe, OC.ensure_topic_workspace, tid, wid, enable_plugin)


@router.get("/api/research/topics/{tid}/opencode/sessions")
async def list_opencode_sessions(tid: str):
    return {"sessions": await call(_safe, OC.list_sessions, tid)}


@router.post("/api/research/topics/{tid}/opencode/sessions")
async def create_opencode_session(tid: str, body: dict = Body(...)):
    spec = _safe(OC.OpenCodeTaskSpec.model_validate, {**body, "topic_id": tid})
    return await call(_safe, OC.start_session, spec)


@router.get("/api/research/topics/{tid}/opencode/sessions/{sid}")
async def get_opencode_session(tid: str, sid: str):
    return await call(_safe, OC.get_session, tid, sid)


@router.post("/api/research/topics/{tid}/opencode/sessions/{sid}/events")
async def post_opencode_event(tid: str, sid: str, body: dict = Body(...)):
    event_type = str(body.get("event_type") or "tool.executed")
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    seq = int(body["seq"]) if body.get("seq") is not None else None
    key_hint = str(body.get("key_hint") or "")
    return await call(_safe, OC.record_event, tid, sid, event_type, payload, seq=seq, key_hint=key_hint)


@router.post("/api/research/topics/{tid}/opencode/sessions/{sid}/approvals")
async def request_opencode_approval(tid: str, sid: str, body: dict = Body(...)):
    action = str(body.get("action") or "")
    scope = str(body.get("scope") or "")
    risk = str(body.get("risk") or "high")
    return await call(_safe, OC.request_approval, tid, sid, action, scope, risk)


@router.post("/api/research/topics/{tid}/opencode/sessions/{sid}/approvals/{aid}")
async def decide_opencode_approval(tid: str, sid: str, aid: str, body: dict = Body(...)):
    decision = str(body.get("decision") or "reject")
    note = str(body.get("note") or "")
    return await call(_safe, OC.decide_approval, tid, sid, aid, decision, note)


@router.post("/api/research/topics/{tid}/opencode/sessions/{sid}/cancel")
async def cancel_opencode_session(tid: str, sid: str):
    return await call(_safe, OC.cancel_session, tid, sid)


@router.post("/api/research/topics/{tid}/opencode/sessions/{sid}/reconcile")
async def reconcile_opencode_session(tid: str, sid: str, body: dict = Body(default={})):
    simulate_gap = bool(body.get("simulate_gap", False))
    return await call(_safe, OC.reconcile_session, tid, sid, simulate_gap)
