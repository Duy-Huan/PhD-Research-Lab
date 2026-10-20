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

from . import ide_fs, sandbox
from .config import APP_VERSION

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
    from .config import load_config
    return load_config()["mcp"]


def tool_list() -> list:
    from .gateway.mcp_tools import listed
    m = _mcfg()
    return listed(m) + (TOOLS if m.get("expose_sandbox", True) else [])


def guard(headers: dict, client: str) -> tuple[int, str]:
    """(0, "") when the request may proceed, else (HTTP status, reason)."""
    m = _mcfg()
    if not m.get("enabled", True):
        return 403, "MCP is disabled in the configuration"
    origin = (headers.get("origin") or "").strip().lower()
    if origin and origin != "null" and not any(origin == o or origin.startswith(o + ":") for o in LOCAL_ORIGINS):
        return 403, "Origin not allowed"
    tok = m.get("token") or ""
    if tok:
        got = (headers.get("authorization") or "")
        got = got[7:].strip() if got.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(got.encode(), tok.encode()):
            return 401, "MCP token required (Authorization: Bearer <token>)"
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
    from .config import data_dir
    try:
        d = data_dir() / "gateway"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "mcp_audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": round(time.time(), 3), **rec}) + "\n")
    except OSError:
        pass


def call_tool(name: str, args: dict, client: dict | None = None) -> dict:
    if name.startswith("research_") or name.startswith("research."):
        from .gateway.mcp_tools import call
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
        job = sandbox.run_blocking(cmd, timeout, "run", f"MCP: {cmd[:60]}")
        return _text({"run_id": job.id, "status": job.status, "exit_code": job.exit_code, "mode": job.mode,
                      "stdout": job.tail(120, "out")[-12000:], "stderr": job.tail(80, "err")[-8000:],
                      "metrics": (job.meta or {}).get("metrics", {}), "figures": (job.meta or {}).get("figures", [])})
    if name == "sandbox_manage_files":
        a = args.get("action")
        if a == "list":
            return _text(ide_fs.tree())
        if a == "read":
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
            SESSIONS[sid] = {"name": str(ci.get("name") or "mcp-client")[:60], "version": str(ci.get("version") or "")[:30],
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
            res = {"tools": tool_list()}
        elif method == "tools/call":
            name = str(params.get("name") or "")
            client = {**SESSIONS.get(session, {"name": "mcp-client"}), "session": session}
            t0 = time.perf_counter()
            ok, err = True, ""
            try:
                res = call_tool(name, params.get("arguments") or {}, client)
            except Exception as e:
                ok, err = False, type(e).__name__
                from .telemetry import redact
                res = {"isError": True, "content": [{"type": "text", "text": redact(f"{type(e).__name__}: {e}")[:2000]}]}
            args = params.get("arguments") or {}
            audit({"tool": name[:64], "client": client.get("name", ""), "session": session[:40], "ok": ok, "error": err,
                   "arg_keys": sorted(args)[:20] if isinstance(args, dict) else [],
                   "latency_ms": round((time.perf_counter() - t0) * 1000, 1)})
            try:
                from .telemetry import record
                record({"ts": round(time.time(), 3), "operation": "mcp.tool", "tool": name[:64], "client": client.get("name", "")[:60],
                        "ok": ok, "latency_ms": round((time.perf_counter() - t0) * 1000, 2)})
            except Exception:
                pass
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": res}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
