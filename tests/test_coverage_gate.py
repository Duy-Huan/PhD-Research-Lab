"""FQC-COVERAGE-GATE-662: coverage is a hard gate (owner 2026-10-27: target 90-100%, try for 100%).

The backend gate fails below its minimum (no exclusions, missing data never passes), the PR/full/release runner
always passes the minimum, and the frontend has vitest thresholds that only ratchet upward."""
import re
import subprocess
import sys
import unittest

import _env
from devtools.verification import runner


class CoverageGate(unittest.TestCase):
    def test_backend_verdict_fails_below_the_minimum_and_without_data(self):
        from tools.backend_quality_gate import coverage_verdict
        self.assertEqual(coverage_verdict({"percent_covered": 90.0}, 90.0), (True, "PASS"))
        self.assertEqual(coverage_verdict({"percent_covered": 89.99}, 90.0), (False, "FAIL"))
        self.assertEqual(coverage_verdict({}, 90.0), (False, "FAIL"), "missing coverage data never passes a gate")
        self.assertEqual(coverage_verdict({"percent_covered": 10}, 0), (True, "INFORMATIONAL"))
        self.assertEqual(coverage_verdict({}, 0), (True, "UNAVAILABLE"))

    def test_runner_always_enforces_the_backend_minimum(self):
        self.assertGreaterEqual(getattr(runner, "BACKEND_COVERAGE_MIN", 0), 90.0)
        source = (_env.ROOT / "devtools/verification/runner.py").read_text("utf-8")
        self.assertIn("'--coverage-min', str(BACKEND_COVERAGE_MIN)", source)
        self.assertNotIn("'mode':'INFORMATIONAL'", source)
        coveragerc = (_env.ROOT / ".coveragerc").read_text("utf-8")
        self.assertNotIn("omit", coveragerc, "coverage is never raised by excluding production files")
        help_text = subprocess.run([sys.executable, str(_env.ROOT / "tools/backend_quality_gate.py"), "--help"],
                                   capture_output=True, text=True, timeout=60).stdout
        self.assertIn("--coverage-min", help_text)

    def test_frontend_thresholds_exist_and_never_drop_below_the_6_6_2_baseline(self):
        config = (_env.ROOT / "frontend/vite.config.ts").read_text("utf-8")
        match = re.search(r"thresholds:\s*\{([^}]*)\}", config)
        self.assertIsNotNone(match, "frontend coverage thresholds are configured")
        values = {k: float(v) for k, v in re.findall(r"(\w+):\s*([\d.]+)", match.group(1))}
        baseline = {"lines": 66, "branches": 65, "functions": 53, "statements": 65}
        for key, floor in baseline.items():
            self.assertGreaterEqual(values.get(key, 0), floor, key)


if __name__ == "__main__":
    unittest.main()
