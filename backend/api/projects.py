"""Research projects, the research outline (levels + attached proposal) and read-only access to project files."""
from __future__ import annotations

import mimetypes
import os
import sys
from pathlib import Path

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.api.common import call
from backend.core import bus
from backend.core.config import (activate_project, create_project, data_dir, forget_project, list_projects, open_project,
                                 rename_project)

router = APIRouter()


def _after_switch() -> None:
    """A project switch: in-process caches are dropped and the runs of the new project resume (durable execution)."""
    from backend.agent import context, runs, sessions
    from backend.memory import cache
    sessions.reset_memory()
    runs.reset_memory()
    context.clear_cache()
    cache.clear_all()
    runs.recover_all()


@router.get("/api/projects")
def projects():
    return {"projects": list_projects()}


@router.get("/api/projects/conversations")
async def project_conversations(directory: str):
    """Explicitly browse a registered project without changing the active project."""
    from backend.core.config import project_scope
    from backend.agent import sessions
    target = Path(directory).resolve()
    if not any(Path(p["data_dir"]).resolve() == target for p in list_projects()):
        raise HTTPException(404, "Project is not registered")

    def read():
        with project_scope(target):
            return {"sessions": sessions.list_sessions()}
    return await call(read)


@router.post("/api/projects")
async def projects_create(body: dict = Body(...)):
    """New project {name, data_dir?, references_dir?, outline?: {keywords|topic|direction|method|proposal}}."""
    def run():
        p = create_project(str(body.get("name", "")), body.get("data_dir"), body.get("references_dir"))
        _after_switch()
        if body.get("outline"):
            from backend.agent import outline
            outline.update(body["outline"], "researcher", "project created")
        return p
    out = await call(run)
    bus.publish("project.created", name=out.get("name", ""))
    return out


@router.post("/api/projects/open")
async def projects_open(body: dict = Body(...)):
    """Register an existing project folder (e.g. copied from another PC) and activate it."""
    out = await call(lambda: (open_project(str(body.get("data_dir", ""))), _after_switch())[0])
    bus.publish("project.opened")
    return out


@router.post("/api/projects/activate")
async def projects_activate(body: dict = Body(...)):
    out = await call(lambda: (activate_project(str(body.get("data_dir", ""))), _after_switch())[0])
    bus.publish("project.activated")
    return out


@router.put("/api/projects/rename")
async def projects_rename(body: dict = Body(...)):
    new_name = str(body.get("name", "")).strip()
    target_dir = str(body.get("data_dir", "")).strip()
    if not new_name:
        raise HTTPException(400, "Project name cannot be empty")
    out = await call(rename_project, target_dir, new_name)
    bus.publish("project.renamed", data_dir=target_dir, name=new_name)
    return out


@router.post("/api/projects/forget")
async def projects_forget(body: dict = Body(...)):
    target_dir = str(body.get("data_dir", "")).strip()
    await call(forget_project, target_dir)
    _after_switch()
    bus.publish("project.forgotten", data_dir=target_dir)
    return {"projects": list_projects()}


@router.delete("/api/projects")
async def projects_delete(data_dir: str = "", delete_files: bool = False, body: dict | None = None):
    """Delete or forget a project from PhD Lab. If delete_files=True, removes directory from disk."""
    payload = body if isinstance(body, dict) else {}
    target_dir = (data_dir or str(payload.get("data_dir") or "")).strip()
    should_delete_files = bool(delete_files or payload.get("delete_files"))
    if not target_dir:
        raise HTTPException(400, "data_dir is required")

    def run():
        import shutil
        from backend.core.config import GLOBAL_DIR, _resolve, forget_project
        d = _resolve(target_dir)
        if d == GLOBAL_DIR.resolve():
            raise HTTPException(400, "The Default project cannot be deleted")
        forget_project(str(d))
        _after_switch()
        if should_delete_files and d.exists() and d.is_dir():
            shutil.rmtree(str(d), ignore_errors=True)
        return {"ok": True, "projects": list_projects()}

    out = await call(run)
    bus.publish("project.deleted", data_dir=target_dir, delete_files=should_delete_files)
    return out


@router.post("/api/projects/reveal")
def projects_reveal(body: dict | None = None):
    """Open the project folder in the file explorer of this computer."""
    data = body if isinstance(body, dict) else {}
    target_dir = str(data.get("data_dir") or "").strip()
    path = Path(target_dir).resolve() if target_dir else data_dir()
    if sys.platform.startswith("win"):
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception:
            pass
    return {"path": str(path)}


# ------------------------------------------------------------------ outline
@router.get("/api/outline")
async def outline_get():
    from backend.agent import outline
    return await call(outline.get)


@router.put("/api/outline")
async def outline_put(body: dict = Body(...)):
    from backend.agent import outline
    return await call(outline.update, {k: v for k, v in body.items() if k in outline.LEVELS}, "researcher",
                      str(body.get("reason", "")))


@router.post("/api/outline/restore")
async def outline_restore(body: dict = Body(...)):
    from backend.agent import outline
    return await call(outline.restore, int(body.get("index", -1)))


@router.post("/api/outline/attach")
async def outline_attach(file: UploadFile = File(...)):
    from backend.agent import outline
    return await call(outline.attach, file.filename or "", await file.read())


@router.get("/api/outline/attach/{aid}")
async def outline_attachment(aid: str):
    from backend.agent import outline
    return {"id": aid, "text": await call(outline.attachment_text, aid)}


@router.delete("/api/outline/attach/{aid}")
async def outline_detach(aid: str):
    from backend.agent import outline
    return await call(outline.remove_attachment, aid)


# ------------------------------------------------------------------ project files (outputs of runs, reports)
@router.get("/api/files")
def project_file(path: str, download: int = 0):
    """A file of the active research project, read-only (paths relative to the project folder; never outside it)."""
    root = data_dir().resolve()
    p = (root / path).resolve()
    if root not in p.parents or not p.is_file():
        raise HTTPException(404, "File not found in this project")
    mt = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    if p.suffix.lower() in (".md", ".tex", ".bib", ".csv", ".jsonl", ".log", ".py", ".txt", ".yaml", ".yml"):
        mt = "text/plain; charset=utf-8"
    return FileResponse(p, media_type=mt, filename=p.name, content_disposition_type="attachment" if download else "inline")
