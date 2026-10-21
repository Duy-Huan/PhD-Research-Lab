"""Plugins and tools: GitHub skill plugins (stored in <data>/plugins), automatic venue ranking, the AI-Scientist-v2
manuscript writer and document export (.md · .tex · .docx · .html · .pdf)."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from backend.api.common import call, sse_job
from backend.core import bus
from backend.core.config import data_dir, load_config, project_scope

router = APIRouter()


# ------------------------------------------------------------------ GitHub skill plugins
@router.get("/api/plugins")
async def plugins_list():
    from backend import plugins as PG
    from backend.plugins import ai_scientist
    return {"plugins": await call(PG.list_plugins), "root": str(PG.root()), "ai_scientist": await call(ai_scientist.status)}


@router.post("/api/plugins")
async def plugins_install(body: dict = Body(...)):
    """{url: github.com/owner/repo[/tree/ref/dir], enable?: true} — downloads one commit into <data>/plugins/<id>/."""
    from backend import plugins as PG
    url = str(body.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "Enter a GitHub repository URL")
    try:
        out = await call(PG.install, url, bool(body.get("enable", True)))
    except HTTPException:
        raise
    except Exception as e:  # network / GitHub errors are the researcher's to see, not a 500
        raise HTTPException(502, f"Could not download the plugin: {e}")
    bus.publish("config.updated", keys="plugins")
    return out


@router.post("/api/plugins/{pid}/update")
async def plugins_update(pid: str):
    from backend import plugins as PG
    try:
        out = await call(PG.update, pid)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Could not update the plugin: {e}")
    bus.publish("config.updated", keys="plugins")
    return out


@router.put("/api/plugins/{pid}")
async def plugins_toggle(pid: str, body: dict = Body(...)):
    """{enabled: bool} for the active research project."""
    from backend import plugins as PG
    out = await call(PG.set_enabled, pid, bool(body.get("enabled")))
    bus.publish("config.updated", keys="plugins")
    return out


@router.put("/api/plugins/skills/{name}")
async def plugins_skill_toggle(name: str, body: dict = Body(...)):
    from backend import plugins as PG
    out = await call(PG.set_skill, name, bool(body.get("enabled")))
    bus.publish("config.updated", keys="plugins")
    return out


@router.delete("/api/plugins/{pid}")
async def plugins_remove(pid: str):
    from backend import plugins as PG
    out = await call(PG.remove, pid)
    bus.publish("config.updated", keys="plugins")
    return out


# ------------------------------------------------------------------ automatic venue ranking
@router.get("/api/ranking")
async def ranking_status(refresh: int = 0):
    from backend.knowledge import ranking as RK
    done = await run_in_threadpool(RK.auto_refresh, load_config(), bool(refresh))
    return {**await run_in_threadpool(RK.status), "refreshed": done}


@router.get("/api/ranking/lookup")
async def ranking_lookup(venue: str = "", issn: str = ""):
    from backend.knowledge import ranking as RK
    if not venue.strip() and not issn.strip():
        raise HTTPException(400, "Give a venue name or an ISSN")
    return await run_in_threadpool(RK.lookup, venue[:400], issn[:40])


@router.post("/api/library/rank")
async def library_rank(body: dict = Body(default={})):
    """Check the venue ranking of every library entry (or {files: [...]}) from local SCImago / CORE data."""
    from backend.knowledge import ranking as RK
    from backend.knowledge.library import load_library, save_library

    def run():
        RK.auto_refresh(load_config())
        with project_scope(data_dir()):
            lib = load_library()
            want = set(body.get("files") or [])
            n = {"ranked": 0, "conference": 0, "unavailable": 0}
            for name, e in lib.items():
                if want and name not in want:
                    continue
                r = RK.rank_entry(e)
                if r:
                    e["journal_ranking"] = r
                    n[r["status"]] = n.get(r["status"], 0) + 1
            save_library(lib)
        return {"checked": sum(n.values()), **n}
    out = await call(run)
    bus.publish("library.updated", ranked=out["checked"])
    return out


# ------------------------------------------------------------------ AI-Scientist-v2 manuscript writer
@router.get("/api/paper/ais")
async def ais_status():
    from backend.plugins import ai_scientist as AS
    st = await call(AS.status)
    out = AS._out_dir() if st.get("installed") else None
    st["has_tex"] = bool(out and (out / "template.tex").is_file())
    st["has_pdf"] = bool(out and (out / "template.pdf").is_file())
    return st


@router.post("/api/paper/ais/install")
async def ais_install():
    from backend import plugins as PG
    from backend.plugins import ai_scientist as AS
    try:
        out = await call(PG.install, AS.URL, True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Could not download AI-Scientist-v2: {e}")
    bus.publish("config.updated", keys="plugins")
    return out


@router.post("/api/paper/ais/writeup")
def ais_writeup(body: dict = Body(default={})):
    """Stream the full manuscript in the AI Scientist template (start → delta… → done {path, dropped_citations})."""
    from backend.plugins import ai_scientist as AS
    try:
        system, user, out = AS.prepare(str(body.get("template") or "icml"))
    except Exception as e:
        raise HTTPException(400, str(e))
    return sse_job("research", system, user, lambda m: AS.finish(m["text"], out), max_tokens=16000, temperature=0.3,
                   start={"stage": "writeup"})


@router.post("/api/paper/ais/compile")
async def ais_compile():
    from backend.plugins import ai_scientist as AS
    return await call(AS.compile_pdf)


@router.get("/api/paper/ais/download/{kind}")
async def ais_download(kind: str):
    from backend.plugins import ai_scientist as AS
    out = AS._out_dir()
    if kind == "tex" and (out / "template.tex").is_file():
        return FileResponse(out / "template.tex", filename="ai_scientist_paper.tex", media_type="application/x-tex")
    if kind == "pdf" and (out / "template.pdf").is_file():
        return FileResponse(out / "template.pdf", filename="ai_scientist_paper.pdf", media_type="application/pdf")
    if kind == "zip" and (out / "template.tex").is_file():
        return Response(await call(AS.bundle), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="ai_scientist_paper.zip"'})
    raise HTTPException(404, "Nothing to download yet — write (and compile) the manuscript first")


# ------------------------------------------------------------------ export
@router.get("/api/export/capabilities")
def export_caps():
    from backend.paper import export as EX
    return {"formats": list(EX.FORMATS), "pdf": bool(EX.browser())}


async def export_project_scope():
    with project_scope(data_dir()):
        yield


@router.post("/api/export", dependencies=[Depends(export_project_scope)])
async def export(body: dict = Body(...)):
    """{format: md|tex|docx|html|pdf, title, markdown, html?, images?: {"chart-0": dataURL}} → the file (a copy is kept in
    <workspace>/exports/)."""
    from backend.paper import export as EX
    fmt = str(body.get("format") or "")
    images = body.get("images") if isinstance(body.get("images"), dict) else {}
    lang = (load_config().get("ui") or {}).get("language", "vi")
    topic_id=str(body.get("topic_id") or "")
    if topic_id:
        from backend.knowledge.research_store import get_topic
        await call(get_topic,topic_id)
    try:
        data, name, mime = await run_in_threadpool(EX.export, fmt, str(body.get("title") or "")[:200],
                                                   str(body.get("markdown") or ""), str(body.get("html") or ""), images, lang, **({"topic_id":topic_id} if topic_id else {}))
    except EX.ExportError as e:
        raise HTTPException(501 if "No Edge" in str(e) else 400, str(e))
    await run_in_threadpool(EX.save_copy, data, name)
    from urllib.parse import quote
    return Response(data, media_type=mime, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
