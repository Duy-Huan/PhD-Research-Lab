"""ClearML offline recording: the real SDK (worker subprocess, no server) when installed, and every failure path."""
import _env  # noqa: F401  (must be first)
import importlib.util
import json
import subprocess
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from backend.core.config import load_config, save_config
from backend.execution import sandbox, tracker as CM
from backend.execution.tools import IntegrationError

SCRIPT = ("import os, json\n"
          "for e in range(3): print(f'epoch {e} loss={1/(e+1):.3f}')\n"
          "json.dump({'loss': 0.33}, open(os.path.join(os.environ['RUN_DIR'], 'metrics.json'), 'w'))\n"
          "print('OFFLINE=' + str(os.environ.get('CLEARML_OFFLINE_MODE')))\n")


def finished_run() -> str:
    (sandbox.code_dir() / "t.py").write_text(SCRIPT, "utf-8")
    j = sandbox.start_job("python t.py", "run", "clearml")
    t0 = time.time()
    while j.status == "running" and time.time() - t0 < 120:
        time.sleep(0.2)
    time.sleep(0.3)
    return j.id


class ClearMLOffline(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("clearml")
        sandbox.save_settings({"mode": "local", "gpu": False, "timeout_s": 120})
        self.addCleanup(save_config, {"clearml": {"enabled": True, "auto_record": False}})

    @unittest.skipUnless(importlib.util.find_spec("clearml"), "pip install clearml to record a real offline session")
    def test_real_offline_session(self):
        rid = finished_run()
        self.assertIn("OFFLINE=1", "\n".join(x[2] for x in sandbox.JOBS[rid].lines))  # the run itself may use Task.init
        info = CM.record_run(rid)
        self.assertEqual(info["mode"], "offline")
        self.assertTrue(info["task_id"])
        self.assertTrue(info["session_zip"].endswith(".zip"), info)
        self.assertTrue((CM.data_dir() / info["session_zip"]).is_file())
        self.assertEqual(sandbox.get_run(rid)["clearml"]["task_id"], info["task_id"])
        self.assertTrue(CM.record_run(rid)["already_recorded"])

    def test_session_written_by_the_training_script_is_linked(self):
        rid = finished_run()
        z = sandbox.runs_dir() / rid / "clearml" / "offline" / "offline-abc.zip"
        z.parent.mkdir(parents=True)
        z.write_bytes(b"PK")
        info = CM.record_run(rid)
        self.assertEqual((info["task_id"], info["source"]), ("offline-abc", "training script"))

    def test_worker_results_and_errors(self):
        rid = finished_run()
        ok = SimpleNamespace(returncode=0, stdout='noise\n@@RESULT@@{"task_id": "t1", "session_zip": ""}\nmore', stderr="")
        with mock.patch.object(subprocess, "run", return_value=ok) as run:
            info = CM.record_run(rid, "P")
        self.assertEqual((info["task_id"], info["session_zip"]), ("t1", ""))
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual((payload["cmd"], payload["args"]["project"]), ("record_run", "P"))
        cases = [SimpleNamespace(returncode=1, stdout='@@ERROR@@{"error": "boom"}', stderr=""),
                 SimpleNamespace(returncode=3, stdout="", stderr="trace"), SimpleNamespace(returncode=3, stdout=None, stderr=None)]
        for r, msg in zip(cases, ("ClearML: boom", "code 3: trace", "no output")):
            with mock.patch.object(subprocess, "run", return_value=r), self.assertRaisesRegex(IntegrationError, msg):
                CM.run_worker("probe", {})
        for exc, msg in ((subprocess.TimeoutExpired("x", 1), "timed out"), (OSError("denied"), "Could not start")):
            with mock.patch.object(subprocess, "run", side_effect=exc), self.assertRaisesRegex(IntegrationError, msg):
                CM.run_worker("probe", {})
        with mock.patch.object(subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout='@@RESULT@@{"task_id": "t2", "session_zip": "C:/elsewhere/s.zip"}', stderr="")):
            self.assertIn("elsewhere", CM.record_run(finished_run())["session_zip"])  # outside the project: absolute

    def test_auto_record_switches_and_error_pointer(self):
        rid = finished_run()
        with mock.patch.object(CM, "record_run") as rec:
            save_config({"clearml": {"enabled": True, "auto_record": False}})
            CM.auto_record(rid)
            save_config({"clearml": {"auto_record": True}})
            with mock.patch.object(importlib.util, "find_spec", return_value=None):
                CM.auto_record(rid)
            rec.assert_not_called()
            with mock.patch.object(importlib.util, "find_spec", return_value=object()):
                CM.auto_record(rid)
            rec.assert_called_once_with(rid, "PhD Research Lab")
        with mock.patch.object(importlib.util, "find_spec", return_value=object()), \
                mock.patch.object(CM, "run_worker", side_effect=IntegrationError("no SDK")):
            CM.auto_record(rid)
        self.assertIn("no SDK", sandbox.get_run(rid)["clearml"]["error"])
        CM._store_pointer(rid, {"mode": "offline", "task_id": "t9"})
        CM._store_pointer(rid, {"error": "later failure"})  # never overwrites a recorded session
        self.assertEqual(sandbox.get_run(rid)["clearml"]["task_id"], "t9")

    def test_pointer_on_damaged_or_missing_record_and_without_provenance(self):
        rid = finished_run()
        f = sandbox.runs_dir() / rid / "run.json"
        f.write_text("{damaged", "utf-8")
        save_config({"provenance": {"enabled": False}})
        try:
            CM._store_pointer(rid, {"mode": "offline", "task_id": "t3"})
        finally:
            save_config({"provenance": {"enabled": True}})
        self.assertEqual(json.loads(f.read_text("utf-8"))["clearml"]["task_id"], "t3")
        CM._store_pointer("ghost-run", {"error": "x"})
        self.assertTrue((sandbox.runs_dir() / "ghost-run" / "run.json").is_file())

    def test_run_env(self):
        self.assertEqual(CM.run_env("/runs/r1/")["CLEARML_CACHE_DIR"], "/runs/r1/clearml")
        cfg = load_config()
        cfg["clearml"]["enabled"] = False
        self.assertEqual(CM.run_env("/runs/r1", cfg), {})


if __name__ == "__main__":
    unittest.main()
