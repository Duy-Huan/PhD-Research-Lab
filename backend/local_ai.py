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
    b = (base_url or "http://localhost:1234/v1").rstrip("/")
    return b[:-3] if b.endswith("/v1") else b


def ollama_root(base_url: str) -> str:
    b = (base_url or "http://localhost:11434").rstrip("/")
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
async def lmstudio_status(base_url: str) -> dict:
    """{online, models:[{id, state, type, quantization, arch, max_context}], loaded:[ids], api:'v0'|'openai', cli}"""
    root = lms_root(base_url)
    out = {"online": False, "models": [], "loaded": [], "api": "", "cli": bool(lms_cli()), "root": root}
    async with httpx.AsyncClient(timeout=8) as c:
        try:
            r = await c.get(f"{root}/api/v0/models")
            if r.status_code == 200:
                data = r.json().get("data", [])
                out.update(online=True, api="v0")
                for m in data:
                    if m.get("type") == "embeddings":
                        continue
                    out["models"].append({"id": m.get("id"), "state": m.get("state", ""), "type": m.get("type", "llm"),
                                          "quantization": m.get("quantization", ""), "arch": m.get("arch", ""),
                                          "max_context": m.get("max_context_length")})
                out["loaded"] = [m["id"] for m in out["models"] if m["state"] == "loaded"]
                return out
        except httpx.HTTPError:
            pass
        try:
            r = await c.get(f"{root}/v1/models")
            r.raise_for_status()
            ids = [m.get("id") for m in r.json().get("data", []) if m.get("id")]
            out.update(online=True, api="openai", models=[{"id": i, "state": "unknown"} for i in ids], loaded=[])
        except httpx.HTTPError as e:
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


async def lmstudio_unload(base_url: str, model: str = "") -> dict:
    root = lms_root(base_url)
    async with httpx.AsyncClient(timeout=60) as c:
        try:
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
    raise LocalAIError("This LM Studio version cannot unload through its API — eject the model in the LM Studio window "
                       "(or install the `lms` CLI).")


# ------------------------------------------------------------------ Ollama
async def ollama_status(base_url: str) -> dict:
    root = ollama_root(base_url)
    out = {"online": False, "models": [], "loaded": [], "root": root}
    async with httpx.AsyncClient(timeout=8) as c:
        try:
            r = await c.get(f"{root}/api/tags")
            r.raise_for_status()
            out["online"] = True
            for m in r.json().get("models", []):
                d = m.get("details") or {}
                out["models"].append({"id": m.get("name") or m.get("model"), "size": m.get("size"),
                                      "params": d.get("parameter_size", ""), "quantization": d.get("quantization_level", ""),
                                      "family": d.get("family", "")})
            try:
                r2 = await c.get(f"{root}/api/ps")
                for m in r2.json().get("models", []):
                    out["loaded"].append({"id": m.get("name") or m.get("model"), "size": m.get("size"),
                                          "size_vram": m.get("size_vram"), "expires_at": m.get("expires_at")})
            except Exception:
                pass
        except httpx.HTTPError as e:
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


async def ollama_pull(base_url: str, model: str):
    """Async generator of progress dicts {status, completed, total}."""
    root = ollama_root(base_url)
    async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=8)) as c:
        async with c.stream("POST", f"{root}/api/pull", json={"model": model, "stream": True}) as r:
            if r.status_code >= 300:
                await r.aread()
                raise LocalAIError(f"Ollama pull failed: {r.text[:300]}")
            async for line in r.aiter_lines():
                if line.strip():
                    try:
                        yield json.loads(line)
                    except ValueError:
                        continue


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
