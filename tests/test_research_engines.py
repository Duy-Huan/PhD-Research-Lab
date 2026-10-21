"""Research-engine contract/recovery tests. Socket fixtures are not a scientific live run."""
import _env  # noqa: F401
import hashlib
import importlib.util
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from backend.core import config
from backend.research_engines import registry
from backend.research_engines.contracts import EngineTask, EngineFailure, EngineResult
from backend.research_engines.feynman import FeynmanEngine
from backend.research_engines import openscience as O

CAP = {"protocolVersion": "1.0", "idempotentPrompts": True, "runSnapshots": True}


class Peer:
    def __init__(self):
        self.state, self.prompts, self.created = "running", [], 0
        self.pending_requests, self.replies, self.cancelled = [], [], 0
        self.lose_admission, self.mode = False, "complete"

    def capabilities(self): return CAP

    def create_session(self, **kwargs):
        self.created += 1
        return {"id": "ses_test"}

    def prompt(self, session, message, **kwargs):
        self.prompts.append((session, message, kwargs))
        if self.lose_admission:
            self.lose_admission = False
            raise ConnectionError("admitted but response lost")
        return {"runID": "run_test"}

    def get_run(self, *args):
        return {"state": self.state, "resultMessageID": "msg_test", "error": {"message": "quota exceeded"}}

    def get_message(self, *args): return {"parts": [{"type": "text", "text": "Finding with evidence pending"}]}

    def snapshot(self, *args):
        return {"permissions": self.pending_requests, "questions": [], "latestSequence": 20}

    def events(self, *args, **kwargs):
        if self.mode == "gap":
            raise RuntimeError("cursor_expired")
        for n in (1, 1, 2):
            yield SimpleNamespace(sequence=n, run_id="run_test", type="message.part.updated", properties={
                "part": {"type": "text", "sessionID": "ses_test"}, "delta": str(n)})
        if self.mode == "complete":
            self.state = "completed"
            yield SimpleNamespace(sequence=3, run_id="run_test", type="runtime.completed", properties={})

    def cancel_run(self, *args):
        self.cancelled += 1
        return {"state": self.state}

    def reply_permission(self, *args):
        self.replies.append(args)
        return {"state": "applied"}


class EngineConformance:
    """Reusable minimum contract for every research-engine adapter; fixtures supply native transport."""
    def test_common_result_contract(self):
        result = self.engine.execute(self.task(), lambda e: None, lambda: False)
        self.assertEqual(result.engine, self.engine.descriptor.id)
        self.assertEqual(result.schema_version, "1.0")
        self.assertEqual(EngineResult.model_validate(result.model_dump()), result)
        self.assertTrue(result.text)
        self.assertIsInstance(result.artifact_refs, list)

    def test_common_cancel_before_dispatch(self):
        with self.assertRaises(EngineFailure) as failure:
            self.engine.execute(self.task(), lambda e: None, lambda: True)
        self.assertEqual(failure.exception.kind, "cancelled")


