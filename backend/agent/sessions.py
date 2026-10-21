"""Universal AI sessions (Firewall spec §11): more than a messages[] array.

    <project>/workspace/ai_sessions/<id>.json          session: binding, settings, messages, turns, approvals,
                                                       artifacts, memory candidates, rolling summary
    <project>/workspace/ai_sessions/<id>.events.jsonl  normalised event log (redacted; message.delta is live-only)
    <project>/workspace/ai_sessions/_trash/            deleted sessions (recoverable by hand)

The per-tool chats of chat_store.py (v1–v4.1) are untouched; they keep working in their modules.
Events carry {seq, id, ts, type, session_id, turn_id, provider_id, data}. Every session has its own sequence and log,
so a client subscribed to one session can never receive another session's events. A client that reconnects passes
`after=<last seq>` and gets exactly what it missed (deltas while the process lives, everything else from the log).
"""
from __future__ import annotations

import json
import shutil
import threading
import time
from collections import deque

from backend.agent import SESSION_RE, MODULES, AIWSError, new_id, now, read_json, redact, write_json

EVENT_TYPES = (
    "session.created", "session.updated", "session.resumed", "session.failed", "session.cancelled", "session.completed",
    "turn.started", "turn.awaiting_launch", "turn.completed", "turn.failed", "turn.cancelled",
    "context.compiled", "message.started", "message.delta", "message.completed", "status.updated",
    "reasoning.summary", "tool.proposed", "tool.approval_required", "tool.started", "tool.stdout", "tool.stderr",
    "tool.completed", "tool.failed", "action.proposed", "action.approval_required", "action.completed", "action.failed",
    "artifact.discovered", "artifact.updated", "memory.candidate", "memory.saved", "usage.updated", "permission.denied",
    "run.updated", "error")
MAX_MESSAGES = 2000
BUF = 5000
_lock = threading.RLock()
_cond = threading.Condition(_lock)
_buf: dict = {}   # session id → deque of recent events (incl. message.delta)
_seq: dict = {}   # session id → last sequence number


def _dir():
    from backend.core.config import workspace
    d = workspace() / "ai_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(sid: str):
    if not isinstance(sid, str) or not SESSION_RE.match(sid):
        raise AIWSError("Invalid session id")
    return _dir() / f"{sid}.json"


def _events_path(sid: str):
    return _dir() / f"{sid}.events.jsonl"


def _summary(s: dict) -> dict:
    last = s["messages"][-1] if s["messages"] else None
    return {"id": s["id"], "title": s["title"], "created": s["created"], "updated": s["updated"], "status": s["status"],
            "archived": s["archived"], "binding": s["binding"], "provider": s["settings"].get("provider", ""),
            "messages": len(s["messages"]), "pending_approvals": sum(1 for a in s["approvals"] if a["status"] == "pending"),
            "last": (last or {}).get("content", "")[:160]}


def create(title: str = "", module: str = "global", entity_id: str = "", entity_label: str = "",
           settings: dict | None = None) -> dict:
    if module not in MODULES:
        raise AIWSError(f"module must be one of {', '.join(MODULES)}")
    from backend.agent.policy import clean_settings
    sid = new_id("as")
    s = {"id": sid, "schema": 1, "title": (title or "").strip()[:120] or "New conversation", "created": now(), "updated": now(),
         "status": "idle", "archived": False,
         "binding": {"module": module, "entity_id": str(entity_id or "")[:120], "entity_label": str(entity_label or "")[:200]},
         "settings": clean_settings(settings or {}), "gateway_session": "", "messages": [], "turns": [], "approvals": [],
         "artifacts": [], "memory": [], "summary": "", "selected_sources": [], "forked_from": None}
    with _lock:
        write_json(_path(sid), s)
    emit(sid, "session.created", module=module, entity_id=s["binding"]["entity_id"])
    return s


def get(sid: str) -> dict:
    s = read_json(_path(sid))
    if not isinstance(s, dict):
        raise AIWSError("Session not found")
    return s


