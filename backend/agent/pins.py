"""Pinned research results (v4.2 research chat): the durable output layer the researcher builds from the conversation.

    <project>/workspace/research_artifacts.json   {"items": [pin, …]}

pin = {id, kind, title, body, status, provenance: {session_id, message_id, source_ids[], run_id}, created, updated}
    kind    gap | hypothesis | decision | method | result | note | source
    status  pinned (default) · approved (the researcher validated it) · verified (backed by a MEASURED run) · deprecated
Pinning never means scientific verification: `verified` is refused unless the pin references a run that exists and
finished successfully. Pins are shared by every conversation of the project (they are part of the project context).
"""
from __future__ import annotations

import re

from backend.agent import AIWSError, new_id, now, read_json, write_json

KINDS = ("gap", "hypothesis", "decision", "method", "result", "note", "source")
STATUS = ("pinned", "approved", "verified", "deprecated")
RUN_RE = re.compile(r"^[\w-]{6,60}$")


def _path():
    from backend.core.config import workspace
    return workspace() / "research_artifacts.json"


def _load() -> list:
    d = read_json(_path(), {"items": []})
    return d.get("items", []) if isinstance(d, dict) else []


def _save(items: list) -> None:
    write_json(_path(), {"items": items})


def _check_status(status: str, prov: dict) -> None:
    if status not in STATUS:
        raise AIWSError(f"status must be one of {', '.join(STATUS)}")
    if status == "verified":
        from backend.execution.sandbox import SandboxError, get_run
        rid = prov.get("run_id") or ""
        if not RUN_RE.match(rid):
            raise AIWSError("Only a pin that references a measured run can be marked verified")
        try:
            r = get_run(rid)
        except SandboxError:
            raise AIWSError(f"Run {rid} not found")
        if r.get("status") != "done":
            raise AIWSError(f"Run {rid} did not finish successfully ({r.get('status')}) — it cannot verify a result")


def _clean_prov(p: dict | None) -> dict:
    p = p or {}
    src = [str(x)[:120] for x in (p.get("source_ids") or []) if str(x).strip()][:30]
    return {"session_id": str(p.get("session_id") or "")[:40], "message_id": str(p.get("message_id") or "")[:40],
            "source_ids": src, "run_id": str(p.get("run_id") or "")[:60]}


def list_pins(kind: str = "", status: str = "") -> list:
    return [p for p in _load() if (not kind or p["kind"] == kind) and (not status or p["status"] == status)]


def add(kind: str, title: str, body: str = "", status: str = "pinned", provenance: dict | None = None) -> dict:
    if kind not in KINDS:
        raise AIWSError(f"kind must be one of {', '.join(KINDS)}")
    title = (title or "").strip()[:200]
    if not title:
        raise AIWSError("Give the pin a title")
    prov = _clean_prov(provenance)
    _check_status(status, prov)
    p = {"id": new_id("pin", 4), "kind": kind, "title": title, "body": str(body or "")[:20000], "status": status,
         "provenance": prov, "created": now(), "updated": now()}
    items = _load()
    items.append(p)
    _save(items)
    return p


def update(pid: str, **fields) -> dict:
    items = _load()
    p = next((x for x in items if x["id"] == pid), None)
    if not p:
        raise AIWSError("Pin not found")
    if "kind" in fields and fields["kind"] not in KINDS:
        raise AIWSError(f"kind must be one of {', '.join(KINDS)}")
    if "provenance" in fields:
        fields["provenance"] = _clean_prov({**p["provenance"], **(fields["provenance"] or {})})
    if "status" in fields:
        _check_status(fields["status"], fields.get("provenance") or p["provenance"])
    for k in ("kind", "title", "body", "status", "provenance"):
        if k in fields and fields[k] is not None:
            p[k] = fields[k] if k != "title" else (str(fields[k]).strip()[:200] or p["title"])
    p["updated"] = now()
    _save(items)
    return p


def remove(pid: str) -> dict:
    items = _load()
    if not any(x["id"] == pid for x in items):
        raise AIWSError("Pin not found")
    _save([x for x in items if x["id"] != pid])
    return {"deleted": pid}
