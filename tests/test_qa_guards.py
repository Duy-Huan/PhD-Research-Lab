"""Deliberately injected violations demonstrate permanent anti-fabrication guards."""
import io
import unittest

from pydantic import ValidationError

from tools.protect_agent_resources import violations
from tools.qa_harness import EvidenceRecord, audit_source, release_decision


class QAGuards(unittest.TestCase):
    def test_subtest_failure_and_skip_are_never_counted_as_parent_success(self):
        from tools.backend_quality_gate import QualityGateTestResult
        class Injected(unittest.TestCase):
            def test_subtests(self):
                for index in range(2):
                    with self.subTest(index=index):
                        self.assertEqual(index, 7)
            @unittest.skip('Injected missing dependency')
            def test_skip(self):
                pass
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Injected)
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=QualityGateTestResult).run(suite)
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.subtests), 2)
        self.assertEqual(sorted(c['status'] for c in result.test_cases_recorded), ['FAIL', 'SKIP'])

    def test_version_bump_preserves_validation_regex_and_other_text(self):
        from tools.bump_version import replace_version
        source = 'APP_VERSION = "1.0.0"\nmatcher = r\'APP_VERSION = "([^"]+)"\'\n'
        updated = replace_version(source, '2.0.0')
        self.assertIn('APP_VERSION = "2.0.0"', updated)
        self.assertEqual(updated.splitlines()[1], source.splitlines()[1])

    def test_injected_fabricated_metrics_and_copied_replay_are_rejected(self):
        self.assertTrue(audit_source('def run():\n return {"coverage_pct": 100, "tokens": 123}\n', 'backend/execution/harness.py'))
        self.assertTrue(audit_source('replayed_metrics["x"] = expected_metrics["x"]\n', 'backend/intelligence/reproducibility.py'))
        self.assertFalse(audit_source('metrics = measure_actual_output()\n', 'backend/execution/harness.py'))

    def test_live_evidence_cannot_be_fabricated_or_renamed_from_a_mock(self):
        base = {'id': 'probe', 'mode': 'LIVE_PROVIDER', 'status': 'PASSED', 'executed': True,
                'source_revision': 'fixture-revision', 'command': ['real-probe'], 'artifacts': ['response.json'], 'actual_provider': 'local'}
        self.assertEqual(EvidenceRecord(**base).status, 'PASSED')
        for patch in ({'executed': False}, {'mock_used': True}, {'artifacts': []}, {'actual_provider': None},
                      {'status': 'pretend_pass'}, {'scientific_verified': True}, {'artifacts': ['../escape']},
                      {'requested_provider': 'cloud', 'fallback_reason': None}):
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                EvidenceRecord(**(base | patch))

    def test_missing_tests_or_coverage_never_certify_release(self):
        report = release_decision({}, {}, [])
        self.assertEqual(report['decision'], 'NO-GO')
        self.assertTrue(report['reasons'])

    def test_protected_resources_cannot_be_deleted_or_moved_out(self):
        self.assertEqual(violations('D\tskills/test/SKILL.md\nD\tagent/STATE.md\nR100\tagent/PLAN.md\tdocs/PLAN.md\n'),
                         ['skills/test/SKILL.md', 'agent/STATE.md', 'agent/PLAN.md'])
        self.assertEqual(violations('M\tagent/STATE.md\nA\tskills/new/SKILL.md\nD\toutput/run.log\nR100\tagent/old.md\tagent/new.md\n'), [])
