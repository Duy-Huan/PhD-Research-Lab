"""Behavioral contracts for development verification; no research/LLM dependency."""
import json
from pathlib import Path
import tempfile
import unittest

from devtools.verification.contracts import validate_contract, validate_promotion
from devtools.verification.evidence import fingerprints, RepairBudget, aggregate
from devtools.verification.selection import select


class Selection(unittest.TestCase):
    def test_transitive_python_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, code in {'backend/a.py': 'VALUE = 1', 'backend/b.py': 'from backend import a',
                               'tests/test_b.py': 'from backend.b import VALUE',
                               'tests/test_other.py': 'import unittest'}.items():
                p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(code)
            result = select(root, ['backend/a.py'], 'quick')
            self.assertEqual(result['backend_tests'], ['test_b'])
            self.assertFalse(result['frontend'])

    def test_unknown_or_deleted_dependency_broadens(self):
        for path in ['requirements.txt', 'backend/deleted.py', 'new_source.rs']:
            with self.subTest(path=path), tempfile.TemporaryDirectory() as d:
                root = Path(d); (root/'tests').mkdir(); (root/'tests/test_x.py').write_text('')
                result = select(root, [path], 'quick')
                self.assertEqual(result['backend_tests'], ['test_x'])
                self.assertTrue(result['frontend'])

    def test_shared_api_and_risk_force_broad_scope(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'tests').mkdir(); (root/'tests/test_x.py').write_text('')
            for name in ['backend/api/chat.py', 'backend/agent/context.py', '.github/workflows/ci.yml']:
                with self.subTest(name=name):
                    result = select(root, [name], 'feature')
                    self.assertEqual(result['backend_tests'], ['test_x'])
                    self.assertTrue(result['frontend'])
                    self.assertEqual(result['risk'], 'CRITICAL')

    def test_frontend_changes_select_frontend_without_python(self):
        with tempfile.TemporaryDirectory() as d:
            result = select(Path(d), ['frontend/src/features/chat/X.tsx'], 'quick')
            self.assertTrue(result['frontend'])
            self.assertEqual(result['backend_tests'], [])

    def test_pr_and_full_never_use_incremental_selection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'tests').mkdir(); (root/'tests/test_all.py').write_text('')
            for profile in ['pr', 'full']:
                result=select(root, ['docs/README.md'], profile)
                self.assertTrue(result['frontend'])
                self.assertEqual(result['backend_tests'], ['test_all'])

    def test_unmapped_python_source_never_produces_empty_suite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'backend').mkdir(); (root/'backend/new.py').write_text('X=1')
            (root/'tests').mkdir(); (root/'tests/test_all.py').write_text('')
            self.assertEqual(select(root,['backend/new.py'],'quick')['backend_tests'], ['test_all'])


