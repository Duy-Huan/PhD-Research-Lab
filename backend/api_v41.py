"""v4.1 API: model lifecycle (load / unload policies, VRAM residency), secure CLI space, workflow orchestrator, HPO,
model intelligence. Every route is local-only (the app's Host guard applies) and returns honest NOT-available states."""
from __future__ import annotations

import json

from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from . import model_lifecycle as LC
from .config import load_config
from .gateway import workspace as W
from .workflow import ORCH, OrchestratorError
from .workflow import hpo as H, model_intel as MI, steps as ST, templates as TP

router = APIRouter()


def _err(e: Exception, code: int = 400) -> HTTPException:
    msg = str(e)
    if isinstance(e, OrchestratorError) and msg.endswith("not found"):
        code = 404
    return HTTPException(code, msg)


# ================================================================ model lifecycle
@router.get("/api/lifecycle/status")
async def lifecycle_status():
    """Resident local models (VRAM), leases, release countdowns, CLI sessions, sandbox container, connection pool."""
    return await LC.status()


@router.post("/api/lifecycle/unload")
async def lifecycle_unload(body: dict = Body(default={})):
    """Manual unload: {engine: ollama | local | all, model?: id, force?: bool}. A model answering right now is skipped
    unless force=true."""
    eng = str(body.get("engine") or "all")
    force = bool(body.get("force"))
    if eng == "all":
        return await LC.unload_all_local(force)
    if eng not in ("ollama", "local"):
        raise HTTPException(400, "engine must be ollama, local (LM Studio) or all")
    return await LC.unload(eng, str(body.get("model") or ""), force)


@router.post("/api/lifecycle/release")
async def lifecycle_release(body: dict = Body(...)):
    """Release one tracked resource now (CLI session, sandbox container, connection pool, local model) if unused."""
    key = str(body.get("key") or "")
    res = LC._res.get(key)
    if res is None:
        raise HTTPException(404, "not a tracked resource")
    if res.leases:
        raise HTTPException(409, "in use right now — try again when the task has finished")
    return await LC._release_now(res, "manual")


# ================================================================ secure CLI space
@router.get("/api/cli-space")
async def cli_space():
    cfg = load_config()
    from .gateway.connectors import CONNECTORS
    return {"root": str(W.root(cfg)), "profile": cfg["gateway"].get("cli_profile", "review"), "profiles": W.PROFILES,
            "isolation": {pid: {pr: W.isolation(pid, pr) for pr in W.PROFILES} for pid in CONNECTORS},
            "sessions": await run_in_threadpool(W.sessions, 50, cfg),
            "retention_days": cfg["gateway"].get("cli_retention_days"), "max_sessions": cfg["gateway"].get("cli_max_sessions")}


@router.post("/api/cli-space/prune")
async def cli_space_prune():
    return {"removed": await run_in_threadpool(W.prune, None, True)}


# ================================================================ model intelligence & HPO (manual tools)
@router.get("/api/model/adapters")
def model_adapters():
    return {"adapters": MI.adapters(), "engines": H.engines(load_config()["features"])}


@router.post("/api/model/analyze")
async def model_analyze(body: dict = Body(...)):
    """Scenario A (manual model audit): spec → complexity report + memory/feasibility against this PC."""
    if not load_config()["features"].get("model_intelligence", True):
        raise HTTPException(403, "model intelligence is switched off (features.model_intelligence)")
    try:
        rep = MI.analyze_spec(body.get("spec") or {})
        feas = await run_in_threadpool(MI.feasibility, rep, int(body.get("batch_size") or 1), body.get("precision") or "fp32",
                                       body.get("optimizer") or "adam")
    except (MI.ModelError, TypeError, ValueError) as e:
        raise HTTPException(400, str(e))
    return {"report": rep, "feasibility": feas}


@router.post("/api/hpo/validate")
def hpo_validate(body: dict = Body(...)):
    try:
        return H.validate_space(body.get("search_space") or {}, body.get("objectives") or [], int(body.get("max_trials") or 0),
                                str(body.get("sampler") or "auto"), float(body.get("est_trial_minutes") or 0),
                                float(body.get("max_runtime_minutes") or 0))
    except (TypeError, ValueError) as e:
        raise HTTPException(400, str(e))


@router.get("/api/workflows/studies")
def studies():
    return {"studies": H.list_studies()}


@router.get("/api/workflows/studies/{study_id}")
def study(study_id: str):
    try:
        st = H.load_study(study_id)
    except H.HPOError as e:
        raise HTTPException(404, str(e))
    return {**st, "summary": H.summarize(st)}


