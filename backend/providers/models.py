"""Hybrid LLM router: many cloud providers (Anthropic native + OpenAI-compatible APIs) and LM Studio."""
from __future__ import annotations

import json
import re
from contextvars import ContextVar
from urllib.parse import urlsplit, urlunsplit

import httpx

from backend.providers import lifecycle as LC
from backend.core.config import PROVIDERS, agent_key, load_config

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


# Reasoning level of the current request ("cấp độ tư duy" in the chat): auto = the model's default, off, low, medium,
# high. Set by the chat turn (orchestrator) for the duration of one answer; mapped per engine below:
#   Anthropic   extended thinking with a token budget        OpenAI      reasoning_effort (off → minimal)
#   LM Studio   reasoning_effort (+ /no_think for Qwen off)   Ollama      think = true / false
# Engines without a control ignore it (the chat shows that note instead of pretending).
REASONING: ContextVar = ContextVar("phdlab_reasoning", default="auto")
THINK_BUDGET = {"low": 2048, "medium": 8192, "high": 24000}
EFFORT = {"off": "minimal", "low": "low", "medium": "medium", "high": "high"}


def _reasoning() -> str:
    v = REASONING.get()
    return v if v in ("off", "low", "medium", "high") else "auto"


def _no_think(messages: list, model: str) -> list:
    """Qwen-family local models switch thinking off with /no_think in the last user message."""
    if _reasoning() != "off" or "qwen" not in (model or "").lower() or not messages:
        return messages
    last = dict(messages[-1])
    last["content"] = f"{last.get('content') or ''} /no_think"
    return messages[:-1] + [last]


