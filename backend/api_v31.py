"""v3.1 routes: external research results (Experiment Design) and per-section writing briefs (Paper Writer)."""
from __future__ import annotations

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, PlainTextResponse

from . import brief as BR
from . import results as RS
from .llm import LLMError
from .paper import SECTION_TITLES, load_project, save_project

router = APIRouter()


def _err(e: Exception, code: int = 400):
    raise HTTPException(code, str(e))


# ---------------------------------------------------------------- results
@router.get("/api/results")
def results_list():
    from .context_graph import load_overlay
    ov = load_overlay()["nodes"]
    items = RS.load()
    for it in items:
        o = ov.get(f"result:{it['id']}", {})
        it["pinned"], it["purged"] = bool(o.get("pinned")), bool(o.get("purged"))
    runs = 0
    try:
        from .sandbox import list_runs
        runs = sum(1 for r in list_runs(200) if r.get("status") == "done")
    except Exception:
        pass
    return {"items": items, "kinds": RS.KINDS, "runs": runs}


@router.get("/api/results/pool")
def results_pool():
    return {"pool": RS.pool(), "present_as": list(BR.PRESENT_HELP)}


@router.post("/api/results/upload")
async def results_upload(files: list[UploadFile] = File(...), notes: str = Form(""), tags: str = Form("")):
    out, errors = [], []
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    for f in files:
        try:
            out.append(await run_in_threadpool(RS.add_file, f.filename or "file", await f.read(), "", notes, tag_list))
        except RS.ResultError as e:
            errors.append(str(e))
    return {"items": out, "errors": errors}


@router.post("/api/results/note")
def results_note(body: dict = Body(...)):
    try:
        return {"item": RS.add_note(body.get("title", ""), body.get("text", ""), body.get("tags") or [], body.get("kind", "note"))}
    except RS.ResultError as e:
        _err(e)


@router.put("/api/results/{rid}")
def results_update(rid: str, body: dict = Body(...)):
    try:
        return {"item": RS.update(rid, body)}
    except RS.ResultError as e:
        _err(e, 404)


@router.delete("/api/results/{rid}")
def results_delete(rid: str):
    try:
        out = RS.delete(rid)
    except RS.ResultError as e:
        _err(e, 404)
    # drop it from every section brief
    p = load_project()
    for sid, b in (p.get("section_briefs") or {}).items():
        if b and b.get("results"):
            b["results"] = [r for r in b["results"] if r.get("ref") != f"up:{rid}"]
    save_project(p)
    return out


@router.get("/api/results/{rid}/file")
def results_file(rid: str, download: int = 0):
    try:
        p = RS.file_path(rid)
    except RS.ResultError as e:
        _err(e, 404)
    it = RS.get(rid)
    media = RS.IMAGE_MIME.get(it.get("ext", "")) or ("application/pdf" if it.get("ext") == ".pdf" else None)
    if it.get("ext") == ".svg" and not download:
        # never render uploaded SVG as a document of this origin (it could contain script)
        return FileResponse(p, media_type="image/svg+xml", headers={"Content-Security-Policy": "script-src 'none'"})
    return FileResponse(p, media_type=media, filename=it["file"], content_disposition_type="attachment" if download else "inline")


@router.get("/api/results/{rid}/text", response_class=PlainTextResponse)
def results_text(rid: str):
    try:
        RS.get(rid)
    except RS.ResultError as e:
        _err(e, 404)
    return RS.text(rid)


@router.post("/api/results/{rid}/analyze")
async def results_analyze(rid: str):
    try:
        return await RS.analyze(rid)
    except RS.ResultError as e:
        _err(e)
    except LLMError as e:
        _err(e, 502)


@router.post("/api/results/{rid}/latex-table")
async def results_latex_table(rid: str, body: dict = Body(default={})):
    try:
        r = await RS.to_latex_table(rid)
    except RS.ResultError as e:
        _err(e)
    except LLMError as e:
        _err(e, 502)
    if body.get("add") and r["latex"]:
        p = load_project()
        if r["latex"] not in p["tables"]:
            p["tables"].append(r["latex"])
            save_project(p)
        r["table_index"] = p["tables"].index(r["latex"])
    return r


