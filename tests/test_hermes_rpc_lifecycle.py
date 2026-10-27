"""FQC-COVERAGE-662: Hermes provider RPC, health, lifecycle (start/stop/restart history), models and the connector.

RPC runs against a real loopback HTTP server that plays the adapter; Docker is replaced by a recorder and container
inspection by fixtures, so ownership, loopback binding and failure mapping are exercised without a daemon or vendor.
"""
import io
import json
import threading
import time
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import _env
from backend.core import config
from backend.providers import hermes
from backend.providers.cli import ProviderError

PROXY = "a" * 64
RUNTIME = "b" * 64


class Adapter(BaseHTTPRequestHandler):
    routes: dict = {}
    seen: list = []

    def _reply(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        Adapter.seen.append((self.command, self.path, body, self.headers.get("Authorization")))
        status, payload = Adapter.routes.get(self.path, (404, {"state": "UNAVAILABLE"}))
        if callable(payload):
            payload = payload()
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = _reply

    def log_message(self, *args):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"hermes-rpc-{self._testMethodName[:28]}")
        self.addCleanup(patch.stopall)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Adapter)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        Adapter.routes, Adapter.seen = {}, []
        self.profile = hermes.runtime_profile()
        self.owner = hermes._owner(self.profile)
        hermes._write(self.profile, {"owner": self.owner, "adapter_sha256": hermes.adapter_digest(), "proxy": PROXY,
                                     "runtime": RUNTIME, "image": "sha256:img", "rpc_token": "tok"})
        self.inspect = patch.object(hermes, "_inspect", side_effect=self.fake_inspect)
        self.inspect.start()
        self.binding = [{"HostIp": "127.0.0.1", "HostPort": str(self.server.server_address[1])}]

    def fake_inspect(self, container, owner, role, image=None):
        return {"NetworkSettings": {"Ports": {"8080/tcp": self.binding}}}


class Rpc(Base):
    def test_rpc_calls_the_loopback_adapter_with_the_project_token(self):
        Adapter.routes["/v1/health"] = (200, {"ok": True})
        self.assertEqual(hermes.rpc("/v1/health", profile=self.profile), {"ok": True})
        self.assertEqual(Adapter.seen[-1][3], "Bearer tok")
        Adapter.routes["/v1/jobs"] = (200, {"status": "running"})
        hermes.rpc("/v1/jobs", {"id": "x"}, profile=self.profile)
        self.assertEqual(Adapter.seen[-1][:3], ("POST", "/v1/jobs", {"id": "x"}))

    def test_rpc_refuses_unsafe_paths_plans_and_bindings(self):
        with self.assertRaisesRegex(ProviderError, "Unsupported Hermes RPC path"):
            hermes.rpc("/v1/admin", profile=self.profile)
        self.binding = [{"HostIp": "0.0.0.0", "HostPort": "1"}]
        with self.assertRaisesRegex(ProviderError, "loopback"):
            hermes.rpc("/v1/health", profile=self.profile)
        hermes._write(self.profile, {"owner": "someone-else"})
        with self.assertRaisesRegex(ProviderError, "not prepared"):
            hermes.rpc("/v1/health", profile=self.profile)

    def test_rpc_errors_are_mapped_without_replay(self):
        Adapter.routes["/v1/models"] = (401, {"state": "AUTH_REQUIRED", "error_code": "nous.expired"})
        with self.assertRaises(ProviderError) as caught:
            hermes.rpc("/v1/models", profile=self.profile)
        self.assertEqual((caught.exception.state, str(caught.exception).endswith("[nous.expired]")), ("AUTH_EXPIRED", True))
        Adapter.routes["/v1/models"] = (500, {"state": "BROKEN", "error_code": "bad code!"})
        with self.assertRaisesRegex(ProviderError, "rejected the RPC request; no automatic replay occurred.$"):
            hermes.rpc("/v1/models", profile=self.profile)
        Adapter.routes["/v1/models"] = (500, b"not json")
        with self.assertRaisesRegex(ProviderError, "RPC failed"):
            hermes.rpc("/v1/models", profile=self.profile)
        Adapter.routes["/v1/models"] = (200, [1, 2])
        with self.assertRaisesRegex(ProviderError, "Invalid Hermes RPC response"):
            hermes.rpc("/v1/models", profile=self.profile)
        self.server.shutdown()
        self.server.server_close()
        with self.assertRaisesRegex(ProviderError, "RPC unavailable"):
            hermes.rpc("/v1/health", profile=self.profile, timeout=2)

    def test_status_reports_ready_incompatible_or_unavailable(self):
        Adapter.routes["/v1/health"] = (200, {"protocol": hermes.PROTOCOL, "upstream": hermes.UPSTREAM, "runtime": "hermes",
                                              "persistence": "durable"})
        ready = hermes.status(self.profile)
        self.assertEqual((ready["state"], ready["ready"], ready["persistence"]), ("READY", True, "durable"))
        Adapter.routes["/v1/health"] = (200, {"protocol": -1})
        self.assertEqual(hermes.status(self.profile)["state"], "INCOMPATIBLE")
        Adapter.routes["/v1/health"] = (503, {"state": "DOWN"})
        self.assertEqual(hermes.status(self.profile)["state"], "UNAVAILABLE")

    def test_models_keep_only_free_entries_from_the_live_catalog(self):
        Adapter.routes["/v1/models"] = (200, {"origin": "live-account-catalog", "provider": "nous",
                                              "models": [{"id": "free-1", "free": True}, {"id": "paid", "free": False}, "x"]})
        out = hermes.refresh_models(self.profile)
        self.assertEqual((out["models"], out["free_only"]), (["free-1"], True))
        self.assertEqual(hermes._read(self.profile)["catalog"]["provider"], "nous")
        Adapter.routes["/v1/models"] = (200, {"origin": "cache", "provider": "nous"})
        with self.assertRaisesRegex(ProviderError, "Unverified"):
            hermes.refresh_models(self.profile)


