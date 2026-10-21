"""Shared Context Hub: lets the follow-up chats of Tools 1-4 see each other's work.

Sources assembled into a compact context block:
  1. latest output of every other tool (lit2plan.md, experiment_design.md, main.tex + review, masterclass guide)
  2. pinned notes (📌) saved from any chat  -> data/workspace/shared_context.json
  3. the last few messages of every other tool's active chat session
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timezone

from backend.core.config import workspace


def _notes_path():
    return workspace() / "shared_context.json"  # per project
MAX_NOTES = 200
_lock = threading.RLock()

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
# ------------------------------------------------------------------ pinned notes
def load_notes() -> list:
    """Load approved notes and import any curated pre-v5 knowledge records exactly once."""
    with _lock:
        notes = _load_notes()
        from backend.memory.knowledge import legacy_notes
        existing = {n.get("id") for n in notes}
        migrated = [n for n in legacy_notes() if n["id"] not in existing]
        if migrated:
            notes = migrated + notes  # existing recent notes stay at the tail used by retrieval
            _save_notes(notes)
        return notes


def _load_notes() -> list:
    p = _notes_path()
    if not p.exists():
        return []
    try:
        notes = json.loads(p.read_text("utf-8")).get("notes", [])
        if not isinstance(notes, list) or not all(isinstance(n, dict) and "id" in n and "text" in n for n in notes):
            raise ValueError("invalid notes")
        return notes
    except (ValueError, AttributeError):
        from backend.memory.store import quarantine
        quarantine(p)  # keep the damaged file: the next save would otherwise destroy every pinned note
        return []
    except OSError:
        return []


def _save_notes(notes: list) -> None:
    from backend.memory.store import replace_retry
    # Curated knowledge is durable. The rolling limit applies only to ordinary shared-context notes.
    regular = {n["id"] for n in [n for n in notes if not n.get("legacy_knowledge")][-MAX_NOTES:]}
    retained = [n for n in notes if n.get("legacy_knowledge") or n["id"] in regular]
    tmp = _notes_path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"notes": retained}, ensure_ascii=False, indent=1), "utf-8")
    replace_retry(tmp, _notes_path())


def add_note(tool: str, text: str, source: str = "") -> dict:
    note = {"id": secrets.token_hex(4), "tool": tool if tool in TOOL_LABELS else "data",
            "text": str(text).strip()[:6000], "source": str(source)[:200], "ts": _now()}
    with _lock:
        notes = load_notes()
        notes.append(note)
        _save_notes(notes)
    return note


# ------------------------------------------------------------------ shared context block
