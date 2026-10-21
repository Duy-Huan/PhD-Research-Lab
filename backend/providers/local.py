"""Local model servers (v3.0): LM Studio and Ollama — list, load, unload, status, pull.

LM Studio
  • OpenAI-compatible API at <base>/v1 (chat), model list at /v1/models
  • REST API at /api/v0/models (LM Studio ≥ 0.3.6): every downloaded model with state loaded / not-loaded
  • Loading: REST /api/v1/models/load (newer LM Studio) → `lms load` CLI → just-in-time load via a 1-token request
Ollama
  • /api/tags (downloaded), /api/ps (loaded, with VRAM), /api/generate with keep_alive to load/unload, /api/pull
  • OpenAI-compatible chat at <base>/v1
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys

import httpx

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class LocalAIError(Exception):
    pass


def lms_root(base_url: str) -> str:
    """'http://localhost:1234/v1' → 'http://localhost:1234'."""
    b = (base_url or "http://localhost:1234/v1").strip().rstrip("/")
    return b[:-3] if b.endswith("/v1") else b


def ollama_root(base_url: str) -> str:
    b = (base_url or "http://localhost:11434").strip().rstrip("/")
    return b[:-3] if b.endswith("/v1") else b


def lms_cli() -> str | None:
    p = shutil.which("lms")
    if p:
        return p
    home = os.path.expanduser("~")
    for c in (os.path.join(home, ".lmstudio", "bin", "lms.exe" if sys.platform.startswith("win") else "lms"),
              os.path.join(home, ".cache", "lm-studio", "bin", "lms")):
        if os.path.isfile(c):
            return c
    return None


# ------------------------------------------------------------------ LM Studio
def _model_list(response: httpx.Response, key: str) -> list:
    data = response.json()
    models = data.get(key) if isinstance(data, dict) else None
    if not isinstance(models, list):
        raise ValueError("server returned an unexpected model list")
    return [m for m in models if isinstance(m, dict)]


async def lmstudio_status(base_url: str) -> dict:
    """{online, models:[{id, state, type, quantization, arch, max_context}], loaded:[ids], api:'v0'|'openai', cli}"""
    root = lms_root(base_url)
    out = {"online": False, "models": [], "loaded": [], "api": "", "cli": bool(lms_cli()), "root": root}
    async with httpx.AsyncClient(timeout=8) as c:
        try:
            r = await c.get(f"{root}/api/v0/models")
            if r.status_code == 200:
                data = _model_list(r, "data")
                out.update(online=True, api="v0")
                for m in data:
                    if m.get("type") in ("embedding", "embeddings") or not m.get("id"):
                        continue
                    out["models"].append({"id": m.get("id"), "state": m.get("state", ""), "type": m.get("type", "llm"),
                                          "quantization": m.get("quantization", ""), "arch": m.get("arch", ""),
                                          "max_context": m.get("max_context_length")})
                out["loaded"] = [m["id"] for m in out["models"] if m["state"] == "loaded"]
                return out
        except (httpx.HTTPError, ValueError):
            pass
        try:
            r = await c.get(f"{root}/v1/models")
            r.raise_for_status()
            ids = [m.get("id") for m in _model_list(r, "data") if m.get("id")]
            out.update(online=True, api="openai", models=[{"id": i, "state": "unknown"} for i in ids], loaded=[])
        except (httpx.HTTPError, ValueError) as e:
            out["error"] = f"LM Studio not reachable at {root} ({type(e).__name__}). Open LM Studio → Developer → Start Server."
    return out


def _run_cli(args: list, timeout: int = 300) -> tuple[int, str]:
    r = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


async def lmstudio_load(base_url: str, model: str, context_length: int | None = None) -> dict:
    root = lms_root(base_url)
    tried = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=8)) as c:
        body = {"model": model}
        if context_length:
            body["context_length"] = int(context_length)
        try:  # newer LM Studio REST API
            r = await c.post(f"{root}/api/v1/models/load", json=body)
            if r.status_code < 300:
                return {"ok": True, "method": "rest", "model": model}
            tried.append(f"REST {r.status_code}")
        except httpx.HTTPError as e:
            tried.append(f"REST {type(e).__name__}")
    cli = lms_cli()
    if cli:
        args = [cli, "load", model, "-y"] + (["--context-length", str(context_length)] if context_length else [])
        try:
            code, out = await asyncio.to_thread(_run_cli, args)
            if code == 0:
                return {"ok": True, "method": "lms", "model": model, "output": out[-400:]}
            tried.append(f"lms exit {code}: {out.strip()[-200:]}")
        except Exception as e:
            tried.append(f"lms {type(e).__name__}")
    async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=8)) as c:
        try:  # just-in-time loading: LM Studio loads a model when a request names it
            r = await c.post(f"{root}/v1/chat/completions", json={"model": model, "max_tokens": 1,
                                                                  "messages": [{"role": "user", "content": "ping"}]})
            if r.status_code == 200:
                return {"ok": True, "method": "jit", "model": model}
            tried.append(f"JIT {r.status_code}: {r.text[:200]}")
        except httpx.HTTPError as e:
            tried.append(f"JIT {type(e).__name__}")
    raise LocalAIError("Could not load the model (" + "; ".join(tried) + "). In LM Studio: Developer → enable "
                       "'Just-in-Time model loading', or install the `lms` CLI, or load the model in the LM Studio window.")


async def lmstudio_loaded_instances(base_url: str) -> list:
    """[(model key, instance id)] from the REST v1 API (LM Studio ≥ 0.4: GET /api/v1/models → loaded_instances)."""
    root = lms_root(base_url)
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.get(f"{root}/api/v1/models")
    r.raise_for_status()
    out = []
    for m in r.json().get("models", []):
        for inst in m.get("loaded_instances") or []:
            if inst.get("id"):
                out.append((m.get("key", ""), inst["id"]))
    return out


async def lmstudio_unload(base_url: str, model: str = "") -> dict:
    root = lms_root(base_url)
    tried = []
    try:  # REST v1: one call per loaded instance (the endpoint requires instance_id)
        inst = [i for k, i in await lmstudio_loaded_instances(base_url) if not model or model in (k, i)]
        async with httpx.AsyncClient(timeout=120) as c:
            done = []
            for iid in inst:
                r = await c.post(f"{root}/api/v1/models/unload", json={"instance_id": iid})
                if r.status_code < 300:
                    done.append(iid)
                else:
                    tried.append(f"REST {r.status_code} for {iid}")
        if len(done) == len(inst):  # also when nothing (matching) is loaded: there is nothing to unload
            return {"ok": True, "method": "rest-v1", "unloaded": done}
    except (httpx.HTTPError, ValueError) as e:
        tried.append(f"REST v1 {type(e).__name__}")
    async with httpx.AsyncClient(timeout=60) as c:
        try:  # older builds that accepted {"all": true} / {"model": …}
            r = await c.post(f"{root}/api/v1/models/unload", json={"model": model} if model else {"all": True})
            if r.status_code < 300:
                return {"ok": True, "method": "rest"}
        except httpx.HTTPError:
            pass
    cli = lms_cli()
    if cli:
        code, out = await asyncio.to_thread(_run_cli, [cli, "unload", model] if model else [cli, "unload", "--all"], 120)
        if code == 0:
            return {"ok": True, "method": "lms"}
        raise LocalAIError(f"lms unload failed: {out.strip()[-300:]}")
    raise LocalAIError("Could not unload LM Studio models (" + ("; ".join(tried) or "no API answered") + ") — eject the model "
                       "in the LM Studio window (or install the `lms` CLI).")


# ------------------------------------------------------------------ Ollama
async def ollama_status(base_url: str) -> dict:
    root = ollama_root(base_url)
    out = {"online": False, "models": [], "loaded": [], "root": root}
    async with httpx.AsyncClient(timeout=8) as c:
        try:
            r = await c.get(f"{root}/api/tags")
            r.raise_for_status()
            models = _model_list(r, "models")
            out["online"] = True
            for m in models:
                if not (m.get("name") or m.get("model")):
                    continue
                d = m.get("details") or {}
                out["models"].append({"id": m.get("name") or m.get("model"), "size": m.get("size"),
                                      "params": d.get("parameter_size", ""), "quantization": d.get("quantization_level", ""),
                                      "family": d.get("family", "")})
            try:
                r2 = await c.get(f"{root}/api/ps")
                r2.raise_for_status()
                for m in _model_list(r2, "models"):
                    out["loaded"].append({"id": m.get("name") or m.get("model"), "size": m.get("size"),
                                          "size_vram": m.get("size_vram"), "expires_at": m.get("expires_at")})
            except Exception:
                pass
        except (httpx.HTTPError, ValueError) as e:
            out["error"] = f"Ollama not reachable at {root} ({type(e).__name__}). Start Ollama (ollama serve)."
    return out


async def ollama_load(base_url: str, model: str, keep_alive: str = "30m") -> dict:
    root = ollama_root(base_url)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=8)) as c:
            r = await c.post(f"{root}/api/generate", json={"model": model, "keep_alive": keep_alive, "stream": False})
    except httpx.HTTPError as e:
        raise LocalAIError(f"Ollama not reachable: {e}")
    if r.status_code >= 300:
        raise LocalAIError(f"Ollama could not load {model}: {r.text[:300]}")
    return {"ok": True, "model": model}


async def ollama_unload(base_url: str, model: str) -> dict:
    root = ollama_root(base_url)
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{root}/api/generate", json={"model": model, "keep_alive": 0, "stream": False})
    if r.status_code >= 300:
        raise LocalAIError(f"Ollama could not unload {model}: {r.text[:300]}")
    return {"ok": True}


async def first_model(engine: str, cfg: dict) -> str | None:
    """Model to use when none is configured: the loaded one (or the first available)."""
    if engine == "ollama":
        st = await ollama_status(cfg.get("ollama_base_url"))
        if st["loaded"]:
            return st["loaded"][0]["id"]
        return st["models"][0]["id"] if st["models"] else None
    st = await lmstudio_status(cfg.get("lmstudio_base_url"))
    if st["loaded"]:
        return st["loaded"][0]
    return st["models"][0]["id"] if st["models"] else None