def strip_think(text: str) -> str:
    """Remove <think>…</think> reasoning (and an unfinished <think> block) from model output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return re.sub(r"<think>.*\Z", "", text, flags=re.S)


def _local_thinking(body: dict, pid: str, model: str) -> None:
    # Qwen 3.5 uses the hard template switch; /no_think alone can consume the
    # entire budget in reasoning_content and produce no user-visible answer.
    if pid == "local" and "qwen3.5" in model.lower().replace("-", "") and _reasoning() == "off":
        body["chat_template_kwargs"] = {"enable_thinking": False}
        body["reasoning_effort"] = "none"


# --------------------------------------------------------------------- Anthropic native
def _anthropic_body(model: str, system: str, messages: list, max_tokens: int) -> dict:
    body = {"model": model, "max_tokens": max_tokens, "system": system, "messages": to_anthropic(messages)}
    level = _reasoning()
    # Current Claude models use effort/adaptive thinking; a legacy manual budget can be rejected with HTTP 400.
    adaptive = bool(re.match(r"^claude-(?:opus|sonnet|haiku|fable|mythos)-5(?:-|$)", model) or
                    re.match(r"^claude-(?:opus|sonnet)-4-[678](?:-|$)", model))
    if level in THINK_BUDGET:
        if adaptive:
            body["thinking"] = {"type": "adaptive"}
            body["output_config"] = {"effort": level}
        else:
            body["thinking"] = {"type": "enabled", "budget_tokens": THINK_BUDGET[level]}
            body["max_tokens"] = max(max_tokens, THINK_BUDGET[level] + 4096)
    elif level == "off":
        if model.startswith("claude-sonnet-5-5"):
            body["thinking"] = {"type": "between_tools"}
            body["output_config"] = {"effort": "low"}
        elif model.startswith(("claude-opus-5-5", "claude-fable-5", "claude-mythos-5")):
            raise LLMError(f"{model} has always-on thinking. Choose low effort instead of off.")
        else:
            body["thinking"] = {"type": "disabled"}
    return body


async def anthropic_chat(base: str, key: str, model: str, system: str, messages: list, max_tokens: int) -> str:
    headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    body = _anthropic_body(model, system, messages, max_tokens)
    try:
        async with LC.http_client(TIMEOUT) as c:
            r = await c.post(f"{base}/messages", headers=headers, json=body)
    except httpx.HTTPError as e:
        raise LLMError(f"Network error contacting Anthropic: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"Anthropic error {r.status_code}: {_err_msg(r)}")
    try:
        data = r.json()
    except ValueError:
        raise LLMError(f"Anthropic returned a non-JSON response (check the base URL): {r.text[:200]}")
    if not isinstance(data, dict) or not isinstance(data.get("content"), list):
        raise LLMError(f"Anthropic returned an unexpected response: {_err_msg(r)}")
    text = "".join(b.get("text", "") for b in data.get("content", [])
                   if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
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
    _local_thinking(body, pid, model)
    if pid == "openai":  # GPT-5 / o-series: max_completion_tokens, default temperature only
        body["max_completion_tokens"] = body.pop("max_tokens")
        body.pop("temperature", None)
    headers = {"Content-Type": "application/json", **gateway_headers(pid)}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if pid == "openrouter":
        headers["X-Title"] = "PhD Research Lab"
    r = None
    while True:  # each retry removes one of two optional parameters; at most two adaptations
        try:
            async with LC.http_client(TIMEOUT) as c:
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
        if not isinstance(msg, dict):
            raise TypeError
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"{label} returned an unexpected response: {str(data)[:300]}")
    content = msg.get("content") or ""
    if isinstance(content, list):  # some providers return content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict) and isinstance(p.get("text"), str))
    if not isinstance(content, str):
        raise LLMError(f"{label} returned unexpected message content; check the selected model.")
    content = strip_think(content).strip()
    if not content:
        raise LLMError(f"{label} returned no answer content (finish_reason={data['choices'][0].get('finish_reason')}); check reasoning settings and token budget.")
    if data["choices"][0].get("finish_reason") == "length":
        content += "\n\n% [WARNING: output truncated at max_tokens]"
    return content


# --------------------------------------------------------------------- providers
def provider_settings(cfg: dict, pid: str) -> tuple[dict, str, str, str]:
    if pid not in PROVIDERS:
        raise LLMError(f"Unknown provider '{pid}'")
    spec, p = PROVIDERS[pid], (cfg.get("providers") or {}).get(pid) or {}
    base = normalize_base_url(p.get("base_url") or spec["base_url"], pid)
    return spec, str(p.get("api_key") or "").strip(), str(p.get("model") or spec["model"]).strip(), base


def normalize_base_url(value: str, pid: str = "") -> str:
    """Accept a server root or a pasted inference URL without duplicating endpoint paths."""
    base = str(value or "").strip().rstrip("/")
    if not base:
        return ""
    try:
        u = urlsplit(base)
        if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError
        _ = u.port
    except ValueError as e:
        raise LLMError("Base URL must be an http(s) server URL without credentials, query or fragment.") from e
    path = u.path.rstrip("/")
    for suffix in ("/chat/completions", "/messages", "/models"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    if not path and pid in PROVIDERS and PROVIDERS[pid].get("base_url"):
        path = urlsplit(PROVIDERS[pid]["base_url"]).path.rstrip("/")
    return urlunsplit((u.scheme, u.netloc, path, "", ""))


def key_required(spec: dict, pid: str, base: str) -> bool:
    """Local custom OpenAI proxies, like the built-in gateways, may run without authentication."""
    return not (spec.get("key_optional") or
                (pid == "custom" and urlsplit(base).hostname in ("localhost", "127.0.0.1", "::1")))


def _validate_target(spec: dict, pid: str, key: str, model: str, base: str) -> None:
    if not base:
        raise LLMError(f"{spec['label']}: base URL is empty.")
    if not key and key_required(spec, pid, base):
        raise LLMError(f"No API key for {spec['label']}. Add it in Settings → Providers.")
    if not model:
        raise LLMError(f"{spec['label']}: no model selected. List models and select an available model first.")


HEADER_NAME_RE = re.compile(r"^X-[A-Za-z0-9-]{1,60}$")


def gateway_headers(pid: str) -> dict:
    """v3.2: optional extra headers for a provider (config.routing.provider_headers), e.g. 9Router "X-9Router-Skills".
    Only X-… names are accepted, so a typo can never inject Authorization/Cookie or identity headers into a request."""
    try:
        hs = (load_config().get("routing") or {}).get("provider_headers", {}).get(pid) or {}
    except Exception:
        return {}
    if not isinstance(hs, dict):
        return {}
    return {str(k): str(v)[:200] for k, v in hs.items()
            if HEADER_NAME_RE.fullmatch(str(k)) and "\n" not in str(v) and "\r" not in str(v)}


async def cloud_chat(cfg: dict, pid: str, system: str, messages: list, max_tokens: int,
                     temperature: float | None = None, model: str | None = None) -> str:
    spec, key, default_model, base = provider_settings(cfg, pid)
    model = model or default_model
    _validate_target(spec, pid, key, model, base)
    if spec["kind"] == "anthropic":
        return await anthropic_chat(base, key, model, system, messages, max_tokens)
    return await openai_compat_chat(base, key, model, system, messages, max_tokens, temperature, spec["label"], pid)


async def list_provider_models(cfg: dict, pid: str) -> list:
    spec, key, _, base = provider_settings(cfg, pid)
    if not base:
        raise LLMError(f"{spec['label']}: base URL is empty.")
    if not key and key_required(spec, pid, base):
        raise LLMError(f"Enter and save the {spec['label']} API key first.")
    headers = {**gateway_headers(pid), **({"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
               if spec["kind"] == "anthropic" else ({"Authorization": f"Bearer {key}"} if key else {}))}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{base}/models", headers=headers, params={"limit": 200} if spec["kind"] == "anthropic" else None)
    except httpx.HTTPError as e:
        raise LLMError(f"{spec['label']}: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"{spec['label']} cannot list models ({r.status_code}): {_err_msg(r)}")
    try:
        data = r.json()
    except ValueError as e:
        raise LLMError(f"{spec['label']} returned a non-JSON model list; check the base URL.") from e
    items = data.get("data", data.get("models", [])) if isinstance(data, dict) else data
    if not isinstance(items, list) or (isinstance(data, dict) and "data" not in data and "models" not in data):
        raise LLMError(f"{spec['label']} returned an unexpected model list; check the base URL.")
    ids = [(m.get("id") or m.get("name") or "") if isinstance(m, dict) else m if isinstance(m, str) else "" for m in items]
    return sorted({i.removeprefix("models/") for i in ids if isinstance(i, str) and i})


# --------------------------------------------------------------------- local (LM Studio)
LMSTUDIO_HINT = "In LM Studio open the Developer tab, load a model and click 'Start Server'."


async def list_local_models(base_url: str) -> list:
    from backend.providers.local import lms_root
    base = lms_root(base_url) + "/v1"
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
    from backend.providers.local import first_model, lms_root, ollama_root
    if engine == "ollama":
        base = ollama_root(cfg.get("ollama_base_url")) + "/v1"
        model = model or cfg.get("ollama_model") or await first_model("ollama", cfg)
        if not model:
            raise LLMError("Ollama has no model. " + OLLAMA_HINT)
        return base, model, "Ollama", OLLAMA_HINT
    base = lms_root(cfg.get("lmstudio_base_url")) + "/v1"
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
        from backend.execution.resources import gpu_busy, ollama_cpu_options
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
    from backend.providers.local import ollama_root
    _, model, label, hint = await local_target(cfg, "ollama", model)
    body = {"model": model, "messages": _ollama_messages(system, messages), "stream": False,
            "options": {**options, "num_predict": max_tokens, "temperature": temperature}}
    try:
        async with LC.http_client(TIMEOUT) as c:
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
    from backend.providers.local import ollama_root
    _, model, label, hint = await local_target(cfg, "ollama", model)
    body = {"model": model, "messages": _ollama_messages(system, messages), "stream": True,
            "options": {**options, "num_predict": max_tokens, "temperature": temperature}}
    if _reasoning() != "auto":
        body["think"] = _reasoning() != "off"
    try:
        async with LC.http_client(TIMEOUT) as c:
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
                     engine: str = "local", model: str | None = None, purpose: str | None = None) -> str:
    """v4.1: every local call holds a lifecycle lease (load → task → release per config.lifecycle)."""
    base, model, label, hint = await local_target(cfg, engine, model)
    async with LC.lease("local", engine, model, purpose):
        if engine == "ollama":
            opts = ollama_offload_options(cfg)
            if opts:
                return await ollama_native_chat(cfg, system, messages, max_tokens, temperature, model, opts)
        return await openai_compat_chat(base, "", model, system, messages, max_tokens, temperature, label, engine, hint)


# --------------------------------------------------------------------- router
def resolve_engine(cfg: dict, agent: str) -> str:
    mode = str(cfg["agent_modes"].get(agent_key(agent), "cloud")).removeprefix("cli:").removeprefix("app:").removeprefix('runtime:')
    if mode == "chatgpt_sub":
        return "codex"
    if mode == "claude":  # Claude preferred: Anthropic when it has a key, otherwise the default cloud provider
        return "anthropic" if (cfg["providers"].get("anthropic") or {}).get("api_key") else cfg["default_cloud"]
    return cfg["default_cloud"] if mode == "cloud" else mode


def resolve_model(cfg: dict, agent: str) -> str | None:
    """Per-agent model override (v3); None = the engine's default model."""
    return (cfg.get("agent_models") or {}).get(agent_key(agent)) or None


