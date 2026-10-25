"""Evidence-driven local production gate. Suite success is not blanket feature certification."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.quality_evidence import assess


def run_orchestrator(args):
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    folder = ROOT / "qa/live_e2e/runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + sha[:7])
    folder.mkdir(parents=True)
    report = {"source_commit": sha, "model": args.model, "phases": [], "release_decision": "BLOCKED"}

    def phase(name, cmd, cwd=ROOT, timeout=1800):
        start = time.monotonic()
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
            (folder / (name + ".log")).write_bytes(result.stdout + result.stderr)
            item = {"name": name, "command": cmd, "exit_code": result.returncode, "status": "PASS" if result.returncode == 0 else "FAIL"}
        except (OSError, subprocess.TimeoutExpired) as exc:
            item = {"name": name, "command": cmd, "status": "BLOCKED", "reason": str(exc)}
        item["elapsed_seconds"] = time.monotonic() - start
        report["phases"].append(item)
        (folder / "report.json").write_text(json.dumps(report, indent=2), "utf-8")

    if args.profile in ("all", "live-e2e", "quick"):
        phase("live-workflows", [sys.executable, "-B", str(ROOT / "tools/autonomy_harness.py"), "--model", args.model, "--rounds", "1" if args.profile == "quick" else "3", "--browser", "--output", str(folder / "live")])
    if args.profile in ("all", "backend-qa"):
        phase("backend", [sys.executable, "-B", str(ROOT / "tools/backend_quality_gate.py"), "--profile", "full" if args.full_backend else "smoke", "--i-understand-full-suite", "--output-dir", str(folder / "backend")])
    if args.profile in ("all", "frontend") and not args.skip_frontend:
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        phase("frontend-build", [npm, "run", "build"], ROOT / "frontend")
        phase("frontend", [npm, "run", "test:coverage"], ROOT / "frontend")
        coverage_path = ROOT / "frontend/coverage/coverage-summary.json"
        if coverage_path.is_file():
            (folder / "frontend-coverage.json").write_bytes(coverage_path.read_bytes())
    if args.profile == "all":
        phase("stress", [sys.executable, "-B", str(ROOT / "tools/stress_runtime.py"), "--workers", "16", "--rounds", "3", "--out", str(folder / "stress.json")])

    backend_path = folder / "backend/report.json"
    if backend_path.is_file():
        backend = json.loads(backend_path.read_text("utf-8"))
        report["backend_assessment"] = assess(backend["summary"], backend["coverage"])
    frontend_path = folder / "frontend-coverage.json"
    if frontend_path.is_file():
        total = json.loads(frontend_path.read_text("utf-8"))["total"]
        report["frontend_coverage_complete"] = all(total[key]["pct"] == 100 for key in ("lines", "branches", "functions", "statements"))
    if any(p["status"] == "FAIL" for p in report["phases"]):
        report["release_decision"] = "FAIL"
    elif report.get("backend_assessment") == "FAIL":
        report["release_decision"] = "FAIL"
    report['coverage_policy'] = 'INFORMATIONAL'
    report["limitations"] = ["No automatic human signoff", "Unexecuted gates remain BLOCKED", "Live Qwen dummy-agent tests do not establish scientific autonomy", "Source coverage and branch/journey coverage are separate measurements"]
    report["source_files_sha256"] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for root in (ROOT / "backend", ROOT / "frontend/src", ROOT / "tools") for path in root.rglob("*") if path.suffix in (".py", ".ts", ".tsx", ".mjs")}
    (folder / "report.json").write_text(json.dumps(report, indent=2), "utf-8")
    (folder / "RELEASE_DECISION.md").write_text("# Production release assessment\n\nDecision: **" + report["release_decision"] + "**\n\nCoverage is informational. Passing tests do not override missing gates, skipped cases or required owner signoff.\n", "utf-8")
    print(json.dumps({"decision": report["release_decision"], "evidence": str(folder)}))
    return 0 if report["release_decision"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["all", "live-e2e", "backend-qa", "frontend", "quick"], default="all")
    parser.add_argument("--model", default="qwen/qwen3.5-9b")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--full-backend", action="store_true", default=True)
    parser.add_argument("--smoke-backend", dest="full_backend", action="store_false")
    return run_orchestrator(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
