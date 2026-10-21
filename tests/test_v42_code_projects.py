"""v4.2 code projects: code/ is the root of code projects; every editor / environment action needs an open project."""
import _env  # noqa: F401  (must be first)
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.execution import code_projects as CP, gitops, sandbox
from backend.core import config
from backend.app import app
from backend.execution import vscode as W


class Registry(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("cp-" + self._testMethodName[:30], code_project=None)


    def test_migration_of_the_flat_layout_is_a_rename(self):
        root = config.data_dir() / "code"
        root.mkdir(parents=True, exist_ok=True)
        (root / "train.py").write_text("print(1)", "utf-8")
        (root / "sub").mkdir()
        lst = CP.list_projects()
        self.assertEqual(lst["active"], "main")
        self.assertEqual(lst["migrated"]["entries"], ["sub", "train.py"])
        self.assertTrue((root / "main" / "train.py").exists())
        self.assertEqual(CP.info("main")["sandbox"], "legacy")
        self.assertEqual(CP.sandbox_dir(CP.active()), config.data_dir() / "sandbox")  # v4.1 settings + venv stay in use

    def test_migration_when_a_main_folder_exists(self):
        root = config.data_dir() / "code"
        (root / "main").mkdir(parents=True)
        self.assertTrue(CP.list_projects()["active"].startswith("legacy-"))

    def test_corrupt_and_invalid_registry(self):
        root = CP.root()
        (root / CP.REGISTRY).write_text("{not json", "utf-8")
        self.assertEqual(CP.list_projects()["projects"], [])
        self.assertTrue(list(root.glob(CP.REGISTRY + ".corrupt-*")))
        CP._CACHE.clear()
        (root / CP.REGISTRY).write_text(json.dumps({"projects": []}), "utf-8")
        self.assertEqual(CP.list_projects()["projects"], [])

    def test_names(self):
        for bad in ("", "-x", "a/b", "con", "x" * 65, "trail."):
            with self.assertRaises(CP.CodeProjectError):
                CP.valid_name(bad)
        self.assertEqual(CP.valid_name(" exp_1.v2 "), "exp_1.v2")

    def test_create_open_rename_delete(self):
        with mock.patch.object(gitops, "git_exe", return_value=None):
            p = CP.create("exp1", "denoising", settings={"gpu": False, "memory_gb": 4})
        self.assertIn("Git is not installed", " ".join(p["notes"]))
        self.assertTrue(p["active"])
        self.assertTrue(p["vscode_settings"])
        self.assertEqual(sandbox.load_settings()["memory_gb"], 4)
        self.assertTrue(str(sandbox.sb_dir()).endswith(p["id"]))
        self.assertIn("# exp1", (CP.root() / "exp1" / "README.md").read_text("utf-8"))
        with self.assertRaises(CP.CodeProjectError):
            CP.create("exp1")
        with mock.patch.object(gitops, "init", side_effect=gitops.GitError("boom")), mock.patch.object(gitops, "git_exe", return_value="git"):
            q = CP.create("exp2", vscode=False, seed=False)
        self.assertIn("git init failed: boom", q["notes"])
        self.assertEqual(sandbox.load_settings()["memory_gb"], 8)       # every project has its own settings
        self.assertNotEqual(sandbox.container_name(), CP.container_for(CP.info("exp1")))
        CP.open_project("exp1")
        self.assertEqual(sandbox.code_dir().name, "exp1")
        (CP.root() / "loose").mkdir()
        self.assertEqual([u["name"] for u in CP.list_projects()["unregistered"]], ["loose"])
        self.assertEqual(CP.open_project("loose")["description"], "Registered from an existing folder")
        with self.assertRaises(CP.CodeProjectError):
            CP.open_project("ghost")
        with self.assertRaises(CP.CodeProjectError):
            CP.info("ghost")
        (CP.root() / "exp2").rename(CP.root() / "exp2-moved")
        with self.assertRaises(CP.CodeProjectError):
            CP.open_project("exp2")
        (CP.root() / "exp2-moved").rename(CP.root() / "exp2")
        CP.open_project("exp1")
        r = CP.rename("exp1", "exp1b")
        self.assertTrue(r["active"])
        CP.rename("exp2", "exp2b")
        for args in (("ghost", "x"), ("exp1b", "loose")):
            with self.assertRaises(CP.CodeProjectError):
                CP.rename(*args)
        with mock.patch("os.replace", side_effect=OSError("in use")), self.assertRaises(CP.CodeProjectError):
            CP.rename("exp1b", "exp1c")
        with self.assertRaises(CP.CodeProjectError):
            CP.delete("exp1b", "nope")
        with self.assertRaises(CP.CodeProjectError):
            CP.delete("ghost", "ghost")
        with mock.patch.object(sandbox, "docker", return_value=(0, "")) as dk:
            d = CP.delete("exp1b", "exp1b", remove_container=True)
        self.assertTrue(d["container_removed"])
        self.assertIn("rm", dk.call_args[0][0])
        self.assertTrue(Path(d["trash"]).exists())
        self.assertIsNone(CP.active())
        import shutil
        shutil.rmtree(CP.root() / "exp2b")
        self.assertEqual(CP.delete("exp2b", "exp2b")["trash"], "")
        CP.open_project("loose")
        self.assertEqual(CP.close()["active"], None)

    def test_active_with_missing_folder_is_none(self):
        CP.create("gone", git=False, vscode=False)
        import shutil
        shutil.rmtree(CP.root() / "gone")
        self.assertIsNone(CP.active())

    def test_sync_vscode(self):
        CP.create("v", git=False, vscode=False)
        f = CP.root() / "v" / ".vscode" / "settings.json"
        r = CP.sync_vscode()
        self.assertTrue(r["written"])
        self.assertFalse(CP.sync_vscode()["written"])
        f.write_text(json.dumps({"editor.tabSize": 2}), "utf-8")
        CP.sync_vscode()
        d = json.loads(f.read_text("utf-8"))
        self.assertEqual(d["editor.tabSize"], 2)
        self.assertIn("python.defaultInterpreterPath", d)
        f.write_text("// comment\n{}", "utf-8")
        self.assertFalse(CP.sync_vscode()["written"])
        f.write_text("", "utf-8")
        self.assertTrue(CP.sync_vscode()["written"])



class SandboxPerProject(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("cps-" + self._testMethodName[:30])

    def test_container_label_mismatch_recreates(self):
        calls = []

        def fake_docker(args, timeout=60):
            calls.append(args)
            if args[0] == "inspect":
                d = {"State": {"Running": True}, "HostConfig": {}, "Config": {"Image": "img", "Labels": {"phdlab.code": "other"}},
                     "Id": "abc", "Mounts": []}
                return (0, json.dumps(d)) if len(calls) == 1 else (1, "")
            if args[0] == "image":
                return 0, "sha"
            return 0, ""
        sandbox.save_settings({"image": "img", "gpu": False, "memory_gb": 0, "cpus": 0, "shm_gb": 0})
        with mock.patch.object(sandbox, "docker", fake_docker):
            sandbox.ensure_container()
        self.assertEqual(calls[1][:2], ["rm", "-f"])
        run = next(a for a in calls if a[0] == "run")
        self.assertIn(f"phdlab.code={sandbox._code_label()}", run)

    def test_job_remembers_its_code_project(self):
        sandbox.save_settings({"mode": "local", "python_mode": "existing", "python_base": sys.executable, "auto_deps": False,
                               "gpu": False})
        (sandbox.code_dir() / "m.py").write_text("import json, os\nprint('acc=0.9')\n"
                                                 "open(os.path.join(os.environ['RUN_DIR'], 'x.png'), 'wb').write(b'1')\n", "utf-8")
        job = sandbox.run_blocking("python m.py", 60, "run", "t")
        self.assertEqual(job.meta["code_project"], "main")
        self.assertEqual(job.meta["code_dir"], str(sandbox.code_dir()))
        self.assertEqual(job.status, "done")
        j = sandbox.Job("run", "x")
        j.run_dir = sandbox.runs_dir() / "r-x"
        j.run_dir.mkdir()
        self.assertEqual(sandbox.collect_run(j)["metrics"], {})  # no meta: falls back to the active project

    def test_stop_job_uses_the_jobs_container(self):
        j = sandbox.Job("run", "sleep")
        j.status, j.mode, j.meta = "running", "docker", {"container": "phdlab-x-cpold"}
        j.proc = mock.Mock(pid=1)
        sandbox.JOBS[j.id] = j
        with mock.patch.object(sandbox, "docker", return_value=(0, "")) as dk, mock.patch("subprocess.run"):
            sandbox.stop_job(j.id)
        self.assertEqual(dk.call_args_list[0][0][0][1], "phdlab-x-cpold")
        sandbox.JOBS.pop(j.id)



if __name__ == "__main__":
    unittest.main()
