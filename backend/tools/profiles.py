"""Agent profiles: what agents may use, set by the owner in Settings (v6.6.2).

The owner bounds agents by tools and permissions only. Grants issued here carry no step, call or wall-clock budget;
the user's Stop, each tool's own hang timeout and the loop's no-progress hint remain. Every agent path uses one of:

  tools.agent_profile                 the chat/Hermes agent ({"permissions": [...], "tools": [patterns]})
  tools.client_profiles[<client>]     external MCP clients: "agent" (same as the agent profile) or an own profile;
                                      clients without an entry keep tools.mcp_permissions (read+compute by default)

workspace_write also allows tools that change project state (mutates=true); it never reaches outside the project.
"""
from __future__ import annotations

from backend.tools.runtime import Grant
from backend.tools.spec import PERMISSIONS

ORDER = ("read", "compute", "network", "workspace_write", "process", "reasoning")  # display order of PERMISSIONS
DEFAULT_PROFILE = {"permissions": ["read", "compute", "network", "workspace_write"], "tools": ["*"]}
DEFAULT_CLIENTS = {"chatgpt": "agent", "hermes": "agent", "antigravity": "agent"}


def normalize_profile(value) -> dict:
    """Validated profile with permissions in canonical order and de-duplicated tool patterns; raises ValueError."""
    if not isinstance(value, dict) or set(value) - {"permissions", "tools"}:
        raise ValueError("A profile is {'permissions': [...], 'tools': [...]}")
    perms, tools = value.get("permissions", []), value.get("tools", ["*"])
    if not isinstance(perms, list) or any(p not in PERMISSIONS for p in perms):
        raise ValueError(f"Profile permissions must be among {list(PERMISSIONS)}")
    if not isinstance(tools, list) or any(not isinstance(t, str) or not t.strip() or len(t) > 120 for t in tools):
        raise ValueError("Profile tools must be tool ids or patterns")
    return {"permissions": [p for p in ORDER if p in perms], "tools": list(dict.fromkeys(t.strip() for t in tools))}


def normalize_clients(value) -> dict:
    if not isinstance(value, dict):
        raise ValueError("client_profiles must map client names to 'agent' or a profile")
    out = {}
    for name, profile in value.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 60:
            raise ValueError("Invalid MCP client name")
        out[name.strip().lower()] = "agent" if profile == "agent" else normalize_profile(profile)
    return out


def _tools_cfg() -> dict:
    from backend.core.config import load_config
    return load_config().get("tools") or {}


def agent_profile() -> dict:
    try:
        return normalize_profile(_tools_cfg().get("agent_profile") or DEFAULT_PROFILE)
    except ValueError:
        return dict(DEFAULT_PROFILE)


def _grant(principal: str, profile: dict, tools: list | None = None) -> Grant:
    return Grant(principal=principal, tools=profile["tools"] if tools is None else tools,
                 permissions=profile["permissions"], allow_mutation="workspace_write" in profile["permissions"],
                 max_calls=None, max_wall_s=None, max_output_bytes=None)


def agent_grant(principal: str, session_tools: list | None = None) -> Grant:
    """Grant for the chat/Hermes agent. session_tools: ["-"] = isolated (no tools), a list narrows, empty = profile."""
    profile = agent_profile()
    if session_tools == ["-"]:
        return _grant(principal, profile, [])
    narrowed = [t for t in (session_tools or []) if t != "-"]
    return _grant(principal, profile, narrowed or None)


def client_grant(client: str, principal: str) -> Grant:
    """Grant for an external MCP client (ChatGPT, Antigravity, Hermes, ...)."""
    cfg = _tools_cfg()
    try:
        clients = {**DEFAULT_CLIENTS, **normalize_clients(cfg.get("client_profiles") or {})}
    except ValueError:
        clients = dict(DEFAULT_CLIENTS)
    profile = clients.get((client or "").strip().lower())
    if profile == "agent":
        return _grant(principal, agent_profile())
    if isinstance(profile, dict):
        return _grant(principal, profile)
    fallback = [p for p in (cfg.get("mcp_permissions") or ["read", "compute"]) if p in PERMISSIONS and p != "workspace_write"]
    return _grant(principal, {"permissions": fallback, "tools": ["*"]})