class Lifecycle(Base):
    def test_docker_failures_and_container_identity_checks(self):
        with patch.object(hermes.subprocess, "run", return_value=type("R", (), {"returncode": 1, "stdout": ""})()):
            with self.assertRaisesRegex(ProviderError, "Docker operation failed"):
                hermes.docker("ps")
        with patch.object(hermes.subprocess, "run", return_value=type("R", (), {"returncode": 0, "stdout": " ok \n"})()):
            self.assertEqual(hermes.docker("ps"), "ok")
        self.inspect.stop()
        with self.assertRaisesRegex(ProviderError, "Invalid runtime container identity"):
            hermes._inspect("short", self.owner, "proxy")
        listing = [{"Config": {"Labels": {"phdlab.hermes.owner": self.owner, "phdlab.hermes.role": "proxy"}}, "Image": "sha256:img"}]
        with patch.object(hermes, "docker", return_value=json.dumps(listing)):
            self.assertEqual(hermes._inspect(PROXY, self.owner, "proxy", "sha256:img")["Image"], "sha256:img")
            with self.assertRaisesRegex(ProviderError, "ownership mismatch"):
                hermes._inspect(PROXY, self.owner, "runtime")
            with self.assertRaisesRegex(ProviderError, "image identity changed"):
                hermes._inspect(PROXY, self.owner, "proxy", "sha256:other")
        with self.assertRaisesRegex(ProviderError, "Unsupported Hermes permission profile"):
            hermes.folder("root")

    def image(self, **labels):
        base = {"phdlab.runtime": "hermes", "phdlab.rpc.version": str(hermes.PROTOCOL), "phdlab.adapter.sha256": hermes.adapter_digest()}
        return json.dumps([{"Id": "sha256:img", "Config": {"Labels": {**base, **labels}}}])

    def test_start_requires_the_reviewed_image_and_keeps_restart_history(self):
        calls = []

        def docker(*args, timeout=20):
            calls.append(args)
            return self.image(**{"phdlab.rpc.version": "0"}) if args[:2] == ("image", "inspect") else ""
        with patch.object(hermes, "docker", docker), patch.object(hermes, "status", return_value={"ready": False}):
            with self.assertRaisesRegex(ProviderError, "Rebuild the pinned Hermes adapter image"):
                hermes.start(self.profile)

        def docker_ok(*args, timeout=20):
            calls.append(args)
            if args[:2] == ("image", "inspect"):
                return self.image()
            return "c" * 64 if args[0] == "run" else ""
        with patch.object(hermes, "docker", docker_ok), patch.object(hermes, "status", return_value={"ready": False}), \
                patch.object(hermes.time, "sleep"):
            with self.assertRaisesRegex(ProviderError, "did not become compatible/healthy"):
                hermes.start(self.profile)
        self.assertIn(("rm", "-f", RUNTIME), calls)
        self.assertIn(("rm", "-f", PROXY), calls)
        history = list((hermes.folder(self.profile) / "lifecycle-history").glob("*.json"))
        self.assertTrue(history)
        self.assertNotIn("rpc_token", json.loads(history[0].read_text("utf-8")), "tokens never enter the history")
        self.assertTrue(hermes._read(self.profile)["start_failed"], "launch identities are retained for diagnosis")

    def test_start_returns_a_ready_runtime_and_stop_keeps_data(self):
        with patch.object(hermes, "status", return_value={"ready": True, "state": "READY"}):
            self.assertEqual(hermes.start(self.profile)["state"], "READY")
        calls = []
        with patch.object(hermes, "docker", lambda *a, timeout=20: calls.append(a) or ""):
            out = hermes.stop(self.profile)
        self.assertEqual((out["state"], out["data_preserved"]), ("STOPPED", True))
        self.assertEqual([c[-1] for c in calls], [RUNTIME, PROXY])


