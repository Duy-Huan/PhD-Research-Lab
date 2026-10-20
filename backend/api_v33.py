"""v3.3 / v3.4 API: research state, state-aware retrieval, role-aware compilation with trace, evidence & provenance,
memory candidates (lifecycle), sensitivity, telemetry — and the Context Gateway (providers, requests, streaming,
comparison, audit). Docs: docs/architecture/context-memory-v3.3.md, docs/architecture/context-gateway-v3.4.md."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from .gateway import connectors as GC, service as GS
from .memory import evidence as EV, lifecycle as LC, research as RM

router = APIRouter()
ERRORS = (ValueError, KeyError, LookupError, PermissionError, RM.ResearchError, EV.EvidenceError, LC.LifecycleError,
          GS.GatewayError, GC.ProviderError)


async def _call(fn, *a, code: int = 400, **k):
    try:
        return await run_in_threadpool(fn, *a, **k)
    except ERRORS as e:
        raise HTTPException(404 if isinstance(e, KeyError) else code, str(e).strip("'\""))


def _purged():
    from .context_graph import purged_ids
    return purged_ids()


# ================================================================ Research State
@router.get("/api/memory/state")
async def memory_state():
    from .memory.state import current
    return await _call(lambda: current(_purged()))


@router.put("/api/memory/focus")
async def memory_focus(body: dict = Body(...)):
    from .memory.working import set_focus
    return await _call(set_focus, str(body.get("hypothesis_id") or ""), str(body.get("experiment_id") or ""))


@router.get("/api/memory/policies")
def memory_policies():
    from .memory.policy import POLICIES, TOOL_ROLE
    return {"roles": {k: v.to_dict() for k, v in POLICIES.items()}, "tool_role": TOOL_ROLE}


# ================================================================ retrieval / compilation
@router.post("/api/memory/v3/retrieve")
async def memory_retrieve(body: dict = Body(...)):
    from .memory import engine

    def go():
        ctx = engine.build_context(str(body.get("query") or "")[:2000], role=str(body.get("role") or ""),
                                   session_id=str(body.get("session_id") or ""), filters=body.get("filters") or {},
                                   temporal=str(body.get("temporal") or "auto"), purged=_purged(), k=max(1, min(100, int(body.get("k") or 24))))
        return engine.retrieve(ctx)
    return await _call(go)


@router.post("/api/memory/v3/compile")
async def memory_compile(body: dict = Body(...)):
    from .config import load_config
    from .memory.compiler import compile_context, trace_text

    def go():
        cfg = load_config()
        c = compile_context(str(body.get("tool") or ""), str(body.get("session_id") or ""), str(body.get("query") or "")[:2000],
                            int(body.get("budget_tokens") or cfg["memory"]["context_budget_tokens"]), _purged(), cfg,
                            role=str(body.get("role") or ""), filters=body.get("filters") or None)
        if body.get("trace"):
            c["trace_text"] = trace_text(c)
        return c
    return await _call(go)


@router.post("/api/memory/explain")
async def memory_explain(body: dict = Body(...)):
    from .memory.engine import explain
    return await _call(explain, str(body.get("id") or ""), str(body.get("query") or ""), str(body.get("role") or ""),
                       purged=_purged())


@router.put("/api/memory/sensitivity")
async def memory_sensitivity(body: dict = Body(...)):
    from .gateway.policy import set_sensitivity
    return await _call(set_sensitivity, str(body.get("id") or ""), str(body.get("level") or ""))


# ================================================================ evidence / decisions / failures / provenance
@router.get("/api/evidence")
def evidence_all():
    return EV.load()


@router.post("/api/evidence/claims")
async def evidence_claim(body: dict = Body(...)):
    return await _call(EV.add_claim, str(body.get("text") or ""), str(body.get("hypothesis_id") or ""), body.get("source_refs") or [])


@router.post("/api/evidence")
async def evidence_add(body: dict = Body(...)):
    return await _call(EV.add_evidence, body, "human")


@router.put("/api/evidence/{evid}/status")
async def evidence_status(evid: str, body: dict = Body(...)):
    return await _call(EV.set_evidence_status, evid, str(body.get("status") or ""), code=404)


@router.get("/api/evidence/{item_id}")
async def evidence_get(item_id: str):
    return await _call(EV.get, item_id, code=404)


@router.delete("/api/evidence/{item_id}")
async def evidence_delete(item_id: str):
    await _call(EV.delete, item_id)
    return {"deleted": item_id}


@router.post("/api/research/decisions")
async def research_decision(body: dict = Body(...)):
    """A decision recorded by the researcher (human origin) — may cite evidence, name the provider/session it came out of,
    and supersede an older decision."""
    from .memory import add_decision

    def go():
        text = str(body.get("text") or "").strip()
        if not text:
            raise ValueError("Describe the decision")
        return add_decision(text, str(body.get("kind") or "direction"), source=str(body.get("source") or "researcher"),
                            locked=bool(body.get("locked", True)), evidence_ids=body.get("evidence_ids") or [], origin="human",
                            provider=str(body.get("provider") or ""), session=str(body.get("session") or ""),
                            supersedes=str(body.get("supersedes") or ""))
    return await _call(go)


@router.put("/api/research/failures/{fid}")
async def research_failure_put(fid: str, body: dict = Body(...)):
    return await _call(RM.update_failure, fid, body, code=404)


@router.get("/api/provenance/chain/{item_id}")
async def provenance_chain(item_id: str, depth: int = 4):
    from .memory.trace import chain
    return await _call(chain, item_id, max(1, min(8, depth)), code=404)


# ================================================================ memory lifecycle (candidates)
@router.get("/api/memory/candidates")
def candidates(status: str = ""):
    return {"candidates": LC.list_candidates(status)}


@router.post("/api/memory/candidates")
async def candidate_add(body: dict = Body(...)):
    return await _call(LC.propose, str(body.get("kind") or ""), body.get("payload") or {}, "human")


@router.post("/api/memory/candidates/{cid}/approve")
async def candidate_approve(cid: str, body: dict = Body(default={})):
    return await _call(LC.approve, cid, (body or {}).get("edits") or None)


@router.post("/api/memory/candidates/{cid}/reject")
async def candidate_reject(cid: str, body: dict = Body(default={})):
    return await _call(LC.reject, cid, str((body or {}).get("reason") or ""))


# ================================================================ telemetry
@router.get("/api/telemetry")
def telemetry(limit: int = 100, operation: str = ""):
    from . import telemetry as T
    from .memory import cache
    return {"summary": T.summary(), "recent": T.recent(max(1, min(1000, limit)), operation), "cache": cache.stats()}


# ================================================================ Context Gateway (v3.4)
def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("/api/gateway/providers")
async def gw_providers():
    return await _call(GS.status)


@router.post("/api/gateway/providers/{pid}/connect")
async def gw_connect(pid: str, body: dict = Body(default={})):
    return await _call(lambda: GC.get(pid).connect(bool((body or {}).get("launch"))))


@router.post("/api/gateway/providers/{pid}/disconnect")
async def gw_disconnect(pid: str, body: dict = Body(default={})):
    return await _call(lambda: GC.get(pid).disconnect(bool((body or {}).get("revoke"))))


@router.get("/api/gateway/providers/{pid}/mcp")
async def gw_mcp_snippet(pid: str, request: Request):
    from .config import load_config
    tok = bool(load_config()["mcp"].get("token"))
    if pid == "chatgpt_web":
        return GC.chatgpt_web_note()
    return await _call(lambda: GC.get(pid).mcp_registration(_base(request), "<token>" if tok else ""))


@router.post("/api/gateway/providers/antigravity/register-mcp")
async def gw_register_antigravity(request: Request):
    from .config import load_config
    return await _call(lambda: GC.CONNECTORS["antigravity"].register_mcp(_base(request), load_config()["mcp"].get("token", "")))


@router.post("/api/gateway/packet")
async def gw_packet(body: dict = Body(...)):
    from .gateway.context import canonical_packet
    from .gateway.policy import allowed_classes
    return await _call(canonical_packet, str(body.get("query") or "")[:2000], str(body.get("role") or ""),
                       allowed=allowed_classes(), purged=_purged())


@router.post("/api/gateway/requests")
async def gw_prepare(request: Request, body: dict = Body(...)):
    """Compile the context for one provider. review=true (or the review_before_external setting) holds it for the
    researcher; otherwise send=true starts it right away."""
    def go():
        r = GS.prepare(str(body.get("query") or ""), str(body.get("provider") or ""), role=str(body.get("role") or ""),
                       session_id=str(body.get("session_id") or ""), review=body.get("review"),
                       budget_tokens=body.get("budget_tokens"), resume_session=str(body.get("resume_session") or ""))
        if body.get("send") and r["status"] == "ready":
            return GS.send(r["id"], base_url=_base(request))
        return r
    return await _call(go)


@router.post("/api/gateway/requests/{rid}/send")
async def gw_send(rid: str, request: Request, body: dict = Body(default={})):
    return await _call(GS.send, rid, (body or {}).get("prompt"), _base(request))


@router.get("/api/gateway/requests/{rid}")
async def gw_get(rid: str):
    return await _call(lambda: GS.public(GS.get(rid)), code=404)


@router.get("/api/gateway/requests/{rid}/events")
async def gw_events(rid: str, after: int = 0):
    return await _call(GS.events, rid, max(0, after), code=404)


@router.get("/api/gateway/requests/{rid}/stream")
async def gw_stream(rid: str, after: int = 0):
    """SSE of the normalised InternalEvents until the request ends."""
    await _call(GS.get, rid, code=404)

    async def gen():
        pos = max(0, after)
        while True:
            d = GS.events(rid, pos)
            for e in d["events"]:
                yield f"data: {json.dumps(e)}\n\n"
            pos = d["next"]
            if d["status"] not in ("running", "review", "ready"):
                yield f"event: end\ndata: {json.dumps({'status': d['status']})}\n\n"
                return
            await asyncio.sleep(0.25)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/api/gateway/requests/{rid}/cancel")
async def gw_cancel(rid: str):
    return await _call(GS.cancel, rid)


@router.post("/api/gateway/requests/{rid}/propose")
async def gw_propose(rid: str, body: dict = Body(...)):
    extra = {k: v for k, v in body.items() if k not in ("kind", "text")}
    return await _call(GS.propose, rid, str(body.get("kind") or ""), str(body.get("text") or ""), **extra)


@router.post("/api/gateway/compare")
async def gw_compare(request: Request, body: dict = Body(...)):
    return await _call(GS.compare, str(body.get("query") or ""), list(body.get("providers") or []), str(body.get("role") or ""),
                       str(body.get("session_id") or ""), body.get("review"), _base(request))


@router.get("/api/gateway/sessions/{sid}")
async def gw_session(sid: str):
    return await _call(GS.get_session, sid, code=404)


@router.get("/api/gateway/audit")
def gw_audit(limit: int = 200):
    return {"events": GS.read_audit(max(1, min(2000, limit)))}


# ================================================================ execution environments (v3.4: Python env / Docker / Auto)
def _sbx_err(e):
    from . import sandbox
    msg = str(e)
    if isinstance(e, sandbox.SandboxError) and msg.startswith("NEED_IMAGE:"):
        img = msg.split(":", 1)[1]
        raise HTTPException(409, {"need_image": img, "message": f"Image {img} is not downloaded yet — pull it first."})
    raise HTTPException(400, msg)


@router.get("/api/env")
async def env_summary():
    from . import envs
    return await _call(envs.summary)


@router.get("/api/env/pythons")
async def env_pythons(refresh: int = 0):
    from . import envs
    return {"pythons": await run_in_threadpool(envs.discover_pythons, bool(refresh))}


@router.get("/api/env/docker/catalog")
async def env_docker_catalog():
    from . import envs
    return await _call(envs.docker_catalog)


@router.get("/api/env/docker/search")
async def env_docker_search(q: str):
    from . import envs
    return {"results": await _call(envs.hub_search, q)}


@router.get("/api/env/docker/tags")
async def env_docker_tags(repo: str, q: str = ""):
    from . import envs
    try:
        return {"tags": await run_in_threadpool(envs.hub_tags, repo, q)}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # network / Docker Hub unavailable
        raise HTTPException(502, f"Docker Hub not reachable: {type(e).__name__}")


@router.post("/api/env/select")
async def env_select(body: dict = Body(...)):
    """{kind: python|docker|auto, python_mode, python_base, image, gpu, auto_deps, torch_index}"""
    from . import envs, sandbox

    def go():
        patch = {k: body[k] for k in ("python_mode", "python_base", "image", "gpu", "auto_deps", "torch_index") if k in body}
        kind = body.get("kind")
        if kind:
            patch["mode"] = {"python": "local", "docker": "docker", "auto": "auto"}.get(kind, "auto")
        if patch.get("image") and not envs.valid_image(patch["image"]):
            raise ValueError(f"Invalid image name: {patch['image']}")
        sandbox.save_settings(patch)
        return envs.summary()
    try:
        return await run_in_threadpool(go)
    except (ValueError, sandbox.SandboxError) as e:
        raise HTTPException(400, str(e))


@router.get("/api/env/deps")
async def env_deps():
    from . import deps
    from .sandbox import code_dir
    return await _call(lambda: deps.detect(code_dir()))


@router.post("/api/env/prepare")
async def env_prepare(body: dict = Body(default={})):
    """One action: create the Python env (or pull the image + start the container) and install the dependencies.
    Returns the job to follow (same stream as runs). With Docker and a missing image the pull job comes first."""
    from . import deps, sandbox

    def go():
        s = sandbox.load_settings()
        mode = sandbox.effective_mode(s)
        if mode == "docker":
            img = sandbox.effective_image(s)
            if not sandbox.image_present(img):
                return {"step": "pull", "job": sandbox.pull_image(img).info(), "image": img}
            sandbox.ensure_container()
        else:
            sandbox._local_python()  # creates the project venv on first use
        plan = deps.write(sandbox.code_dir())
        job = sandbox.start_job("python .phdlab/ensure_deps.py", kind="setup", title="Install project dependencies")
        return {"step": "deps", "job": job.info(), "mode": mode, "deps": plan}
    try:
        return await run_in_threadpool(go)
    except sandbox.SandboxError as e:
        _sbx_err(e)


@router.post("/api/jupyter/kernel")
async def jupyter_kernel():
    from .integrations import workspace as W
    return await _call(W.ensure_project_kernel)
