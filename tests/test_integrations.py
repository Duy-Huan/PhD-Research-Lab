import _env  # noqa: F401  (must be first)
import copy
import json
import os
import tempfile
import unittest
from collections import deque
from pathlib import Path
from unittest import mock

from backend.config import load_config
from backend.connectors.registry import chat_block, registry
from backend.integrations import agents as A, base as B, experiment as X, workspace as W


class Contract(unittest.TestCase):
    def test_status_states_are_validated(self):
        with self.assertRaises(ValueError):
            B.IntegrationStatus("x", "X", "ok")
        s = B.IntegrationStatus("x", "X", "available")
        self.assertTrue(s.to_dict()["ok"])

    def test_local_backend_capabilities_are_explicit(self):
        lb = X.LocalRunsBackend()
        self.assertTrue(lb.status().ok)
        with self.assertRaises(B.NotSupported):
            lb.log_metric("id", "loss", 1.0)


class ClearML(unittest.TestCase):
    def cfg(self, **c):
        cfg = copy.deepcopy(load_config())
        cfg["clearml"].update(c)
        return cfg

    SDK_OK = {"installed": True, "ok": True, "version": "2.1.12", "error": ""}

    def test_states_offline_mode(self):
        self.assertEqual(X.ClearMLAdapter(self.cfg(enabled=False)).status().state, "disabled")
        with mock.patch.object(X.ClearMLAdapter, "sdk_installed", return_value=False):
            st = X.ClearMLAdapter(self.cfg(enabled=True)).status()
            self.assertEqual(st.state, "unavailable")
            self.assertTrue(st.extra["can_install"])
            self.assertIn("pip install clearml", " ".join(st.setup))
        with mock.patch.object(X.ClearMLAdapter, "sdk_installed", return_value=True), \
                mock.patch.object(X.ClearMLAdapter, "sdk", return_value={"installed": True, "ok": False, "version": "", "error": "DLL load failed"}):
            st = X.ClearMLAdapter(self.cfg(enabled=True)).status()
            self.assertEqual(st.state, "error")  # e.g. Smart App Control blocked a native dependency
        with mock.patch.object(X.ClearMLAdapter, "sdk_installed", return_value=True), mock.patch.object(X.ClearMLAdapter, "sdk", return_value=self.SDK_OK), \
                mock.patch.object(X.ClearMLAdapter, "server_ready", return_value=False):
            st = X.ClearMLAdapter(self.cfg(enabled=True, mode="offline")).status()
            self.assertEqual(st.state, "available")  # offline: no server needed
            self.assertNotIn("import_offline", st.capabilities)
            with self.assertRaises(B.NotSupported):  # fine-grained ops need a server
                X.ClearMLAdapter(self.cfg(enabled=True, mode="offline")).create_experiment("x")

    def test_states_server_mode(self):
        with mock.patch.object(X.ClearMLAdapter, "sdk_installed", return_value=True), mock.patch.object(X.ClearMLAdapter, "sdk", return_value=self.SDK_OK), \
                mock.patch.object(X, "_clearml_conf_file", return_value=False), mock.patch.dict(os.environ, {"CLEARML_API_HOST": "", "CLEARML_API_ACCESS_KEY": ""}):
            self.assertEqual(X.ClearMLAdapter(self.cfg(enabled=True, mode="server")).status().state, "unconfigured")
            ad = X.ClearMLAdapter(self.cfg(enabled=True, mode="server", api_host="http://127.0.0.1:9", access_key="k", secret_key="s"))
            self.assertEqual(ad.status().state, "unavailable")
            with self.assertRaises(B.IntegrationError):
                ad.sync_run("20260101-120000-abcd")

    def test_worker_output_parsing(self):
        class R:
            returncode, stderr = 0, ""
            stdout = 'ClearML Task: created\n@@RESULT@@{"task_id": "offline-' + "a" * 32 + '"}\nClearML Task: Offline session stored in x.zip\n'
        with mock.patch.object(X.subprocess, "run", return_value=R()):
            self.assertEqual(X.run_worker("probe", {}, True, {})["task_id"], "offline-" + "a" * 32)
        R.stdout, R.returncode = '@@ERROR@@{"error": "ValueError: boom"}\n', 1
        with mock.patch.object(X.subprocess, "run", return_value=R()):
            with self.assertRaises(B.IntegrationError) as cm:
                X.run_worker("probe", {}, True, {})
        self.assertIn("boom", str(cm.exception))

    def test_server_credentials_never_reach_offline_workers(self):
        seen = {}

        def fake_run(args, **kw):
            seen.update(kw["env"])

            class R:
                returncode, stderr, stdout = 0, "", '@@RESULT@@{"version": "x"}'
            return R()
        with mock.patch.dict(os.environ, {"CLEARML_API_SECRET_KEY": "leak"}), mock.patch.object(X.subprocess, "run", side_effect=fake_run):
            X.run_worker("probe", {}, True, {})
        self.assertNotIn("CLEARML_API_SECRET_KEY", seen)
        self.assertTrue(seen["CLEARML_CACHE_DIR"].endswith("clearml"))

    def test_read_offline_session_zip(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            z = os.path.join(d, "offline-" + "b" * 32 + ".zip")
            task = {"id": "offline-" + "b" * 32, "name": "t [r1]", "project_name": "P",
                    "hyperparams": {"General": {"run_id": {"value": "r1"}, "status": {"value": "done"}}},
                    "script": {"repository": "", "branch": "main", "version_num": "abc", "entry_point": "python t.py"}}
            ev = [{"type": "training_stats_scalar", "metric": "loss", "variant": "loss", "value": v, "iter": i} for i, v in enumerate((1.0, 0.5))]
            with zipfile.ZipFile(z, "w") as f:
                f.writestr("task.json", json.dumps(task))
                f.writestr("metrics.jsonl", json.dumps(ev) + "\n")
            s = X.read_offline_session(Path(z))
        self.assertEqual((s["run_id"], s["status"], s["metrics"]["loss"], s["points"]["loss"]), ("r1", "done", 0.5, 2))
        self.assertEqual(s["script"]["commit"], "abc")

    def test_run_env_only_in_offline_mode_and_without_secrets(self):
        cfg = self.cfg(enabled=True, mode="offline", secret_key="s3cret")
        env = X.run_env("/runs/r1", cfg)
        self.assertEqual(env, {"CLEARML_OFFLINE_MODE": "1", "CLEARML_CACHE_DIR": "/runs/r1/clearml"})
        self.assertEqual(X.run_env("/runs/r1", self.cfg(enabled=True, mode="server")), {})


class Workspace(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("workspace")

    def test_targets_are_allow_listed(self):
        with self.assertRaises(B.IntegrationError):
            W.resolve_target("C:/Windows")
        self.assertTrue(W.deep_link("code").startswith("vscode://file/"))
        self.assertIn("dev-container+", W.devcontainer_uri("code"))

    def test_environment_files_respect_hardware_caps(self):
        from backend import resources
        with mock.patch.object(resources, "_scan", return_value={"memory": {"total_gb": 32}, "cpu": {"cores": 16},
                                                                    "gpus": [{"vram_total_mb": 12288}]}):
            files = W.build_environment({"gpu": True, "torch": "2.5.1", "cuda": "12.4"})
        dc = json.loads(files[".devcontainer/devcontainer.json"])
        self.assertIn("--gpus", dc["runArgs"])
        self.assertIn("--memory=16g", dc["runArgs"])
        self.assertIn("--cpus=6", dc["runArgs"])
        self.assertIn("FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime", files[".devcontainer/Dockerfile"])
        with self.assertRaises(B.IntegrationError):
            W.build_environment({"gpu": True, "torch": "9.9", "cuda": "1.0"})
        with self.assertRaises(B.IntegrationError):
            W.build_environment({"gpu": False, "datasets_dir": "relative/path"})

    def test_open_file_and_extensions_are_restricted(self):
        with self.assertRaises(B.IntegrationError):
            W.open_file("../../outside.py")
        with self.assertRaises(B.IntegrationError):
            W.open_file("missing.py")
        with self.assertRaises(B.IntegrationError):
            W.install_extension("evil.publisher-ext")
        self.assertIn("openai.chatgpt", W.INSTALLABLE)

    def test_write_environment_never_overwrites_silently(self):
        W.write_environment({"gpu": False, "python": "3.11"})
        with self.assertRaises(B.IntegrationError):
            W.write_environment({"gpu": False, "python": "3.11"})
        self.assertTrue(W.write_environment({"gpu": False, "python": "3.12"}, overwrite=True)["overwritten"])


class Codex(unittest.TestCase):
    def test_disabled_and_missing_cli(self):
        cfg = copy.deepcopy(load_config())
        self.assertEqual(A.CodexBackend(cfg).status().state, "disabled")
        cfg["codex"]["enabled"] = True
        B.clear_cache()
        with mock.patch.object(A.CodexBackend, "binary", return_value=None):
            st = A.CodexBackend(cfg).status()
        self.assertEqual(st.state, "unavailable")
        with self.assertRaises(B.IntegrationError):
            with mock.patch.object(A.CodexBackend, "binary", return_value=None):
                A.CodexBackend(cfg).start_run("fix the bug")

    def test_event_mapping(self):
        run = {"thread_id": "", "usage": {}, "errors": [], "status": "running", "final_message": "", "events": deque(maxlen=10)}
        for ev in ({"type": "thread.started", "thread_id": "th_1"},
                   {"type": "item.completed", "item": {"id": "i1", "type": "command_execution", "command": "pytest", "status": "completed"}},
                   {"type": "item.completed", "item": {"id": "i2", "type": "agent_message", "text": "Done: fixed it"}},
                   {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}}):
            A.apply_event(run, ev)
        self.assertEqual(run["thread_id"], "th_1")
        self.assertEqual(run["final_message"], "Done: fixed it")
        self.assertEqual(run["usage"]["output_tokens"], 5)
        A.apply_event(run, {"type": "turn.failed", "error": {"message": "auth required"}})
        self.assertEqual(run["status"], "failed")
        self.assertIn("auth required", run["errors"][0])


class Connectors(unittest.TestCase):
    def test_registry_discovers_plugins(self):
        names = {c["name"] for c in registry().list()}
        self.assertTrue({"huggingface", "kaggle"} <= names)

    def test_kaggle_without_token_is_unconfigured(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"KAGGLE_CONFIG_DIR": d, "KAGGLE_USERNAME": "", "KAGGLE_KEY": ""}):
            self.assertEqual(registry().connectors["kaggle"].status()["state"], "unconfigured")

    def test_chat_command(self):
        self.assertEqual(chat_block("normal question"), "")
        fake = {"source": "huggingface", "query": "q", "items": [{"id": "org/ds", "title": "org/ds", "url": "https://hf.co/org/ds"}]}
        with mock.patch.object(registry(), "fetch", return_value=fake):
            self.assertIn("org/ds", chat_block("/hf hyperspectral"))


if __name__ == "__main__":
    unittest.main()
