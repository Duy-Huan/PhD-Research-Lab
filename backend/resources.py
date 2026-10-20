"""Hardware resource governor (v3.2) — HARDWARE_RESOURCE_CONSTRAINT.md.

Policy (derived from the scanned machine; every value can be overridden in config.resources, 0 = derived):
                         reference machine (i5-14400F 10C/16T · RTX 3060 12 GB · 32 GB RAM)
    VRAM safety cap      total − 1 GB for the display                    → 11 GB
    local AI VRAM        ≤ 73 % of the safety cap, max 8 GB (Q4_K_M)      → 8 GB
    RAM safety cap       total − max(12 GB, 37.5 %)                       → 20 GB
    sandbox RAM          80 % of the RAM cap, clamped to [2, 16] GB       → 16 GB
    sandbox CPUs         37.5 % of the logical threads, max 6             → 6
    local AI threads     25 % of the logical threads, max 4               → 4
    free disk            ≥ 50 GB

Strategies
  A  VRAM gate        (researcher's rule) a GPU training run is REFUSED while Ollama / LM Studio still hold a model in
     VRAM (resources.require_unload). Nothing is unloaded automatically: the researcher presses 🧹 Unload
     (unload_local_models: keep_alive 0 / LM Studio unload, then wait ≥ unload_wait_s until VRAM ≤ vram_free_target_mb)
     or chooses to run that job on CPU.
  B  hybrid routing   gpu_busy() tells the LLM router to keep local models off the GPU (cloud, or Ollama num_gpu=0).
  C  CPU offloading   ollama_cpu_options() = {"num_gpu": 0, "num_thread": local AI threads}.
  +  thermal guard    a GPU at/above gpu_temp_limit_c or an unreachable driver → the run starts on CPU
     (CUDA_VISIBLE_DEVICES=""); a run that dies with a GPU-fault signature is re-run once on CPU.
Everything here degrades gracefully: a failing probe never blocks a run, it only adds a warning line to the job log.
"""
from __future__ import annotations

import asyncio
import os
import re
import time

from .config import load_config

GPU_FAULT_RE = re.compile(r"(CUDA driver|NVML|no CUDA-capable device|CUDA error: (?:unspecified launch failure|unknown error|"
                          r"an illegal memory access)|GPU is lost|Xid \d+|cudaErrorDevicesUnavailable|CUDA-capable device\(s\) is/are busy)", re.I)
OOM_RE = re.compile(r"CUDA out of memory|OutOfMemoryError|CUBLAS_STATUS_ALLOC_FAILED", re.I)
_gpu_cache = {"t": 0.0, "gpus": None}


# ------------------------------------------------------------------ hardware & policy
def _scan() -> dict:
    try:
        from .sysinfo import scan
        return scan()
    except Exception:
        return {}


