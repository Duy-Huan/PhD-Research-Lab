"""System: version, settings, models (picker + local engines), research providers, dashboard, the UI ⇄ CLI event bus."""
from __future__ import annotations

import asyncio
from asyncio import wait_for

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from backend.api.common import call, sse, stream
from backend.core import bus
from backend.core.config import APP_VERSION, AGENTS, PROVIDERS, ROOT, load_config, public_config, save_config

router = APIRouter()


@router.get("/api/version")
def version():
    return {"version": APP_VERSION, "root": str(ROOT)}


@router.get("/api/config")
def get_config():
    return public_config(load_config())


@router.post("/api/config")
def set_config(body: dict = Body(...)):
    out = public_config(save_config(body))
    bus.publish("config.updated", keys=",".join(sorted(body))[:200])
    return out


# ------------------------------------------------------------------ models
@router.post("/api/models/cli/codex")
async def codex_catalog():
    from backend.providers.app_server import model_catalog
    models = await call(model_catalog)
    cfg = load_config()
    save_config({"gateway": {"cli_models": {**cfg["gateway"].get("cli_models", {}), "codex": models}}})
    return {"models": models, "entitlement_verified": False}


@router.get("/api/models")
async def models():
    """The chat's model picker: the agents (what engine/model each one uses now) and every selectable provider id."""
    from backend.providers import registry
    from backend.providers.models import agent_runtime
    cfg = load_config()
    agents = await run_in_threadpool(lambda: {a: agent_runtime(cfg, a) | {"label": AGENTS[a]["label"]} for a in AGENTS})
    provs = await run_in_threadpool(registry.registry)
    from backend.providers.models import resolve_engine
    catalog = {}
    for agent in AGENTS:
        engine = resolve_engine(cfg, agent)
        provider = next((p for p in provs if p["id"] in ("app:" + engine, "cli:" + engine)), None)
        choices = (cfg.get("mcp_agent") or {}).get("models", []) if engine == "mcp" else (provider or {}).get("capabilities", {}).get("models", [])
        catalog[agent] = {"engine": engine, "mode": cfg["agent_modes"][agent], "label": (provider or {}).get("label", engine),
                          "models": list(dict.fromkeys([m for m in [*choices, cfg.get("agent_models", {}).get(agent)] if m])),
                          "selected": cfg.get("agent_models", {}).get(agent, "")}
    return {"agents": agents, "agent_catalog": catalog, "providers": [{k: p[k] for k in ("id", "label", "transport", "state", "available", "detail")}
                                            | {"models": p["capabilities"]["models"],
                                               "reasoning": p["capabilities"]["reasoning_controls"]} for p in provs],
            "default": cfg["aiws"]["provider"], "cloud": {k: {"label": v["label"], "models": v["models"]}
                                                          for k, v in PROVIDERS.items()}}


@router.post("/api/models/test")
async def test_model(body: dict = Body(...)):
    from backend.providers.models import LLMError, _stream_engine, default_model_for
    pid = str(body.get("provider", "")).removeprefix("app:")
    if pid not in (*PROVIDERS, "local", "ollama"):
        raise HTTPException(400, "Unknown provider")
    cfg = load_config()
    model = str(body.get("model") or "").strip() or None
    async def collect():
        return [part async for part in _stream_engine(cfg, pid, "Reply with the single word: OK",
                                                     [{"role": "user", "content": "ping"}], 256, None, model)]
    try:
        parts = await wait_for(collect(), timeout=60)
    except asyncio.TimeoutError as e:
        raise HTTPException(504, "Provider connection test timed out after 60 seconds.") from e
    text = "".join(parts).strip()
    if not text:
        raise LLMError("The provider returned an empty stream. Check the base URL, selected model and provider logs.")
    return {"ok": True, "provider": pid, "transport": "stream", "model": model or default_model_for(cfg, pid) or "(auto)",
            "reply": text[:80]}


@router.post("/api/models/list")
async def provider_models(body: dict = Body(...)):
    from backend.providers.models import list_provider_models
    return {"models": await list_provider_models(load_config(), str(body.get("provider", "")))}


@router.get("/api/models/local")
async def local_status():
    """LM Studio / Ollama: reachable, available models, what is in VRAM now."""
    from backend.providers import lifecycle as LC
    from backend.providers import local as local_ai
    cfg = load_config()
    lm, ol = await asyncio.gather(local_ai.lmstudio_status(cfg["lmstudio_base_url"]), local_ai.ollama_status(cfg["ollama_base_url"]))
    return {"lmstudio": lm, "ollama": ol, "selected": {"local": cfg.get("local_model", ""), "ollama": cfg.get("ollama_model", "")},
            "lifecycle": await LC.status()}


@router.post("/api/models/unload")
async def unload_models(body: dict = Body(default={})):
    """Unload local models from VRAM: {engine: all | local | ollama, model?, force?}."""
    from backend.providers import lifecycle as LC
    eng = str(body.get("engine") or "all")
    if eng == "all":
        return await LC.unload_all_local(bool(body.get("force")))
    if eng not in ("ollama", "local"):
        raise HTTPException(400, "engine must be ollama, local (LM Studio) or all")
    return await LC.unload(eng, str(body.get("model") or ""), bool(body.get("force")))


# ------------------------------------------------------------------ research providers
@router.get("/api/providers")
async def providers(fresh: int = 0):
    from backend.providers.research import describe_all
    return {"providers": await run_in_threadpool(describe_all, bool(fresh))}


@router.post("/api/providers/{pid}/connect")
async def provider_connect(pid: str):
    """CLI providers sign in with the vendor's own flow; PhD Lab only opens a terminal with the official command."""
    from backend.providers.cli import CONNECTORS
    if pid == "feynman":
        import subprocess
        import sys
        if sys.platform.startswith("win"):
            subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k", "feynman model login"])
        return {"provider": pid, "command": "feynman model login", "launched": sys.platform.startswith("win")}
    if pid not in CONNECTORS:
        raise HTTPException(400, f"{pid} has no sign-in flow")
    return await call(CONNECTORS[pid].connect, True)


# ------------------------------------------------------------------ dashboard + events
@router.get("/api/dashboard")
async def dashboard(advanced: int = 0):
    from backend.agent.dashboard import status
    return await call(status, bool(advanced))


@router.get("/api/events")
def events(after: int = 0, limit: int = 500):
    return bus.since(max(0, after), max(1, min(2000, limit)))


@router.get("/api/events/stream")
async def events_stream(request: Request, after: int = -1, timeout: float = 3600):
    async def gen():
        last = bus.last() if after < 0 else after
        end = asyncio.get_running_loop().time() + max(1.0, min(86400.0, timeout))
        yield sse({"type": "hello", "seq": last})
        while asyncio.get_running_loop().time() < end:
            for e in await run_in_threadpool(bus.wait, last, 1.0):
                last = e["seq"]
                yield sse(e)
            if await request.is_disconnected():
                return
    return stream(gen())