class AdapterTests(EngineConformance, unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("engine-" + self._testMethodName[:20])
        config.save_config({"openscience": {"enabled": True, "token": "deployment-test-token", "policy_confirmed": True}})
        self.peer, self.events = Peer(), []
        self.engine = O.OpenScienceEngine(client_factory=lambda *a, **kw: self.peer)
        self.policy_patch = mock.patch.object(O.OpenScienceEngine, "verify_policy")
        self.policy_patch.start()
        self.addCleanup(self.policy_patch.stop)
        self.collect = mock.patch.object(self.engine, "collect", return_value=[])
        self.collect.start()
        self.addCleanup(self.collect.stop)

    def task(self, **kw):
        return EngineTask(**({"operation_id": "RR-12345678:S1", "project_id": config.data_dir().name,
                            "workflow_id": "RR-12345678", "step_id": "S1", "question": "Find a gap",
                            "context": "current approved evidence", "output_dir": config.data_dir() / "output",
                            "approved": True} | kw))

    def execute(self, task=None, cancelled=lambda: False):
        return self.engine.execute(task or self.task(), self.events.append, cancelled)

    def test_stream_dedup_authoritative_result_and_same_operation(self):
        result = self.execute()
        self.assertIsInstance(result, EngineResult)
        self.assertEqual(result.native_run_id, "run_test")
        self.assertEqual([e.data["text"] for e in self.events if e.type == "text_delta"], ["1", "2"])
        self.assertEqual(result.provenance["scientific_review"], "pending")
        self.assertEqual(self.execute().text, result.text)
        self.assertEqual(len(self.peer.prompts), 1)
        self.assertFalse(self.peer.prompts[0][2]["delegation"])

    def test_ambiguous_admission_never_reprompts_automatically(self):
        self.peer.lose_admission = True
        with self.assertRaises(EngineFailure) as failure:
            self.execute()
        jid = failure.exception.job_id
        record = O.read_job(jid)
        self.assertEqual(record["state"], "admission_unconfirmed")
        with self.assertRaisesRegex(EngineFailure, "Admission is unresolved"):
            self.execute(self.task(attempt=2, context="changed context must not replace saved admission"))
        self.assertEqual(len(self.peer.prompts), 1)
        with mock.patch.object(O.OpenScienceEngine, "client", return_value=self.peer):
            O.recover_admission(jid)
        self.assertEqual(self.peer.prompts[0], self.peer.prompts[1])
        self.assertEqual(self.peer.created, 1)

    def test_pending_approval_is_fresh_and_denied_tools_cannot_be_granted(self):
        self.peer.pending_requests = [{"id": "per_test", "permission": "bash", "patterns": ["*"]}]
        with self.assertRaises(EngineFailure) as failure:
            self.execute()
        self.assertEqual(failure.exception.kind, "decision")
        jid = failure.exception.job_id
        with mock.patch.object(O.OpenScienceEngine, "client", return_value=self.peer):
            with self.assertRaisesRegex(EngineFailure, "exceeds"):
                O.decide(jid, "per_test", reply="once")
            O.decide(jid, "per_test", reply="reject")
            self.peer.pending_requests = []
            with self.assertRaisesRegex(EngineFailure, "no longer pending"):
                O.decide(jid, "per_test", reply="reject")
        self.assertEqual(len(self.peer.replies), 1)
        self.assertEqual(O.read_job(jid)["decisions"][0]["reply"], "reject")

    def test_eof_is_not_completion_and_recovery_observes_without_reprompt(self):
        self.peer.mode = "gap"
        with self.assertRaises(EngineFailure) as failure:
            self.execute()
        self.assertEqual(failure.exception.kind, "indeterminate")
        self.assertEqual(O.read_job(failure.exception.job_id)["cursor"], 20)
        self.peer.state = "completed"
        self.execute(self.task(attempt=2))
        self.assertEqual(len(self.peer.prompts), 1)

    def test_cancellation_receipt_remains_unconfirmed(self):
        calls = iter([False, True, True])
        with self.assertRaises(EngineFailure) as failure:
            self.execute(cancelled=lambda: next(calls, True))
        self.assertEqual(self.peer.cancelled, 1)
        self.assertEqual(failure.exception.kind, "cancelled")
        # The fixture might complete before cancellation; use a guaranteed running peer below.
        record = O.read_job(failure.exception.job_id)
        self.peer.state = "running"
        with mock.patch.object(O.OpenScienceEngine, "client", return_value=self.peer):
            receipt = O.cancel_job(record["id"])
        self.assertEqual(receipt["state"], "cancellation_unconfirmed")

    def test_unapproved_outside_project_and_cancelled_preflight_submit_nothing(self):
        for task, cancel in ((self.task(approved=False), lambda: False),
                             (self.task(output_dir=config.GLOBAL_DIR.parent), lambda: False),
                             (self.task(), lambda: True)):
            with self.assertRaises(EngineFailure):
                self.execute(task, cancel)
        self.assertEqual(self.peer.created, 0)

    def test_native_pending_job_blocks_second_admission(self):
        self.peer.mode = "gap"
        with self.assertRaises(EngineFailure):
            self.execute()
        with self.assertRaisesRegex(EngineFailure, "Another native run"):
            self.execute(self.task(operation_id="RR-87654321:S1"))
        self.assertEqual(len(self.peer.prompts), 1)

    def test_quota_receipt_not_auto_retried_and_explicit_retry_is_new_attempt(self):
        self.peer.state = "failed"
        with self.assertRaises(EngineFailure) as failure:
            self.execute()
        self.assertEqual(failure.exception.kind, "quota")
        self.peer.state = "completed"
        self.execute(self.task(attempt=2))
        self.assertNotEqual(self.peer.prompts[0][2]["request_id"], self.peer.prompts[1][2]["request_id"])

    def test_context_snapshot_and_project_scope(self):
        self.execute(self.task(context="access_token=secret-value-test-123456"))
        record = O.read_job(self.events[0].data["job_id"])
        self.assertNotIn("secret-value-test-123456", record["message"])
        with self.assertRaisesRegex(EngineFailure, "Task input changed"):
            self.execute(self.task(question="silently changed question"))
        _env.fresh_project("different-project")
        with self.assertRaises(FileNotFoundError):
            O.read_job(record["id"])

    def test_disabled_commands_refuse_approval(self):
        self.execute()
        config.save_config({"openscience": {"enabled": False}})
        with self.assertRaisesRegex(EngineFailure, "Enable and configure"):
            O.decide(self.events[0].data["job_id"], "per_test", reply="once")

    def test_engine_switch_requires_terminal_receipt(self):
        self.peer.mode = "gap"
        with self.assertRaises(EngineFailure) as failure:
            self.execute()
        jid = failure.exception.job_id
        with mock.patch.object(O.OpenScienceEngine, "client", return_value=self.peer):
            with self.assertRaisesRegex(EngineFailure, "Cancel and settle"):
                O.require_settled(jid)
            self.peer.state = "cancelled"
            O.require_settled(jid)
        self.assertEqual(O.read_job(jid)["state"], "cancelled")

    def test_project_switch_does_not_redirect_old_journal_writes(self):
        self.execute()
        jid = self.events[0].data["job_id"]
        original_path, record = O.job_path(jid), O.read_job(jid)
        _env.fresh_project("switch-during-observation")
        record["state"] = "retained-in-original-project"
        O.save_job(record)
        self.assertFalse(O.job_path(jid).exists())
        self.assertEqual(json.loads(original_path.read_text("utf-8"))["state"], record["state"])

    def test_idle_socket_reconnects_observation_without_skipping_cursor(self):
        native_events = self.peer.events
        cursors = []
        def stream(*args, **kwargs):
            cursors.append(kwargs["after_sequence"])
            if len(cursors) == 1:
                raise ConnectionError("idle socket")
            yield from native_events(*args, **kwargs)
        self.peer.events = stream
        self.execute()
        self.assertEqual(cursors, [0, 0])
        self.assertEqual(len(self.peer.prompts), 1)

    def test_deployment_credential_split_across_events_is_not_exposed(self):
        def stream(*a, **kw):
            for n, delta in enumerate(("prefix deployment-test-", "token suffix"), 1):
                yield SimpleNamespace(sequence=n, run_id="run_test", type="message.part.updated", properties={
                    "part": {"type": "text", "sessionID": "ses_test"}, "delta": delta})
            self.peer.state = "completed"
            yield SimpleNamespace(sequence=3, run_id="run_test", type="runtime.completed", properties={})
        self.peer.events = stream
        self.execute()
        text = ''.join(e.data["text"] for e in self.events if e.type == "text_delta")
        self.assertEqual(text, "prefix [REDACTED] suffix")

    def test_deadline_requests_cancel_instead_of_restarting(self):
        def slow_events(*a, **kw):
            time.sleep(0.03)
            return
            yield
        self.peer.events = slow_events
        with self.assertRaises(EngineFailure) as failure:
            self.execute(self.task(time_limit_s=0.01))
        self.assertEqual(failure.exception.kind, "timeout")
        self.assertEqual(self.peer.cancelled, 1)
        self.assertEqual(len(self.peer.prompts), 1)

    def test_model_and_execution_preflight_and_duplicate_observers(self):
        config.save_config({"openscience": {"model_provider": "native"}})
        with self.assertRaisesRegex(EngineFailure, "both the native model"):
            self.execute()
        config.save_config({"openscience": {"model_provider": ""}})
        with self.assertRaisesRegex(EngineFailure, "Enable reviewed tool"):
            self.execute(self.task(capability="prototype"))
        jid = "ej-" + hashlib.sha256(self.task().operation_id.encode()).hexdigest()[:20]
        lease = threading.Lock()
        with mock.patch.dict(O._locks, {str(O.job_path(jid)): lease}):
            lease.acquire()
            try:
                with self.assertRaisesRegex(EngineFailure, "already has an observer"):
                    self.execute()
            finally:
                lease.release()
        self.assertEqual(self.peer.created, 0)

    def test_runtime_health_protocol_and_missing_sdk_are_explicit(self):
        self.assertTrue(self.engine.health()["ready"])
        self.peer.capabilities = lambda: {"protocolVersion": "2"}
        self.assertFalse(self.engine.health()["ready"])
        config.save_config({"openscience": {"policy_confirmed": False}})
        self.assertEqual(self.engine.health()["state"], "NOT_CONFIGURED")
        with mock.patch("urllib.request.getproxies", return_value={}), \
             mock.patch.object(O.importlib, "import_module", side_effect=ImportError("missing source client")):
            with self.assertRaisesRegex(EngineFailure, "Install the pinned"):
                O.OpenScienceEngine().client(O.Settings())
        with mock.patch("urllib.request.getproxies", return_value={"http": "http://proxy.invalid"}), \
             mock.patch("urllib.request.proxy_bypass", return_value=False):
            with self.assertRaisesRegex(EngineFailure, "NO_PROXY"):
                self.engine.client(O.Settings())
        with self.assertRaises(ValidationError): O.Settings(token="bad\ntoken")
        with self.assertRaises(ValidationError): O.Settings(qualified_tasks=["unverified-magic"])

    def test_admission_auth_errors_are_normalized_without_reprompt(self):
        error = RuntimeError("deployment auth rejected")
        error.status = 401
        with mock.patch.object(self.peer, "create_session", side_effect=error):
            with self.assertRaises(EngineFailure) as failure:
                self.execute()
        self.assertEqual(failure.exception.kind, "auth")
        self.assertEqual(self.peer.prompts, [])

    def test_live_job_inspection_and_questions_do_not_reuse_historical_decisions(self):
        self.peer.pending_requests = [{"id": "per", "permission": "python"}]
        with self.assertRaises(EngineFailure) as failure:
            self.execute()
        jid = failure.exception.job_id
        with mock.patch.object(O.OpenScienceEngine, "client", return_value=self.peer):
            inspected = O.inspect_job(jid)
            self.assertEqual(inspected["pending"][0]["id"], "per")
            self.assertNotIn("message", inspected["job"])
            config.save_config({"openscience": {"allow_execution": True}})
            O.decide(jid, "per", reply="once")
            with mock.patch.object(self.peer, "snapshot", return_value={"permissions": [], "questions": [{"id": "q"}]}), \
                 mock.patch.object(self.peer, "reply_question", create=True, return_value={"status": "resolved"}) as answer, \
                 mock.patch.object(self.peer, "reject_question", create=True, return_value={"status": "resolved"}) as reject:
                O.decide(jid, "q", answers=[["baseline"]])
                answer.assert_called_once_with("ses_test", "q", [["baseline"]])
                O.decide(jid, "q")
                reject.assert_called_once_with("ses_test", "q")
            with mock.patch.object(self.peer, "snapshot", side_effect=ConnectionError("offline")):
                inspected = O.inspect_job(jid)
            self.assertEqual(inspected["pending"], [])
            self.assertIn("offline", inspected["observation_error"])

    def test_effective_metadata_response_has_a_byte_limit(self):
        with httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b'x' * (4 * 1024 * 1024 + 1)))) as http:
            with self.assertRaisesRegex(EngineFailure, "response limit"):
                self.engine.public_json(http, "/config/")