def policy(cfg: dict | None = None, scan: dict | None = None) -> dict:
    cfg = cfg or load_config()
    rc = cfg["resources"]
    s = scan if scan is not None else _scan()
    g = (s.get("gpus") or [None])[0] or {}
    vram_total = (g.get("vram_total_mb") or 0) / 1024
    ram_total = (s.get("memory") or {}).get("total_gb") or 0
    threads = (s.get("cpu") or {}).get("cores") or os.cpu_count() or 4
    vram_safe = max(0.0, vram_total - 1.0) if vram_total else 0.0
    ram_cap = max(2.0, ram_total - max(12.0, ram_total * 0.375)) if ram_total else 8.0
    derived = {
        "vram_total_gb": round(vram_total, 1), "vram_safety_cap_gb": round(vram_safe, 1),
        "local_ai_vram_gb": round(min(8.0, vram_safe * 0.73), 1) if vram_safe else 0.0,
        "ram_total_gb": ram_total, "ram_safety_cap_gb": round(ram_cap, 1),
        "sandbox_memory_gb": int(max(2, min(16, ram_cap * 0.8))),
        "sandbox_cpus": int(max(1, min(6, round(threads * 0.375)))),
        "local_ai_threads": int(max(1, min(4, threads // 4))),
        "cpu_threads": threads, "cpu_load_cap_pct": 85, "disk_min_free_gb": 50,
        "gpu": g.get("name", ""),
    }
    out = dict(derived)
    src = {}
    for k in ("sandbox_memory_gb", "sandbox_cpus", "local_ai_vram_gb", "local_ai_threads"):
        v = rc.get(k) or 0
        src[k] = "override" if v else "detected"
        if v:
            out[k] = v
    out["source"] = src
    out["settings"] = {k: rc[k] for k in ("enforce_caps", "require_unload", "vram_free_target_mb", "unload_wait_s", "unload_timeout_s",
                                           "gpu_temp_limit_c", "cpu_fallback_on_gpu_fault", "gpu_busy_util_pct")}
    return out


def clamp_sandbox(settings: dict, cfg: dict | None = None) -> tuple[dict, list]:
    """Sandbox limits after the hard caps (0 = unlimited is replaced by the cap). Returns (settings, warnings)."""
    cfg = cfg or load_config()
    if not cfg["resources"].get("enforce_caps", True):
        return dict(settings), []
    p = policy(cfg)
    s, warn = dict(settings), []
    for key, cap in (("memory_gb", p["sandbox_memory_gb"]), ("cpus", p["sandbox_cpus"])):
        cur = s.get(key) or 0
        if not cur or cur > cap:
            if cur:
                warn.append(f"sandbox {key}={cur} exceeds the hardware policy — capped at {cap}")
            s[key] = cap
    return s, warn


# ------------------------------------------------------------------ live GPU state
def gpus(max_age: float = 1.5) -> list:
    if _gpu_cache["gpus"] is not None and time.time() - _gpu_cache["t"] < max_age:
        return _gpu_cache["gpus"]
    try:
        from .sysinfo import gpus as smi
        g = smi()
    except Exception:
        g = []
    _gpu_cache.update(t=time.time(), gpus=g)
    return g


def gpu_job_running() -> bool:
    try:
        from .sandbox import JOBS
        return any(j.status == "running" and j.kind == "run" and (j.meta.get("environment") or {}).get("gpu") for j in JOBS.values())
    except Exception:
        return False


def gpu_busy(cfg: dict | None = None) -> bool:
    """GPU should be left to training: a GPU sandbox run is active, or utilisation is above gpu_busy_util_pct."""
    if gpu_job_running():
        return True
    cfg = cfg or load_config()
    g = (gpus(5) or [None])[0]
    return bool(g and (g.get("util_pct") or 0) >= cfg["resources"].get("gpu_busy_util_pct", 80))


def ollama_cpu_options(cfg: dict | None = None) -> dict:
    p = policy(cfg)
    return {"num_gpu": 0, "num_thread": p["local_ai_threads"]}


def preflight_gpu(cfg: dict | None = None) -> dict:
    """Can a run use the GPU right now? {use_gpu, reason, gpu}."""
    cfg = cfg or load_config()
    g = (gpus(0) or [None])[0]
    if not g:
        return {"use_gpu": False, "reason": "no NVIDIA GPU / nvidia-smi not reachable", "gpu": None}
    limit = cfg["resources"].get("gpu_temp_limit_c", 83)
    if g.get("temp_c") is not None and g["temp_c"] >= limit:
        return {"use_gpu": False, "reason": f"GPU at {g['temp_c']:.0f} °C ≥ limit {limit} °C — running on CPU to protect the card", "gpu": g}
    return {"use_gpu": True, "reason": "", "gpu": g}


# ------------------------------------------------------------------ Strategy A: JIT VRAM unload
def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("called from a running event loop — use the async API")


def loaded_local_models(cfg: dict | None = None) -> dict:
    from . import local_ai
    cfg = cfg or load_config()
    out = {"ollama": [], "lmstudio": []}
    try:
        st = _run_async(local_ai.ollama_status(cfg["ollama_base_url"]))
        out["ollama"] = [m["id"] for m in st.get("loaded", []) if m.get("id")]
    except Exception:
        pass
    try:
        st = _run_async(local_ai.lmstudio_status(cfg["lmstudio_base_url"]))
        out["lmstudio"] = list(st.get("loaded", []))
    except Exception:
        pass
    try:  # REST v1 (LM Studio >= 0.4) lists loaded instances even where /api/v0 is missing — never miss a loaded model
        for key, _iid in _run_async(local_ai.lmstudio_loaded_instances(cfg["lmstudio_base_url"])):
            if key and key not in out["lmstudio"]:
                out["lmstudio"].append(key)
    except Exception:
        pass
    return out


def unload_local_models(cfg: dict | None = None, log=None) -> dict:
    """Unload every local LLM from VRAM and wait until VRAM is (almost) free. Never raises."""
    from . import local_ai
    cfg = cfg or load_config()
    rc = cfg["resources"]
    log = log or (lambda _m: None)
    rep = {"unloaded": [], "errors": [], "vram_before_mb": None, "vram_after_mb": None, "waited_s": 0.0, "lmstudio_method": ""}
    g = (gpus(0) or [None])[0]
    rep["vram_before_mb"] = g.get("vram_used_mb") if g else None
    models = loaded_local_models(cfg)
    for m in models["ollama"]:
        try:
            _run_async(local_ai.ollama_unload(cfg["ollama_base_url"], m))
            rep["unloaded"].append(f"ollama:{m}")
        except Exception as e:
            rep["errors"].append(f"ollama {m}: {e}")
    if models["lmstudio"]:
        try:
            r = _run_async(local_ai.lmstudio_unload(cfg["lmstudio_base_url"], ""))
            rep["unloaded"] += [f"lmstudio:{m}" for m in models["lmstudio"]]
            rep["lmstudio_method"] = r.get("method", "")  # rest-v1 | rest | lms (CLI, only as a last resort)
        except Exception as e:
            rep["errors"].append(f"lmstudio: {e}")
    if not rep["unloaded"]:
        return rep
    log(f"🧹 VRAM unload: {', '.join(rep['unloaded'])}")
    t0 = time.time()
    time.sleep(max(0.0, float(rc.get("unload_wait_s", 1.5))))
    target, deadline = rc.get("vram_free_target_mb", 2048), t0 + max(2, int(rc.get("unload_timeout_s", 20)))
    while True:
        g = (gpus(0) or [None])[0]
        used = g.get("vram_used_mb") if g else None
        if used is None or used <= target or time.time() >= deadline:
            break
        time.sleep(0.5)
    rep["vram_after_mb"], rep["waited_s"] = used, round(time.time() - t0, 1)
    if used is not None and used > target:
        log(f"⚠ VRAM still {used:.0f} MB after {rep['waited_s']} s (target ≤ {target} MB) — another program holds the GPU")
    else:
        log(f"✓ VRAM free: {used if used is not None else '?'} MB used after {rep['waited_s']} s")
    return rep


class VramBusy(Exception):
    """A GPU run was requested while local LLMs still occupy VRAM (the researcher must unload them first)."""

    def __init__(self, models: list, vram_used_mb=None):
        self.models, self.vram_used_mb = models, vram_used_mb
        used = f" ({vram_used_mb:.0f} MB VRAM in use)" if isinstance(vram_used_mb, (int, float)) else ""
        super().__init__(f"VRAM is held by local LLMs{used}: {', '.join(models)}. Press 🧹 Unload before a GPU training run, "
                         "or run this job on CPU.")


def vram_gate(cfg: dict | None = None) -> None:
    """Raise VramBusy when resources.require_unload is on and Ollama / LM Studio have a model loaded."""
    cfg = cfg or load_config()
    if not cfg["resources"].get("require_unload", True):
        return
    m = loaded_local_models(cfg)
    names = [f"ollama:{x}" for x in m["ollama"]] + [f"lmstudio:{x}" for x in m["lmstudio"]]
    if names:
        g = (gpus(0) or [None])[0]
        raise VramBusy(names, g.get("vram_used_mb") if g else None)


def prepare_gpu_run(settings: dict, log=None, cfg: dict | None = None) -> dict:
    """Called by the sandbox before a GPU run (after vram_gate): thermal/driver guard. Returns {use_gpu, env, notes}."""
    cfg = cfg or load_config()
    log = log or (lambda _m: None)
    if not settings.get("gpu"):
        return {"use_gpu": False, "env": {}, "notes": []}
    pf = preflight_gpu(cfg)
    if not pf["use_gpu"]:
        log("⚠ " + pf["reason"] + " → CPU (CUDA_VISIBLE_DEVICES='')")
        return {"use_gpu": False, "env": {"CUDA_VISIBLE_DEVICES": ""}, "notes": [pf["reason"]]}
    g = pf["gpu"] or {}
    log(f"✓ GPU free for training: {g.get('vram_used_mb') or 0:.0f}/{g.get('vram_total_mb') or 0:.0f} MB VRAM used, {g.get('temp_c')} °C")
    return {"use_gpu": True, "env": {}, "notes": []}


def classify_failure(stderr: str) -> str:
    """'' | 'gpu_fault' | 'gpu_oom' from the tail of a failed run's stderr."""
    if GPU_FAULT_RE.search(stderr or ""):
        return "gpu_fault"
    if OOM_RE.search(stderr or ""):
        return "gpu_oom"
    return ""
