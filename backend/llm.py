"""Hybrid LLM router: many cloud providers (Anthropic native + OpenAI-compatible APIs) and LM Studio."""
from __future__ import annotations

import json
import re

import httpx

from .config import PROVIDERS, load_config

ANTHROPIC_VERSION = "2023-06-01"
TIMEOUT = httpx.Timeout(900, connect=20)


class LLMError(Exception):
    pass


def _err_msg(r: httpx.Response) -> str:
    try:
        j = r.json()
        e = j.get("error", j) if isinstance(j, dict) else j
        if isinstance(e, dict):
            return str(e.get("message") or e)
        if isinstance(j, list) and j and isinstance(j[0], dict):  # Gemini style
            return str(j[0].get("error", {}).get("message", j))
        return str(e)
    except Exception:
        return r.text[:600]


# --------------------------------------------------------------------- multimodal message conversion
def to_anthropic(messages: list) -> list:
    out = []
    for m in messages:
        imgs = m.get("images") or []
        if m["role"] == "user" and imgs:
            content = [{"type": "image", "source": {"type": "base64", "media_type": i["media_type"], "data": i["data"]}}
                       for i in imgs] + [{"type": "text", "text": m["content"] or "(see attached images)"}]
            out.append({"role": "user", "content": content})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def to_openai(messages: list) -> list:
    out = []
    for m in messages:
        imgs = m.get("images") or []
        if m["role"] == "user" and imgs:
            content = [{"type": "text", "text": m["content"] or "(see attached images)"}] + [
                {"type": "image_url", "image_url": {"url": f"data:{i['media_type']};base64,{i['data']}"}} for i in imgs]
            out.append({"role": "user", "content": content})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def strip_think(text: str) -> str:
    """Remove <think>…</think> reasoning (and an unfinished <think> block) from model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return re.sub(r"<think>.*\Z", "", text, flags=re.S)


# --------------------------------------------------------------------- Anthropic native
async def anthropic_chat(base: str, key: str, model: str, system: str, messages: list, max_tokens: int) -> str:
    headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    body = {"model": model, "max_tokens": max_tokens, "system": system, "messages": to_anthropic(messages)}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.post(f"{base}/messages", headers=headers, json=body)
    except httpx.HTTPError as e:
        raise LLMError(f"Network error contacting Anthropic: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"Anthropic error {r.status_code}: {_err_msg(r)}")
    try:
        data = r.json()
    except ValueError:
        raise LLMError(f"Anthropic returned a non-JSON response (check the base URL): {r.text[:200]}")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if data.get("stop_reason") == "max_tokens":
        text += "\n\n% [WARNING: output truncated at max_tokens]"
    return text


# --------------------------------------------------------------------- OpenAI-compatible
async def openai_compat_chat(base: str, key: str, model: str, system: str, messages: list, max_tokens: int,
                             temperature: float | None, label: str, pid: str = "", connect_hint: str = "") -> str:
    body = {"model": model, "messages": [{"role": "system", "content": system}] + to_openai(messages),
            "max_tokens": max_tokens, "stream": False}
    if temperature is not None:
        body["temperature"] = temperature
    if pid == "openai":  # GPT-5 / o-series: max_completion_tokens, default temperature only
        body["max_completion_tokens"] = body.pop("max_tokens")
        body.pop("temperature", None)
    headers = {"Content-Type": "application/json", **gateway_headers(pid)}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if pid == "openrouter":
        headers["X-Title"] = "PhD Research Lab"
    r = None
    for _ in range(3):  # adapt to provider-specific parameter rules
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as c:
                r = await c.post(f"{base}/chat/completions", headers=headers, json=body)
        except httpx.ConnectError as e:
            raise LLMError(f"Cannot reach {label} at {base}. {connect_hint}".strip()) from e
        except httpx.HTTPError as e:
            raise LLMError(f"{label} request failed: {e}") from e
        if r.status_code == 400:
            t = r.text.lower()
            if "max_tokens" in t and "max_tokens" in body:
                body["max_completion_tokens"] = body.pop("max_tokens")
                continue
            if "temperature" in t and "temperature" in body:
                body.pop("temperature")
                continue
        break
    if r.status_code != 200:
        raise LLMError(f"{label} error {r.status_code}: {_err_msg(r)}")
    try:
        data = r.json()
    except ValueError:
        raise LLMError(f"{label} returned a non-JSON response (check the base URL): {r.text[:200]}")
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"{label} returned an unexpected response: {str(data)[:300]}")
    content = msg.get("content") or ""
    if isinstance(content, list):  # some providers return content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    content = strip_think(content).strip()
    if data["choices"][0].get("finish_reason") == "length":
        content += "\n\n% [WARNING: output truncated at max_tokens]"
    return content


# --------------------------------------------------------------------- providers
def provider_settings(cfg: dict, pid: str) -> tuple[dict, str, str, str]:
    if pid not in PROVIDERS:
        raise LLMError(f"Unknown provider '{pid}'")
    spec, p = PROVIDERS[pid], cfg["providers"][pid]
    base = (p.get("base_url") or spec["base_url"]).rstrip("/")
    return spec, p.get("api_key", ""), (p.get("model") or spec["model"]), base


HEADER_NAME_RE = re.compile(r"^X-[A-Za-z0-9-]{1,60}$")


def gateway_headers(pid: str) -> dict:
    """v3.2: optional extra headers for a provider (config.routing.provider_headers), e.g. 9Router "X-9Router-Skills".
    Only X-… names are accepted, so a typo can never inject Authorization/Cookie or identity headers into a request."""
    try:
        hs = (load_config().get("routing") or {}).get("provider_headers", {}).get(pid) or {}
    except Exception:
        return {}
    return {k: str(v)[:200] for k, v in hs.items() if HEADER_NAME_RE.match(str(k)) and "\n" not in str(v)}


async def cloud_chat(cfg: dict, pid: str, system: str, messages: list, max_tokens: int,
                     temperature: float | None = None, model: str | None = None) -> str:
    spec, key, default_model, base = provider_settings(cfg, pid)
    model = model or default_model
    if not key and not spec.get("key_optional"):
        raise LLMError(f"No API key for {spec['label']}. Add it in Configuration → Cloud AI providers.")
    if not base:
        raise LLMError(f"{spec['label']}: base URL is empty.")
    if not model:
        raise LLMError(f"{spec['label']}: no model selected.")
    if spec["kind"] == "anthropic":
        return await anthropic_chat(base, key, model, system, messages, max_tokens)
    return await openai_compat_chat(base, key, model, system, messages, max_tokens, temperature, spec["label"], pid)


async def list_provider_models(cfg: dict, pid: str) -> list:
    spec, key, _, base = provider_settings(cfg, pid)
    if not key:
        raise LLMError(f"Enter and save the {spec['label']} API key first.")
    headers = ({"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION} if spec["kind"] == "anthropic"
               else {"Authorization": f"Bearer {key}"})
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{base}/models", headers=headers, params={"limit": 200} if spec["kind"] == "anthropic" else None)
    except httpx.HTTPError as e:
        raise LLMError(f"{spec['label']}: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"{spec['label']} cannot list models ({r.status_code}): {_err_msg(r)}")
    data = r.json()
    items = data.get("data", data.get("models", [])) if isinstance(data, dict) else data
    ids = [(m.get("id") or m.get("name") or "") if isinstance(m, dict) else str(m) for m in items]
    return sorted({i.removeprefix("models/") for i in ids if i})


# --------------------------------------------------------------------- local (LM Studio)
LMSTUDIO_HINT = "In LM Studio open the Developer tab, load a model and click 'Start Server'."


async def list_local_models(base_url: str) -> list:
    base = base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{base}/models")
        r.raise_for_status()
        return [m.get("id") for m in r.json().get("data", []) if m.get("id")]
    except Exception as e:
        raise LLMError(f"Cannot reach LM Studio at {base}. {LMSTUDIO_HINT} ({e})") from e


OLLAMA_HINT = "Start Ollama (it runs in the system tray, or `ollama serve`) and pull a model, e.g. `ollama pull qwen2.5-coder:14b`."
LOCAL_ENGINES = ("local", "ollama")


async def local_target(cfg: dict, engine: str, model: str | None = None) -> tuple[str, str, str, str]:
    """(base_url_v1, model, label, hint) for LM Studio ('local') or Ollama."""
    from .local_ai import first_model, ollama_root
    if engine == "ollama":
        base = ollama_root(cfg.get("ollama_base_url")) + "/v1"
        model = model or cfg.get("ollama_model") or await first_model("ollama", cfg)
        if not model:
            raise LLMError("Ollama has no model. " + OLLAMA_HINT)
        return base, model, "Ollama", OLLAMA_HINT
    base = cfg["lmstudio_base_url"].rstrip("/")
    model = model or cfg.get("local_model")
    if not model:
        try:
            model = await first_model("local", cfg)
        except Exception:
            model = None
        if not model:
            models = await list_local_models(base)
            if not models:
                raise LLMError("LM Studio is running but no model is loaded.")
            model = models[0]
    return base, model, "LM Studio", LMSTUDIO_HINT


def ollama_offload_options(cfg: dict) -> dict | None:
    """v3.2 Strategy C: while the GPU trains, Ollama answers from CPU/RAM (num_gpu=0, limited threads)."""
    try:
        from .resources import gpu_busy, ollama_cpu_options
        return ollama_cpu_options(cfg) if gpu_busy(cfg) else None
    except Exception:
        return None


def _ollama_messages(system: str, messages: list) -> list:
    out = [{"role": "system", "content": system}]
    for m in messages:
        d = {"role": m["role"], "content": m.get("content") or ""}
        if m.get("images"):
            d["images"] = [i["data"] for i in m["images"]]
        out.append(d)
    return out


async def ollama_native_chat(cfg: dict, system: str, messages: list, max_tokens: int, temperature: float,
                             model: str | None, options: dict) -> str:
    """Ollama /api/chat (native API: accepts `options`, unlike its OpenAI-compatible endpoint)."""
    from .local_ai import ollama_root
    _, model, label, hint = await local_target(cfg, "ollama", model)
    body = {"model": model, "messages": _ollama_messages(system, messages), "stream": False,
            "options": {**options, "num_predict": max_tokens, "temperature": temperature}}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.post(ollama_root(cfg.get("ollama_base_url")) + "/api/chat", json=body)
    except httpx.ConnectError as e:
        raise LLMError(f"Cannot reach Ollama. {hint}") from e
    except httpx.HTTPError as e:
        raise LLMError(f"Ollama request failed: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"Ollama error {r.status_code}: {_err_msg(r)}")
    d = r.json()
    text = strip_think((d.get("message") or {}).get("content") or "").strip()
    if d.get("done_reason") == "length":
        text += "\n\n% [WARNING: output truncated at max_tokens]"
    return text


async def _stream_ollama_native(cfg, system, messages, max_tokens, temperature, model, options):
    from .local_ai import ollama_root
    _, model, label, hint = await local_target(cfg, "ollama", model)
    body = {"model": model, "messages": _ollama_messages(system, messages), "stream": True,
            "options": {**options, "num_predict": max_tokens, "temperature": temperature}}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            async with c.stream("POST", ollama_root(cfg.get("ollama_base_url")) + "/api/chat", json=body) as r:
                if r.status_code != 200:
                    await r.aread()
                    raise LLMError(f"Ollama error {r.status_code}: {_err_msg(r)}")
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    if d.get("error"):
                        raise LLMError(f"Ollama: {d['error']}")
                    piece = (d.get("message") or {}).get("content")
                    if piece:
                        yield piece
                    if d.get("done") and d.get("done_reason") == "length":
                        yield "\n\n% [WARNING: output truncated at max_tokens]"
    except httpx.ConnectError as e:
        raise LLMError(f"Cannot reach Ollama. {hint}") from e
    except httpx.HTTPError as e:
        raise LLMError(f"Ollama request failed: {e}") from e


async def local_chat(cfg: dict, system: str, messages: list, max_tokens: int, temperature: float,
                     engine: str = "local", model: str | None = None) -> str:
    if engine == "ollama":
        opts = ollama_offload_options(cfg)
        if opts:
            return await ollama_native_chat(cfg, system, messages, max_tokens, temperature, model, opts)
    base, model, label, hint = await local_target(cfg, engine, model)
    return await openai_compat_chat(base, "", model, system, messages, max_tokens, temperature, label, engine, hint)


# --------------------------------------------------------------------- router
def resolve_engine(cfg: dict, agent: str) -> str:
    mode = cfg["agent_modes"].get(agent, "cloud")
    if mode == "claude":  # Claude preferred: Anthropic when it has a key, otherwise the default cloud provider
        return "anthropic" if (cfg["providers"].get("anthropic") or {}).get("api_key") else cfg["default_cloud"]
    return cfg["default_cloud"] if mode == "cloud" else mode


def resolve_model(cfg: dict, agent: str) -> str | None:
    """Per-agent model override (v3); None = the engine's default model."""
    return (cfg.get("agent_models") or {}).get(agent) or None