def save(s: dict) -> dict:
    s["updated"] = now()
    with _lock:
        write_json(_path(s["id"]), s)
    return s


def update(sid: str, fn):
    """Atomic read-modify-write of one session; returns fn's result."""
    with _lock:
        s = get(sid)
        out = fn(s)
        save(s)
        return out


def list_sessions(module: str = "", entity_id: str = "", q: str = "", archived: bool = False, limit: int = 200) -> list:
    out = []
    for f in _dir().glob("as-*.json"):
        s = read_json(f)
        if not isinstance(s, dict) or "binding" not in s:
            continue
        if bool(s.get("archived")) != bool(archived):
            continue
        if module and s["binding"]["module"] != module:
            continue
        if entity_id and s["binding"]["entity_id"] != entity_id:
            continue
        if q and q.lower() not in (s["title"] + " " + " ".join(m["content"][:400] for m in s["messages"])).lower():
            continue
        out.append(_summary(s))
    return sorted(out, key=lambda x: -x["updated"])[:limit]


NOTE_FIELDS = {"message_id": 64, "quote": 2000, "prefix": 120, "suffix": 120, "text": 4000}


def _clean_note(body: dict) -> dict:
    n = {k: str(body.get(k) or "")[:limit] for k, limit in NOTE_FIELDS.items() if k in body}
    if isinstance(body.get("point"), dict):  # a data point of a chart: {chart, series, x, y, label}
        n["point"] = {k: str(v)[:120] for k, v in body["point"].items() if k in ("chart", "series", "x", "y", "label")}
    if body.get("status") in ("open", "resolved"):
        n["status"] = body["status"]
    return n


def add_note(sid: str, body: dict) -> dict:
    """A researcher's note pinned to a passage or a chart point of a message (shown as a highlight in the answer)."""
    n = _clean_note(body)
    if not n.get("message_id") or not (n.get("quote") or n.get("point")):
        raise AIWSError("A note needs the message and the passage (or chart point) it refers to")
    note = {"id": new_id("nt", 4), "created": now(), "status": "open", "text": "", **n}

    def fn(s):
        if not any(m["id"] == note["message_id"] for m in s["messages"]):
            raise AIWSError("Message not found in this conversation")
        s.setdefault("notes", []).append(note)
        return note
    out = update(sid, fn)
    emit(sid, "session.updated", note=note["id"])
    return out


def update_note(sid: str, nid: str, body: dict) -> dict:
    patch = {k: v for k, v in _clean_note(body).items() if k in ("text", "status")}

    def fn(s):
        n = next((x for x in s.get("notes") or [] if x["id"] == nid), None)
        if not n:
            raise AIWSError("Note not found")
        n.update(patch, updated=now())
        return n
    return update(sid, fn)


def delete_note(sid: str, nid: str) -> dict:
    def fn(s):
        before = len(s.get("notes") or [])
        s["notes"] = [x for x in s.get("notes") or [] if x["id"] != nid]
        if len(s["notes"]) == before:
            raise AIWSError("Note not found")
        return {"deleted": nid}
    return update(sid, fn)


def rename(sid: str, title: str) -> dict:
    title = (title or "").strip()[:120]
    if not title:
        raise AIWSError("Give a title")

    def fn(s):
        s["title"] = title
        return _summary(s)
    out = update(sid, fn)
    emit(sid, "session.updated", field="title")
    return out


def archive(sid: str, archived: bool = True) -> dict:
    def fn(s):
        s["archived"] = bool(archived)
        return _summary(s)
    out = update(sid, fn)
    emit(sid, "session.updated", field="archived", value=bool(archived))
    return out


def delete(sid: str, confirm: str) -> dict:
    if confirm != sid:
        raise AIWSError("Confirm the deletion with the session id")
    get(sid)
    t = _dir() / "_trash"
    t.mkdir(exist_ok=True)
    with _lock:
        for f in (_path(sid), _events_path(sid)):
            if f.exists():
                shutil.move(str(f), str(t / f.name))
        _buf.pop(sid, None)
    return {"deleted": sid}


