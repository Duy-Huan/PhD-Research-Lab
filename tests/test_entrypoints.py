"""Launcher release checks and stdio bridge behavior without installs, UI windows or cloud calls."""
import _env
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import start
import mcp_stdio_bridge as bridge
from backend.core import config


class Launcher(unittest.TestCase):
    def test_installer_reexec_success_and_failure_never_launch_real_commands(self):
        class Reexecuted(Exception): pass
        for exists, calls, expected in ((False, [1], SystemExit), (False, [0, 0], Reexecuted),
                                        (True, [1, 1], SystemExit), (True, [1, 0, 1], SystemExit),
                                        (True, [1, 0, 0], Reexecuted)):
            with self.subTest(exists=exists, calls=calls), mock.patch.object(start.os.path, "exists", return_value=exists), \
                 mock.patch.object(start.subprocess, "call", side_effect=calls), mock.patch.object(start.os, "execv", side_effect=Reexecuted), \
                 mock.patch.object(start.sys, "stdin", io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(expected): start.reexec_in_venv()

    def test_install_success_and_still_missing_package(self):
        for answers, expected in (([["missing"], []], None), ([["missing"], ["missing"]], SystemExit)):
            with mock.patch.object(start, "missing_packages", side_effect=answers + [answers[-1]]), mock.patch.object(start, "in_venv", return_value=True), \
                 mock.patch.object(start.subprocess, "call", return_value=0), mock.patch.object(start.sys, "stdin", io.StringIO()), \
                 contextlib.redirect_stdout(io.StringIO()):
                if expected:
                    with self.assertRaises(expected): start.ensure_packages()
                else:
                    start.ensure_packages()

    def test_main_reuses_same_release_and_moves_away_from_other_servers(self):
        import uvicorn
        for info in ({"version": config.APP_VERSION, "root": start.ROOT}, {"version": "old", "root": "C:/other"}, None):
            with self.subTest(info=info), contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(start.sys, "argv", ["start.py", "--port", "9000", "--no-browser"]))
                stack.enter_context(mock.patch.object(start, "check_python"))
                stack.enter_context(mock.patch.object(start, "check_files"))
                stack.enter_context(mock.patch.object(start, "ensure_packages"))
                stack.enter_context(mock.patch.object(start, "report_tools"))
                stack.enter_context(mock.patch.object(start, "port_free", side_effect=[False, True]))
                stack.enter_context(mock.patch.object(start, "running_lab", return_value=info))
                stack.enter_context(mock.patch.dict(start.os.environ))
                server = stack.enter_context(mock.patch.object(uvicorn, "run"))
                output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                start.main()
                if info and info["version"] == config.APP_VERSION:
                    server.assert_not_called()
                    self.assertIn("already running", output.getvalue())
                else:
                    self.assertEqual(server.call_args.kwargs["port"], 9001)
                    self.assertEqual(start.os.environ["PHDLAB_URL"], "http://127.0.0.1:9001")

    def test_no_free_port_and_server_start_failure_are_readable_errors(self):
        import uvicorn
        for busy in (True, False):
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(start.sys, "argv", ["start.py", "--no-browser"]))
                for name in ("check_python", "check_files", "ensure_packages", "report_tools"):
                    stack.enter_context(mock.patch.object(start, name))
                stack.enter_context(mock.patch.object(start, "port_free", return_value=not busy))
                stack.enter_context(mock.patch.object(start, "running_lab", return_value=None))
                stack.enter_context(mock.patch.object(uvicorn, "run", side_effect=RuntimeError("fixture server failure")))
                stack.enter_context(mock.patch.object(start.sys, "stdin", io.StringIO()))
                stack.enter_context(mock.patch.dict(start.os.environ))
                output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                with self.assertRaises(SystemExit): start.main()
                self.assertIn("ports are busy" if busy else "Server crashed", output.getvalue())

    def test_browser_readiness_tools_and_python_version_checks(self):
        with mock.patch.object(start.socket, "create_connection", side_effect=[OSError("not ready"), mock.MagicMock()]), \
             mock.patch.object(start.time, "sleep"), mock.patch.object(start.webbrowser, "open") as browser, \
             contextlib.redirect_stdout(io.StringIO()):
            start.open_when_ready("http://127.0.0.1:9000", 9000)
        browser.assert_called_once_with("http://127.0.0.1:9000")
        with mock.patch("shutil.which", return_value=None), contextlib.redirect_stdout(io.StringIO()) as output:
            start.report_tools()
        self.assertIn("Tools", output.getvalue())
        with mock.patch.object(start.sys, "version_info", (3, 9)), mock.patch.object(start.sys, "stdin", io.StringIO()), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit): start.check_python()

    def test_current_release_checks_files_and_dependencies(self):
        self.assertEqual(start.APP_VERSION, config.APP_VERSION)
        with mock.patch.object(start.sys, "argv", ["start.py", "--check"]), \
             mock.patch.object(start, "report_tools"), contextlib.redirect_stdout(io.StringIO()) as output:
            start.main()
        self.assertIn("Files   : OK", output.getvalue())
        self.assertIn("Installation OK.", output.getvalue())

    def test_incomplete_install_and_mixed_version_remain_errors(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(start, "ROOT", temp), \
             mock.patch.object(start.sys, "stdin", io.StringIO()), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit): start.check_files()
            self.assertIn("incomplete", output.getvalue())
            for name in start.REQUIRED_FILES:
                path = Path(temp) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("")
            path = Path(temp) / "backend/core/config.py"
            path.write_text('APP_VERSION = "0.0.0"')
            with self.assertRaises(SystemExit): start.check_files()
            self.assertIn("Version mismatch", output.getvalue())
            path.write_text("invalid version metadata")
            with self.assertRaises(SystemExit): start.check_files()
            self.assertIn("unknown", output.getvalue())

    def test_port_probe_folder_identity_and_install_failure(self):
        self.assertTrue(start.port_free(0))
        self.assertTrue(start.same_folder(start.ROOT, str(Path(start.ROOT) / ".")))
        with mock.patch.object(start, "missing_packages", return_value=["required"]), \
             mock.patch.object(start, "in_venv", return_value=True), mock.patch.object(start.subprocess, "call", return_value=1) as pip, \
             mock.patch.object(start.sys, "stdin", io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit): start.ensure_packages()
        self.assertIn("requirements.txt", pip.call_args.args[0][-1])

    def test_server_identity_uses_the_version_endpoint(self):
        config_reply = io.BytesIO(json.dumps({"agent_modes": {}, "version": "old"}).encode())
        version_reply = io.BytesIO(json.dumps({"version": "5.1.0", "root": start.ROOT}).encode())
        with mock.patch.object(start.urllib.request, "urlopen", side_effect=[config_reply, version_reply]):
            self.assertEqual(start.running_lab(8765), {"version": "5.1.0", "root": start.ROOT})
        with mock.patch.object(start.urllib.request, "urlopen", side_effect=OSError("offline")):
            self.assertIsNone(start.running_lab(8765))


class Bridge(unittest.TestCase):
    def test_json_rpc_replies_notifications_auth_and_unreachable_server(self):
        lines = '\n{bad\n' + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + '\n' + json.dumps({"method": "notifications/initialized"}) + '\n'
        def reply(*args, **kwargs): return io.BytesIO(b'{"jsonrpc":"2.0","id":1,"result":{}}')
        output = io.StringIO()
        with mock.patch.object(bridge.sys, "stdin", io.StringIO(lines)), mock.patch.object(bridge, "TOKEN", "test-token"), \
             mock.patch.object(bridge.urllib.request, "urlopen", side_effect=reply) as network, contextlib.redirect_stdout(output):
            bridge.main()
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(network.call_args.args[0].get_header("Authorization"), "Bearer test-token")
        output = io.StringIO()
        with mock.patch.object(bridge.sys, "stdin", io.StringIO(lines)), mock.patch.object(bridge, "TOKEN", ""), \
             mock.patch.object(bridge.urllib.request, "urlopen", side_effect=OSError("offline")), contextlib.redirect_stdout(output):
            bridge.main()
        response = json.loads(output.getvalue())
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["error"]["code"], -32000)
