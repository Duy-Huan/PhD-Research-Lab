"""The project library: PDFs in the project's references folder, their metadata and BibTeX."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, PlainTextResponse

from backend.api.common import call
from backend.core import bus
from backend.core.config import data_dir, load_config, project_scope, refs_dir
from backend.knowledge.library import (PDF_BACKEND, build_bibtex, first_pages_text, load_library, merge_llm_metadata,
                                       save_library, scan_directory)

router = APIRouter()

PDF_PARSER_SYS = """You extract bibliographic metadata from the first pages of a scientific PDF. Return ONLY a JSON object:
{"title": "", "authors": ["Last, First"], "year": "", "venue": "", "entry_type": "article|inproceedings|misc|book|phdthesis",
 "volume": "", "number": "", "pages": "", "doi": "", "publisher": "", "abstract": ""}
Use exactly what the text shows; leave a field empty when it is not visible. Never invent a DOI or a venue."""


def _sorted(lib: dict) -> list:
    return sorted(lib.values(), key=lambda e: e.get("key", ""))


@router.post("/api/search")
async def search(body: dict = Body(...)):
    from backend.knowledge import websearch as WS
    query = str(body.get("query") or "").strip()
    mode = body.get("mode", "both")
    if not query or len(query) > 2000 or mode not in ("papers", "web", "both"):
        raise HTTPException(400, "Enter a search query (1–2000 characters) and mode papers, web or both")
    try:
        n = int(body.get("n_results", load_config()["search"].get("n_results", 12)))
        year = int(body["year_from"]) if body.get("year_from") else None
        if not 1 <= n <= 30 or (year and not 1900 <= year <= 2100):
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(400, "n_results must be 1–30; year_from must be 1900–2100")
    with project_scope(data_dir()):
        res = await WS.search(mode, [query], [query], n, year)
    return {**res, "sources": WS.compact(res["sources"])}


@router.post("/api/journals/import")
async def import_rankings(file: UploadFile = File(...), year: int = Form(...)):
    from backend.knowledge.ranking import import_scimago
    raw = await file.read(20 * 1024 * 1024 + 1)
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Ranking CSV must be smaller than 20 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    return await call(import_scimago, text, year)


@router.post("/api/library/save")
async def save_paper(body: dict = Body(...)):
    from backend.knowledge.library import save_source
    from backend.knowledge.download import pdf_bytes
    source = body.get("source")
    if not isinstance(source, dict):
        raise HTTPException(400, "source must be a retrieved paper record")
    with project_scope(data_dir()):
        pdf, warning = None, ""
        if source.get("pdf_url"):
            try:
                pdf = await pdf_bytes(str(source["pdf_url"]))
            except Exception:
                warning = "Đã lưu metadata. Không tải được PDF mở; bạn có thể tải PDF lên thư viện sau."
        result = await call(save_source, source, pdf)
        if not result["already_saved"] or result.get("upgraded"):
            bus.publish("library.updated", added=1)
    return {**result, "warning": warning}


@router.get("/api/library")
async def library():
    res = await run_in_threadpool(scan_directory)
    return {"references": _sorted(res["library"]), "added": res["added"], "dir": str(refs_dir()), "pdf_backend": PDF_BACKEND}


@router.post("/api/library/upload")
async def upload(files: list[UploadFile] = File(...)):
    rdir = refs_dir()
    saved, skipped = [], []
    for f in files:
        name = re.sub(r"[^\w.\- ()\[\]]", "_", Path(f.filename or "").name)
        data = await f.read()
        if not name.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
            skipped.append(name)
            continue
        (rdir / name).write_bytes(data)
        saved.append(name)
    res = await run_in_threadpool(scan_directory)
    if saved:
        bus.publish("library.updated", added=len(saved))
    return {"saved": saved, "skipped": skipped, "added": res["added"], "references": _sorted(res["library"])}


@router.post("/api/library/refine")
async def refine(body: dict = Body(...)):
    """Better metadata for one PDF from its first pages (utility agent)."""
    from backend.providers.models import call_agent, extract_json
    name = str(body.get("file", ""))
    lib = load_library()
    if name not in lib:
        raise HTTPException(404, f"{name} not in library")
    if lib[name].get("metadata_only"):
        raise HTTPException(422, "Upload a PDF before extracting metadata from its pages")
    text = await run_in_threadpool(first_pages_text, refs_dir() / name)
    if not text.strip():
        raise HTTPException(422, f"{name}: no extractable text (scanned PDF? run OCR first)")
    r = await call_agent("utility", PDF_PARSER_SYS, f"FILE: {name}\n\n{text[:12000]}", max_tokens=1500, temperature=0.0)
    try:
        data = extract_json(r["text"])
    except Exception:
        raise HTTPException(502, f"{name}: model did not return valid JSON")
    lib = load_library()
    lib[name] = merge_llm_metadata(lib[name], data)
    save_library(lib)
    return {"entry": load_library()[name], "engine": r["engine"]}


@router.put("/api/library/{name}")
async def update(name: str, body: dict = Body(...)):
    def run():
        lib = load_library()
        if name not in lib:
            raise KeyError("not found")
        e = lib[name]
        for k in ("title", "year", "venue", "entry_type", "volume", "number", "pages", "doi", "publisher", "abstract"):
            if k in body:
                e[k] = str(body[k]).strip()
        if "authors" in body:
            a = body["authors"]
            e["authors"] = [x.strip() for x in (a if isinstance(a, list) else re.split(r";|\n", a)) if x.strip()]
        if "include" in body:
            e["include"] = bool(body["include"])
        if body.get("key"):
            e["key"] = re.sub(r"[^\w:\-]", "", body["key"])
            e["key_locked"] = True
        save_library(lib)
        return load_library()[name]
    return await call(run)


@router.delete("/api/library/{name}")
async def delete(name: str):
    def run():
        from backend.knowledge.library import _lock
        with _lock:
            f = refs_dir() / Path(name).name
            if f.exists():
                f.unlink()
            lib = load_library()
            lib.pop(name, None)
            save_library(lib)
        return {"deleted": name}
    return await call(run)


@router.get("/api/library/file/{name}")
def file(name: str):
    f = refs_dir() / Path(name).name
    if not f.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(f, media_type="application/pdf", content_disposition_type="inline")


@router.get("/api/library/bib", response_class=PlainTextResponse)
def bib():
    return build_bibtex()
