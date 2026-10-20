"""v3.0 API: local AI servers, system scan, Docker sandbox, workspace files, co-coding agent, Git/GitHub,
hierarchical memory, context graph, Lit2Plan decisions & regeneration, results import, project export, MCP."""
from __future__ import annotations

import asyncio
import io
import json
import re
import time
import zipfile
from collections import deque
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from . import coder, context_graph as CG, gitops, ide_fs, local_ai, mcp_server, memory as M, prompts, sandbox, sysinfo
from .config import AGENTS, data_dir, load_config, save_config, workspace
from .llm import LLMError, agent_runtime, call_agent, stream_agent

router = APIRouter()


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _err(e: Exception, code: int = 400):
    raise HTTPException(code, str(e))


# ================================================================ local AI servers & live agent runtime
@router.get("/api/local/status")
async def local_status():
    cfg = load_config()
    lm, ol = await asyncio.gather(local_ai.lmstudio_status(cfg["lmstudio_base_url"]), local_ai.ollama_status(cfg["ollama_base_url"]))
    return {"lmstudio": lm, "ollama": ol, "selected": {"local": cfg.get("local_model", ""), "ollama": cfg.get("ollama_model", "")}}


@router.post("/api/local/load")
async def local_load(body: dict = Body(...)):
    cfg = load_config()
    eng, model = body.get("engine", "local"), (body.get("model") or "").strip()
    if not model:
        raise HTTPException(400, "Choose a model")
    try:
        if eng == "ollama":
            r = await local_ai.ollama_load(cfg["ollama_base_url"], model, body.get("keep_alive", "30m"))
            save_config({"ollama_model": model})
        else:
            r = await local_ai.lmstudio_load(cfg["lmstudio_base_url"], model, body.get("context_length"))
            save_config({"local_model": model})
    except local_ai.LocalAIError as e:
        _err(e, 502)
    return r


@router.post("/api/local/unload")
async def local_unload(body: dict = Body(...)):
    cfg = load_config()
    try:
        if body.get("engine") == "ollama":
            return await local_ai.ollama_unload(cfg["ollama_base_url"], body.get("model", ""))
        return await local_ai.lmstudio_unload(cfg["lmstudio_base_url"], body.get("model", ""))
    except local_ai.LocalAIError as e:
        _err(e, 502)


@router.post("/api/local/pull")
async def local_pull(body: dict = Body(...)):
    cfg = load_config()
    model = (body.get("model") or "").strip()

    async def gen():
        try:
            async for ev in local_ai.ollama_pull(cfg["ollama_base_url"], model):
                yield sse({"type": "progress", **ev})
            yield sse({"type": "done"})
        except Exception as e:
            yield sse({"type": "error", "detail": str(e)})
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/api/agents/runtime")
async def agents_runtime():
    cfg = load_config()
    out = await run_in_threadpool(lambda: {a: agent_runtime(cfg, a) for a in AGENTS})  # "auto" agents probe engines
    auto = {r["engine"] for r in out.values() if r["model"] == "(auto)" and r["engine"] in ("local", "ollama")}
    resolved = {}
    for eng in auto:  # show the model that will really be used (the loaded one)
        try:
            resolved[eng] = await asyncio.wait_for(local_ai.first_model(eng, cfg), 4)
        except Exception:
            resolved[eng] = None
    for r in out.values():
        if r["model"] == "(auto)" and resolved.get(r["engine"]):
            r["model"] = resolved[r["engine"]]
            r["auto"] = True
    return out


# ================================================================ system scan
@router.get("/api/system/scan")
async def system_scan(force: int = 0):
    return await run_in_threadpool(sysinfo.scan, bool(force))


_HIST: deque = deque(maxlen=600)
_HIST_T = {"t": 0.0}


