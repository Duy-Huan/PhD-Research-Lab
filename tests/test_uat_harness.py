"""Development AI-UAT policy tests; doubles never certify actual browser/model execution."""
from pathlib import Path
import tempfile
import unittest

from devtools.verification.uat import validate_target, run_space, exploration_required, bounded_options, exploratory_verdict


class UATPolicy(unittest.TestCase):
    def test_reject_non_loopback_or_credentialed_urls(self):
        for url in ['https://example.com','file:///C:/Windows/system.ini','http://127.0.0.1.evil:8765',
                    'http://user:pass@127.0.0.1:8765','http://192.168.1.1:8765','http://127.0.0.1:0','http://localhost']:
            with self.subTest(url=url),self.assertRaises(ValueError):validate_target(url)
        self.assertEqual(validate_target('http://127.0.0.1:8771/'),'http://127.0.0.1:8771')

    def test_profiles_are_unique_and_inside_disposable_root(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=run_space(root);b=run_space(root)
            self.assertNotEqual(a,b)
            self.assertTrue(a.is_relative_to(root.resolve()))
            self.assertNotEqual(a/'browser-profile',b/'browser-profile')

    def test_unavailable_adapter_never_passes(self):
        self.assertEqual(exploratory_verdict({'adapter_available':False}), 'BLOCKED')
        self.assertNotEqual(exploratory_verdict({}), 'PASS')

    def test_ai_success_is_unverified_until_reproduced(self):
        self.assertEqual(exploratory_verdict({'adapter_available':True,'ai_success':True,'steps':5}), 'UNVERIFIED')
        self.assertEqual(exploratory_verdict({'adapter_available':True,'ai_success':True,'steps':5,
            'deterministic_confirmation':'PASS','defects':[],'evidence_complete':True}), 'PASS')
        self.assertEqual(exploratory_verdict({'adapter_available':True,'ai_success':True,'steps':5,
            'deterministic_confirmation':'FAIL','defects':[{'status':'CONFIRMED'}],'evidence_complete':True}), 'FAIL')

    def test_risk_policy_preserves_optional_low_risk_exploration(self):
        self.assertFalse(exploration_required('LOW'))
        self.assertFalse(exploration_required('MEDIUM'))
        self.assertTrue(exploration_required('HIGH'))
        self.assertTrue(exploration_required('CRITICAL'))
        with self.assertRaises(ValueError):exploration_required('unknown')

    def test_bounds_steps_and_deadlines(self):
        self.assertEqual(bounded_options(6,120),{'max_steps':6,'timeout_s':120,'max_failures':3})
        for steps,deadline in [(0,120),(99,120),(3,0),(3,3600),(3.5,120),(3,2.5),('3',120),(True,120)]:
            with self.subTest(steps=steps,deadline=deadline),self.assertRaises(ValueError):bounded_options(steps,deadline)


if __name__=='__main__':unittest.main()
