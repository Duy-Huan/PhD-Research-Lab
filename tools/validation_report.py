"""Display one canonical Verification Harness receipt without combining historical runs.

Use: python tools/validation_report.py --report output/<run>/report.json
This reader never runs tests, imports successful provider logs or certifies a release.
The old date/provider-specific aggregator is retired; retained historical files stay intact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devtools.verification.runner import identity


def render_receipt(path: Path) -> tuple[str, int]:
    """Read only: retain recorded scope and require current source for exit success."""
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("Expected a canonical Verification Harness schema1 report")
    states = ("PASS", "FAIL", "ERROR", "SKIP", "NOT_RUN", "BLOCKED", "UNVERIFIED")
    counts = record.get("counts")
    cases = record.get("cases")
    if (not isinstance(counts, dict) or not isinstance(cases, list)
            or any(type(counts.get(state)) is not int or counts[state] < 0 for state in states)
            or any(not isinstance(case, dict) or case.get("status") not in states for case in cases)
            or any(counts[state] != sum(case.get("status") == state for case in cases) for state in states)):
        raise ValueError("Canonical case counts are missing or inconsistent; no result was qualified")
    decision = record.get("decision")
    if decision not in ("PASS", "FAIL", "BLOCKED", "NOT_RUN"):
        raise ValueError("Unknown canonical decision")
    if decision == "PASS" and (not cases or counts["PASS"] != len(cases)):
        raise ValueError("PASS receipt contains incomplete or failed execution")
    source = record.get("source")
    current = isinstance(source, dict) and source == identity(ROOT) and record.get("source_stable") is True
    steps = record.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Canonical gate results are absent")
    if decision == "PASS" and any(not isinstance(step, dict) or step.get("status") != "PASS" for step in steps):
        raise ValueError("PASS receipt contradicts its gate results")
    result = {
        "recorded_decision": decision, "profile": record.get("profile"), "component": record.get("component"),
        "head_sha": record.get("head_sha"), "timestamp": record.get("timestamp"), "mode": record.get("mode"),
        "source_sha256": source.get("sha256") if isinstance(source, dict) else None,
        "current_source": current, "counts": counts, "coverage": record.get("coverage"),
        "coverage_policy": "INFORMATIONAL; desired production line/branch target100% is not presumed",
        "separate_live_inventory": record.get("separate_live_inventory"),
        "limitations": record.get("limitations", []) + [
            "This is a receipt reader, not another test runner or release decision.",
            "Scoped software PASS never substitutes for current live provider, research, AI-UAT or GitHub qualification.",
            "Historical/stale reports remain readable but cannot return verification success."]}
    return json.dumps(result, ensure_ascii=False, indent=2), (0 if decision == "PASS" and current else 1 if decision == "FAIL" else 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="One actual scripts/verify.py report.json")
    args = parser.parse_args()
    try:
        output, status = render_receipt(args.report)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, "BLOCKED: " + str(error) + "\n")
    print(output)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
