"""Recovery regressions; GitHub states are explicit fixtures, not live merge proof."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GateAccounting(unittest.TestCase):
    def invoke(self, needs, phase='development'):
        result = subprocess.run(
            [sys.executable, str(ROOT/'scripts/quality_gate.py'), 'aggregate', '--phase', phase],
            cwd=ROOT, env=dict(os.environ, NEEDS_JSON=json.dumps(needs)),
            capture_output=True, text=True, check=False)
        return result.returncode, json.loads(result.stdout)

    def fixture(self):
        return {name: {'result': 'success'} for name in
                ['policy', 'backend', 'frontend', 'security', 'browser']}

    def test_qa_requires_executed_software_gate_without_optional_live_jobs(self):
        self.assertEqual(self.invoke({'development-gate':{'result':'success'}},'qa')[0],0)
        for result in ('failure','skipped','cancelled','queued',None):
            with self.subTest(result=result):
                self.assertNotEqual(self.invoke({'development-gate':{'result':result}},'qa')[0],0)
        self.assertNotEqual(self.invoke({},'qa')[0],0)

    def test_failed_dependency_remains_fail_instead_of_blocked(self):
        needs = self.fixture(); needs['backend']['result'] = 'failure'
        code, report = self.invoke(needs)
        self.assertNotEqual(code, 0)
        self.assertEqual(report['decision'], 'FAIL')
        self.assertEqual(report['states']['backend'], 'FAIL')
        self.assertEqual(report['upstream_results']['backend'], 'failure')

    def test_unexecuted_dependencies_never_pass(self):
        for status in ['skipped', 'cancelled', 'queued', 'timed_out', None]:
            with self.subTest(status=status):
                needs = self.fixture(); needs['backend']['result'] = status
                code, report = self.invoke(needs)
                self.assertNotEqual(code, 0)
                self.assertEqual(report['decision'], 'BLOCKED')

    def test_missing_dependency_cannot_be_masked_by_other_successes(self):
        needs = self.fixture(); del needs['security']
        code, report = self.invoke(needs)
        self.assertNotEqual(code, 0)
        self.assertEqual(report['decision'], 'BLOCKED')

    def test_only_complete_success_passes(self):
        code, report = self.invoke(self.fixture())
        self.assertEqual(code, 0)
        self.assertEqual(report['decision'], 'PASS')

    def test_malformed_result_preserves_fail_closed_behavior(self):
        code, report = self.invoke(['success'])
        self.assertNotEqual(code, 0)
        self.assertEqual(report['decision'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
