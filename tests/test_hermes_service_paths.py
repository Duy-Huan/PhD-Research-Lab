"""FQC-COVERAGE-662: Hermes in-container adapter paths not reached by the job-protocol tests.

GET routes and error mapping over a real HTTP server; the scoped MCP bridge and tool registration against a real
loopback MCP fixture; the egress relay over real socket pairs; worker supervision and startup recovery with the
process and Linux-only primitives replaced. No model, Nous account or Docker daemon is used.
"""
import hashlib
import http.client
import http.server
import json
import socket
import subprocess
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch

import _env
import importlib.util
from backend.core import config

spec = importlib.util.spec_from_file_location("phdlab_hermes_service_paths", _env.ROOT / "tools/hermes_runtime/service.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)
JID = "a" * 32


class McpFixture(http.server.BaseHTTPRequestHandler):
    reply = {"result": {}}
    status = 200
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        McpFixture.seen.append((body["method"], body["params"], self.headers.get("X-Phdlab-Job")))
        raw = json.dumps(McpFixture.reply(body) if callable(McpFixture.reply) else McpFixture.reply).encode()
        self.send_response(McpFixture.status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"hermes-service-{self._testMethodName[:24]}")
        self.addCleanup(patch.stopall)
        patch.object(service, "STATE", config.data_dir() / "rpc-fixture").start()
        patch.dict(service.ACTIVE, {}, clear=True).start()

    def serve(self, handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address[1]


class Routes(Base):
    def setUp(self):
        super().setUp()
        self.port = self.serve(service.Handler)

    def get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_health_models_jobs_and_unknown_paths(self):
        status, health = self.get("/v1/health")
        self.assertEqual((status, health["protocol"], health["network"]), (200, service.PROTOCOL, "unrestricted-internet"))
        with patch.object(service, "catalog", return_value={"models": []}):
            self.assertEqual(self.get("/v1/models"), (200, {"models": []}))
        service.save(service.job_path(JID), {"id": JID, "status": "running", "prompt": "secret"})
        status, job = self.get(f"/v1/jobs/{JID}")
        self.assertEqual((status, job.get("prompt")), (200, None), "prompts never leave through RPC")
        self.assertEqual(self.get(f"/v1/jobs/{'b' * 32}")[0], 404)
        self.assertEqual(self.get("/v1/other")[0], 404)

    def test_catalog_failures_map_to_sign_in_or_unavailable(self):
        auth = type("NousAuthError", (Exception,), {"code": "nous_auth_required"})
        with patch.object(service, "catalog", side_effect=auth("expired")):
            status, body = self.get("/v1/models")
        self.assertEqual((status, body["state"], body["error_code"]), (503, "AUTH_REQUIRED", "nous_auth_required"))
        with patch.object(service, "catalog", side_effect=RuntimeError("https://secret-url key=abc")):
            status, body = self.get("/v1/models")
        self.assertEqual((status, body["state"], body["error_code"]), (503, "UNAVAILABLE", "RuntimeError"))
        self.assertNotIn("secret", json.dumps(body))
        self.assertEqual(service.error_code(type("E", (Exception,), {"code": "bad code!"})()), "E")

    def test_cancel_kills_the_active_worker_group(self):
        service.save(service.job_path(JID), {"id": JID, "status": "running"})
        process = Mock(pid=4242)
        process.poll.return_value = None
        service.ACTIVE[JID] = process
        killpg = patch.object(service.os, "killpg", create=True).start()
        patch("signal.SIGKILL", 9, create=True).start()
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/jobs/{JID}/cancel", data=b"{}")
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(json.load(response)["status"], "cancelled")
        self.assertEqual(killpg.call_args.args[0], 4242)
        self.assertEqual(service.read_job(JID)["status"], "cancelled")
        oversized = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/jobs", data=b"{}",
                                           headers={"Content-Length": "2000000"})
        with self.assertRaises((urllib.error.HTTPError, ConnectionError, OSError)):
            urllib.request.urlopen(oversized, timeout=5)


class ToolBridge(Base):
    def setUp(self):
        super().setUp()
        McpFixture.reply, McpFixture.status, McpFixture.seen = {"result": {}}, 200, []
        port = self.serve(McpFixture)
        real = http.client.HTTPConnection
        patch.object(http.client, "HTTPConnection", lambda host, _port, timeout=30: real(host, port, timeout=timeout)).start()
        self.job = {"id": JID, "tools": ["read_note"]}

    def test_mcp_calls_carry_the_job_identity_and_reject_errors(self):
        McpFixture.reply = {"result": {"ok": 1}}
        self.assertEqual(service.mcp(self.job, "tools/list", {}), {"ok": 1})
        self.assertEqual(McpFixture.seen[-1], ("tools/list", {}, JID))
        McpFixture.reply = {"error": {"code": -1}}
        with self.assertRaisesRegex(ValueError, "rejected the tool request"):
            service.mcp(self.job, "tools/list", {})
        McpFixture.status = 500
        with self.assertRaisesRegex(ValueError, "unavailable"):
            service.mcp(self.job, "tools/list", {})

    def test_only_granted_tools_are_registered_and_calls_go_through_the_bridge(self):
        def reply(body):
            if body["method"] == "tools/list":
                return {"result": {"tools": [{"name": "read_note", "description": "d", "inputSchema": {"type": "object"}},
                                             {"name": "delete_all"}]}}
            return {"result": {"content": "note"}}
        McpFixture.reply = reply
        registered = {}
        registry = types.SimpleNamespace(register=lambda **kw: registered.__setitem__(kw["name"], kw),
                                         get_tool_names_for_toolset=lambda name: sorted(registered))
        toolsets = types.SimpleNamespace(TOOLSETS={})
        modules = {"tools": types.ModuleType("tools"), "tools.registry": types.SimpleNamespace(registry=registry), "toolsets": toolsets}
        with patch.dict(sys.modules, modules):
            service.register_tools({"id": JID, "tools": []})
            self.assertEqual(registered, {}, "no grant means no PhD Lab toolset")
            service.register_tools(self.job)
        self.assertEqual(list(registered), ["phdlab_read_note"])
        self.assertEqual(toolsets.TOOLSETS["phdlab"]["tools"], ["phdlab_read_note"])
        out = registered["phdlab_read_note"]["handler"]({"id": 1})
        self.assertEqual(json.loads(out), {"content": "note"})
        self.assertEqual(McpFixture.seen[-1][:2], ("tools/call", {"name": "read_note", "arguments": {"id": 1}}))


class Relay(Base):
    def test_proxy_relays_both_directions_and_closes(self):
        client, client_peer = socket.socketpair()
        remote, remote_peer = socket.socketpair()

        class Remote:
            def connect(self, address):
                self.address = address

            def __getattr__(self, name):
                return getattr(remote, name)
        fake = Remote()
        with patch.object(service.socket, "AF_UNIX", 1, create=True), patch.object(service.socket, "socket", lambda *a: fake):
            worker = threading.Thread(target=service.connect_proxy, args=(client,))
            worker.start()
            client_peer.sendall(b"ping")
            self.assertEqual(remote_peer.recv(4), b"ping")
            remote_peer.sendall(b"pong")
            self.assertEqual(client_peer.recv(4), b"pong")
            remote_peer.close()
            client_peer.close()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(fake.address, "/ipc/egress.sock")

    def test_listener_binds_loopback_and_hands_clients_to_the_relay(self):
        handed = threading.Event()
        block = threading.Event()  # never set: the daemon accept loop parks after the first client
        accepted = iter([("client", None)])

        class Listener:
            def setsockopt(self, *a): pass
            def bind(self, address): self.address = address
            def listen(self, n): pass
            def accept(self):
                try:
                    return next(accepted)
                except StopIteration:
                    block.wait()
        listener = Listener()
        with patch.object(service.socket, "socket", lambda *a: listener), \
                patch.object(service, "connect_proxy", lambda c: handed.set()):
            service.start_proxy()
            self.assertTrue(handed.wait(5))
        self.assertEqual(listener.address, ("127.0.0.1", 3128))


class Supervision(Base):
    def test_deadline_kills_the_worker_and_exit_without_result_fails(self):
        service.save(service.job_path(JID), {"id": JID, "status": "running", "deadline_s": 5})
        process = Mock(pid=7)
        process.wait.side_effect = [subprocess.TimeoutExpired("w", 20), 0]
        patch.object(service.subprocess, "Popen", return_value=process).start()
        killpg = patch.object(service.os, "killpg", create=True).start()
        patch("signal.SIGKILL", 9, create=True).start()
        service.supervise(service.read_job(JID))
        self.assertEqual(process.wait.call_args_list[0].kwargs["timeout"], 20)
        self.assertEqual(killpg.call_args.args[0], 7)
        self.assertEqual(service.read_job(JID)["error"], "Hermes exceeded its execution deadline")
        self.assertNotIn(JID, service.ACTIVE)
        service.save(service.job_path(JID), {"id": JID, "status": "running"})
        process.wait.side_effect = None
        service.supervise(service.read_job(JID))
        self.assertIsNone(process.wait.call_args.kwargs["timeout"], "no owner limit means no deadline")
        self.assertEqual(service.read_job(JID)["error"], "Hermes worker exited without a final result")
        service.save(service.job_path(JID), {"id": JID, "status": "cancelled"})
        service.ACTIVE[JID] = None
        service.supervise(service.read_job(JID))
        self.assertNotIn(JID, service.ACTIVE, "a job cancelled before launch never starts a worker")

    def test_oversized_history_fails_the_job(self):
        service.save(service.job_path(JID), {"id": JID, "status": "running", "model": "free", "session": "s" * 32})
        service.save(service.STATE / "sessions" / ("s" * 32 + ".json"), {"messages": ["x" * 4_100_000]})
        real_read = service.Path.read_bytes
        patch.object(service.Path, "read_bytes", autospec=True,
                     side_effect=lambda p: b"agent" if str(p).replace("\\", "/").endswith("/opt/hermes/run_agent.py") else real_read(p)).start()
        patch.object(service, "AGENT_HASH", hashlib.sha256(b"agent").hexdigest()).start()
        patch.object(service, "catalog", return_value={"models": [{"id": "free", "free": True}]}).start()
        patch.dict(sys.modules, {"run_agent": types.SimpleNamespace(AIAgent=Mock())}).start()
        service.run_agent(JID)
        self.assertEqual(service.read_job(JID)["error_code"], "ValueError")


class Startup(Base):
    def test_main_requires_linux_runs_workers_and_marks_interrupted_jobs(self):
        if not hasattr(service.socketserver, "UnixStreamServer"):
            with self.assertRaisesRegex(RuntimeError, "Linux Docker runtime"):
                service.main()
        patch.object(service.socketserver, "UnixStreamServer", type("U", (), {}), create=True).start()
        with patch.object(service, "run_agent", return_value="ran") as worker, patch.object(sys, "argv", ["s", "--worker", JID]):
            self.assertEqual(service.main(), "ran")
        worker.assert_called_once_with(JID)
        service.save(service.job_path(JID), {"id": JID, "status": "running"})
        service.save(service.job_path("b" * 32), {"id": "b" * 32, "status": "completed"})
        patch.object(service, "start_proxy").start()
        real_read = service.Path.read_bytes
        patch.object(service.Path, "read_bytes", autospec=True,
                     side_effect=lambda p: b"other" if str(p).replace("\\", "/").endswith("/opt/hermes/run_agent.py") else real_read(p)).start()
        with patch.object(sys, "argv", ["s"]), self.assertRaisesRegex(ValueError, "compatibility check failed"):
            service.main()
        self.assertEqual(service.read_job(JID)["status"], "interrupted", "a runtime restart never replays a job")
        self.assertEqual(service.read_job("b" * 32)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
