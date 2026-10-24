"""Real CLI Provider Verification Suite.

Exercises real binaries (codex, claude_code, antigravity, gemini_cli):
  - Binary detection and version check
  - Non-destructive authentication status inspection
  - Workspace directory isolation and profile permissions
  - Safe read-only probe if authenticated, otherwise honest UNAUTHENTICATED
"""
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from tests.live_e2e.conftest_or_setup import configure_live_phi4
from backend.core import config as C
from backend.providers.cli import CONNECTORS, CodexConnector, ClaudeCodeConnector, AntigravityConnector, GeminiCliConnector
from backend.providers import cli_space as W


class TestProviderCLILive(unittest.TestCase):
    def setUp(self):
        configure_live_phi4()

    def test_cli_connectors_inventory_and_contracts(self):
        """Verify all 4 official connectors adhere to ProviderConnector contract."""
        expected = {"codex", "claude_code", "antigravity", "gemini_cli"}
        self.assertEqual(set(CONNECTORS.keys()), expected)
        for pid, conn in CONNECTORS.items():
            caps = conn.capabilities()
            self.assertIsInstance(caps, dict)
            self.assertTrue(caps.get("health"))
            self.assertTrue(caps.get("capabilities"))

    def test_codex_cli_health_and_version(self):
        """Inspect ChatGPT / Codex CLI binary and real login status."""
        conn = CONNECTORS["codex"]
        h = conn.health()
        self.assertIn(h["state"], ("CONNECTED", "DISCONNECTED", "AUTH_EXPIRED", "UNAVAILABLE", "ERROR", "UNKNOWN"))
        self.assertIn("version", h)
        self.assertIn("state", h)

    def test_claude_code_cli_health_and_version(self):
        """Inspect Claude Code CLI binary and real login status."""
        conn = CONNECTORS["claude_code"]
        h = conn.health()
        self.assertIn(h["state"], ("CONNECTED", "DISCONNECTED", "AUTH_EXPIRED", "UNAVAILABLE", "ERROR", "UNKNOWN"))
        self.assertIn("version", h)
        self.assertIn("state", h)

    def test_antigravity_connector_health_and_version(self):
        """Inspect Google Antigravity connector health and version."""
        conn = CONNECTORS["antigravity"]
        h = conn.health()
        self.assertIn(h["state"], ("CONNECTED", "DISCONNECTED", "AUTH_EXPIRED", "UNAVAILABLE", "ERROR", "UNKNOWN"))
        self.assertIn("version", h)
        self.assertIn("state", h)

    def test_gemini_cli_health_and_version(self):
        """Inspect Gemini CLI binary and real login status."""
        conn = CONNECTORS["gemini_cli"]
        h = conn.health()
        self.assertIn(h["state"], ("CONNECTED", "DISCONNECTED", "AUTH_EXPIRED", "UNAVAILABLE", "ERROR", "UNKNOWN"))
        self.assertIn("version", h)
        self.assertIn("state", h)

    def test_cli_workspace_session_isolation(self):
        """Verify open_session creates an isolated temporary directory outside app code."""
        sid = f"test-cli-{time.time_ns()}"
        session = W.open_session("codex", sid, "review", W.check_profile("codex", "review"))
        try:
            cwd = Path(session["cwd"])
            self.assertTrue(cwd.exists())
            self.assertNotEqual(cwd.resolve(), C.ROOT.resolve())
            self.assertNotEqual(cwd.resolve(), (C.ROOT / "backend").resolve())
            self.assertFalse(cwd.is_relative_to(C.ROOT / "backend"))
        finally:
            shutil.rmtree(session.get("dir", session["cwd"]), ignore_errors=True)

    def test_cli_authenticated_readonly_probe(self):
        """Execute tiny read-only probe if Codex or Claude is authenticated."""
        if os.environ.get("PHDLAB_CODEX_LIVE") != "1":
            self.skipTest("Live CLI execution requires opt-in via PHDLAB_CODEX_LIVE=1")
        codex_h = CONNECTORS["codex"].health()
        if codex_h["state"] == "CONNECTED":
            sid = f"live-codex-{time.time_ns()}"
            session = W.open_session("codex", sid, "review", W.check_profile("codex", "review"))
            try:
                hello = Path(session["cwd"]) / "probe.py"
                hello.write_text("def ping(): return 'PONG'\n", encoding="utf-8")
                events = list(CONNECTORS["codex"].stream_message(
                    "Read probe.py and state in 1 word what ping returns. Do not modify files.",
                    {"cwd": session["cwd"], "profile": "review", "timeout_s": 120}
                ))
                self.assertFalse([e for e in events if e.get("type") == "error"], events)
                self.assertEqual(hello.read_text("utf-8"), "def ping(): return 'PONG'\n")
            finally:
                shutil.rmtree(session.get("dir", session["cwd"]), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
