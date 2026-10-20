"""Real execution (no mocks): a job in the local sandbox → metrics, environment, git commit, provenance seal."""
import _env  # noqa: F401  (must be first)
import json
import textwrap
import time
import unittest

from backend import gitops, provenance, sandbox
from test_provenance_critic import tiny_png

SCRIPT = textwrap.dedent('''
    import json, os, base64
    rd = os.environ["RUN_DIR"]
    for e in range(3):
        print(f"epoch {e} loss={1.0/(e+1):.4f} psnr={30+e}")
    json.dump({"psnr": 32.0, "loss": 0.3333}, open(os.path.join(rd, "metrics.json"), "w"))
    open(os.path.join(rd, "curve.png"), "wb").write(base64.b64decode("%s"))
    open(os.path.join(rd, "table.csv"), "w").write("a,b\\n1,2\\n")
''')


class SandboxE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _env.fresh_project("e2e")
        sandbox.save_settings({"mode": "local", "gpu": False, "timeout_s": 300})  # hermetic: the GPU gate has its own tests
        import base64
        (sandbox.code_dir() / "train.py").write_text(SCRIPT % base64.b64encode(tiny_png()).decode(), "utf-8")
        if gitops.git_exe():
            gitops.init()
            gitops.commit("baseline")

    def test_run_is_traceable_and_sealed(self):
        job = sandbox.start_job("python train.py", "run", "e2e")
        t0 = time.time()
        while job.status == "running" and time.time() - t0 < 240:
            time.sleep(0.3)
        time.sleep(0.5)
        self.assertEqual(job.status, "done", job.tail(40))
        r = sandbox.get_run(job.id)
        self.assertEqual(r["metrics"]["psnr"], 32.0)
        self.assertEqual(r["environment"]["mode"], "local")
        if gitops.git_exe():
            self.assertRegex(r["git"]["sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(r["provenance"]["sealed"], 2)
        png = (sandbox.runs_dir() / job.id / "curve.png").read_bytes()
        meta = provenance.read_bytes("curve.png", png)
        self.assertEqual(meta["run_id"], job.id)
        self.assertEqual(meta["git_sha"], (r.get("git") or {}).get("sha", ""))
        self.assertTrue((sandbox.runs_dir() / job.id / "table.csv").read_text("utf-8").startswith("# Provenance: run_id=" + job.id))
        manifest = json.loads((sandbox.runs_dir() / job.id / "provenance.json").read_text("utf-8"))
        self.assertIn("curve.png", manifest["files"])
        res = provenance.inspect("curve.png", png)
        self.assertTrue(res["found"])
        self.assertEqual(res["run"]["metrics"]["psnr"], 32.0)


if __name__ == "__main__":
    unittest.main()
