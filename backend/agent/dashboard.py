"""The minimal tracking view (90-day simulation spec §7): what is shown by default —

    current goal · current step (and the provider on it) · status · pinned results · next decision

— and, under "Advanced details", runs, approvals, resources and providers. Shared by the dashboard page, `/status` in the
chat and `phdlab status`.
"""
from __future__ import annotations


def _goal() -> str:
    from backend.agent import outline
    o = outline.get()
    if o["topic"]:
        return o["topic"]
    if o["keywords"]:
        return "Từ khoá: " + ", ".join(o["keywords"][:8])
    try:
        from backend.memory import state as S
        obj = S.current()["objective"]
        return "; ".join(str(g) for g in obj[:2])
    except Exception:
        return ""


def pending() -> list:
    """Everything that waits for the researcher, across conversations and runs (newest first)."""
    from backend.agent import runs, sessions
    out = []
    for r in runs.list_runs("APPROVAL_PENDING,NEEDS_USER_ACTION", limit=50):
        out.append({"kind": "run", "id": r["id"], "title": r["title"], "status": r["status"],
                    "text": r["next_decision"] or r["reason"], "session_id": r["session_id"], "ts": r["updated"]})
    for c in sessions.list_sessions(limit=60):
        if not c["pending_approvals"]:
            continue
        s = sessions.get(c["id"])
        for a in s["approvals"]:
            if a["status"] == "pending":
                out.append({"kind": "approval", "id": a["id"], "title": a["name"], "status": "pending",
                            "text": a.get("reason", ""), "session_id": c["id"], "ts": a["created"]})
    try:
        from backend.memory import lifecycle
        n = len(lifecycle.list_candidates("pending"))
        if n:
            out.append({"kind": "memory", "id": "", "title": f"{n} đề xuất ghi nhớ", "status": "pending",
                        "text": "đề xuất cập nhật bộ nhớ dự án", "session_id": "", "ts": 0})
    except Exception:
        pass
    return sorted(out, key=lambda x: -(x["ts"] or 0))


def status(advanced: bool = False) -> dict:
    from backend.agent import outline, pins, runs
    from backend.core.config import active_project
    active = runs.list_runs("RUNNING,VERIFYING,RECOVERING,BLOCKED", limit=10)
    waiting = pending()
    cur = active[0] if active else None
    st = "running" if active else ("waiting approval" if waiting else "idle")
    o = outline.get()
    out = {"project": active_project().get("name", ""), "goal": _goal(), "outline_level": o["level"],
           "outline_label": o["level_label"], "status": st,
           "current": cur and {"run": cur["id"], "title": cur["title"], "status": cur["status"],
                               "step": (cur.get("current") or {}).get("label", ""),
                               "provider": (cur.get("current") or {}).get("provider", ""),
                               "progress": f"{cur['done']}/{cur['steps']}"},
           "active_runs": active, "pending": waiting[:20],
           "next_decision": (waiting[0]["text"] or waiting[0]["title"]) if waiting else "",
           "pins": [p for p in pins.list_pins() if p["status"] != "deprecated"][-8:][::-1],
           "recent_runs": runs.list_runs(limit=8)}
    from backend.execution.remote_compute import list_runs as compute_runs
    out["compute_runs"] = compute_runs()[:8]
    if advanced:
        from backend.execution import guard
        from backend.providers.research import describe_all
        out["resources"] = guard.snapshot()
        try:
            from backend.execution.resources import gpus
            out["gpus"] = gpus()
        except Exception:
            out["gpus"] = []
        try:
            from backend.execution.resources import loaded_local_models
            out["local_models"] = loaded_local_models()
        except Exception:
            out["local_models"] = {}
        out["providers"] = describe_all()
    return out


def status_text() -> str:
    from backend.core.i18n import L
    d = status()
    lines = [L("**Dự án:** ", "**Project:** ") + d["project"],
             L("**Mục tiêu:** ", "**Goal:** ") + (d["goal"] or L("(chưa có — bắt đầu bằng /outline)", "(none yet — start with /outline)")),
             L(f"**Đề cương:** cấp {d['outline_level']}/5", f"**Outline:** level {d['outline_level']}/5")
             + (f" · {d['outline_label']}" if d['outline_label'] else "")]
    if d["current"]:
        c = d["current"]
        lines.append(L("**Đang chạy:** ", "**Running:** ") + f"{c['title']} — {c['step']} ({c['provider']}) · {c['status']} · {c['progress']}")
    else:
        lines.append(L("**Đang chạy:** không có", "**Running:** nothing"))
    if d["pending"]:
        lines.append(L(f"**Cần bạn duyệt ({len(d['pending'])}):**", f"**Waiting for your approval ({len(d['pending'])}):**"))
        lines += [f"- {p['title']} — {p['text'][:140]}" for p in d["pending"][:6]]
    if d["pins"]:
        lines.append(L("**Kết quả đã ghim:**", "**Pinned results:**"))
        lines += [f"- [{p['status']}] {p['title']}" for p in d["pins"][:6]]
    if d["next_decision"]:
        lines.append(L("**Quyết định tiếp theo:** ", "**Next decision:** ") + d["next_decision"])
    return "\n".join(lines)
