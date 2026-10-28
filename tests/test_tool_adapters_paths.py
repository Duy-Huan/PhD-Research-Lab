"""FQC-COVERAGE-662: tool execution adapters — owned processes (cancel, timeout, output budget, missing binary),
native probes/callables, CLI argument templates, the streamable-HTTP MCP client against a real loopback server
(JSON and SSE replies, protocol/error/correlation failures, pagination) and container launch policy."""
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import _env  # noqa: F401
from backend.tools import adapters as A
from backend.tools.spec import ToolError


def ctx(**kw):
    base = dict(workdir=Path(tempfile.mkdtemp(prefix="phdlab-tool-")), max_output_bytes=1_000_000, cancelled=threading.Event(),
                deadline=time.monotonic() + 30, principal="test", job_id="j1", observed=[])
    base.update(kw)
    c = SimpleNamespace(**base)
    c.observe = lambda kind, text: c.observed.append((kind, text))
    return c


def spec(**execution):
    return SimpleNamespace(execution=execution, ref="t@1", id="t", capabilities=[], permissions=[],
                           budget=SimpleNamespace(memory_mb=256, cpus=1))


class Processes(unittest.TestCase):
    def test_output_stderr_and_failures_are_bounded(self):
        c = ctx()
        out = A.run_process([sys.executable, "-c", "import sys;print('ok');print('warn',file=sys.stderr)"], c, env=None)
        self.assertEqual((out["exit_code"], out["stdout"].strip()), (0, "ok"))
        self.assertIn(("stderr", "warn"), c.observed)
        with self.assertRaises(ToolError) as e:
            A.run_process([sys.executable, "-c", "print('x'*5000)"], ctx(max_output_bytes=100))
        self.assertEqual(e.exception.code, "budget_exceeded")
        with self.assertRaises(ToolError) as e:
            A.run_process([sys.executable, "-c", "import time;time.sleep(30)"], ctx(deadline=time.monotonic() + 0.5))
        self.assertEqual((e.exception.code, e.exception.retryable), ("timeout", True))
        cancelled = ctx()
        threading.Timer(0.3, cancelled.cancelled.set).start()
        with self.assertRaises(ToolError) as e:
            A.run_process([sys.executable, "-c", "import time;time.sleep(30)"], cancelled)
        self.assertEqual(e.exception.code, "cancelled")
        with self.assertRaises(ToolError) as e:
            A.run_process(["phdlab-no-such-binary-xyz"], ctx())
        self.assertEqual(e.exception.code, "unavailable")
        with patch.object(A.subprocess, "Popen", side_effect=PermissionError("denied")), self.assertRaises(ToolError) as e:
            A.run_process(["x"], ctx())
        self.assertEqual(e.exception.code, "execution_failed")

    def test_json_results_and_cli_templates(self):
        with self.assertRaises(ToolError):
            A._json_result("not json", spec())
        with self.assertRaises(ToolError):
            A._json_result("[1]", spec())
        self.assertEqual(A.Cli.argv(["--in", "{path}", "{n}"], {"path": "a.csv", "n": 3}), ["--in", "a.csv", "3"])
        for args in ({}, {"path": "--evil"}):
            with self.subTest(args), self.assertRaises(ToolError):
                A.Cli.argv(["{path}"], args)
        self.assertIsNone(A.Cli.resolve(spec()))
        self.assertIsNone(A.Cli.resolve(spec(binary=str(Path(tempfile.gettempdir()) / "missing.exe"))))
        self.assertFalse(A.Cli.probe(spec(binary="phdlab-no-such-binary-xyz"))["available"])
        with self.assertRaises(ToolError) as e:
            A.Cli.execute(spec(binary="phdlab-no-such-binary-xyz"), {}, ctx())
        self.assertEqual(e.exception.code, "unavailable")
        py = spec(binary=sys.executable, args=["-c", "import sys;sys.exit(3)"])
        with self.assertRaises(ToolError) as e:
            A.Cli.execute(py, {}, ctx())
        self.assertEqual(e.exception.code, "execution_failed")
        ok = spec(binary=sys.executable, args=["-c", "print('{\"a\": 1}')"], output="json")
        self.assertEqual(A.Cli.execute(ok, {}, ctx()), {"a": 1})
        raw = spec(binary=sys.executable, args=["-c", "print('hi')"])
        self.assertEqual(A.Cli.execute(raw, {}, ctx())["stdout"].strip(), "hi")


