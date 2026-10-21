"""SmartMultiRouter (v3.2) — LLM_UPDATE_PROMPT.md + HARDWARE_RESOURCE_CONSTRAINT.md Strategy B/C.

Used when an agent's engine mode is "auto". Every agent has a task kind (config.AGENT_TASK_KIND); each kind has an ordered
chain of engines (config.routing.chains overrides the defaults below). The router keeps only engines that can work now:
    cloud provider      has an API key (local gateways 9Router/OmniRoute: key optional) and the machine is online
    local gateway       9Router / OmniRoute answering on localhost
    ollama / local      server answering; while the GPU trains (resources.gpu_busy) LM Studio is skipped and Ollama runs
                        with num_gpu=0 (CPU offload) — and cloud engines are tried first (Strategy B)
    offline             only local engines remain (forced local Qwen, Strategy C)
llm.call_agent / stream_agent then try the candidates in order and fall through on errors (sequential fallback).

Tokens: "@cloud" = the default cloud provider, "@claude" = Anthropic when it has a key.
"""
from __future__ import annotations

import socket
import time
import hashlib
import json

import httpx

from backend.core.config import AGENT_TASK_KIND, PROVIDERS

DEFAULT_CHAINS = {
    "live_critic": ["groq", "ollama", "local", "ninerouter", "omniroute", "@cloud"],
    "extract":     ["ollama", "local", "ninerouter", "omniroute", "deepinfra", "openrouter", "@cloud"],
    "summarize":   ["ollama", "local", "ninerouter", "omniroute", "deepinfra", "@cloud"],
    "context":     ["ninerouter", "omniroute", "@cloud", "openrouter", "ollama", "local"],
    "code":        ["openrouter", "deepinfra", "@cloud", "ollama", "local"],
    "reasoning":   ["@claude", "@cloud", "openrouter", "deepinfra", "ollama", "local"],
    "writing":     ["@claude", "@cloud", "openrouter", "deepinfra", "ollama", "local"],
    "general":     ["@cloud", "openrouter", "ollama", "local"],
}
LOCAL = ("ollama", "local")
_cache: dict = {}


def _cached(key: str, ttl: float, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    v = fn()
    _cache[key] = (time.time(), v)
    return v


def online() -> bool:
    def probe():
        for host, port in (("1.1.1.1", 443), ("8.8.8.8", 53)):
            try:
                with socket.create_connection((host, port), timeout=1.5):
                    return True
            except OSError:
                continue
        return False
    return _cached("online", 30, probe)


def _reachable(url: str, headers: dict | None = None) -> bool:
    def probe():
        try:
            return 200 <= httpx.get(url, timeout=1.5, headers=headers).status_code < 300
        except httpx.HTTPError:
            return False
    fingerprint = hashlib.sha256(json.dumps(headers or {}, sort_keys=True).encode()).hexdigest()
    return _cached("reach:" + url + ":" + fingerprint, 20, probe)


def local_up(cfg: dict, engine: str) -> bool:
    from backend.providers.local import lms_root, ollama_root
    if engine == "ollama":
        return _reachable(ollama_root(cfg.get("ollama_base_url")) + "/api/tags")
    return _reachable(lms_root(cfg.get("lmstudio_base_url")) + "/v1/models")


def provider_ready(cfg: dict, pid: str, is_online: bool) -> bool:
    from backend.providers.models import LLMError, gateway_headers, key_required, provider_settings
    spec = PROVIDERS.get(pid)
    if not spec:
        return False
    try:
        _, key, model, base = provider_settings(cfg, pid)
    except LLMError:
        return False
    if not base or not model or (not key and key_required(spec, pid, base)):
        return False
    if spec.get("local_gateway") or (pid == "custom" and not key_required(spec, pid, base)):
        headers = gateway_headers(pid)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return _reachable(base + "/models", headers)
    return is_online


def chain_for(cfg: dict, agent: str) -> tuple[str, list]:
    kind = AGENT_TASK_KIND.get(agent) or ("reasoning" if agent.startswith("chat_") or agent.startswith("ext_") else "general")
    custom = (cfg.get("routing") or {}).get("chains") or {}
    return kind, list(custom.get(kind) or DEFAULT_CHAINS.get(kind) or DEFAULT_CHAINS["general"])


def plan(cfg: dict, agent: str) -> dict:
    """{kind, online, gpu_busy, candidates: [engine…], skipped: {engine: reason}} for an "auto" agent."""
    kind, chain = chain_for(cfg, agent)
    is_online = online() if (cfg.get("routing") or {}).get("online_check", True) else True
    try:
        from backend.execution.resources import gpu_busy
        busy = gpu_busy(cfg)
    except Exception:
        busy = False
    out, skipped = [], {}
    for tok in chain:
        eng = cfg["default_cloud"] if tok == "@cloud" else ("anthropic" if tok == "@claude" else tok)
        if eng in out or eng in skipped:
            continue
        if eng in LOCAL:
            policy = cfg.get("routing") or {}
            if policy.get("capability_aware", True) and kind not in policy.get("verified_local_tasks", ["extract", "summarize", "context", "live_critic"]):
                skipped[eng] = "task needs a verified reasoning provider; waiting for cloud or researcher selection"
            elif not local_up(cfg, eng):
                skipped[eng] = "server not running"
            elif busy and eng == "local":
                skipped[eng] = "GPU busy (LM Studio cannot offload to CPU per request)"
            else:
                out.append(eng)
        elif provider_ready(cfg, eng, is_online):
            out.append(eng)
        else:
            skipped[eng] = "offline" if not is_online and not PROVIDERS.get(eng, {}).get("local_gateway") else "no API key / not reachable"
    if busy:  # Strategy B: keep the GPU for training — cloud first, CPU-offloaded Ollama last
        out = [e for e in out if e not in LOCAL] + [e for e in out if e in LOCAL]
    policy = cfg.get("routing") or {}
    if policy.get("capability_aware", True) and kind in ("reasoning", "code", "writing") and out:
        verified = (policy.get("verified_fallbacks") or {}).get(kind) or []
        kept = [out[0]]  # configured primary; alternatives require explicit model-specific qualification
        for eng in out[1:]:
            model = cfg.get("ollama_model", "") if eng == "ollama" else cfg.get("local_model", "") if eng == "local" else (cfg.get("providers", {}).get(eng) or {}).get("model", "")
            if f"{eng}:{model}" in verified:
                kept.append(eng)
            else:
                skipped[eng] = "alternative model has not been qualified for this task in routing.verified_fallbacks"
        out = kept
    return {"agent": agent, "kind": kind, "online": is_online, "gpu_busy": busy, "candidates": out, "skipped": skipped}
