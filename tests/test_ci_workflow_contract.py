"""CI/CD safety contracts, not proof that any remote workflow has passed."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class WorkflowContract(unittest.TestCase):
    def load(self, name):
        return yaml.safe_load((ROOT/'.github/workflows'/name).read_text(encoding='utf-8'))

    def test_policy_dependencies_precede_targeted_worker_execution(self):
        steps=self.load('quality.yml')['jobs']['policy']['steps']
        installs=[i for i,s in enumerate(steps) if 'pip install --require-hashes -r requirements-ci.lock' in s.get('run','')]
        workers=[i for i,s in enumerate(steps) if 'devtools.verification.unittest_worker' in s.get('run','')]
        self.assertEqual(len(installs),1)
        self.assertTrue(workers,'Critical tests must execute through the existing bounded worker')
        self.assertTrue(all(installs[0]<i for i in workers))
        self.assertFalse(any('unittest discover' in s.get('run','') for s in steps),
                         'Discovery imports unrelated package initializers despite filename patterns')

    def test_pr_quality_has_no_release_or_production_approval(self):
        workflow=self.load('quality.yml');triggers=workflow.get('on',workflow.get(True))
        self.assertIn('pull_request',triggers)
        self.assertEqual(triggers['push']['branches'],['dev'])
        self.assertEqual(triggers['pull_request']['branches'],['qa','main'])
        self.assertNotIn('workflow_dispatch',triggers,'Diagnostic dispatch must not overwrite required PR status contexts')
        self.assertNotIn('release-gate',workflow['jobs'])
        self.assertNotIn('release-approval',workflow['jobs'])
        self.assertEqual(workflow['jobs']['development-gate']['if'],'always()')

    def test_dev_push_cannot_emit_a_skipped_required_qa_context(self):
        job=self.load('quality.yml')['jobs']['qa-gate']
        self.assertEqual(job['name'], "${{ github.event_name == 'pull_request' && 'QA gate' || 'QA not requested on dev push' }}")

    def test_all_promotion_stages_require_software_regression_without_live_credits(self):
        from scripts.quality_gate import REQUIRED
        self.assertEqual(REQUIRED['qa'],['development-gate'])
        workflow=self.load('quality.yml')
        self.assertEqual(workflow['jobs']['qa-gate']['needs'],['development-gate'])
        self.assertEqual(set(workflow['jobs']['development-gate']['needs']),{'policy','backend','frontend','security','browser','installers'})
        optional={'Matching-source live research qualification','Risk-triggered verified AI-UAT evidence'}
        import json
        required=json.loads((ROOT/'.github/required-ci-jobs.json').read_text('utf-8'))['qa']
        self.assertFalse(optional & set(required))
        self.assertTrue({'Development gate','QA gate'} <= set(required))

    def test_release_runs_only_for_main_and_uses_exact_provenance(self):
        workflow=self.load('release.yml');triggers=workflow.get('on',workflow.get(True))
        self.assertEqual(triggers['push']['branches'],['main'])
        self.assertNotIn('pull_request',triggers)
        script=workflow['jobs']['release-gate']['steps'][0]['with']['script']
        source=(ROOT/'.github/scripts/release_provenance.cjs').read_text(encoding='utf-8').split('module.exports')[0].strip()
        self.assertIn(source,script,'Inline privileged source must match its separately tested implementation')
        self.assertEqual(workflow['jobs']['publish']['permissions']['contents'],'write')
        self.assertNotIn('write-all',str(workflow))

    def test_legacy_workflows_are_replaced_and_3d_is_not_left_diff_optional(self):
        for name in ['backend-quality-gate.yml','full-harness-regression.yml']:
            self.assertFalse((ROOT/'.github/workflows'/name).exists())
        runs=[s.get('run','') for s in self.load('quality.yml')['jobs']['browser']['steps']]
        self.assertTrue(any('devtools.verification.browser' in command and '--offline-all' in command for command in runs))


if __name__=='__main__':unittest.main()