class Contracts(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)

    def test_contract_versions_loopback_and_optional_registration(self):
        with self.assertRaises(ValidationError): EngineResult(schema_version="2", engine="x", text="x")
        for url in ("https://example.com", "http://127.0.0.1/path", "http://u:p@127.0.0.1", "http://127.0.0.1:0"):
            with self.assertRaises(ValidationError): O.Settings(base_url=url)
        for name in registry.FACTORIES:
            engine = registry.get(name)
            self.assertEqual(engine.descriptor.schema_version, "1.0")
            self.assertEqual(engine.descriptor.skills_owner, "engine")
            self.assertTrue(callable(engine.execute))
        config.save_config({"openscience": {"enabled": False}})
        self.assertFalse(registry.get("openscience").health()["ready"])

    def test_auto_needs_qualified_model_and_identity_changes_reset_qualification(self):
        config.save_config({"research_providers": {"engine_priority": ["openscience", "feynman"]},
                            "openscience": {"model_provider": "test", "model_id": "strong"}})
        with mock.patch.object(O.OpenScienceEngine, "health", return_value={"ready": True}), \
             mock.patch.object(FeynmanEngine, "health", return_value={"ready": True}):
            self.assertEqual(registry.plan("auto", "review"), ["feynman"])
            config.save_config({"openscience": {"qualified_tasks": ["review"]}})
            self.assertEqual(registry.plan("auto", "review"), ["openscience"])
            config.save_config({"openscience": {"model_id": "different", "qualified_tasks": ["review"]}})
            self.assertEqual(config.load_config()["openscience"]["qualified_tasks"], [])
            self.assertEqual(registry.plan("auto", "review"), ["feynman"])
        self.assertEqual(registry.plan("collaborative", "analysis"), ["openscience", "feynman"])
        with self.assertRaises(EngineFailure): registry.plan("infinite", "review")

    def test_feynman_uses_existing_dispatch_and_contract(self):
        task = EngineTask(operation_id="RR-12345678:S1", project_id="p", workflow_id="RR-12345678", step_id="S1",
                          question="Find gaps", output_dir=config.data_dir() / "feynman")
        with mock.patch("backend.providers.research.run_feynman", return_value={"text": "evidence", "files": []}) as native:
            result = FeynmanEngine().execute(task, lambda e: None, lambda: False)
            self.assertEqual(result.engine, "feynman")
            native.assert_called_once()
            with self.assertRaises(EngineFailure):
                FeynmanEngine().execute(task.model_copy(update={"capability": "prototype"}), lambda e: None, lambda: False)
        self.assertEqual(native.call_count, 1)