def engine_label(engine: str) -> str:
    if engine == "local":
        return "LM Studio (local)"
    if engine == "ollama":
        return "Ollama (local)"
    return PROVIDERS.get(engine, {}).get("label", engine)


def default_model_for(cfg: dict, engine: str) -> str:
    if engine == "local":
        return cfg.get("local_model") or ""
    if engine == "ollama":
        return cfg.get("ollama_model") or ""
    if engine in PROVIDERS:
        return cfg["providers"][engine].get("model") or PROVIDERS[engine]["model"]
    return ""


def agent_runtime(cfg: dict, agent: str) -> dict:
    """What an agent will use right now: {engine, engine_label, model} — shown in every chat header."""
    eng = resolve_engine(cfg, agent)
    if eng == "auto":
        from .llm_router import plan
        p = plan(cfg, agent)
        first = (p["candidates"] or [""])[0]
        return {"agent": agent, "mode": "auto", "engine": first or "none", "kind": p["kind"],
                "engine_label": ("auto → " + engine_label(first)) if first else "auto → (no engine available)",
                "model": default_model_for(cfg, first) or "(auto)", "override": False, "candidates": p["candidates"],
                "gpu_busy": p["gpu_busy"], "online": p["online"]}
    return {"agent": agent, "mode": cfg["agent_modes"].get(agent, "cloud"), "engine": eng, "engine_label": engine_label(eng),
            "model": resolve_model(cfg, agent) or default_model_for(cfg, eng) or "(auto)",
            "override": bool(resolve_model(cfg, agent))}


