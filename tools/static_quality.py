"""Capture static/dependency scan results without hiding findings or auto-upgrading dependencies."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/autonomy-qa/static"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    commands = [
        ("ruff", [sys.executable, "-m", "ruff", "check", "backend", "--output-format=json"], ROOT),
        ("bandit", [sys.executable, "-m", "bandit", "-q", "-r", "backend", "-f", "json"], ROOT),
        ("pip-audit", [sys.executable, "-m", "pip_audit", "--format=json", "--progress-spinner=off"], ROOT),
        ("npm-audit", ["npm.cmd" if sys.platform == "win32" else "npm", "audit", "--json"], ROOT / "frontend"),
    ]
    reports = []
    for name, cmd, cwd in commands:
        started = time.monotonic()
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=300, check=False)
            (OUTPUT / (name + ".json")).write_bytes(result.stdout)
            (OUTPUT / (name + ".stderr.log")).write_bytes(result.stderr)
            reports.append({"scan": name, "exit_code": result.returncode, "status": "PASS" if result.returncode == 0 else "FINDINGS_OR_ERROR", "elapsed_seconds": time.monotonic() - started})
        except (OSError, subprocess.TimeoutExpired) as exc:
            reports.append({"scan": name, "status": "BLOCKED", "error": str(exc)})
        print(json.dumps(reports[-1]), flush=True)
    (OUTPUT / "summary.json").write_text(json.dumps(reports, indent=2), "utf-8")
    return 0 if all(r["status"] == "PASS" for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
