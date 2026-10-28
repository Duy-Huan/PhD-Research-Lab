"""Public MCP gateway for ChatGPT (chatgpt.com Developer Mode connector), v6.6.2. Off by default.

A separate ASGI app on its own loopback port, reached only through a tunnel the owner switches on. It serves nothing
but /mcp, /oauth/* and /.well-known/*; the main application (UI, settings, files) is never exposed. Six layers, all on:

1. ChatGPT's tools run under a container-isolated grant (profiles.CONTAINER_CLIENTS): Python tools execute in the
   Docker sandbox; host-executing tools are refused. ChatGPT sees only phdlab_tools_search/describe/call, so every
   call goes through the runtime (grants, provenance with actor "chatgpt").
2. OAuth 2.1 authorization code + PKCE S256, dynamic client registration restricted to ChatGPT redirect URIs, issuer
   identification (iss) and the RFC 9728 `resource` echoed into an audience-bound token. Each authorization waits for
   the owner to approve it in the local app (loopback API), so a stranger opening the public URL gets nothing.
   Access tokens live 1 h; refresh tokens rotate and are single use. Only SHA-256 hashes are stored.
3. Server-to-server endpoints (/mcp, /oauth/token, /oauth/register) accept only OpenAI's published ChatGPT egress
   ranges (https://openai.com/chatgpt-connectors.json, refreshed daily). OpenAI calls these ranges best effort, so this
   layer supplements OAuth. If the list is unavailable, /mcp fails closed. The owner's browser (authorize) is exempt.
4. Per-client request rate limit and a lockout for addresses that present invalid tokens repeatedly.
5. The tunnel runs only while enabled; kill_switch() stops it, stops the gateway and revokes every token.
6. Every request decision is appended to an audit log (never tokens or arguments); denials raise alerts.
"""
from __future__ import annotations

import base64
import hashlib
import html
import ipaddress
import json
import re
import secrets
import shutil
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

RANGES_URL = "https://openai.com/chatgpt-connectors.json"
REDIRECT_PATTERNS = (re.compile(r"^https://chatgpt\.com/connector_platform_oauth_redirect$"),
                     re.compile(r"^https://chatgpt\.com/connector/oauth/[A-Za-z0-9_-]{1,200}$"))
ACCESS_TTL, REFRESH_TTL, CODE_TTL, PENDING_TTL = 3600, 30 * 86400, 300, 600
EXPOSED_TOOLS = ["phdlab_tools_search", "phdlab_tools_describe", "phdlab_tools_call", "phdlab_tools_job"]
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_lock = threading.RLock()

STATE: dict = {}


def reset_for_tests() -> None:
    with _lock:
        STATE.clear()
        STATE.update(enabled=False, public_url="", ranges=None, ranges_at=0.0, tunnel=None, server=None,
                     clients={}, pending={}, codes={}, access={}, refresh={}, per_minute=120,
                     hits={}, failures={}, alerts=deque(maxlen=50))


reset_for_tests()


# ---------------------------------------------------------------------------------------------------- storage
def _root() -> Path:
    from backend.core.config import GLOBAL_DIR
    path = GLOBAL_DIR / "chatgpt_mcp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def audit(decision: str, request: Request | None = None, **extra) -> None:
    entry = {"ts": round(time.time(), 3), "decision": decision, **extra}
    if request is not None:
        entry.update(path=request.url.path[:80], ip=client_ip(request))
    try:
        with (_root() / "audit.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass
    if decision.startswith("deny") or decision in ("lockout", "rate_limited"):
        STATE["alerts"].append({"kind": decision, "ts": entry["ts"], "ip": entry.get("ip", ""), "path": entry.get("path", "")})


def audit_tail(n: int = 100) -> list:
    path = _root() / "audit.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()[-n:] if line.strip()]


# ---------------------------------------------------------------------------------------------------- settings
def set_public_url(url: str) -> None:
    STATE["public_url"] = url.rstrip("/")


def set_ranges(prefixes: list | None) -> None:
    STATE["ranges"] = None if prefixes is None else [ipaddress.ip_network(p, strict=False) for p in prefixes]
    STATE["ranges_at"] = time.time()


def set_rate_limit(per_minute: int) -> None:
    STATE["per_minute"] = max(1, int(per_minute))


def refresh_ranges() -> dict:
    """Fetch OpenAI's published ChatGPT egress ranges; keep the previous list on failure (fail closed if none)."""
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(RANGES_URL, headers={"User-Agent": "phdlab"}), timeout=20) as r:
            data = json.load(r)
        prefixes = [p.get("ipv4Prefix") or p.get("ipv6Prefix") or p.get("prefix") for p in data.get("prefixes", [])]
        set_ranges([p for p in prefixes if p])
        (_root() / "ranges.json").write_text(json.dumps({"creationTime": data.get("creationTime"), "prefixes": prefixes}), "utf-8")
        return {"ok": True, "count": len(STATE["ranges"]), "creationTime": data.get("creationTime")}
    except Exception as e:  # noqa: BLE001 - any fetch/parse failure keeps the old list
        audit("ranges_refresh_failed", error=type(e).__name__)
        return {"ok": False, "error": type(e).__name__, "count": len(STATE["ranges"] or [])}


