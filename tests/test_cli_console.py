"""FQC-CLI-STUDIO-663: "Open in cmd" continues the web CLI conversation in the phdlab terminal chat.

Only PhD Lab's own client starts, with a fixed command and a validated session id; the console talks to the same
server over loopback, so the browser and cmd share one conversation. Credentials are not passed to the console."""
import os
import subprocess
import sys
import unittest
from unittest import mock

import _env
from backend.agent import AIWSError, sessions
from backend.providers import native


class OpenChatConsole(unittest.TestCase):
    def setUp(self):
        _env.fresh_project('cli-console-663')
        self.sid = sessions.create("CLI")["id"]

    def test_windows_opens_cmd_on_this_conversation_with_a_clean_environment(self):
        with mock.patch.object(native.sys, "platform", "win32"), mock.patch.object(native.subprocess, "Popen") as popen, \
                mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-secret"}):
            popen.return_value.pid = 4242
            out = native.open_chat_console(self.sid, 8791)
        self.assertTrue(out["launched"])
        self.assertEqual(out["command"], f"chat.bat --session {self.sid}")
        argv = popen.call_args.args[0]
        self.assertIsInstance(argv, str, "cmd.exe receives one command line")
        self.assertTrue(argv.startswith("cmd.exe /d /k "))
        self.assertIn(f"-m backend.cli chat --session {self.sid}", argv)
        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["PHDLAB_URL"], "http://127.0.0.1:8791")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertEqual(popen.call_args.kwargs["creationflags"], getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10))

    def test_invalid_or_unknown_sessions_never_start_a_process(self):
        with mock.patch.object(native.subprocess, "Popen") as popen:
            for bad in ("as-1 & calc", "../x", "as-0000000000"):
                with self.subTest(bad=bad), self.assertRaises(AIWSError):
                    native.open_chat_console(bad, 8791)
            with self.assertRaises(ValueError):
                native.open_chat_console(self.sid, 0)
        popen.assert_not_called()

    def test_opening_a_console_returns_at_once_without_waiting_for_it(self):
        import time
        with mock.patch.object(native.sys, "platform", "win32"), mock.patch.object(native.subprocess, "Popen") as popen:
            popen.return_value.pid = 1
            started = time.perf_counter()
            native.open_chat_console(self.sid, 8791)
            self.assertLess(time.perf_counter() - started, 0.5)
        popen.return_value.wait.assert_not_called()
        popen.return_value.communicate.assert_not_called()

    def test_without_a_terminal_the_command_is_still_offered(self):
        with mock.patch.object(native.sys, "platform", "linux"), mock.patch.object(native.shutil, "which", return_value=None), \
                mock.patch.object(native.subprocess, "Popen") as popen:
            out = native.open_chat_console(self.sid, 8765)
        self.assertFalse(out["launched"])
        self.assertEqual(out["command"], f"./phdlab chat --session {self.sid}")
        popen.assert_not_called()

    def test_api_uses_the_port_the_server_listens_on(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        with mock.patch.object(native, "open_chat_console", return_value={"launched": True, "command": "x"}) as opened:
            r = TestClient(app, base_url="http://127.0.0.1:8791").post(f"/api/chat/sessions/{self.sid}/console")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(opened.call_args.args[0], self.sid)
        self.assertIsInstance(opened.call_args.args[1], int)

    @unittest.skipUnless(sys.platform.startswith("win"), "real cmd.exe quoting")
    def test_the_command_line_runs_in_a_real_cmd(self):
        # Same command line as the console window, with /c so it exits: proves cmd.exe parses the quoting.
        line = native.console_command(sys.executable, ["-m", "backend.cli", "--help"], keep_open=False)
        r = subprocess.run(line, cwd=str(_env.ROOT), env=dict(os.environ, PYTHONPATH=str(_env.ROOT), PYTHONIOENCODING="utf-8"),
                           capture_output=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        self.assertIn("phdlab", r.stdout.decode("utf-8", "replace"))


if __name__ == "__main__":
    unittest.main()
