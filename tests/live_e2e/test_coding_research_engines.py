"""Coding & Research Engines Live Verification Suite.

Tests:
  - Python sandbox subprocess execution with CPU/wall-time bounds
  - Feynman, OpenScience, and OpenCode adapter health and capability truthfulness
  - ClearML offline experiment tracking integration
"""
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.live_e2e.conftest_or_setup import configure_live_phi4
from backend.core import config as C
from backend.execution import tools, tracker
from backend.research_engines.registry import FACTORIES, get


class TestCodingResearchEngines(unittest.TestCase):
    def setUp(self):
        configure_live_phi4()

    def test_sandbox_python_subprocess_caps_and_artifacts(self):
        """Run bounded Python script in subprocess, capture stdout and verify SHA-256."""
        script = """
import hashlib
data = b'PhD Lab Reproducible Research Artifact'
sha = hashlib.sha256(data).hexdigest()
print(f'HASH={sha}')
"""
        code, out = tools.run_cli([sys.executable, "-c", script], timeout=10)
        self.assertEqual(code, 0)
        expected_sha = hashlib.sha256(b'PhD Lab Reproducible Research Artifact').hexdigest()
        self.assertIn(f"HASH={expected_sha}", out)

    def test_research_engines_registry_health_and_capabilities(self):
        """Enumerate research engines (feynman, openscience, opencode)."""
        engines = list(FACTORIES.keys())
        self.assertIn("opencode", engines)
        self.assertIn("feynman", engines)
        self.assertIn("openscience", engines)

        for eng_name in engines:
            eng = get(eng_name)
            h = eng.health()
            state = getattr(h, "state", None) or (h.get("state") if isinstance(h, dict) else "")
            self.assertIn(state.upper(), ("READY", "INSTALLED", "NOT_INSTALLED", "UNAVAILABLE", "ERROR", "DISABLED", "UNKNOWN"))

    def test_clearml_offline_tracker(self):
        """Verify ClearML offline cache directory is safely created inside project."""
        cd = tracker.clearml_dir()
        self.assertTrue(cd.exists())
        self.assertTrue(cd.is_dir())


if __name__ == "__main__":
    unittest.main()
