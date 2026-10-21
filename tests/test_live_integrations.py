"""OPT-IN smoke tests against real services. Skipped unless explicitly enabled:

    PHDLAB_CLEARML_LIVE=1  + CLEARML_API_HOST / CLEARML_API_ACCESS_KEY / CLEARML_API_SECRET_KEY (or ~/clearml.conf)
    PHDLAB_CODEX_LIVE=1    + an installed, logged-in `codex` CLI (uses your Codex quota: one tiny read-only task)
"""
import _env  # noqa: F401  (must be first)
import os
import time
import unittest

from backend.core.config import save_config


@unittest.skipUnless(os.environ.get("PHDLAB_CLEARML_LIVE") == "1", "set PHDLAB_CLEARML_LIVE=1 to run against a real ClearML server")
class ClearMLLive(unittest.TestCase):
    def test_create_log_read(self):
        from backend.execution.tracker import ClearMLAdapter
        save_config({"clearml": {"enabled": True, "api_host": os.environ.get("CLEARML_API_HOST", ""),
                                 "web_host": os.environ.get("CLEARML_WEB_HOST", ""), "files_host": os.environ.get("CLEARML_FILES_HOST", ""),
                                 "access_key": os.environ.get("CLEARML_API_ACCESS_KEY", ""),
                                 "secret_key": os.environ.get("CLEARML_API_SECRET_KEY", ""), "project": "PhD Lab smoke test"}})
        ad = ClearMLAdapter()
        self.assertEqual(ad.status().state, "available", ad.status().detail)
        exp = ad.create_experiment("smoke", params={"lr": 0.001}, tags=["smoke"])
        ad.start_run(exp["id"])
        for i in range(3):
            ad.log_metric(exp["id"], "loss", 1.0 / (i + 1), i)
        ad.finish_run(exp["id"])
        got = ad.get_experiment(exp["id"])
        self.assertEqual(got["id"], exp["id"])
        self.assertIn(got["status"], ("completed", "closed"))


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
