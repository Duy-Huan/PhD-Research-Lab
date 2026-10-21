"""Application event bus (v4.2): the browser UI and the `phdlab` CLI are two clients of ONE backend; every change one of
them makes is published here so the other can refresh (GET /api/events, SSE /api/events/stream).

Events: {"seq", "ts", "type", "client", ...}. `client` is the X-PhDLab-Client header of the request that caused it
("ui", "cli", or "" for internal events). Only metadata is published — never request bodies, answers or secrets.
In-memory ring buffer (per process); a client that missed events simply refreshes.
"""
from __future__ import annotations

import threading
import time
from collections import deque

MAX = 2000
_events: deque = deque(maxlen=MAX)
_lock = threading.Lock()
_cond = threading.Condition(_lock)
_seq = {"n": 0}


def publish(type_: str, client: str = "", **data) -> dict:
    with _cond:
        _seq["n"] += 1
        ev = {"seq": _seq["n"], "ts": round(time.time(), 3), "type": str(type_)[:80], "client": str(client or "")[:20],
              **{k: v for k, v in data.items() if isinstance(v, (str, int, float, bool)) or v is None}}
        _events.append(ev)
        _cond.notify_all()
    return ev


def since(after: int = 0, limit: int = 500) -> dict:
    with _lock:
        evs = [e for e in _events if e["seq"] > after]
        last = _seq["n"]
    return {"events": evs[-limit:], "last": last}


def wait(after: int, timeout: float = 15.0) -> list:
    """Block until an event newer than `after` exists (or timeout); used by the SSE stream in a worker thread."""
    end = time.time() + timeout
    with _cond:
        while _seq["n"] <= after:
            left = end - time.time()
            if left <= 0:
                return []
            _cond.wait(left)
        return [e for e in _events if e["seq"] > after]


def last() -> int:
    return _seq["n"]


def reset() -> None:
    with _cond:
        _events.clear()
        _seq["n"] = 0


class MutationMiddleware:
    """Pure ASGI middleware (streams untouched): every successful POST/PUT/PATCH/DELETE under /api/ is published as
    `api.mutation` with the calling client's X-PhDLab-Client header, so the other client can refresh."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH", "DELETE") or \
                not scope["path"].startswith("/api/") or scope["path"].startswith("/api/events"):
            return await self.app(scope, receive, send)
        status = {"code": 500}

        async def wrapped(msg):
            if msg["type"] == "http.response.start":
                status["code"] = msg["status"]
            await send(msg)
        await self.app(scope, receive, wrapped)
        if status["code"] < 400:
            hdr = dict(scope.get("headers") or [])
            publish("api.mutation", client=hdr.get(b"x-phdlab-client", b"").decode("latin-1"), method=scope["method"],
                    path=scope["path"])
