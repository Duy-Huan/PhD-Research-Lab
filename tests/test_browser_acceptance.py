"""Acceptance orchestration tests; explicit fixtures do not certify exploratory UAT."""
import json
import hashlib
from pathlib import Path
import unittest
import tempfile

from devtools.verification.journeys import browser_plan, load_configuration, relevant_contracts
from devtools.verification.defects import defect_report

ROOT = Path(__file__).resolve().parents[1]


class BrowserAcceptance(unittest.TestCase):
    def test_personas_have_existing_tests_and_explicit_exploration_capabilities(self):
        config = load_configuration(ROOT)
        self.assertEqual(len(config['personas']), 5)
        for journey in config['journeys'].values():
            self.assertTrue(all((ROOT / 'frontend/e2e' / f).is_file() for f in journey['tests']))
        self.assertEqual(config['journeys']['settings-language']['adapter'], 'local-settings')
        self.assertEqual(config['journeys']['research-evidence']['adapter'], 'NOT_IMPLEMENTED')

    def test_docs_select_smoke_without_llm_and_unknown_ui_broadens_offline(self):
        low = browser_plan(ROOT, ['docs/readme.md'], [], 'feature')
        self.assertFalse(low['exploration']['required'])
        self.assertEqual(low['tests'], ['ci_smoke.spec.ts', 'uat_harness.spec.ts', 'ui_quality.spec.ts'])
        ui = browser_plan(ROOT, ['frontend/src/UnknownWidget.tsx'], [], 'feature')
        self.assertIn('navigation.spec.ts', ui['tests'])
        self.assertFalse(ui['calls_model'])

    def test_live_journeys_never_silently_join_offline_ci(self):
        contract = {'risk': 'CRITICAL', 'browser_acceptance': {'required': True,
                    'journeys': ['research-evidence', 'settings-language']}}
        plan = browser_plan(ROOT, ['frontend/src/App.tsx'], [contract], 'pr')
        self.assertNotIn('journeys.spec.ts', plan['tests'])
        self.assertTrue(plan['exploration']['required'])
        self.assertEqual(plan['journeys']['research-evidence'], 'NOT_IMPLEMENTED')
        self.assertEqual(plan['journeys']['settings-language'], 'NOT_RUN')

    def test_unknown_journey_and_unchanged_affected_contract_are_not_ignored(self):
        contract = {'id': 'existing', 'affected_modules': ['frontend/src/features/chat/**'],
                    'risk': 'HIGH', 'browser_acceptance': {'required': True, 'journeys': ['unknown-journey']}}
        selected = relevant_contracts(['frontend/src/features/chat/Composer.tsx'], [contract])
        self.assertEqual(selected, [contract])
        plan = browser_plan(ROOT, ['frontend/src/features/chat/Composer.tsx'], selected, 'feature')
        self.assertEqual(plan['journeys']['unknown-journey'], 'NOT_IMPLEMENTED')
        self.assertTrue(plan['errors'])

    def test_unreproduced_findings_remain_unconfirmed_with_compact_evidence(self):
        finding = {'title': 'Unexpected loading state', 'expected': 'Ready', 'actual': 'Loading',
                   'actions': ['open settings'], 'artifacts': ['final.png'], 'severity': 'HIGH'}
        report = defect_report([finding], 'source', 'REAL_LOCAL')
        self.assertEqual(report['defects'][0]['status'], 'UNCONFIRMED')
        self.assertEqual(report['unresolved'], 1)
        self.assertFalse(report['claims_fixed'])

    def test_fixed_requires_reproduction_and_matching_behavioral_regression(self):
        finding = {'title': 'Save failed', 'expected': 'Saved', 'actual': 'Pending', 'actions': ['save'],
                   'reproduction': {'status': 'REPRODUCED', 'artifact': 'repro.json'},
                   'regression': {'test': 'tests/test_save.py::Save.test_persist', 'before': 'FAIL',
                                  'after': 'PASS', 'source_sha256': 'new-source', 'artifact': 'regression.json'}}
        self.assertEqual(defect_report([finding], 'new-source', 'REAL_LOCAL')['defects'][0]['status'], 'UNCONFIRMED')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for field in ['reproduction', 'regression']:
                record = finding[field]
                raw = json.dumps({'fixture': True, **record}).encode()
                (root / record['artifact']).write_bytes(raw)
                record['sha256'] = hashlib.sha256(raw).hexdigest()
            report = defect_report([finding], 'new-source', 'MOCKED', root)
            self.assertEqual(report['defects'][0]['status'], 'FIXED')
            self.assertFalse(report['defects'][0]['production_fix'])
            finding['regression']['source_sha256'] = 'old-source'
            self.assertEqual(defect_report([finding], 'new-source', 'REAL_LOCAL', root)['defects'][0]['status'], 'CONFIRMED')




if __name__ == '__main__':
    unittest.main()
