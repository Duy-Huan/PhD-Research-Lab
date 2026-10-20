"""v3.2 API: Context Memory v2 (compiler, retrieval, compressor, page-store, research & knowledge memory), integration
layer (workspace/VS Code/Dev Containers/Jupyter, ClearML, Codex), hardware resource governor, provenance, live critic,
data connectors and the Control Center dashboard."""
from __future__ import annotations

import re

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from . import resources as RES
from .config import active_project, load_config
from .integrations import IntegrationError, NotSupported, all_status
from .memory import research as RM

router = APIRouter()
RUN_ID = re.compile(r"^[\w-]{6,60}$")


def _err(e: Exception, code: int = 400):
    raise HTTPException(code, str(e))


async def _call(fn, *a, code: int = 400, **k):
    """Run a blocking adapter call in the threadpool and map adapter errors to HTTP errors (no tracebacks to the UI)."""
    try:
        return await run_in_threadpool(fn, *a, **k)
    except NotSupported as e:
        _err(e, 501)
    except (IntegrationError, RM.ResearchError, ValueError, KeyError) as e:
        _err(e, code)


# ================================================================ Context Memory v2
@router.get("/api/memory/v2/compile")
async def memory_compile(q: str = "", tool: str = "", session: str = ""):
    """Exactly the block the agents receive for this query (transparency) + diagnostics + LOD-1 memory map."""
    from .context_graph import purged_ids
    from .memory.compiler import compile_context
    cfg = load_config()
    return await _call(compile_context, tool, session, q[:2000], cfg["memory"]["context_budget_tokens"], purged_ids(), cfg)


@router.post("/api/memory/v2/search")
async def memory_search(body: dict = Body(...)):
    from .context_graph import purged_ids
    from .memory import lod
    from .memory.retrieval import search

    def run():
        nodes = lod.collect(purged_ids())
        res = search(str(body.get("q", ""))[:2000], nodes, load_config(), k=int(body.get("k") or 20))
        by = {n.id: n for n in nodes}
        for h in res["hits"]:
            n = by[h["id"]]
            h.update(tier=n.tier, type=n.type, text=lod.render(n, 5), pages=n.pages)
        return res
    return await _call(run)


@router.get("/api/memory/v2/plan")
async def memory_plan():
    from .memory.compressor import plan
    return await _call(plan, load_config(), False)


@router.post("/api/memory/v2/compress")
async def memory_compress(body: dict = Body(default={})):
    from .memory.compressor import compress
    return await compress(force=bool(body.get("force", True)))


@router.get("/api/memory/pages")
def memory_pages(limit: int = 100):
    from .memory.pages import list_pages
    return {"pages": list(reversed(list_pages(limit)))}


@router.get("/api/memory/pages/{pid}")
def memory_page(pid: str):
    from .memory.pages import get_page
    try:
        return get_page(pid)
    except (ValueError, KeyError) as e:
        _err(e, 404)


# ---------------------------------------------------------------- Research Memory
@router.get("/api/research")
def research_all():
    return RM.load()


@router.get("/api/research/timeline")
def research_timeline(limit: int = 200):
    return {"events": RM.timeline(limit)}


@router.post("/api/research/hypotheses")
async def research_hyp_add(body: dict = Body(...)):
    return await _call(RM.add_hypothesis, str(body.get("text", "")), "researcher", body.get("status", "proposed"))


@router.put("/api/research/hypotheses/{hid}")
async def research_hyp_put(hid: str, body: dict = Body(...)):
    return await _call(RM.update_hypothesis, hid, body, code=404)


@router.post("/api/research/experiments")
async def research_exp_add(body: dict = Body(...)):
    return await _call(RM.add_experiment, body)


@router.put("/api/research/experiments/{eid}")
async def research_exp_put(eid: str, body: dict = Body(...)):
    return await _call(RM.update_experiment, eid, body, code=404)


@router.post("/api/research/failures")
async def research_fail_add(body: dict = Body(...)):
    return await _call(RM.add_failure, str(body.get("text", "")), str(body.get("hypothesis_id", "")),
                       str(body.get("run_id", "")), str(body.get("reason", "")))


