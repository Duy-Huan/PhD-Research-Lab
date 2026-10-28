"""FQC-DEPS-PINS-664 (agent/PLAN_6.6.4_L3.md A4): installs honour pins, one install per environment, no inherited packages.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): after a pinned requirement failed, the import fallback
installed the latest version instead (matplotlib 3.11.2 for a 3.9.2 pin, torch 2.6.0+cu124 for a 2.5.1+cpu pin); two
runs installed into the same venv at once; the project venv inherited the interpreter's packages. The real generated
ensure_deps.py runs offline (PIP_NO_INDEX), so pip fails and the decisions show in its output."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import _env
from backend.execution import deps


class Pins(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.lock = self.root / "deps.lock"

    def ensure(self, requirements: str, imports: list, extra_env=None):
        (self.root / "requirements.txt").write_text(requirements, "utf-8")
        d = self.root / ".phdlab"
        d.mkdir(exist_ok=True)
        (d / "deps.json").write_text(json.dumps({"requirements_files": ["requirements.txt"], "declared": [], "imports": imports}), "utf-8")
        (d / "ensure_deps.py").write_text(deps.ENSURE, "utf-8")
        env = {**os.environ, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PHDLAB_DEPS_LOCK": str(self.lock),
               **(extra_env or {})}
        return subprocess.run([sys.executable, str(d / "ensure_deps.py")], capture_output=True, text=True, cwd=str(self.root),
                              env=env, timeout=300)

    def test_a_failed_pinned_requirement_is_never_replaced_by_an_unpinned_install(self):
        r = self.ensure("phdlab-pinned-pkg==1.2.3\n", [{"module": "phdlab_pinned_pkg", "pip": "phdlab-pinned-pkg"}])
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("phdlab-pinned-pkg is named in a requirements file; it is not installed unpinned", r.stdout)
        self.assertNotIn("pip install phdlab-pinned-pkg", r.stdout)  # only `-r requirements.txt` was attempted
        self.assertIn("could not install: requirements.txt", r.stdout)

    def test_unpinned_imports_outside_the_requirements_are_still_installed(self):
        r = self.ensure("phdlab-pinned-pkg==1.2.3\n", [{"module": "phdlab_other_pkg", "pip": "phdlab-other-pkg"}])
        self.assertIn("pip install phdlab-other-pkg", r.stdout)

    def test_local_version_pins_use_the_matching_pytorch_index(self):
        for pin, index in (("torch==2.5.1+cpu", "https://download.pytorch.org/whl/cpu"),
                           ("torch==2.5.1+cu124", "https://download.pytorch.org/whl/cu124")):
            with self.subTest(pin=pin):
                r = self.ensure(pin + "\n", [])
                self.assertIn("--extra-index-url " + index, r.stdout)
        r = self.ensure("numpy==1.26.4\n", [])
        self.assertNotIn("--extra-index-url", r.stdout)

    def test_a_second_install_waits_for_the_first_and_a_stale_lock_is_taken_over(self):
        self.lock.mkdir()
        (self.lock / "owner").write_text("12345", "utf-8")
        t0 = time.monotonic()
        r = self.ensure("", [], {"PHDLAB_DEPS_LOCK_WAIT": "2"})
        self.assertEqual(r.returncode, 4)
        self.assertIn("waiting for another dependency install", r.stdout)
        self.assertIn("still running", r.stdout)
        self.assertGreaterEqual(time.monotonic() - t0, 2)
        old = time.time() - 7200
        os.utime(self.lock, (old, old))
        r = self.ensure("", [])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("taking over a dependency lock older than 1 h", r.stdout)
        self.assertFalse(self.lock.exists())  # released at exit

    def test_the_lock_is_released_after_an_install(self):
        r = self.ensure("", [])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.lock.exists())


class NewProjects(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("deps pins", code_project=None)

    def test_a_new_code_project_does_not_inherit_system_packages(self):
        from backend.execution import code_projects, sandbox
        code_projects.create("fresh", git=False, vscode=False, seed=False)
        self.assertFalse(sandbox.load_settings()["inherit_packages"])
        calls = []

        def fake_run(args, **kw):
            calls.append(args)
            return subprocess.CompletedProcess(args, 1, "", "no venv in this test")
        with patch.object(sandbox.subprocess, "run", side_effect=fake_run):
            sandbox._local_python()
        self.assertTrue(calls and "-m" in calls[0] and "venv" in calls[0])
        self.assertNotIn("--system-site-packages", calls[0])

    def test_an_explicit_choice_is_kept(self):
        from backend.execution import code_projects, sandbox
        code_projects.create("legacy", git=False, vscode=False, seed=False, settings={"inherit_packages": True})
        self.assertTrue(sandbox.load_settings()["inherit_packages"])


if __name__ == "__main__":
    unittest.main()