def add_message(sid: str, role: str, content: str, turn_id: str = "", **meta) -> dict:
    m = {"id": new_id("m", 4), "role": role, "content": str(content or "")[:250_000], "ts": now(), "turn_id": turn_id,
         **{k: v for k, v in meta.items() if v is not None}}

    def fn(s):
        s["messages"].append(m)
        del s["messages"][:-MAX_MESSAGES]
        if s["title"] == "New conversation" and role == "user" and m["content"].strip():
            s["title"] = m["content"].strip().splitlines()[0][:70]
        return m
    return update(sid, fn)


def fork(sid: str, message_id: str = "") -> dict:
    src = get(sid)
    msgs = src["messages"]
    if message_id:
        idx = next((i for i, m in enumerate(msgs) if m["id"] == message_id), None)
        if idx is None:
            raise AIWSError("Message not found")
        msgs = msgs[: idx + 1]
    b = src["binding"]
    s = create(f"{src['title']} (fork)", b["module"], b["entity_id"], b["entity_label"], src["settings"])

    def fn(x):
        x["messages"] = [dict(m) for m in msgs]
        x["forked_from"] = {"session": sid, "message": message_id or (msgs[-1]["id"] if msgs else "")}
        x["selected_sources"] = list(src.get("selected_sources") or [])
        return x
    return update(s["id"], fn)


# ------------------------------------------------------------------ events
def _last_seq(sid: str) -> int:
    if sid in _seq:
        return _seq[sid]
    n = 0
    p = _events_path(sid)
    if p.exists():
        lines = [l for l in p.read_text("utf-8").splitlines() if l.strip()]
        if lines:
            try:
                n = int(json.loads(lines[-1]).get("seq", 0))
            except ValueError:
                n = len(lines)
    _seq[sid] = n
    return n


def _clean(v):
    if isinstance(v, str):
        return redact(v)
    if isinstance(v, list):
        return [_clean(x) for x in v]
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    return v


def emit(sid: str, type_: str, turn_id: str = "", provider_id: str = "", **data) -> dict:
    if type_ not in EVENT_TYPES:
        raise AIWSError(f"unknown event type {type_}")
    with _cond:
        seq = _last_seq(sid) + 1
        _seq[sid] = seq
        e = {"seq": seq, "id": f"{sid}:{seq}", "ts": now(), "type": type_, "session_id": sid, "turn_id": turn_id,
             "provider_id": provider_id, "data": _clean(data)}
        _buf.setdefault(sid, deque(maxlen=BUF)).append(e)
        if type_ != "message.delta":
            try:
                with open(_events_path(sid), "a", encoding="utf-8") as f:
                    f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
            except OSError:
                pass
        _cond.notify_all()
    from backend.core import bus
    if type_ != "message.delta":
        bus.publish("aiws." + type_, session_id=sid, turn_id=turn_id)
    return e


def events(sid: str, after: int = 0, limit: int = 2000) -> list:
    get(sid)
    with _lock:
        buf = list(_buf.get(sid) or [])
    if buf and buf[0]["seq"] <= after + 1:
        return [e for e in buf if e["seq"] > after][:limit]
    out = []
    p = _events_path(sid)
    if p.exists():
        for line in p.read_text("utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("seq", 0) > after:
                out.append(e)
    top = out[-1]["seq"] if out else after
    return (out + [e for e in buf if e["seq"] > top])[:limit]


def wait_events(sid: str, after: int, timeout: float = 15.0) -> list:
    end = time.time() + timeout
    with _cond:
        while _last_seq(sid) <= after:
            left = end - time.time()
            if left <= 0:
                return []
            _cond.wait(left)
    return events(sid, after)


def reset_memory() -> None:
    """Tests / project switch: forget the in-process buffers (logs on disk stay)."""
    with _lock:
        _buf.clear()
        _seq.clear()