def _sample():
    if time.time() - _HIST_T["t"] < 1.5 and _HIST:
        return _HIST[-1]
    lv = sysinfo.live()
    g = (lv["gpus"] or [{}])[0]
    s = {"t": time.time(), "ram_pct": lv["memory"].get("used_pct"), "ram_avail": lv["memory"].get("available_gb"),
         "gpu_util": g.get("util_pct"), "vram_used": g.get("vram_used_mb"), "vram_total": g.get("vram_total_mb"),
         "gpu_temp": g.get("temp_c"), "gpu_power": g.get("power_w"), "cpu_load": lv["cpu"].get("load_1m")}
    _HIST.append(s)
    _HIST_T["t"] = time.time()
    return s


@router.get("/api/system/live")
async def system_live():
    lv = await run_in_threadpool(sysinfo.live)
    await run_in_threadpool(_sample)
    return {**lv, "history": list(_HIST)[-300:]}


@router.post("/api/system/apply-recommendation")
async def apply_recommendation():
    s = await run_in_threadpool(sysinfo.scan, False)
    rec = s.get("recommendation", {})
    sb = rec.get("sandbox") or {}
    patch = {k: v for k, v in sb.items() if k in sandbox.DEFAULT_SETTINGS}
    if patch.get("mode") == "docker":
        patch["mode"] = "auto"
    settings = sandbox.save_settings(patch)
    save_config({"agent_modes": rec.get("agents") or {}})
    return {"settings": settings, "agents": rec.get("agents")}


# ================================================================ sandbox / docker
@router.get("/api/sandbox/status")
async def sandbox_status(full: int = 1):
    def collect():
        st = sandbox.load_settings()
        mode = sandbox.effective_mode(st)
        out = {"settings": st, "mode": mode, "image": sandbox.effective_image(st), "docker_installed": bool(sandbox.docker_exe()),
               "docker_running": sandbox.docker_running(5) if sandbox.docker_exe() else False,
               "container": None, "stats": None, "jobs": [j.info() for j in sorted(sandbox.JOBS.values(), key=lambda j: j.id, reverse=True)[:40]],
               "code_dir": str(sandbox.code_dir()), "runs_dir": str(sandbox.runs_dir())}
        if out["docker_running"]:
            out["container"] = sandbox.container_state()
            if out["container"].get("running"):
                out["stats"] = sandbox.container_stats()
            if full:
                out["images"] = sandbox.list_images()
                out["containers"] = sandbox.list_containers()
                out["image_present"] = sandbox.image_present(out["image"])
        return out
    return await run_in_threadpool(collect)


@router.put("/api/sandbox/settings")
def sandbox_settings(body: dict = Body(...)):
    try:
        return {"settings": sandbox.save_settings(body)}
    except sandbox.SandboxError as e:
        _err(e)


@router.post("/api/sandbox/container")
async def sandbox_container(body: dict = Body(...)):
    try:
        return await run_in_threadpool(sandbox.container_action, body.get("action", "start"))
    except sandbox.SandboxError as e:
        msg = str(e)
        if msg.startswith("NEED_IMAGE:"):
            raise HTTPException(409, {"need_image": msg.split(":", 1)[1], "message": f"Image {msg.split(':', 1)[1]} is not downloaded yet — pull it first."})
        _err(e)


@router.post("/api/sandbox/pull")
async def sandbox_pull(body: dict = Body(...)):
    image = (body.get("image") or sandbox.effective_image(sandbox.load_settings())).strip()
    try:
        return (await run_in_threadpool(sandbox.pull_image, image)).info()
    except sandbox.SandboxError as e:
        _err(e)


def vram_busy_http(e: "sandbox.VramBusyError") -> HTTPException:
    return HTTPException(409, {"vram_busy": e.models, "vram_used_mb": e.vram_used_mb, "message": str(e)})


def _start(cmd, kind="run", title="", cpu=False):
    try:
        return sandbox.start_job(cmd, kind, title, extra_env={"CUDA_VISIBLE_DEVICES": ""} if cpu else None)
    except sandbox.VramBusyError as e:
        raise vram_busy_http(e)
    except sandbox.SandboxError as e:
        msg = str(e)
        if msg.startswith("NEED_IMAGE:"):
            raise HTTPException(409, {"need_image": msg.split(":", 1)[1], "message": f"Image {msg.split(':', 1)[1]} is not downloaded yet — pull it first."})
        raise HTTPException(400, msg)