CLI_LABELS = {
    "codex": "ChatGPT Subscription (Codex CLI)",
    "claude_code": "Claude Subscription (Claude Code CLI)",
    "gemini_cli": "Google Gemini CLI",
    "antigravity": "Google Antigravity CLI",
}
AGENT_RUNTIME_LABELS = {'hermes': 'Hermes Agent (isolated Nous runtime)'}


def engine_label(engine: str) -> str:
    if engine == "mcp":
        return "MCP inference agent"
    if engine == "local":
        return "LM Studio (local)"
    if engine == "ollama":
        return "Ollama (local)"
    if engine in CLI_LABELS:
        return CLI_LABELS[engine]
    if engine in AGENT_RUNTIME_LABELS:
        return AGENT_RUNTIME_LABELS[engine]
    return PROVIDERS.get(engine, {}).get("label", engine)


def default_model_for(cfg: dict, engine: str) -> str:
    if engine == "local":
        return cfg.get("local_model") or ""
    if engine == "ollama":
        return cfg.get("ollama_model") or ""
    if engine == 'hermes':
        return (cfg.get('hermes') or {}).get('model') or ''
    if engine in CLI_LABELS:
        return ""  # no override means the signed-in vendor CLI chooses its configured default
    if engine in PROVIDERS:
        return cfg["providers"][engine].get("model") or PROVIDERS[engine]["model"]
    return ""