# ---------------------------------------------------------------------------------------------------- guards
def client_ip(request: Request) -> str:
    host = request.client.host if request.client else ""
    if host in LOOPBACK:  # the tunnel connects from loopback and reports the real caller
        return request.headers.get("cf-connecting-ip", host).strip()
    return host


def _ip_allowed(ip: str) -> bool:
    ranges = STATE["ranges"]
    if not ranges:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in ranges)


def _locked(ip: str) -> bool:
    now = time.time()
    recent = [t for t in STATE["failures"].get(ip, []) if now - t < 600]
    STATE["failures"][ip] = recent
    return len(recent) >= 10


def _rate_limited(key: str) -> bool:
    now = time.time()
    window = [t for t in STATE["hits"].get(key, []) if now - t < 60]
    window.append(now)
    STATE["hits"][key] = window
    return len(window) > STATE["per_minute"]


def _error(status: int, error: str, description: str = "", headers: dict | None = None) -> JSONResponse:
    return JSONResponse({"error": error, "error_description": description}, status_code=status, headers=headers)


def _server_guard(request: Request, rate_key: str | None = "ip") -> Response | None:
    """Layers 3 and 4 for server-to-server endpoints; rate_key=None defers the rate limit to the caller."""
    ip = client_ip(request)
    if not STATE["enabled"]:
        return _error(404, "not_found")
    if _locked(ip):
        audit("lockout", request)
        return _error(429, "too_many_failures", "Address temporarily locked after repeated invalid credentials")
    if not _ip_allowed(ip):
        audit("deny_ip", request)
        return _error(403, "forbidden", "Caller is not in OpenAI's published ChatGPT egress ranges")
    if rate_key and _rate_limited("ip:" + ip):
        audit("rate_limited", request)
        return _error(429, "rate_limited", "Too many requests")
    return None


# ---------------------------------------------------------------------------------------------------- OAuth
def pending_requests() -> list:
    now = time.time()
    with _lock:
        return [{"id": k, "client_name": v["client_name"], "created": v["created"], "status": v["status"]}
                for k, v in STATE["pending"].items() if now - v["created"] < PENDING_TTL and v["status"] == "pending"]


def reset_pending() -> None:
    STATE["pending"].clear()


def approve(request_id: str) -> dict:
    return _decide(request_id, "approved")


def deny(request_id: str) -> dict:
    return _decide(request_id, "denied")


def _decide(request_id: str, status: str) -> dict:
    with _lock:
        req = STATE["pending"].get(request_id)
        if not req or req["status"] != "pending":
            raise ValueError("No pending ChatGPT authorization with this id")
        req["status"] = status
    audit("owner_" + status, request_id=request_id[:12])
    return {"id": request_id, "status": status}


