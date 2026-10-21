import _env  # noqa: F401  (must be first)
import os
import threading
import time
import unittest
from unittest import mock

from backend.providers import cli as C
from providers.fakes import fake

PIDS = ("codex", "claude_code", "antigravity", "gemini_cli")


class Contract(unittest.TestCase):
    """Every connector satisfies the common contract; unsupported capabilities say NOT_SUPPORTED."""

    def setUp(self):
        _env.fresh_project("providers")


    def test_missing_cli_is_unavailable_not_faked(self):
        with mock.patch.object(C.ClaudeCodeConnector, "binary", return_value=None):
            C.cached.__globals__["_cache"].clear()
            h = C.ClaudeCodeConnector().health()
            self.assertEqual(h["state"], "UNAVAILABLE")
            with self.assertRaises(C.ProviderError):
                list(C.ClaudeCodeConnector().stream_message("hi", {}))



    def test_codex_api_key_login_refused_without_fallback(self):
        c = C.CodexConnector()
        st, detail = c.auth_state({"login_code": 0, "login": "Logged in using an API key - sk-…"})
        self.assertEqual(st, "ERROR")
        self.assertIn("API billing", detail)
        self.assertEqual(c.auth_state({"login_code": 0, "login": "Logged in using ChatGPT"})[0], "CONNECTED")
        self.assertEqual(c.auth_state({"login_code": 1, "login": "Not logged in"})[0], "AUTH_EXPIRED")

    def test_error_normalisation(self):
        for pid in PIDS:
            evs = list(fake(pid, "auth").stream_message("q", {}))
            self.assertIn("error", [e["type"] for e in evs], pid)
        self.assertEqual(C.classify_error("429 rate limit exceeded"), "RATE_LIMITED")
        self.assertEqual(C.classify_error("Authentication required"), "AUTH_EXPIRED")
        self.assertEqual(C.classify_error("disk full"), "ERROR")
        evs = list(fake("codex", "crash").stream_message("q", {}))
        err = [e for e in evs if e["type"] == "error"]
        self.assertTrue(err and "something broke" in err[0]["message"])

    def test_auth_failure_updates_health(self):
        c = fake("claude_code", "auth")
        list(c.stream_message("q", {}))
        self.assertEqual(c.health()["state"], "AUTH_EXPIRED")
        C._last_error.clear()

    def test_cancel(self):
        c = fake("gemini_cli", "slow")
        out = []
        th = threading.Thread(target=lambda: out.extend(c.stream_message("q", {"request_id": "req-cancel01"})))
        th.start()
        for _ in range(100):
            if "req-cancel01" in C._procs:
                break
            time.sleep(0.05)
        self.assertTrue(c.cancel("req-cancel01")["cancelled"])
        th.join(20)
        self.assertIn("request_cancelled", [e["type"] for e in out])
        self.assertFalse(c.cancel("req-cancel01")["cancelled"])


    def test_claude_mcp_allowlist_read_only(self):
        ctx = {"mcp_url": "http://127.0.0.1:8765/mcp"}
        args = C.ClaudeCodeConnector().argv.__func__(fake("claude_code"), ctx)
        allowed = args[args.index("--allowedTools") + 1]
        self.assertNotIn("record", allowed)
        self.assertNotIn("sandbox", allowed)
        self.assertNotIn("--bare", args)  # bare mode would bypass the subscription login
        os.remove(ctx["_tmpfile"])




if __name__ == "__main__":
    unittest.main()
