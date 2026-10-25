"""Actual isolated Git fixtures for dev-only mutation and source-bound push evidence."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

from devtools.verification.branch_policy import LOCAL_STEPS, record_report, report_errors
from scripts.install_ci_sdk import unpack
from scripts.development_guard import remote_errors


class DevelopmentGuard(unittest.TestCase):
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


class PinnedSDK(unittest.TestCase):
    def archive(self, names):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w:gz') as archive:
            for name in names:
                content=b'# synthetic bounded test input\n';item=tarfile.TarInfo(name);item.size=len(content)
                archive.addfile(item,io.BytesIO(content))
        return stream.getvalue()

    def test_wrong_digest_and_escaping_archive_never_write_files(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'sdk'
            with self.assertRaises(ValueError):unpack(b'not trusted',out)
            raw=self.archive(['../../escape.py'])
            with self.assertRaises(ValueError):unpack(raw,out,hashlib.sha256(raw).hexdigest(),'fixture/')
            self.assertFalse(out.exists())

    def test_reviewed_inventory_is_exact_and_unknown_output_is_preserved(self):
        raw=self.archive(['fixture/__init__.py','fixture/client.py'])
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'sdk'
            result=unpack(raw,out,hashlib.sha256(raw).hexdigest(),'fixture/')
            self.assertEqual(set(result['files']),{'openscience/__init__.py','openscience/client.py'})
            with self.assertRaises(ValueError):unpack(raw,out,hashlib.sha256(raw).hexdigest(),'fixture/')
            self.assertTrue((out/'openscience/client.py').is_file())


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
