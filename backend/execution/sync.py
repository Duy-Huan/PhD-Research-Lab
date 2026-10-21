"""VS Code ↔ PhD Lab: experiments are coded in VS Code; this brings the results back into the research project.

    open      code project → VS Code (its Python env is written into .vscode/settings.json)
    scan      what changed since the last sync: git changes, metrics files (metrics.json anywhere under outputs/,
              results/, runs/ or the project root) and figures written since then
    propose   the scan becomes proposals in the conversation — "Commit code" and "Ghim kết quả" — that the
              researcher accepts or rejects; nothing is committed or pinned without that decision

    <code project>/.phdlab/sync.json   time of the last sync
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

METRIC_DIRS = ("", "outputs", "results", "runs", "logs")
FIG_EXT = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}


def _state_file() -> Path:
    from backend.execution.code_projects import active_dir
    f = active_dir() / ".phdlab" / "sync.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    return f


def last_sync() -> float:
    try:
        return float(json.loads(_state_file().read_text("utf-8")).get("ts") or 0)
    except (OSError, ValueError):
        return 0.0


def _metrics(root: Path, since: float) -> list:
    out = []
    for d in METRIC_DIRS:
        base = root / d if d else root
        if not base.is_dir():
            continue
        for f in (base.rglob("metrics*.json") if d else base.glob("metrics*.json")):
            if ".phdlab" in f.parts or f.stat().st_mtime < since:
                continue
            try:
                data = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            nums = {k: v for k, v in (data.items() if isinstance(data, dict) else [])
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
            if nums:
                out.append({"path": str(f.relative_to(root)).replace("\\", "/"), "metrics": nums, "mtime": f.stat().st_mtime})
    return sorted(out, key=lambda x: -x["mtime"])[:20]


def _figures(root: Path, since: float) -> list:
    out = []
    for d in ("outputs", "figures", "results"):
        base = root / d
        if base.is_dir():
            out += [str(f.relative_to(root)).replace("\\", "/") for f in base.rglob("*")
                    if f.suffix.lower() in FIG_EXT and f.is_file() and f.stat().st_mtime >= since]
    return sorted(out)[:50]


def scan() -> dict:
    from backend.execution import gitops
    from backend.execution.code_projects import active, active_dir
    root = active_dir()
    since = last_sync()
    try:
        g = gitops.status()
    except Exception as e:  # git missing / broken repo: results can still come back
        g = {"repo": False, "files": [], "error": str(e)[:200]}
    files = [f for f in g.get("files") or [] if not f["path"].startswith(".phdlab/")]
    return {"project": (active() or {}).get("name", ""), "since": since, "repo": g.get("repo", False),
            "changes": files[:200], "metrics": _metrics(root, since), "figures": _figures(root, since),
            "head": (g.get("commits") or [{}])[0].get("hash", "")}


def propose(session_id: str) -> dict:
    """Turn the scan into accept / reject proposals in the conversation (and remember the sync time)."""
    from backend.agent import new_id, now, sessions
    sc = scan()
    aps = []
    if sc["changes"]:
        names = [f["path"] for f in sc["changes"]]
        aps.append({"name": "commit_code", "args": {"message": f"VS Code: {len(names)} file thay đổi", "files": names[:100]},
                    "reason": "thay đổi code từ VS Code: " + ", ".join(names[:6]) + ("…" if len(names) > 6 else "")})
    for m in sc["metrics"][:5]:
        aps.append({"name": "pin_result", "reason": f"metrics mới trong {m['path']}",
                    "args": {"kind": "result", "title": f"{sc['project']} · {m['path']}",
                             "body": ", ".join(f"{k}={v:g}" for k, v in m["metrics"].items())[:3000]}})
    sessions.get(session_id)
    for a in aps:
        ap = {"id": new_id("ap", 4), "turn_id": "", "kind": "action", "name": a["name"], "args": a["args"], "risk": 1,
              "status": "pending", "created": now(), "reason": a["reason"]}
        sessions.update(session_id, lambda x, ap=ap: x["approvals"].append(ap))
        sessions.emit(session_id, "action.approval_required", "", "phdlab", approval=ap["id"], action=ap["name"], risk=1)
    lines = [f"**Đồng bộ từ VS Code** — {sc['project']}"]
    lines.append(f"- {len(sc['changes'])} file thay đổi" + (" (chưa có git repo)" if not sc["repo"] else ""))
    lines.append(f"- {len(sc['metrics'])} file metrics mới, {len(sc['figures'])} hình mới")
    if not aps:
        lines.append("Không có gì mới để lưu.")
    else:
        lines.append("Duyệt từng đề xuất bên dưới để lưu vào dự án.")
    m = sessions.add_message(session_id, "assistant", "\n".join(lines), "", provider="phdlab", kind="sync")
    sessions.emit(session_id, "message.completed", "", "phdlab", message_id=m["id"], text=m["content"], chars=len(m["content"]))
    _state_file().write_text(json.dumps({"ts": time.time()}), "utf-8")
    return {**sc, "proposals": len(aps)}
