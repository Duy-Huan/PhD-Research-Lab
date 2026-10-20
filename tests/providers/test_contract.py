import _env  # noqa: F401  (must be first)
import os
import threading
import time
import unittest
from unittest import mock

from backend.gateway import connectors as C
from providers.fakes import fake

PIDS = ("codex", "claude_code", "antigravity", "gemini_cli")


class Contract(unittest.TestCase):
    """Every connector satisfies the common contract; unsupported capabilities say NOT_SUPPORTED."""

    def setUp(self):
        _env.fresh_project("providers")

    def test_contract_surface(self):
        for pid, c in C.CONNECTORS.items():
            caps = c.capabilities()
            self.assertEqual(set(caps), set(C.CAPS), pid)
            for v in caps.values():
                self.assertIn(v, (True, C.NOT_SUPPORTED), pid)
            h = c.health()
            self.assertIn(h["state"], C.HEALTH, pid)
            for m in ("connect", "disconnect", "health", "capabilities", "send_message", "stream_message", "cancel", "start_session"):
                self.assertTrue(callable(getattr(c, m)), (pid, m))
        self.assertFalse(C.chatgpt_web_note()["supported"])
        with self.assertRaises(C.ProviderError):
            C.get("chatgpt_private_api")

    def test_missing_cli_is_unavailable_not_faked(self):
        with mock.patch.object(C.ClaudeCodeConnector, "binary", return_value=None):
            C.cached.__globals__["_cache"].clear()
            h = C.ClaudeCodeConnector().health()
            self.assertEqual(h["state"], "UNAVAILABLE")
            with self.assertRaises(C.ProviderError):
                list(C.ClaudeCodeConnector().stream_message("hi", {}))

    def test_send_and_stream_every_provider(self):
        for pid in PIDS:
            c = fake(pid)
            evs = list(c.stream_message("question about HYPE-002", {"request_id": f"req-{pid}"}))
            types = [e["type"] for e in evs]
            self.assertEqual(types[0], "request_started", pid)
            self.assertEqual(types[-1], "request_completed", pid)
            self.assertTrue(set(types) <= set(C.E.TYPES), pid)
            r = c.send_message("question about HYPE-002", {})
            self.assertIn("hyp=True", r["text"], pid)
            self.assertTrue(r["session_id"], pid)

    def test_cost_guard_removes_api_keys(self):
        env = {"OPENAI_API_KEY": "sk-test", "CODEX_API_KEY": "x", "ANTHROPIC_API_KEY": "sk-ant-x", "GEMINI_API_KEY": "g", "GOOGLE_API_KEY": "g"}
        with mock.patch.dict(os.environ, env):
            for pid in PIDS:
                self.assertIn("keys=none", fake(pid).send_message("q", {})["text"], pid)
            _env.config.save_config({"gateway": {"claude_code_api_fallback": True}})
            self.assertIn("ANTHROPIC_API_KEY", fake("claude_code").send_message("q", {})["text"])
            _env.config.save_config({"gateway": {"claude_code_api_fallback": False}})

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

    def test_disconnect_and_connect_never_touch_credentials(self):
        c = C.CONNECTORS["gemini_cli"]
        self.assertEqual(c.disconnect()["state"], "DISCONNECTED")
        self.assertEqual(c.health()["state"], "DISCONNECTED")
        r = c.connect()
        self.assertEqual(r["action"], "sign_in_with_vendor")
        self.assertNotIn("password", str(r).lower().replace("never sees your password", ""))

    def test_claude_mcp_allowlist_read_only(self):
        ctx = {"mcp_url": "http://127.0.0.1:8765/mcp"}
        args = C.ClaudeCodeConnector().argv.__func__(fake("claude_code"), ctx)
        allowed = args[args.index("--allowedTools") + 1]
        self.assertNotIn("record", allowed)
        self.assertNotIn("sandbox", allowed)
        self.assertNotIn("--bare", args)  # bare mode would bypass the subscription login
        os.remove(ctx["_tmpfile"])

    def test_mcp_registration_snippets(self):
        base = "http://127.0.0.1:8765"
        self.assertIn("claude mcp add --transport http", C.CONNECTORS["claude_code"].mcp_registration(base)["command"])
        snip = C.CONNECTORS["antigravity"].mcp_registration(base)["snippet"]
        self.assertEqual(snip["mcpServers"]["phd-research-lab"]["serverUrl"], base + "/mcp")
        self.assertIn("mcp_servers.phd-research-lab", C.CONNECTORS["codex"].mcp_registration(base)["snippet"])

    def test_antigravity_register_mcp_merges_and_backs_up(self):
        import json
        import tempfile
        from pathlib import Path
        home = Path(tempfile.mkdtemp())
        cfgf = home / ".gemini" / "config" / "mcp_config.json"
        cfgf.parent.mkdir(parents=True)
        cfgf.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), "utf-8")
        with mock.patch.object(C.AntigravityConnector, "config_path", return_value=cfgf):
            C.CONNECTORS["antigravity"].register_mcp("http://127.0.0.1:8765", "")
            d = json.loads(cfgf.read_text("utf-8"))
            self.assertIn("other", d["mcpServers"])
            self.assertIn("phd-research-lab", d["mcpServers"])
            self.assertTrue(cfgf.with_suffix(".json.bak").exists())
            self.assertTrue(C.CONNECTORS["antigravity"].mcp_registered())


if __name__ == "__main__":
    unittest.main()
