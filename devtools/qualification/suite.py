"""Frozen qualification suites (6.6.4 B1; RQ-13). A suite is frozen by the sha256 of its canonical JSON, kept beside it
in suite.sha256: load() refuses a suite whose content no longer matches, and campaign_template() starts the campaign
record that backend.agent.qualification scores (B5) with that digest and its denominators."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = {"guided", "open-ended"}


def canonical_digest(suite: dict) -> str:
    return hashlib.sha256(json.dumps(suite, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def validate(suite: dict) -> list[str]:
    problems = []
    cases = suite.get("cases") or []
    ids = [c.get("id") for c in cases]
    if not cases or len(set(ids)) != len(ids):
        problems.append("Cases must exist and have unique ids")
    for c in cases:
        if c.get("kind") not in KINDS:
            problems.append(f"{c.get('id')}: kind must be guided or open-ended")
        if not str(c.get("question") or "").strip():
            problems.append(f"{c.get('id')}: question missing")
        if not c.get("data") or any(len(str(d.get("sha256", ""))) != 64 for d in c["data"]):
            problems.append(f"{c.get('id')}: every dataset needs its sha256")
        if c.get("kind") == "open-ended" and not any(d.get("role") == "held_out" for d in c.get("data") or []):
            problems.append(f"{c.get('id')}: an open-ended case needs held-out data")
        if not set(c.get("measures") or []) <= {f"RQ-{i:02d}" for i in range(1, 15)} or not c.get("measures"):
            problems.append(f"{c.get('id')}: measures must be RQ-01..RQ-14")
    budget = suite.get("budget") or {}
    for key in ("max_turns", "max_restarts", "max_wall_seconds"):
        if not isinstance(budget.get(key), int) or budget[key] < 0:
            problems.append(f"budget.{key} must be a whole number")
    if not suite.get("stopping_rules"):
        problems.append("Stopping rules are required before running")
    return problems


def load(folder: Path) -> dict:
    """The suite, only if valid and unchanged since it was frozen."""
    suite = json.loads((folder / "suite.json").read_text("utf-8"))
    frozen = (folder / "suite.sha256").read_text("utf-8").strip()
    if canonical_digest(suite) != frozen:
        raise ValueError(f"Suite {folder.name} changed after it was frozen; freeze a new version instead of editing it")
    problems = validate(suite)
    if problems:
        raise ValueError("; ".join(problems))
    return suite


def campaign_template(folder: Path, campaign_id: str) -> dict:
    """The empty campaign record for B5: every planned case listed, nothing measured yet (all criteria NOT_RUN)."""
    suite = load(folder)
    return {"campaign_id": campaign_id, "suite_id": suite["suite_id"], "suite_digest": canonical_digest(suite),
            "planned_cases": len(suite["cases"]), "budget": suite["budget"],
            "cases": [{"case_id": c["id"], "kind": c["kind"], "planned_measures": c["measures"], "attempts": [],
                       "interventions": {}, "measurements": {}} for c in suite["cases"]]}
