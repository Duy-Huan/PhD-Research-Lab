"""Artifact collector (Firewall spec §13): provider workspace → discovery → validation → registry + preview →
researcher action (inspect / export / compare / apply / reject). Nothing is ever copied into the project by itself.

Sources
  * fenced code blocks of an answer that name a file:  ```python path=train.py   ```python title="cfg.yaml"   ```python:x.py
  * files a CLI provider wrote in ITS session workspace during the turn (cli-space/<provider>/sessions/<id>/workspace)
Storage: <project>/workspace/ai_artifacts/<session>/<artifact>/<file>  (+ metadata in the session: sha256, size, type,
origin, turn, status collected | applied | rejected | quarantined).
Apply: only into the ACTIVE code project (ide_fs path rules), only after the researcher saw the diff — the request must
repeat the sha256 of the target as it was when the diff was shown (stale diff → refused); an existing file is backed up
to <code project>/.phdlab/backups/<timestamp>/ first. References, memory and run outputs can never be targets.
"""
from __future__ import annotations

import difflib
import hashlib
import re
import shutil
import time
from pathlib import Path

from backend.agent import AIWSError, new_id, now

MAX_BYTES = 2_000_000
FENCE = re.compile(r"```([\w+.#-]*)(?::([^\s`]+)|[ \t]+(?:path|title|file)=\"?([^\s\"`]+)\"?)[^\n]*\n(.*?)```", re.S)
TEXT_EXT = {".py", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".tex", ".bib", ".sh", ".csv", ".ipynb",
            ".js", ".ts", ".html", ".css", ".r", ".m", ".jl", ".c", ".h", ".cpp", ".cu", ".sql", ".xml", ""}


def _root(sid: str) -> Path:
    from backend.core.config import workspace
    return workspace() / "ai_artifacts" / sid


def safe_rel(rel: str) -> str:
    r = str(rel or "").replace("\\", "/").strip()
    parts = [p for p in r.split("/") if p not in ("", ".")]
    if not parts or len(r) > 200 or r.startswith("/") or re.match(r"^[A-Za-z]:", r) or ".." in parts or \
            any(p.startswith(".git") for p in parts):
        raise AIWSError(f"Unsafe artifact path '{rel}'")
    return "/".join(parts)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def register(session_id: str, turn_id: str, rel: str, data: bytes, origin: str, provider: str = "") -> dict:
    from backend.agent import sessions as store
    try:
        rel = safe_rel(rel)
        status, why = "collected", ""
    except AIWSError as e:
        rel, status, why = re.sub(r"[^\w.-]", "_", str(rel))[-80:] or "artifact", "quarantined", str(e)
    if len(data) > MAX_BYTES:
        status, why = "quarantined", f"larger than {MAX_BYTES // 1_000_000} MB"
    aid = new_id("art", 4)
    a = {"id": aid, "turn_id": turn_id, "path": rel, "sha256": _sha(data), "size": len(data),
         "type": "text" if Path(rel).suffix.lower() in TEXT_EXT else "binary", "origin": origin, "provider": provider,
         "created": now(), "status": status, "reason": why}
    if status == "collected":
        f = _root(session_id) / aid / Path(rel).name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        a["stored"] = str(f)
    store.update(session_id, lambda s: s["artifacts"].append(a))
    store.emit(session_id, "artifact.discovered", turn_id, provider, artifact=aid, path=rel, status=status)
    return a


def from_text(session_id: str, turn_id: str, text: str, provider: str = "") -> list:
    out = []
    for m in FENCE.finditer(text or ""):
        path = m.group(2) or m.group(3)
        out.append(register(session_id, turn_id, path, m.group(4).encode("utf-8"), "answer code block", provider))
    return out[:30]


def from_workspace(session_id: str, turn_id: str, ws: Path, since: float, provider: str = "") -> list:
    out = []
    if not ws.is_dir():
        return out
    for f in sorted(ws.rglob("*")):
        if f.is_file() and f.stat().st_mtime >= since - 1:
            out.append(register(session_id, turn_id, f.relative_to(ws).as_posix(), f.read_bytes(), "cli workspace", provider))
    return out[:100]


def get(session: dict, aid: str) -> dict:
    a = next((x for x in session["artifacts"] if x["id"] == aid), None)
    if not a:
        raise AIWSError("Artifact not found")
    return a


def content(session: dict, aid: str) -> bytes:
    a = get(session, aid)
    if a["status"] == "quarantined":
        raise AIWSError(f"Artifact is quarantined: {a['reason']}")
    return Path(a["stored"]).read_bytes()


def preview(session: dict, aid: str) -> dict:
    a = get(session, aid)
    b = content(session, aid)
    return {**a, "text": b.decode("utf-8", "replace")[:200_000] if a["type"] == "text" else ""}


def _target(rel: str) -> Path:
    from backend.execution import files as ide_fs
    try:
        return ide_fs.safe(safe_rel(rel))
    except ide_fs.FsError as e:
        raise AIWSError(str(e))


def diff(session: dict, aid: str, target: str = "") -> dict:
    a = get(session, aid)
    if a["type"] != "text":
        raise AIWSError("Only text artifacts can be compared")
    new = content(session, aid).decode("utf-8", "replace")
    t = target or a["path"]
    p = _target(t)
    old = p.read_text("utf-8", "replace") if p.is_file() else ""
    d = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{t}", f"b/{t}"))
    return {"artifact": aid, "target": safe_rel(t), "exists": p.is_file(), "target_sha256": _sha(p.read_bytes()) if p.is_file() else "",
            "diff": d or "(no differences)", "identical": not d}


def apply(session_id: str, aid: str, target: str, expected_sha: str) -> dict:
    """Explicit researcher action after seeing the diff."""
    from backend.agent import sessions as store
    s = store.get(session_id)
    a = get(s, aid)
    if a["status"] != "collected":
        raise AIWSError(f"Artifact is {a['status']}")
    data = content(s, aid)
    t = safe_rel(target or a["path"])
    p = _target(t)
    cur = _sha(p.read_bytes()) if p.is_file() else ""
    if cur != (expected_sha or ""):
        raise AIWSError("The target changed since the diff was shown — compare again before applying")
    backup = ""
    if p.is_file():
        from backend.execution.code_projects import active_dir
        b = active_dir() / ".phdlab" / "backups" / time.strftime("%Y%m%d-%H%M%S") / t
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
        backup = str(b)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)

    def fn(x):
        for y in x["artifacts"]:
            if y["id"] == aid:
                y.update(status="applied", applied_to=t, applied_at=now(), backup=backup)
        x["approvals"].append({"id": new_id("ap", 4), "turn_id": a["turn_id"], "kind": "apply_artifact", "name": t,
                               "args": {"artifact": aid}, "risk": 2, "status": "approved", "decided_by": "researcher",
                               "decided_at": now(), "result": {"backup": backup}})
    store.update(session_id, fn)
    store.emit(session_id, "artifact.updated", a["turn_id"], artifact=aid, status="applied", target=t)
    return {"applied": t, "backup": backup}


def reject(session_id: str, aid: str, reason: str = "") -> dict:
    from backend.agent import sessions as store

    def fn(x):
        a = get(x, aid)
        if a["status"] == "applied":
            raise AIWSError("Artifact was already applied (restore it from the backup if needed)")
        a.update(status="rejected", reason=reason[:300])
        return a
    a = store.update(session_id, fn)
    store.emit(session_id, "artifact.updated", a["turn_id"], artifact=aid, status="rejected")
    return a
