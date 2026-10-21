import _env  # noqa: F401  (must be first)
import json
import os
import subprocess
import sys
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

from backend.execution import deps, envs, sandbox  # noqa: E402
from backend.app import app  # noqa: E402


class DependencyDetection(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("deps34")
        self.root = sandbox.code_dir()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")

    def test_imports_mapped_stdlib_and_local_excluded(self):
        self.write("train.py", "import os, json\nimport cv2\nfrom sklearn.metrics import mean_squared_error\nimport torch.nn as nn\n"
                               "from models.net import Net\nfrom . import helper\nimport utils\n")
        self.write("models/__init__.py", "")
        self.write("models/net.py", "import numpy as np\n")
        self.write("utils.py", "import yaml\n")
        self.write("notebooks/a.ipynb", json.dumps({"cells": [{"cell_type": "code", "source": ["%matplotlib inline\n", "import seaborn as sns\n"]},
                                                              {"cell_type": "markdown", "source": ["import notcode"]}]}))
        self.write(".venv/lib/x.py", "import shouldbeignored\n")
        plan = deps.detect(self.root)
        pip = {i["pip"] for i in plan["imports"]}
        self.assertEqual(pip, {"opencv-python", "scikit-learn", "torch", "numpy", "PyYAML", "seaborn"})
        self.assertEqual(plan["gpu_frameworks"], ["torch"])

    def test_declared_files(self):
        self.write("requirements.txt", "numpy==1.26.4\n")
        self.write("pyproject.toml", '[project]\nname="x"\ndependencies=["einops>=0.7"]\n')
        self.write("environment.yml", "dependencies:\n  - python=3.11\n  - scipy\n  - pip:\n    - timm==1.0.9\n")
        plan = deps.detect(self.root)
        self.assertEqual(plan["requirements_files"], ["requirements.txt"])
        self.assertIn("einops>=0.7", plan["declared"])
        self.assertIn("scipy", plan["declared"])
        self.assertIn("timm==1.0.9", plan["declared"])

    def test_write_is_idempotent_and_gitignored(self):
        self.write("a.py", "import tqdm\n")
        deps.write(self.root)
        deps.write(self.root)
        self.assertTrue((self.root / ".phdlab" / "ensure_deps.py").exists())
        self.assertEqual((self.root / ".gitignore").read_text("utf-8").count(".phdlab/"), 1)

    def _ensure(self, plan, extra_env=None):
        d = self.root / ".phdlab"
        d.mkdir(exist_ok=True)
        (d / "deps.json").write_text(json.dumps(plan), "utf-8")
        (d / "ensure_deps.py").write_text(deps.ENSURE, "utf-8")
        env = {**os.environ, "PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1", **(extra_env or {})}
        return subprocess.run([sys.executable, str(d / "ensure_deps.py")], capture_output=True, text=True, cwd=str(self.root), env=env, timeout=300)

    def test_ensure_present_and_satisfied_requirements_need_no_network(self):
        import importlib.metadata as md
        self.write("requirements.txt", f"pip=={md.version('pip')}\n")
        r = self._ensure({"requirements_files": ["requirements.txt"], "declared": [], "imports": [{"module": "json", "pip": "json"}]})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("all dependencies present", r.stdout)
        self.assertNotIn("pip install", r.stdout)

    def test_ensure_reports_what_cannot_be_installed(self):
        r = self._ensure({"requirements_files": [], "declared": [], "imports": [{"module": "phdlab_does_not_exist", "pip": "phdlab-does-not-exist"}]})
        self.assertEqual(r.returncode, 3)
        self.assertIn("could not install: phdlab-does-not-exist", r.stdout)


class Environments(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("envs34")

    def test_discovery_finds_the_running_python(self):
        ps = envs.discover_pythons(force=True)
        self.assertTrue(any(Path(p["path"]).resolve() == Path(sys.executable).resolve() for p in ps))
        self.assertFalse(any("WindowsApps" in p["path"] for p in ps))
        self.assertIn("jupyterlab", ps[0])


    def test_auto_choice(self):
        s = {"mode": "auto", "gpu": True}
        gpu_plan = {"gpu_frameworks": ["torch"]}
        with mock.patch("backend.execution.sandbox.docker_exe", return_value="docker"), mock.patch("backend.execution.sandbox.docker_running", return_value=True), \
                mock.patch("backend.execution.envs.gpu_present", return_value=True):
            self.assertEqual(envs.choose(s, gpu_plan)[0], "docker")
            self.assertEqual(envs.choose(s, {"gpu_frameworks": []})[0], "local")
            self.assertEqual(envs.choose({**s, "gpu": False}, gpu_plan)[0], "local")
            self.assertEqual(envs.choose({**s, "mode": "local"}, gpu_plan), ("local", "chosen in the environment settings"))
        with mock.patch("backend.execution.sandbox.docker_exe", return_value=None):
            self.assertEqual(envs.choose(s, gpu_plan), ("local", "Docker is not running"))

    def test_python_settings(self):
        with self.assertRaises(sandbox.SandboxError):
            sandbox.save_settings({"python_base": "C:/definitely/not/python.exe"})
        with self.assertRaises(sandbox.SandboxError):
            sandbox.save_settings({"torch_index": "http://insecure.example"})
        s = sandbox.save_settings({"python_mode": "existing", "python_base": sys.executable})
        self.assertEqual(s["python_mode"], "existing")
        self.assertEqual(sandbox.local_python_info()["python"], sys.executable)
        self.assertEqual(sandbox._local_python(), sys.executable)
        sandbox.save_settings({"python_mode": "venv", "python_base": ""})
        self.assertTrue(sandbox.local_python_info()["python"].startswith(str(sandbox.sb_dir() / "venv")))

    def test_run_installs_then_runs_in_one_job(self):
        sandbox.save_settings({"mode": "local", "gpu": False, "python_mode": "existing", "python_base": sys.executable})
        (sandbox.code_dir() / "requirements.txt").write_text("", "utf-8")
        (sandbox.code_dir() / "main.py").write_text("print('RESULT ran')\n", "utf-8")
        job = sandbox.start_job("python main.py", "run", "deps")
        t0 = time.time()
        while job.status == "running" and time.time() - t0 < 120:
            time.sleep(0.3)
        out = job.tail(50, "out")
        self.assertEqual(job.status, "done", out + job.tail(20, "err"))
        self.assertLess(out.index("[deps] all dependencies present"), out.index("RESULT ran"))
        self.assertEqual(job.meta["deps"]["requirements_files"], ["requirements.txt"])
        sandbox.save_settings({"auto_deps": False})
        job = sandbox.start_job("python main.py", "run", "nodeps")
        while job.status == "running":
            time.sleep(0.3)
        self.assertNotIn("[deps]", job.tail(50, "out"))


class EnvApiAndIntegrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app)

    def setUp(self):
        _env.fresh_project("envapi34")






if __name__ == "__main__":
    unittest.main()