@router.delete("/api/research/{item_id}")
async def research_delete(item_id: str):
    await _call(RM.delete, item_id, code=404)
    return {"deleted": item_id}


# ---------------------------------------------------------------- Knowledge Memory
@router.get("/api/knowledge")
def knowledge_all():
    from .memory import knowledge
    return {**knowledge.load(), "papers": knowledge.papers(60)}


@router.post("/api/knowledge")
async def knowledge_add(body: dict = Body(...)):
    from .memory import knowledge
    try:
        return knowledge.add(body.get("kind", "concept"), body.get("name", ""), body.get("text", ""), body.get("refs") or [],
                             body.get("code_ref", ""))
    except knowledge.KnowledgeError as e:
        _err(e)


@router.delete("/api/knowledge/{item_id}")
def knowledge_delete(item_id: str):
    from .memory import knowledge
    knowledge.delete(item_id)
    return {"deleted": item_id}


# ================================================================ integrations
@router.get("/api/integrations")
async def integrations(force: int = 0):
    if force:
        from .integrations.base import clear_cache
        clear_cache()
    return {"integrations": await run_in_threadpool(all_status)}


@router.get("/api/workspace")
async def workspace_info():
    from .integrations import workspace as W

    def run():
        t = W.targets()
        st = W.vscode_status()
        from . import gitops
        return {"targets": {k: str(v) for k, v in t.items()}, "deep_links": {k: W.deep_link(k) for k in t},
                "vscode": st.to_dict(), "devcontainer": (t["code"] / ".devcontainer" / "devcontainer.json").exists(),
                "git": gitops.head_info(), "jupyter": W.jupyter_status().to_dict()}
    return await _call(run)


@router.post("/api/workspace/open")
async def workspace_open(body: dict = Body(default={})):
    from .integrations import workspace as W
    target = body.get("target", "code")
    if body.get("mode") == "devcontainer":
        return await _call(W.open_devcontainer, target, code=409)
    return await _call(W.open_folder, target, code=409)


@router.post("/api/workspace/open-file")
async def workspace_open_file(body: dict = Body(...)):
    from .integrations import workspace as W
    return await _call(W.open_file, str(body.get("path", "")), int(body.get("line") or 1), code=409)


@router.post("/api/workspace/extension")
async def workspace_extension(body: dict = Body(...)):
    """Install an allow-listed VS Code extension, e.g. {"id": "openai.chatgpt"} (Codex)."""
    from .integrations import workspace as W
    return await _call(W.install_extension, str(body.get("id", "")), code=409)


@router.get("/api/workspace/environment/options")
def environment_options():
    from .integrations import workspace as W
    return {**W.environment_options(), "policy": RES.policy()}


@router.post("/api/workspace/environment/preview")
async def environment_preview(body: dict = Body(default={})):
    from .integrations import workspace as W
    return {"files": await _call(W.build_environment, body.get("spec") or {})}


@router.post("/api/workspace/environment")
async def environment_write(body: dict = Body(default={})):
    from .integrations import workspace as W
    return await _call(W.write_environment, body.get("spec") or {}, bool(body.get("overwrite")), code=409)


@router.post("/api/jupyter/launch")
async def jupyter_launch(body: dict = Body(default={})):
    from .integrations import workspace as W
    return await _call(W.jupyter_launch, body.get("target", "code"), code=409)


@router.post("/api/jupyter/stop")
async def jupyter_stop():
    from .integrations import workspace as W
    return await _call(W.jupyter_stop)


# ---------------------------------------------------------------- experiment backends & compute
@router.get("/api/experiments/backends")
async def experiment_backends():
    from .integrations.experiment import ClearMLAdapter, LocalRunsBackend
    return {"backends": [(await run_in_threadpool(b.status)).to_dict() for b in (LocalRunsBackend(), ClearMLAdapter())]}


