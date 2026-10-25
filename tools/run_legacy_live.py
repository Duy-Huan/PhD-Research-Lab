"""Run every legacy live test with an explicitly selected local model and per-case evidence."""
import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests"), str(ROOT / "tests/live_e2e")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/autonomy-qa/legacy-live")
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phdlab-legacy-live-") as temporary:
        os.environ["PHDLAB_DATA_DIR"] = temporary
        os.environ["PHDLAB_LIVE_MODEL"] = "qwen/qwen3.5-9b"
        os.environ["PHDLAB_LIVE_EVIDENCE_DIR"] = str(output)
        os.environ["JUPYTER_DATA_DIR"] = str(Path(temporary) / "_jupyter")
        from tools.backend_quality_gate import QualityGateTestResult
        suite = unittest.defaultTestLoader.loadTestsFromNames(args.modules) if args.modules else unittest.defaultTestLoader.discover(str(ROOT / "tests/live_e2e"), pattern="test_*.py")
        with (output / "unittest.log").open("w", encoding="utf-8") as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=QualityGateTestResult).run(suite)
        report = {"model": os.environ["PHDLAB_LIVE_MODEL"], "total_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "cases": result.test_cases_recorded, "scope": "Legacy integration contracts; test names retaining phi4 are historical; actual model is Qwen 3.5", "limitations": ["Does not replace actual browser E2E", "Some fault cases use protocol fixtures; not a zero-mocks certificate", "Optional external providers stay opt-in"]}
        from backend.agent import missions
        from backend.knowledge import research_store as S
        with S.db() as c:
            failed_ids = [r[0] for r in c.execute("SELECT id FROM missions WHERE status IN ('failed','interrupted','paused')")]
        report["non_successful_missions"] = [missions.get(mid) for mid in failed_ids]
        (output / "report.json").write_text(json.dumps(report, indent=2), "utf-8")
        print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "non_successful_missions")}))
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
