"""The research agent layer (v5): ONE chat per project, two agents (Research, Reviewer), skills and background runs.

    orchestrator.py    the Primary Research Orchestrator: one chat turn — skill / intent → policy → context → provider
                       stream → proposals the researcher accepts or rejects (UI and CLI share it)
    skills.py          "/" commands: Markdown skills (built-in, the researcher's, per project)
    launch.py          prompt → skill → research run; the transparent intent router
    runs.py            durable research runs: state machine, resource guard, budget, idempotency, recovery, events
    simulation.py      the 90-day dry-run on the real run engine (SYNTHETIC executor)
    acceptance.py      the eight acceptance criteria and their evidence
    outline.py         the research outline in levels (keywords → proposal) with attached files
    dashboard.py       the minimal tracking view (goal, current step, status, pins, next decision)
    sessions.py        conversations: messages, turns, approvals, artifacts, memory candidates, events
    policy.py          effective settings and the approval rule (risk tiers)
    project_context.py the shared research context + the actions the chat may propose
    context.py         context compiler: manifest with provenance, trust labels, budget, cache
    mcp_policy.py      per-session MCP allowlist and ephemeral tokens
    memory_modes.py    Off / Manual / Suggest / restricted Auto memory proposals
    artifacts.py       files proposed by a provider: preview, diff, apply-with-backup (never automatic)
    pins.py            pinned results shared by every conversation
"""
from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path

SESSION_RE = re.compile(r"^as-[0-9a-f]{10}$")
MODULES = ("global",)


class AIWSError(ValueError):
    pass


def now() -> float:
    return round(time.time(), 3)


def new_id(prefix: str, n: int = 5) -> str:
    return f"{prefix}-{secrets.token_hex(n)}"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=str)
    from backend.memory.store import replace_retry
    replace_retry(tmp, path)  # Windows: a reader holding the file open for a moment is not an error


def read_json(path: Path, default=None, tries: int = 40):
    for i in range(tries):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except PermissionError:  # the file is being replaced right now (Windows sharing violation)
            time.sleep(0.005 * (i + 1))
        except (OSError, ValueError):
            return default
    return default


def redact(text: str) -> str:
    from backend.core.telemetry import redact as _r
    return _r(text or "")
