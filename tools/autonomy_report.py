"""Build a reproducible audit index from measured artifacts; missing evidence never becomes PASS."""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/autonomy-qa"


def read(path):
    return json.loads(Path(path).read_text("utf-8"))


def main():
    backend = read(OUT / "final-backend/report.json")
    coverage = read(OUT / "release-combined-coverage.json")
    supplemental = read(OUT / "supplemental/report.json")
    front = read(ROOT / "frontend/coverage/coverage-summary.json")
    front_tests = read(OUT / "frontend-results.json")
    stress = read(OUT / "stress.json")
    legacy_path = OUT / "legacy-live-repeat/report.json"
    legacy = read(legacy_path) if legacy_path.is_file() else read(OUT / "legacy-live/report.json")
    initial_legacy = read(OUT / "legacy-live/report.json")
    live = read(OUT / "final-live/report.json")
    browser_run = OUT / "final-live"
    browser = read(browser_run / "browser-report.json")
    static = read(OUT / "static/summary.json")
    bandit_text = (OUT / "static/bandit.json").read_text("utf-8")
    bandit = json.loads(bandit_text[bandit_text.index('{'):])
    totals = coverage["totals"]
    changed = {k: v["summary"] for k, v in coverage["files"].items() if k.endswith(("autonomy.py", "workflow_worker.py", "clearml_worker.py"))}
    source_hashes = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                     for directory in ("backend", "frontend/src", "tools", "tests") for p in (ROOT / directory).rglob("*") if p.suffix in (".py", ".ts", ".tsx", ".mjs")}
    for path in [ROOT / name for name in ("start.py", "run.bat", ".coveragerc", "requirements.txt", "requirements-dev.txt", "frontend/react.html", "frontend/vite.config.ts", "frontend/package.json", "frontend/package-lock.json", "frontend/assets/app.css")]:
        source_hashes[str(path.relative_to(ROOT)).replace('\\', '/')] = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = {
        "decision": "NO-GO", "reason": "Whole-project 100% coverage is not achieved; mandatory skipped and unqualified journeys remain; initial live suite had intermittent failures",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "platform": platform.platform(),
        "versions": {name: importlib.metadata.version(name) for name in ("coverage", "sqlalchemy", "pypdf", "certifi", "defusedxml", "ruff", "bandit", "pip-audit")},
        "offline_tests": backend["summary"], "supplemental_tests": supplemental["summary"], "backend_coverage": totals,
        "coverage_scope": "Full backend run plus a distinct supplemental positive L4 synthesis case; identical production source bytes",
        "frontend_tests": {k: front_tests.get(k) for k in ("numTotalTests", "numPassedTests", "numFailedTests", "numPendingTests")},
        "frontend_coverage": front["total"], "changed_backend_coverage": changed,
        "changed_frontend_coverage": {k: v for k, v in front.items() if k.endswith(("AutonomyPanel.tsx", "autonomyPlan.ts"))},
        "live_workflows": {"passed": live["passed"], "rounds": len([c for c in live["cases"] if c["id"].startswith("four-workflows-round-")]), "workflows": sum(len(c.get("evidence", {}).get("missions", [])) for c in live["cases"] if c["id"].startswith("four-workflows-round-")), "inference_requests": len(live["real_inference_calls"]), "production_hashes_unchanged": live["production_bytes_unchanged"]},
        "browser": browser,
        "legacy_live": {k: legacy[k] for k in ("total_run", "failures", "errors", "skipped")},
        "initial_legacy_live": {k: initial_legacy[k] for k in ("total_run", "failures", "errors", "skipped")},
        "stress_passed": stress["passed"], "stress_phases": len(stress["phases"]),
        "http_p95_ms_per_round": [p["latency"]["p95_ms"] for p in stress["phases"] if p["name"] == "http-load"],
        "static": static, "bandit_metrics": bandit["metrics"]["_totals"],
        "source_files_sha256": source_hashes,
        "unverified_scientific_dimensions": ["novelty", "domain validity", "scientific impact", "generalization across scientific domains", "accountable scientific autonomy at L3/L4"],
    }
    full_ids = {case["id"] for case in backend["cases"]}
    extra_ids = {case["id"] for case in supplemental["cases"]}
    if full_ids & extra_ids:
        raise ValueError("Supplemental test IDs overlap; do not add duplicate test counts")
    summary["unique_backend_tests_executed"] = len(full_ids | extra_ids)
    (OUT / "frontend-coverage-summary.json").write_text(json.dumps(front, indent=2), "utf-8")
    (OUT / "audit-summary.json").write_text(json.dumps(summary, indent=2), "utf-8")
    with tempfile.TemporaryDirectory(prefix="phdlab-api-inventory-") as data:
        os.environ["PHDLAB_DATA_DIR"] = data
        import sys
        sys.path.insert(0, str(ROOT))
        from backend.app import app
        schema = app.openapi()
        (OUT / "openapi.json").write_text(json.dumps(schema, indent=2), "utf-8")
        with (OUT / "api-journey-inventory.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["method", "path", "operation_id", "qualification"])
            count = 0
            for path, item in schema["paths"].items():
                for method, operation in item.items():
                    if method in ("get", "post", "put", "patch", "delete", "options", "head"):
                        writer.writerow([method.upper(), path, operation.get("operationId"), "Requires per-operation production journey qualification; see executed test cases"])
                        count += 1
            summary["openapi_operation_count"] = count
    (OUT / "audit-summary.json").write_text(json.dumps(summary, indent=2), "utf-8")
    gaps = sorted(((v["summary"]["missing_lines"] + v["summary"].get("missing_branches", 0), k, v["summary"]) for k, v in coverage["files"].items()), reverse=True)
    (OUT / "coverage-gaps.json").write_text(json.dumps([{"module": k, "missing": missing, "coverage": v} for missing, k, v in gaps if missing], indent=2), "utf-8")
    print(json.dumps({k: summary[k] for k in ("decision", "offline_tests", "frontend_tests", "legacy_live", "openapi_operation_count")}))


if __name__ == "__main__":
    main()
