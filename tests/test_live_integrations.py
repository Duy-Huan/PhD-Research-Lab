"""OPT-IN smoke tests against real services. Skipped unless explicitly enabled:

    PHDLAB_CLEARML_LIVE=1  + CLEARML_API_HOST / CLEARML_API_ACCESS_KEY / CLEARML_API_SECRET_KEY (or ~/clearml.conf)
    PHDLAB_CODEX_LIVE=1    + an installed, logged-in `codex` CLI (uses your Codex quota: one tiny read-only task)
"""
import _env  # noqa: F401  (must be first)
import os
import time
import unittest

from backend.config import save_config


@unittest.skipUnless(os.environ.get("PHDLAB_CLEARML_LIVE") == "1", "set PHDLAB_CLEARML_LIVE=1 to run against a real ClearML server")
class ClearMLLive(unittest.TestCase):
    def test_create_log_read(self):
        from backend.integrations.experiment import ClearMLAdapter
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
        from backend.integrations import agents as A
        from backend.sandbox import code_dir
        _env.fresh_project("codex-live")
        (code_dir() / "hello.py").write_text("def add(a, b):\n    return a + b\n", "utf-8")
        save_config({"codex": {"enabled": True}})
        run = A.CodexBackend().start_run("Read hello.py and answer in one sentence what add() returns. Do not modify files.")
        t0 = time.time()
        while A.get_run(run["id"])["status"] in ("starting", "running") and time.time() - t0 < 600:
            time.sleep(2)
        r = A.get_run(run["id"])
        self.assertEqual(r["status"], "completed", r.get("errors"))
        self.assertEqual(r["permission_mode"], "read-only")
        self.assertTrue(r["thread_id"])
        self.assertEqual(r["changed_files"], [])
        self.assertTrue(r["final_message"])


if __name__ == "__main__":
    unittest.main()
