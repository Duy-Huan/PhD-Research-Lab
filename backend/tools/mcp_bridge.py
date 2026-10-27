"""The native tool registry as MCP tools for external agent clients (Antigravity, Codex, Claude Code, Gemini CLI ...).

The client is the agent: it runs its own model under its own account and calls this local server, so no third-party
software drives the client (the direction its terms permit). Three meta-tools are exposed on /mcp:

  phdlab_tools_search    rank registry tools for a need (capability/kind filters)
  phdlab_tools_describe  full schema, permissions and availability of one tool
  phdlab_tools_call      execute a registry tool through the unified runtime (grants, budgets, provenance)

Authority stays with this application. A session holding an ephemeral PhD Lab grant may only call the registry tools
named in that grant; a directly registered local client gets the owner-configured `tools.mcp_permissions`
(default read + compute), never mutation, with a per-session budget. Meta-tools are not registry entries, so a call
cannot recurse into them.
"""
from __future__ import annotations

import json
import threading

from backend.tools.registry import REGISTRY
from backend.tools.runtime import RUNTIME, Grant
from backend.tools.spec import PERMISSIONS, ToolError

TOOLS = [
    {"name": "phdlab_tools_search", "group": "read",
     "description": "Search the PhD Research Lab tool registry (native, python, CLI, MCP, container, optional Google tools). "
                    "Returns ranked tool ids with one-line purpose, permissions and availability.",
     "inputSchema": {"type": "object", "additionalProperties": False, "properties": {
         "query": {"type": "string", "maxLength": 500}, "capability": {"type": "string", "maxLength": 60},
         "kind": {"type": "string", "enum": ["", "native", "python", "cli", "mcp", "container"]},
         "limit": {"type": "integer", "minimum": 1, "maximum": 50}}}},
    {"name": "phdlab_tools_describe", "group": "read",
     "description": "Full input/output schema, permissions, versions and availability of one registry tool.",
     "inputSchema": {"type": "object", "required": ["tool"], "additionalProperties": False, "properties": {
         "tool": {"type": "string", "maxLength": 120}, "version": {"type": "string", "maxLength": 40}}}},
    {"name": "phdlab_tools_call", "group": "read",
     "description": "Execute one registry tool with JSON arguments through the PhD Research Lab runtime. Returns the job id, "
                    "status, result or a structured error with a hint. Every call is recorded with provenance.",
     "inputSchema": {"type": "object", "required": ["tool"], "additionalProperties": False, "properties": {
         "tool": {"type": "string", "maxLength": 120}, "version": {"type": "string", "maxLength": 40},
         "args": {"type": "object"}}}},
]
NAMES = {t["name"] for t in TOOLS}
_grants: dict[str, Grant] = {}
_lock = threading.Lock()


def _permissions() -> list:
    from backend.core.config import load_config
    configured = (load_config().get("tools") or {}).get("mcp_permissions") or ["read", "compute"]
    return [p for p in configured if p in PERMISSIONS and p != "workspace_write"]


def grant_for(client: dict) -> Grant:
    session = str(client.get("session") or client.get("name") or "mcp-client")[:80]
    ephemeral = client.get("grant")
    tools = sorted(ephemeral["tools"]) if ephemeral else ["*"]
    perms = _permissions()
    key = json.dumps([session, tools, perms])
    with _lock:
        g = _grants.get(key)
        if g is None:
            g = Grant(principal=f"mcp:{client.get('name') or 'client'}:{session}", tools=tools, permissions=perms,
                      allow_mutation=False, max_calls=200, max_wall_s=3600)
            _grants[key] = g
            while len(_grants) > 500:
                _grants.pop(next(iter(_grants)))
    return g


def _result(obj: dict, error: bool = False) -> dict:
    out = {"content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False, default=str)[:60000]}],
           "structuredContent": obj}
    if error:
        out["isError"] = True
    return out


def call(name: str, args: dict, client: dict | None = None) -> dict:
    client = client or {}
    args = args if isinstance(args, dict) else {}
    try:
        if name == "phdlab_tools_search":
            return _result({"results": REGISTRY.search(str(args.get("query", "")), capability=str(args.get("capability", "")),
                                                       kind=str(args.get("kind", "")), limit=int(args.get("limit") or 10))})
        if name == "phdlab_tools_describe":
            return _result(REGISTRY.describe(str(args.get("tool", "")), str(args.get("version", ""))))
        if name == "phdlab_tools_call":
            job = RUNTIME.run(str(args.get("tool", "")), args.get("args") if isinstance(args.get("args"), dict) else {},
                              grant_for(client), version=str(args.get("version", "")))
            obj = {"job": job["id"], "tool": f"{job['tool']}@{job.get('version', '')}", "status": job["status"],
                   "result": job["result"], "error": job["error"]}
            return _result(obj, error=job["status"] != "succeeded")
    except ToolError as e:
        return _result({"error": e.as_dict()}, error=True)
    raise ValueError(f"Unknown registry bridge tool {name}")