class NativeTools(unittest.TestCase):
    def test_probes_and_callables(self):
        with patch("backend.core.config.load_config", return_value={"mcp": {"enabled": False}}):
            self.assertFalse(A.Native.probe(spec(mcp_tool="x"))["available"])
        sandbox = spec(mcp_tool="x")
        sandbox.capabilities = ["sandbox"]
        with patch("backend.core.config.load_config", return_value={"mcp": {"expose_sandbox": False}}):
            self.assertIn("expose_sandbox", A.Native.probe(sandbox)["reason"])
        self.assertFalse(A.Native.probe(spec(probe="os:getcwd"))["available"])
        self.assertTrue(A.Native.probe(spec(callable="backend.x:y"))["available"])
        self.assertFalse(A.Native.probe(spec())["available"])
        with self.assertRaises(ToolError):
            A.Native.execute(spec(callable="os:getcwd"), {}, ctx())
        with patch("backend.core.config.coverage_text_tool", lambda args, c: "text", create=True), self.assertRaises(ToolError) as e:
            A.Native.execute(spec(callable="backend.core.config:coverage_text_tool"), {}, ctx())
        self.assertEqual(e.exception.code, "invalid_output")
        with patch("backend.core.config.coverage_spec_tool", lambda args, c, s: {"ref": s.ref}, create=True):
            self.assertEqual(A.Native.execute(spec(callable="backend.core.config:coverage_spec_tool", pass_spec=True), {}, ctx()),
                             {"ref": "t@1"})

    def test_mcp_backed_native_tools_map_errors(self):
        cases = [(PermissionError("no"), "permission_denied"), (KeyError("k"), "invalid_input")]
        for error, code in cases:
            with self.subTest(code), patch("backend.providers.mcp_server.call_tool", side_effect=error), self.assertRaises(ToolError) as e:
                A.Native.execute(spec(mcp_tool="x"), {}, ctx())
            self.assertEqual(e.exception.code, code)
        with patch("backend.providers.mcp_server.call_tool", return_value={"isError": True, "content": [{"type": "text", "text": "bad"}]}):
            with self.assertRaises(ToolError):
                A.Native.execute(spec(mcp_tool="x"), {}, ctx())
        with patch("backend.providers.mcp_server.call_tool",
                   return_value={"content": [{"type": "text", "text": "ok"}], "structuredContent": {"n": 1}}):
            self.assertEqual(A.Native.execute(spec(mcp_tool="x"), {}, ctx()), {"text": "ok", "structured": {"n": 1}})


class Server(BaseHTTPRequestHandler):
    script = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        status, kind, payload = Server.script.pop(0) if Server.script else (200, "json", {"result": {}})
        if callable(payload):
            payload = payload(body)
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        if kind == "sse":
            raw = b"event: message\ndata: " + raw + b"\n\n"
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream" if kind == "sse" else "application/json")
        self.send_header("Mcp-Session-Id", "s-1")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


def reply(result):
    return lambda body: {"jsonrpc": "2.0", "id": body.get("id"), "result": result}