async def call_agent(agent: str, system: str, user: str | None = None, messages: list | None = None,
                     max_tokens: int = 4096, temperature: float = 0.2) -> dict:
    """Run an agent on its configured engine/model. Returns {text, engine, engine_label, model, note}."""
    cfg = load_config()
    engine = resolve_engine(cfg, agent)
    model = resolve_model(cfg, agent)
    msgs = messages or [{"role": "user", "content": user or ""}]
    if engine == "auto":
        return await _call_auto(cfg, agent, system, msgs, max_tokens, temperature)
    if engine not in LOCAL_ENGINES:
        text = await cloud_chat(cfg, engine, system, msgs, max_tokens, temperature, model)
        return {"text": text, "engine": engine, "engine_label": engine_label(engine), "model": model or default_model_for(cfg, engine), "note": ""}
    try:
        text = await local_chat(cfg, system, msgs, max_tokens, temperature, engine, model)
        return {"text": text, "engine": engine, "engine_label": engine_label(engine), "model": model or default_model_for(cfg, engine), "note": ""}
    except LLMError as e:
        fb = cfg["default_cloud"]
        if cfg.get("fallback_to_cloud") and cfg["providers"][fb].get("api_key"):
            text = await cloud_chat(cfg, fb, system, msgs, max_tokens, temperature)
            return {"text": text, "engine": fb, "engine_label": engine_label(fb), "model": default_model_for(cfg, fb),
                    "note": f"Local model unavailable, fell back to {engine_label(fb)}: {e}"}
        raise


