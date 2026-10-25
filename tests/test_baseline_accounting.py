"""A known issue is accounting, never permission to bypass a mandatory failure."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


class BaselineAccounting(unittest.TestCase):
    def test_baseline_policy_changes_invalidate_source_evidence(self):
        import subprocess
        from devtools.verification.runner import identity
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(['git', 'init', '-q', str(root)], check=True, capture_output=True)
            path = root/'docs/qa/KNOWN_ISSUES_BASELINE.json'
            path.parent.mkdir(parents=True)
            path.write_text('{"exceptions":[]}', encoding='utf-8')
            before = identity(root)['sha256']
            path.write_text('{"exceptions":["unauthorized"]}', encoding='utf-8')
            self.assertNotEqual(before, identity(root)['sha256'])

    def fixture(self, root):
        raw = b'{"decision":"FAIL"}\n'
        (root/'proof.json').write_bytes(raw)
        return {'schema_version': 1, 'baseline_sha': 'a'*40, 'exceptions': [],
                'issues': [{'id': 'CI-001', 'severity': 'P2', 'classification': 'CI_INFRASTRUCTURE',
                            'status': 'OPEN', 'owner': 'Maintainer', 'remediation': 'Fix reporting',
                            'evidence': [{'path': 'proof.json', 'sha256': hashlib.sha256(raw).hexdigest()}]}]}

    def validate(self, data, root):
        from devtools.verification.baseline import validate_baseline
        path = root/'baseline.json'; path.write_text(json.dumps(data), encoding='utf-8')
        return validate_baseline(path, root)

    def test_verified_open_issue_is_accounted_without_becoming_a_waiver(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); data = self.fixture(root)
            self.assertEqual(self.validate(data, root), [])
            self.assertEqual(data['issues'][0]['status'], 'OPEN')

    def test_claimed_approval_cannot_authorize_any_exception(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); data = self.fixture(root)
            for value in [[{'test_id': 'test.exact', 'approved': True}], ['*'], None, {}]:
                with self.subTest(value=value):
                    data['exceptions'] = value
                    self.assertTrue(self.validate(data, root))

    def test_changed_missing_or_escaping_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); data = self.fixture(root)
            (root/'proof.json').write_text('changed', encoding='utf-8')
            self.assertTrue(self.validate(data, root))
            for path in ['absent.json', '../proof.json']:
                data['issues'][0]['evidence'][0]['path'] = path
                self.assertTrue(self.validate(data, root))

    def test_malformed_duplicate_and_unowned_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); data = self.fixture(root)
            data['baseline_sha'] = 'main'
            self.assertTrue(self.validate(data, root))
            data['baseline_sha'] = 'a'*40
            data['issues'].append(data['issues'][0].copy())
            self.assertTrue(self.validate(data, root))
            data['issues'] = [data['issues'][0]]; data['issues'][0]['owner'] = ''
            self.assertTrue(self.validate(data, root))


if __name__ == '__main__': unittest.main()
