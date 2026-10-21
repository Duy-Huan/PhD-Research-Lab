"""Model lifecycle manager (v4.1): when is a model / session / container / connection pool loaded, and when is it released.

Every AI engine class goes through one lease API, so the researcher chooses the policy once in Settings:

    kind   resource                                   "loaded" means                       released by
    local  LM Studio / Ollama model                   weights resident in VRAM/RAM          unload (keep_alive 0 / REST unload)
    cli    native CLI conversation (Codex, Claude     a resumable provider session id       forgetting the session id (the CLI
           Code, agy) per gateway session            (the process exits after a request)   process itself always exits)
    mcp    the Docker sandbox container used by MCP   container running                     docker stop (only when no job runs)
           tools and agent/HPO trial runs
    cloud  pooled HTTPS connections to LLM APIs       keep-alive connections + TLS          closing the pool

Policies (config.lifecycle, one vocabulary for every class):
    unload_after_task  load → task → unload, after `unload_grace_s` (debounce: a burst of calls does not thrash VRAM)
    keep_loaded        keep until the researcher unloads it (Settings → Local AI → Unload)
    idle_unload        keep while in use, release after <kind>_idle_min minutes without a task
Local models have two policies: `local_background` (agents in config.BACKGROUND_AGENTS, workflow steps, embeddings —
default unload_after_task) and `local_interactive` (chats; default idle_unload).

Safety rules
  • A resource with an active lease is never released (a model is never unloaded while it is answering).
  • respect_manual_loads: a model / container that was already resident before PhD-Lab needed it belongs to the
    researcher — it is used but never released automatically (only the manual Unload button releases it).
  • single_model_vram: before PhD-Lab loads a model it releases its OWN idle local models first, so two models never
    compete for a consumer GPU's VRAM (12 GB on the reference machine).
  • Every failure is reported in status()/history and never breaks the request that triggered it.
"""
from __future__ import annotations

import asyncio
import contextvars
import threading
import time
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field

import httpx

from backend.core.config import BACKGROUND_AGENTS, LIFECYCLE_POLICIES, load_config

KINDS = ("local", "cli", "mcp", "cloud")
UNLOAD, KEEP, IDLE = LIFECYCLE_POLICIES
_PURPOSE: contextvars.ContextVar = contextvars.ContextVar("phdlab_lifecycle_purpose", default="")
_lock = threading.RLock()
_res: dict = {}
HISTORY: deque = deque(maxlen=60)
_probe_cache: dict = {}
_pool: dict = {"client": None, "loop": None}
_main: dict = {"loop": None}
CLI_SESSIONS: dict = {}  # (gateway session id, provider) → native provider session id


@dataclass
class Resource:
    key: str
    kind: str
    engine: str
    model: str
    leases: int = 0
    owner: str = "lifecycle"      # lifecycle | external (resident before PhD-Lab needed it)
    state: str = "loading"        # loading | in_use | idle
    policy: str = ""
    purposes: set = field(default_factory=set)
    purpose: str = ""            # purpose of the most recent lease (used when release() is not told)
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    release_at: float | None = None
    tasks: int = 0
    note: str = ""
    ready: threading.Event = field(default_factory=threading.Event)

    def public(self, now: float | None = None) -> dict:
        now = now or time.time()
        return {"key": self.key, "kind": self.kind, "engine": self.engine, "model": self.model, "leases": self.leases,
                "owner": self.owner, "state": self.state, "policy": self.policy, "purposes": sorted(self.purposes),
                "loaded_at": round(self.loaded_at, 1), "last_used": round(self.last_used, 1), "tasks": self.tasks,
                "release_in_s": None if self.release_at is None else max(0, round(self.release_at - now)), "note": self.note}


# ------------------------------------------------------------------ settings & purpose
def settings(cfg: dict | None = None) -> dict:
    return (cfg or load_config())["lifecycle"]


def enabled(cfg: dict | None = None) -> bool:
    return bool(settings(cfg).get("enabled", True))


def purpose_for(agent: str) -> str:
    """Explicit context (workflow steps, background jobs) wins; otherwise the agent's own nature."""
    return _PURPOSE.get() or ("background" if agent in BACKGROUND_AGENTS else "interactive")


def policy_for(kind: str, purpose: str = "interactive", cfg: dict | None = None) -> str:
    s = settings(cfg)
    if kind == "local":
        return s.get("local_background" if purpose == "background" else "local_interactive", IDLE)
    return s.get(kind, IDLE)