@router.post("/api/sandbox/run")
async def sandbox_run(body: dict = Body(...)):
    job = await run_in_threadpool(_start, body.get("cmd", ""), body.get("kind", "run"), body.get("title", ""), bool(body.get("cpu")))
    return job.info()


@router.post("/api/sandbox/test-gpu")
async def sandbox_test_gpu():
    job = await run_in_threadpool(_start, "nvidia-smi || echo 'nvidia-smi not available in this container (CPU only)'", "shell", "GPU test")
    return job.info()


@router.get("/api/sandbox/jobs")
def sandbox_jobs():
    return {"jobs": [j.info() for j in sorted(sandbox.JOBS.values(), key=lambda j: j.id, reverse=True)]}


@router.post("/api/sandbox/jobs/{job_id}/stop")
async def sandbox_stop(job_id: str):
    try:
        return await run_in_threadpool(sandbox.stop_job, job_id)
    except sandbox.SandboxError as e:
        _err(e)


@router.get("/api/sandbox/jobs/{job_id}/stream")
async def sandbox_stream(job_id: str, request: Request, since: int = 0):
    job = sandbox.JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found (finished jobs are listed under Runs)")

    async def gen():
        last = since
        yield sse({"type": "info", "job": job.info()})
        while True:
            if await request.is_disconnected():
                return
            new = job.since(last)
            if new:
                last = new[-1][0]
                yield sse({"type": "lines", "lines": [[s, t] for _, s, t in new[-1000:]], "seq": last})
            elif job.status not in ("running", "queued"):
                yield sse({"type": "end", "job": job.info()})
                return
            await asyncio.sleep(0.2)
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/api/sandbox/runs")
def sandbox_runs():
    return {"runs": sandbox.list_runs(200), "best": sandbox.best_metrics()}


@router.get("/api/sandbox/runs/{run_id}")
def sandbox_run_get(run_id: str):
    try:
        return sandbox.get_run(run_id)
    except sandbox.SandboxError as e:
        _err(e, 404)


@router.get("/api/sandbox/runs/{run_id}/file")
def sandbox_run_file(run_id: str, path: str):
    base = (sandbox.runs_dir() / run_id).resolve()
    f = (base / path).resolve()
    if base not in f.parents or not f.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(f)