def agent_runtime(cfg: dict, agent: str) -> dict:
    """What an agent will use right now: {engine, engine_label, model} — shown in every chat header."""
    eng = resolve_engine(cfg, agent)
    if eng == "auto":
        from backend.providers.router import plan
        p = plan(cfg, agent)
        first = (p["candidates"] or [""])[0]
        return {"agent": agent, "mode": "auto", "engine": first or "none", "kind": p["kind"],
                "engine_label": ("auto → " + engine_label(first)) if first else "auto → (no engine available)",
                "model": default_model_for(cfg, first) or "(auto)", "override": False, "candidates": p["candidates"],
                "gpu_busy": p["gpu_busy"], "online": p["online"]}
    return {"agent": agent, "mode": cfg["agent_modes"].get(agent_key(agent), "cloud"), "engine": eng, "engine_label": engine_label(eng),
            "model": resolve_model(cfg, agent) or default_model_for(cfg, eng) or "(auto)",
            "override": bool(resolve_model(cfg, agent))}


async def _stream_cli(cfg: dict, engine: str, system: str, messages: list, model: str | None = None):
    """All native CLI/runtime model calls use the existing durable project gateway."""
    import asyncio
    from backend.providers import gateway as G
    prompt = (system + "\n\n" if system else "") + "\n\n".join(
        f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in messages
    )
    request = None
    finished = False
    emitted = False
    try:
        request = await asyncio.to_thread(G.prepare, prompt, engine,
            profile=cfg.get('gateway', {}).get('cli_profile', 'review'), memory=False)
        await asyncio.to_thread(G.send, request['id'], model=model or '', reasoning=_reasoning())
        cursor = 0
        while True:
            batch = await asyncio.to_thread(G.wait_events, request['id'], cursor, 1.0)
            cursor = batch['next']
            for event in batch['events']:
                if event.get('type') == 'text_delta' and event.get('text'):
                    emitted = True
                    yield event['text']
            if batch['status'] not in ('ready', 'starting', 'running'):
                # Drain the durable event window before accepting terminal state.
                if batch['events']: continue
                actual = await asyncio.to_thread(G.get, request['id'])
                finished = True
                if actual['status'] != 'completed':
                    raise LLMError('; '.join(actual.get('errors') or []) or f"{engine} request {actual['status']}")
                if not emitted and actual.get('answer'):
                    yield actual['answer']
                if not emitted and not actual.get('answer'):
                    raise LLMError(f'{engine} returned no model response')
                break
    except G.GatewayError as error:
        raise LLMError(str(error)) from error
    finally:
        if request and not finished:
            actual = await asyncio.to_thread(G.get, request['id'])
            if actual.get('status') in ('ready', 'starting', 'running'):
                await asyncio.to_thread(G.cancel, request['id'])