def _issue(client_id: str, resource: str) -> dict:
    access, refresh = "cga_" + secrets.token_urlsafe(32), "cgr_" + secrets.token_urlsafe(40)
    now = time.time()
    STATE["access"][_hash(access)] = {"client_id": client_id, "aud": resource, "exp": now + ACCESS_TTL}
    STATE["refresh"][_hash(refresh)] = {"client_id": client_id, "aud": resource, "exp": now + REFRESH_TTL}
    return {"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_TTL, "refresh_token": refresh}


def _verify_access(token: str) -> dict | None:
    rec = STATE["access"].get(_hash(token)) if token.startswith("cga_") else None
    if not rec or rec["exp"] < time.time() or rec["aud"] != STATE["public_url"]:
        return None
    return rec


def revoke_all() -> None:
    with _lock:
        for key in ("access", "refresh", "codes", "pending"):
            STATE[key].clear()


# ---------------------------------------------------------------------------------------------------- app
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _challenge() -> dict:
    return {"WWW-Authenticate": f'Bearer resource_metadata="{STATE["public_url"]}/.well-known/oauth-protected-resource"'}


@app.get("/.well-known/oauth-protected-resource")
def protected_resource():
    return {"resource": STATE["public_url"], "authorization_servers": [STATE["public_url"]],
            "bearer_methods_supported": ["header"]}


@app.get("/.well-known/oauth-authorization-server")
def authorization_server():
    base = STATE["public_url"]
    return {"issuer": base, "authorization_endpoint": base + "/oauth/authorize", "token_endpoint": base + "/oauth/token",
            "registration_endpoint": base + "/oauth/register", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"], "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"], "authorization_response_iss_parameter_supported": True}


@app.post("/oauth/register")
async def register(request: Request):
    blocked = _server_guard(request)
    if blocked:
        return blocked
    try:
        body = await request.json()
    except ValueError:
        return _error(400, "invalid_client_metadata", "JSON body required")
    uris = body.get("redirect_uris") if isinstance(body, dict) else None
    if not isinstance(uris, list) or not uris or any(not isinstance(u, str) or not any(p.match(u) for p in REDIRECT_PATTERNS)
                                                     for u in uris):
        audit("deny_redirect", request)
        return _error(400, "invalid_redirect_uri", "Only ChatGPT connector redirect URIs are accepted")
    if body.get("token_endpoint_auth_method", "none") != "none":
        return _error(400, "invalid_client_metadata", "Public clients with PKCE only")
    client_id = "cgc_" + secrets.token_urlsafe(16)
    STATE["clients"][client_id] = {"redirect_uris": uris, "name": str(body.get("client_name") or "ChatGPT")[:80],
                                   "created": time.time()}
    audit("client_registered", request, client=client_id[:12])
    return JSONResponse({"client_id": client_id, "redirect_uris": uris, "token_endpoint_auth_method": "none",
                         "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}, status_code=201)


@app.get("/oauth/authorize")
def authorize(request: Request):
    q = request.query_params
    client = STATE["clients"].get(q.get("client_id", ""))
    if (q.get("response_type") != "code" or not client or q.get("redirect_uri") not in client["redirect_uris"]
            or q.get("code_challenge_method") != "S256" or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", q.get("code_challenge", ""))
            or q.get("resource") != STATE["public_url"]):
        audit("deny_authorize", request)
        return _error(400, "invalid_request", "Invalid client, redirect URI, PKCE S256 challenge or resource")
    rid = secrets.token_urlsafe(18)
    with _lock:
        STATE["pending"][rid] = {"client_id": q["client_id"], "client_name": client["name"], "redirect_uri": q["redirect_uri"],
                                 "state": q.get("state", ""), "challenge": q["code_challenge"], "resource": q["resource"],
                                 "created": time.time(), "status": "pending"}
    audit("authorize_pending", request, request_id=rid[:12])
    wait = html.escape(f"/oauth/authorize/wait/{rid}")
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8"><title>PhD Research Lab</title>
<meta http-equiv="refresh" content="2;url={wait}">
<body style="font-family:system-ui;max-width:32rem;margin:4rem auto">
<h1>Approve in PhD Research Lab</h1><p>ChatGPT asks to connect. Open PhD Research Lab on your computer and approve
request <b>{html.escape(rid[:6])}</b>. This page continues automatically.</p></body>""")


@app.get("/oauth/authorize/wait/{rid}")
def authorize_wait(rid: str):
    req = STATE["pending"].get(rid)
    if not req or time.time() - req["created"] > PENDING_TTL:
        return _error(404, "not_found", "Authorization request expired")
    if req["status"] == "pending":
        return Response(status_code=202, headers={"Refresh": "2"})
    params = {"state": req["state"], "iss": STATE["public_url"]}
    if req["status"] == "denied":
        params["error"] = "access_denied"
    else:
        code = secrets.token_urlsafe(32)
        STATE["codes"][_hash(code)] = {"client_id": req["client_id"], "redirect_uri": req["redirect_uri"],
                                       "challenge": req["challenge"], "resource": req["resource"], "exp": time.time() + CODE_TTL}
        params["code"] = code
    STATE["pending"].pop(rid, None)
    return RedirectResponse(req["redirect_uri"] + "?" + urlencode(params), status_code=302)


@app.post("/oauth/token")
async def token(request: Request):
    blocked = _server_guard(request)
    if blocked:
        return blocked
    form = dict(await request.form())
    grant = form.get("grant_type")
    if form.get("resource") and form["resource"] != STATE["public_url"]:
        return _error(400, "invalid_target", "Unknown resource")
    if grant == "authorization_code":
        rec = STATE["codes"].pop(_hash(str(form.get("code", ""))), None)
        verifier = str(form.get("code_verifier", ""))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        if (not rec or rec["exp"] < time.time() or rec["redirect_uri"] != form.get("redirect_uri")
                or not secrets.compare_digest(challenge, rec["challenge"])
                or (form.get("client_id") and form["client_id"] != rec["client_id"])):
            STATE["failures"].setdefault(client_ip(request), []).append(time.time())
            audit("deny_token", request, grant="authorization_code")
            return _error(400, "invalid_grant", "Invalid, expired or already used code, or PKCE mismatch")
        audit("token_issued", request, grant="authorization_code")
        return _issue(rec["client_id"], rec["resource"])
    if grant == "refresh_token":
        rec = STATE["refresh"].pop(_hash(str(form.get("refresh_token", ""))), None)
        if not rec or rec["exp"] < time.time() or (form.get("client_id") and form["client_id"] != rec["client_id"]):
            STATE["failures"].setdefault(client_ip(request), []).append(time.time())
            audit("deny_token", request, grant="refresh_token")
            return _error(400, "invalid_grant", "Invalid, expired or already used refresh token")
        audit("token_refreshed", request)
        return _issue(rec["client_id"], rec["aud"])
    return _error(400, "unsupported_grant_type")


@app.post("/mcp")
async def mcp(request: Request):
    blocked = _server_guard(request, rate_key=None)
    if blocked:
        return blocked
    auth = request.headers.get("authorization", "")
    rec = _verify_access(auth[7:].strip()) if auth.lower().startswith("bearer ") else None
    if rec is None:
        STATE["failures"].setdefault(client_ip(request), []).append(time.time())
        audit("deny_token", request)
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "Unauthorized"}},
                            status_code=401, headers=_challenge())
    if _rate_limited("client:" + rec["client_id"]):  # layer 4: per connected client
        audit("rate_limited", request)
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32029, "message": "Too many requests"}}, 429)
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}, 400)
    from fastapi.concurrency import run_in_threadpool
    from backend.core.config import data_dir, project_scope
    from backend.providers import mcp_server
    session = request.headers.get("mcp-session-id", "")[:80]
    meta = {"client_name": "chatgpt", "only_tools": EXPOSED_TOOLS}

    def handle(msg):
        with project_scope(data_dir()):
            return mcp_server.handle(msg, session, meta)
    if isinstance(payload, list):
        res = [r for r in [await run_in_threadpool(handle, m) for m in payload if isinstance(m, dict)] if r]
        out = JSONResponse(res) if res else Response(status_code=202)
    elif isinstance(payload, dict):
        r = await run_in_threadpool(handle, payload)
        out = JSONResponse(r) if r else Response(status_code=202)
    else:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}, 400)
    if meta.get("session_id"):
        out.headers["Mcp-Session-Id"] = meta["session_id"]
    audit("mcp", request, method=str(payload.get("method", "batch") if isinstance(payload, dict) else "batch")[:40])
    return out


@app.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def nothing_else(rest: str):
    return Response(status_code=404)


# ---------------------------------------------------------------------------------------------------- lifecycle
def parse_tunnel_url(line: str) -> str | None:
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line or "")
    return m.group(0) if m else None


def enable(port: int = 8770) -> dict:
    """Start the gateway on loopback and a Cloudflare quick tunnel to it (layer 5). Requires cloudflared."""
    import uvicorn
    exe = shutil.which("cloudflared")
    if not exe:
        raise ValueError("Install cloudflared first (winget install Cloudflare.cloudflared / apt install cloudflared)")
    with _lock:
        if STATE["enabled"]:
            return status()
        refresh_ranges()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        threading.Thread(target=server.run, daemon=True, name="chatgpt-gateway").start()
        proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        url, deadline = None, time.time() + 40
        while url is None and time.time() < deadline and proc.poll() is None:
            url = parse_tunnel_url(proc.stdout.readline())
        if not url:
            proc.kill()
            server.should_exit = True
            raise ValueError("cloudflared did not report a public URL")
        threading.Thread(target=lambda: [None for _ in proc.stdout], daemon=True).start()  # drain output
        stop = threading.Event()
        threading.Thread(target=ranges_loop, args=(stop,), daemon=True, name="chatgpt-ranges").start()
        STATE.update(enabled=True, tunnel=proc, server=server, stop=stop)
        set_public_url(url)
    audit("enabled", url=url)
    return status()


def ranges_loop(stop: threading.Event, interval_s: float = 86400) -> None:
    """Refresh OpenAI's published ranges daily while the gateway is enabled (they change over time)."""
    while not stop.wait(interval_s):
        refresh_ranges()


def kill_switch() -> dict:
    """Layer 5: stop the tunnel and gateway and revoke every token and pending authorization at once."""
    with _lock:
        proc, server = STATE.get("tunnel"), STATE.get("server")
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
        if server is not None:
            server.should_exit = True
        if STATE.get("stop") is not None:
            STATE["stop"].set()
        STATE.update(enabled=False, tunnel=None, server=None, stop=None)
        revoke_all()
    audit("kill_switch")
    return {"enabled": False, "tokens_revoked": True}


def status() -> dict:
    return {"enabled": STATE["enabled"], "public_url": STATE["public_url"], "mcp_url": STATE["public_url"] + "/mcp"
            if STATE["public_url"] else "", "ranges": len(STATE["ranges"] or []), "ranges_refreshed": STATE["ranges_at"],
            "active_tokens": len(STATE["access"]), "pending": pending_requests(), "alerts": list(STATE["alerts"]),
            "cloudflared": bool(shutil.which("cloudflared"))}