# ================================================================ IDE files
def _fs(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ide_fs.FsError as e:
        code = 409 if str(e).startswith("CONFLICT") else 400
        raise HTTPException(code, str(e))


@router.get("/api/ide/tree")
def ide_tree():
    return ide_fs.tree()


@router.get("/api/ide/file")
def ide_read(path: str):
    return _fs(ide_fs.read, path)


@router.get("/api/ide/raw")
def ide_raw(path: str):
    p = _fs(ide_fs.safe, path)
    if not p.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(p)


@router.put("/api/ide/file")
def ide_write(body: dict = Body(...)):
    return _fs(ide_fs.write, body.get("path", ""), body.get("content", ""), body.get("mtime"))


@router.post("/api/ide/create")
def ide_create(body: dict = Body(...)):
    return _fs(ide_fs.create, body.get("path", ""), bool(body.get("folder")))


@router.post("/api/ide/rename")
def ide_rename(body: dict = Body(...)):
    return _fs(ide_fs.rename, body.get("from", ""), body.get("to", ""))


@router.delete("/api/ide/file")
def ide_delete(path: str):
    return _fs(ide_fs.delete, path)


@router.post("/api/ide/upload")
async def ide_upload(folder: str = Form(""), files: list[UploadFile] = File(...)):
    out = []
    for f in files:
        out.append(_fs(ide_fs.upload, f"{folder.rstrip('/')}/{Path(f.filename or 'file').name}".lstrip("/"), await f.read()))
    return {"uploaded": out}


@router.get("/api/ide/search")
def ide_search(q: str):
    return {"hits": ide_fs.search(q)}


@router.post("/api/ide/seed")
def ide_seed():
    design = (workspace() / "experiment_design.md")
    skel = (workspace() / "experiment_skeleton.py")
    created = ide_fs.seed(design.read_text("utf-8") if design.exists() else "", skel.read_text("utf-8") if skel.exists() else "")
    return {"created": created, "tree": ide_fs.tree()}


# ================================================================ co-coding agent (self-debugging loop)
@router.post("/api/ide/agent")
async def ide_agent(body: dict = Body(...)):
    from .chat_store import create_session, record_turn
    history = [m for m in body.get("messages", []) if m.get("role") in ("user", "assistant") and m.get("content")]
    if not history or history[-1]["role"] != "user":
        raise HTTPException(400, "Last message must be from the user")
    auto = bool(body.get("auto"))
    cpu = bool(body.get("cpu"))  # v3.2: the agent's commands run on CPU (smoke tests while the GPU must stay free)
    max_iters = max(1, min(8, int(body.get("max_iters") or sandbox.load_settings().get("self_debug_max", 4))))
    open_file = body.get("open_file") or ""
    sid = body.get("session_id") or create_session(tool="ide")["id"]
    keep = int(load_config()["memory"]["keep_recent_turns"])
    q: asyncio.Queue = asyncio.Queue()

    async def emit(ev):
        await q.put(ev)

    async def work():
        convo = [{"role": m["role"], "content": m["content"]} for m in history[-keep * 2:]]
        transcript = []
        try:
            await emit({"type": "start", "session_id": sid, "auto": auto, "max_iters": max_iters,
                        "runtime": agent_runtime(load_config(), "coder")})
            for it in range(1, max_iters + 1):
                await emit({"type": "iter", "n": it})
                system = await asyncio.to_thread(coder.system_prompt, open_file, "", convo[-1]["content"][:2000] if convo else "")
                text, meta = "", {}
                async for kind, val in stream_agent("coder", system, convo, max_tokens=8000, temperature=0.2):
                    if kind == "delta":
                        text += val
                        await emit({"type": "delta", "text": val})
                    else:
                        meta = val
                text = meta.get("text", text)
                parsed = coder.parse(text)
                files = await asyncio.to_thread(coder.preview, parsed["files"])
                await emit({"type": "proposal", "iter": it, "text": text, "files": files, "run": parsed["run"],
                            "engine": meta.get("engine"), "model": meta.get("model"), "note": meta.get("note", "")})
                transcript.append(text)
                convo.append({"role": "assistant", "content": text})
                if not auto:
                    break
                if files:
                    applied = await asyncio.to_thread(coder.apply, files)
                    await emit({"type": "applied", "paths": applied})
                cmd = parsed["run"] or body.get("run_cmd") or ""
                if not cmd:
                    break
                res = await coder.run_and_wait(cmd, emit, cpu=cpu)
                j = res["job"]
                if j["status"] == "done":
                    transcript.append(f"✅ `{cmd}` succeeded (exit 0). Metrics: {json.dumps((res['meta'] or {}).get('metrics', {}))[:300]}")
                    break
                if j["status"] == "stopped":
                    transcript.append(f"■ `{cmd}` was stopped.")
                    break
                fb = (f"The command `{cmd}` FAILED with exit code {j['exit_code']} (attempt {it}/{max_iters}).\n"
                      f"STDERR (last lines):\n```\n{res['stderr'][-6000:]}\n```\nSTDOUT (last lines):\n```\n{res['stdout'][-2500:]}\n```\n"
                      "Find the root cause, fix the files (complete file blocks) and run again.")
                transcript.append(f"❌ `{cmd}` failed (exit {j['exit_code']}) — self-debugging…")
                convo.append({"role": "user", "content": fb})
                if it == max_iters:
                    await emit({"type": "gave_up", "n": it})
            final = "\n\n".join(transcript)
            saved = await asyncio.to_thread(record_turn, sid, history, {"content": final, "engine": meta.get("engine", ""), "note": meta.get("note", "")})
            await emit({"type": "done", "reply": final, "session": {"id": sid, "title": saved.get("title"), "count": len(saved.get("messages", []))}})
        except LLMError as e:
            await emit({"type": "error", "detail": str(e)})
        except sandbox.VramBusyError as e:
            await emit({"type": "error", "detail": str(e), "vram_busy": e.models})
        except sandbox.SandboxError as e:
            await emit({"type": "error", "detail": str(e)})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await emit({"type": "error", "detail": f"{type(e).__name__}: {e}"})
        finally:
            await q.put(None)

    async def gen():
        task = asyncio.create_task(work())
        try:
            while True:
                ev = await q.get()
                if ev is None:
                    break
                yield sse(ev)
        finally:
            if not task.done():
                task.cancel()
    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/api/ide/apply")
def ide_apply(body: dict = Body(...)):
    files = [f for f in body.get("files", []) if f.get("path")]
    return {"applied": _fs(coder.apply, files)}


# ================================================================ git / github
def _git(fn, *a, **k):
    try:
        return fn(*a, **k)
    except gitops.GitError as e:
        raise HTTPException(400, str(e))


@router.get("/api/git/status")
async def git_status():
    return await run_in_threadpool(_git, gitops.status)


@router.post("/api/git/init")
async def git_init():
    return await run_in_threadpool(_git, gitops.init)


@router.get("/api/git/diff")
async def git_diff(path: str):
    return await run_in_threadpool(_git, gitops.diff, path)


@router.post("/api/git/commit")
async def git_commit(body: dict = Body(...)):
    return await run_in_threadpool(_git, gitops.commit, body.get("message", ""), body.get("paths"))


@router.post("/api/git/discard")
async def git_discard(body: dict = Body(...)):
    return await run_in_threadpool(_git, gitops.discard, body.get("path", ""))


@router.post("/api/git/publish")
async def git_publish(body: dict = Body(...)):
    return await run_in_threadpool(_git, gitops.publish, body.get("repo", ""), body.get("private", True), body.get("description", ""))


@router.post("/api/git/push")
async def git_push():
    return await run_in_threadpool(_git, gitops.push)


@router.post("/api/git/pull")
async def git_pull():
    return await run_in_threadpool(_git, gitops.pull)


@router.get("/api/git/user")
async def git_user():
    return await run_in_threadpool(_git, gitops.gh_user)


# ================================================================ memory, decisions, context graph
@router.get("/api/memory/status")
async def memory_status():
    return await run_in_threadpool(M.status)


@router.post("/api/memory/summarize")
async def memory_summarize(body: dict = Body(default={})):
    return await M.summarize(force=bool(body.get("force", True)))


@router.put("/api/memory/tier3")
def memory_tier3(body: dict = Body(...)):
    return M.set_tier3(body)["tier3"]


@router.put("/api/memory/episode/{eid}")
def memory_episode_put(eid: str, body: dict = Body(...)):
    return M.edit_episode(eid, body)


@router.delete("/api/memory/episode/{eid}")
def memory_episode_delete(eid: str):
    M.delete_episode(eid)
    return {"deleted": eid}


@router.get("/api/decisions")
def decisions_list():
    return {"decisions": M.load()["decisions"]}


@router.post("/api/decisions")
def decisions_add(body: dict = Body(...)):
    if not str(body.get("text", "")).strip():
        raise HTTPException(400, "Empty decision")
    return M.add_decision(body["text"], body.get("kind", "direction"), body.get("source", ""), body.get("locked", True))


@router.put("/api/decisions/{did}")
def decisions_edit(did: str, body: dict = Body(...)):
    return M.edit_decision(did, body)


@router.delete("/api/decisions/{did}")
def decisions_delete(did: str):
    M.delete_decision(did)
    return {"deleted": did}


@router.get("/api/context/graph")
async def context_graph():
    return await run_in_threadpool(CG.build)


@router.post("/api/context/ops")
async def context_ops(body: dict = Body(...)):
    return await run_in_threadpool(CG.apply_ops, body.get("ops", []))


@router.get("/api/context/chat")
def context_chat_get():
    return {"messages": CG.load_chat()}


@router.delete("/api/context/chat")
def context_chat_clear():
    CG.save_chat([])
    return {"ok": True}


@router.post("/api/context/agent")
async def context_agent(body: dict = Body(...)):
    msg = str(body.get("message", "")).strip()
    if not msg:
        raise HTTPException(400, "Empty command")
    hist = CG.load_chat()
    r = await CG.agent(msg, hist)
    hist += [{"role": "user", "content": msg, "ts": time.time()},
             {"role": "assistant", "content": r["reply"], "ops": r["ops"], "engine": r["engine"], "ts": time.time()}]
    CG.save_chat(hist)
    return r


# ================================================================ Lit2Plan: decisions-aware regeneration with versions
def _versions_dir():
    d = workspace() / "lit2plan_versions"
    d.mkdir(exist_ok=True)
    return d


def snapshot_plan(reason: str):
    f = workspace() / "lit2plan.md"
    if f.exists() and f.read_text("utf-8").strip():
        name = time.strftime("%Y%m%d-%H%M%S") + ".md"
        k = 1
        while (_versions_dir() / name).exists():
            k += 1
            name = time.strftime("%Y%m%d-%H%M%S") + f"-{k}.md"
        (_versions_dir() / name).write_text(f.read_text("utf-8"), "utf-8")
        meta = _versions_dir() / "_index.json"
        idx = json.loads(meta.read_text("utf-8")) if meta.exists() else {}
        idx[name] = reason
        meta.write_text(json.dumps(idx, ensure_ascii=False, indent=1), "utf-8")


@router.post("/api/tool/lit2plan/regenerate")
async def lit2plan_regenerate(body: dict = Body(default={})):
    from .chat_store import SessionNotFound, get_active, load_session
    from .library import included, reference_digest
    plan_f = workspace() / "lit2plan.md"
    plan = plan_f.read_text("utf-8") if plan_f.exists() else ""
    if not plan.strip():
        raise HTTPException(400, "Generate a research plan first")
    sid = body.get("session_id") or get_active("lit2plan")
    discussion = ""
    if sid:
        try:
            msgs = load_session(sid, activate=False)["messages"]
            discussion = "\n\n".join(f"{m['role'].upper()}: {m['content'][:4000]}" for m in msgs[-30:])
        except SessionNotFound:
            pass
    st = M.load()
    episodes = "\n\n".join(f"### {e['title']}\n{e['summary']}" for e in st["tier2"] if e.get("tool") == "lit2plan" or (sid and e.get("session") == sid))
    decisions = M.decisions_block(st, CG.purged_ids())
    pinned = CG.pinned_block()
    user = (f"CURRENT RESEARCH PLAN (version to update):\n{plan}\n\n"
            f"LOCKED DECISIONS (binding — chosen directions must be central, rejected ones must not reappear):\n{decisions or '(none)'}\n\n"
            f"OTHER PINNED CONTEXT:\n{pinned or '(none)'}\n\n"
            f"SUMMARIES OF EARLIER DISCUSSION:\n{episodes or '(none)'}\n\n"
            f"RECENT DISCUSSION WITH THE RESEARCHER:\n{discussion or '(none)'}\n\n"
            f"LOCAL LIBRARY (cite as [bib_key]):\n{reference_digest(included()[:40], 300)}")
    system = (prompts.LIT2PLAN_SYS + prompts.output_language(body.get("lang")) +
              "\n\nYOU ARE UPDATING AN EXISTING PLAN after a discussion with the researcher. Keep the same section structure; integrate every "
              "conclusion of the discussion; make the locked decisions the backbone of the plan (gaps, hypotheses, roadmap must follow them); "
              "drop or demote directions that were rejected; keep what is still valid. End with a section:\n"
              "## Changelog vs previous version\nBullet list of what changed and why (which discussion point or decision caused it).")
    r = await call_agent("lit2plan", system, user, max_tokens=10000, temperature=0.3)
    snapshot_plan("before regeneration")
    plan_f.write_text(r["text"], "utf-8")
    snapshot_plan("regenerated from discussion")
    await run_in_threadpool(M.refresh_tier3)
    return {"plan": r["text"], "engine": r["engine"], "note": r.get("note", ""), "versions": lit2plan_versions()["versions"]}


@router.get("/api/tool/lit2plan/versions")
def lit2plan_versions():
    meta = _versions_dir() / "_index.json"
    idx = json.loads(meta.read_text("utf-8")) if meta.exists() else {}
    vs = sorted([p.name for p in _versions_dir().glob("*.md")], reverse=True)
    return {"versions": [{"name": v, "reason": idx.get(v, ""), "size": (_versions_dir() / v).stat().st_size} for v in vs]}


@router.get("/api/tool/lit2plan/version/{name}")
def lit2plan_version(name: str):
    f = _versions_dir() / Path(name).name
    if not f.exists():
        raise HTTPException(404, "Version not found")
    return {"name": f.name, "content": f.read_text("utf-8")}


@router.post("/api/tool/lit2plan/restore")
def lit2plan_restore(body: dict = Body(...)):
    f = _versions_dir() / Path(body.get("name", "")).name
    if not f.exists():
        raise HTTPException(404, "Version not found")
    snapshot_plan("before restore")
    (workspace() / "lit2plan.md").write_text(f.read_text("utf-8"), "utf-8")
    return {"plan": f.read_text("utf-8")}


# ================================================================ Paper Writer: import experiment results
@router.post("/api/paper/import-results")
def paper_import_results(body: dict = Body(default={})):
    from .paper import load_project, save_project
    runs = [r for r in sandbox.list_runs(200) if r.get("status") == "done" and r.get("metrics")]
    want = set(body.get("run_ids") or [])
    if want:
        runs = [r for r in runs if r["id"] in want]
    runs = runs[:12]
    if not runs:
        raise HTTPException(400, "No successful runs with metrics yet — run experiments in 💻 Workspace & Runs first")
    best = sandbox.best_metrics()
    keys = []
    for r in runs:
        for k in r["metrics"]:
            if k not in keys:
                keys.append(k)
    keys = keys[:8]
    lines = ["Results imported from the sandbox runs (real measured values):"]
    for r in runs:
        lines.append(f"- run {r['id']} (`{(r.get('cmd') or '')[:80]}`): " + ", ".join(f"{k}={v:.4g}" for k, v in r["metrics"].items() if isinstance(v, (int, float))))
    if best:
        lines.append("Best values: " + ", ".join(f"{k}={v['value']:.4g} ({v['direction']}, run {v['run']})" for k, v in best.items()))

    def esc(s):
        return re.sub(r"([_%&#])", r"\\\1", str(s))
    head = " & ".join(["Run"] + [esc(k) for k in keys])
    rows = []
    for r in runs:
        vals = []
        for k in keys:
            v = r["metrics"].get(k)
            b = best.get(k, {})
            cell = "--" if not isinstance(v, (int, float)) else f"{v:.4g}"
            if isinstance(v, (int, float)) and b.get("run") == r["id"]:
                cell = f"\\textbf{{{cell}}}"
            vals.append(cell)
        rows.append(" & ".join([esc(r["id"][-9:])] + vals) + r" \\")
    table = ("\\begin{table}[t]\n\\centering\n\\caption{Experimental results (imported from the sandbox runs).}\n\\label{tab:runs}\n"
             f"\\resizebox{{\\columnwidth}}{{!}}{{%\n\\begin{{tabular}}{{l{'c' * len(keys)}}}\n\\toprule\n{head} \\\\\n\\midrule\n"
             + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}}\n\\end{table}")
    p = load_project()
    notes = "\n".join(lines)
    if body.get("save", True):
        p["results_notes"] = ((p.get("results_notes") or "").rstrip() + "\n\n" + notes).strip()
        if body.get("add_table", True) and table not in p["tables"]:
            p["tables"].append(table)
        save_project(p)
    figs = []
    for r in runs:
        for f in r.get("figures") or []:
            figs.append(f"{r['id']}/{f}")
    return {"notes": notes, "table": table, "figures": figs, "project": p}


