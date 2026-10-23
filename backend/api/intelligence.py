"""HTTP API routes for v6.4.2 Unified Research Intelligence & Integration Layer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.core.config import data_dir, project_scope
from backend.intelligence.context_gateway import (
    ContextPackRequest as GatewayContextPackRequest,
    build_context_pack,
    get_task_context_pack,
)
from backend.intelligence.observability import emit_trace_event, get_mission_trace
from backend.intelligence.report_composer import compose_report_manifest
from backend.intelligence.reproducibility import export_reproducibility_pack, replay_reproducibility_pack
from backend.intelligence.smart_router import (
    RoutePreviewRequest as RouterPreviewRequest,
    preview_route,
)
from backend.intelligence.urap import (
    get_artifact,
    lineage_graph,
    list_artifacts,
    register_artifact,
    verify_integrity,
)
from backend.knowledge import research_store as S

async def bind_project():
    with project_scope(data_dir()):
        yield


router = APIRouter(dependencies=[Depends(bind_project)])


class RegisterArtifactRequest(BaseModel):
    topic_id: str = ""
    mission_id: str = ""
    task_id: str = ""
    artifact_type: str = "experiment_result"
    producer_runtime: str = "phdlab"
    producer_version: str = "6.4.2"
    session_id: str = ""
    agent_id: str = "researcher"
    uri: str = ""
    media_type: str = "application/json"
    content_text: str = ""
    sha256: str = ""
    byte_size: int = 0
    input_artifact_ids: list[str] = Field(default_factory=list)
    experiment_id: str = ""
    code_revision: str = ""
    verification_status: str = "unverified"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceEventRequest(BaseModel):
    topic_id: str = ""
    event_type: str = "TOOL_EXECUTION"
    mission_id: str = ""
    team_id: str = ""
    task_id: str = ""
    runtime_id: str = "phdlab"
    span_name: str = "task.execute"
    parent_span_id: str = ""
    severity: str = "info"
    payload: dict[str, Any] = Field(default_factory=dict)
    dedup_key: str = ""


class ContextPackBody(BaseModel):
    topic_id: str = ""
    mission_id: str = ""
    role: str = "experiment_engineer"
    objective: str = "Execute bounded research task"
    query: str = ""
    max_tokens: int = 3500
    requested_source_ids: list[str] = Field(default_factory=list)


class RoutePreviewBody(BaseModel):
    topic_id: str = ""
    mission_id: str = ""
    capability: str = "paper.discover"
    preferred_engine: str = "deterministic"
    fallback_engines: list[str] = Field(default_factory=list)
    allow_metered_api: bool = False
    simulate_quota_exhausted: bool = False


class ReproExportRequest(BaseModel):
    topic_id: str = ""
    include_ro_crate: bool = True


class ReproReplayRequest(BaseModel):
    topic_id: str = ""
    tolerance: float = 1e-6


class ReportManifestRequest(BaseModel):
    topic_id: str = ""
    title: str = ""
    artifact_ids: list[str] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    export_format: str = "md"


def _resolve_mission_topic(mission_id: str, explicit_topic_id: str = "") -> str:
    if explicit_topic_id:
        return explicit_topic_id
    with S.db() as c:
        row = c.execute("SELECT topic_id FROM missions WHERE id=?", (mission_id,)).fetchone()
        if row and row["topic_id"]:
            return str(row["topic_id"])
        t_row = c.execute("SELECT id FROM topics ORDER BY created DESC LIMIT 1").fetchone()
        if t_row:
            return str(t_row["id"])
    raise HTTPException(404, f"Cannot resolve topic_id for mission {mission_id}")


# ── Module A: URAP Artifacts ───────────────────────────────────────────────

@router.post("/api/research/topics/{tid}/artifacts-urap")
@router.post("/api/research/topics/{tid}/urap/artifacts")
def api_register_topic_artifact(tid: str, body: RegisterArtifactRequest):
    try:
        return register_artifact(
            topic_id=tid,
            artifact_type=body.artifact_type,
            sha256=body.sha256,
            byte_size=body.byte_size,
            uri=body.uri,
            media_type=body.media_type,
            content_text=body.content_text,
            mission_id=body.mission_id,
            task_id=body.task_id,
            producer_runtime=body.producer_runtime,
            producer_version=body.producer_version,
            session_id=body.session_id,
            agent_id=body.agent_id,
            input_artifact_ids=body.input_artifact_ids,
            experiment_id=body.experiment_id,
            code_revision=body.code_revision,
            verification_status=body.verification_status,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/artifacts")
def api_register_artifact_root(body: RegisterArtifactRequest):
    if not body.topic_id:
        raise HTTPException(400, "topic_id is required")
    return api_register_topic_artifact(body.topic_id, body)


@router.get("/api/research/topics/{tid}/artifacts-urap")
@router.get("/api/research/topics/{tid}/urap/artifacts")
def api_list_topic_urap_artifacts(tid: str, mission_id: str = "", task_id: str = "", artifact_type: str = ""):
    try:
        items = list_artifacts(
            topic_id=tid,
            mission_id=mission_id,
            task_id=task_id,
            artifact_type=artifact_type,
        )
        return {"items": items, "count": len(items)}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/api/artifacts")
def api_list_artifacts_root(topic_id: str = "", mission_id: str = "", task_id: str = "", artifact_type: str = ""):
    tid = _resolve_mission_topic(mission_id, topic_id)
    return api_list_topic_urap_artifacts(tid, mission_id=mission_id, task_id=task_id, artifact_type=artifact_type)


@router.get("/api/artifacts/{aid}")
def api_get_artifact(aid: str, topic_id: str = ""):
    try:
        return get_artifact(aid, topic_id=topic_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/api/artifacts/{aid}/lineage")
def api_get_artifact_lineage(aid: str, topic_id: str = ""):
    try:
        return lineage_graph(aid, topic_id=topic_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/api/artifacts/{aid}/verify-integrity")
def api_verify_artifact_integrity(aid: str, topic_id: str = ""):
    try:
        return verify_integrity(aid, topic_id=topic_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


# ── Module B: Mission Observability & Trace ────────────────────────────────

@router.get("/api/missions/{mid}/trace")
def api_get_mission_trace(mid: str, topic_id: str = ""):
    tid = _resolve_mission_topic(mid, topic_id)
    try:
        return get_mission_trace(mission_id=mid, topic_id=tid)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/api/research/topics/{tid}/missions/{mid}/trace")
def api_get_topic_mission_trace(tid: str, mid: str):
    try:
        return get_mission_trace(mission_id=mid, topic_id=tid)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/api/missions/{mid}/trace")
def api_emit_mission_trace(mid: str, body: TraceEventRequest):
    tid = _resolve_mission_topic(mid, body.topic_id)
    try:
        return emit_trace_event(
            topic_id=tid,
            event_type=body.event_type,
            mission_id=mid,
            team_id=body.team_id,
            task_id=body.task_id,
            runtime_id=body.runtime_id,
            span_name=body.span_name,
            parent_span_id=body.parent_span_id,
            severity=body.severity,
            payload=body.payload,
            dedup_key=body.dedup_key,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ── Module C: Context Pack Builder & Gateway ───────────────────────────────

@router.post("/api/tasks/{task_id}/context-pack")
def api_build_task_context_pack(task_id: str, body: ContextPackBody):
    tid = _resolve_mission_topic(body.mission_id, body.topic_id)
    try:
        req = GatewayContextPackRequest(
            topic_id=tid,
            mission_id=body.mission_id,
            task_id=task_id,
            role=body.role,  # type: ignore[arg-type]
            objective=body.objective,
            query=body.query,
            max_tokens=body.max_tokens,
            requested_source_ids=body.requested_source_ids,
        )
        return build_context_pack(req)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/tasks/{task_id}/context-pack")
def api_get_task_context_pack(task_id: str, topic_id: str = ""):
    try:
        return get_task_context_pack(task_id, topic_id=topic_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


# ── Module D: Smart Router & Quota-Aware Scheduler ─────────────────────────

@router.post("/api/tasks/{task_id}/route-preview")
def api_preview_task_route(task_id: str, body: RoutePreviewBody):
    tid = _resolve_mission_topic(body.mission_id, body.topic_id)
    try:
        req = RouterPreviewRequest(
            topic_id=tid,
            mission_id=body.mission_id,
            task_id=task_id,
            capability=body.capability,
            preferred_engine=body.preferred_engine,
            fallback_engines=body.fallback_engines,
            allow_metered_api=body.allow_metered_api,
            simulate_quota_exhausted=body.simulate_quota_exhausted,
        )
        return preview_route(req)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ── Module F: Reproducibility Pack & RO-Crate Exporter ─────────────────────

@router.post("/api/missions/{mid}/reproducibility-export")
def api_export_reproducibility(mid: str, body: ReproExportRequest | None = None):
    req = body or ReproExportRequest()
    tid = _resolve_mission_topic(mid, req.topic_id)
    try:
        return export_reproducibility_pack(tid, mid, include_ro_crate=req.include_ro_crate)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/api/missions/{mid}/reproducibility-export/download")
def api_download_reproducibility(mid: str, topic_id: str = ""):
    tid = _resolve_mission_topic(mid, topic_id)
    with S.db() as c:
        row = c.execute(
            "SELECT payload FROM reproducibility_exports WHERE topic_id=? AND mission_id=? ORDER BY created_at DESC LIMIT 1",
            (tid, mid),
        ).fetchone()
    if not row:
        info = export_reproducibility_pack(tid, mid, include_ro_crate=True)
        path = Path(info["bundle_path"])
    else:
        pay = json.loads(row["payload"])
        path = Path(pay["bundle_path"])
        if not path.exists():
            info = export_reproducibility_pack(tid, mid, include_ro_crate=True)
            path = Path(info["bundle_path"])
    return FileResponse(
        str(path),
        media_type="application/zip",
        filename=f"reproducibility-{mid}.zip",
    )


@router.post("/api/missions/{mid}/reproducibility-replay")
def api_replay_reproducibility(mid: str, body: ReproReplayRequest | None = None):
    req = body or ReproReplayRequest()
    tid = _resolve_mission_topic(mid, req.topic_id)
    try:
        return replay_reproducibility_pack(tid, mid, tolerance=req.tolerance)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc


# ── Module H: Unified Research Report Composer ─────────────────────────────

@router.post("/api/missions/{mid}/report-manifest")
def api_compose_report_manifest(mid: str, body: ReportManifestRequest | None = None):
    req = body or ReportManifestRequest()
    tid = _resolve_mission_topic(mid, req.topic_id)
    try:
        return compose_report_manifest(
            topic_id=tid,
            mission_id=mid,
            title=req.title,
            artifact_ids=req.artifact_ids or None,
            sections=req.sections or None,
            export_format=req.export_format,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
