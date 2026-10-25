"""Root-cause grouping must retain the cause even when each test wraps it."""
import unittest
from pathlib import Path
import tempfile
from devtools.verification.evidence import fingerprints
from devtools.verification.selection import select


class FailureReporting(unittest.TestCase):
    def test_nested_test_packages_are_included_in_broad_and_incremental_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,text in {'backend/a.py':'VALUE=1','tests/nested/__init__.py':'',
                              'tests/nested/test_a.py':'from backend.a import VALUE'}.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
            self.assertEqual(select(root,['backend/api/chat.py'],'feature')['backend_tests'],['nested.test_a'])
            self.assertEqual(select(root,['backend/a.py'],'quick')['backend_tests'],['nested.test_a'])

    def test_live_opt_in_inventory_stays_separate_and_unknown_tests_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ['tests/test_unit.py','tests/live_e2e/test_inference.py','tests/unclassified/test_unknown.py']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('',encoding='utf-8')
            result=select(root,['backend/api/chat.py'],'feature')
            self.assertEqual(result['backend_tests'],['test_unit'])
            self.assertEqual(result['separate_live_tests'],['tests/live_e2e/test_inference.py'])
            self.assertEqual(result['blocked_tests'],['tests/unclassified/test_unknown.py'])

    def test_wrapped_database_failures_group_by_original_exception(self):
        cases=[{'id':f'case-{i}','status':'ERROR','details':
                f'ConnectionRefusedError: database connection refused\n\nThe above exception was the direct cause of the following exception:\nRuntimeError: session-{i} could not start'}
               for i in range(50)]
        groups=fingerprints(cases)
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['count'],50)
        self.assertEqual(groups[0]['classification'],'ENVIRONMENT_OR_DEPENDENCY')

    def test_skip_volume_does_not_hide_an_actual_failure(self):
        cases=[{'id':f'skip-{i}','status':'SKIP','details':'Optional SDK unavailable'} for i in range(100)]
        cases.append({'id':'error','status':'ERROR','details':'AssertionError: state was lost'})
        groups=fingerprints(cases)
        self.assertIn('AssertionError',groups[0]['cause'])


if __name__=='__main__':unittest.main()
