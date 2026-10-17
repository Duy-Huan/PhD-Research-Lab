"""FastAPI server for the PhD Interactive Autonomous Research Lab.

Run:  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
"""
import os
import re
import sys
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from . import prompts
from .config import APP_VERSION, ROOT, load_config, public_config, refs_dir, save_config
from .library import (PDF_BACKEND, build_bibtex, first_pages_text, included, load_library,
                      merge_llm_metadata, reference_digest, save_library, scan_directory)
from .llm import (LLMError, call_agent, cloud_chat, extract_json, list_local_models, list_provider_models,
                  provider_settings, strip_fences)
from .paper import (SECTION_TITLES, SECTIONS, assemble, build_zip, clean_section,
                    fix_citations, load_project, read_ws, save_project, write_ws)

app = FastAPI(title="PhD Interactive Autonomous Research Lab", version=APP_VERSION)
FRONTEND = ROOT / "frontend" / "index.html"


@app.exception_handler(LLMError)
async def llm_error_handler(_, exc: LLMError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/")
def index():
    return FileResponse(FRONTEND)


# ================================================================ configuration
@app.get("/api/config")
def get_config():
    return public_config(load_config())


@app.post("/api/config")
def set_config(body: dict = Body(...)):
    return public_config(save_config(body))


@app.post("/api/test/provider")
async def test_provider(body: dict = Body(...)):
    pid = body.get("provider", "")
    cfg = load_config()
    _, _, model, _ = provider_settings(cfg, pid)
    text = await cloud_chat(cfg, pid, "Reply with the single word: OK", [{"role": "user", "content": "ping"}], 256)
    return {"ok": True, "model": model, "reply": (text.strip() or "(empty reply - connection OK)")[:80]}


@app.post("/api/provider/models")
async def provider_models(body: dict = Body(...)):
    return {"models": await list_provider_models(load_config(), body.get("provider", ""))}


@app.get("/api/local/models")
async def local_models():
    cfg = load_config()
    return {"models": await list_local_models(cfg["lmstudio_base_url"])}


@app.post("/api/references/open")
def open_refs_folder():
    path = refs_dir()
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')
    return {"path": str(path)}


# ================================================================ reference library
@app.get("/api/references")
async def list_references():
    res = await run_in_threadpool(scan_directory)
    return {"references": sorted(res["library"].values(), key=lambda e: e.get("key", "")),
            "added": res["added"], "dir": str(refs_dir()), "pdf_backend": PDF_BACKEND}


@app.post("/api/references/upload")
async def upload_references(files: list[UploadFile] = File(...)):
    rdir = refs_dir()
    saved = []
    for f in files:
        name = Path(f.filename or "").name
        if not name.lower().endswith(".pdf"):
            continue
        name = re.sub(r"[^\w.\- ()\[\]]", "_", name)
        data = await f.read()
        if not data.startswith(b"%PDF"):
            continue
        (rdir / name).write_bytes(data)
        saved.append(name)
    res = await run_in_threadpool(scan_directory)
    return {"saved": saved, "added": res["added"],
            "references": sorted(res["library"].values(), key=lambda e: e.get("key", ""))}


async def _refine(name: str, agent: str) -> dict:
    lib = load_library()
    if name not in lib:
        raise HTTPException(404, f"{name} not in library")
    entry = lib[name]
    text = await run_in_threadpool(first_pages_text, refs_dir() / name)
    if not text.strip():
        raise HTTPException(422, f"{name}: no extractable text (scanned PDF? run OCR first)")
    r = await call_agent(agent, prompts.PDF_PARSER_SYS, prompts.pdf_parser_user(name, entry, text),
                         max_tokens=1500, temperature=0.0)
    try:
        data = extract_json(r["text"])
    except Exception:
        raise HTTPException(502, f"{name}: model did not return valid JSON")
    lib = load_library()  # reload: other requests may have run
    lib[name] = merge_llm_metadata(lib[name], data)
    save_library(lib)
    return {"entry": load_library()[name], "engine": r["engine"], "note": r["note"]}


@app.post("/api/references/refine")
async def refine_reference(body: dict = Body(...)):
    return await _refine(body["file"], body.get("agent", "pdf_parser"))


@app.put("/api/references/{name}")
def update_reference(name: str, body: dict = Body(...)):
    lib = load_library()
    if name not in lib:
        raise HTTPException(404, "not found")
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


@app.delete("/api/references/{name}")
def delete_reference(name: str):
    f = refs_dir() / Path(name).name
    if f.exists():
        f.unlink()
    scan_directory()
    return {"deleted": name}


@app.post("/api/bib/generate")
async def generate_bib(body: dict = Body(default={})):
    """Agent 3.1: normalise any un-refined entries with the bib_extractor agent, then format BibTeX."""
    notes = []
    if body.get("refine", True):
        for e in [e for e in included() if not e.get("llm_refined")]:
            try:
                r = await _refine(e["file"], "bib_extractor")
                if r["note"]:
                    notes.append(r["note"])
            except (HTTPException, LLMError) as ex:
                notes.append(f"{e['file']}: {getattr(ex, 'detail', ex)} (kept heuristic metadata)")
    bib = build_bibtex()
    write_ws("references.bib", bib)
    return {"bib": bib, "notes": notes, "count": len(included())}


@app.get("/api/bib", response_class=PlainTextResponse)
def get_bib():
    return build_bibtex()


# ================================================================ Tool 1 & 2
@app.post("/api/tool/lit2plan")
async def lit2plan(body: dict = Body(...)):
    idea = body.get("idea", "").strip()
    if not idea:
        raise HTTPException(400, "Research idea is required")
    exp = await call_agent("query_expansion", prompts.QUERY_EXPANSION_SYS,
                           f"Idea: {idea}\nDomain: {body.get('domain', '')}", max_tokens=1500, temperature=0.3)
    digest = reference_digest(included()[:40], 350)
    plan = await call_agent("lit2plan", prompts.LIT2PLAN_SYS,
                            prompts.lit2plan_user(idea, body.get("domain", ""), exp["text"], digest), max_tokens=10000)
    write_ws("lit2plan.md", plan["text"])
    return {"expansion": exp["text"], "plan": plan["text"],
            "engines": {"query_expansion": exp["engine"], "lit2plan": plan["engine"]},
            "notes": [n for n in (exp["note"], plan["note"]) if n]}


@app.post("/api/tool/experiment")
async def experiment(body: dict = Body(...)):
    if not body.get("novelty", "").strip():
        raise HTTPException(400, "Novelty proposal is required")
    r = await call_agent("experiment", prompts.EXPERIMENT_SYS,
                         prompts.experiment_user(body["novelty"], body.get("domain", ""), body.get("constraints", "")),
                         max_tokens=16000)
    code_blocks = re.findall(r"```python\n(.*?)```", r["text"], flags=re.S)
    code = max(code_blocks, key=len) if code_blocks else "# Model did not return a code block. Re-run the generator.\n"
    write_ws("experiment_design.md", r["text"])
    write_ws("experiment_skeleton.py", code)
    return {"design": r["text"], "code": code, "engine": r["engine"], "note": r["note"]}


DOWNLOADABLE = {"lit2plan.md", "experiment_design.md", "experiment_skeleton.py", "main.tex",
                "references.bib", "review.md"}


@app.get("/api/download/{name}")
def download(name: str):
    if name == "references.bib":
        write_ws(name, build_bibtex())
    if name not in DOWNLOADABLE or not read_ws(name):
        raise HTTPException(404, "Not generated yet")
    return Response(read_ws(name), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ================================================================ Tool 3: chat console
@app.post("/api/chat")
async def chat(body: dict = Body(...)):
    msgs = [m for m in body.get("messages", []) if m.get("role") in ("user", "assistant") and m.get("content")]
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(400, "Last message must be from the user")
    msgs = msgs[-12:]
    if msgs[0]["role"] != "user":
        msgs = msgs[1:]
    system = prompts.DATA_EXTRACTOR_SYS + "\n\nLOCAL LIBRARY:\n" + reference_digest(included()[:30], 200)
    r = await call_agent("data_extractor", system, messages=msgs, max_tokens=6000, temperature=0.1)
    tables = re.findall(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", r["text"], flags=re.S)
    return {"reply": r["text"], "tables": tables, "engine": r["engine"], "note": r["note"]}


# ================================================================ Tool 3: paper pipeline
@app.get("/api/paper/project")
def get_project():
    p = load_project()
    return {"project": p, "sections": SECTIONS, "main_tex": read_ws("main.tex")}


@app.post("/api/paper/project")
def update_project(body: dict = Body(...)):
    p = load_project()
    for k in ("title", "authors", "style", "keywords", "contribution", "method_notes", "results_notes"):
        if k in body:
            p[k] = body[k]
    return {"project": save_project(p)}


@app.post("/api/paper/tables")
def add_table(body: dict = Body(...)):
    p = load_project()
    t = body.get("latex", "").strip()
    if t and t not in p["tables"]:
        p["tables"].append(t)
    return {"project": save_project(p)}


@app.delete("/api/paper/tables/{idx}")
def delete_table(idx: int):
    p = load_project()
    if 0 <= idx < len(p["tables"]):
        p["tables"].pop(idx)
    return {"project": save_project(p)}


@app.post("/api/paper/draft")
async def draft_section(body: dict = Body(...)):
    sid = body.get("section")
    if sid not in SECTION_TITLES:
        raise HTTPException(400, f"Unknown section {sid}")
    p = load_project()
    entries = included()
    keys = [e["key"] for e in entries]
    r = await call_agent("author", prompts.AUTHOR_SYS,
                         prompts.author_user(sid, SECTION_TITLES[sid], p, reference_digest(entries), keys),
                         max_tokens=8000, temperature=0.4)
    tex = clean_section(sid, strip_fences(r["text"]))
    tex, unknown = fix_citations(tex, set(keys))
    p = load_project()
    p["sections"][sid] = tex
    save_project(p)
    return {"section": sid, "latex": tex, "unknown_citations": unknown, "engine": r["engine"], "note": r["note"]}


@app.put("/api/paper/section")
def save_section(body: dict = Body(...)):
    sid = body.get("section")
    if sid not in SECTION_TITLES:
        raise HTTPException(400, "Unknown section")
    p = load_project()
    p["sections"][sid] = body.get("latex", "")
    save_project(p)
    return {"ok": True}


@app.post("/api/paper/assemble")
def assemble_paper():
    main, bib, report = assemble()
    return {"main_tex": main, "bib": bib, "report": report}


@app.post("/api/paper/review")
async def review_paper():
    main, _, report = assemble()
    entries = included()
    r = await call_agent("reviewer", prompts.REVIEWER_SYS,
                         prompts.reviewer_user(main, reference_digest(entries, 400), report), max_tokens=8000)
    p = load_project()
    p["review"] = r["text"]
    save_project(p)
    write_ws("review.md", r["text"])
    return {"review": r["text"], "report": report, "engine": r["engine"], "note": r["note"]}


@app.post("/api/paper/revise")
async def revise_section(body: dict = Body(...)):
    sid = body.get("section")
    p = load_project()
    if not p.get("review"):
        raise HTTPException(400, "Run the Peer Reviewer (3.3) first")
    current = (p.get("sections") or {}).get(sid)
    if not current:
        return {"section": sid, "skipped": True}
    entries = included()
    keys = [e["key"] for e in entries]
    r = await call_agent("editor", prompts.EDITOR_SYS,
                         prompts.editor_user(sid, current, p["review"], keys, reference_digest(entries, 300)),
                         max_tokens=8000, temperature=0.2)
    tex = clean_section(sid, strip_fences(r["text"]))
    tex, unknown = fix_citations(tex, set(keys))
    if len(tex) < 0.3 * len(current):  # guard against truncated / degenerate rewrites
        return {"section": sid, "latex": current, "rejected": True,
                "note": "Revision discarded: output was much shorter than the original section."}
    p = load_project()
    p["sections"][sid] = tex
    save_project(p)
    return {"section": sid, "latex": tex, "unknown_citations": unknown, "engine": r["engine"], "note": r["note"]}


@app.get("/api/export/latex.zip")
async def export_zip():
    data = await run_in_threadpool(build_zip)
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="latex.zip"'})


# ================================================================ Tool 4
@app.post("/api/masterclass")
async def masterclass(body: dict = Body(...)):
    topic = body.get("topic", "").strip()
    if not topic:
        raise HTTPException(400, "Topic required")
    user = f"MILESTONE: {topic}\n\nRESEARCHER CONTEXT:\n{body.get('context') or '(none provided)'}"
    r = await call_agent("masterclass", prompts.MASTERCLASS_SYS, user, max_tokens=8000, temperature=0.4)
    return {"guide": r["text"], "engine": r["engine"], "note": r["note"]}