class FeynmanConformance(EngineConformance, unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("feynman-contract")
        self.engine = FeynmanEngine()
        patch = mock.patch("backend.providers.research.run_feynman", return_value={"text": "Native fixture result", "files": []})
        patch.start()
        self.addCleanup(patch.stop)

    def task(self):
        return EngineTask(operation_id="RR-12345678:S1", project_id=config.data_dir().name, workflow_id="RR-12345678",
                          step_id="S1", question="Find a gap", output_dir=config.data_dir() / "out", approved=True)


class Artifacts(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("native-artifacts")

    def collect(self, *, corrupt=False, filename="../../metrics.json", size=7):
        blob = b'{"x":1}'
        digest = hashlib.sha256(blob).hexdigest()
        def handle(request):
            if request.url.path.endswith("/raw"):
                return httpx.Response(200, content=b"wrong" if corrupt else blob)
            return httpx.Response(200, json=[{"id": "art_test", "current": {"id": "ver_test", "filename": filename,
                "sessionID": "ses_test", "size": size, "sha256": digest, "sourcePath": "C:/private/secret"}}])
        engine = O.OpenScienceEngine()
        record = {"id": "ej-" + "1" * 20, "workspace": str(config.data_dir()), "output_dir": str(config.data_dir() / "out"), "session_id": "ses_test"}
        with mock.patch.object(engine, "http", side_effect=lambda *a: httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(handle))):
            return engine.collect(O.Settings(), record, "msg_test")

    def test_checksum_and_filename_containment(self):
        refs = self.collect()
        from pathlib import Path
        target = Path(refs[0]["path"])
        self.assertTrue(target.resolve().is_relative_to((config.data_dir() / "out").resolve()))
        self.assertEqual(target.read_bytes(), b'{"x":1}')
        self.assertEqual(refs[0]["scientific_review"], "pending")

    def test_corrupt_or_misreported_size_is_refused_and_partial_removed(self):
        for kwargs in ({"corrupt": True}, {"size": 9000000}):
            with self.assertRaisesRegex(EngineFailure, "checksum/size"):
                self.collect(**kwargs)
        self.assertEqual(list((config.data_dir() / "out").glob("*.partial")), [])

    def test_effective_policy_rejects_native_worker_and_global_grants(self):
        engine = O.OpenScienceEngine()
        def handle(request):
            return httpx.Response(200, json={"permission": O.policy(False) | {"task": "allow"}})
        with mock.patch.object(engine, "http", side_effect=lambda *a: httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(handle))):
            with self.assertRaisesRegex(EngineFailure, "permissions differ"):
                engine.verify_policy(O.Settings(), str(config.data_dir()))

    def test_artifact_byte_budget_is_enforced_before_publish(self):
        blob = b'x' * (1024 * 1024 + 1)
        def handle(request):
            if request.url.path.endswith("/raw"):
                return httpx.Response(200, content=blob)
            return httpx.Response(200, json=[{"id": "art_big", "current": {"id": "ver_big", "filename": "big.bin",
                "sessionID": "ses_test", "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}}])
        engine = O.OpenScienceEngine()
        record = {"id": "ej-" + "1" * 20, "workspace": str(config.data_dir()), "output_dir": str(config.data_dir() / "out"), "session_id": "ses_test"}
        with mock.patch.object(engine, "http", side_effect=lambda *a: httpx.Client(base_url="http://127.0.0.1", transport=httpx.MockTransport(handle))):
            with self.assertRaisesRegex(EngineFailure, "bytes exceed"):
                engine.collect(O.Settings(max_artifact_mb=1), record, "msg_test")
        self.assertEqual(list((config.data_dir() / "out").iterdir()), [])


@unittest.skipUnless(importlib.util.find_spec("openscience"), "Optional official SDK not installed; run with audited SDK source on PYTHONPATH")
class OfficialSDKSocket(unittest.TestCase):
    def test_real_sdk_through_adapter_with_bounded_socket_fixture(self):
        _env.isolate_config(self)
        _env.fresh_project("official-sdk-socket")
        calls, terminal = [], threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def send(self, body, content_type="application/json", status=200):
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            def do_GET(self):
                path = urlsplit(self.path).path
                if path == "/runtime/capabilities": self.send(CAP)
                elif path == "/config/": self.send({"permission": O.policy(False)})
                elif path == "/runtime/run": self.send({"state": "completed" if terminal.is_set() else "running", "resultMessageID": "msg_socket"})
                elif path == "/runtime/snapshot": self.send({"permissions": [], "questions": [], "latestSequence": 0})
                elif path == "/runtime/events":
                    event = {"sequence": 1, "type": "runtime.completed", "sessionID": "ses_socket", "runID": "run_socket", "time": 1, "properties": {}}
                    terminal.set()
                    self.send(("id: 1\nevent: runtime.completed\ndata: " + json.dumps(event) + "\n\n").encode(), "text/event-stream")
                elif path.startswith("/session/"): self.send({"parts": [{"type": "text", "text": "Fixture result"}]})
                elif path == "/file/artifact-store": self.send([])
                else: self.send({"error": path}, status=404)
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, body))
                if self.path.startswith("/session"): self.send({"id": "ses_socket"})
                else: self.send({"runID": "run_socket", "acceptedAt": 1}, status=202)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config.save_config({"openscience": {"enabled": True, "base_url": f"http://127.0.0.1:{server.server_port}",
                                               "token": "test-deployment-token", "policy_confirmed": True}})
            task = EngineTask(operation_id="RR-12345678:S1", project_id="p", workflow_id="RR-12345678", step_id="S1",
                              question="Socket test", output_dir=config.data_dir() / "out", approved=True)
            result = O.OpenScienceEngine().execute(task, lambda event: None, lambda: False)
            self.assertEqual(result.text, "Fixture result")
            self.assertEqual(len([c for c in calls if c[0].startswith("/runtime/prompt")]), 1)
            self.assertEqual(calls[-1][1]["delegation"], False)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


from test_runs import RunsBase
from backend.agent import launch, runs, sessions


class RunIntegration(RunsBase):
    def test_bounded_collaboration_approval_and_resume_preserve_primary(self):
        config.save_config({"research_providers": {"engine_mode": "collaborative"}, "openscience": {"enabled": True}})
        session = sessions.create("Research integration")
        with mock.patch("backend.providers.research.pick", side_effect=lambda pid: (pid, "")), \
             mock.patch("backend.providers.research.run_feynman", return_value={"text": "Primary finding", "files": []}) as native, \
             mock.patch.object(O.OpenScienceEngine, "execute", side_effect=[EngineFailure("quota exceeded", "quota"),
                  EngineResult(engine="openscience", text="Critical review", native_run_id="run_review", provenance={"scientific_review": "pending"})]) as science:
            created = launch.from_skill("lit", "Review supplied papers", session)
            self.assertEqual(created["status"], "APPROVAL_PENDING")
            self.assertEqual([s["kind"] for s in created["steps"]], ["research", "review", "verify_sources", "report"])
            self.assertEqual(native.call_count + science.call_count, 0)
            runs.approve(created["id"])
            paused = self.wait(created["id"])
            self.assertEqual(paused["status"], "NEEDS_USER_ACTION")
            self.assertEqual(paused["steps"][0]["status"], "done")
            self.assertEqual(paused["steps"][0]["result"]["text"], "Primary finding")
            runs.resume(created["id"], False)
            finished = self.wait(created["id"])
        self.assertEqual(finished["status"], "COMPLETED")
        self.assertEqual(native.call_count, 1)
        self.assertEqual(science.call_count, 2)
        output = runs.out_dir(created["id"])
        self.assertEqual((output / "research_report.md").read_text("utf-8"), "Primary finding")
        self.assertEqual((output / "review_report.md").read_text("utf-8"), "Critical review")
        evidence = json.loads((output / "engine-evidence-S2.json").read_text("utf-8"))
        self.assertIsNone(evidence["clearml_task_id"])
        self.assertEqual(evidence["scientific_review"], "pending")
        proposals = sessions.get(session["id"])["approvals"]
        self.assertTrue(any(p["name"] == "pin_result" and p["status"] == "pending" for p in proposals))

    def test_explicit_science_mode_needs_approval_even_when_disabled(self):
        config.save_config({"openscience": {"enabled": False}, "research_providers": {"engine_mode": "feynman"}})
        created = launch.from_skill("science", "Analyze an approved dataset")
        self.assertEqual(created["status"], "APPROVAL_PENDING")
        self.assertEqual(created["steps"][0]["provider"], "openscience")
        runs.cancel(created["id"])


class EngineApi(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("engine-api")
        from fastapi.testclient import TestClient
        from backend.app import app
        self.client = TestClient(app)

    def test_inventory_separate_from_llm_and_invalid_decision_rejected(self):
        config.save_config({"openscience": {"enabled": False, "token": "engine-api-test-token"}})
        with mock.patch.object(FeynmanEngine, "health", return_value={"ready": False, "state": "DISABLED"}):
            result = self.client.get("/api/research-engines")
        self.assertEqual(result.status_code, 200)
        native = next(e for e in result.json()["engines"] if e["descriptor"]["id"] == "openscience")
        self.assertEqual(native["health"]["state"], "DISABLED")
        self.assertNotIn("openscience", config.PROVIDERS)
        response = self.client.post("/api/research-engines/jobs/ej-" + "1" * 20 + "/decisions",
                                    json={"request_id": "p", "reply": "always"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/api/research-engines/jobs/invalid-job").status_code, 400)
        from backend.api.research_engines import public
        self.assertEqual(public({"metadata": "engine-api-test-token"}), {"metadata": "[REDACTED]"})
