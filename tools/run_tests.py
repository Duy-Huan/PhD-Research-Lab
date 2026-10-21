"""Run backend test modules quickly (no coverage) on a throw-away data folder.
Usage: .venv/Scripts/python tools/run_tests.py [module …]      e.g. test_runs test_skills   (none = every test_*.py)"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list) -> int:
    os.chdir(ROOT)
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    os.environ.setdefault("PHDLAB_DATA_DIR", tempfile.mkdtemp(prefix="phdlab-tests-"))
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromNames(argv) if argv else loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