@router.post("/api/results/to-section")
def results_to_section(body: dict = Body(...)):
    """Add pool items to a section's brief: {section, refs: [...], as}."""
    sid = body.get("section")
    if sid not in SECTION_TITLES:
        raise HTTPException(400, "Unknown section")
    p = load_project()
    briefs = p.setdefault("section_briefs", {})
    b = BR.clean_brief(briefs.get(sid) or {})
    have = {r["ref"] for r in b["results"]}
    titles = {x["ref"]: x["title"] for x in RS.pool()}
    for ref in body.get("refs") or []:
        if ref not in have and ref in titles:
            b["results"].append({"ref": ref, "as": body.get("as") if body.get("as") in BR.PRESENT_HELP else "auto", "note": "",
                                 "title": titles[ref]})
    briefs[sid] = BR.clean_brief(b)
    save_project(p)
    return {"brief": _enrich(BR.get_brief(p, sid))}


# ---------------------------------------------------------------- briefs
@router.get("/api/paper/brief")
def brief_get(section: str = ""):
    p = load_project()
    out = {"paper_brief": BR.clean_paper_brief(p.get("paper_brief") or {}),
           "options": {"tones": list(BR.TONES), "lengths": list(BR.LENGTHS), "present_as": list(BR.PRESENT_HELP)},
           "summary": {sid: _summary(BR.get_brief(p, sid)) for sid in SECTION_TITLES}}
    if section in SECTION_TITLES:
        out["brief"] = _enrich(BR.get_brief(p, section))
    return out


def _enrich(b: dict) -> dict:
    """Add display info (kind, thumbnail, still-available) to the brief's results for the UI."""
    pool = {x["ref"]: x for x in RS.pool()}
    for r in b.get("results") or []:
        x = pool.get(r["ref"])
        r.update({"kind": x["kind"], "thumb": x["thumb"], "figure_ok": x["figure_ok"], "missing": False} if x else {"missing": True})
        if x and not r.get("title"):
            r["title"] = x["title"]
    return b


def _summary(b: dict) -> dict:
    return {"empty": BR.is_empty(b), "results": len(b["results"]), "outline": len(b["outline"]),
            "directions": bool(b.get("directions", "").strip())}


@router.put("/api/paper/brief")
def brief_put(body: dict = Body(...)):
    p = load_project()
    if "paper_brief" in body:
        p["paper_brief"] = BR.clean_paper_brief(body["paper_brief"])
    sid = body.get("section")
    if sid in SECTION_TITLES and isinstance(body.get("brief"), dict):
        b = body["brief"]
        if "directions" in b:
            p.setdefault("section_notes", {})[sid] = str(b.get("directions") or "")[:12000]
        p.setdefault("section_briefs", {})[sid] = BR.clean_brief(b)
    save_project(p)
    return {"ok": True, "brief": _enrich(BR.get_brief(p, sid)) if sid in SECTION_TITLES else None,
            "paper_brief": BR.clean_paper_brief(p.get("paper_brief") or {})}


@router.post("/api/paper/brief/copy")
def brief_copy(body: dict = Body(...)):
    """Copy the structured brief of one section to others (directions included): {from, to: [...]}"""
    src, dst = body.get("from"), [s for s in body.get("to") or [] if s in SECTION_TITLES]
    if src not in SECTION_TITLES:
        raise HTTPException(400, "Unknown section")
    p = load_project()
    b = BR.get_brief(p, src)
    for d in dst:
        p.setdefault("section_briefs", {})[d] = BR.clean_brief(b)
        p.setdefault("section_notes", {})[d] = b.get("directions", "")
    save_project(p)
    return {"copied": dst}


@router.get("/api/paper/brief/preview", response_class=PlainTextResponse)
def brief_preview(section: str):
    """Exactly what the Author agent receives from the brief (transparency)."""
    if section not in SECTION_TITLES:
        raise HTTPException(400, "Unknown section")
    from .library import included
    p = load_project()
    return BR.render(p, section, "author", [e["key"] for e in included()]) or "(empty brief — the agent uses the generic section guidance)"