async def _auto_plan(cfg: dict, agent: str) -> dict:
    import asyncio
    from .llm_router import plan
    p = await asyncio.to_thread(plan, cfg, agent)
    if not p["candidates"]:
        why = "; ".join(f"{k}: {v}" for k, v in p["skipped"].items())
        raise LLMError(f"Auto routing ({p['kind']}): no engine is available right now ({why}). Add an API key, start "
                       "Ollama/LM Studio, or choose a fixed engine for this agent.")
    return p


def _auto_note(p: dict, eng: str, errors: list) -> str:
    bits = [f"auto routing ({p['kind']}{', GPU busy' if p['gpu_busy'] else ''}{', offline' if not p['online'] else ''}) → {engine_label(eng)}"]
    if errors:
        bits.append("fell back after: " + "; ".join(errors))
    return " · ".join(bits)


async def _call_auto(cfg: dict, agent: str, system: str, msgs: list, max_tokens: int, temperature: float) -> dict:
    """SmartMultiRouter: try the planned engines in order (sequential fallback on any error)."""
    p = await _auto_plan(cfg, agent)
    errors = []
    for eng in p["candidates"][:4]:
        try:
            if eng in LOCAL_ENGINES:
                text = await local_chat(cfg, system, msgs, max_tokens, temperature, eng)
            else:
                text = await cloud_chat(cfg, eng, system, msgs, max_tokens, temperature)
            return {"text": text, "engine": eng, "engine_label": engine_label(eng), "model": default_model_for(cfg, eng),
                    "note": _auto_note(p, eng, errors) if errors else ""}
        except LLMError as e:
            errors.append(f"{engine_label(eng)}: {str(e)[:160]}")
    raise LLMError("Auto routing: every engine failed — " + " | ".join(errors))


