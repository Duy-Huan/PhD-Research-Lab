"""MCP server (v3.0): the sandbox exposed as Model Context Protocol tools over JSON-RPC 2.0 (HTTP POST /mcp).

Tools: sandbox_run_code, sandbox_manage_files, sandbox_get_metrics.
Any MCP client that speaks Streamable HTTP can connect to http://127.0.0.1:<port>/mcp (local machine only).
Clients that only support stdio (e.g. Claude Desktop) can use mcp_stdio_bridge.py — see the Guide.
"""
from __future__ import annotations

import json

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


def call_tool(name: str, args: dict) -> dict:
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


def handle(msg: dict) -> dict | None:
    """One JSON-RPC message → response (None for notifications)."""
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None  # notification (e.g. notifications/initialized)
    try:
        if method == "initialize":
            res = {"protocolVersion": params.get("protocolVersion") or PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "phd-research-lab-sandbox", "version": APP_VERSION},
                   "instructions": "Research sandbox of PhD Research Lab: run code, manage workspace files, read metrics."}
        elif method == "ping":
            res = {}
        elif method == "tools/list":
            res = {"tools": TOOLS}
        elif method == "tools/call":
            try:
                res = call_tool(params.get("name"), params.get("arguments") or {})
            except Exception as e:
                res = {"isError": True, "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}]}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": res}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