def _deadline(kind: str, policy: str, cfg: dict, now: float) -> float | None:
    s = settings(cfg)
    if policy == UNLOAD:
        return now + float(s.get("unload_grace_s", 15))
    if policy == IDLE:
        return now + 60.0 * max(1, int(s.get(f"{kind}_idle_min", 10)))
    return None


def _log(action: str, key: str, ok: bool = True, reason: str = "", detail: str = "") -> None:
    HISTORY.appendleft({"ts": round(time.time(), 1), "action": action, "key": key, "ok": ok, "reason": reason,
                        "detail": detail[:240]})


def _run(coro):
    """Run a coroutine from synchronous code (also when this thread already runs an event loop)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: dict = {}

    def target():
        try:
            box["v"] = asyncio.run(coro)
        except BaseException as e:  # re-raised in the caller's thread
            box["e"] = e
    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join()
    if "e" in box:
        raise box["e"]
    return box.get("v")


# ------------------------------------------------------------------ local model residency
def _norm(model: str) -> str:
    m = (model or "").strip().lower()
    return m[:-7] if m.endswith(":latest") else m


async def resident_local(cfg: dict | None = None, max_age: float = 2.0) -> dict:
    """{"ollama": {model: info}, "local": {model: info}} — what LM Studio / Ollama hold right now (cached briefly)."""
    hit = _probe_cache.get("local")
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    from backend.providers import local as local_ai
    cfg = cfg or load_config()
    out: dict = {"ollama": {}, "local": {}, "online": {"ollama": False, "local": False}}
    ol, lm = await asyncio.gather(local_ai.ollama_status(cfg["ollama_base_url"]), local_ai.lmstudio_status(cfg["lmstudio_base_url"]),
                                  return_exceptions=True)
    if isinstance(ol, dict):
        out["online"]["ollama"] = bool(ol.get("online"))
        for m in ol.get("loaded") or []:
            if m.get("id"):
                out["ollama"][m["id"]] = {"size_mb": _mb(m.get("size")), "vram_mb": _mb(m.get("size_vram")),
                                          "expires_at": m.get("expires_at")}
    if isinstance(lm, dict):
        out["online"]["local"] = bool(lm.get("online"))
        info = {m.get("id"): m for m in lm.get("models") or []}
        for mid in lm.get("loaded") or []:
            out["local"][mid] = {"quantization": (info.get(mid) or {}).get("quantization", ""), "vram_mb": None}
    _probe_cache["local"] = (time.time(), out)
    return out


def _mb(v) -> float | None:
    return round(v / 2 ** 20) if isinstance(v, (int, float)) and v else None


def _is_resident(res_map: dict, engine: str, model: str) -> bool:
    return _norm(model) in {_norm(m) for m in res_map.get(engine, {})}


async def _prepare_local(res: Resource, cfg: dict) -> None:
    from backend.providers import local as local_ai
    s = settings(cfg)
    resident = await resident_local(cfg, max_age=0)
    if _is_resident(resident, res.engine, res.model):
        res.owner = "external" if s.get("respect_manual_loads", True) else "lifecycle"
        res.note = "already loaded when PhD-Lab needed it" if res.owner == "external" else ""
        return
    if s.get("single_model_vram", True):
        for other in [r for r in list(_res.values()) if r.kind == "local" and r is not res and r.leases == 0
                      and r.owner == "lifecycle" and _norm(r.model) != _norm(res.model)]:
            await _release_now(other, "single model in VRAM: making room for " + res.model, cfg)
    res.owner = "lifecycle"
    if res.engine == "local":  # LM Studio: load explicitly (no JIT TTL), so the lifecycle — not LM Studio — decides
        try:
            await local_ai.lmstudio_load(cfg["lmstudio_base_url"], res.model)
            _log("loaded", res.key, reason="lease")
        except Exception as e:  # the request itself still tries just-in-time loading
            res.note = f"explicit load failed ({str(e)[:120]}); just-in-time load"
    _probe_cache.pop("local", None)


async def _after_local_release(res: Resource, cfg: dict) -> None:
    """Ollama re-applies its own default keep_alive (5 min) on every request: pin the model so OUR policy decides."""
    if res.engine != "ollama" or res.owner != "lifecycle" or res.policy == UNLOAD:
        return
    from backend.providers import local as local_ai
    try:
        await local_ai.ollama_load(cfg["ollama_base_url"], res.model, keep_alive="-1")
    except Exception as e:
        res.note = f"could not pin keep_alive ({str(e)[:100]})"


# ------------------------------------------------------------------ mcp (sandbox container)
def _container_running() -> bool:
    from backend.execution import sandbox
    try:
        return bool(sandbox.container_state().get("running"))
    except Exception:
        return False


async def _prepare_mcp(res: Resource, cfg: dict) -> None:
    running = await asyncio.to_thread(_container_running)
    if running and settings(cfg).get("respect_manual_loads", True):
        res.owner, res.note = "external", "container was already running"


def _stop_container() -> str:
    from backend.execution import sandbox
    if any(j.status == "running" for j in sandbox.JOBS.values()):
        return "kept: a sandbox job is still running"
    if not _container_running():
        return "already stopped"
    sandbox.container_action("stop")
    return "container stopped"


# ------------------------------------------------------------------ leases
async def acquire(kind: str, engine: str, model: str, purpose: str | None = None, cfg: dict | None = None) -> Resource | None:
    if kind not in KINDS:
        raise ValueError(f"unknown lifecycle kind {kind}")
    cfg = cfg or load_config()
    if not enabled(cfg):
        return None
    purpose = purpose or _PURPOSE.get() or "interactive"
    key = f"{kind}:{engine}:{model}"
    with _lock:
        res = _res.get(key)
        creator = res is None
        if creator:
            res = _res[key] = Resource(key, kind, engine, model)
        res.leases += 1
        res.purposes.add(purpose)
        res.purpose = purpose
        res.release_at = None
    if creator:
        try:
            if kind == "local":
                await _prepare_local(res, cfg)
            elif kind == "mcp":
                await _prepare_mcp(res, cfg)
        except Exception as e:  # never break the task over bookkeeping
            res.note = f"prepare failed: {str(e)[:140]}"
        finally:
            res.state = "in_use"
            res.ready.set()
    elif not res.ready.is_set():
        await asyncio.to_thread(res.ready.wait, 900)
    res.state = "in_use"
    return res


async def release(res: Resource | None, purpose: str | None = None, cfg: dict | None = None) -> None:
    if res is None:
        return
    cfg = cfg or load_config()
    now = time.time()
    with _lock:
        res.leases = max(0, res.leases - 1)
        res.tasks += 1
        res.last_used = now
        if res.leases:
            return
        res.state = "idle"
        res.policy = policy_for(res.kind, purpose or res.purpose or _PURPOSE.get() or "interactive", cfg)
        protected = res.owner == "external" and settings(cfg).get("respect_manual_loads", True)
        res.release_at = None if protected else _deadline(res.kind, res.policy, cfg, now)
    if res.kind == "local":
        await _after_local_release(res, cfg)


@asynccontextmanager
async def lease(kind: str, engine: str, model: str, purpose: str | None = None):
    cfg = load_config()
    res = await acquire(kind, engine, model, purpose, cfg)
    try:
        yield res
    finally:
        await release(res, purpose, cfg)


@contextmanager
def lease_sync(kind: str, engine: str, model: str, purpose: str | None = None):
    cfg = load_config()
    purpose = purpose or _PURPOSE.get() or "interactive"
    res = _run(acquire(kind, engine, model, purpose, cfg))
    try:
        yield res
    finally:
        _run(release(res, purpose, cfg))


@contextmanager
def sandbox_lease(purpose: str = "background"):
    """Lease on the Docker sandbox container for MCP tools / agent / trial runs (no-op in local Python mode)."""
    from backend.execution import sandbox
    try:
        docker = sandbox.effective_mode() == "docker"
    except Exception:
        docker = False
    if not docker:
        yield None
        return
    with lease_sync("mcp", "docker", sandbox.container_name(), purpose) as r:
        yield r


# ------------------------------------------------------------------ releasing
async def _release_now(res: Resource, reason: str, cfg: dict | None = None) -> dict:
    """Release one resource (callers check that it has no lease). Never raises."""
    from backend.providers import local as local_ai
    cfg = cfg or load_config()
    with _lock:
        if res.leases:
            return {"key": res.key, "ok": False, "detail": "in use"}
        _res.pop(res.key, None)
    detail, ok = "", True
    try:
        if res.kind == "local":
            if res.engine == "ollama":
                await local_ai.ollama_unload(cfg["ollama_base_url"], res.model)
            else:
                await local_ai.lmstudio_unload(cfg["lmstudio_base_url"], res.model)
            detail = "unloaded from memory"
            _probe_cache.pop("local", None)
        elif res.kind == "cli":
            CLI_SESSIONS.pop((res.model, res.engine), None)
            detail = "native session forgotten (next request starts a new one)"
        elif res.kind == "mcp":
            detail = await asyncio.to_thread(_stop_container)
        else:  # cloud (acquire() only accepts KINDS)
            detail = await _close_pool()
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
    _log("released", res.key, ok, reason, detail)
    return {"key": res.key, "ok": ok, "detail": detail}


async def release_due(now: float | None = None, cfg: dict | None = None) -> list:
    now = now or time.time()
    with _lock:
        due = [r for r in _res.values() if r.leases == 0 and r.release_at is not None and r.release_at <= now]
    out = []
    for r in due:
        out.append(await _release_now(r, f"policy {r.policy}", cfg))
    return out


def next_deadline() -> float | None:
    with _lock:
        ds = [r.release_at for r in _res.values() if r.leases == 0 and r.release_at is not None]
    return min(ds) if ds else None


async def reaper(stop: asyncio.Event) -> None:
    """Started with the app: applies the release deadlines (sleeps until the next one, at most 10 s)."""
    _main["loop"] = asyncio.get_running_loop()
    while not stop.is_set():
        try:
            await release_due()
        except Exception as e:  # pragma: no cover - defensive: the loop must survive anything
            _log("reaper_error", "-", False, detail=str(e))
        nd = next_deadline()
        delay = 10.0 if nd is None else min(10.0, max(0.25, nd - time.time()))
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
    await _close_pool()


async def unload(engine: str, model: str = "", force: bool = False) -> dict:
    """Manual unload (Settings → Local AI). Works for any resident model, also those PhD-Lab did not load.
    A model that is answering right now is skipped unless force=True."""
    from backend.providers import local as local_ai
    cfg = load_config()
    resident = await resident_local(cfg, max_age=0)
    targets = [m for m in resident.get(engine, {}) if not model or _norm(m) == _norm(model)]
    if model and not targets:
        targets = [model]
    done, skipped, errors = [], [], []
    for m in targets:
        busy = [r for r in _res.values() if r.kind == "local" and r.engine == engine and _norm(r.model) == _norm(m) and r.leases]
        if busy and not force:
            skipped.append(m)
            continue
        try:
            if engine == "ollama":
                await local_ai.ollama_unload(cfg["ollama_base_url"], m)
            else:
                await local_ai.lmstudio_unload(cfg["lmstudio_base_url"], m)
            done.append(m)
            with _lock:
                for k in [k for k, r in _res.items() if r.kind == "local" and r.engine == engine and _norm(r.model) == _norm(m)]:
                    _res.pop(k, None)
            _log("unloaded", f"local:{engine}:{m}", reason="manual")
        except Exception as e:
            errors.append(f"{m}: {str(e)[:160]}")
            _log("unloaded", f"local:{engine}:{m}", False, "manual", str(e))
    _probe_cache.pop("local", None)
    return {"engine": engine, "unloaded": done, "skipped_in_use": skipped, "errors": errors}


async def unload_all_local(force: bool = False) -> dict:
    a = await unload("ollama", force=force)
    b = await unload("local", force=force)
    return {"ollama": a, "lmstudio": b,
            "unloaded": [f"ollama:{m}" for m in a["unloaded"]] + [f"lmstudio:{m}" for m in b["unloaded"]],
            "skipped_in_use": a["skipped_in_use"] + b["skipped_in_use"], "errors": a["errors"] + b["errors"]}


def local_busy() -> list:
    with _lock:
        return [r.key for r in _res.values() if r.kind == "local" and r.leases]


def free_vram_for_gpu(cfg: dict | None = None, log=None) -> dict:
    """resources.auto_unload_for_gpu: release idle local models before a GPU training run (never a model that answers).
    Synchronous (called by the sandbox from a worker thread)."""
    from backend.execution import resources
    busy = local_busy()
    if busy:
        return {"ok": False, "busy": busy}
    rep = resources.unload_local_models(cfg, log)
    with _lock:
        for k in [k for k, r in _res.items() if r.kind == "local"]:
            _res.pop(k, None)
    _probe_cache.pop("local", None)
    _log("unloaded", "local:*", not rep.get("errors"), "GPU training run", ", ".join(rep.get("unloaded") or []))
    return {"ok": not rep.get("errors"), **rep}


# ------------------------------------------------------------------ cloud: pooled HTTP client
async def _close_pool() -> str:
    c, loop = _pool["client"], _pool["loop"]
    _pool.update(client=None, loop=None)
    if c is None:
        return "no open connections"
    try:
        if loop is asyncio.get_running_loop():
            await c.aclose()
        elif loop is not None and not loop.is_closed():
            asyncio.run_coroutine_threadsafe(c.aclose(), loop)
    except Exception:  # pragma: no cover - closing a dead pool is best effort
        pass
    return "connection pool closed"


@asynccontextmanager
async def http_client(timeout):
    """HTTP client for LLM calls. Pooled (keep-alive, TLS reuse) on the app's event loop unless the cloud policy is
    unload_after_task; a fresh client — closed at the end — everywhere else (worker threads, tests, lifecycle off)."""
    cfg = load_config()
    loop = asyncio.get_running_loop()
    pooled = enabled(cfg) and policy_for("cloud", cfg=cfg) != UNLOAD and loop is _main["loop"]
    if not pooled:
        async with httpx.AsyncClient(timeout=timeout) as c:
            yield c
        return
    if _pool["client"] is None or _pool["client"].is_closed:
        _pool.update(client=httpx.AsyncClient(timeout=timeout, limits=httpx.Limits(max_keepalive_connections=8,
                                                                                    keepalive_expiry=60)), loop=loop)
    res = await acquire("cloud", "http", "pool", cfg=cfg)
    try:
        yield _pool["client"]
    finally:
        await release(res, cfg=cfg)


# ------------------------------------------------------------------ cli: native sessions
def cli_resume(gw_session: str, provider: str, cfg: dict | None = None) -> str:
    """Native provider session to resume for this gateway session ('' = start a new one), per the cli policy."""
    cfg = cfg or load_config()
    if not enabled(cfg) or policy_for("cli", cfg=cfg) == UNLOAD:
        return ""
    return CLI_SESSIONS.get((gw_session, provider), "")


def cli_remember(gw_session: str, provider: str, native_session: str, cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    if not native_session or not enabled(cfg) or policy_for("cli", cfg=cfg) == UNLOAD:
        return
    CLI_SESSIONS[(gw_session, provider)] = native_session


# ------------------------------------------------------------------ status (Settings → Local AI / lifecycle card)
async def status(cfg: dict | None = None) -> dict:
    from backend.execution import resources
    cfg = cfg or load_config()
    now = time.time()
    resident = await resident_local(cfg, max_age=1.5)
    with _lock:
        reg = {k: r.public(now) for k, r in _res.items()}
    models = []
    for engine in ("ollama", "local"):
        for mid, info in resident.get(engine, {}).items():
            r = next((v for v in reg.values() if v["kind"] == "local" and v["engine"] == engine and _norm(v["model"]) == _norm(mid)), None)
            models.append({"engine": engine, "engine_label": "Ollama" if engine == "ollama" else "LM Studio", "model": mid, **info,
                           "managed": bool(r), "owner": (r or {}).get("owner", "external"), "leases": (r or {}).get("leases", 0),
                           "state": (r or {}).get("state", "resident"), "policy": (r or {}).get("policy", ""),
                           "release_in_s": (r or {}).get("release_in_s"), "last_used": (r or {}).get("last_used")})
    loading = [v for v in reg.values() if v["kind"] == "local" and v["state"] == "loading"]
    g = (await asyncio.to_thread(resources.gpus, 2.0) or [None])[0] or {}
    try:
        from backend.providers import cli as connectors
        cli_running = len(connectors._procs)
    except Exception:  # pragma: no cover
        cli_running = 0
    s = settings(cfg)
    return {"settings": s, "policies": list(LIFECYCLE_POLICIES), "local": {"models": models, "loading": loading,
                                                                            "online": resident.get("online", {})},
            "gpu": {"name": g.get("name", ""), "vram_used_mb": g.get("vram_used_mb"), "vram_total_mb": g.get("vram_total_mb"),
                    "util_pct": g.get("util_pct"), "temp_c": g.get("temp_c")},
            "cli": {"running_processes": cli_running, "sessions": [v for v in reg.values() if v["kind"] == "cli"],
                    "remembered": len(CLI_SESSIONS)},
            "mcp": [v for v in reg.values() if v["kind"] == "mcp"],
            "cloud": {"pool_open": _pool["client"] is not None, "leases": [v for v in reg.values() if v["kind"] == "cloud"]},
            "registry": list(reg.values()), "history": list(HISTORY)[:30], "busy_local": local_busy()}


def reset() -> None:
    """Tests: forget all bookkeeping (nothing is unloaded)."""
    with _lock:
        _res.clear()
    HISTORY.clear()
    _probe_cache.clear()
    CLI_SESSIONS.clear()
    _pool.update(client=None, loop=None)
    _main["loop"] = None