async def call_agent(agent: str, system: str, user: str | None = None, messages: list | None = None,
                     max_tokens: int = 4096, temperature: float = 0.2) -> dict:
    """Run an agent on its configured engine/model. Returns {text, engine, engine_label, model, note}."""
    cfg = load_config()
    engine = resolve_engine(cfg, agent)
    model = resolve_model(cfg, agent)
    msgs = messages or [{"role": "user", "content": user or ""}]
    if engine == "auto":
        return await _call_auto(cfg, agent, system, msgs, max_tokens, temperature)
    if engine == "mcp":
        from backend.providers.mcp_agent import complete
        text = await complete(cfg, system, msgs, model, max_tokens, temperature)
        return {"text": strip_think(text).strip(), "engine": engine, "engine_label": engine_label(engine),
                "model": model or "(server default)", "note": "MCP inference tool; server owns model execution"}
    if engine in CLI_LABELS or engine in AGENT_RUNTIME_LABELS:
        parts = [p async for p in _stream_cli(cfg, engine, system, msgs, model)]
        text = strip_think("".join(parts)).strip()
        return {"text": text, "engine": engine, "engine_label": engine_label(engine),
                "model": model or default_model_for(cfg, engine),
                "note": "Isolated agent runtime; final response after agent completion" if engine in AGENT_RUNTIME_LABELS else "CLI subscription connector"}
    if engine not in LOCAL_ENGINES:
        text = await cloud_chat(cfg, engine, system, msgs, max_tokens, temperature, model)
        return {"text": text, "engine": engine, "engine_label": engine_label(engine), "model": model or default_model_for(cfg, engine), "note": ""}
    try:
        text = await local_chat(cfg, system, msgs, max_tokens, temperature, engine, model, LC.purpose_for(agent))
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
    from backend.providers.router import plan
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
                text = await local_chat(cfg, system, msgs, max_tokens, temperature, eng, purpose=LC.purpose_for(agent))
            elif eng in CLI_LABELS or eng in AGENT_RUNTIME_LABELS:
                text = ''.join([part async for part in _stream_cli(cfg, eng, system, msgs, default_model_for(cfg, eng) or None)])
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
    body = {**_anthropic_body(model, system, messages, max_tokens), "stream": True}
    try:
        async with LC.http_client(TIMEOUT) as c:
            async with c.stream("POST", f"{base}/messages", headers=headers, json=body) as r:
                if r.status_code != 200:
                    await r.aread()
                    raise LLMError(f"Anthropic error {r.status_code}: {_err_msg(r)}")
                async for line in r.aiter_lines():
                    d = _sse_lines_to_json(line)
                    if not isinstance(d, dict):
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
    body = {"model": model, "messages": [{"role": "system", "content": system}] + to_openai(_no_think(messages, model)),
            "max_tokens": max_tokens, "stream": True}
    if temperature is not None:
        body["temperature"] = temperature
    if pid == "openai":
        body["max_completion_tokens"] = body.pop("max_tokens")
        body.pop("temperature", None)
    if _reasoning() != "auto" and pid in ("openai", "local", "ollama"):
        body["reasoning_effort"] = EFFORT[_reasoning()]
    _local_thinking(body, pid, model)
    headers = {"Content-Type": "application/json", **gateway_headers(pid)}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if pid == "openrouter":
        headers["X-Title"] = "PhD Research Lab"
    try:
        async with LC.http_client(TIMEOUT) as c:
            while True:  # retries remove max_tokens or temperature, so adaptation is bounded
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
                        if not isinstance(d, dict):
                            continue
                        if d.get("error"):
                            error = d["error"]
                            detail = error.get("message", error) if isinstance(error, dict) else error
                            raise LLMError(f"{label} stream error: {detail}")
                        if not d.get("choices"):
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


async def _stream_engine(cfg, engine, system, messages, max_tokens, temperature, model=None, purpose=None):
    if engine in LOCAL_ENGINES:
        base, model, label, hint = await local_target(cfg, engine, model)
        async with LC.lease("local", engine, model, purpose):
            opts = ollama_offload_options(cfg) if engine == "ollama" else None
            if opts:
                async for t in _stream_ollama_native(cfg, system, messages, max_tokens, temperature, model, opts):
                    yield t
                return
            async for t in _stream_openai(base, "", model, system, messages, max_tokens, temperature, label, engine, hint):
                yield t
        return
    if engine in CLI_LABELS or engine in AGENT_RUNTIME_LABELS:
        async for t in _stream_cli(cfg, engine, system, messages, model):
            yield t
        return
    spec, key, default_model, base = provider_settings(cfg, engine)
    model = model or default_model
    _validate_target(spec, engine, key, model, base)
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
    if engine == "mcp":
        from backend.providers.mcp_agent import complete
        text = strip_think(await complete(cfg, system, messages, model, max_tokens, temperature)).strip()
        yield ("delta", text)
        yield ("meta", {"engine": engine, "engine_label": engine_label(engine), "model": model or "(server default)",
                        "text": text, "note": "MCP inference tool; response delivered after tool completion"})
        return
    note, raw, emitted = "", "", 0

    purpose = LC.purpose_for(agent)

    async def run(eng, mdl):
        nonlocal raw, emitted
        async for chunk in _stream_engine(cfg, eng, system, messages, max_tokens, temperature, mdl, purpose):
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
