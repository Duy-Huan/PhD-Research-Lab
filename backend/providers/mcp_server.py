"""MCP server: research memory + sandbox as Model Context Protocol tools over JSON-RPC 2.0 (HTTP POST /mcp).

Tools
    research_*   (v3.4) the shared research brain: state, memory search, hypotheses, experiments, evidence, decisions,
                 failures, compiled context, provenance; record_* tools only create review candidates (gateway/mcp_tools.py)
    sandbox_*    (v3.0) run code, manage workspace files, read metrics — switchable with mcp.expose_sandbox
Any MCP client that speaks Streamable HTTP can connect to http://127.0.0.1:<port>/mcp (local machine only).
Clients that only support stdio (e.g. Claude Desktop, Codex) can use mcp_stdio_bridge.py — see the Guide.

Security (v3.4 §18, enforced in guard()): localhost-only Host (app middleware) + Origin validation (DNS rebinding),
optional bearer token (mcp.token), per-client rate limit, input validation, audit log without argument values.
"""
from __future__ import annotations

import hmac
import json
import secrets
import threading
import time

from backend.execution import files as ide_fs, sandbox
from backend.core.config import APP_VERSION

PROTOCOL = "2025-06-18"

TOOLS = [
    {"name": "sandbox_run_code",
     "description": "Run Python code or a shell command in the research sandbox (Docker container with GPU when available, "
                    "working directory = project code workspace). Returns exit code, stdout/stderr tails, metrics and figures.",
     "inputSchema": {"type": "object", "properties": {
         "code": {"type": "string", "description": "Python source to run (saved as _mcp_snippet.py)"},
         "command": {"type": "string", "description": "Shell command instead of code, e.g. 'python train.py --epochs 1'"},
         "timeout": {"type": "integer", "description": "seconds (default 600, max 3600)"}}}},
    {"name": "sandbox_manage_files",
     "description": "List, read, write or delete files in the project code workspace.",
     "inputSchema": {"type": "object", "required": ["action"], "properties": {
         "action": {"type": "string", "enum": ["list", "read", "write", "delete", "search"]},
         "path": {"type": "string"}, "content": {"type": "string"}, "query": {"type": "string"}}}},
    {"name": "sandbox_get_metrics",
     "description": "Metrics of a run (metrics.json + values parsed from the log), or the best metric values over all runs.",
     "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string", "description": "omit for best metrics + recent runs"}}}},
]


def _text(obj) -> dict:
    return {"content": [{"type": "text", "text": obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=1)}]}


SANDBOX_NAMES = {t["name"] for t in TOOLS}
SESSIONS: dict = {}   # Mcp-Session-Id → clientInfo (name/version) for provenance + audit
_rl: dict = {}
_rl_lock = threading.Lock()
LOCAL_ORIGINS = ("http://localhost", "http://127.0.0.1", "https://localhost", "https://127.0.0.1", "http://[::1]")


def _mcfg() -> dict:
    from backend.core.config import load_config
    return load_config()["mcp"]


def sandbox_tools() -> list:
    """TOOLS with the shell note on sandbox_run_code, computed per call; the shared list is never modified."""
    note = sandbox.shell_note()
    return [{**t, "description": f"{t['description']} {note}"} if t["name"] == "sandbox_run_code" else t for t in TOOLS]


def tool_list() -> list:
    from backend.providers.mcp_tools import listed
    m = _mcfg()
    out = listed(m) + (sandbox_tools() if m.get("expose_sandbox", True) else [])
    if _registry_enabled():  # v6.6.0: the native tool registry for external agent clients
        from backend.tools.mcp_bridge import TOOLS as BRIDGE
        out += [{k: v for k, v in t.items() if k != "group"} for t in BRIDGE]
    return out


def _registry_enabled() -> bool:
    from backend.core.config import load_config
    return bool((load_config().get("tools") or {}).get("mcp_registry", True))


def guard(headers: dict, client: str) -> tuple[int, str]:
    """(0, "") when the request may proceed, else (HTTP status, reason)."""
    m = _mcfg()
    if not m.get("enabled", True):
        return 403, "MCP is disabled in the configuration"
    origin = (headers.get("origin") or "").strip().lower()
    if origin and origin != "null" and not any(origin == o or origin.startswith(o + ":") for o in LOCAL_ORIGINS):
        return 403, "Origin not allowed"
    tok = m.get("token") or ""
    got = (headers.get("authorization") or "")
    got = got[7:].strip() if got.lower().startswith("bearer ") else ""
    from backend.agent.mcp_policy import lookup
    grant = lookup(got)
    if (tok or got) and not grant and not (tok and hmac.compare_digest(got.encode(), tok.encode())):
        return 401, "A valid project-scoped MCP token is required"
    limit = int(m.get("rate_limit_per_min") or 0)
    if limit > 0:
        now = time.time()
        with _rl_lock:
            win = [t for t in _rl.get(client, []) if now - t < 60]
            if len(win) >= limit:
                _rl[client] = win
                return 429, "Rate limit exceeded"
            win.append(now)
            _rl[client] = win
    return 0, ""


def audit(rec: dict) -> None:
    if not _mcfg().get("audit", True):
        return
    from backend.core.config import data_dir
    try:
        d = data_dir() / "gateway"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "mcp_audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": round(time.time(), 3), **rec}) + "\n")
    except OSError:
        pass


