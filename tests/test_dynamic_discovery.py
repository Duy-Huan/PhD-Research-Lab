"""New software test files are selected without editing a hand-maintained list."""
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

from devtools.verification.journeys import browser_plan
from devtools.verification.selection import select

ROOT=Path(__file__).resolve().parents[1]


class DynamicDiscovery(unittest.TestCase):
    def test_empty_test_module_cannot_hide_behind_another_passing_module(self):
        from devtools.verification.layers import load_modules
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'phdlab_fixture_collected.py').write_text('import unittest\nEVENTS=[]\nclass Cases(unittest.TestCase):\n def test_actual_case(self): EVENTS.append("executed"); self.assertEqual(2+2,4)\n')
            (root/'phdlab_fixture_uncollected.py').write_text('def test_pytest_only():\n raise AssertionError("unittest would silently miss this")\n')
            try:
                with patch.object(sys,'path',[str(root),*sys.path]):
                    suite=load_modules(unittest.TestLoader(),['phdlab_fixture_collected','phdlab_fixture_uncollected'])
                    result=unittest.TestResult();suite.run(result)
                    self.assertFalse(result.wasSuccessful())
                    self.assertEqual(result.testsRun,2)
                    self.assertEqual(len(result.failures),1)
                    self.assertIn('phdlab_fixture_uncollected',result.failures[0][0].id())
                    self.assertEqual(sys.modules['phdlab_fixture_collected'].EVENTS,['executed'])
            finally:
                sys.modules.pop('phdlab_fixture_collected',None);sys.modules.pop('phdlab_fixture_uncollected',None)

    def fixture(self,root):
        config=json.loads((ROOT/'devtools/verification/uat_config.json').read_text(encoding='utf-8'))
        p=root/'devtools/verification/uat_config.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(config))
        for name in set(config['smoke']) | {f for record in config['journeys'].values() for f in record['tests']}:
            p=root/'frontend/e2e'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('// isolated selection fixture\n')

    def test_new_e2e_is_automatically_included_without_enabling_live_suites(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root)
            p=root/'frontend/e2e/new_feature.spec.ts';p.write_text('// no model\n')
            plan=browser_plan(root,[],[],'pr',all_offline=True)
            self.assertIn('new_feature.spec.ts',plan['tests'])
            self.assertNotIn('harness_ide.spec.ts',plan['tests'])
            self.assertEqual(plan['errors'],[])
            self.assertEqual(plan['status'],'NOT_RUN')
            self.assertFalse(plan['calls_model'])
            self.assertIn('harness_ide.spec.ts',browser_plan(root,[],[],'full')['tests'])

    def test_new_nested_backend_package_is_discovered_and_missing_init_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'tests/new_feature';p.mkdir(parents=True)
            (p/'test_behavior.py').write_text('import unittest\n')
            result=select(root,[],'pr')
            self.assertEqual(result['blocked_tests'],['tests/new_feature/test_behavior.py'])
            (p/'__init__.py').write_text('')
            result=select(root,[],'pr')
            self.assertEqual(result['backend_tests'],['new_feature.test_behavior'])
            self.assertEqual(result['blocked_tests'],[])

    def test_2d_and_3d_are_executed_as_separate_ordered_groups(self):
        from devtools.verification.journeys import execution_groups
        self.assertEqual(execution_groups(['office3d.spec.ts','navigation.spec.ts','new.3d.spec.ts','chat.spec.ts']),
                         [('2d',['navigation.spec.ts','chat.spec.ts']),('3d',['office3d.spec.ts','new.3d.spec.ts'])])
        self.assertEqual(execution_groups([]),[])

    def test_full_app_screen_audit_runs_in_its_own_2d_group(self):
        # FQC-UI-QA-663: the 181-screen audit alone fills most of one invocation's 600 s budget in CI, so it gets its
        # own invocation (same per-invocation timeout), still before 3D.
        from devtools.verification.journeys import execution_groups
        self.assertEqual(execution_groups(['office3d.spec.ts','qa_screens.spec.ts','navigation.spec.ts']),
                         [('2d',['navigation.spec.ts']),('2d-audit',['qa_screens.spec.ts']),('3d',['office3d.spec.ts'])])
        self.assertEqual(execution_groups(['qa_screens.spec.ts']),[('2d-audit',['qa_screens.spec.ts'])])

