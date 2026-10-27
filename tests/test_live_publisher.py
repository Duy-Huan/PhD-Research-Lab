"""MOCKED verification dependency, actual filesystem packaging boundary assertions."""
import hashlib
import json
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from scripts.publish_live_evidence import publish,collect_files,main,unpack_bundle
from devtools.verification.runner import identity


class LivePublisher(unittest.TestCase):
    def test_latest_failed_owner_dispatch_blocks_cached_success(self):
        from scripts.live_qualification import latest_owner_run
        run={'id':1,'workflow_id':5,'head_repository':{'full_name':'owner/repo'},
             'actor':{'login':'owner'},'event':'workflow_dispatch','head_sha':'head',
             'path':'.github/workflows/research-live.yml','status':'completed','conclusion':'success'}
        self.assertEqual(latest_owner_run([run],5,'owner/repo','head')['id'],1)
        for patch in [{'conclusion':'failure'},{'status':'in_progress','conclusion':None}]:
            with self.assertRaises(ValueError):latest_owner_run([run,run | {'id':2} | patch],5,'owner/repo','head')
        with self.assertRaises(ValueError):latest_owner_run([run | {'actor':{'login':'external'}}],5,'owner/repo','head')

    def test_archive_hash_paths_duplicates_and_existing_evidence_are_enforced(self):
        def archive(names):
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w') as stream:
                for name in names:stream.writestr(name,b'PACKAGING UNIT FIXTURE ONLY')
            return data.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'received';raw=archive(['manifest.json','raw/report.json'])
            with self.assertRaises(ValueError):unpack_bundle(raw,out,'0'*64)
            self.assertFalse(out.exists())
            for name in ['../escape','/absolute','C:/system','back\\slash','raw/../escape']:
                bad=archive(['manifest.json',name])
                # Windows ZipInfo normalizes backslashes during fixture creation;
                # patch both filename headers to reproduce actual untrusted bytes.
                if chr(92) in name:bad=bad.replace(b'back/slash',b'back'+bytes([92])+b'slash')
                with self.subTest(name=name),self.assertRaises(ValueError):unpack_bundle(bad,out,hashlib.sha256(bad).hexdigest())
                self.assertFalse(out.exists())
            duplicate=archive(['manifest.json','./manifest.json'])
            with self.assertRaises(ValueError):unpack_bundle(duplicate,out,hashlib.sha256(duplicate).hexdigest())
            unpack_bundle(raw,out,hashlib.sha256(raw).hexdigest())
            self.assertEqual((out/'raw/report.json').read_bytes(),b'PACKAGING UNIT FIXTURE ONLY')
            with self.assertRaises(ValueError):unpack_bundle(raw,out,hashlib.sha256(raw).hexdigest())

    def fixture(self,root):
        subprocess.run(['git','init','-q','--initial-branch=dev',str(root)],check=True,capture_output=True)
        subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                        'commit','--allow-empty','-m','Private packaging fixture'],cwd=root,check=True,capture_output=True)
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        source=identity(root)['sha256'];evidence=root/'raw';folder=evidence/head;folder.mkdir(parents=True)
        raw=b'UNIT fixture only; no model or scientific execution\n';digest=hashlib.sha256(raw).hexdigest()
        (folder/'result.json').write_bytes(raw)
        manifest={'mode':'MOCKED_PACKAGING_FIXTURE','layers':{'fixture':{'artifacts':[{'path':'result.json','sha256':digest}]}},
                  'live_regression':{'path':'result.json','sha256':digest}}
        (folder/'manifest.json').write_text(json.dumps(manifest))
        return head,source,evidence,folder

    def test_no_owner_dispatch_means_no_execution_or_publishing(self):
        with (patch.dict(os.environ,{'GITHUB_EVENT_NAME':'pull_request','GITHUB_ACTOR':'external'},clear=True),
             patch('sys.argv',['publish_live_evidence.py','--out','output/playwright/fixture']),
             patch('scripts.publish_live_evidence.publish') as operation):
            self.assertEqual(main(),2);operation.assert_not_called()

    def test_copy_only_declared_bytes_and_preserve_existing_output(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-publish-fixture-') as directory:
            root=Path(directory);head,source,evidence,folder=self.fixture(root)
            (folder/'private-unlisted.txt').write_text('must not be published')
            with patch('scripts.publish_live_evidence.validate_live',return_value=[]),patch('scripts.publish_live_evidence.uat_files',return_value={}):
                result=publish(root,evidence,root/'output',head,source)
                self.assertFalse(result['model_invoked']);self.assertEqual(result['files'],2)
                self.assertEqual((root/'output/result.json').read_bytes(),(folder/'result.json').read_bytes())
                self.assertFalse((root/'output/private-unlisted.txt').exists())
                with self.assertRaises(ValueError):publish(root,evidence,root/'output',head,source)

    def test_failed_qualification_or_changed_artifact_cannot_write_output(self):
        with tempfile.TemporaryDirectory(prefix='phdlab-publish-fixture-') as directory:
            root=Path(directory);head,source,evidence,folder=self.fixture(root)
            with patch('scripts.publish_live_evidence.validate_live',return_value=['No real provider execution']):
                with self.assertRaises(ValueError):publish(root,evidence,root/'output',head,source)
                self.assertFalse((root/'output').exists())
            (folder/'result.json').write_text('changed bytes')
            with patch('scripts.publish_live_evidence.validate_live',return_value=[]),patch('scripts.publish_live_evidence.uat_files',return_value={}):
                with self.assertRaises(ValueError):publish(root,evidence,root/'output',head,source)
                self.assertFalse((root/'output').exists())

    def test_conflicting_artifact_digests_fail_closed(self):
        with self.assertRaises(ValueError):collect_files({'layers':{'one':{'artifacts':[{'path':'a','sha256':'1'}]},
            'two':{'artifacts':[{'path':'a','sha256':'2'}]}},'live_regression':{'path':'a','sha256':'1'}})

