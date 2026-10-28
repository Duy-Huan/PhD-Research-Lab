"""The native tool registry as MCP tools for external agent clients (Antigravity, Codex, Claude Code, Gemini CLI ...).

The client is the agent: it runs its own model under its own account and calls this local server, so no third-party
software drives the client (the direction its terms permit). Three meta-tools are exposed on /mcp:

  phdlab_tools_search    rank registry tools for a need (capability/kind filters)
  phdlab_tools_describe  full schema, permissions and availability of one tool
  phdlab_tools_call      execute a registry tool through the unified runtime (grants, budgets, provenance)
  phdlab_tools_job       status, result or cancellation of a call that was still running (6.6.4)

A call waits at most `wait_s` (default below the CLI clients' 60 s MCP tool timeout) and then returns its running job,
so a long tool never holds the HTTP request until a proxy answers 502; the client polls phdlab_tools_job. Only the
principal that started a job may read or cancel it.

Authority stays with this application (v6.6.2 profiles). A session holding an ephemeral PhD Lab grant may only call
the registry tools named in that grant, under the agent profile; a directly connected client gets its entry in
`tools.client_profiles` ("agent" for chatgpt/hermes/antigravity by default) or, when it has none, the owner-configured
`tools.mcp_permissions` (default read + compute, no mutation). No call/time budgets. Meta-tools are not registry
entries, so a call cannot recurse into them.
"""
from __future__ import annotations

import json
import re
import threading

from backend.tools.registry import REGISTRY
from backend.tools.runtime import RUNTIME, TERMINAL, Grant
from backend.tools.spec import ToolError

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
                    "status, result or a structured error with a hint. Waits up to wait_s seconds (default 45); a tool "
                    "still running then returns status 'running': poll it with phdlab_tools_job. Every call is recorded "
                    "with provenance.",
     "inputSchema": {"type": "object", "required": ["tool"], "additionalProperties": False, "properties": {
         "tool": {"type": "string", "maxLength": 120}, "version": {"type": "string", "maxLength": 40},
         "args": {"type": "object"}, "wait_s": {"type": "number"}}}},
    {"name": "phdlab_tools_job", "group": "read",
     "description": "Status, observations and result of a phdlab_tools_call job you started, waiting up to wait_s seconds "
                    "(default 45) for it to finish; action 'cancel' stops it.",
     "inputSchema": {"type": "object", "required": ["job"], "additionalProperties": False, "properties": {
         "job": {"type": "string", "maxLength": 40}, "action": {"type": "string", "enum": ["status", "cancel"]},
         "wait_s": {"type": "number"}}}},
]
DEFAULT_WAIT_S = 45.0
MAX_WAIT_S = 300.0
JOB_ID = re.compile(r"^tj-[0-9a-f]{20}$")
NAMES = {t["name"] for t in TOOLS}
_grants: dict[str, Grant] = {}
_lock = threading.Lock()


def grant_for(client: dict) -> Grant:
    """v6.6.2: authority comes from the owner's profiles (tools.client_profiles / tools.agent_profile), no budgets.
    A PhD-Lab-issued ephemeral session grant (CLI agents, Hermes) runs under the agent profile, scoped to the registry
    patterns issued with it (agent mode) or else to its own MCP tool list."""
    from backend.tools import profiles
    session = str(client.get("session") or client.get("name") or "mcp-client")[:80]
    name = str(client.get("name") or "client")[:60]
    ephemeral = client.get("grant")
    principal = f"mcp:{name}:{session}"
    base = profiles.agent_grant(principal) if ephemeral else profiles.client_grant(name, principal)
    tools = sorted(ephemeral.get("registry", ephemeral["tools"])) if ephemeral else base.tools
    key = json.dumps([principal, tools, base.permissions])
    with _lock:
        g = _grants.get(key)
        if g is None:
            g = base.model_copy(update={"tools": tools})
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


def bounded_wait(value) -> float:
    try:
        return min(MAX_WAIT_S, max(0.0, float(value)))
    except (TypeError, ValueError):
        return DEFAULT_WAIT_S


def _job_view(job: dict) -> dict:
    obj = {"job": job["id"], "tool": f"{job['tool']}@{job.get('version', '')}", "status": job["status"],
           "result": job["result"], "error": job["error"]}
    if job["status"] not in TERMINAL:
        obj["observations"] = job.get("observations", [])[-10:]
        obj["hint"] = (f"Still {job['status']}. Call phdlab_tools_job with job '{job['id']}' to wait for the result, "
                       "or with action 'cancel' to stop it.")
    return obj


def _own_job(job_id: str, client: dict) -> dict:
    """Another principal's job looks exactly like a missing one, so ids cannot be probed."""
    missing = ToolError("not_found", f"No tool job {job_id} for this client")
    if not JOB_ID.match(job_id):
        raise missing
    job = RUNTIME.get(job_id)
    if job.get("principal") != grant_for(client).principal:
        raise missing
    return job


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
            job = RUNTIME.submit(str(args.get("tool", "")), args.get("args") if isinstance(args.get("args"), dict) else {},
                                 grant_for(client), version=str(args.get("version", "")))
            if job["status"] not in TERMINAL:
                job = RUNTIME.wait(job["id"], bounded_wait(args.get("wait_s", DEFAULT_WAIT_S)))
            return _result(_job_view(job), error=job["status"] in TERMINAL and job["status"] != "succeeded")
        if name == "phdlab_tools_job":
            job = _own_job(str(args.get("job", "")), client)
            if args.get("action") == "cancel" and job["status"] not in TERMINAL:
                RUNTIME.cancel(job["id"])
            if job["status"] not in TERMINAL:
                job = RUNTIME.wait(job["id"], bounded_wait(args.get("wait_s", DEFAULT_WAIT_S)))
            return _result(_job_view(job), error=job["status"] in TERMINAL and job["status"] != "succeeded")
    except ToolError as e:
        return _result({"error": e.as_dict()}, error=True)
    raise ValueError(f"Unknown registry bridge tool {name}")