@router.post("/api/experiments/clearml/sync")
async def clearml_sync(body: dict = Body(...)):
    from .integrations.experiment import ClearMLAdapter
    rid = str(body.get("run_id", ""))
    if not RUN_ID.match(rid):
        raise HTTPException(400, "Invalid run id")
    return await _call(ClearMLAdapter().sync_run, rid, code=409)


@router.get("/api/experiments/clearml/{task_id}")
async def clearml_task(task_id: str):
    from .integrations.experiment import ClearMLAdapter
    if not re.fullmatch(r"[0-9a-f]{32}", task_id):
        raise HTTPException(400, "Invalid ClearML task id")
    return await _call(ClearMLAdapter().get_experiment, task_id, code=409)


@router.get("/api/experiments/compare")
async def experiments_compare(ids: str, backend: str = "local"):
    from .integrations.experiment import get_backend
    lst = [i for i in ids.split(",") if i.strip()][:12]
    return await _call(get_backend(backend).compare_experiments, lst)


@router.post("/api/compute/submit")
async def compute_submit(body: dict = Body(...)):
    """target=clearml: enqueue the script for a ClearML Agent; if ClearML is not usable and fallback_local is true
    the command runs in the local sandbox instead (and the answer says so)."""
    from . import sandbox
    from .integrations.experiment import ClearMLAdapter
    script = str(body.get("script", "")).strip()
    cmd = str(body.get("cmd") or (f"python {script}" if script else "")).strip()
    if body.get("target") == "clearml":
        try:
            return {"target": "clearml", **await run_in_threadpool(ClearMLAdapter().submit_remote, script, body.get("args") or {},
                                                                    str(body.get("queue", "")))}
        except IntegrationError as e:
            if not body.get("fallback_local", True):
                _err(e, 409)
            reason = str(e)
        except Exception as e:
            if not body.get("fallback_local", True):
                _err(e, 502)
            reason = f"{type(e).__name__}: {e}"
    else:
        reason = ""
    try:
        job = await run_in_threadpool(sandbox.start_job, cmd, "run", body.get("title", ""),
                                      {"CUDA_VISIBLE_DEVICES": ""} if body.get("cpu") else None)
    except sandbox.VramBusyError as e:
        from .api_v3 import vram_busy_http
        raise vram_busy_http(e)
    except sandbox.SandboxError as e:
        _err(e)
    return {"target": "local", "fallback_reason": reason, "job": job.info()}


# ---------------------------------------------------------------- Codex coding agent
@router.get("/api/codex/status")
async def codex_status():
    from .integrations.agents import CodexBackend
    return (await run_in_threadpool(CodexBackend().status)).to_dict()


@router.post("/api/codex/runs")
async def codex_start(body: dict = Body(...)):
    from .integrations.agents import CodexBackend
    return await _call(CodexBackend().start_run, str(body.get("prompt", "")), bool(body.get("allow_write")),
                       str(body.get("model", "")), str(body.get("resume_thread", "")), body.get("link") or {}, code=409)


@router.get("/api/codex/runs")
def codex_runs():
    from .integrations.agents import list_runs
    return {"runs": list_runs()}


@router.get("/api/codex/runs/{rid}")
async def codex_run(rid: str):
    from .integrations.agents import get_run
    return await _call(get_run, rid, code=404)


@router.post("/api/codex/runs/{rid}/cancel")
async def codex_cancel(rid: str):
    from .integrations.agents import CodexBackend
    return await _call(CodexBackend().cancel_run, rid, code=409)


# ================================================================ hardware resource governor
@router.get("/api/resources/policy")
async def resources_policy():
    return await run_in_threadpool(RES.policy)


@router.get("/api/resources/vram")
async def resources_vram():
    """Which local LLMs hold VRAM right now (a GPU training run is refused while this list is not empty)."""
    def run():
        m = RES.loaded_local_models()
        g = (RES.gpus(0) or [None])[0] or {}
        return {"loaded": [f"ollama:{x}" for x in m["ollama"]] + [f"lmstudio:{x}" for x in m["lmstudio"]],
                "vram_used_mb": g.get("vram_used_mb"), "vram_total_mb": g.get("vram_total_mb"),
                "require_unload": load_config()["resources"].get("require_unload", True)}
    return await run_in_threadpool(run)


