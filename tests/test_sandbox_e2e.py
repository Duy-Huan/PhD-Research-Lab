"""Real execution (no mocks): a job in the local sandbox → metrics, environment, git commit, provenance seal."""
import _env  # noqa: F401  (must be first)
import json
import textwrap
import time
import unittest
import sys

from backend.execution import gitops, sandbox
from backend.knowledge import provenance
from test_provenance import tiny_png

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
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("e2e")
        sandbox.save_settings({"mode": "local", "gpu": False, "timeout_s": 30,
                               "python_mode": "existing", "python_base": sys.executable, "auto_deps": False})
        import base64
        (sandbox.code_dir() / "train.py").write_text(SCRIPT % base64.b64encode(tiny_png()).decode(), "utf-8")
        if gitops.git_exe():
            gitops.init()
            gitops.commit("baseline")

    def test_run_is_traceable_and_sealed(self):
        """Actual CPU process; declared synthetic numbers test provenance, not science."""
        job=sandbox.run_blocking('python train.py',timeout=30,title='Synthetic provenance regression')
        self.assertEqual(job.status,'done',job.tail(40))
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and not (sandbox.runs_dir()/job.id/'provenance.json').exists():time.sleep(.05)
        result=sandbox.get_run(job.id)
        self.assertEqual(result['metrics']['psnr'],32.0)
        self.assertEqual(result['environment']['mode'],'local')
        self.assertEqual(result['provenance']['sealed'],2)
        self.assertEqual(result['provenance']['errors'],[])
        if gitops.git_exe():self.assertRegex(result['git']['sha'],r'^[0-9a-f]{40}$')
        raw=(sandbox.runs_dir()/job.id/'curve.png').read_bytes()
        record=provenance.read_bytes('curve.png',raw)
        self.assertEqual(record['run_id'],job.id)
        self.assertEqual(record['git_sha'],result.get('git',{}).get('sha',''))
        self.assertTrue((sandbox.runs_dir()/job.id/'table.csv').read_text('utf-8').startswith('# Provenance: run_id='+job.id))
        manifest=json.loads((sandbox.runs_dir()/job.id/'provenance.json').read_text('utf-8'))
        self.assertIn('curve.png',manifest['files'])
        self.assertEqual(manifest['files']['curve.png'],provenance.sha256(raw))
        # The old provenance.inspect API was removed during consolidation.
        # Resolve the embedded run ID through the current canonical run store.
        self.assertEqual(sandbox.get_run(record['run_id'])['metrics']['psnr'],32.0)



if __name__ == "__main__":
    unittest.main()
