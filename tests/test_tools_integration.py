"""JupyterLab, Codex CLI and ClearML wired to the Python environment that runs the app (no PATH assumptions)."""
import _env  # noqa: F401  (must be first)
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from backend import sandbox
from backend.config import load_config, save_config
from backend.integrations import agents as A, base as B, workspace as W


class Jupyter(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("jupyter")

    def test_found_through_the_app_python_module(self):
        # v3.4: the project environment and every Python on the machine are searched too (envs.discover_pythons)
        with mock.patch.object(W, "_project_python", return_value=None),                 mock.patch.object(W.importlib.util, "find_spec", return_value=object()):
            self.assertEqual(W.jupyter_argv(), [sys.executable, "-m", "jupyterlab"])
        with mock.patch.object(W, "_project_python", return_value=None), mock.patch("backend.envs.python_with", return_value=None),                 mock.patch.object(W.importlib.util, "find_spec", return_value=None), mock.patch.object(W, "which", return_value=None):
            self.assertIsNone(W.jupyter_argv())
            self.assertEqual(W.jupyter_status().state, "unavailable")

    def test_notebook_template_and_no_overwrite(self):
        nb = W.create_notebook("Baseline exploration!")
        self.assertEqual(nb["path"], "notebooks/Baseline-exploration.ipynb")
        d = json.loads((sandbox.code_dir() / nb["path"]).read_text("utf-8"))
        src = "".join("".join(c["source"]) for c in d["cells"])
        self.assertEqual(d["nbformat"], 4)
        self.assertIn("Task.init", src)
        self.assertIn("Context Memory", src)
        with self.assertRaises(B.IntegrationError):
            W.create_notebook("Baseline exploration!")

    def test_kernel_env_has_project_context_and_no_secrets(self):
        save_config({"clearml": {"enabled": True, "mode": "offline"}})
        with mock.patch.dict(os.environ, {"CLEARML_API_SECRET_KEY": "leak", "PHDLAB_DATA_DIR": os.environ["PHDLAB_DATA_DIR"]}):
            env = W._kernel_env()
        self.assertNotIn("CLEARML_API_SECRET_KEY", env)
        self.assertNotIn("PHDLAB_DATA_DIR", env)
        self.assertEqual(env["CLEARML_OFFLINE_MODE"], "1")
        self.assertTrue(env["CLEARML_CACHE_DIR"].endswith("clearml"))
        from backend.config import data_dir
        self.assertEqual(env["PHDLAB_PROJECT"], data_dir().name)

    @unittest.skipUnless(importlib.util.find_spec("jupyterlab"), "JupyterLab not installed")
    def test_real_launch_token_and_stop(self):
        import httpx
        r = W.jupyter_launch("code")
        try:
            tok = r["url"].split("token=")[1]
            self.assertEqual(httpx.get(f"http://127.0.0.1:{r['port']}/api/status", params={"token": tok}).status_code, 200)
            self.assertEqual(httpx.get(f"http://127.0.0.1:{r['port']}/api/status").status_code, 403)
            self.assertTrue(W.jupyter_launch("code")["already_running"])
        finally:
            self.assertTrue(W.jupyter_stop()["stopped"])
        self.assertFalse(W.jupyter_status().extra["running"])


class CodexArgs(unittest.TestCase):
    def cfg(self, **c):
        cfg = copy.deepcopy(load_config())
        cfg["codex"].update(enabled=True, **c)
        return cfg

    def test_npm_shim_is_bypassed_on_windows(self):
        with tempfile.TemporaryDirectory() as d:
            shim = Path(d) / "codex.cmd"
            shim.write_text("@echo off", "utf-8")
            js = Path(d) / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            js.parent.mkdir(parents=True)
            js.write_text("", "utf-8")
            with mock.patch.object(A.sys, "platform", "win32"), mock.patch.object(A, "which", side_effect=lambda n: str(shim) if n == "codex" else "node.exe"):
                self.assertEqual(A.CodexBackend(self.cfg()).argv(), ["node.exe", str(js)])

    def _args(self, **kw):
        seen = {}

        class P:
            pid, stdin, stdout, stderr, returncode = 1, mock.MagicMock(), mock.MagicMock(), mock.MagicMock(), 0

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0
        P.stdout.readline.return_value = ""
        P.stderr.readline.return_value = ""

        def popen(args, **k):
            seen["args"] = args
            return P()
        cb = A.CodexBackend(self.cfg(**kw.pop("cfg", {})))
        st = B.IntegrationStatus("codex", "Codex", "available")
        with mock.patch.object(A.CodexBackend, "status", return_value=st), mock.patch.object(A.CodexBackend, "argv", return_value=["codex"]), \
                mock.patch.object(A.subprocess, "Popen", side_effect=popen), mock.patch.object(A.threading, "Timer"), \
                mock.patch.object(A.sys, "platform", "win32"):
            cb.start_run("task", **kw)
        time.sleep(0.3)
        return seen["args"]

    def test_new_run_arguments(self):
        _env.fresh_project("codex-args")
        a = self._args()
        self.assertEqual(a[:2], ["codex", "exec"])
        self.assertEqual(a[a.index("--sandbox") + 1], "read-only")
        self.assertIn("windows.sandbox=unelevated", a)
        self.assertIn("-C", a)
        self.assertEqual(a[-1], "-")  # prompt via stdin
        self.assertNotIn("danger-full-access", " ".join(a))
        self.assertEqual(self._args(allow_write=True)[self._args(allow_write=True).index("--sandbox") + 1], "workspace-write")

    def test_resume_uses_config_override_not_sandbox_flag(self):
        _env.fresh_project("codex-resume")
        a = self._args(resume_thread="01a156f2-06e6-7653-8c73-6e95468c2bb7", allow_write=True)
        self.assertEqual(a[:3], ["codex", "exec", "resume"])
        self.assertNotIn("--sandbox", a)  # `codex exec resume` has no --sandbox option
        self.assertIn("sandbox_mode=workspace-write", a)
        self.assertEqual(a[-2:], ["01a156f2-06e6-7653-8c73-6e95468c2bb7", "-"])

    def test_windows_sandbox_config_passthrough(self):
        _env.fresh_project("codex-cfg")
        self.assertNotIn("windows.sandbox=unelevated", " ".join(self._args(cfg={"windows_sandbox": "config"})))
        self.assertIn("windows.sandbox=elevated", self._args(cfg={"windows_sandbox": "elevated"}))


class SandboxVenv(unittest.TestCase):
    def test_local_venv_inherits_app_packages(self):
        _env.fresh_project("venv-inherit")
        sandbox.save_settings({"mode": "local", "gpu": False, "inherit_packages": True})
        py = sandbox._local_python()
        cfg = (Path(py).parent.parent / "pyvenv.cfg").read_text("utf-8").lower()
        self.assertIn("include-system-site-packages = true", cfg)
        out = subprocess.run([py, "-c", "import fastapi; print('ok')"], capture_output=True, text=True, timeout=120)
        self.assertEqual(out.stdout.strip(), "ok")  # a package of the app's Python is importable in the sandbox venv
        sandbox.save_settings({"inherit_packages": False})
        sandbox._local_python()
        self.assertIn("include-system-site-packages = false", (Path(py).parent.parent / "pyvenv.cfg").read_text("utf-8").lower())


if __name__ == "__main__":
    unittest.main()
