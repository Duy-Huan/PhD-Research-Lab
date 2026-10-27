"""Offline GitHub protocol fixtures, not live release qualification."""
from pathlib import Path
import shutil
import subprocess
import unittest


class ReleaseProvenance(unittest.TestCase):
    def test_bounded_consistency_and_all_original_negative_qualification_cases(self):
        root = Path(__file__).resolve().parents[1]
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required; missing runtime cannot skip policy assertions')
        result = subprocess.run(
            [node, '--test', '.github/scripts/release_provenance.test.cjs'],
            cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
