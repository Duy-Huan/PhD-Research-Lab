import _env  # noqa: F401
import json
import sys
import threading
import time
import unittest
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend.providers import gateway as G, cli as C, app_server as A, router
from backend.core import config
from backend.execution import remote_compute as RC
from providers.fakes import fake


class Runtime(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("runtime")
        config.save_config({"gateway": {"codex_app_server": False}})

    def request(self):
        with mock.patch.dict(C.CONNECTORS, {"codex": fake("codex")}):
            return G.prepare("Reply OK", "codex", memory=False)

    def test_bounded_replay_and_no_lost_wakeup(self):
        r = G.get(self.request()["id"])
        for i in range(G.EVENT_WINDOW + 30):
            G._publish(r, {"type": "text_delta", "text": str(i)})
        self.assertEqual(len(r["events"]), G.EVENT_WINDOW)
        a = G.wait_events(r["id"], 0, 0)
        b = G.wait_events(r["id"], a["next"], 0)
        self.assertEqual([e["text"] for e in a["events"] + b["events"]], [str(i) for i in range(G.EVENT_WINDOW + 30)])
        def terminal():
            time.sleep(0.02)
            with G._changed:
                r["status"] = "failed"
                G._changed.notify_all()
        th = threading.Thread(target=terminal)
        th.start()
        start = time.monotonic()
        self.assertEqual(G.wait_events(r["id"], b["next"], 2)["status"], "failed")
        self.assertLess(time.monotonic() - start, 0.5)
        th.join()

    def test_send_is_idempotent_and_redacts_events(self):
        with mock.patch.dict(C.CONNECTORS, {"codex": fake("codex")}):
            r = self.request()
            G.send(r["id"])
            thread = G.get(r["id"])["thread"]
            G.send(r["id"])
            self.assertIs(thread, G.get(r["id"])["thread"])
            thread.join(10)
            G._publish(G.get(r["id"]), {"type": "error", "message": "access_token=secret12345"})
            self.assertNotIn("secret12345", json.dumps(G.events(r["id"])))

    def test_provider_exception_retains_partial_findings(self):
        r = G.get(self.request()["id"])
        r["status"] = "running"
        def broken(message, context):
            yield {"type": "text_delta", "text": "finding already produced"}
            raise C.ProviderError("quota exceeded", "RATE_LIMITED")
        G._run_inner(r, SimpleNamespace(stream_message=broken), {})
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["answer"], "finding already produced")

    def test_native_rpc_resume_failure_and_approval(self):
        peer = str(Path(__file__).parent / "providers" / "fake_app_server.py")
        for mode in ("ok", "startup_fail", "turn_fail", "approval"):
            conn = SimpleNamespace(_prefix=lambda: [sys.executable, peer, mode], env=lambda: {})
            ctx = {"request_id": "rpc-test", "cwd": str(config.data_dir()), "resume_session": "thread-existing-123456", "timeout_s": 5}
            if mode == "startup_fail":
                with self.assertRaises(A.StartupFailure):
                    list(A.stream(conn, "hi", ctx, []))
            elif mode in ("turn_fail", "approval"):
                with self.assertRaises(C.ProviderError) as failure:
                    list(A.stream(conn, "hi", ctx, []))
                self.assertNotIsInstance(failure.exception, A.StartupFailure)
            else:
                events = list(A.stream(conn, "hi", ctx, []))
                self.assertEqual([e["text"] for e in events if e["type"] == "text_delta"], ["hello"])
                self.assertEqual(next(e["session_id"] for e in events if e.get("state") == "session"), ctx["resume_session"])
            self.assertNotIn("rpc-test", C._procs)

    def test_reasoning_cannot_fall_to_unverified_local(self):
        cfg = config.load_config()
        cfg["routing"]["chains"] = {"reasoning": ["ollama"], "summarize": ["ollama"]}
        with mock.patch.object(router, "online", return_value=False), mock.patch.object(router, "local_up", return_value=True):
            self.assertEqual(router.plan(cfg, "research")["candidates"], [])
            self.assertIn("ollama", router.plan(cfg, "research")["skipped"])

    def test_cancel_before_popen_does_not_start_a_process(self):
        cancel = threading.Event()
        cancel.set()
        with mock.patch.object(C.subprocess, "Popen") as popen:
            events = list(fake("claude_code").stream_message("hi", {"_cancel": cancel}))
        self.assertEqual(events[0]["type"], "request_cancelled")
        popen.assert_not_called()

    def test_alternative_qualification_is_model_specific(self):
        cfg = config.load_config()
        cfg["routing"]["chains"] = {"reasoning": ["openai", "anthropic"]}
        cfg["routing"]["verified_fallbacks"] = {"reasoning": ["anthropic:" + cfg["providers"]["anthropic"]["model"]]}
        with mock.patch.object(router, "online", return_value=True), mock.patch.object(router, "provider_ready", return_value=True):
            self.assertEqual(router.plan(cfg, "research")["candidates"], ["openai", "anthropic"])
            cfg["providers"]["anthropic"]["model"] = "unqualified-model"
            self.assertEqual(router.plan(cfg, "research")["candidates"], ["openai"])

    def test_sse_reconnect_cursor_and_delivery_telemetry(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        from backend.agent import sessions
        from backend.core.telemetry import RING
        session = sessions.create("resume")
        sid = session["id"]
        before = sessions.emit(sid, "message.delta", "turn-test", "cli:codex", text="before-cursor")
        sessions.emit(sid, "message.delta", "turn-test", "cli:codex", text="after-cursor")
        client = TestClient(app, headers={"X-PhDLab-Client": "ui", "Last-Event-ID": before["id"]})
        response = client.get(f"/api/chat/sessions/{sid}/stream?timeout=1")
        self.assertNotIn("before-cursor", response.text)
        self.assertIn("after-cursor", response.text)
        self.assertIn("id: " + sid + ":" + str(before["seq"] + 1), response.text)
        self.assertTrue(any(e.get("operation") == "chat.sse_delivery" and e.get("session_id") == sid for e in RING))


class Remote(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("remote")
        from backend.execution.code_projects import active_dir
        self.code = active_dir()
        (self.code / "train.py").write_text("print('training')", "utf-8")

    def test_bundle_approval_and_verified_completion(self):
        r = RC.create({"files": ["train.py"], "required_artifacts": ["metrics.json"]})
        rid = r["run_id"]
        with self.assertRaises(ValueError):
            RC.bundle(rid)
        RC.approve(rid)
        self.assertTrue(RC.bundle(rid).is_file())
        def collect(cmd, args, **kw):
            dest = Path(args["destination"])
            dest.mkdir(parents=True, exist_ok=True)
            f = dest / "metrics.json"
            f.write_text('{"loss": 0.1}')
            return {"status": "completed", "metrics": {"loss": 0.1}, "artifacts": [{"name": f.name, "sha256": RC.sha(f)}] if args["collect"] else []}
        with mock.patch("backend.execution.tracker.run_worker", side_effect=collect):
            self.assertEqual(RC.sync(rid, "task123456")["status"], "awaiting_collection")
            self.assertEqual(RC.sync(rid, collect=True)["status"], "completed")
        self.assertEqual(len(RC.get(rid)["approvals"]), 1)
        self.assertEqual(RC.get(rid)["evaluation"]["researcher_review"], "pending")

    def test_paths_secrets_and_tampering(self):
        for name in ("../secret.py", ".env", "checkpoint.pt"):
            with self.assertRaises(ValueError):
                RC.create({"files": [name], "entrypoint": name})
        (self.code / "train.py").write_text('api_key="secret12345"')
        with self.assertRaises(ValueError):
            RC.create({"files": ["train.py"]})
        (self.code / "train.py").write_text("print('hello')")
        r = RC.create({"files": ["train.py"]})
        (RC.folder(r["run_id"]) / "bundle.zip").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            RC.approve(r["run_id"])

    def test_corrupt_record_cannot_break_other_run_cards(self):
        good = RC.create({"files": ["train.py"]})
        bad = RC.create({"files": ["train.py"]})
        path = RC.folder(bad["run_id"]) / "run.json"
        path.write_text("{invalid")
        self.assertEqual([r["run_id"] for r in RC.list_runs()], [good["run_id"]])
        self.assertTrue(any(path.parent.glob("run.json.corrupt-*")))
        self.assertEqual(path.read_text(), "{invalid")

    def test_generated_launcher_executes_and_checks_code_before_training(self):
        (self.code / "train.py").write_text("import os\nfrom pathlib import Path\nPath(os.environ['RUN_DIR'], 'metrics.json').write_text('{\"loss\":0.1}')\n")
        r = RC.create({"files": ["train.py"], "compute_target": "docker", "required_artifacts": ["metrics.json"]})
        RC.approve(r["run_id"])
        unpack = config.data_dir() / "unpacked"
        with zipfile.ZipFile(RC.bundle(r["run_id"])) as z:
            z.extractall(unpack)
        (unpack / "clearml.py").write_text('''class Task:
    @classmethod
    def init(cls, **kwargs): return cls()
    def set_parameter(self, name, value): print(name, value)
    def get_logger(self): return self
    def report_single_value(self, **kwargs): pass
    def upload_artifact(self, **kwargs): print('UPLOAD', kwargs['name'])
    def mark_failed(self, **kwargs): print('FAILED')
    def close(self): pass
''')
        result = subprocess.run([sys.executable, str(unpack / "launch.py")], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("General/run_id " + r["run_id"], result.stdout)
        self.assertIn("UPLOAD metrics.json", result.stdout)
        (unpack / "code/train.py").write_text("raise SystemExit('should not execute')")
        result = subprocess.run([sys.executable, "-O", str(unpack / "launch.py")], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum mismatch", result.stderr)
