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
    headers = {"Content-Type": "application/json"}
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


async def cloud_chat(cfg: dict, pid: str, system: str, messages: list, max_tokens: int,
                     temperature: float | None = None) -> str:
    spec, key, model, base = provider_settings(cfg, pid)
    if not key:
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


async def local_chat(cfg: dict, system: str, messages: list, max_tokens: int, temperature: float) -> str:
    base = cfg["lmstudio_base_url"].rstrip("/")
    model = cfg.get("local_model")
    if not model:
        models = await list_local_models(base)
        if not models:
            raise LLMError("LM Studio is running but no model is loaded.")
        model = models[0]
    return await openai_compat_chat(base, "", model, system, messages, max_tokens, temperature,
                                    "LM Studio", "local", LMSTUDIO_HINT)


# --------------------------------------------------------------------- router
def resolve_engine(cfg: dict, agent: str) -> str:
    mode = cfg["agent_modes"].get(agent, "cloud")
    if mode == "claude":  # Claude preferred: Anthropic when it has a key, otherwise the default cloud provider
        return "anthropic" if (cfg["providers"].get("anthropic") or {}).get("api_key") else cfg["default_cloud"]
    return cfg["default_cloud"] if mode == "cloud" else mode


def engine_label(engine: str) -> str:
    return "LM Studio (local)" if engine == "local" else PROVIDERS.get(engine, {}).get("label", engine)


async def call_agent(agent: str, system: str, user: str | None = None, messages: list | None = None,
                     max_tokens: int = 4096, temperature: float = 0.2) -> dict:
    """Run an agent on its configured engine. Returns {text, engine, engine_label, note}."""
    cfg = load_config()
    engine = resolve_engine(cfg, agent)
    msgs = messages or [{"role": "user", "content": user or ""}]
    if engine != "local":
        text = await cloud_chat(cfg, engine, system, msgs, max_tokens, temperature)
        return {"text": text, "engine": engine, "engine_label": engine_label(engine), "note": ""}
    try:
        text = await local_chat(cfg, system, msgs, max_tokens, temperature)
        return {"text": text, "engine": "local", "engine_label": engine_label("local"), "note": ""}
    except LLMError as e:
        fb = cfg["default_cloud"]
        if cfg.get("fallback_to_cloud") and cfg["providers"][fb].get("api_key"):
            text = await cloud_chat(cfg, fb, system, msgs, max_tokens, temperature)
            return {"text": text, "engine": fb, "engine_label": engine_label(fb),
                    "note": f"Local model unavailable, fell back to {engine_label(fb)}: {e}"}
        raise


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
    headers = {"Content-Type": "application/json"}
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


async def _stream_engine(cfg, engine, system, messages, max_tokens, temperature):
    if engine == "local":
        base = cfg["lmstudio_base_url"].rstrip("/")
        model = cfg.get("local_model") or ((await list_local_models(base)) or [None])[0]
        if not model:
            raise LLMError("LM Studio is running but no model is loaded.")
        async for t in _stream_openai(base, "", model, system, messages, max_tokens, temperature,
                                      "LM Studio", "local", LMSTUDIO_HINT):
            yield t
        return
    spec, key, model, base = provider_settings(cfg, engine)
    if not key:
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
    note, raw, emitted = "", "", 0

    async def run(eng):
        nonlocal raw, emitted
        async for chunk in _stream_engine(cfg, eng, system, messages, max_tokens, temperature):
            raw += chunk
            visible = strip_think(raw)
            if len(visible) > emitted and visible.startswith(visible[:emitted]):
                yield visible[emitted:]
                emitted = len(visible)

    try:
        async for piece in run(engine):
            yield ("delta", piece)
    except LLMError as e:
        fb = cfg["default_cloud"]
        if engine == "local" and not raw and cfg.get("fallback_to_cloud") and cfg["providers"][fb].get("api_key"):
            note = f"Local model unavailable, fell back to {engine_label(fb)}: {e}"
            engine = fb
            async for piece in run(engine):
                yield ("delta", piece)
        else:
            raise
    yield ("meta", {"engine": engine, "engine_label": engine_label(engine), "note": note,
                    "text": strip_think(raw).strip()})


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
