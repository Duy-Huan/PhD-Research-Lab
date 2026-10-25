"""Owner-authorized regression/coverage/branch policy; explicit software fixtures."""
import io
import json
from pathlib import Path
import unittest

from tools.quality_evidence import assess

ROOT = Path(__file__).resolve().parents[1]


class RegressionOnlyPolicy(unittest.TestCase):
    def good(self):
        return {'total_run': 2, 'passed': 2, 'failures': 0, 'errors': 0, 'skipped': 0}

    def test_measured_low_or_missing_coverage_does_not_fail_complete_regression(self):
        for coverage in (None, {}, {'num_statements': 10},
                         {'num_statements': 10, 'covered_lines': 1, 'num_branches': 8, 'covered_branches': 0}):
            with self.subTest(coverage=coverage):
                self.assertEqual(assess(self.good(), coverage), 'CONDITIONAL')

    def test_full_coverage_never_masks_failed_or_incomplete_regression(self):
        coverage = {'num_statements': 2, 'covered_lines': 2, 'num_branches': 2, 'covered_branches': 2}
        for patch, expected in [({'failures': 1}, 'FAIL'), ({'errors': 1}, 'FAIL'),
                                ({'skipped': 1, 'passed': 1}, 'BLOCKED'),
                                ({'passed': 1}, 'BLOCKED'), ({'unverified': 1}, 'BLOCKED'),
                                ({'total_run': 0, 'passed': 0}, 'BLOCKED')]:
            with self.subTest(patch=patch):
                self.assertEqual(assess(self.good() | patch, coverage), expected)

    def test_missing_or_invalid_execution_counts_fail_closed(self):
        for patch in ({'total_run': -1}, {'total_run': True}, {'passed': -1}, {'passed': 3},
                      {'errors': -1}, {'skipped': '0'}):
            with self.subTest(patch=patch):
                self.assertEqual(assess(self.good() | patch), 'BLOCKED')
        self.assertEqual(assess({'total_run': 2}), 'BLOCKED')

    def test_old_minimum_argument_cannot_reintroduce_a_coverage_gate(self):
        self.assertEqual(assess(self.good(), {'num_statements': 100, 'covered_lines': 1}, minimum=100), 'CONDITIONAL')

    def test_frontend_command_collects_coverage_without_percentage_thresholds(self):
        import ast
        tree = ast.parse((ROOT / 'devtools/verification/runner.py').read_text(encoding='utf-8'))
        values = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self.assertIn('test:coverage', values)
        self.assertFalse(any('coverage.thresholds.' in value for value in values))


class LayersAndFlow(unittest.TestCase):
    def test_live_cases_remain_registered_and_never_execute_in_software_layer(self):
        from devtools.verification.layers import partition
        events = []
        class Cases(unittest.TestCase):
            def test_software(self): events.append('software')
            def test_live(self): events.append('live')
        items = list(unittest.defaultTestLoader.loadTestsFromTestCase(Cases))
        live_id = next(t.id() for t in items if t.id().endswith('test_live'))
        software, deferred = partition(unittest.TestSuite(items), 'software', {live_id})
        result = unittest.TextTestRunner(stream=io.StringIO()).run(software)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(events, ['software'])
        self.assertEqual(deferred, [{'id': live_id, 'status': 'NOT_RUN', 'layer': 'LIVE_PROVIDER', 'required_at': ['qa', 'main']}])
        complete, missing = partition(unittest.TestSuite(items), 'all', {live_id})
        self.assertEqual(complete.countTestCases(), 2)
        self.assertEqual(missing, [])

    def test_declared_live_ids_are_exact_and_do_not_hide_new_software_tests(self):
        from devtools.verification.layers import live_ids
        ids = live_ids()
        self.assertEqual(ids, {
            'test_live_integrations.ClearMLLive.test_create_log_read',
            'test_live_integrations.CodexLive.test_read_only_run',
            'test_vram_gate.LMStudioLive.test_real_gate_and_manual_unload'})
        self.assertFalse(any('*' in name for name in ids))
        self.assertNotIn('test_clearml.ClearMLOffline.test_real_offline_session', ids)
        self.assertNotIn('test_research_engines.OfficialSDKSocket.test_real_sdk_through_adapter_with_bounded_socket_fixture', ids)

    def test_ai_development_guard_only_accepts_dev_and_promotion_is_forward(self):
        from devtools.verification.branch_policy import development_errors, promotion_errors
        self.assertEqual(development_errors('dev'), [])
        for branch in ('main', 'qa', 'feature/new', 'fix/bug', 'HEAD', ''):
            with self.subTest(branch=branch): self.assertTrue(development_errors(branch))
        self.assertEqual(promotion_errors('dev', 'qa'), [])
        self.assertEqual(promotion_errors('qa', 'main'), [])
        for source, target in [('dev', 'main'), ('main', 'dev'), ('feature/new', 'dev'), ('qa', 'dev')]:
            self.assertTrue(promotion_errors(source, target))

    def test_pr_and_dev_workflow_target_the_three_branch_flow(self):
        import yaml
        workflow = yaml.safe_load((ROOT / '.github/workflows/quality.yml').read_text(encoding='utf-8'))
        event = workflow.get('on', workflow.get(True))
        self.assertEqual(event['pull_request']['branches'], ['qa', 'main'])
        self.assertEqual(event['push']['branches'], ['dev'])
        self.assertEqual(set(workflow['jobs']['development-gate']['needs']), {'policy', 'backend', 'frontend', 'security', 'browser'})
        self.assertIn('uat-policy', workflow['jobs']['qa-gate']['needs'])
        condition = workflow['jobs']['uat-policy']['if']
        self.assertIn("github.base_ref == 'qa'", condition)
        self.assertIn("github.base_ref == 'main'", condition)
        self.assertNotIn("github.base_ref == 'dev'", condition)


if __name__ == '__main__': unittest.main()
