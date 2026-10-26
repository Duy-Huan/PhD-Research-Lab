"""Effective session policy (Firewall spec §6.4, §12): global defaults → module defaults → session → turn.

Every effective value is reported with its SOURCE ("global" | "module" | "session" | "turn") so the UI and the CLI
can show where a setting came from. A turn override never changes the session's stored settings.

Operating modes (real backend behaviour, not a toggle):
  automation  module context + retrieval are compiled automatically, read-only research tools proposed by the
              orchestrator run within the allowlist, memory follows memory_mode, the turn is sent immediately.
  manual      only the sources the researcher selected are used (no automatic retrieval), no automatic tool selection,
              EVERY tool call and action waits for a decision, memory extraction is manual unless explicitly set, and
              a turn stops at `awaiting_launch` with the full launch plan (context manifest, provider, command, cwd,
              environment allowlist, mounts) until the researcher launches it.

Risk tiers (approval rule): 0 read · 1 writes inside the session (candidates, staged files) · 2 changes research
state / the code project / starts compute / network · 3 destructive. Automation auto-runs tier 0 only; manual runs
nothing without a decision. A model can never approve its own request — decisions only come through the API.
"""
from __future__ import annotations

import re

from backend.agent import AIWSError

MEMORY_TYPES = ("decision", "finding", "hypothesis", "experiment", "knowledge", "open_question", "rejected_approach")
CHOICES = {"operating_mode": ("automation", "manual"), "context_mode": ("none", "selected", "relevant", "expanded"),
           "memory_mode": ("off", "manual", "suggest", "auto"), "security_profile": ("review", "assisted"),
           "reasoning": ("auto", "off", "low", "medium", "high")}
BOOLS = ("mcp_auto", "keep_history", "summaries", "collect_artifacts")
KEYS = ("provider", "model", "reasoning", "context_mode", "memory_mode", "operating_mode", "security_profile",
        "mcp_auto", "mcp_tools", "auto_memory_types", "keep_history", "summaries", "collect_artifacts",
        "context_budget_tokens")
# per-turn shortcuts → the settings they imply (labelled as turn overrides in the UI)
TURN_FLAGS = {"selected_only": ("context_mode", "selected"), "read_only": ("security_profile", "review"),
              "no_mcp": ("mcp_tools", ["-"]), "no_memory": ("use_memory", False)}
RISK_LABEL = {0: "read", 1: "session write", 2: "research state / project / compute", 3: "destructive"}


def _check(key: str, v):
    if key in CHOICES:
        if v not in CHOICES[key]:
            raise AIWSError(f"{key} must be one of {', '.join(CHOICES[key])}")
        return v
    if key in BOOLS:
        if not isinstance(v, bool):
            raise AIWSError(f"{key} must be true or false")
        return v
    if key == "provider":
        from backend.providers.registry import ids
        known_ids = ids()
        if v not in known_ids:
            alias_map = {
                "codex": "cli:codex",
                "claude": "cli:claude_code",
                "claude_code": "cli:claude_code",
                "antigravity": "cli:antigravity",
                "gemini_cli": "cli:gemini_cli",
                "openai": "app:openai",
                "anthropic": "app:anthropic",
                "gemini": "app:gemini",
                "google": "app:gemini",
                "cloud:google": "app:gemini",
                "cloud:openai": "app:openai",
                "cloud:anthropic": "app:anthropic",
                "cloud:deepseek": "app:deepseek",
            }
            if v in alias_map and alias_map[v] in known_ids:
                v = alias_map[v]
            elif f"runtime:{v}" in known_ids:
                v = f"runtime:{v}"
            elif f"cli:{v}" in known_ids:
                v = f"cli:{v}"
            elif f"app:{v}" in known_ids:
                v = f"app:{v}"
            else:
                raise AIWSError(f"Unknown provider '{v}'")
        return v
    if key == "model":
        v = str(v or "").strip()
        if v and not re.fullmatch(r"[\w.:/@+-]{1,80}", v):
            raise AIWSError("Invalid model name")
        return v
    if key == "mcp_tools":
        from backend.agent.mcp_policy import catalog
        known = {t["name"] for t in catalog()} | {"-"}
        if not isinstance(v, list) or any(x not in known for x in v):
            raise AIWSError("mcp_tools must be a list of known tool names ('-' = no tools)")
        return list(dict.fromkeys(v))
    if key == "auto_memory_types":
        if not isinstance(v, list) or any(x not in MEMORY_TYPES for x in v):
            raise AIWSError(f"auto_memory_types: subset of {', '.join(MEMORY_TYPES)}")
        return list(dict.fromkeys(v))
    try:  # context_budget_tokens
        n = int(v)
    except (TypeError, ValueError):
        raise AIWSError("context_budget_tokens must be a number")
    return max(500, min(60000, n))


