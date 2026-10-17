"""Multi-session, per-tool chat persistence.

Every session belongs to one tool: "data" (Data Chat), "lit2plan" (Tool 1), "experiment" (Tool 2),
"paper" (Tool 3 paper chat) or "masterclass" (Tool 4). A session can carry a snapshot of the tool
output it discusses ("context"), so reopening an old session keeps its original context.


Layout (inside the project workspace):
    data/workspace/chat_sessions/<session_id>.json   one file per conversation
    data/workspace/chat_sessions/_state.json         which session is active
    data/workspace/chat_sessions/_trash/             deleted sessions (recoverable by hand)

- Atomic writes (temp file + os.replace) so a crash never leaves a half-written file.
- A corrupt session file is moved aside as <id>.corrupt-<ts>.json instead of crashing the app.
- v1.3 single-file history (chat_session.json) is migrated automatically into a session.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone

from .config import workspace


# paths are resolved per call so they follow the active research project
def _sess_dir():
    return workspace() / "chat_sessions"


def _trash_dir():
    return _sess_dir() / "_trash"


def _state_path():
    return _sess_dir() / "_state.json"


def _legacy_path():
    return workspace() / "chat_session.json"
SCHEMA_VERSION = 3
TOOLS = ("data", "lit2plan", "experiment", "paper", "masterclass", "review")
MAX_CONTEXT_CHARS = 60_000
MAX_MESSAGES = 1000
MAX_CONTENT_CHARS = 250_000
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_lock = threading.RLock()


class SessionNotFound(KeyError):
    pass


# ------------------------------------------------------------------ helpers
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(sid: str):
    if not isinstance(sid, str) or not ID_RE.match(sid):
        raise SessionNotFound(sid)
    return _sess_dir() / f"{sid}.json"


def _write(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)  # atomic on Windows and POSIX


def _read(path) -> dict | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        path.replace(path.with_name(f"{path.stem}.corrupt-{int(time.time())}.json"))
        return None


def _clean_message(m: dict) -> dict | None:
    if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
        return None
    content = m.get("content")
    if not isinstance(content, str) or not content:
        return None
    out = {"role": m["role"], "content": content[:MAX_CONTENT_CHARS], "ts": str(m.get("ts") or _now())}
    if m["role"] == "user" and m.get("attachments"):
        from .attachments import clean_refs  # lazy import: attachments depends on config only
        out["attachments"] = clean_refs(m["attachments"])
    if m["role"] == "assistant":
        out["tables"] = [t for t in (m.get("tables") or []) if isinstance(t, str)][:20]
        out["added"] = sorted({int(i) for i in (m.get("added") or []) if isinstance(i, (int, float))})
        out["engine"] = str(m.get("engine") or "")
        out["note"] = str(m.get("note") or "")
    return out


def clean_messages(messages) -> list:
    if not isinstance(messages, list):
        return []
    return [c for c in (_clean_message(m) for m in messages) if c][-MAX_MESSAGES:]


def auto_title(messages: list) -> str:
    for m in messages:
        if m["role"] == "user":
            first = next((ln.strip() for ln in m["content"].splitlines() if ln.strip()), "")
            first = re.sub(r"^--- FILE: (.+?) ---$", r"📎 \1", first)
            return (first[:60] + "…") if len(first) > 60 else (first or "New chat")
    return "New chat"


def _tool(t) -> str:
    return t if t in TOOLS else "data"


def _meta(d: dict) -> dict:
    return {"id": d["id"], "title": d.get("title") or "New chat", "created": d.get("created"),
            "updated": d.get("updated"), "count": len(d.get("messages", [])),
            "tool": _tool(d.get("tool")), "has_context": bool(d.get("context"))}


# ------------------------------------------------------------------ active session
def _state() -> dict:
    st = (_read(_state_path()) or {}).get("active")
    if isinstance(st, str):  # v1.4 format: single active session (Data Chat)
        st = {"data": st}
    return st if isinstance(st, dict) else {}


def get_active(tool: str = "data") -> str | None:
    sid = _state().get(_tool(tool))
    try:
        return sid if sid and _path(sid).exists() else None
    except SessionNotFound:
        return None


def set_active(tool: str, sid: str | None) -> None:
    st = _state()
    st[_tool(tool)] = sid
    _write(_state_path(), {"active": st})


# ------------------------------------------------------------------ CRUD
def new_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def create_session(title: str | None = None, messages: list | None = None, tool: str = "data",
                   context: str = "") -> dict:
    with _lock:
        msgs = clean_messages(messages or [])
        now = _now()
        d = {"version": SCHEMA_VERSION, "id": new_id(), "created": now, "updated": now, "tool": _tool(tool),
             "title": (title or "").strip()[:120] or auto_title(msgs), "title_auto": not (title or "").strip(),
             "context": str(context or "")[:MAX_CONTEXT_CHARS], "messages": msgs}
        _write(_path(d["id"]), d)
        set_active(d["tool"], d["id"])
        return d


def load_session(sid: str, activate: bool = True) -> dict:
    with _lock:
        d = _read(_path(sid))
        if d is None:
            raise SessionNotFound(sid)
        d["messages"] = clean_messages(d.get("messages"))
        d["id"], d["tool"] = sid, _tool(d.get("tool"))
        if activate:
            set_active(d["tool"], sid)
        return d


def save_session(sid: str, messages: list | None = None, title: str | None = None) -> dict:
    with _lock:
        p = _path(sid)
        d = _read(p) or {"version": SCHEMA_VERSION, "id": sid, "created": _now(), "title_auto": True,
                         "tool": "data", "context": "", "messages": []}
        if messages is not None:
            d["messages"] = clean_messages(messages)
        if title is not None and title.strip():
            d["title"], d["title_auto"] = title.strip()[:120], False
        if d.get("title_auto", True):
            d["title"] = auto_title(d["messages"])
        d["updated"], d["id"], d["version"] = _now(), sid, SCHEMA_VERSION
        _write(p, d)
        return d


def delete_session(sid: str) -> str | None:
    """Move to _trash/. Returns the new active session id (most recent remaining) or None."""
    with _lock:
        p = _path(sid)
        d = _read(p)
        if d is None:
            raise SessionNotFound(sid)
        tool = _tool(d.get("tool"))
        _trash_dir().mkdir(parents=True, exist_ok=True)
        os.replace(p, _trash_dir() / f"{sid}.json")
        if get_active(tool) in (None, sid):
            rest = list_sessions(tool)
            set_active(tool, rest[0]["id"] if rest else None)
        return get_active(tool)


def list_sessions(tool: str | None = None) -> list:
    migrate_legacy()
    out = []
    for p in _sess_dir().glob("*.json"):
        if p.name.startswith("_") or ".corrupt-" in p.name:
            continue
        d = _read(p)
        if d and (tool is None or _tool(d.get("tool")) == _tool(tool)):
            d["id"] = p.stem
            out.append(_meta(d))
    return sorted(out, key=lambda m: m.get("updated") or "", reverse=True)


def _same(a: dict, b: dict) -> bool:
    return a.get("role") == b.get("role") and a.get("content") == b.get("content")


def record_turn(sid: str, client_history: list, assistant: dict) -> dict:
    """Persist one completed Q&A turn into session `sid`, keeping metadata of matching stored messages."""
    with _lock:
        try:
            stored = load_session(sid, activate=False)["messages"]
        except SessionNotFound:
            stored = []
        k = 0
        while k < min(len(stored), len(client_history)) and _same(stored[k], client_history[k]):
            k += 1
        merged = stored[:k] + list(client_history[k:]) + [{**assistant, "role": "assistant", "ts": _now()}]
        return save_session(sid, merged)


# ------------------------------------------------------------------ migration from v1.3
def migrate_legacy() -> None:
    with _lock:
        _sess_dir().mkdir(parents=True, exist_ok=True)
        if not _legacy_path().exists():
            return
        data = _read(_legacy_path())
        msgs = clean_messages((data or {}).get("messages"))
        if msgs:
            d = create_session(None, msgs, tool="data")
            d["updated"] = (data or {}).get("updated") or d["updated"]
            _write(_path(d["id"]), d)
        if _legacy_path().exists():
            os.replace(_legacy_path(), _legacy_path().with_name("chat_session.migrated.json"))
