"""Real ClearML (Python SDK, offline mode — no server): a sandbox run is recorded as an offline session and read back.
Skipped when the `clearml` package is not installed."""
import _env  # noqa: F401  (must be first)
import importlib.util
import json
import time
import unittest
import zipfile

from backend import gitops, sandbox
from backend.config import save_config
from backend.integrations.experiment import ClearMLAdapter, clearml_dir

SCRIPT = ("import os, json\n"
          "for e in range(4): print(f'epoch {e} loss={1/(e+1):.3f} psnr={28+e}')\n"
          "json.dump({'psnr': 31.0, 'loss': 0.25}, open(os.path.join(os.environ['RUN_DIR'], 'metrics.json'), 'w'))\n"
          "print('CLEARML_OFFLINE_MODE=' + str(os.environ.get('CLEARML_OFFLINE_MODE')))\n")


def run(cmd):
    j = sandbox.start_job(cmd, "run", "clearml offline")
    t0 = time.time()
    while j.status == "running" and time.time() - t0 < 120:
        time.sleep(0.3)
    time.sleep(0.5)
    return j


@unittest.skipUnless(importlib.util.find_spec("clearml"), "pip install clearml to run the real ClearML offline test")
class ClearMLOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _env.fresh_project("clearml-offline")
        save_config({"clearml": {"enabled": True, "mode": "offline", "auto_record": False}})
        sandbox.save_settings({"mode": "local", "gpu": False, "timeout_s": 120})
        (sandbox.code_dir() / "t.py").write_text(SCRIPT, "utf-8")
        if gitops.git_exe():
            gitops.init()
            gitops.commit("baseline")

    def test_status_is_available_without_server(self):
        st = ClearMLAdapter().status()
        self.assertEqual(st.state, "available", st.detail)
        self.assertIn("offline", st.detail)

    def test_record_run_offline_and_read_back(self):
        j = run("python t.py")
        self.assertEqual(j.status, "done", j.tail(20))
        self.assertIn("CLEARML_OFFLINE_MODE=1", j.tail(20, "out"))  # scripts may call Task.init themselves
        ad = ClearMLAdapter()
        info = ad.record_run(j.id)
        self.assertEqual(info["mode"], "offline")
        self.assertRegex(info["task_id"], r"^offline-[0-9a-f]{32}$")
        z = clearml_dir().parent / info["session_zip"]
        self.assertTrue(z.is_file())
        with zipfile.ZipFile(z) as f:
            self.assertTrue(any(n.endswith("task.json") for n in f.namelist()))
        self.assertTrue(ad.record_run(j.id)["already_recorded"])  # never twice
        r = sandbox.get_run(j.id)
        self.assertEqual(r["clearml"]["task_id"], info["task_id"])
        got = ad.get_experiment(info["task_id"])
        self.assertEqual(got["run_id"], j.id)
        self.assertEqual(got["metrics"]["loss"], 0.25)
        self.assertEqual(got["points"]["loss"], 4)
        if gitops.git_exe():
            self.assertEqual(got["script"]["commit"], r["git"]["sha"])  # the research code, not this app
        self.assertEqual(got["script"]["entry_point"], "python t.py")
        self.assertIn(info["task_id"], [s["id"] for s in ad.offline_sessions()])
        meta = json.loads((sandbox.runs_dir() / j.id / "provenance.json").read_text("utf-8"))
        self.assertEqual(meta["record"]["clearml_task_id"], info["task_id"])  # artifacts re-sealed with the task id

    def test_script_session_is_linked_instead_of_duplicated(self):
        j = run("python t.py")
        own = sandbox.runs_dir() / j.id / "clearml" / "offline"
        own.mkdir(parents=True)
        (own / ("offline-" + "c" * 32 + ".zip")).write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # empty zip
        info = ClearMLAdapter().record_run(j.id)
        self.assertEqual(info["task_id"], "offline-" + "c" * 32)
        self.assertEqual(info["source"], "training script")

    def test_auto_record_after_a_run(self):
        save_config({"clearml": {"auto_record": True}})
        try:
            j = run("python t.py")
            t0 = time.time()
            while not (sandbox.get_run(j.id).get("clearml") or {}).get("task_id") and time.time() - t0 < 90:
                time.sleep(1)
            self.assertTrue(sandbox.get_run(j.id)["clearml"]["task_id"].startswith("offline-"))
        finally:
            save_config({"clearml": {"auto_record": False}})

    def test_api(self):
        import warnings
        warnings.filterwarnings("ignore")
        from fastapi.testclient import TestClient
        from backend.app import app
        c = TestClient(app)
        sessions = c.get("/api/experiments/clearml/offline").json()["sessions"]
        if sessions:
            self.assertEqual(c.get(f"/api/experiments/clearml/{sessions[0]['id']}").status_code, 200)
        self.assertEqual(c.get("/api/experiments/clearml/offline-" + "d" * 32).status_code, 409)
        self.assertEqual(c.post("/api/experiments/clearml/import", json={"run_id": "../x"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
