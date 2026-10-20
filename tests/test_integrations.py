import _env  # noqa: F401  (must be first)
import copy
import json
import os
import tempfile
import unittest
from collections import deque
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

    def test_disabled_unavailable_unconfigured(self):
        self.assertEqual(X.ClearMLAdapter(self.cfg(enabled=False)).status().state, "disabled")
        with mock.patch.object(X.ClearMLAdapter, "sdk_installed", return_value=False):
            self.assertEqual(X.ClearMLAdapter(self.cfg(enabled=True)).status().state, "unavailable")
        with mock.patch.object(X.ClearMLAdapter, "sdk_installed", return_value=True), mock.patch.object(X, "_clearml_conf_file", return_value=False), \
                mock.patch.dict(os.environ, {"CLEARML_API_HOST": "", "CLEARML_API_ACCESS_KEY": ""}):
            self.assertEqual(X.ClearMLAdapter(self.cfg(enabled=True)).status().state, "unconfigured")

    def test_server_down_is_unavailable_and_never_called_success(self):
        ad = X.ClearMLAdapter(self.cfg(enabled=True, api_host="http://127.0.0.1:9", access_key="k", secret_key="s"))
        with mock.patch.object(X.ClearMLAdapter, "sdk_installed", return_value=True):
            st = ad.status()
            self.assertEqual(st.state, "unavailable")
            with self.assertRaises(B.IntegrationError):
                ad.sync_run("20260101-120000-abcd")


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