def call_tool(name: str, args: dict, client: dict | None = None) -> dict:
    if name.startswith("phdlab_tools_"):
        from backend.tools.mcp_bridge import NAMES, call
        if name in NAMES and _registry_enabled():
            return call(name, args, client)
        raise ValueError(f"Unknown tool {name}")
    if name.startswith("research_") or name.startswith("research."):
        from backend.providers.mcp_tools import call
        return call(name, args, client)
    if name in SANDBOX_NAMES and not _mcfg().get("expose_sandbox", True):
        raise PermissionError(f"{name} is disabled (mcp.expose_sandbox)")
    if name == "sandbox_run_code":
        cmd = (args.get("command") or "").strip()
        if not cmd:
            code = args.get("code") or ""
            if not code.strip():
                raise ValueError("Give 'code' or 'command'")
            ide_fs.write("_mcp_snippet.py", code)
            cmd = "python _mcp_snippet.py"
        timeout = max(5, min(3600, int(args.get("timeout") or 600)))
        from backend.providers.lifecycle import sandbox_lease
        with sandbox_lease():  # v4.1: the container follows lifecycle.mcp (stop after task / idle / keep running)
            job = sandbox.run_blocking(cmd, timeout, "run", f"MCP: {cmd[:60]}")
        return _text({"run_id": job.id, "status": job.status, "exit_code": job.exit_code, "mode": job.mode,
                      "stdout": job.tail(120, "out")[-12000:], "stderr": job.tail(80, "err")[-8000:],
                      "metrics": (job.meta or {}).get("metrics", {}), "figures": (job.meta or {}).get("figures", [])})
    if name == "sandbox_manage_files":
        a = args.get("action")
        if a == "list":
            return _text(ide_fs.tree())
        if a == "read":
            from backend.providers.privacy import gw
            if gw().get("block_source_code", False):
                raise PermissionError("Source file reads are disabled by gateway.block_source_code")
            return _text(ide_fs.read(args.get("path", "")).get("content", "(binary file)"))
        if a == "write":
            return _text(ide_fs.write(args.get("path", ""), args.get("content", "")))
        if a == "delete":
            return _text(ide_fs.delete(args.get("path", "")))
        if a == "search":
            return _text(ide_fs.search(args.get("query", "")))
        raise ValueError("Unknown action")
    if name == "sandbox_get_metrics":
        rid = args.get("run_id")
        if rid:
            r = sandbox.get_run(rid)
            return _text({k: r.get(k) for k in ("id", "status", "exit_code", "metrics", "figures", "parsed")})
        return _text({"best": sandbox.best_metrics(), "recent_runs": sandbox.list_runs(10)})
    raise ValueError(f"Unknown tool {name}")


INSTRUCTIONS = ("PhD Research Lab — the researcher's local research memory. Start with research_get_current_state, use "
                "research_search_memory / research_get_* for details and cite record ids. research_record_* tools only "
                "create review candidates: tell the researcher they must approve them in PhD-Lab. Sandbox tools (if listed) "
                "run code in the project's workspace.")


def handle(msg: dict, session: str = "", meta: dict | None = None) -> dict | None:
    """One JSON-RPC message → response (None for notifications). meta receives {session_id} on initialize."""
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None  # notification (e.g. notifications/initialized)
    try:
        if method == "initialize":
            ci = params.get("clientInfo") or {}
            sid = "mcp-" + secrets.token_hex(8)
            # An authenticated gateway (v6.6.2 ChatGPT) fixes the client identity; clientInfo cannot spoof it.
            name = (meta or {}).get("client_name") or ci.get("name") or "mcp-client"
            SESSIONS[sid] = {"name": str(name)[:60], "version": str(ci.get("version") or "")[:30],
                             "started": time.time()}
            while len(SESSIONS) > 500:
                SESSIONS.pop(next(iter(SESSIONS)))
            if meta is not None:
                meta["session_id"] = sid
            res = {"protocolVersion": params.get("protocolVersion") or PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "phd-research-lab", "version": APP_VERSION}, "instructions": INSTRUCTIONS}
        elif method == "ping":
            res = {}
        elif method == "tools/list":
            g = (meta or {}).get("grant")
            only = (meta or {}).get("only_tools")
            res = {"tools": [t for t in tool_list() if (not g or t["name"] in g["tools"]) and (only is None or t["name"] in only)]}
        elif method == "tools/call":
            name = str(params.get("name") or "")
            g = (meta or {}).get("grant")
            client = {**SESSIONS.get(session, {"name": "mcp-client"}), "session": session, "grant": g}
            if (meta or {}).get("client_name"):  # gateway-authenticated identity wins over any session record
                client["name"] = meta["client_name"]
            t0 = time.perf_counter()
            ok, err = True, ""
            try:
                if g and name not in g["tools"]:  # v4.2: outside the session's MCP allowlist
                    raise PermissionError(f"{name} is not allowed in this AI workspace session")
                only = (meta or {}).get("only_tools")
                if only is not None and name not in only:
                    raise PermissionError(f"{name} is not exposed to this client")
                res = call_tool(name, params.get("arguments") or {}, client)
            except Exception as e:
                ok, err = False, type(e).__name__
                from backend.core.telemetry import redact
                res = {"isError": True, "content": [{"type": "text", "text": redact(f"{type(e).__name__}: {e}")[:2000]}]}
            args = params.get("arguments") or {}
            audit({"tool": name[:64], "client": client.get("name", ""), "session": session[:40], "ok": ok, "error": err,
                   "arg_keys": sorted(args)[:20] if isinstance(args, dict) else [],
                   "latency_ms": round((time.perf_counter() - t0) * 1000, 1)})
            try:
                from backend.core.telemetry import record
                record({"ts": round(time.time(), 3), "operation": "mcp.tool", "tool": name[:64], "client": client.get("name", "")[:60],
                        "ok": ok, "latency_ms": round((time.perf_counter() - t0) * 1000, 2)})
            except Exception:
                pass
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": res}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
