"""Standalone worker contract tests: no SDK hooks, no server and no unsafe deserialization."""
import _env
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

from backend.core import config
from backend.execution import clearml_worker as W


class Worker(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("worker-contract")
        self.task = mock.MagicMock()
        self.task.id, self.task.project = "task-real-id", "project-real-id"
        self.task.get_status.return_value = "completed"
        self.task.get_parameters.return_value = {"General/run_id": "rc-123456789012"}
        self.task.get_last_scalar_metrics.return_value = {"loss": {"val": .1}}
        self.task.get_offline_mode_folder.return_value = str(config.data_dir() / "offline")
        self.task.artifacts = {}
        self.Task = mock.MagicMock()
        self.Task.init.return_value = self.task
        self.Task.get_task.return_value = self.task
        self.module = ModuleType("clearml")
        self.module.Task, self.module.__version__ = self.Task, "fixture-version"

    def invoke(self, request):
        stdout = io.StringIO()
        with mock.patch.dict("sys.modules", {"clearml": self.module}), \
             mock.patch.object(W.sys, "stdin", io.StringIO(json.dumps(request))), contextlib.redirect_stdout(stdout):
            code = W.main()
        line = stdout.getvalue().strip().splitlines()[-1]
        prefix = W.RESULT if code == 0 else W.ERROR
        self.assertTrue(line.startswith(prefix), line)
        return code, json.loads(line[len(prefix):])

    def request(self, **kwargs):
        return {"cmd": "remote_snapshot", "offline": False, "args": {"task_id": "task-real-id",
                "run_id": "rc-123456789012", "collect": True, "destination": str(config.data_dir() / "collected"),
                "required_artifacts": ["metrics.json"]} | kwargs}

    def artifact(self, digest="sha256"):
        source = config.data_dir() / "remote-cache.json"
        source.write_bytes(b'{"loss":0.1}')
        art = mock.Mock(hash=hashlib.new(digest, source.read_bytes()).hexdigest() if digest else "")
        art.get_local_copy.return_value = str(source)
        self.task.artifacts["metrics.json"] = art
        return source, art

    def test_probe_and_unknown_command_protocol(self):
        code, result = self.invoke({"cmd": "probe"})
        self.assertEqual((code, result), (0, {"version": "fixture-version"}))
        code, result = self.invoke({"cmd": "no-such-command"})
        self.assertEqual(code, 1)
        self.assertIn("unknown command", result["error"])
        self.Task.init.assert_not_called()

    def test_offline_record_keeps_measured_metrics_and_code_identity(self):
        artifact, _ = self.artifact()
        offline = config.data_dir() / "offline.zip"
        offline.write_bytes(b"PK")
        request = {"cmd": "record_run", "args": {"project": "P", "run": {"id": "run-1", "title": "baseline",
            "cmd": "python train.py", "git": {"remote": "https://example.org/repo", "sha": "abc", "branch": "main"},
            "environment": {"cuda": False}, "metrics": {"loss": .1, "skip_bool": True, "skip_text": "unknown"},
            "series": {"loss": [[0, 1.], [1, .1]]}, "stdout_tail": "epoch 1", "files": [str(artifact), str(artifact) + ".missing"]}}}
        with mock.patch.dict(os.environ, {}, clear=False):
            code, result = self.invoke(request)
            self.assertEqual(os.environ["CLEARML_VCS_COMMIT_ID"], "abc")
        self.assertEqual(code, 0)
        self.assertTrue(result["session_zip"].endswith("offline.zip"))
        self.Task.set_offline.assert_called_once_with(True)
        self.task.get_logger().report_single_value.assert_called_once_with(name="loss", value=.1)
        self.assertEqual(self.task.get_logger().report_scalar.call_count, 2)
        self.task.upload_artifact.assert_called_once()
        self.task.close.assert_called_once()

    def test_record_tolerates_sdk_script_metadata_unavailable(self):
        self.task.data.script = None
        self.task._wait_for_repo_detection.side_effect = RuntimeError("not available")
        args = {"run": {"id": "r", "git": {}, "cmd": "", "status": ""}}
        result = W.record_run(self.Task, args)
        self.assertIn("script section not available", result["notes"][0])
        self.assertEqual(result["session_zip"], "")
        self.task.data.script = object()
        self.task.set_script.side_effect = RuntimeError("old SDK")
        self.assertIn("set_script skipped", W.record_run(self.Task, args)["notes"][0])

    def test_remote_snapshot_requires_online_and_matching_run_identity(self):
        request = self.request()
        request["offline"] = True
        code, result = self.invoke(request)
        self.assertEqual(code, 1)
        self.assertIn("online mode", result["error"])
        self.task.get_parameters.return_value = {"General/run_id": "another-run"}
        code, result = self.invoke(self.request())
        self.assertEqual(code, 1)
        self.assertIn("does not match", result["error"])
        self.assertFalse((config.data_dir() / "collected").exists())

    def test_snapshot_without_collection_never_downloads(self):
        _, art = self.artifact()
        code, result = self.invoke(self.request(collect=False))
        self.assertEqual(code, 0)
        self.assertEqual(result["artifacts"], [])
        art.get_local_copy.assert_not_called()

    def test_collection_accepts_sha256_md5_and_missing_legacy_hash(self):
        for digest in ("sha256", "md5", ""):
            with self.subTest(digest=digest):
                source, art = self.artifact(digest)
                code, result = self.invoke(self.request())
                self.assertEqual(code, 0, result)
                target = config.data_dir() / "collected" / "metrics.json"
                self.assertEqual(target.read_bytes(), source.read_bytes())
                self.assertEqual(result["artifacts"][0]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
                art.get_local_copy.assert_called_once_with(extract_archive=False)
                art.get.assert_not_called()

    def test_corruption_never_publishes_or_leaves_partial_bytes(self):
        for expected in ("f" * 64, "f" * 32):
            _, art = self.artifact()
            art.hash = expected
            code, result = self.invoke(self.request())
            self.assertEqual(code, 1)
            self.assertIn("checksum mismatch", result["error"])
            dest = config.data_dir() / "collected"
            self.assertEqual(list(dest.iterdir()), [], "Failed downloads must remove partial files")

    def test_missing_artifacts_and_nonfiles_are_refused(self):
        code, result = self.invoke(self.request())
        self.assertEqual(code, 1)
        self.assertIn("Required artifact missing", result["error"])
        _, art = self.artifact()
        art.get_local_copy.return_value = str(config.data_dir())
        code, result = self.invoke(self.request())
        self.assertEqual(code, 1)
        self.assertIn("regular file", result["error"])

    def test_malformed_input_remains_a_structured_worker_error(self):
        stdout = io.StringIO()
        with mock.patch.object(W.sys, "stdin", io.StringIO("{invalid")), contextlib.redirect_stdout(stdout):
            code = W.main()
        self.assertEqual(code, 1)
        self.assertIn(W.ERROR, stdout.getvalue())