@router.post("/api/resources/unload")
async def resources_unload():
    """Manual Strategy A: unload every local LLM from VRAM now."""
    lines = []
    rep = await run_in_threadpool(RES.unload_local_models, None, lines.append)
    return {**rep, "log": lines}


@router.get("/api/resources/routing")
async def resources_routing():
    from .config import AGENTS
    from .llm_router import plan
    cfg = load_config()
    return {"routing": await run_in_threadpool(lambda: {a: plan(cfg, a) for a in AGENTS if cfg["agent_modes"].get(a) == "auto"}),
            "gpu_busy": await run_in_threadpool(RES.gpu_busy)}


# ================================================================ provenance
@router.post("/api/provenance/inspect")
async def provenance_inspect(file: UploadFile = File(...)):
    from .provenance import inspect
    data = await file.read()
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(413, "File larger than 60 MB")
    return await _call(inspect, file.filename or "artifact", data)


@router.post("/api/provenance/seal/{run_id}")
async def provenance_seal(run_id: str):
    from . import sandbox
    from .provenance import seal_run
    if not RUN_ID.match(run_id):
        raise HTTPException(400, "Invalid run id")
    try:
        r = sandbox.get_run(run_id)
    except sandbox.SandboxError as e:
        _err(e, 404)
    cfg = load_config()
    return await run_in_threadpool(seal_run, sandbox.runs_dir() / run_id, run_id, r, cfg["provenance"].get("csv_header", True))


# ================================================================ live critic (on demand)
@router.post("/api/critic/check")
async def critic_check(body: dict = Body(...)):
    from .critic import bib_keys, check_llm, check_rules
    text = str(body.get("text", ""))[:200_000]
    issues = check_rules(text, await run_in_threadpool(bib_keys))
    note = ""
    if body.get("llm"):
        try:
            issues += await check_llm(text)
        except Exception as e:
            note = f"LLM critic unavailable: {type(e).__name__}: {e}"[:300]
    return {"issues": issues, "note": note}


# ================================================================ data connectors
@router.get("/api/connectors")
def connectors_list():
    from .connectors.registry import registry
    return {"connectors": registry().list()}


@router.post("/api/connectors/{name}/search")
async def connectors_search(name: str, body: dict = Body(...)):
    from .connectors.base import ConnectorError
    from .connectors.registry import registry
    try:
        return await run_in_threadpool(registry().fetch, name, str(body.get("query", "")), int(body.get("limit") or 10))
    except ConnectorError as e:
        _err(e, 502)


# ================================================================ Control Center dashboard (fast: no network probes)
@router.get("/api/dashboard")
async def dashboard():
    def run():
        from . import memory as M
        from . import sandbox
        st = M.load()
        rs = RM.load()
        runs = sandbox.list_runs(30)
        g = (RES.gpus(2) or [None])[0]
        active = [j.info() for j in sandbox.JOBS.values() if j.status == "running"]
        hyps = sorted(rs["hypotheses"], key=lambda h: (h["status"] not in ("testing", "proposed"), h["id"]))
        t1 = M.tier1(st)
        return {"project": active_project(),
                "goals": st["tier3"].get("goals", [])[:3],
                "hypotheses": hyps[:8], "hypotheses_total": len(rs["hypotheses"]),
                "experiments": rs["experiments"][-6:][::-1], "failures": rs["failures"][-5:][::-1],
                "active_jobs": active, "recent_runs": runs[:8],
                "failed_runs": [r for r in runs if r.get("status") == "failed"][:5],
                "best_metrics": st["tier3"].get("best_metrics", {}),
                "decisions": [d for d in st["decisions"] if d.get("locked")][-5:],
                "memory": {"tier1_tokens": t1["tokens"], "high": load_config()["memory"]["high_watermark_tokens"],
                           "episodes": len(st["tier2"]), "last_summary": (st.get("stats") or {}).get("last_summary")},
                "gpu": g, "gpu_busy": RES.gpu_busy(),
                "timeline": RM.timeline(12)}
    return await run_in_threadpool(run)
