"""Optional Google Colab and Google Drive MCP tools, isolated to one dedicated folder per project.

Servers (both OFF until the researcher enables them):
  google_colab  official googlecolab/colab-mcp, a LOCAL stdio bridge to a Colab notebook open in the researcher's
                browser (`uvx git+https://github.com/googlecolab/colab-mcp`). Code it runs executes in that Colab
                runtime, not on this machine.
  google_drive  official Google Workspace remote MCP server https://drivemcp.googleapis.com/mcp/v1 (Developer Preview,
                Streamable HTTP, OAuth 2.0 with drive.readonly + drive.file).

Isolation ("Google MCP is confined to its own folder"):
  local   everything Google lives in <project data>/google_mcp/ (settings, OAuth client/token in secrets/, Colab bridge
          working dir/HOME/caches/temp in colab/). The Colab process gets an allowlisted environment without PhD Lab,
          provider or GitHub credentials, and advertises only colab/ as its MCP root.
  drive   every Drive call passes FolderGuard, default-deny: reads/downloads/permissions/copies must prove the file is
          inside the configured Drive folder (parent chain via get_file_metadata, bounded depth); create/copy are forced
          to that folder as parent; search/list results are filtered to it; unknown tools are not exposed. When the
          guard cannot prove containment (unknown schema/response shape) the call is refused.
  token   the Drive OAuth token is sent only to *.googleapis.com (loopback only in an explicit test setting) and only by
          application-defined specs; manifests and snapshots cannot reference it.
Google's own scopes still allow the token to read the whole Drive; the folder boundary is enforced by this
application, not by Google. That is defense in depth, reported as such.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from backend.tools.spec import ToolError, ToolSpec

DRIVE_ENDPOINT = "https://drivemcp.googleapis.com/mcp/v1"
COLAB_COMMAND = ["uvx", "git+https://github.com/googlecolab/colab-mcp"]
SCOPES = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/drive.file"]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SERVERS = ("google_colab", "google_drive")
DRIVE_POLICY = {"search_files": "filter", "list_recent_files": "filter", "get_file_metadata": "contain",
                "read_file_content": "contain", "download_file_content": "contain", "get_file_permissions": "contain",
                "create_file": "parent", "copy_file": "contain+parent"}
ID_ARGS = ("fileId", "file_id", "id", "sourceFileId", "source_file_id")
PARENT_ARGS = ("parentId", "parent_id", "parents", "folderId", "folder_id", "parentFolderId", "parent_folder_id",
               "destinationFolderId", "destination_folder_id")
FOLDER_ID = re.compile(r"^[A-Za-z0-9_-]{10,200}$")
_lock = threading.Lock()


# ------------------------------------------------------------------ isolated folder and settings
def root() -> Path:
    from backend.core.config import data_dir
    base = data_dir() / "google_mcp"
    for sub in ("colab", "drive", "secrets", "logs"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def _read(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), "utf-8")
    os.replace(tmp, path)


def settings() -> dict:
    s = _read(root() / "settings.json", {})
    colab = {"enabled": False, "command": COLAB_COMMAND, **(s.get("colab") or {})}
    drive = {"enabled": False, "endpoint": DRIVE_ENDPOINT, "folder_id": "", "allow_loopback_endpoint": False,
             **(s.get("drive") or {})}
    return {"colab": colab, "drive": drive}


def save_settings(patch: dict) -> dict:
    current = settings()
    for server in ("colab", "drive"):
        for key, value in ((patch or {}).get(server) or {}).items():
            if key == "enabled":
                if not isinstance(value, bool):
                    raise ToolError("invalid_input", f"{server}.enabled must be true or false")
            elif server == "colab" and key == "command":
                if not isinstance(value, list) or not 1 <= len(value) <= 20 or not all(isinstance(x, str) and x for x in value):
                    raise ToolError("invalid_input", "colab.command must be a non-empty list of arguments (no shell)")
            elif server == "drive" and key == "folder_id":
                if value and not FOLDER_ID.match(str(value)):
                    raise ToolError("invalid_input", "drive.folder_id must be a Google Drive folder id")
            elif server == "drive" and key == "endpoint":
                _drive_url(str(value), current["drive"].get("allow_loopback_endpoint", False))
            elif server == "drive" and key == "allow_loopback_endpoint":
                if not isinstance(value, bool):
                    raise ToolError("invalid_input", "allow_loopback_endpoint must be a boolean")
            else:
                raise ToolError("invalid_input", f"Unknown Google MCP setting {server}.{key}")
            current[server][key] = value
    if current["drive"]["enabled"] and not current["drive"]["folder_id"]:
        raise ToolError("invalid_input", "Drive needs a dedicated folder_id before it can be enabled (folder isolation)")
    _write(root() / "settings.json", current)
    return status()


def _drive_url(url: str, allow_loopback: bool) -> str:
    u = urlsplit(url)
    if u.username or u.password or u.query or u.fragment:
        raise ToolError("invalid_input", "Drive endpoint must not contain credentials, query or fragment")
    if u.scheme == "https" and (u.hostname or "").endswith(".googleapis.com"):
        return url
    if allow_loopback and u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1"):
        return url
    raise ToolError("invalid_input", "Drive endpoint must be an https://*.googleapis.com MCP server")


# ------------------------------------------------------------------ Drive OAuth (authorization code + PKCE)
def save_oauth_client(client_id: str, client_secret: str) -> dict:
    if not re.fullmatch(r"[\w.-]{10,200}\.apps\.googleusercontent\.com", client_id or ""):
        raise ToolError("invalid_input", "client_id must be a Google OAuth client id (*.apps.googleusercontent.com)")
    if not (client_secret or "").strip():
        raise ToolError("invalid_input", "client_secret is required (Web application client)")
    _write(root() / "secrets" / "oauth_client.json", {"client_id": client_id, "client_secret": client_secret})
    return {"saved": True}


def oauth_start(redirect_uri: str) -> dict:
    client = _read(root() / "secrets" / "oauth_client.json", None)
    if not client:
        raise ToolError("invalid_input", "Save a Google OAuth client first")
    u = urlsplit(redirect_uri)
    if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost"):
        raise ToolError("invalid_input", "OAuth redirect must return to this local application")
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(24)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    _write(root() / "secrets" / "oauth_pending.json", {"state": state, "verifier": verifier,
                                                       "redirect_uri": redirect_uri, "created": time.time()})
    query = {"client_id": client["client_id"], "redirect_uri": redirect_uri, "response_type": "code",
             "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "state": state,
             "code_challenge": challenge, "code_challenge_method": "S256"}
    return {"auth_url": AUTH_URL + "?" + urlencode(query), "scopes": SCOPES}


def _token_request(data: dict) -> dict:
    import httpx
    try:
        r = httpx.post(TOKEN_URL, data=data, timeout=30, trust_env=False)
    except httpx.HTTPError as e:
        raise ToolError("unavailable", "Google token endpoint unreachable", retryable=True) from e
    if r.status_code != 200:
        raise ToolError("permission_denied", f"Google token exchange failed (HTTP {r.status_code})",
                        hint="Re-authorize Google Drive in Settings")
    return r.json()


def oauth_finish(code: str, state: str) -> dict:
    pending = _read(root() / "secrets" / "oauth_pending.json", None)
    client = _read(root() / "secrets" / "oauth_client.json", None)
    if not pending or not client or not secrets.compare_digest(str(state), pending["state"]) \
            or time.time() - pending["created"] > 900:
        raise ToolError("permission_denied", "OAuth state mismatch or expired; start authorization again")
    token = _token_request({"code": code, "client_id": client["client_id"], "client_secret": client["client_secret"],
                            "redirect_uri": pending["redirect_uri"], "grant_type": "authorization_code",
                            "code_verifier": pending["verifier"]})
    (root() / "secrets" / "oauth_pending.json").unlink(missing_ok=True)
    _save_token(token)
    return {"authorized": True, "scope": token.get("scope", "")}


def _save_token(token: dict, previous: dict | None = None) -> None:
    stored = {"access_token": token["access_token"], "expires_at": time.time() + int(token.get("expires_in", 3600)) - 60,
              "refresh_token": token.get("refresh_token") or (previous or {}).get("refresh_token", ""),
              "scope": token.get("scope", (previous or {}).get("scope", ""))}
    _write(root() / "secrets" / "drive_token.json", stored)


def access_token() -> str:
    with _lock:
        token = _read(root() / "secrets" / "drive_token.json", None)
        if not token:
            raise ToolError("unavailable", "Google Drive is not authorized", hint="Authorize Google Drive in Settings")
        if token["expires_at"] > time.time():
            return token["access_token"]
        client = _read(root() / "secrets" / "oauth_client.json", None)
        if not token.get("refresh_token") or not client:
            raise ToolError("unavailable", "Google Drive authorization expired", hint="Authorize Google Drive again")
        fresh = _token_request({"refresh_token": token["refresh_token"], "client_id": client["client_id"],
                                "client_secret": client["client_secret"], "grant_type": "refresh_token"})
        _save_token(fresh, token)
        return fresh["access_token"]


def auth_headers(provider: str, url: str) -> dict:
    if provider != "google_drive":
        raise ToolError("invalid_spec", "Unknown application token provider")
    _drive_url(url, settings()["drive"]["allow_loopback_endpoint"])  # the token never leaves for another host
    return {"Authorization": "Bearer " + access_token()}


# ------------------------------------------------------------------ Colab: owned stdio MCP server process
class StdioServer:
    """Long-lived owned MCP server over newline-delimited JSON-RPC on stdin/stdout."""

    def __init__(self, name: str, argv: list, cwd: Path, env: dict):
        self.name, self.argv, self.cwd, self.env = name, argv, cwd, env
        self.proc, self.seq, self.replies = None, 0, {}
        self.cond = threading.Condition()
        self.tools_changed = False
        self.write_lock = threading.Lock()

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, timeout: float = 60) -> None:
        log = (self.cwd.parent / "logs" / f"{self.name}.log").open("ab")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                         cwd=str(self.cwd), env=self.env, creationflags=flags)
        except OSError as e:
            raise ToolError("unavailable", f"Could not start {self.name}: {type(e).__name__}",
                            hint="Install uv (uvx) or set the Colab MCP command in Settings") from e
        finally:
            log.close()
        threading.Thread(target=self._read, daemon=True, name=f"mcp-{self.name}").start()
        init = self.request("initialize", {"protocolVersion": "2025-06-18", "clientInfo": {"name": "phdlab-tool-runtime", "version": "1"},
                                           "capabilities": {"roots": {"listChanged": False}}}, timeout)
        if init.get("protocolVersion") not in ("2024-11-05", "2025-03-26", "2025-06-18"):
            self.stop()
            raise ToolError("incompatible_version", "Unsupported MCP protocol version from local server")
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def _send(self, msg: dict) -> None:
        if not self.alive:
            raise ToolError("unavailable", f"{self.name} is not running", retryable=True)
        with self.write_lock:
            self.proc.stdin.write((json.dumps(msg) + "\n").encode())
            self.proc.stdin.flush()

    def _read(self) -> None:
        for line in iter(self.proc.stdout.readline, b""):
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            method = msg.get("method")
            if method and "id" in msg:  # server -> client request: answer only what this client supports
                result = {"roots": [{"uri": self.cwd.resolve().as_uri(), "name": "isolated Google MCP folder"}]} \
                    if method == "roots/list" else {} if method == "ping" else None
                reply = {"jsonrpc": "2.0", "id": msg["id"]}
                reply.update({"result": result} if result is not None else
                             {"error": {"code": -32601, "message": "Method not supported by this client"}})
                try:
                    self._send(reply)
                except (ToolError, OSError):
                    pass
            elif method == "notifications/tools/list_changed":
                self.tools_changed = True
            elif "id" in msg:
                with self.cond:
                    self.replies[msg["id"]] = msg
                    self.cond.notify_all()
        with self.cond:
            self.cond.notify_all()

    def request(self, method: str, params: dict, timeout: float = 60) -> dict:
        with self.cond:
            self.seq += 1
            rid = self.seq
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        end = time.monotonic() + timeout
        with self.cond:
            while rid not in self.replies:
                if not self.alive:
                    raise ToolError("unavailable", f"{self.name} exited", retryable=True)
                if time.monotonic() >= end:
                    raise ToolError("timeout", f"{self.name} did not answer {method} in time", retryable=True)
                self.cond.wait(min(0.5, max(0.01, end - time.monotonic())))
            msg = self.replies.pop(rid)
        if "error" in msg:
            raise ToolError("execution_failed", f"{self.name}: {str((msg['error'] or {}).get('message', ''))[:300]}")
        if not isinstance(msg.get("result"), dict):
            raise ToolError("invalid_output", f"{self.name} returned a malformed result")
        return msg["result"]

    def list_tools(self) -> list:
        tools, cursor = [], None
        for _ in range(10):
            page = self.request("tools/list", {"cursor": cursor} if cursor else {})
            tools += [t for t in page.get("tools") or [] if isinstance(t, dict)]
            cursor = page.get("nextCursor")
            if not cursor:
                break
        self.tools_changed = False
        return tools

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            from backend.tools.adapters import _kill_tree
            _kill_tree(self.proc)
            self.proc.wait(timeout=15)
        for pipe in (self.proc.stdin, self.proc.stdout):
            try:
                pipe.close()
            except OSError:
                pass


_servers: dict[str, StdioServer] = {}


def colab_env(folder: Path) -> dict:
    """Allowlisted environment: PATH/system variables only; every home/cache/temp location inside the folder."""
    keep = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL", "TZ")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    for sub in ("home", "cache", "tmp", "appdata", "localappdata"):
        (folder / sub).mkdir(exist_ok=True)
    env.update(HOME=str(folder / "home"), USERPROFILE=str(folder / "home"), APPDATA=str(folder / "appdata"),
               LOCALAPPDATA=str(folder / "localappdata"), XDG_CACHE_HOME=str(folder / "cache"),
               XDG_CONFIG_HOME=str(folder / "home"), XDG_DATA_HOME=str(folder / "home"), UV_CACHE_DIR=str(folder / "cache" / "uv"),
               TMP=str(folder / "tmp"), TEMP=str(folder / "tmp"), TMPDIR=str(folder / "tmp"), PYTHONIOENCODING="utf-8",
               PYTHONNOUSERSITE="1")
    return env


def stdio_server(name: str, timeout: float = 120) -> StdioServer:
    if name != "google_colab":
        raise ToolError("invalid_spec", "Unknown application stdio server")
    s = settings()["colab"]
    if not s["enabled"]:
        raise ToolError("unavailable", "Google Colab MCP is disabled", hint="Enable it in Settings > Tools > Google")
    folder = root() / "colab"
    key = f"{name}:{folder.resolve()}"
    with _lock:
        server = _servers.get(key)
        if server is None or not server.alive or server.argv != s["command"]:
            if server:
                server.stop()
            server = StdioServer(name, list(s["command"]), folder, colab_env(folder))
            server.start(timeout)
            _servers[key] = server
    return server


def stop_servers() -> list:
    with _lock:
        stopped = list(_servers)
        for s in _servers.values():
            s.stop()
        _servers.clear()
    return stopped


# ------------------------------------------------------------------ discovery and registry specs
def discover(server: str) -> dict:
    if server not in SERVERS:
        raise ToolError("not_found", f"Unknown Google MCP server {server}")
    if server == "google_colab":
        tools = stdio_server("google_colab").list_tools()
    else:
        from backend.tools.adapters import McpSession
        d = settings()["drive"]
        if not d["enabled"]:
            raise ToolError("unavailable", "Google Drive MCP is disabled")
        url = _drive_url(d["endpoint"], d["allow_loopback_endpoint"])
        with McpSession(url, 30, auth_headers("google_drive", url)) as session:
            tools = session.list_tools()
    keep = [{"name": t.get("name"), "description": t.get("description", ""), "title": t.get("title", ""),
             "inputSchema": t.get("inputSchema") or {"type": "object"}, "annotations": t.get("annotations") or {}}
            for t in tools if isinstance(t.get("name"), str)]
    folder = "colab" if server == "google_colab" else "drive"
    _write(root() / folder / "tools.json", {"server": server, "discovered_at": time.time(), "tools": keep})
    exposed = [t["name"] for t in keep if server == "google_colab" or t["name"] in DRIVE_POLICY]
    return {"server": server, "discovered": [t["name"] for t in keep], "exposed": exposed,
            "withheld": [t["name"] for t in keep if t["name"] not in exposed]}


def _snapshot(folder: str) -> list:
    return [t for t in (_read(root() / folder / "tools.json", {}) or {}).get("tools", []) if isinstance(t, dict)]


def specs() -> list[ToolSpec]:
    s = settings()
    out = []
    if s["colab"]["enabled"]:
        server = _servers.get(f"google_colab:{(root() / 'colab').resolve()}")
        if server and server.alive and server.tools_changed:  # honor notifications/tools/list_changed
            try:
                discover("google_colab")
            except ToolError:
                pass
        for t in _snapshot("colab"):
            name = re.sub(r"[^a-z0-9_]", "_", t["name"].lower())[:60]
            read_only = bool(t["annotations"].get("readOnlyHint"))
            out.append(_spec(f"mcp.google_colab.{name}", t, ["google", "colab", "notebook", "gpu", "experiment"],
                             ["network", "compute"], not read_only, {"stdio": "google_colab", "tool": t["name"]}))
    d = s["drive"]
    if d["enabled"] and d["folder_id"]:
        for t in _snapshot("drive"):
            if t["name"] not in DRIVE_POLICY:  # default deny: unknown Drive tools are never exposed
                continue
            mutates = DRIVE_POLICY[t["name"]] in ("parent", "contain+parent")
            out.append(_spec(f"mcp.google_drive.{t['name']}", t, ["google", "drive", "files", "literature"],
                             ["network", "workspace_write"] if mutates else ["network", "read"], mutates,
                             {"url": d["endpoint"], "auth": "google_drive", "guard": "google_drive_folder", "tool": t["name"]}))
    return out


def _spec(tool_id, t, caps, permissions, mutates, execution) -> ToolSpec:
    schema = t["inputSchema"] if isinstance(t["inputSchema"], dict) else {"type": "object"}
    try:
        return ToolSpec(id=tool_id, kind="mcp", source="google_mcp", description=(t["description"] or t["name"])[:4000],
                        title=(t.get("title") or t["name"])[:200], capabilities=caps, input_schema=schema,
                        permissions=permissions, mutates=mutates, idempotent=not mutates, execution=execution)
    except ValueError:  # a remote schema using keywords this runtime cannot enforce is exposed with a permissive object schema
        return ToolSpec(id=tool_id, kind="mcp", source="google_mcp", description=(t["description"] or t["name"])[:4000],
                        capabilities=caps, permissions=permissions, mutates=mutates, idempotent=not mutates,
                        input_schema={"type": "object"}, execution=execution)


def probe(spec: ToolSpec) -> dict:
    s = settings()
    if spec.execution.get("stdio") == "google_colab":
        if not s["colab"]["enabled"]:
            return {"available": False, "reason": "Google Colab MCP is disabled"}
        binary = s["colab"]["command"][0]
        found = shutil.which(binary) or (Path(binary).is_file() and binary)
        return {"available": bool(found), "reason": "" if found else f"{binary} not found (install uv)"}
    if spec.execution.get("auth") == "google_drive":
        if not (s["drive"]["enabled"] and s["drive"]["folder_id"]):
            return {"available": False, "reason": "Google Drive MCP is disabled or has no dedicated folder"}
        if not (root() / "secrets" / "drive_token.json").is_file():
            return {"available": False, "reason": "Google Drive is not authorized"}
        return {"available": True, "reason": ""}
    return {"available": False, "reason": "Unknown Google MCP server"}


def status() -> dict:
    s = settings()
    return {"folder": str(root()), "colab": {**s["colab"], "running": any(v.alive for v in _servers.values()),
                                             "tools": [t["name"] for t in _snapshot("colab")]},
            "drive": {**s["drive"], "authorized": (root() / "secrets" / "drive_token.json").is_file(),
                      "oauth_client": (root() / "secrets" / "oauth_client.json").is_file(),
                      "tools": [t["name"] for t in _snapshot("drive") if t["name"] in DRIVE_POLICY]}}


# ------------------------------------------------------------------ Drive FolderGuard
def _payload(result: dict):
    if isinstance(result.get("structuredContent"), (dict, list)):
        return result["structuredContent"]
    text = "\n".join(c.get("text", "") for c in result.get("content") or [] if c.get("type") == "text")
    try:
        return json.loads(text)
    except ValueError:
        return None


def _arg(schema: dict, names: tuple) -> str | None:
    props = (schema or {}).get("properties") or {}
    return next((n for n in names if n in props), None)


class FolderGuard:
    def __init__(self, call, folder_id: str):
        self.call, self.folder = call, folder_id
        tools = {t["name"]: t for t in _snapshot("drive")}
        self.meta_arg = _arg((tools.get("get_file_metadata") or {}).get("inputSchema"), ID_ARGS)
        self.cache: dict[str, bool] = {folder_id: True}

    def parents(self, file_id: str) -> list:
        if not self.meta_arg:
            raise ToolError("permission_denied", "Folder containment cannot be verified (no metadata tool schema)")
        data = _payload(self.call("get_file_metadata", {self.meta_arg: file_id}))
        data = data.get("file", data) if isinstance(data, dict) else None
        if not isinstance(data, dict) or not isinstance(data.get("parents", []), list):
            raise ToolError("permission_denied", "Folder containment cannot be verified (unrecognized metadata)")
        return [p for p in data.get("parents", []) if isinstance(p, str)]

    def inside(self, file_id: str, depth: int = 8) -> bool:
        if file_id in self.cache:
            return self.cache[file_id]
        ok = False
        if depth > 0:
            ok = any(p == self.folder or self.inside(p, depth - 1) for p in self.parents(file_id))
        self.cache[file_id] = ok
        return ok

    def require(self, file_id) -> None:
        if not isinstance(file_id, str) or not file_id or not self.inside(file_id):
            raise ToolError("permission_denied", "File is outside the dedicated Google Drive folder",
                            hint="Only files inside the configured PhD Lab Drive folder are accessible")

    def filter(self, result: dict) -> dict:
        data = _payload(result)
        items = data if isinstance(data, list) else next(
            (data[k] for k in ("files", "items", "results") if isinstance(data, dict) and isinstance(data.get(k), list)), None)
        if items is None:
            raise ToolError("permission_denied", "Search results cannot be verified against the dedicated folder")
        kept = []
        for item in items[:100]:  # bounded: each unknown item may cost metadata lookups
            fid = item.get("id") if isinstance(item, dict) else None
            if isinstance(fid, str) and (self.folder in (item.get("parents") or []) or self.inside(fid)):
                kept.append(item)
        dropped = len(items) - len(kept)
        out = {"files": kept, "filtered_outside_folder": dropped, "folder_id": self.folder}
        return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}], "structuredContent": out}


def guarded_call(spec: ToolSpec, args: dict, call) -> dict:
    if spec.execution.get("guard") != "google_drive_folder":
        raise ToolError("invalid_spec", "Unknown tool guard")
    tool = spec.execution.get("tool", "")
    rule = DRIVE_POLICY.get(tool)
    folder = settings()["drive"]["folder_id"]
    if not rule or not folder:
        raise ToolError("permission_denied", f"{tool} is not allowed by the Drive folder policy")
    guard, args = FolderGuard(call, folder), dict(args)
    if "contain" in rule:
        id_arg = _arg(spec.input_schema, ID_ARGS)
        if not id_arg:
            raise ToolError("permission_denied", f"{tool}: cannot identify the target file argument; refused")
        guard.require(args.get(id_arg))
    if "parent" in rule:
        parent_arg = _arg(spec.input_schema, PARENT_ARGS)
        if not parent_arg:
            raise ToolError("permission_denied", f"{tool}: cannot force the dedicated parent folder; refused")
        args[parent_arg] = [folder] if parent_arg == "parents" else folder
    result = call(tool, args)
    if rule == "filter" and not result.get("isError"):
        return guard.filter(result)
    return result