class Evidence(unittest.TestCase):
    def test_fifty_database_errors_have_one_fingerprint(self):
        cases=[{'id': f'test_{i}', 'status':'ERROR', 'details':
                f'File "/tmp/run-{i}/test_db.py", line {i+1}\nConnectionRefusedError: [Errno 111] Connection refused'} for i in range(50)]
        groups=fingerprints(cases)
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['count'],50)
        self.assertEqual(len(groups[0]['case_ids']),50)

    def test_distinct_assertion_causes_remain_distinct(self):
        groups=fingerprints([{'id':'a','status':'FAIL','details':'AssertionError: 1 != 2'},
                             {'id':'b','status':'FAIL','details':'AssertionError: 1 != 3'}])
        self.assertEqual(len(groups),2)

    def test_missing_skipped_failed_and_cancelled_never_pass(self):
        for state in ['MISSING','SKIP','NOT_RUN','CANCELLED','BLOCKED','FAIL']:
            with self.subTest(state=state):
                self.assertNotEqual(aggregate({'unit':'PASS','build':state},['unit','build']), 'PASS')
        self.assertNotEqual(aggregate({'unit':'PASS'},['unit','build']),'PASS')
        self.assertEqual(aggregate({'unit':'PASS','build':'PASS'},['unit','build']),'PASS')

    def test_repair_budget_is_persistent_and_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'budget.json'
            for count in [1,2,3]:
                state=RepairBudget(p,'PR-7').record_failure('head-'+str(count))
                self.assertEqual(state['attempts'],count)
            self.assertFalse(RepairBudget(p,'PR-7').can_repair())
            with self.assertRaises(RuntimeError): RepairBudget(p,'PR-7').record_failure('another-head')
            self.assertTrue(RepairBudget(p,'PR-8').can_repair())

    def test_success_does_not_reset_prior_failed_repair_cycles(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json'; b=RepairBudget(p,'task')
            b.record_failure('sha1'); b.record_success('sha2')
            self.assertEqual(RepairBudget(p,'task').attempts,1)

    def test_corrupt_repair_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json'; p.write_text('{broken')
            with self.assertRaises(ValueError): RepairBudget(p,'task').can_repair()


class Contracts(unittest.TestCase):
    def valid(self):
        return {'id':'FQC-TEST','title':'Verification','risk':'HIGH','mode':'MOCKED',
                'user_story':'As an owner I need truthful gates',
                'requirements':[{'id':'REQ-1','description':'Block missing checks'}],
                'nonfunctional':['Bound logs'],'inputs':['check results'],'outputs':['report.json'],
                'preconditions':['Git repository'],'postconditions':['No missing check passes'],
                'dependencies':['Python'],'affected_modules':['devtools/**'],
                'acceptance_criteria':['Missing gate blocks merge'],
                'scenarios':[{'id':kind,'requirement':'REQ-1','kind':kind,'expected':'Blocked or validated',
                              'test':'tests/test_verification_harness.py::Evidence.test_missing_skipped_failed_and_cancelled_never_pass'}
                             for kind in ['positive','negative','boundary','failure','security','performance']],
                'recovery':'Preserve evidence and stop after three failures',
                'test_environment':'Disposable temporary directories',
                'skill_sources':['skills/SOURCES.json'], 'review':{'status':'REVIEWED','method':'same-agent review, not independent'}}

    def test_valid_contract_has_executable_traceability(self):
        self.assertEqual(validate_contract(self.valid(),Path(__file__).resolve().parents[1]),[])

    def test_missing_requirements_traceability_and_security_block(self):
        for mutate in [lambda c:c.pop('inputs'), lambda c:c['scenarios'][0].update(requirement='UNKNOWN'),
                       lambda c:c['scenarios'][0].update(test='tests/missing.py::absent'),
                       lambda c:c.update(scenarios=[s for s in c['scenarios'] if s['kind']!='security'])]:
            with self.subTest(mutate=mutate):
                c=self.valid(); mutate(c)
                self.assertTrue(validate_contract(c,Path(__file__).resolve().parents[1]))

    def test_invalid_risk_and_unreviewed_contract_block(self):
        for key,value in [('risk','tiny'),('review',{'status':'DRAFT'}),('mode','LIVE_BUT_MOCKED')]:
            c=self.valid(); c[key]=value
            self.assertTrue(validate_contract(c,Path(__file__).resolve().parents[1]))

    def test_malformed_contract_fields_return_errors_without_crashing(self):
        for field,value in [('requirements',17),('requirements',[17]),('scenarios',17),('risk',[]),('mode',[])]:
            with self.subTest(field=field,value=value):
                c=self.valid(); c[field]=value
                self.assertTrue(validate_contract(c,Path(__file__).resolve().parents[1]))

    def test_branch_promotion_direction_and_human_release(self):
        self.assertTrue(validate_promotion('feature/test','dev',False))
        self.assertEqual(validate_promotion('dev','qa',False),[])
        self.assertTrue(validate_promotion('feature/test','main',True))
        self.assertTrue(validate_promotion('qa','main',False))
        self.assertEqual(validate_promotion('qa','main',True),[])
        self.assertTrue(validate_promotion('qa','dev',False))


if __name__ == '__main__': unittest.main()
