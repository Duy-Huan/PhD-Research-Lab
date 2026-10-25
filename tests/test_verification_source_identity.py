"""Evidence identity binds actual runtime inputs independently of Git staging state."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from devtools.verification.runner import identity


class SourceIdentity(unittest.TestCase):
    def make_repo(self, root):
        subprocess.run(['git','init','-q',str(root)],check=True,capture_output=True)
        for name in ['backend/app.py','frontend/react.html','frontend/public/icon.svg','cli.py']:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'original\n')
        subprocess.run(['git','add','--','.'],cwd=root,check=True,capture_output=True)

    def test_html_public_assets_and_cli_changes_invalidate_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.make_repo(root)
            for name in ['frontend/react.html','frontend/public/icon.svg','cli.py']:
                before=identity(root)['sha256']
                (root/name).write_bytes(b'changed\n')
                with self.subTest(path=name):self.assertNotEqual(before,identity(root)['sha256'])

    def test_staging_a_real_deletion_does_not_change_worktree_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.make_repo(root)
            initial=identity(root)['sha256'];(root/'backend/app.py').unlink()
            deleted=identity(root)['sha256'];self.assertNotEqual(initial,deleted)
            subprocess.run(['git','add','-u'],cwd=root,check=True,capture_output=True)
            self.assertEqual(deleted,identity(root)['sha256'])

    def test_build_outputs_are_not_source_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.make_repo(root);before=identity(root)['sha256']
            for name in ['frontend/dist/react.html','frontend/node_modules/mock/index.js','frontend/coverage/result.json',
                         'output/generated.py','artifacts/experiment.py','docs/qa/evidence/replay.py']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'generated')
            self.assertEqual(before,identity(root)['sha256'])

    def test_new_agent_policies_invalidate_evidence_but_operational_records_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.make_repo(root)
            policy=root/'agent/future-capability-policy.md'
            policy.parent.mkdir(parents=True);policy.write_text('Require independent evidence\n',encoding='utf-8')
            initial=identity(root)['sha256']
            self.assertIn('agent/future-capability-policy.md',identity(root)['files'])
            policy.write_text('Require independent evidence and rollback\n',encoding='utf-8')
            changed=identity(root)['sha256'];self.assertNotEqual(initial,changed)
            for name in ['agent/STATE.md','agent/PLAN.md','agent/history/prior-policy.md',
                         'agent/repair-ledgers/ledger.json']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('Operational progress, not execution policy\n',encoding='utf-8')
            self.assertEqual(changed,identity(root)['sha256'])
            subprocess.run(['git','add','--','.'],cwd=root,check=True,capture_output=True)
            self.assertEqual(changed,identity(root)['sha256'])

    def test_declared_upstream_license_line_endings_do_not_change_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.make_repo(root)
            path=root/'skills/reference/DECLARED_SOURCE_APACHE_LICENSE'
            path.parent.mkdir(parents=True);path.write_bytes(b'License terms\nRetain attribution\n')
            original=identity(root)['sha256']
            path.write_bytes(b'License terms\r\nRetain attribution\r\n')
            self.assertEqual(original,identity(root)['sha256'])
            subprocess.run(['git','add','--','.'],cwd=root,check=True,capture_output=True)
            self.assertEqual(original,identity(root)['sha256'])
            path.write_bytes(b'Changed license terms\nRetain attribution\n')
            self.assertNotEqual(original,identity(root)['sha256'])


if __name__=='__main__':unittest.main()
