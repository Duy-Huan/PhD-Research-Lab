"""Shared Context Hub: lets the follow-up chats of Tools 1-4 see each other's work.

Sources assembled into a compact context block:
  1. latest output of every other tool (lit2plan.md, experiment_design.md, main.tex + review, masterclass guide)
  2. pinned notes (📌) saved from any chat  -> data/workspace/shared_context.json
  3. the last few messages of every other tool's active chat session
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import datetime, timezone

from .config import workspace


def _notes_path():
    return workspace() / "shared_context.json"  # per project
MAX_NOTES = 200
_lock = threading.Lock()

TOOL_LABELS = {
    "lit2plan": "Tool 1 · Lit2Plan research direction",
    "experiment": "Tool 2 · Experimental design",
    "data": "Tool 3 · Data chat (results → LaTeX tables)",
    "paper": "Tool 3 · Paper (main.tex + peer review)",
    "masterclass": "Tool 4 · Masterclass guide",
    "review": "Tool 3 · Paper Review (external manuscript, simulated venue review)",
    "ide": "💻 Workspace (co-coding agent)",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ tool outputs
def _read(name: str) -> str:
    f = workspace() / name
    return f.read_text("utf-8") if f.exists() else ""


def tool_output(tool: str) -> dict:
    """Latest saved output of a tool: {content, updated}."""
    files = {"lit2plan": "lit2plan.md", "experiment": "experiment_design.md", "masterclass": "masterclass_guide.md"}
    if tool in files:
        f = workspace() / files[tool]
        meta = {}
        if tool == "masterclass" and (workspace() / "masterclass_meta.json").exists():
            try:
                meta = json.loads((workspace() / "masterclass_meta.json").read_text("utf-8"))
            except Exception:
                meta = {}
        if tool == "lit2plan" and (workspace() / "lit2plan_sources.json").exists():
            try:
                meta = json.loads((workspace() / "lit2plan_sources.json").read_text("utf-8"))
            except Exception:
                meta = {}
        return {"content": _read(files[tool]), "updated": _mtime(f), **meta}
    if tool == "paper":
        main, review = _read("main.tex"), _read("review.md")
        content = (main and f"=== main.tex ===\n{main}") + (review and f"\n\n=== Peer review (Agent 3.3) ===\n{review}")
        return {"content": content, "updated": _mtime(workspace() / "main.tex")}
    if tool == "review":
        from .review_ext import chat_context, get_active
        rid = get_active()
        return {"content": chat_context(rid), "updated": None, "review_id": rid}
    return {"content": "", "updated": None}


def _mtime(f) -> str | None:
    try:
        return datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return None


# ------------------------------------------------------------------ pinned notes
def load_notes() -> list:
    p = _notes_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text("utf-8")).get("notes", [])
    except (ValueError, AttributeError):
        from .memory.store import quarantine
        quarantine(p)  # keep the damaged file: the next save would otherwise destroy every pinned note
        return []
    except OSError:
        return []


def _save_notes(notes: list) -> None:
    tmp = _notes_path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"notes": notes[-MAX_NOTES:]}, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, _notes_path())


def add_note(tool: str, text: str, source: str = "") -> dict:
    note = {"id": secrets.token_hex(4), "tool": tool if tool in TOOL_LABELS else "data",
            "text": str(text).strip()[:6000], "source": str(source)[:200], "ts": _now()}
    with _lock:
        notes = load_notes()
        notes.append(note)
        _save_notes(notes)
    return note


def delete_note(note_id: str) -> None:
    with _lock:
        _save_notes([n for n in load_notes() if n.get("id") != note_id])


# ------------------------------------------------------------------ shared context block
def build_shared_context(exclude_tool: str, recent_sessions: dict, per_output: int = 6000,
                         notes_budget: int = 8000) -> str:
    """recent_sessions: {tool: [messages]} from the active session of each tool."""
    parts = []
    for tool, label in TOOL_LABELS.items():
        if tool in (exclude_tool, "data"):
            continue
        out = tool_output(tool)["content"]
        if out:
            cut = out[:per_output] + ("\n…[truncated]" if len(out) > per_output else "")
            parts.append(f"## {label} — latest output\n{cut}")
    notes = load_notes()
    if notes:
        used, lines = 0, []
        for n in reversed(notes):  # newest first within budget
            line = f"- 📌 [{TOOL_LABELS.get(n['tool'], n['tool'])}] {n['text']}"
            if used + len(line) > notes_budget:
                break
            lines.append(line)
            used += len(line)
        parts.append("## Pinned notes (researcher-curated, highest priority)\n" + "\n".join(reversed(lines)))
    for tool, msgs in recent_sessions.items():
        if tool == exclude_tool or not msgs:
            continue
        tail = "\n".join(f"{m['role'].upper()}: {m['content'][:800]}" for m in msgs[-4:])
        parts.append(f"## {TOOL_LABELS.get(tool, tool)} — recent chat\n{tail}")
    return "\n\n".join(parts)
