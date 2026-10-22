"""Provider registry with truthful capability descriptors (Firewall spec §10).

Provider ids
    app:auto · app:local · app:ollama · app:<cloud provider>   in-app engines of llm.py (HTTP to local / cloud models)
    cli:codex · cli:claude_code · cli:gemini_cli · cli:antigravity   CLI connectors (subscription sign-in, firewalled)

Only what an adapter can verify is advertised. Notably:
  * reasoning_controls — the "cấp độ tư duy" of the chat: Anthropic extended thinking, OpenAI / LM Studio
    reasoning_effort, Ollama think, Codex `-c model_reasoning_effort=…`; every other provider shows "not supported"
    instead of pretending a setting was applied;
  * native_session_resume — CLI connectors with `supports_resume`; in-app engines are stateless HTTP calls, so a
    session continues by re-sending the conversation (reported as "restored context", never as native resume);
  * structured_tool_events — CLI stream-json/JSONL normalisers (gateway/events.py); in-app engines run no tools of
    their own (PhD-Lab executes approved research tools and passes the results as context);
  * sandbox_options — the profiles gateway/workspace.py can enforce (or offer with consent) for that CLI.
"""
from __future__ import annotations

from backend.agent import AIWSError

REASONING = {"codex": ("low", "medium", "high")}
APP_LOCAL = {"local": "Local AI (LM Studio / configured local engine)", "ollama": "Ollama (local)"}


def _cfg():
    from backend.core.config import load_config
    return load_config()


def _app(pid: str, cfg: dict) -> dict:
    from backend.core.config import PROVIDERS
    engine = pid.split(":", 1)[1]
    if engine == "auto":
        label, transport, state, models = "Smart router (auto: local → cloud chain)", "router", "UNKNOWN", []
        detail = "routes between configured engines (llm_router); no fallback to a paid API unless configured"
    elif engine in APP_LOCAL:
        label, transport, state = APP_LOCAL[engine], "local", "UNKNOWN"
        models = [m for m in [cfg.get("ollama_model") if engine == "ollama" else cfg.get("local_model")] if m]
        detail = "local model server on this computer (checked when the first message is sent)"
    else:
        from backend.providers.models import LLMError, key_required, provider_settings
        p = (cfg.get("providers") or {}).get(engine) or {}
        label, transport = PROVIDERS[engine]["label"], "api"
        try:
            spec, key, _, base = provider_settings(cfg, engine)
            state = "UNKNOWN" if key or not key_required(spec, engine, base) else "NO_KEY"
            detail = "configured; use Test connection to verify authentication and model access"
            if not base:
                state, detail = "ERROR", "base URL is empty — add one in Settings → Providers"
            elif state == "NO_KEY":
                detail = "no API key — add one in Settings → Providers"
        except LLMError as e:
            state, detail = "ERROR", str(e)
        models = list(dict.fromkeys(m for m in [p.get("model"), *PROVIDERS[engine]["models"]] if m))
    levels = ["off", "low", "medium", "high"] if engine in ("auto", "local", "ollama", "anthropic", "openai") else []
    if engine == "anthropic" and (p.get("model") or PROVIDERS[engine]["model"]).startswith(
            ("claude-opus-5-5", "claude-fable-5", "claude-mythos-5")):
        levels.remove("off")
    return {"id": pid, "label": label, "transport": transport, "state": state, "detail": detail, "available": state not in ("NO_KEY", "ERROR"),
            "capabilities": {"streaming": True, "native_session_resume": False, "conversation": "restored-context",
                             "reasoning_controls": levels, "image_or_file_inputs": False, "structured_tool_events": False,
                             "usage_reporting": False, "cancellation": True, "model_override": True, "models": models,
                             "sandbox_options": [], "approval_options": ["phdlab"],
                             "mcp": "phdlab-executed"}}


def _cli(pid: str) -> dict:
    from backend.providers import cli as C
    from backend.providers import cli_space as W
    name = pid.split(":", 1)[1]
    conn = C.CONNECTORS[name]
    try:
        h = conn.health()
        caps = conn.capabilities()
    except Exception as e:  # a broken probe must not break the registry
        h, caps = {"state": "ERROR", "detail": f"{type(e).__name__}: {e}"[:200]}, {}
    sendable = caps.get("send") is True
    profiles = [{"profile": prof, "level": iso[1], "enforced": iso[2], "how": iso[3]}
                for (p, prof), iso in W.ISOLATION.items() if p == name and iso[0]]
    return {"id": pid, "label": conn.label, "transport": "cli", "state": h.get("state", "UNKNOWN"), "detail": h.get("detail", ""),
            "available": sendable and h.get("state") not in ("DISCONNECTED", "UNAVAILABLE", "ERROR", "AUTH_EXPIRED"),
            "setup": h.get("setup", []), "billing": h.get("billing", ""),
            "capabilities": {"streaming": sendable, "native_session_resume": bool(conn.supports_resume),
                             "conversation": "native" if conn.supports_resume else "restored-context",
                             "reasoning_controls": list(REASONING.get(name, ())), "image_or_file_inputs": False,
                             "structured_tool_events": True, "usage_reporting": True, "cancellation": caps.get("cancel") is True,
                             "model_override": True, "models": list(dict.fromkeys((_cfg()["gateway"].get("cli_models") or {}).get(name) or
                                  (["sonnet", "opus", "haiku"] if name == "claude_code" else []))), "sandbox_options": profiles,
                             "approval_options": ["profile"],
                             "mcp": "session-scoped" if name == "claude_code" else "vendor-config"}}


def ids(cfg: dict | None = None) -> list:
    from backend.core.config import PROVIDERS
    from backend.providers.cli import CONNECTORS
    return ["app:auto", "app:local", "app:ollama"] + [f"app:{p}" for p in PROVIDERS] + \
        [f"cli:{c}" for c in CONNECTORS]


def describe(pid: str, cfg: dict | None = None) -> dict:
    cfg = cfg or _cfg()
    if pid not in ids(cfg):
        raise AIWSError(f"Unknown provider '{pid}'")
    if pid.startswith("app:"):
        return _app(pid, cfg)
    return _cli(pid)


def registry() -> list:
    """Every provider; CLI probes (version / sign-in checks, seconds each) run in parallel and are cached."""
    from concurrent.futures import ThreadPoolExecutor
    cfg = _cfg()
    with ThreadPoolExecutor(max_workers=8) as ex:
        return list(ex.map(lambda p: describe(p, cfg), ids(cfg)))


def check_setting(pid: str, key: str, value) -> str:
    """'' when the provider supports `value` for `key`, else the reason (shown instead of silently applying it)."""
    caps = describe(pid)["capabilities"]
    if key == "reasoning" and value not in ("", "auto", None):
        if value == "off" and not caps["reasoning_controls"]:
            return ""
        if value not in caps["reasoning_controls"]:
            return f"{pid} has no reasoning control" + (f" for '{value}'" if caps["reasoning_controls"] else "") + \
                " — the provider's default is used"
    if key == "security_profile" and pid.startswith("cli:"):
        if value not in [p["profile"] for p in caps["sandbox_options"]]:
            return f"{pid} cannot run the '{value}' profile — refused (fail closed)"
    if key == "model" and value and not caps["model_override"]:
        return f"{pid} does not accept a model choice"
    return ""