class McpClient(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Server)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/mcp"
        Server.script = []

    def session(self, *extra):
        Server.script = [(200, "json", reply({"protocolVersion": "2025-06-18"})), (202, "json", b"")] + list(extra)
        return A.McpSession(self.url, 5)

    def test_session_negotiates_and_paginates_tool_lists(self):
        with self.session((200, "sse", reply({"tools": [{"name": "a"}, "junk"], "nextCursor": "c1"})),
                          (200, "json", reply({"tools": [{"name": "b"}], "nextCursor": "c1"}))) as s:
            self.assertEqual(s.headers["Mcp-Session-Id"], "s-1")
            self.assertEqual([t["name"] for t in s.list_tools()], ["a", "b"], "a repeated cursor ends pagination")

    def test_protocol_and_response_failures(self):
        Server.script = [(200, "json", reply({"protocolVersion": "1999-01-01"}))]
        with self.assertRaises(ToolError) as e, A.McpSession(self.url, 5):
            pass
        self.assertEqual(e.exception.code, "incompatible_version")
        failures = [((500, "json", {}), "unavailable"), ((403, "json", {}), "execution_failed"),
                    ((200, "json", b"{bad"), "invalid_output"), ((200, "json", {"id": 999, "result": {}}), "invalid_output"),
                    ((200, "json", lambda b: {"id": b["id"], "error": {"message": "boom"}}), "execution_failed"),
                    ((200, "json", lambda b: {"id": b["id"], "result": [1]}), "invalid_output")]
        for step, code in failures:
            with self.subTest(code=code, step=str(step[2])[:30]), self.session(step) as s, self.assertRaises(ToolError) as e:
                s.request("tools/call", {})
            self.assertEqual(e.exception.code, code)
        with self.session() as s:
            s.LIMIT = 10
            Server.script = [(200, "json", reply({"x": "y" * 100}))]
            with self.assertRaises(ToolError) as e:
                s.request("tools/call", {})
        self.assertEqual(e.exception.code, "budget_exceeded")
        import httpx
        dead = A.McpSession(self.url, 2)
        for error, code in ((httpx.ConnectError("refused"), "unavailable"), (httpx.ReadTimeout("slow"), "timeout")):
            with self.subTest(code), patch.object(dead.client, "post", side_effect=error), self.assertRaises(ToolError) as e:
                dead.request("ping", {})
            self.assertEqual((e.exception.code, e.exception.retryable), (code, True))
        dead.client.close()

    def test_remote_tools_unpack_results(self):
        c = ctx()
        with patch.object(A.Mcp, "_url", return_value=self.url):
            Server.script = [(200, "json", reply({"protocolVersion": "2025-03-26"})), (202, "json", b""),
                             (200, "json", reply({"content": [{"type": "text", "text": "done"}], "structuredContent": {"k": 1}}))]
            self.assertEqual(A.Mcp.execute(spec(url=self.url, tool="remote"), {}, c), {"text": "done", "structured": {"k": 1}})
            Server.script = [(200, "json", reply({"protocolVersion": "2025-03-26"})), (202, "json", b""),
                             (200, "json", reply({"isError": True, "content": []}))]
            with self.assertRaises(ToolError):
                A.Mcp.execute(spec(url=self.url, tool="remote"), {}, c)
        self.assertFalse(A.Mcp.probe(spec(url="ftp://nowhere"))["available"])


class ContainerTools(unittest.TestCase):
    def test_probe_and_launch_policy(self):
        with patch("backend.execution.sandbox.docker_exe", return_value=None):
            self.assertIn("not installed", A.Container.probe(spec(image="i"))["reason"])
        with patch("backend.execution.sandbox.docker_exe", return_value="docker"), \
                patch("backend.execution.sandbox.docker_running", return_value=False):
            self.assertIn("not running", A.Container.probe(spec(image="i"))["reason"])
            with self.assertRaises(ToolError):
                A.Container.execute(spec(image="i"), {}, ctx())
        with patch("backend.execution.sandbox.docker_exe", return_value="docker"), \
                patch("backend.execution.sandbox.docker_running", return_value=True), \
                patch("backend.execution.sandbox.image_present", return_value=True), \
                patch("backend.execution.sandbox.docker") as docker, \
                patch.object(A, "run_process", return_value={"exit_code": 0, "stdout": '{"ok": true}', "stderr": ""}) as run:
            self.assertEqual(A.Container.execute(spec(image="py", command=["python"], home="/tools/t"), {"a": 1}, ctx()), {"ok": True})
            argv = run.call_args.args[0]
            self.assertIn("--network", argv)
            self.assertIn("/tools/t:/tool:ro", argv)
            self.assertTrue(docker.called, "the named container is always removed")
            run.return_value = {"exit_code": 2, "stdout": "", "stderr": "boom"}
            with self.assertRaises(ToolError):
                A.Container.execute(spec(image="py"), {}, ctx())


if __name__ == "__main__":
    unittest.main()
