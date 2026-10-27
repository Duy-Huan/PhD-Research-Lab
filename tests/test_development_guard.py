"""Actual isolated Git fixtures for dev-only mutation and source-bound push evidence."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import sys

from devtools.verification.branch_policy import LOCAL_STEPS, record_report, report_errors
from scripts.development_guard import remote_errors


class DevelopmentGuard(unittest.TestCase):
    def test_installed_reference_hook_rejects_new_development_branches(self):
        script=Path(__file__).resolve().parents[1]/'scripts/development_guard.py'
        with tempfile.TemporaryDirectory(prefix='phdlab-reference-policy-') as directory:
            root=Path(directory)
            def command(*args):
                return subprocess.run(['git',*args],cwd=root,capture_output=True,text=True)
            self.assertEqual(command('init','-q','--initial-branch=dev').returncode,0)
            setup=subprocess.run([sys.executable,str(script),'install','--root',str(root)],capture_output=True,text=True)
            self.assertEqual(setup.returncode,0,setup.stderr)
            initial=command('-c','user.name=Policy Fixture','-c','user.email=fixture@example.invalid',
                            'commit','--allow-empty','-m','Isolated actual Git fixture')
            self.assertEqual(initial.returncode,0,initial.stderr)
            before=command('rev-parse','HEAD').stdout.strip()
            for branch in ['feature/forbidden','fix/forbidden','backup/forbidden','arbitrary','qa','main']:
                with self.subTest(branch=branch):
                    result=command('branch',branch)
                    self.assertNotEqual(result.returncode,0,'Installed hook allowed new branch '+branch)
                    self.assertEqual(command('show-ref','--verify','refs/heads/'+branch).returncode,128)
            self.assertEqual(command('rev-parse','HEAD').stdout.strip(),before)
            self.assertEqual(command('branch','--show-current').stdout.strip(),'dev')

    def test_push_cannot_target_another_repository_or_remote(self):
        self.assertEqual(remote_errors('origin','https://github.com/Duy-Huan/PhD-Research-Lab.git'),[])
        self.assertEqual(remote_errors('origin','git@github.com:Duy-Huan/PhD-Research-Lab.git'),[])
        for name,url in [('origin','https://github.com/attacker/PhD-Research-Lab.git'),
                         ('other','https://github.com/Duy-Huan/PhD-Research-Lab.git'),
                         ('origin','https://github.com/Duy-Huan/PhD-Research-Lab/../other')]:
            self.assertTrue(remote_errors(name,url))

    def report(self):
        return {'decision':'PASS','profile':'pr','component':'all','source_stable':True,
                'source':{'sha256':'source'},'counts':{'PASS':7,'FAIL':0,'ERROR':0,'SKIP':0,'NOT_RUN':0},
                'steps':[{'id':name,'status':'PASS'} for name in LOCAL_STEPS]}

    def test_complete_source_bound_regression_is_required_for_push(self):
        self.assertEqual(report_errors(self.report(),'source'),[])
        for key,value in [('decision','FAIL'),('profile','quick'),('component','backend'),('source_stable',False)]:
            report=self.report();report[key]=value
            self.assertTrue(report_errors(report,'source'))
        self.assertTrue(report_errors(self.report(),'changed-source'))
        report=self.report();report['counts']['SKIP']=1
        self.assertTrue(report_errors(report,'source'))
        report=self.report();report['steps'].pop()
        self.assertTrue(report_errors(report,'source'))

    def test_latest_failure_replaces_a_previous_green_receipt(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-git-policy-') as directory:
            root=Path(directory)
            subprocess.run(['git','init','-q','--initial-branch=dev',str(root)],check=True,capture_output=True)
            file=root/'report.json';report=self.report();file.write_text(json.dumps(report))
            record_report(root,file,report)
            receipt=root/'.git/agent-verification/dev.json'
            self.assertEqual(json.loads(receipt.read_text())['decision'],'PASS')
            report['decision']='FAIL';file.write_text(json.dumps(report));record_report(root,file,report)
            stored=json.loads(receipt.read_text());self.assertEqual(stored['decision'],'FAIL')
            self.assertEqual(stored['sha256'],hashlib.sha256(file.read_bytes()).hexdigest())


class LiveEvidencePolicy(unittest.TestCase):
    def test_deferred_live_ids_require_real_complete_non_skipped_evidence(self):
        from devtools.verification.layers import live_ids, live_regression_errors
        data={'mode':'REAL_LOCAL','passed':True,'cases':[{'id':name,'status':'PASS'} for name in live_ids()]}
        self.assertEqual(live_regression_errors(data),[])
        for status in ['SKIP','FAIL','ERROR','NOT_RUN']:
            item=json.loads(json.dumps(data));item['cases'][0]['status']=status
            self.assertTrue(live_regression_errors(item))
        self.assertTrue(live_regression_errors(data | {'mode':'MOCKED'}))
        self.assertTrue(live_regression_errors(data | {'cases':data['cases'][1:]}))
