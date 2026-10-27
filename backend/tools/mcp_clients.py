"""Register PhD Lab as an MCP server in interactive agent clients the researcher drives (Antigravity IDE/CLI).

The researcher runs the client under their own account; the client calls PhD Lab (its research_* tools and the
registry meta-tools phdlab_tools_*). PhD Lab never launches or drives the client, which is the direction Antigravity's
terms permit. Registration edits only the client's documented MCP config file:

  ~/.gemini/config/mcp_config.json   {"mcpServers": {"phd-research-lab": {"serverUrl": "http://127.0.0.1:<port>/mcp"}}}

Other configured servers are preserved, a non-empty file is backed up before writing, and a file that is not valid
JSON is never overwritten. The local endpoint is loopback-only; a bearer header is added only when the owner set
mcp.token.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

from backend.tools.spec import ToolError

SERVER = "phd-research-lab"


def antigravity_config() -> Path:
    from backend.providers.cli import get
    return get("antigravity").config_path()


def _local_mcp_url(url: str) -> str:
    u = urlsplit(url)
    if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost") or not u.port or u.path.rstrip("/") != "/mcp" \
            or u.username or u.password or u.query or u.fragment:
        raise ToolError("invalid_input", "PhD Lab MCP URL must be http://127.0.0.1:<port>/mcp")
    return url


def _read(path: Path) -> dict:
    if not path.is_file() or not path.read_text("utf-8").strip():
        return {}
    try:
        data = json.loads(path.read_text("utf-8"))
    except ValueError as e:
        raise ToolError("invalid_input", f"{path} is not valid JSON; it was left unchanged. Fix or remove it first") from e
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        raise ToolError("invalid_input", f"{path} has an unexpected structure; it was left unchanged")
    return data


def _write(path: Path, data: dict) -> str:
    backup = ""
    if path.is_file() and path.read_text("utf-8").strip():
        backup = str(path.with_name(f"{path.name}.phdlab-backup-{int(time.time())}"))
        Path(backup).write_bytes(path.read_bytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), "utf-8")
    os.replace(tmp, path)
    return backup


def register_antigravity(url: str) -> dict:
    from backend.core.config import load_config
    url = _local_mcp_url(url)
    path = antigravity_config()
    data = _read(path)
    entry = {"serverUrl": url, "timeoutSeconds": 600}
    token = (load_config().get("mcp") or {}).get("token") or ""
    if token:
        entry["headers"] = {"Authorization": "Bearer " + token}
    data.setdefault("mcpServers", {})[SERVER] = entry
    backup = _write(path, data)
    return {"client": "antigravity", "path": str(path), "server": SERVER, "url": url, "backup": backup,
            "authorization_header": bool(token),
            "next": "Restart Antigravity (or reload MCP servers), then ask it to use phdlab_tools_search"}


def unregister_antigravity() -> dict:
    path = antigravity_config()
    data = _read(path)
    removed = (data.get("mcpServers") or {}).pop(SERVER, None) is not None
    backup = _write(path, data) if removed else ""
    return {"client": "antigravity", "path": str(path), "removed": removed, "backup": backup}


def status() -> dict:
    path = antigravity_config()
    try:
        entry = (_read(path).get("mcpServers") or {}).get(SERVER)
        error = ""
    except ToolError as e:
        entry, error = None, e.message
    return {"antigravity": {"path": str(path), "registered": bool(entry), "url": (entry or {}).get("serverUrl", ""),
                            "error": error}}
