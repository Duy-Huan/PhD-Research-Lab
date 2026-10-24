"""HTTP API for v6.4.0 Scientific Visualization & Figure Studio and v6.4.2 Figure Integrity."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.api.common import call
from backend.core.config import data_dir, project_scope
from backend.figures import renderers, store
from backend.figures.contracts import FigureSpec
from backend.knowledge import research_store as S


async def bind_project():
    with project_scope(data_dir()):
        yield


router = APIRouter(dependencies=[Depends(bind_project)])


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/figures/capabilities")
async def figure_capabilities():
    return await call(renderers.probe_capabilities)


@router.get("/api/research/topics/{tid}/figures")
async def list_topic_figures(tid: str):
    return {"figures": await call(_safe, store.list_figures, tid)}


@router.post("/api/research/topics/{tid}/figures")
async def create_topic_figure(tid: str, body: dict = Body(...)):
    payload = {**body, "topic_id": tid}
    spec = _safe(FigureSpec.model_validate, payload)
    return await call(_safe, store.create_or_regenerate, spec)


@router.get("/api/research/topics/{tid}/figures/{fid}")
async def get_topic_figure(tid: str, fid: str, version: int = 0):
    return await call(_safe, store.get_figure, tid, fid, version)


@router.put("/api/research/topics/{tid}/figures/{fid}/style")
async def update_figure_style(tid: str, fid: str, body: dict = Body(...)):
    style_patch = body.get("style") if isinstance(body.get("style"), dict) else body
    title = str(body.get("title") or "")
    caption = str(body.get("caption") or "")
    return await call(_safe, store.update_style, tid, fid, style_patch, title, caption)


@router.post("/api/research/topics/{tid}/figures/{fid}/regenerate")
async def regenerate_topic_figure(tid: str, fid: str, body: dict = Body(default={})):
    def run():
        cur = store.get_figure(tid, fid)
        merged = {**cur["spec"], **body, "topic_id": tid, "figure_id": fid}
        spec = FigureSpec.model_validate(merged)
        return store.create_or_regenerate(spec, figure_id=fid)
    return await call(_safe, run)


@router.post("/api/research/topics/{tid}/figures/{fid}/validate")
async def validate_topic_figure(tid: str, fid: str, body: dict = Body(default={})):
    version = int(body.get("version") or 0)
    return await call(_safe, store.validate_figure_version, tid, fid, version)


@router.post("/api/figures/{fid}/validate")
async def validate_figure_direct(fid: str, body: dict = Body(default={})):
    """v6.4.2 Module E direct endpoint `/api/figures/{id}/validate`."""
    def run():
        with S.db() as c:
            row = c.execute("SELECT topic_id FROM figures WHERE id=?", (fid,)).fetchone()
            if not row:
                raise ValueError("Figure not found")
            tid = row[0]
        version = int(body.get("version") or 0)
        return store.validate_figure_version(tid, fid, version)
    return await call(_safe, run)


@router.post("/api/research/topics/{tid}/figures/{fid}/approve")
async def approve_topic_figure(tid: str, fid: str, body: dict = Body(...)):
    version = int(body.get("version") or 0)
    note = str(body.get("note") or "")
    return await call(_safe, store.approve_figure, tid, fid, version, note)


@router.post("/api/research/topics/{tid}/figures/{fid}/attach-paper")
async def attach_figure_to_paper(tid: str, fid: str, body: dict = Body(default={})):
    section = str(body.get("section") or "experiments")
    version = int(body.get("version") or 0)
    return await call(_safe, store.attach_to_paper, tid, fid, section, version)


@router.get("/api/research/topics/{tid}/figures/{fid}/export/{fmt}")
def export_topic_figure(tid: str, fid: str, fmt: str, version: int = 0):
    p = _safe(store.export_file_path, tid, fid, fmt, version)
    mime_map = {
        "svg": "image/svg+xml",
        "png": "image/png",
        "pdf": "application/pdf",
        "html": "text/html; charset=utf-8",
        "dot": "text/vnd.graphviz; charset=utf-8",
        "script": "text/x-python; charset=utf-8",
        "spec": "text/yaml; charset=utf-8",
        "provenance": "application/json",
    }
    return FileResponse(
        p,
        media_type=mime_map.get(fmt, "application/octet-stream"),
        filename=f"{fid}_v{(version or 1):04d}.{p.suffix.lstrip('.')}",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data: self;",
        },
    )
