"""Comparison fixtures cannot certify a branch or turn missing tests into success."""
import unittest
from devtools.verification.comparison import compare


class Comparison(unittest.TestCase):
    def test_offline_all_covers_actual_3d_without_scheduling_model_journeys(self):
        from pathlib import Path
        from devtools.verification.journeys import browser_plan
        root=Path(__file__).resolve().parents[1]
        plan=browser_plan(root,[],[],'pr',all_offline=True)
        self.assertIn('office3d.spec.ts',plan['tests'])
        self.assertNotIn('multi_turn_chat.spec.ts',plan['tests'])
        self.assertNotIn('workflows.spec.ts',plan['tests'])
        self.assertFalse(plan['calls_model'])

    def fixture(self):
        return {'manifest':{'suite_sha256':'suite','environment_sha256':'env','policy_sha256':'policy'},
                'cases':[{'id':'critical','status':'PASS'}],'coverage':{'lines':{'covered':80,'total':100}},
                'source':{'sha':'a'*40,'stable':True}}

    def test_different_suite_environment_or_policy_is_incomparable(self):
        for key in self.fixture()['manifest']:
            left,right=self.fixture(),self.fixture();right['manifest'][key]='different'
            with self.assertRaises(ValueError):compare(left,right,[])

    def test_unstable_source_cannot_be_ranked_by_passing_cases(self):
        left,right=self.fixture(),self.fixture();left['source']['stable']=False
        with self.assertRaises(ValueError):compare(left,right,[])

    def test_fixed_critical_denominator_never_counts_missing_or_skipped_as_pass(self):
        left,right=self.fixture(),self.fixture();right['cases'].append({'id':'second','status':'SKIP'})
        critical=[{'id':name,'case_ids':[name]} for name in ['critical','second']]
        result=compare(left,right,critical)
        for side in ['main','candidate']:
            self.assertEqual(result[side]['critical_pass_rate'],{'passed':1,'required':2,'percent':50.0})
        self.assertEqual(result['main']['coverage']['lines']['total'],100)

    def test_later_duplicate_pass_cannot_erase_a_failure(self):
        left,right=self.fixture(),self.fixture()
        left['cases']=[{'id':'critical','status':'FAIL'},{'id':'critical','status':'PASS'}]
        result=compare(left,right,[{'id':'workflow','case_ids':['critical']}])
        self.assertEqual(result['main']['critical_software_checks'][0]['status'],'FAIL')
        self.assertEqual(result['main']['known_confirmed_unresolved_defects']['P1'],0)
        self.assertFalse(result['main']['defect_inventory_complete'])


if __name__=='__main__':unittest.main()