# --------------------------------------------------------------------- streaming
def _sse_lines_to_json(line: str):
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        return json.loads(payload)
    except ValueError:
        return None


async def _stream_anthropic(base, key, model, system, messages, max_tokens):
    headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    body = {"model": model, "max_tokens": max_tokens, "system": system, "messages": to_anthropic(messages), "stream": True}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            async with c.stream("POST", f"{base}/messages", headers=headers, json=body) as r:
                if r.status_code != 200:
                    await r.aread()
                    raise LLMError(f"Anthropic error {r.status_code}: {_err_msg(r)}")
                async for line in r.aiter_lines():
                    d = _sse_lines_to_json(line)
                    if not d:
                        continue
                    t = d.get("type")
                    if t == "content_block_delta" and d.get("delta", {}).get("type") == "text_delta":
                        yield d["delta"]["text"]
                    elif t == "message_delta" and d.get("delta", {}).get("stop_reason") == "max_tokens":
                        yield "\n\n% [WARNING: output truncated at max_tokens]"
                    elif t == "error":
                        raise LLMError(f"Anthropic stream error: {d.get('error', {}).get('message', d)}")
    except httpx.HTTPError as e:
        raise LLMError(f"Network error contacting Anthropic: {e}") from e


async def _stream_openai(base, key, model, system, messages, max_tokens, temperature, label, pid="", connect_hint=""):
    body = {"model": model, "messages": [{"role": "system", "content": system}] + to_openai(messages),
            "max_tokens": max_tokens, "stream": True}
    if temperature is not None:
        body["temperature"] = temperature
    if pid == "openai":
        body["max_completion_tokens"] = body.pop("max_tokens")
        body.pop("temperature", None)
    headers = {"Content-Type": "application/json", **gateway_headers(pid)}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if pid == "openrouter":
        headers["X-Title"] = "PhD Research Lab"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            for _ in range(3):
                async with c.stream("POST", f"{base}/chat/completions", headers=headers, json=body) as r:
                    if r.status_code == 400:
                        await r.aread()
                        t = r.text.lower()
                        if "max_tokens" in t and "max_tokens" in body:
                            body["max_completion_tokens"] = body.pop("max_tokens")
                            continue
                        if "temperature" in t and "temperature" in body:
                            body.pop("temperature")
                            continue
                    if r.status_code != 200:
                        await r.aread()
                        raise LLMError(f"{label} error {r.status_code}: {_err_msg(r)}")
                    async for line in r.aiter_lines():
                        d = _sse_lines_to_json(line)
                        if not d or not d.get("choices"):
                            continue
                        ch = d["choices"][0]
                        delta = (ch.get("delta") or {}).get("content")
                        if isinstance(delta, list):
                            delta = "".join(p.get("text", "") for p in delta if isinstance(p, dict))
                        if delta:
                            yield delta
                        if ch.get("finish_reason") == "length":
                            yield "\n\n% [WARNING: output truncated at max_tokens]"
                    return
    except httpx.ConnectError as e:
        raise LLMError(f"Cannot reach {label} at {base}. {connect_hint}".strip()) from e
    except httpx.HTTPError as e:
        raise LLMError(f"{label} request failed: {e}") from e


