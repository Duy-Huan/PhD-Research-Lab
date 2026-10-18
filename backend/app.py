"""FastAPI server for the PhD Interactive Autonomous Research Lab.

Run:  python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import httpx
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse

from . import prompts
from . import brief as BR
from .config import (APP_VERSION, ROOT, activate_project, create_project, data_dir, forget_project, list_projects,
                     load_config, open_project, public_config, refs_dir, rename_project, save_config)
from .library import (PDF_BACKEND, build_bibtex, first_pages_text, included, load_library,
                      merge_llm_metadata, reference_digest, save_library, scan_directory)
from .attachments import (AttachmentError, add_library_paper, add_link, add_upload, clean_refs, get_meta,
                          get_text, raw_path, render_for_llm)
from .fs_browse import list_dir, make_dir, pick_folder_native
from .context_hub import add_note, build_shared_context, delete_note, load_notes, tool_output
from .chat_store import (TOOLS, SessionNotFound, create_session, delete_session, get_active, list_sessions,
                         load_session, record_turn, save_session)
from .llm import (LLMError, call_agent, stream_agent, cloud_chat, extract_json, list_local_models, list_provider_models,
                  provider_settings, strip_fences)
from . import review_ext as RX
from . import websearch as WS
from . import review_prompts as RP
from .paper import (SECTION_TITLES, SECTIONS, assemble, build_zip, clean_section,
                    fix_citations, load_project, read_ws, save_project, write_ws)

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    """v3: background Summarization Agent (hierarchical memory) runs while the app is up."""
    from .memory import worker
    stop = asyncio.Event()
    task = asyncio.create_task(worker(stop))
    try:
        yield
    finally:
        stop.set()
        task.cancel()


app = FastAPI(title="PhD Interactive Autonomous Research Lab", version=APP_VERSION, lifespan=lifespan)
FRONTEND = ROOT / "frontend" / "index.html"


@app.exception_handler(RX.ReviewError)
async def review_error_handler(_, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(LLMError)
async def llm_error_handler(_, exc: LLMError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}


@app.get("/")
def index():
    """The page links its scripts with ?v=<version> so a browser never mixes files from two versions."""
    html = FRONTEND.read_text("utf-8")
    html = re.sub(r'((?:src|href)="/(?:app/[\w.-]+|i18n\.js))"', lambda m: f'{m.group(1)}?v={APP_VERSION}"', html)
    return Response(html, media_type="text/html; charset=utf-8", headers=NO_CACHE)


class _NoStaleUI:
    """Pure ASGI (does not buffer SSE streams): UI files are always revalidated, so an upgrade shows up immediately."""
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(("/app/", "/guide/", "/i18n.js")):
            return await self.inner(scope, receive, send)

        async def snd(msg):
            if msg["type"] == "http.response.start":
                hs = [(k, v) for k, v in msg.get("headers", []) if k.lower() != b"cache-control"]
                msg = {**msg, "headers": hs + [(b"cache-control", b"no-cache, must-revalidate")]}
            await send(msg)
        return await self.inner(scope, receive, snd)


app.add_middleware(_NoStaleUI)


@app.get("/api/version")
def api_version():
    return {"version": APP_VERSION, "root": str(ROOT)}


app.mount("/vendor", StaticFiles(directory=str(ROOT / "frontend" / "vendor")), name="vendor")  # offline UI libraries
@app.get("/i18n.js")
def i18n_js():
    return FileResponse(ROOT / "frontend" / "i18n.js", media_type="application/javascript")


app.mount("/guide", StaticFiles(directory=str(ROOT / "frontend" / "guide")), name="guide")  # user guide (EN/VI)
app.mount("/app", StaticFiles(directory=str(ROOT / "frontend" / "app")), name="app")  # v3 IDE / Docker / Context modules
from .api_v3 import router as _v3_router  # noqa: E402
app.include_router(_v3_router)
from .api_v31 import router as _v31_router  # noqa: E402
app.include_router(_v31_router)


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


@app.post("/api/fs/pick-folder")
async def fs_pick_folder(body: dict = Body(default={})):
    """Native 'Select folder' dialog of the OS; {native: False} means: use the in-app browser instead."""
    return await run_in_threadpool(pick_folder_native, body.get("initial", ""), body.get("title", "Select folder"))


@app.get("/api/fs/list")
def fs_list(path: str = ""):
    """Sub-folders of a folder (in-app folder browser)."""
    return list_dir(path)


@app.post("/api/fs/mkdir")
def fs_mkdir(body: dict = Body(...)):
    try:
        return make_dir(body.get("parent", ""), body.get("name", ""))
    except (ValueError, OSError) as e:
        raise HTTPException(400, str(e))


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
    web = body.get("web") if body.get("web") in WS.MODES else "off"
    online, res = "", {"sources": [], "errors": [], "queries": {}}
    if web != "off":
        q = await WS.plan_queries(call_agent, f"USER: Research idea: {idea}\nDomain / constraints: {body.get('domain', '')}\n"
                                              f"Find the most relevant and recent literature (seminal + state of the art).\n\nQuery expansion:\n{exp['text'][:3000]}")
        res = await WS.search(web, q["papers"], q["web"], n=12, year_from=q.get("year_from"))
        online = WS.sources_block(res["sources"])
    system = prompts.LIT2PLAN_SYS + prompts.output_language(body.get("lang")) + (prompts.LIT2PLAN_ONLINE if online else "")
    must = _v3_context("lit2plan", "")
    if must:
        system += must + "\n(Build the plan around the locked decisions above.)"
    plan = await call_agent("lit2plan", system, prompts.lit2plan_user(idea, body.get("domain", ""), exp["text"], digest, online),
                            max_tokens=10000)
    from .api_v3 import snapshot_plan
    snapshot_plan("before new generation")
    write_ws("lit2plan.md", plan["text"])
    snapshot_plan("generated")
    sources = WS.compact(res["sources"])
    write_ws("lit2plan_sources.json", json.dumps({"sources": sources, "queries": res["queries"]}, ensure_ascii=False))
    return {"expansion": exp["text"], "plan": plan["text"], "sources": sources, "search_errors": res["errors"],
            "queries": res["queries"], "engines": {"query_expansion": exp["engine"], "lit2plan": plan["engine"]},
            "notes": [n for n in (exp["note"], plan["note"]) if n]}


@app.post("/api/search")
async def internet_search(body: dict = Body(...)):
    """Direct search (Find papers panel): {query, mode: papers|web|both, year_from?}."""
    query = str(body.get("query", "")).strip()
    if not query:
        raise HTTPException(400, "Query required")
    mode = body.get("mode") if body.get("mode") in ("papers", "web", "both") else "papers"
    yf = body.get("year_from")
    res = await WS.search(mode, [query], [query], year_from=int(yf) if str(yf or "").isdigit() else None)
    return {"sources": WS.compact(res["sources"]), "errors": res["errors"]}


@app.post("/api/references/fetch")
async def fetch_reference(body: dict = Body(...)):
    """Download an open-access PDF found online into this project's references folder (with its metadata)."""
    url = str(body.get("pdf_url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "No open-access PDF link for this paper — open the page and download it manually")
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers={"User-Agent": WS.UA, "Accept": "application/pdf,*/*"}) as c:
            r = await c.get(url)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Could not download the PDF: {e}")
    data = r.content
    if r.status_code >= 400 or not data.startswith(b"%PDF"):
        raise HTTPException(502, "The link did not return a PDF (publisher page or paywall) — open it and download manually")
    rdir = refs_dir()
    name = WS.safe_pdf_name(body.get("title", ""), body.get("year"))
    base, k = name[:-4], 1
    while (rdir / name).exists():
        k += 1
        name = f"{base}_{k}.pdf"
    (rdir / name).write_bytes(data)
    res = await run_in_threadpool(scan_directory)
    lib = load_library()
    if name in lib:  # metadata from the scholarly database is more reliable than PDF heuristics
        authors = body.get("authors") or []
        merge_llm_metadata(lib[name], {"title": body.get("title"), "authors": authors, "year": body.get("year"),
                                       "venue": body.get("venue"), "doi": body.get("doi"),
                                       "abstract": body.get("snippet") or lib[name].get("abstract"),
                                       "entry_type": "misc" if "arxiv" in (body.get("venue") or "").lower() else lib[name].get("entry_type", "article")})
        lib[name]["source_url"] = body.get("url") or url
        save_library(lib)
    return {"file": name, "added": res["added"]}


@app.post("/api/tool/experiment")
async def experiment(body: dict = Body(...)):
    if not body.get("novelty", "").strip():
        raise HTTPException(400, "Novelty proposal is required")
    ctx = _v3_context("experiment", "")
    if ctx and "RESEARCH RESULTS PROVIDED" in ctx:
        ctx += ("\n(The researcher already has the results above: design the methodology around them — reuse their datasets, "
                "metrics and baselines, and propose the experiments that are still missing, e.g. ablations, significance tests.)")
    r = await call_agent("experiment", prompts.EXPERIMENT_SYS + prompts.output_language(body.get("lang")) + ctx,
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


# ================================================================ chats (Data chat + follow-up chats of Tools 1-4)
@app.exception_handler(SessionNotFound)
async def session_not_found(_, exc):
    return JSONResponse(status_code=404, content={"detail": f"Chat session not found: {exc}"})


@app.exception_handler(AttachmentError)
async def attachment_error(_, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


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


ATTACHMENT_BUDGET = 150_000  # characters of attached documents per request (newest messages first)


def _llm_messages(history: list, window: int) -> list:
    """Last `window` messages -> LLM messages with attachment text/images; same-role turns merged."""
    hist = history[-window:]
    budget, rendered = ATTACHMENT_BUDGET, [None] * len(hist)
    n_images = 0
    for i in range(len(hist) - 1, -1, -1):  # newest first gets the attachment budget
        m = hist[i]
        content, images = m["content"], []
        if m["role"] == "user" and m.get("attachments"):
            block, images, used = render_for_llm(m["attachments"], budget)
            budget -= used
            images = images[: max(0, 8 - n_images)]
            n_images += len(images)
            if block:
                content = f"{block}\n\n{content}"
        rendered[i] = {"role": m["role"], "content": content, "images": images}
    msgs = []
    for m in rendered:
        if msgs and msgs[-1]["role"] == m["role"]:
            msgs[-1]["content"] += "\n\n" + m["content"]
            msgs[-1]["images"] += m["images"]
        else:
            msgs.append(m)
    if msgs and msgs[0]["role"] != "user":
        msgs = msgs[1:]
    return msgs


def _prepare_chat(body: dict) -> dict:
    tool = body.get("tool") or "data"
    if tool not in TOOLS:
        raise HTTPException(400, f"Unknown tool {tool}")
    history = [m for m in body.get("messages", []) if m.get("role") in ("user", "assistant") and m.get("content")]
    if not history or history[-1]["role"] != "user":
        raise HTTPException(400, "Last message must be from the user")
    for m in history:
        if m.get("attachments"):
            m["attachments"] = clean_refs(m["attachments"])
    sid = body.get("session_id")
    if not sid:
        sid = (get_active("data") if tool == "data" else None) or create_session(
            tool=tool, context=tool_output(tool)["content"] if tool in ("lit2plan", "experiment", "masterclass") else "")["id"]
    shared = ""
    if tool == "data":
        agent, temp = "data_extractor", 0.1
        system = prompts.DATA_EXTRACTOR_SYS + "\n\nLOCAL LIBRARY:\n" + reference_digest(included()[:30], 200)
        msgs = _llm_messages(history, 12)
    else:
        agent, temp = f"chat_{tool}", 0.4
        sess = load_session(sid, activate=False)
        own = sess.get("context") or tool_output(tool)["content"]  # snapshot first, else latest output
        own = own[:40000] + ("\n…[truncated]" if len(own) > 40000 else "")
        shared = build_shared_context(tool, _recent_sessions(tool)) if body.get("share", True) else ""
        system = prompts.tool_chat_system(tool, own, shared, reference_digest(included()[:30], 250))
        msgs = _llm_messages(history, max(8, 2 * int(load_config()["memory"]["keep_recent_turns"])))
    system += _v3_context(tool, sid)
    system += prompts.ATTACHMENT_RULES
    web = body.get("web") if body.get("web") in WS.MODES else "off"
    return {"tool": tool, "agent": agent, "temp": temp, "system": system, "msgs": msgs,
            "sid": sid, "history": history, "shared": bool(shared), "web": web, "sources": []}


def _v3_context(tool: str, sid: str) -> str:
    """Pinned graph nodes + locked decisions (always, must-follow) and hierarchical memory (Tier 3 + Tier 2)."""
    out = ""
    try:
        from .context_graph import pinned_block, purged_ids
        from .memory import memory_block
        pinned = pinned_block()
        if pinned:
            out += ("\n\n# MUST-FOLLOW CONTEXT (pinned / locked by the researcher — comply strictly; never contradict it; "
                    "point out explicitly if the researcher's new request conflicts with it)\n" + pinned)
        mem = memory_block(tool, sid, budget=7000, purged=purged_ids())
        if mem:
            out += "\n\n# PROJECT MEMORY (hierarchical: long-term facts + summaries of earlier work)\n" + mem
        from .results import digest as results_digest
        res = results_digest(4000, purged_ids())
        if res:
            out += ("\n\n# RESEARCH RESULTS PROVIDED BY THE RESEARCHER (work done outside the app; real results — "
                    "quote their numbers exactly, never extrapolate)\n" + res)
    except Exception:
        pass
    return out


def _conversation_text(history: list, n: int = 6) -> str:
    return "\n\n".join(f"{m['role'].upper()}: {m['content'][:2500]}" for m in history[-n:])


async def _web_search(ctx: dict, on_event=None) -> dict:
    """Plan queries for the latest question, search the internet, add the results to the system prompt."""
    plan = await WS.plan_queries(call_agent, _conversation_text(ctx["history"]))
    if on_event:
        await on_event({"type": "search", "status": "searching", "mode": ctx["web"],
                        "queries": {"papers": plan["papers"] if ctx["web"] in ("papers", "both") else [],
                                    "web": plan["web"] if ctx["web"] in ("web", "both") else []}})
    res = await WS.search(ctx["web"], plan["papers"], plan["web"], year_from=plan.get("year_from"))
    if res["sources"]:
        ctx["system"] += WS.WEB_RULES + WS.sources_block(res["sources"])
    else:
        ctx["system"] += ("\n\n# INTERNET SEARCH\nAn internet search was attempted but returned no usable results"
                          f"{' (' + '; '.join(res['errors']) + ')' if res['errors'] else ''}. Say so briefly and answer from the other context.")
    ctx["sources"] = WS.compact(res["sources"])
    return res


def _finish(ctx: dict, text: str, engine: str, note: str) -> tuple[dict, dict]:
    tables = re.findall(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", text, flags=re.S) if ctx["tool"] == "data" else []
    reply = {"content": text, "tables": tables, "engine": engine, "note": note, "sources": ctx.get("sources") or []}
    saved = record_turn(ctx["sid"], ctx["history"], reply)
    return reply, {"id": ctx["sid"], "title": saved["title"], "updated": saved["updated"], "count": len(saved["messages"])}


async def _chat_once(body: dict) -> dict:
    ctx = _prepare_chat(body)
    if ctx["web"] != "off":
        await _web_search(ctx)
    r = await call_agent(ctx["agent"], ctx["system"], messages=ctx["msgs"], max_tokens=6000, temperature=ctx["temp"])
    reply, session = await run_in_threadpool(_finish, ctx, r["text"], r["engine"], r["note"])
    return {"reply": reply["content"], "tables": reply["tables"], "engine": r["engine"], "note": r["note"],
            "shared": ctx["shared"], "session": session, "sources": reply["sources"]}


@app.post("/api/chat")
async def chat(body: dict = Body(...)):
    """Data chat (non-streaming)."""
    return await _chat_once({**body, "tool": "data"})


@app.post("/api/tool-chat")
async def tool_chat(body: dict = Body(...)):
    """Follow-up chat of Tools 1-4 (non-streaming)."""
    if body.get("tool") not in prompts.TOOL_CHAT_SYS:
        raise HTTPException(400, f"Unknown tool {body.get('tool')}")
    return await _chat_once(body)


@app.post("/api/chat/stream")
async def chat_stream(body: dict = Body(...)):
    """Streaming chat for every tool (Server-Sent Events): delta events, then a final done/error event.
    The turn is saved when the answer completes; if the user presses Stop the browser saves the partial answer."""
    ctx = _prepare_chat(body)

    def sse(obj: dict) -> str:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

    async def gen():
        meta = {}
        try:
            yield sse({"type": "start", "session_id": ctx["sid"], "shared": ctx["shared"], "web": ctx["web"]})
            if ctx["web"] != "off":
                yield sse({"type": "search", "status": "planning", "mode": ctx["web"]})
                q = []

                async def push(ev):
                    q.append(ev)
                task = asyncio.ensure_future(_web_search(ctx, push))
                try:
                    while not task.done():
                        await asyncio.sleep(0.15)
                        while q:
                            yield sse(q.pop(0))
                finally:
                    if not task.done():  # browser pressed Stop during the search
                        task.cancel()
                while q:
                    yield sse(q.pop(0))
                res = task.result()
                yield sse({"type": "sources", "sources": ctx["sources"], "errors": res["errors"]})
            async for kind, val in stream_agent(ctx["agent"], ctx["system"], ctx["msgs"], max_tokens=6000, temperature=ctx["temp"]):
                if kind == "delta":
                    yield sse({"type": "delta", "text": val})
                else:
                    meta = val
            reply, session = await run_in_threadpool(_finish, ctx, meta["text"], meta["engine"], meta["note"])
            yield sse({"type": "done", "reply": reply["content"], "tables": reply["tables"], "engine": meta["engine"],
                       "note": meta["note"], "shared": ctx["shared"], "session": session, "sources": reply["sources"]})
        except LLMError as e:
            yield sse({"type": "error", "detail": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ================================================================ attachments & library catalogue
@app.post("/api/attachments")
async def upload_attachments(files: list[UploadFile] = File(...)):
    """Upload files to attach to a chat message; returns metadata (and per-file errors)."""
    out, errors = [], []
    for f in files:
        try:
            out.append(await run_in_threadpool(add_upload, f.filename or "file", await f.read()))
        except AttachmentError as e:
            errors.append(str(e))
    return {"attachments": out, "errors": errors}


@app.post("/api/attachments/link")
async def attach_link(body: dict = Body(...)):
    """Fetch a web page / online PDF and attach its text."""
    return await add_link(body.get("url", ""))


@app.post("/api/attachments/paper")
def attach_paper(body: dict = Body(...)):
    """Attach the full text of a paper from the project's references folder."""
    return add_library_paper(body.get("file", ""))


@app.get("/api/attachments/{att_id}/raw")
def attachment_raw(att_id: str):
    p = raw_path(att_id)
    return FileResponse(p, filename=get_meta(att_id)["name"], content_disposition_type="inline")


@app.get("/api/attachments/{att_id}/text", response_class=PlainTextResponse)
def attachment_text(att_id: str):
    return get_text(att_id)


@app.get("/api/library/catalog")
def library_catalog():
    """Included references (for citation chips and the paper picker)."""
    return {"papers": [{k: e.get(k) for k in ("key", "title", "authors", "year", "venue", "doi", "file")} for e in included()]}


@app.get("/api/references/file/{name}")
def reference_file(name: str, download: int = 0):
    """Serve a library PDF: inline for the in-app reader / new tab, or as a download (?download=1)."""
    f = refs_dir() / Path(name).name
    if not f.exists():
        raise HTTPException(404, "PDF not found in this project's references folder")
    return FileResponse(f, media_type="application/pdf", filename=f.name,
                        content_disposition_type="attachment" if download else "inline")


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
    for k in ("title", "authors", "style", "keywords", "contribution", "method_notes", "results_notes", "venue"):
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
                         prompts.author_user(sid, SECTION_TITLES[sid], p, reference_digest(entries), keys,
                                             BR.render(p, sid, "author", keys)),
                         max_tokens=8000, temperature=0.4)
    tex = clean_section(sid, strip_fences(r["text"]))
    tex, unknown = fix_citations(tex, set(keys))
    p = load_project()
    p["sections"][sid] = tex
    p["section_state"][sid] = "drafted"
    save_project(p)
    return {"section": sid, "latex": tex, "unknown_citations": unknown, "engine": r["engine"], "note": r["note"]}


@app.put("/api/paper/section")
def save_section(body: dict = Body(...)):
    """Save a section's LaTeX and/or its AI instructions and/or its workflow state (accepted, ...)."""
    sid = body.get("section")
    if sid not in SECTION_TITLES:
        raise HTTPException(400, "Unknown section")
    p = load_project()
    if "latex" in body:
        changed = (p["sections"].get(sid) or "") != (body.get("latex") or "")
        p["sections"][sid] = body.get("latex") or ""
        if changed:
            p["section_state"][sid] = "edited" if body["latex"] else ""
    if "notes" in body:
        p["section_notes"][sid] = str(body.get("notes") or "")
    if body.get("state") in ("accepted", "edited", "drafted", "reviewed", "revised", ""):
        p["section_state"][sid] = body["state"]
    save_project(p)
    return {"ok": True, "state": p["section_state"].get(sid, "")}


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
                         prompts.editor_user(sid, current, p["review"], keys, reference_digest(entries, 300),
                                             BR.render(p, sid, "editor", keys)),
                         max_tokens=8000, temperature=0.2)
    tex = clean_section(sid, strip_fences(r["text"]))
    tex, unknown = fix_citations(tex, set(keys))
    if len(tex) < 0.3 * len(current):  # guard against truncated / degenerate rewrites
        return {"section": sid, "latex": current, "rejected": True,
                "note": "Revision discarded: output was much shorter than the original section."}
    p = load_project()
    p["sections"][sid] = tex
    p["section_state"][sid] = "revised"
    save_project(p)
    return {"section": sid, "latex": tex, "unknown_citations": unknown, "engine": r["engine"], "note": r["note"]}


# ---------------------------------------------------------------- v2.5: streaming section workshop
SCORE_RE = re.compile(r"SCORE:\s*(\d{1,2})\s*/\s*10", re.I)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def sse_job(agent: str, system: str, user: str, finalize, max_tokens: int = 8000, temperature: float = 0.3,
            start: dict | None = None) -> StreamingResponse:
    """Stream one agent run as Server-Sent Events: start → delta… → done (finalize(meta) result) | error.
    If the browser aborts (■ Stop), Starlette cancels this generator and the upstream AI request, and nothing is saved."""
    async def gen():
        try:
            yield _sse({"type": "start", **(start or {})})
            meta = {}
            async for kind, val in stream_agent(agent, system, [{"role": "user", "content": user}],
                                                max_tokens=max_tokens, temperature=temperature):
                if kind == "delta":
                    yield _sse({"type": "delta", "text": val})
                else:
                    meta = val
            if not meta.get("text", "").strip():
                raise LLMError("The model returned an empty answer.")
            out = await run_in_threadpool(finalize, meta)
            yield _sse({"type": "done", "engine": meta["engine"], "note": meta["note"], **out})
        except LLMError as e:
            yield _sse({"type": "error", "detail": str(e)})
        except HTTPException as e:
            yield _sse({"type": "error", "detail": str(e.detail)})
        except Exception as e:  # never leave the browser hanging
            yield _sse({"type": "error", "detail": f"{type(e).__name__}: {e}"})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/paper/stream")
def paper_stream(body: dict = Body(...)):
    """Streaming paper agents. action: draft | review_section | revise | review (whole paper).
    Options: section, deep (bool), instructions (str, saved as the section's notes)."""
    action, sid = body.get("action"), body.get("section")
    deep = bool(body.get("deep"))
    if action != "review" and sid not in SECTION_TITLES:
        raise HTTPException(400, f"Unknown section {sid}")
    p = load_project()
    if "instructions" in body and sid in SECTION_TITLES:
        p["section_notes"][sid] = str(body.get("instructions") or "")
        save_project(p)
    entries = included()
    keys = [e["key"] for e in entries]
    notes = BR.render(p, sid, "author", keys) if sid else ""   # v3.1 brief (directions + structure + selected results)

    if action == "draft":
        user = prompts.author_user(sid, SECTION_TITLES[sid], p, reference_digest(entries), keys, notes, deep)

        def fin(meta):
            tex = clean_section(sid, strip_fences(meta["text"]))
            tex, unknown = fix_citations(tex, set(keys))
            q = load_project()
            q["sections"][sid] = tex
            q["section_state"][sid] = "drafted"
            q["section_reviews"].pop(sid, None)  # an old review no longer matches the new text
            q["section_scores"].pop(sid, None)
            save_project(q)
            return {"section": sid, "latex": tex, "unknown_citations": unknown}
        return sse_job("author", prompts.AUTHOR_SYS, user, fin, max_tokens=12000 if deep else 8000, temperature=0.4,
                       start={"action": action, "section": sid})

    if action == "review_section":
        cur = (p.get("sections") or {}).get(sid)
        if not cur:
            raise HTTPException(400, "Draft this section first")
        user = prompts.section_reviewer_user(sid, SECTION_TITLES[sid], cur, p, reference_digest(entries, 300), keys,
                                             BR.render(p, sid, "reviewer", keys))

        def fin(meta):
            m = SCORE_RE.search(meta["text"])
            score = max(1, min(10, int(m.group(1)))) if m else None
            q = load_project()
            q["section_reviews"][sid] = meta["text"]
            if score:
                q["section_scores"][sid] = score
            q["section_state"][sid] = "reviewed"
            save_project(q)
            return {"section": sid, "review": meta["text"], "score": score}
        return sse_job("reviewer", prompts.SECTION_REVIEWER_SYS, user, fin, max_tokens=6000, temperature=0.2,
                       start={"action": action, "section": sid})

    if action == "revise":
        cur = (p.get("sections") or {}).get(sid)
        if not cur:
            raise HTTPException(400, "Draft this section first")
        review = (p.get("section_reviews") or {}).get(sid) or p.get("review")
        if not review:
            raise HTTPException(400, "Review this section (🔍) or the whole paper (3.3) first")
        source = "section" if (p.get("section_reviews") or {}).get(sid) else "paper"
        user = prompts.editor_user(sid, cur, review, keys, reference_digest(entries, 300), BR.render(p, sid, "editor", keys))

        def fin(meta):
            tex = clean_section(sid, strip_fences(meta["text"]))
            tex, unknown = fix_citations(tex, set(keys))
            if len(tex) < 0.3 * len(cur):
                return {"section": sid, "latex": cur, "rejected": True,
                        "message": "Revision discarded: output was much shorter than the original section."}
            q = load_project()
            q["sections"][sid] = tex
            q["section_state"][sid] = "revised"
            save_project(q)
            return {"section": sid, "latex": tex, "unknown_citations": unknown, "review_source": source}
        return sse_job("editor", prompts.EDITOR_SYS, user, fin, max_tokens=12000 if deep else 8000, temperature=0.2,
                       start={"action": action, "section": sid, "review_source": source})

    if action == "review":
        main, _, report = assemble()

        def fin(meta):
            q = load_project()
            q["review"] = meta["text"]
            save_project(q)
            write_ws("review.md", meta["text"])
            return {"review": meta["text"], "report": report}
        return sse_job("reviewer", prompts.REVIEWER_SYS,
                       prompts.reviewer_user(main, reference_digest(entries, 400), report), fin, max_tokens=8000,
                       temperature=0.2, start={"action": action})

    raise HTTPException(400, f"Unknown action {action}")


# ---------------------------------------------------------------- v2.7: LaTeX → PDF preview
from . import latex_build as LB


@app.get("/api/latex/engines")
def latex_engines():
    return {**LB.engines(), "install_help": LB.install_help()}


@app.post("/api/latex/compile")
async def latex_compile(body: dict = Body(default={})):
    """Assemble main.tex and compile it to PDF with the local TeX engine (or online, if enabled)."""
    try:
        return await run_in_threadpool(LB.compile_pdf, body.get("engine", ""), body.get("layout", "template"))
    except LB.NoEngine as e:
        raise HTTPException(424, {"message": str(e), "install_help": LB.install_help()})
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@app.get("/api/latex/pdf")
def latex_pdf(download: int = 0):
    f = LB.build_dir() / "main.pdf"
    if not f.exists():
        raise HTTPException(404, "No PDF yet — press ▶ Compile PDF")
    return FileResponse(f, media_type="application/pdf", filename="main.pdf",
                        content_disposition_type="attachment" if download else "inline",
                        headers={"Cache-Control": "no-store"})


@app.get("/api/latex/log", response_class=PlainTextResponse)
def latex_log():
    f = LB.build_dir() / "build.log"
    return f.read_text("utf-8", "replace") if f.exists() else "(no build log yet)"


@app.get("/api/export/latex.zip")
async def export_zip():
    data = await run_in_threadpool(build_zip)
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="latex.zip"'})


# ================================================================ v2.5: external Paper Review flow
@app.get("/api/review")
def review_list():
    return {"reviews": RX.list_reviews(), "active": RX.get_active()}


@app.post("/api/review/upload")
async def review_upload(file: UploadFile = File(...)):
    """Start a new review from a manuscript file (PDF / DOCX / TEX / MD / TXT)."""
    meta = await run_in_threadpool(RX.create_review, file.filename or "paper.pdf", await file.read())
    return {"meta": meta, "state": RX.load_state(meta["id"])}


@app.get("/api/review/{rid}")
def review_get(rid: str):
    return RX.get_review(rid)


@app.delete("/api/review/{rid}")
def review_delete(rid: str):
    RX.delete_review(rid)
    return {"deleted": rid}


@app.put("/api/review/{rid}/settings")
def review_settings(rid: str, body: dict = Body(...)):
    """Venue standard (conference ICORE / h5, journal Q1-Q4), number of reviewers, blind mode."""
    return {"meta": RX.set_settings(rid, body)}


@app.post("/api/review/{rid}/source")
async def review_source(rid: str, file: UploadFile = File(...)):
    """Attach the LaTeX source so accepted fixes can be applied automatically."""
    return {"meta": await run_in_threadpool(RX.add_source, rid, file.filename or "", await file.read())}


@app.get("/api/review/{rid}/text", response_class=PlainTextResponse)
def review_text(rid: str):
    return RX.paper_text(rid)


@app.get("/api/review/{rid}/original")
def review_original(rid: str):
    m = RX.load_meta(rid)
    f = RX._dir(rid) / f"original{m.get('ext', '')}"
    return FileResponse(f, filename=m.get("file"), content_disposition_type="inline")


def _rv_paper(rid: str) -> str:
    t = RX.paper_text(rid)
    return t[:RX.PAPER_BUDGET] + ("\n…[manuscript truncated]" if len(t) > RX.PAPER_BUDGET else "")


@app.post("/api/review/{rid}/stage")
def review_stage(rid: str, body: dict = Body(...)):
    """Streaming review stages: reviewer (idx 1-3) → meta (area chair / editor) → issues (structured list) → response letter."""
    stage = body.get("stage")
    meta = RX.load_meta(rid)
    v = meta.get("venue") or {}
    label = RP.venue_label(v)
    ps = RX.prescreen_text(meta.get("prescreen") or {}, meta.get("truncated", False))
    st = RX.load_state(rid)

    if stage == "reviewer":
        n = meta.get("n_reviewers", 3)
        idx = int(body.get("idx", 1))
        personas = RP.PERSONAS.get(n, RP.PERSONAS[3])
        if not 1 <= idx <= len(personas):
            raise HTTPException(400, "Reviewer index out of range")
        persona = personas[idx - 1]

        def fin(m):
            rec = {"id": persona[0], "persona": persona[1], "text": m["text"], "engine": m["engine"],
                   "ts": RX._now(), "venue": label, **RX.parse_review_header(m["text"])}

            def put(s):
                if body.get("fresh"):  # a full new round: drop the reports of the previous round
                    s["reviewers"] = {}
                for k in [k for k in s["reviewers"] if k not in {x[0] for x in personas}]:
                    s["reviewers"].pop(k)  # reviewer count was lowered
                s["reviewers"][persona[0]] = rec
            RX.update_state(rid, put)
            return {"reviewer": rec}
        return sse_job("ext_reviewer", RP.reviewer_system(v, persona), RP.reviewer_user(_rv_paper(rid), ps, meta.get("title", "")),
                       fin, max_tokens=7000, temperature=0.3, start={"stage": stage, "id": persona[0], "persona": persona[1]})

    if stage == "meta":
        if not st["reviewers"]:
            raise HTTPException(400, "Run the reviewers first")
        user = (f"AUTOMATIC DESK CHECK:\n{ps}\n\nREVIEWER REPORTS:\n{RX.reviews_digest(st)}\n\n"
                f"MANUSCRIPT TEXT:\n{_rv_paper(rid)}")

        def fin(m):
            rec = {"text": m["text"], "engine": m["engine"], "ts": RX._now(), "venue": label, **RX.parse_meta_header(m["text"])}
            RX.update_state(rid, lambda s: s.__setitem__("meta", rec))
            return {"meta": rec}
        return sse_job("ext_meta", RP.meta_system(v), user, fin, max_tokens=7000, temperature=0.2, start={"stage": stage})

    if stage == "issues":
        if not st["reviewers"]:
            raise HTTPException(400, "Run the reviewers first")
        text = RX.paper_text(rid)

        def fin(m):
            try:
                data = extract_json(m["text"])
            except Exception as e:
                raise LLMError(f"Could not parse the issue list returned by the model ({e}). Press Retry.")
            issues = RX.normalise_issues(data.get("issues") if isinstance(data, dict) else data, text)

            def put(s):
                s["issues"] = issues
                s["fixes"] = {}  # fixes belong to the previous issue list
            RX.update_state(rid, put)
            return {"issues": issues}
        return sse_job("ext_meta", RP.ISSUES_SYS,
                       RP.issues_user(_rv_paper(rid), RX.reviews_digest(st), (st.get("meta") or {}).get("text", "(none)"), RP.venue_brief(v)),
                       fin, max_tokens=12000, temperature=0.1, start={"stage": stage})

    if stage == "response":
        if not st["reviewers"]:
            raise HTTPException(400, "Run the reviewers first")

        def fin(m):
            rec = {"text": m["text"], "engine": m["engine"], "ts": RX._now()}
            RX.update_state(rid, lambda s: s.__setitem__("response", rec))
            return {"response": rec}
        return sse_job("ext_meta", RP.RESPONSE_SYS,
                       RP.response_user(RP.venue_brief(v), (st.get("meta") or {}).get("text", ""), RX.reviews_digest(st, 15000), RX.issues_digest(st)),
                       fin, max_tokens=8000, temperature=0.3, start={"stage": stage})

    raise HTTPException(400, f"Unknown stage {stage}")


@app.post("/api/review/{rid}/fix")
def review_fix(rid: str, body: dict = Body(...)):
    """Streaming quick fix for one issue: ORIGINAL → REVISED passage (+ note / plan)."""
    st = RX.load_state(rid)
    issue = next((i for i in st["issues"] if i["id"] == body.get("issue_id")), None)
    if not issue:
        raise HTTPException(404, "Issue not found — extract the issue list first")
    meta = RX.load_meta(rid)
    excerpt, fmt = RX.excerpt_for(rid, issue)

    def fin(m):
        fx = {**RX.parse_fix(m["text"]), "engine": m["engine"], "ts": RX._now(), "format": fmt, "status": "proposed"}
        fx["original_found"] = bool(fx["original"]) and RX.quote_found(excerpt, fx["original"])
        RX.update_state(rid, lambda s: s["fixes"].__setitem__(issue["id"], fx))
        return {"issue_id": issue["id"], "fix": fx}
    return sse_job("ext_fixer", RP.FIX_SYS, RP.fix_user(RP.venue_brief(meta.get("venue") or {}), issue, excerpt, fmt,
                                                        body.get("instructions", "")),
                   fin, max_tokens=5000, temperature=0.2, start={"issue_id": issue["id"]})


@app.put("/api/review/{rid}/issue/{iid}")
def review_issue(rid: str, iid: str, body: dict = Body(...)):
    """Update an issue status (open | done | wontfix) and/or its fix status (proposed | accepted | dismissed)."""
    def upd(s):
        for it in s["issues"]:
            if it["id"] == iid and body.get("status") in ("open", "done", "wontfix"):
                it["status"] = body["status"]
        fx = s["fixes"].get(iid)
        if fx and body.get("fix_status") in ("proposed", "accepted", "dismissed"):
            fx["status"] = body["fix_status"]
        if fx and isinstance(body.get("revised"), str):
            fx["revised"] = body["revised"]
    st = RX.update_state(rid, upd)
    return {"issue": next((i for i in st["issues"] if i["id"] == iid), None), "fix": st["fixes"].get(iid)}


@app.post("/api/review/{rid}/apply")
def review_apply(rid: str, body: dict = Body(default={})):
    """Apply accepted fixes to the LaTeX source → source_revised.tex (the original is never modified)."""
    return RX.apply_fixes(rid, body.get("ids"))


@app.get("/api/review/{rid}/download/{kind}")
def review_download(rid: str, kind: str):
    m = RX.load_meta(rid)
    stem = re.sub(r"[^\w\-]+", "_", Path(m.get("file", "paper")).stem)[:40]
    if kind == "report":
        return Response(RX.report_md(rid), media_type="text/markdown",
                        headers={"Content-Disposition": f'attachment; filename="review_report_{stem}.md"'})
    if kind == "fixes":
        return Response(RX.fixes_md(rid), media_type="text/markdown",
                        headers={"Content-Disposition": f'attachment; filename="proposed_fixes_{stem}.md"'})
    if kind == "response":
        st = RX.load_state(rid)
        if not st.get("response"):
            raise HTTPException(404, "Generate the response letter first")
        return Response(st["response"]["text"], media_type="text/markdown",
                        headers={"Content-Disposition": f'attachment; filename="response_to_reviewers_{stem}.md"'})
    if kind == "source":
        f = RX._dir(rid) / "source_revised.tex"
        if not f.exists():
            raise HTTPException(404, "No revised source yet — accept fixes and press Apply")
        return FileResponse(f, filename=f"{stem}_revised.tex", media_type="application/x-tex")
    raise HTTPException(404, "Unknown download")


# ================================================================ Tool 4
@app.post("/api/masterclass")
async def masterclass(body: dict = Body(...)):
    topic = body.get("topic", "").strip()
    if not topic:
        raise HTTPException(400, "Topic required")
    user = f"MILESTONE: {topic}\n\nRESEARCHER CONTEXT:\n{body.get('context') or '(none provided)'}"
    r = await call_agent("masterclass", prompts.MASTERCLASS_SYS + prompts.output_language(body.get("lang")), user, max_tokens=8000, temperature=0.4)
    write_ws("masterclass_guide.md", r["text"])
    write_ws("masterclass_meta.json", json.dumps({"topic": topic, "context": body.get("context", "")}, ensure_ascii=False))
    return {"guide": r["text"], "engine": r["engine"], "note": r["note"]}
