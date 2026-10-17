"""FastAPI server for the PhD Interactive Autonomous Research Lab.

Run:  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
"""
import json
import os
import re
import sys
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from . import prompts
from .config import (APP_VERSION, ROOT, activate_project, create_project, data_dir, forget_project, list_projects,
                     load_config, open_project, public_config, refs_dir, rename_project, save_config)
from .library import (PDF_BACKEND, build_bibtex, first_pages_text, included, load_library,
                      merge_llm_metadata, reference_digest, save_library, scan_directory)
from .context_hub import add_note, build_shared_context, delete_note, load_notes, tool_output
from .chat_store import (TOOLS, SessionNotFound, create_session, delete_session, get_active, list_sessions,
                         load_session, record_turn, save_session)
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


def _open_in_explorer(path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')


@app.post("/api/references/open")
def open_refs_folder():
    path = refs_dir()
    _open_in_explorer(path)
    return {"path": str(path)}


# ================================================================ research projects
def _project_call(fn, *args):
    try:
        return fn(*args)
    except (ValueError, FileNotFoundError, OSError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/projects")
def projects():
    """All registered research projects; each has its own data folder and references folder."""
    return {"projects": list_projects()}


@app.post("/api/projects")
def projects_create(body: dict = Body(...)):
    """New project: {name, data_dir?, references_dir?}. Becomes the active project."""
    return _project_call(create_project, body.get("name", ""), body.get("data_dir"), body.get("references_dir"))


@app.post("/api/projects/open")
def projects_open(body: dict = Body(...)):
    """Register an existing project folder (e.g. copied from another PC) and activate it."""
    return _project_call(open_project, body.get("data_dir", ""))


@app.post("/api/projects/activate")
def projects_activate(body: dict = Body(...)):
    return _project_call(activate_project, body.get("data_dir", ""))


@app.put("/api/projects/rename")
def projects_rename(body: dict = Body(...)):
    return _project_call(rename_project, body.get("data_dir", ""), body.get("name", ""))


@app.post("/api/projects/forget")
def projects_forget(body: dict = Body(...)):
    """Remove from the list only - no files are deleted."""
    _project_call(forget_project, body.get("data_dir", ""))
    return {"projects": list_projects()}


@app.post("/api/projects/open-folder")
def projects_open_folder():
    path = data_dir()
    _open_in_explorer(path)
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
    history = [m for m in body.get("messages", []) if m.get("role") in ("user", "assistant") and m.get("content")]
    if not history or history[-1]["role"] != "user":
        raise HTTPException(400, "Last message must be from the user")
    msgs = []  # LLM context window: last 12 messages, consecutive same-role turns merged
    for m in history[-12:]:  # (a question left unanswered by a refresh would otherwise break role alternation)
        if msgs and msgs[-1]["role"] == m["role"]:
            msgs[-1]["content"] += "\n\n" + m["content"]
        else:
            msgs.append({"role": m["role"], "content": m["content"]})
    if msgs[0]["role"] != "user":
        msgs = msgs[1:]
    system = prompts.DATA_EXTRACTOR_SYS + "\n\nLOCAL LIBRARY:\n" + reference_digest(included()[:30], 200)
    r = await call_agent("data_extractor", system, messages=msgs, max_tokens=6000, temperature=0.1)
    tables = re.findall(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", r["text"], flags=re.S)
    reply = {"content": r["text"], "tables": tables, "engine": r["engine"], "note": r["note"]}
    # Session persistence: save the completed Q&A turn to data/workspace/chat_sessions/<id>.json
    sid = body.get("session_id") or get_active("data") or create_session(tool="data")["id"]
    saved = await run_in_threadpool(record_turn, sid, history, reply)
    return {"reply": r["text"], "tables": tables, "engine": r["engine"], "note": r["note"],
            "session": {"id": sid, "title": saved["title"], "updated": saved["updated"], "count": len(saved["messages"])}}


@app.exception_handler(SessionNotFound)
async def session_not_found(_, exc):
    return JSONResponse(status_code=404, content={"detail": f"Chat session not found: {exc}"})


@app.get("/api/chat/sessions")
def chat_sessions(tool: str = "data"):
    """Saved conversations of one tool (newest first) and its active one."""
    if tool not in TOOLS:
        raise HTTPException(400, f"Unknown tool {tool}")
    return {"tool": tool, "active": get_active(tool), "sessions": list_sessions(tool),
            "restore": load_config().get("chat_restore", True)}


@app.post("/api/chat/sessions")
def chat_session_create(body: dict = Body(default={})):
    """New session. For Tools 1/2/4 the current tool output is snapshotted as the session context."""
    tool = body.get("tool", "data")
    if tool not in TOOLS:
        raise HTTPException(400, f"Unknown tool {tool}")
    context = tool_output(tool)["content"] if tool in ("lit2plan", "experiment", "masterclass") else ""
    return create_session(body.get("title"), body.get("messages"), tool=tool, context=context)


# ================================================================ follow-up chats for Tools 1-4
def _recent_sessions(exclude: str) -> dict:
    out = {}
    for t in TOOLS:
        sid = get_active(t)
        if t != exclude and sid:
            try:
                out[t] = load_session(sid, activate=False)["messages"]
            except SessionNotFound:
                pass
    return out


@app.post("/api/tool-chat")
async def tool_chat(body: dict = Body(...)):
    """Follow-up chat about a tool's output, optionally sharing context with the other tools."""
    tool = body.get("tool")
    if tool not in prompts.TOOL_CHAT_SYS:
        raise HTTPException(400, f"Unknown tool {tool}")
    history = [m for m in body.get("messages", []) if m.get("role") in ("user", "assistant") and m.get("content")]
    if not history or history[-1]["role"] != "user":
        raise HTTPException(400, "Last message must be from the user")
    sid = body.get("session_id")
    if not sid:
        sid = create_session(tool=tool, context=tool_output(tool)["content"] if tool != "paper" else "")["id"]
    sess = load_session(sid, activate=False)
    own = sess.get("context") or tool_output(tool)["content"]  # snapshot first, else latest output
    own = own[:40000] + ("\n…[truncated]" if len(own) > 40000 else "")
    shared = build_shared_context(tool, _recent_sessions(tool)) if body.get("share", True) else ""
    system = prompts.tool_chat_system(tool, own, shared, reference_digest(included()[:30], 250))
    msgs = []
    for m in history[-16:]:
        if msgs and msgs[-1]["role"] == m["role"]:
            msgs[-1]["content"] += "\n\n" + m["content"]
        else:
            msgs.append({"role": m["role"], "content": m["content"]})
    if msgs[0]["role"] != "user":
        msgs = msgs[1:]
    r = await call_agent(f"chat_{tool}", system, messages=msgs, max_tokens=6000, temperature=0.4)
    reply = {"content": r["text"], "tables": [], "engine": r["engine"], "note": r["note"]}
    saved = await run_in_threadpool(record_turn, sid, history, reply)
    return {"reply": r["text"], "tables": [], "engine": r["engine"], "note": r["note"], "shared": bool(shared),
            "session": {"id": sid, "title": saved["title"], "updated": saved["updated"], "count": len(saved["messages"])}}


@app.get("/api/tool/output/{tool}")
def get_tool_output(tool: str):
    """Last saved output of a tool, so the UI can restore it after a refresh."""
    return tool_output(tool)


@app.get("/api/context/notes")
def get_notes():
    return {"notes": load_notes()}


@app.post("/api/context/notes")
def post_note(body: dict = Body(...)):
    if not str(body.get("text", "")).strip():
        raise HTTPException(400, "Empty note")
    return add_note(body.get("tool", "data"), body["text"], body.get("source", ""))


@app.delete("/api/context/notes/{note_id}")
def remove_note(note_id: str):
    delete_note(note_id)
    return {"deleted": note_id}


@app.get("/api/chat/sessions/{sid}")
def chat_session_get(sid: str):
    """Open a conversation (also marks it as the active one)."""
    return load_session(sid)


@app.put("/api/chat/sessions/{sid}")
def chat_session_put(sid: str, body: dict = Body(...)):
    """Background save of messages and/or rename."""
    d = save_session(sid, body.get("messages"), body.get("title"))
    return {"id": sid, "title": d["title"], "updated": d["updated"], "count": len(d["messages"])}


@app.delete("/api/chat/sessions/{sid}")
def chat_session_delete(sid: str):
    """Move a conversation to chat_sessions/_trash/ (recoverable)."""
    return {"deleted": sid, "active": delete_session(sid)}


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
    write_ws("masterclass_guide.md", r["text"])
    write_ws("masterclass_meta.json", json.dumps({"topic": topic, "context": body.get("context", "")}, ensure_ascii=False))
    return {"guide": r["text"], "engine": r["engine"], "note": r["note"]}
