"""Real execution (no mocks): a job in the local sandbox → metrics, environment, git commit, provenance seal."""
import _env  # noqa: F401  (must be first)
import json
import textwrap
import time
import unittest

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
    @classmethod
    def setUpClass(cls):
        _env.fresh_project("e2e")
        sandbox.save_settings({"mode": "local", "gpu": False, "timeout_s": 300})  # hermetic: the GPU gate has its own tests
        import base64
        (sandbox.code_dir() / "train.py").write_text(SCRIPT % base64.b64encode(tiny_png()).decode(), "utf-8")
        if gitops.git_exe():
            gitops.init()
            gitops.commit("baseline")



if __name__ == "__main__":
    unittest.main()
