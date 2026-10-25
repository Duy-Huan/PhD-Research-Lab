import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from scripts.package_release import package


class ReleasePackaging(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='phdlab-release-fixture-'); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name, content in {'frontend/package.json':'{"version":"1.2.3"}',
                              'backend/core/config.py':'APP_VERSION = "1.2.3"', 'start.py':'APP_VERSION = "1.2.3"',
                              'data/private.txt':'SYNTHETIC_PRIVATE_MARKER', '.env':'SYNTHETIC_TOKEN',
                              'agent/AGENT.md':'Synthetic fixture instructions', 'skills/fixture/SKILL.md':'Fixture'}.items():
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content, encoding='utf-8')
        self.git('init', '-q'); self.git('add', '.')
        self.git('-c', 'user.name=QA', '-c', 'user.email=qa@example.invalid', 'commit', '-qm', 'synthetic release fixture')
        self.sha = self.git('rev-parse', 'HEAD').strip()
        p = self.root / 'frontend/dist/index.html'; p.parent.mkdir(); p.write_text('<script src="new.js"></script>', encoding='utf-8')
        (p.parent / 'new.js').write_text('console.log("built fixture")', encoding='utf-8')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True, stderr=subprocess.STDOUT)

    def test_new_compiled_assets_and_exact_digests_are_packaged_without_private_data(self):
        out = self.root / 'output/release/first'; result = package(self.root, out, self.sha)
        self.assertEqual(result['source_sha'], self.sha)
        for asset in result['assets']:
            self.assertEqual(hashlib.sha256((out / asset['name']).read_bytes()).hexdigest(), asset['sha256'])
        with zipfile.ZipFile(out / 'phdlab-1.2.3-source.zip') as archive:
            names = archive.namelist(); self.assertNotIn('data/private.txt', names); self.assertNotIn('.env', names)
            self.assertIn('agent/AGENT.md', names); self.assertIn('skills/fixture/SKILL.md', names)
        with zipfile.ZipFile(out / 'phdlab-1.2.3-web.zip') as archive:
            self.assertIn('new.js', archive.namelist())

    def test_wrong_commit_and_unsafe_output_are_rejected(self):
        for target, sha in [(self.root / 'output/release/x', 'f' * 40), (self.root / 'outside', self.sha)]:
            with self.subTest(target=target), self.assertRaises(ValueError): package(self.root, target, sha)

    def test_version_mismatch_and_missing_build_are_rejected(self):
        (self.root / 'start.py').write_text('APP_VERSION = "9.9.9"', encoding='utf-8')
        with self.assertRaises(ValueError): package(self.root, self.root / 'output/release/a', self.sha)
        (self.root / 'start.py').write_text('APP_VERSION = "1.2.3"', encoding='utf-8')
        (self.root / 'frontend/dist/index.html').unlink()
        with self.assertRaises(ValueError): package(self.root, self.root / 'output/release/b', self.sha)

    def test_archive_is_reproducible_and_does_not_overwrite_a_prior_output(self):
        a = package(self.root, self.root / 'output/release/a', self.sha)
        b = package(self.root, self.root / 'output/release/b', self.sha)
        self.assertEqual(a, b)
        with self.assertRaises(ValueError): package(self.root, self.root / 'output/release/a', self.sha)

    def test_uncommitted_source_cannot_be_labeled_with_the_committed_sha(self):
        with (self.root / 'start.py').open('a', encoding='utf-8') as stream:
            stream.write('\nUNAPPROVED_RUNTIME_CHANGE = True\n')
        with self.assertRaises(ValueError): package(self.root, self.root / 'output/release/dirty', self.sha)

    def test_source_archive_preserves_git_executable_permissions(self):
        # Git's index bit alone leaves the Linux checkout dirty. Model a real
        # executable file before committing; Windows still needs update-index.
        (self.root / 'start.py').chmod(0o755)
        self.git('update-index', '--chmod=+x', 'start.py')
        self.git('-c', 'user.name=QA', '-c', 'user.email=qa@example.invalid', 'commit', '-qm', 'executable fixture')
        sha = self.git('rev-parse', 'HEAD').strip()
        out = self.root / 'output/release/executable'; package(self.root, out, sha)
        with zipfile.ZipFile(out / 'phdlab-1.2.3-source.zip') as archive:
            self.assertEqual((archive.getinfo('start.py').external_attr >> 16) & 0o777, 0o755)