def clean_settings(patch: dict) -> dict:
    out = {}
    for k, v in (patch or {}).items():
        if k not in KEYS:
            raise AIWSError(f"Unknown setting '{k}'")
        out[k] = _check(k, v)
    return out


def clean_overrides(ov: dict) -> dict:
    """Per-turn overrides: any setting, plus the TURN_FLAGS shortcuts and consent_weaker / launch flags."""
    ov = dict(ov or {})
    flags = {k: bool(ov.pop(k)) for k in list(ov) if k in TURN_FLAGS or k in ("consent_weaker", "patch_only")}
    sources = ov.pop("sources", None)
    tools = ov.pop("run_tools", None)
    out = clean_settings(ov)
    if sources is not None:
        out["sources"] = clean_sources(sources)
    if tools is not None:
        from backend.agent.mcp_policy import catalog
        known = {t["name"] for t in catalog()}
        if not isinstance(tools, list) or any(not isinstance(x, dict) or x.get("tool") not in known or
                                              not isinstance(x.get("args", {}), dict) for x in tools):
            raise AIWSError("run_tools must be a list of {tool, args} with known tool names")
        out["run_tools"] = [{"tool": x["tool"], "args": x.get("args", {})} for x in tools][:5]
    for k, on in flags.items():
        if on and k in TURN_FLAGS:
            key, val = TURN_FLAGS[k]
            out[key] = val
        elif on:
            out[k] = True
    return out


def clean_sources(v) -> list:
    if not isinstance(v, list) or any(not isinstance(x, str) or not re.fullmatch(r"(ref|mem|run|note|att|paper|evidence|artifact|claim):[\w.:@/+-]{1,120}", x)
                                      for x in v):
        raise AIWSError("sources must be a list of ids like ref:<key>, mem:<id>, run:<id>, note:<id>, att:<id>")
    return list(dict.fromkeys(v))[:100]


def defaults() -> dict:
    from backend.core.config import load_config
    a = load_config()["aiws"]
    return {k: a[k] for k in KEYS} | {"use_memory": True}


def effective(session: dict, overrides: dict | None = None) -> dict:
    from backend.core.config import load_config
    module = session["binding"]["module"]
    md = (load_config()["aiws"].get("module_defaults") or {}).get(module) or {}
    eff = {k: {"value": v, "source": "global"} for k, v in defaults().items()}
    for src, layer in (("module", md), ("session", session.get("settings") or {}), ("turn", overrides or {})):
        for k, v in layer.items():
            if k in eff or k in ("consent_weaker", "patch_only", "sources", "run_tools"):
                eff[k] = {"value": v, "source": src}
    if eff["operating_mode"]["value"] == "manual":
        if eff["context_mode"]["value"] in ("relevant", "expanded") and eff["context_mode"]["source"] != "turn":
            eff["context_mode"] = {"value": "selected", "source": "manual mode"}
        if eff["mcp_auto"]["value"]:
            eff["mcp_auto"] = {"value": False, "source": "manual mode"}
        if eff["memory_mode"]["source"] in ("global", "module") and eff["memory_mode"]["value"] in ("suggest", "auto"):
            eff["memory_mode"] = {"value": "manual", "source": "manual mode"}
    if session.get("topic_id"):
        # Existing MCP tools and memory extraction operate at project scope. Do not expose them implicitly to Topics.
        for key, value in {"mcp_auto": False, "mcp_tools": ["-"], "memory_mode": "off"}.items():
            eff[key] = {"value": value, "source": "topic isolation"}
    return eff


def values(eff: dict) -> dict:
    return {k: v["value"] for k, v in eff.items()}


def needs_approval(risk: int, operating_mode: str) -> bool:
    return operating_mode == "manual" or int(risk) >= 1


def check_provider(eff: dict) -> list:
    """Unsupported choices are reported (and not applied); an unenforceable security profile is refused later."""
    from backend.providers.registry import check_setting
    v = values(eff)
    notes = []
    for key in ("reasoning", "model", "security_profile"):
        why = check_setting(v["provider"], key, v[key])
        if why:
            notes.append({"setting": key, "value": v[key], "note": why})
    return notes
