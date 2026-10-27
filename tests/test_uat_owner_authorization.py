"""Private fixtures only: never authorize or invoke the real fourth UAT execution."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from devtools.verification.uat_authorization import authorization_dir,consume,finish,TASK
from devtools.verification.uat import bounded_options


class OwnerSingleRetry(unittest.TestCase):
    def fixture(self,root):
        subprocess.run(['git','init','-q','--initial-branch=dev',str(root)],check=True,capture_output=True)
        folder=authorization_dir(root);folder.mkdir(parents=True)
        ledger=root/'agent/repair-ledgers/ledger.json';ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({TASK:{'attempts':3,'history':[{'status':'FAIL','sha':str(n)} for n in range(3)]}}))
        grant={'owner':'Duy-Huan','task_key':TASK,'allowed_runs':1,'used':False,
               'authorization':'OWNER_CHAT_2026_10_25_SINGLE_BOUNDED_UAT','source_sha256':'source','head_sha':'head',
               'model':'spark-x2.5-4b','max_steps':6,'deadline_s':600,
               'expires_utc':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
        path=folder/'fixture-owner-grant.json';path.write_text(json.dumps(grant));return ledger,path,grant

    def test_single_consumption_preserves_original_three_failures_and_blocks_new_file_replay(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-uat-grant-') as directory:
            root=Path(directory);ledger,path,grant=self.fixture(root);original=ledger.read_bytes()
            receipt=consume(root,path,'source','head','spark-x2.5-4b',6,600)
            self.assertEqual(receipt['status'],'RESERVED');self.assertEqual(ledger.read_bytes(),original)
            self.assertTrue(json.loads(path.read_text())['used'])
            with self.assertRaises(ValueError):consume(root,path,'source','head','spark-x2.5-4b',6,600)
            alternate=path.with_name('cannot-reset-with-a-new-key.json');alternate.write_text(json.dumps(grant))
            with self.assertRaises(ValueError):consume(root,alternate,'source','head','spark-x2.5-4b',6,600)
            finish(root,'BLOCKED');self.assertEqual(ledger.read_bytes(),original)
            with self.assertRaises(ValueError):finish(root,'PASS')

    def test_wrong_scope_budget_model_or_expired_permission_never_consumes(self):
        for change in [{'source_sha256':'other'},{'head_sha':'other'},{'model':'paid-cloud'},
                       {'owner':'external'},{'used':True},{'max_steps':8},
                       {'expires_utc':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}]:
            with self.subTest(change=change),tempfile.TemporaryDirectory(prefix='phdlab-uat-grant-') as directory:
                root=Path(directory);ledger,path,grant=self.fixture(root)
                path.write_text(json.dumps(grant | change));original=ledger.read_bytes()
                with self.assertRaises(ValueError):consume(root,path,'source','head','spark-x2.5-4b',6,600)
                self.assertEqual(ledger.read_bytes(),original)
                self.assertFalse((authorization_dir(root)/(TASK+'-single-execution.json')).exists())

    def test_repository_or_pr_content_cannot_become_owner_authorization(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-uat-grant-') as directory:
            root=Path(directory);ledger,path,grant=self.fixture(root)
            untrusted=root/'pr-grant.json';untrusted.write_text(json.dumps(grant))
            with self.assertRaises(ValueError):consume(root,untrusted,'source','head','spark-x2.5-4b',6,600)

    def test_default_deadline_and_failure_limit_remain_strict(self):
        with self.assertRaises(ValueError):bounded_options(6,600)
        self.assertEqual(bounded_options(6,600,owner_limit=True),{'max_steps':6,'timeout_s':600,'max_failures':3})
        for steps,deadline in [(7,600),(6,601),(True,600),(6,True)]:
            with self.assertRaises(ValueError):bounded_options(steps,deadline,owner_limit=True)

