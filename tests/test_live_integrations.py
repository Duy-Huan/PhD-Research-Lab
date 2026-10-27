"""OPT-IN smoke tests against real services. Skipped unless explicitly enabled:

    PHDLAB_CODEX_LIVE=1    + an installed, logged-in `codex` CLI (uses your Codex quota: one tiny read-only task)
"""
import _env  # noqa: F401  (must be first)
import os
import time
import unittest

from backend.core.config import save_config


@unittest.skipUnless(os.environ.get("PHDLAB_CODEX_LIVE") == "1", "set PHDLAB_CODEX_LIVE=1 to run one real read-only Codex task")
class CodexLive(unittest.TestCase):
    def test_read_only_run(self):
        from pathlib import Path
        from backend.providers.cli import CodexConnector
        from backend.providers import cli_space as W
        _env.fresh_project("codex-live")
        save_config({"gateway": {"codex_enabled": True}})
        session = W.open_session("codex", f"live-{time.time_ns()}", "review", W.check_profile("codex", "review"))
        hello = Path(session["cwd"]) / "hello.py"
        source = "def add(a, b):\n    return a + b\n"
        hello.write_text(source, "utf-8")
        events = list(CodexConnector().stream_message(
            "Read hello.py and answer in one sentence what add() returns. Do not modify files.",
            {"cwd": session["cwd"], "profile": "review", "timeout_s": 120}))
        self.assertFalse([e for e in events if e["type"] == "error"], events)
        self.assertTrue(any(e["type"] == "request_completed" and e["exit_code"] == 0 for e in events), events)
        self.assertTrue(any(e["type"] == "text_delta" and e.get("text") for e in events), events)
        self.assertEqual(hello.read_text("utf-8"), source)


if __name__ == "__main__":
    unittest.main()