# ================================================================ project export (everything)
@router.get("/api/export/project.zip")
def export_project():
    from .paper import assemble, load_project
    buf = io.BytesIO()
    ws = workspace()
    try:
        main, bib, _ = assemble()
    except Exception:
        main, bib = "", ""
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if main:
            z.writestr("paper/main.tex", main)
            z.writestr("paper/references.bib", bib)
            from .results import figure_files
            for src, rel in figure_files([main]):
                z.write(src, f"paper/{rel}")
        rroot = data_dir() / "results"
        if rroot.exists():
            for f in rroot.rglob("*"):
                if f.is_file() and "_trash" not in f.relative_to(rroot).parts and f.stat().st_size < 40_000_000:
                    z.write(f, "results/" + str(f.relative_to(rroot)).replace("\\", "/"))
        pdf = ws / "build" / "main.pdf"
        if pdf.exists():
            z.write(pdf, "paper/main.pdf")
        for name in ("lit2plan.md", "experiment_design.md", "experiment_skeleton.py", "review.md", "masterclass_guide.md"):
            if (ws / name).exists():
                z.write(ws / name, f"research/{name}")
        z.writestr("research/project.json", json.dumps(load_project(), ensure_ascii=False, indent=1))
        mem = data_dir() / "memory"
        for f in mem.glob("*.json") if mem.exists() else []:
            z.write(f, f"memory/{f.name}")
        code = sandbox.code_dir()
        for f in code.rglob("*"):
            if f.is_file() and not any(p in ide_fs.IGNORE_DIRS for p in f.relative_to(code).parts) and f.stat().st_size < 20_000_000:
                z.write(f, "code/" + str(f.relative_to(code)).replace("\\", "/"))
        for r in sandbox.runs_dir().iterdir():
            for f in r.glob("*"):
                if f.is_file() and f.stat().st_size < 10_000_000:
                    z.write(f, f"runs/{r.name}/{f.name}")
            for f in (r / "figures").glob("*") if (r / "figures").exists() else []:
                z.write(f, f"runs/{r.name}/figures/{f.name}")
        z.writestr("README.md", f"# Project export — {date.today().isoformat()}\n\nPhD Research Lab v3 project export:\n"
                                "- `paper/` LaTeX manuscript (+ PDF if compiled)\n- `research/` plan, experiment design, reviews\n"
                                "- `code/` the code workspace\n- `runs/` logs, metrics.json and figures of every run\n"
                                "- `results/` research results you uploaded (files, extracted text, notes in index.json)\n"
                                "- `memory/` hierarchical memory (project_state.json), context graph, decisions\n")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="project_export.zip"'})


# ================================================================ MCP (Streamable HTTP, JSON responses)
@router.post("/mcp")
async def mcp(request: Request):
    hdrs = {k.lower(): v for k, v in request.headers.items()}
    code, why = mcp_server.guard(hdrs, request.client.host if request.client else "?")
    if code:
        mcp_server.audit({"denied": code, "reason": why})
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": why}}, code)
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}, 400)
    sess = hdrs.get("mcp-session-id", "")[:80]
    meta: dict = {}
    if isinstance(payload, list):
        res = [r for r in [await run_in_threadpool(mcp_server.handle, m, sess, meta) for m in payload if isinstance(m, dict)] if r]
        out = JSONResponse(res) if res else Response(status_code=202)
    elif isinstance(payload, dict):
        r = await run_in_threadpool(mcp_server.handle, payload, sess, meta)
        out = JSONResponse(r) if r else Response(status_code=202)
    else:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}, 400)
    if meta.get("session_id"):
        out.headers["Mcp-Session-Id"] = meta["session_id"]
    return out


@router.get("/mcp")
def mcp_get():
    return Response(status_code=405, headers={"Allow": "POST"})
