"""Real subprocess protocol faults and HTTP compute handoff boundaries, with no cloud execution."""
import _env
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend.core import config
from backend.providers import app_server as A, cli as C
from backend.execution import remote_compute as RC


class RPC(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("rpc-contract")
        self.peer = str(Path(__file__).parent / "providers" / "fake_app_server.py")

    def connection(self, mode):
        return SimpleNamespace(_prefix=lambda: [sys.executable, self.peer, mode], env=lambda: {})

    def test_catalog_real_pipe_deduplicates_and_reports_rejection(self):
        for mode in ("ok", "catalog_error", "eof"):
            with self.subTest(mode=mode), mock.patch.dict(C.CONNECTORS, {"codex": self.connection(mode)}):
                if mode == "ok":
                    self.assertEqual(A.model_catalog(), ["catalog-model"])
                else:
                    with self.assertRaises(A.StartupFailure): A.model_catalog()

    def test_stream_tools_noise_interrupt_error_and_firewall(self):
        for mode in ("tools", "noise", "interrupted", "server_error", "forbidden"):
            context = {"request_id": "rpc-fault-" + mode, "cwd": str(config.data_dir()), "timeout_s": 5,
                       "model": "test-model", "reasoning": "high", "profile": "assisted"}
            with self.subTest(mode=mode):
                if mode in ("server_error", "forbidden"):
                    with self.assertRaises(C.ProviderError) as error:
                        list(A.stream(self.connection(mode), "fixture", context, []))
                    self.assertNotIsInstance(error.exception, A.StartupFailure)
                else:
                    events = list(A.stream(self.connection(mode), "fixture", context, []))
                    if mode == "tools":
                        self.assertEqual([e["type"] for e in events if e["type"].startswith("tool_")], ["tool_call", "tool_result"])
                    self.assertEqual(events[-1]["type"], "request_cancelled" if mode == "interrupted" else "request_completed")
                self.assertNotIn(context["request_id"], C._procs)

    def test_launch_failure_cancel_and_startup_deadline_clean_registry(self):
        context = {"request_id": "rpc-no-start", "cwd": str(config.data_dir()), "timeout_s": 5}
        with mock.patch.object(A.subprocess, "Popen", side_effect=OSError("not installed")):
            with self.assertRaises(A.StartupFailure): list(A.stream(self.connection("ok"), "fixture", context, []))
        for timeout, cancel in ((.00001, None), (5, threading.Event())):
            if cancel: cancel.set()
            context.update(timeout_s=timeout, _cancel=cancel)
            if cancel:
                self.assertEqual(list(A.stream(self.connection("ok"), "fixture", context, []))[-1]["type"], "request_cancelled")
            else:
                with self.assertRaises(A.StartupFailure): list(A.stream(self.connection("ok"), "fixture", context, []))
            self.assertNotIn(context["request_id"], C._procs)


class ComputeAPI(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("compute-api")
        from fastapi.testclient import TestClient
        from backend.app import app
        from backend.execution.code_projects import active_dir
        (active_dir() / "train.py").write_text("print('baseline')", "utf-8")
        self.client = TestClient(app)

    def test_approval_download_and_verified_collection_end_to_end(self):
        self.assertEqual(self.client.get("/api/compute/runs").status_code, 200)
        created = self.client.post("/api/compute/runs", json={"files": ["train.py"], "required_artifacts": ["metrics.json"]})
        self.assertEqual(created.status_code, 200, created.text)
        rid = created.json()["run_id"]
        url = "/api/compute/runs/" + rid
        self.assertEqual(self.client.get(url).json()["status"], "awaiting_approval")
        self.assertEqual(self.client.get(url + "/bundle").status_code, 400)
        self.assertEqual(self.client.post(url + "/approve").status_code, 200)
        self.assertTrue(self.client.get(url + "/bundle").content.startswith(b"PK"))
        from backend.execution.tools import IntegrationError
        with mock.patch("backend.execution.tracker.run_worker", side_effect=IntegrationError("access_token=secret-value-12345")):
            fault = self.client.post(url + "/sync", json={"task_id": "task123456"})
        self.assertEqual(fault.status_code, 502)
        self.assertNotIn("secret-value-12345", fault.text)
        def collect(cmd, args, **kwargs):
            dest = Path(args["destination"])
            dest.mkdir(parents=True, exist_ok=True)
            file = dest / "metrics.json"
            file.write_text('{"loss":0.1}')
            return {"status": "completed", "metrics": {}, "artifacts": [{"name": file.name, "sha256": RC.sha(file)}]}
        with mock.patch("backend.execution.tracker.run_worker", side_effect=collect):
            result = self.client.post(url + "/sync", json={"task_id": "task123456", "collect": True})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "completed")