async def _stream_engine(cfg, engine, system, messages, max_tokens, temperature, model=None):
    if engine == "ollama":
        opts = ollama_offload_options(cfg)
        if opts:
            async for t in _stream_ollama_native(cfg, system, messages, max_tokens, temperature, model, opts):
                yield t
            return
    if engine in LOCAL_ENGINES:
        base, model, label, hint = await local_target(cfg, engine, model)
        async for t in _stream_openai(base, "", model, system, messages, max_tokens, temperature, label, engine, hint):
            yield t
        return
    spec, key, default_model, base = provider_settings(cfg, engine)
    model = model or default_model
    if not key and not spec.get("key_optional"):
        raise LLMError(f"No API key for {spec['label']}. Add it in Configuration → Cloud AI providers.")
    if spec["kind"] == "anthropic":
        async for t in _stream_anthropic(base, key, model, system, messages, max_tokens):
            yield t
    else:
        async for t in _stream_openai(base, key, model, system, messages, max_tokens, temperature, spec["label"], engine):
            yield t


async def stream_agent(agent: str, system: str, messages: list, max_tokens: int = 4096, temperature: float = 0.3):
    """Async generator: yields ("delta", text) chunks (reasoning <think> blocks hidden), then ("meta", {...})."""
    cfg = load_config()
    engine = resolve_engine(cfg, agent)
    model = resolve_model(cfg, agent)
    note, raw, emitted = "", "", 0

    async def run(eng, mdl):
        nonlocal raw, emitted
        async for chunk in _stream_engine(cfg, eng, system, messages, max_tokens, temperature, mdl):
            raw += chunk
            visible = strip_think(raw)
            if len(visible) > emitted and visible.startswith(visible[:emitted]):
                yield visible[emitted:]
                emitted = len(visible)

    if engine == "auto":
        p = await _auto_plan(cfg, agent)
        errors = []
        for eng in p["candidates"][:4]:
            try:
                async for piece in run(eng, None):
                    yield ("delta", piece)
                engine, model = eng, None
                break
            except LLMError as e:
                if raw:  # failed mid-answer: do not splice two models' text together
                    raise
                errors.append(f"{engine_label(eng)}: {str(e)[:160]}")
        else:
            raise LLMError("Auto routing: every engine failed — " + " | ".join(errors))
        note = _auto_note(p, engine, errors) if errors else ""
        yield ("meta", {"engine": engine, "engine_label": engine_label(engine), "note": note,
                        "model": default_model_for(cfg, engine), "text": strip_think(raw).strip()})
        return
    try:
        async for piece in run(engine, model):
            yield ("delta", piece)
    except LLMError as e:
        fb = cfg["default_cloud"]
        if engine in LOCAL_ENGINES and not raw and cfg.get("fallback_to_cloud") and cfg["providers"][fb].get("api_key"):
            note = f"Local model unavailable, fell back to {engine_label(fb)}: {e}"
            engine, model = fb, None
            async for piece in run(engine, None):
                yield ("delta", piece)
        else:
            raise
    yield ("meta", {"engine": engine, "engine_label": engine_label(engine), "note": note,
                    "model": model or default_model_for(cfg, engine), "text": strip_think(raw).strip()})


# --------------------------------------------------------------------- helpers
def extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object in model output")
    return json.loads(text[start:end + 1])


def strip_fences(text: str) -> str:
    """Return the content of the largest fenced code block, or the text without stray fences."""
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", text, flags=re.S)
    if blocks:
        return max(blocks, key=len).strip()
    return re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text.strip()).strip()