# ================================================================ workflow registry
@router.get("/api/workflows/templates")
def wf_templates():
    out = []
    for t in TP.all_templates():
        out.append({k: t.get(k) for k in ("id", "version", "name", "description", "execution_mode", "builtin", "inputs",
                                          "budgets", "approvals")} | {"steps": [{"id": s["id"], "type": s["type"],
                                                                                   "label": s.get("label", s["id"]),
                                                                                   "mode": s.get("mode", "")}
                                                                                  for s in t["steps"]]})
    return {"templates": out, "step_types": ST.public_registry(), "features": load_config()["features"]}


@router.get("/api/workflows/templates/{wid}")
def wf_template(wid: str, version: int | None = None):
    t = TP.get(wid, version)
    if t is None:
        raise HTTPException(404, "workflow not found")
    return t


@router.post("/api/workflows/validate")
def wf_validate(body: dict = Body(...)):
    d, errs = ORCH.validate(body.get("definition") or body)
    return {"valid": not errs, "errors": errs, "definition": d}


@router.post("/api/workflows/templates")
def wf_save(body: dict = Body(...)):
    d, errs = ORCH.validate(body.get("definition") or {})
    if errs:
        raise HTTPException(400, "; ".join(errs[:12]))
    try:
        return TP.save(d)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/api/workflows/templates/{wid}/{version}")
def wf_delete(wid: str, version: int):
    try:
        ok = TP.delete(wid, version)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "workflow not found")
    return {"deleted": True}


# ================================================================ runs
@router.get("/api/workflows/runs")
def wf_runs(limit: int = 50):
    return {"runs": ORCH.list(max(1, min(200, limit)))}


@router.post("/api/workflows/runs")
async def wf_create(body: dict = Body(...)):
    try:
        run = ORCH.create(str(body.get("workflow_id") or ""), body.get("definition"), body.get("inputs") or {},
                          body.get("overrides") or {}, body.get("version"))
        if body.get("start", True):
            ORCH.start(run["id"])
    except OrchestratorError as e:
        raise _err(e)
    return ORCH.public(run)


@router.get("/api/workflows/runs/{rid}")
def wf_run(rid: str):
    try:
        return ORCH.public(ORCH.get(rid))
    except OrchestratorError as e:
        raise _err(e)


@router.post("/api/workflows/runs/{rid}/{action}")
async def wf_action(rid: str, action: str):
    try:
        if action in ("start", "resume"):
            return ORCH.start(rid)
        if action == "pause":
            return ORCH.pause(rid)
        if action == "cancel":
            return ORCH.cancel(rid)
    except OrchestratorError as e:
        raise _err(e)
    raise HTTPException(404, "unknown action (start, resume, pause, cancel)")


@router.post("/api/workflows/runs/{rid}/steps/{sid}/decision")
async def wf_decide(rid: str, sid: str, body: dict = Body(...)):
    try:
        return ORCH.decide(rid, sid, str(body.get("decision") or ""), str(body.get("note") or ""), body.get("output"),
                           body.get("params_patch"), body.get("values"))
    except OrchestratorError as e:
        raise _err(e)


@router.get("/api/workflows/runs/{rid}/events")
def wf_events(rid: str, after: int = 0):
    try:
        return {"events": ORCH.events_since(rid, max(0, after))}
    except OrchestratorError as e:
        raise _err(e)


@router.get("/api/workflows/runs/{rid}/stream")
async def wf_stream(rid: str, after: int = 0, once: int = 0):
    """SSE: events after `after`, then live until the run ends (heartbeat every 15 s). once=1 returns after one batch."""
    try:
        ORCH.get(rid)
    except OrchestratorError as e:
        raise _err(e)

    async def gen():
        seq = max(0, after)
        while True:
            evs = ORCH.events_since(rid, seq)
            for e in evs:
                seq = e["seq"]
                yield f"data: {json.dumps(e, default=str)}\n\n"
            run = ORCH.get(rid)
            if once or (run["status"] in ("SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXCEEDED") and not evs):
                yield f"data: {json.dumps({'type': 'end', 'status': run['status']})}\n\n"
                return
            await ORCH.wait_change(rid, 15)
            yield ": keep-alive\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/api/workflows/runs/{rid}/export")
def wf_export(rid: str):
    try:
        run = ORCH.get(rid)
    except OrchestratorError as e:
        raise _err(e)
    return {"definition": run["definition"], "run": ORCH.public(run), "events": ORCH.events_since(rid, 0)}