class Connector(Base):
    def setUp(self):
        super().setUp()
        config.save_config({"hermes": {"enabled": True, "model": "nous/free"}})
        self.connector = hermes.HermesConnector()
        patch.object(hermes.time, "sleep").start()

    def run_job(self, context=None, message="hi"):
        return list(self.connector.stream_message(message, {"cwd": "/w", **(context or {})}))

    def test_capabilities_health_and_sign_in(self):
        self.assertTrue(self.connector.capabilities()["mcp_client"])
        with patch.object(hermes, "status", return_value={"ready": False, "detail": "down"}):
            self.assertEqual(self.connector.health()["state"], "UNAVAILABLE")
        with patch.object(hermes, "start"), patch("backend.providers.native._open_console", return_value={"launched": True}), \
                patch.object(hermes.shutil, "which", return_value="docker"):
            out = self.connector.connect(launch=True)
        self.assertEqual(out["command"][:4], ["docker", "exec", "-it", RUNTIME])
        self.assertTrue(out["launched"])

    def test_job_runs_to_completion_with_registry_tools(self):
        states = iter([{"status": "running"}, {"status": "completed", "answer": "done", "usage": {"t": 1}}])
        Adapter.routes["/v1/jobs"] = (200, {"status": "running"})
        jid = "c" * 32
        Adapter.routes[f"/v1/jobs/{jid}"] = (200, lambda: next(states))
        config.save_config({"hermes": {"max_tokens": 1000}})
        events = self.run_job({"runtime_job_id": jid, "mcp_url": "http://127.0.0.1:9/mcp", "mcp_token": "m", "mcp_tools": ["x"]})
        kinds = [e["type"] if isinstance(e, dict) and "type" in e else e[0] if isinstance(e, tuple) else getattr(e, "type", "") for e in events]
        self.assertTrue(kinds)
        job = Adapter.seen[0][2]
        self.assertEqual(job["max_tokens"], 1000)
        self.assertNotIn("deadline_s", job, "no owner limit means no budget is sent")
        self.assertEqual(job["mcp"]["tools"], sorted({"x", *hermes.REGISTRY_TOOLS}))
        self.assertIn("done", json.dumps(events, default=str))

    def test_job_refusals_failures_cancellation_and_liveness(self):
        with self.assertRaisesRegex(ProviderError, "Hermes tools must use the scoped local"):
            self.run_job({"mcp_url": "https://evil/mcp", "mcp_token": "m"})
        Adapter.routes["/v1/jobs"] = (200, {"status": "failed", "error": "model refused"})
        with self.assertRaisesRegex(ProviderError, "model refused"):
            self.run_job()
        jid = "d" * 32
        Adapter.routes["/v1/jobs"] = (200, {"status": "running"})
        Adapter.routes[f"/v1/jobs/{jid}/cancel"] = (200, {"status": "cancelled"})
        cancel = threading.Event()
        cancel.set()
        events = self.run_job({"runtime_job_id": jid, "_cancel": cancel, "request_id": "req-1"})
        self.assertIn("request_cancelled", json.dumps(events, default=str))
        self.assertTrue(self.connector.cancel("req-1")["cancelled"])
        self.assertFalse(self.connector.cancel("unknown")["cancelled"])
        Adapter.routes[f"/v1/jobs/{jid}"] = (503, {"state": "DOWN"})
        clock = iter([0.0, 0.0, 500.0, 500.0, 500.0])
        with patch.object(hermes.time, "monotonic", lambda: next(clock)), \
                self.assertRaisesRegex(ProviderError, "not responding"):
            self.run_job({"runtime_job_id": jid})
        config.save_config({"hermes": {"model": ""}})
        with self.assertRaisesRegex(ProviderError, "free Nous model"):
            self.run_job()
        config.save_config({"hermes": {"enabled": False}})
        with self.assertRaisesRegex(ProviderError, "disabled"):
            self.run_job()

    def test_cancel_refuses_a_mismatched_request_record(self):
        Adapter.routes["/v1/jobs"] = (200, {"status": "completed", "answer": "ok"})
        self.run_job({"request_id": "req-2", "runtime_job_id": "e" * 32})
        record = next((hermes.folder(self.profile) / "requests").glob("request-*.json"))
        record.write_text(json.dumps({"job": "e" * 32, "profile": "other", "request_id": "req-2"}), "utf-8")
        with self.assertRaisesRegex(ProviderError, "identity mismatch"):
            self.connector.cancel("req-2")


if __name__ == "__main__":
    unittest.main()
