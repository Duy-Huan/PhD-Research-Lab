"""The paper: sections written through the chat (/write → accepted proposals), LaTeX → PDF, export."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, PlainTextResponse, Response

from backend.api.common import call
from backend.paper import latex as LB
from backend.paper.writer import SECTION_TITLES, SECTIONS, build_zip, load_project, save_project

router = APIRouter()


@router.get("/api/paper")
async def paper():
    def run():
        p = load_project()
        return {"title": p["title"], "authors": p["authors"], "style": p["style"], "venue": p.get("venue", ""),
                "sections": [{"id": sid, "title": t, "text": p["sections"].get(sid, ""),
                              "state": p["section_state"].get(sid, ""),
                              "versions": len((p.get("section_history") or {}).get(sid, []))} for sid, t in SECTIONS],
                "pdf": (LB.build_dir() / "main.pdf").exists()}
    return await call(run)


@router.put("/api/paper")
async def paper_update(body: dict = Body(...)):
    def run():
        p = load_project()
        for k in ("title", "authors", "style", "venue", "keywords"):
            if k in body:
                p[k] = str(body[k])[:2000]
        save_project(p)
        return {"ok": True}
    return await call(run)


@router.put("/api/paper/section")
async def section(body: dict = Body(...)):
    """Direct edit of a section (the chat path is /write → proposal → Accept)."""
    sid = body.get("section")
    if sid not in SECTION_TITLES:
        raise HTTPException(400, "Unknown section")

    def run():
        p = load_project()
        old = p["sections"].get(sid, "")
        new = str(body.get("text") or "")
        if old and old != new:
            p.setdefault("section_history", {}).setdefault(sid, []).append(old)
            p["section_history"][sid] = p["section_history"][sid][-10:]
        p["sections"][sid] = new
        p["section_state"][sid] = "edited" if new else ""
        save_project(p)
        return {"ok": True}
    return await call(run)


@router.get("/api/paper/engines")
async def paper_engines():
    """Returns detected local engines and online compilation availability."""
    return await run_in_threadpool(LB.engines)


@router.post("/api/paper/engines/online")
async def toggle_online_compilation(body: dict = Body(default={})):
    """Toggle online LaTeX compilation permission in project/global config."""
    from backend.core.config import save_config
    enabled = bool(body.get("enabled", True))
    save_config({"latex_online": enabled})
    return await run_in_threadpool(LB.engines)


@router.post("/api/paper/compile")
async def compile_pdf(body: dict = Body(default={})):
    try:
        raw_engine = str(body.get("engine", "")).strip()
        layout = str(body.get("layout", "template")).strip()
        allow_online = body.get("allow_online")

        # Auto-enable latex_online in config if explicitly requested
        if raw_engine == "online" or allow_online is True:
            from backend.core.config import load_config, save_config
            if not load_config().get("latex_online"):
                save_config({"latex_online": True})

        if raw_engine == "local":
            eng_info = LB.engines()
            engine = eng_info["available"][0] if eng_info["available"] else ""
        else:
            engine = raw_engine

        return await run_in_threadpool(LB.compile_pdf, engine, layout)
    except LB.NoEngine as e:
        raise HTTPException(424, {"message": str(e), "install_help": LB.install_help()})
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.get("/api/paper/tex", response_class=PlainTextResponse)
def tex():
    """Return the assembled main.tex source code."""
    f = LB.build_dir() / "main.tex"
    if f.exists():
        return f.read_text("utf-8", "replace")
    from backend.paper.writer import assemble
    main, _, _ = assemble()
    return main


@router.get("/api/paper/pdf")
def pdf(download: int = 0):
    f = LB.build_dir() / "main.pdf"
    if not f.exists():
        raise HTTPException(404, "No PDF yet — type /latex in the chat")
    return FileResponse(f, media_type="application/pdf", filename="main.pdf",
                        content_disposition_type="attachment" if download else "inline", headers={"Cache-Control": "no-store"})


@router.get("/api/paper/log", response_class=PlainTextResponse)
def log():
    f = LB.build_dir() / "build.log"
    return f.read_text("utf-8", "replace") if f.exists() else "(no build log yet)"


@router.get("/api/paper/latex.zip")
async def export_zip():
    data = await run_in_threadpool(build_zip)
    return Response(data, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="latex.zip"'})
