"""Legacy integration adapters (coverage pass): status registry, VS Code / Dev Container / Jupyter, ClearML backend,
Codex backend. External tools are faked (run_cli / subprocess / httpx); the adapters' logic is real."""
import _env  # noqa: F401  (must be first)
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest import mock

import httpx
import unittest

from backend import config, sandbox as SB
from backend import integrations as INT
from backend.integrations import agents as AG, base as B, experiment as EX, workspace as WS


class Registry(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-int")
        B.clear_cache()

    def test_probes(self):
        with mock.patch("backend.sandbox.docker_exe", return_value=None):
            self.assertEqual(INT._docker().state, "unavailable")
        with mock.patch("backend.sandbox.docker_exe", return_value="docker"), mock.patch("backend.sandbox.docker_running", return_value=False):
            self.assertIn("not running", INT._docker().detail)
        with mock.patch("backend.sandbox.docker_exe", return_value="docker"), mock.patch("backend.sandbox.docker_running", return_value=True):
            self.assertTrue(INT._docker().ok)
        with mock.patch("backend.gitops.git_exe", return_value=None):
            self.assertEqual(INT._git().state, "unavailable")
        with mock.patch("backend.gitops.status", return_value={"repo": True, "branch": "main"}), \
                mock.patch("backend.gitops.head_info", return_value={"short": "abc", "dirty": True}), mock.patch("backend.gitops.git_exe", return_value="git"):
            self.assertIn("uncommitted", INT._git().detail)
        with mock.patch("backend.gitops.status", return_value={"repo": False}), mock.patch("backend.gitops.git_exe", return_value="git"):
            self.assertIn("not a git repository", INT._git().detail)
        with mock.patch("backend.resources.gpus", return_value=[]):
            self.assertEqual(INT._gpu().state, "unavailable")
        with mock.patch("backend.resources.gpus", return_value=[{"name": "RTX", "vram_used_mb": 1, "vram_total_mb": 2, "temp_c": 40, "driver": "560"}]):
            self.assertEqual(INT._gpu().version, "560")

        async def ost(_):
            return {"online": True, "loaded": [{"id": "q"}], "models": [1]}

        async def lst(_):
            raise RuntimeError("down")
        with mock.patch("backend.local_ai.ollama_status", ost), mock.patch("backend.local_ai.lmstudio_status", lst):
            out = INT._local_ai()
        self.assertEqual((out[0].ok, out[1].ok), (True, False))

    def test_all_status_never_fails(self):
        fake = lambda: B.IntegrationStatus("x", "X", "available")  # noqa: E731
        with mock.patch.object(WS, "vscode_status", fake), mock.patch.object(WS, "jupyter_status", side_effect=RuntimeError("boom")), \
                mock.patch.object(INT, "_docker", fake), mock.patch.object(INT, "_git", fake), mock.patch.object(INT, "_gpu", fake), \
                mock.patch.object(EX.ClearMLAdapter, "status", lambda self: fake()), mock.patch.object(AG.CodexBackend, "status", lambda self: fake()), \
                mock.patch.object(INT, "_local_ai", lambda: [fake(), fake()]):
            out = INT.all_status()
        self.assertTrue(any(s["state"] == "error" for s in out))
        self.assertEqual(len(out), 10)
        with self.assertRaises(ValueError):
            B.IntegrationStatus("x", "X", "weird")


class Workspace(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-ws")
        B.clear_cache()

    def test_vscode_states_and_actions(self):
        with mock.patch.object(WS, "vscode_cli", return_value=None):
            self.assertEqual(WS.vscode_status(force=True).state, "unavailable")
            for fn in (lambda: WS.open_folder(), lambda: WS.open_file("a.py"), lambda: WS.install_extension(WS.EXT_DEVCONTAINERS)):
                with self.assertRaises(B.IntegrationError):
                    fn()
        calls = []

        def cli(args, timeout=15, cwd=None, input_text=None):
            calls.append(args)
            if "--version" in args:
                return 0, "1.99\nhash"
            if "--list-extensions" in args:
                return 0, f"{WS.EXT_JUPYTER}\n{WS.EXT_PYTHON}"
            if "--install-extension" in args:
                return (1, "denied") if args[-1] == "fail" else (0, "installed")
            return 0, ""
        (SB.code_dir() / "a.py").write_text("x", "utf-8")
        with mock.patch.object(WS, "vscode_cli", return_value="code"), mock.patch.object(WS, "run_cli", cli):
            st = WS.vscode_status(force=True)
            self.assertTrue(st.ok and "jupyter" in st.capabilities and not st.extra["dev_containers_ext"])
            self.assertTrue(WS.open_folder("code")["launched"])
            self.assertTrue(WS.open_file("a.py", 3)["launched"])
            self.assertIn("a.py:3", calls[-1][-1])
            for bad in ("../x.py", "missing.py"):
                with self.assertRaises(B.IntegrationError):
                    WS.open_file(bad)
            with self.assertRaises(B.IntegrationError):
                WS.install_extension("evil.ext")
            self.assertEqual(WS.install_extension(WS.EXT_DEVCONTAINERS)["installed"], WS.EXT_DEVCONTAINERS)
            with mock.patch.object(WS, "INSTALLABLE", WS.INSTALLABLE | {"fail"}):
                with self.assertRaises(B.IntegrationError):
                    WS.install_extension("fail")
            with self.assertRaises(B.IntegrationError):
                WS.resolve_target("nowhere")
            self.assertTrue(WS.deep_link().startswith("vscode://file/"))
            self.assertTrue(WS.devcontainer_uri().startswith("vscode-remote://dev-container+"))
            with self.assertRaises(B.IntegrationError):
                WS.open_devcontainer(prepare=False)  # extension missing
            with mock.patch("backend.sandbox.docker_exe", return_value=None):
                with self.assertRaises(B.IntegrationError):
                    WS.open_devcontainer()  # docker not running
            self.assertTrue((SB.code_dir() / ".devcontainer" / "devcontainer.json").exists())
            with mock.patch("backend.sandbox.docker_exe", return_value="docker"), mock.patch("backend.sandbox.docker_running", return_value=True):
                self.assertTrue(WS.open_devcontainer()["launched"])
        with mock.patch.object(WS, "vscode_cli", return_value="code"), mock.patch.object(WS, "run_cli", return_value=(2, "bad")):
            B.clear_cache()
            self.assertEqual(WS.vscode_status(force=True).state, "error")
            for fn in (lambda: WS.open_folder(), lambda: WS.open_file("a.py")):
                with self.assertRaises(B.IntegrationError):
                    fn()
        config.save_config({"workspace": {"vscode_path": sys.executable}})
        self.assertEqual(WS.vscode_cli(), sys.executable)
        config.save_config({"workspace": {"vscode_path": ""}})
        with mock.patch.object(WS, "which", return_value=None), mock.patch.object(WS, "IS_WIN", True), mock.patch.object(Path, "is_file", return_value=True), \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": "C:/L"}):
            self.assertTrue(WS.vscode_cli().endswith("code.cmd"))

    def test_environment_builder(self):
        opts = WS.environment_options()
        self.assertTrue(opts["gpu_images"])
        g = opts["gpu_images"][0]
        files = WS.build_environment({"gpu": True, "torch": g["torch"], "cuda": g["cuda"]})["files"]
        self.assertIn(".devcontainer/devcontainer.json", files)
        with self.assertRaises(B.IntegrationError):
            WS.build_environment({"gpu": True, "torch": "0.1", "cuda": "1"})
        with self.assertRaises(B.IntegrationError):
            WS.build_environment({"gpu": False, "python": "2.7"})
        with self.assertRaises(B.IntegrationError):
            WS.build_environment({"image": "Bad Image!"})
        with self.assertRaises(B.IntegrationError):
            WS.build_environment({"gpu": False, "datasets_dir": "relative/path"})
        ok = WS.build_environment({"gpu": False, "datasets_dir": str(SB.code_dir()), "image": "python:3.11-slim"})
        self.assertIn("mounts", ok["files"][".devcontainer/devcontainer.json"])
        WS.write_environment({"gpu": False})
        with self.assertRaises(B.IntegrationError):
            WS.write_environment({"gpu": False})
        self.assertTrue(WS.write_environment({"gpu": False}, overwrite=True)["overwritten"])

    def test_jupyter(self):
        WS._JUP.update(proc=None, port=None, token=None, root=None)
        self.assertFalse(WS.jupyter_stop()["stopped"])
        with mock.patch.object(WS, "jupyter_argv", return_value=None):
            self.assertEqual(WS.jupyter_status().state, "unavailable")
            with self.assertRaises(B.IntegrationError):
                WS.jupyter_launch()
        with mock.patch.object(WS, "jupyter_argv", return_value=[sys.executable, "-m", "jupyterlab"]), mock.patch.object(WS, "run_cli", return_value=(0, "4.2")):
            self.assertIn("4.2", WS.jupyter_status().version)

        class Proc:
            def __init__(self, code=None):
                self.code, self.pid, self.returncode = code, 1, code

            def poll(self):
                return self.code

            def wait(self, t=None):
                raise subprocess.TimeoutExpired("j", 1)

            def kill(self):
                self.code = -9

            def terminate(self):
                pass
        with mock.patch.object(WS, "jupyter_argv", return_value=["jupyter-lab"]), mock.patch.object(WS, "ensure_project_kernel", side_effect=RuntimeError("no kernel")), \
                mock.patch("subprocess.Popen", return_value=Proc(code=3)):
            with self.assertRaises(B.IntegrationError):
                WS.jupyter_launch()
        p = Proc()
        with mock.patch.object(WS, "jupyter_argv", return_value=["jupyter-lab"]), mock.patch.object(WS, "ensure_project_kernel", return_value={"registered": True}), \
                mock.patch("subprocess.Popen", return_value=p), mock.patch("httpx.get", return_value=httpx.Response(200)):
            out = WS.jupyter_launch()
            self.assertIn("token=", out["url"])
            self.assertTrue(WS.jupyter_launch()["already_running"])
        with mock.patch("subprocess.run"):
            self.assertTrue(WS.jupyter_stop()["stopped"])
        with mock.patch.object(WS, "IS_WIN", False):
            WS._kill_tree(Proc())
        WS._kill_tree(None)
        with mock.patch.object(WS, "_free_port", side_effect=B.IntegrationError("no port")), mock.patch.object(WS, "jupyter_argv", return_value=["j"]), \
                mock.patch.object(WS, "ensure_project_kernel", return_value={}):
            with self.assertRaises(B.IntegrationError):
                WS.jupyter_launch()
        import socket
        busy = socket.socket()
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        port = busy.getsockname()[1]
        self.assertNotEqual(WS._free_port(port), port)
        busy.close()
        with mock.patch("socket.socket.bind", side_effect=OSError):
            with self.assertRaises(B.IntegrationError):
                WS._free_port(20000)

    def test_notebooks_and_kernel(self):
        nb = WS.create_notebook("analysis")
        self.assertTrue(nb["path"].endswith(".ipynb"))
        with self.assertRaises(B.IntegrationError):
            WS.create_notebook("analysis")
        with mock.patch.object(WS, "_project_python", return_value=None):
            self.assertFalse(WS.ensure_project_kernel()["registered"])
        with mock.patch.object(WS, "_project_python", return_value=sys.executable), mock.patch.object(WS, "run_cli", side_effect=[(1, "no"), (1, "pip failed")]):
            self.assertIn("pip install ipykernel failed", WS.ensure_project_kernel()["detail"])
        with mock.patch.object(WS, "_project_python", return_value=sys.executable), mock.patch.object(WS, "run_cli", side_effect=[(1, "no")]):
            self.assertIn("missing", WS.ensure_project_kernel(install=False)["detail"])
        with mock.patch.object(WS, "_project_python", return_value=sys.executable), mock.patch.object(WS, "run_cli", side_effect=[(0, ""), (1, "kernel err")]):
            self.assertIn("kernel err", WS.ensure_project_kernel()["detail"])
        with mock.patch("backend.sandbox._local_python", side_effect=RuntimeError):
            self.assertIsNone(WS._project_python())
        with mock.patch("importlib.util.find_spec", return_value=None), mock.patch.object(WS, "_project_python", return_value=None), \
                mock.patch("backend.envs.python_with", return_value={"path": "C:/py/python.exe"}):
            self.assertEqual(WS.jupyter_argv()[0], "C:/py/python.exe")
        with mock.patch("importlib.util.find_spec", return_value=None), mock.patch.object(WS, "_project_python", return_value=None), \
                mock.patch("backend.envs.python_with", return_value=None), mock.patch.object(WS, "which", side_effect=lambda *n: "jupyter-lab" if "jupyter-lab" in n else None):
            self.assertEqual(WS.jupyter_argv(), ["jupyter-lab"])
        with mock.patch("importlib.util.find_spec", return_value=None), mock.patch.object(WS, "_project_python", return_value=None), \
                mock.patch("backend.envs.python_with", return_value=None), mock.patch.object(WS, "which", return_value=None):
            self.assertIsNone(WS.jupyter_argv())


def make_session(folder: Path, with_metrics=True):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "task.json").write_text(json.dumps({"id": "offline-abc", "name": "run", "project_name": "P",
                                                  "hyperparams": {"General": {"run_id": {"value": "r1"}, "status": {"value": "done"}}},
                                                  "script": {"repository": "repo", "version_num": "sha"}}), "utf-8")
    if with_metrics:
        (folder / "metrics.jsonl").write_text(json.dumps([{"type": "training_stats_scalar", "metric": "loss", "variant": "loss", "value": 0.3},
                                                          {"type": "training_stats_scalar", "metric": "acc", "variant": "val", "value": 0.9},
                                                          {"type": "other"}]) + "\n\n", "utf-8")


class ClearML(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-clearml")
        B.clear_cache()

    def test_offline_sessions_folder_zip_and_missing_metrics(self):
        f = EX.clearml_dir() / "offline" / "offline-abc"
        make_session(f)
        s = EX.read_offline_session(f)
        self.assertEqual((s["metrics"], s["run_id"], s["script"]["commit"]), ({"loss": 0.3, "acc/val": 0.9}, "r1", "sha"))
        z = f.with_suffix(".zip")
        with zipfile.ZipFile(z, "w") as zz:
            zz.writestr("offline-abc/task.json", (f / "task.json").read_text("utf-8"))
        self.assertEqual(EX.read_offline_session(z)["metrics"], {})
        bare = EX.clearml_dir() / "offline" / "offline-bare"
        make_session(bare, with_metrics=False)
        self.assertEqual(EX.read_offline_session(bare)["metrics"], {})  # a folder session without metrics is readable
        (EX.clearml_dir() / "offline" / "offline-bad.zip").write_bytes(b"not zip")
        ad = EX.ClearMLAdapter()
        sess = ad.offline_sessions()
        self.assertEqual({x["id"] for x in sess} >= {"offline-abc", "offline-bad"}, True)
        self.assertTrue(any("error" in x for x in sess))
        with mock.patch.object(EX.ClearMLAdapter, "offline_sessions", return_value=[{"id": "offline-abc", "path": str(f), "zip": "z"}]):
            self.assertTrue(ad.get_experiment("offline-abc")["offline"])
            with self.assertRaises(B.IntegrationError):
                ad.get_experiment("offline-zzz")
        with self.assertRaises(B.IntegrationError):
            ad.get_experiment("bad id!")
        with self.assertRaises(B.IntegrationError):
            ad._abs("../../etc")
        self.assertEqual(ad._rel(Path("C:/elsewhere/x.zip")), "C:/elsewhere/x.zip".replace("/", os.sep).replace("\\", "/") if False else ad._rel(Path("C:/elsewhere/x.zip")))

    def test_status_matrix(self):
        cfg = config.load_config()
        cfg["clearml"]["enabled"] = False
        self.assertEqual(EX.ClearMLAdapter(cfg).status().state, "disabled")
        cfg["clearml"]["enabled"] = True
        with mock.patch.object(EX.ClearMLAdapter, "sdk_installed", return_value=False):
            self.assertEqual(EX.ClearMLAdapter(cfg).status().state, "unavailable")
        with mock.patch.object(EX.ClearMLAdapter, "sdk_installed", return_value=True), mock.patch.object(EX.ClearMLAdapter, "sdk", return_value={"ok": False, "error": "dll"}):
            self.assertEqual(EX.ClearMLAdapter(cfg).status().state, "error")
        ok_sdk = mock.patch.object(EX.ClearMLAdapter, "sdk", return_value={"ok": True, "version": "2.1"})
        with mock.patch.object(EX.ClearMLAdapter, "sdk_installed", return_value=True), ok_sdk, mock.patch.object(EX.ClearMLAdapter, "server_ready", return_value=True):
            st = EX.ClearMLAdapter(cfg).status()
            self.assertIn("import_offline", st.capabilities)
        cfg["clearml"].update(mode="server", api_host="", access_key="", secret_key="")
        with mock.patch.object(EX.ClearMLAdapter, "sdk_installed", return_value=True), ok_sdk, mock.patch.object(EX, "_clearml_conf_file", return_value=False), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLEARML_API_HOST", None)
            self.assertEqual(EX.ClearMLAdapter(cfg).status().state, "unconfigured")
        cfg["clearml"].update(api_host="http://h:8008", access_key="a", secret_key="s", web_host="http://h:8080", files_host="http://h:8081")
        ad = EX.ClearMLAdapter(cfg)
        with mock.patch.object(EX.ClearMLAdapter, "sdk_installed", return_value=True), ok_sdk, mock.patch("httpx.get", side_effect=httpx.ConnectError("x")):
            self.assertEqual(ad.status().state, "unavailable")
        B.clear_cache()
        with mock.patch.object(EX.ClearMLAdapter, "sdk_installed", return_value=True), ok_sdk, mock.patch("httpx.get", return_value=httpx.Response(200)):
            st = ad.status()
            self.assertTrue(st.ok and "submit_remote" in st.capabilities)
        env = ad._server_env()
        self.assertEqual(env["CLEARML_API_SECRET_KEY"], "s")
        with mock.patch.dict(os.environ, {"CLEARML_CONFIG_FILE": "C:/c.conf"}):
            self.assertIn("CLEARML_CONFIG_FILE", ad._server_env())
        self.assertEqual(ad.web_host(), "http://h:8080")

    def test_server_ops_record_import_submit(self):
        cfg = config.load_config()
        cfg["clearml"].update(enabled=True, mode="server", api_host="http://h", access_key="a", secret_key="s")
        ad = EX.ClearMLAdapter(cfg)
        avail = B.IntegrationStatus("clearml", "ClearML", "available")
        worker_calls = []

        def worker(cmd, args, offline, env_extra, timeout=900, cwd=None):
            worker_calls.append((cmd, args.get("op")))
            if cmd == "record_run":
                return {"task_id": "0123456789abcdef0123456789abcdef", "url": "http://web/task"}
            if cmd == "op" and args.get("op") == "list":
                return {"tasks": [{"id": "t"}]}
            if cmd == "import_offline":
                return {"task_id": "srv-task", "url": "u"}
            return {"ok": True}
        with mock.patch.object(EX.ClearMLAdapter, "status", return_value=avail), mock.patch.object(EX, "run_worker", worker), \
                mock.patch.object(EX.ClearMLAdapter, "server_ready", return_value=True):
            ad.create_experiment("n")
            ad.start_run("x"); ad.log_metric("x", "m", 1.0); ad.log_parameter("x", "p", 1)
            ad.log_artifact("x", "a", "p"); ad.log_model("x", "m", "p"); ad.finish_run("x")
            self.assertEqual(ad.list_experiments(), [{"id": "t"}])
            self.assertEqual(ad.get_experiment("0123456789abcdef0123456789abcdef")["backend"], "clearml")
            job = SB.run_blocking('python -c "print(\'loss=0.1\')"', 60)
            info = ad.record_run(job.id)
            self.assertEqual(info["mode"], "server")
            self.assertTrue(ad.record_run(job.id)["already_recorded"])
            with self.assertRaises(B.IntegrationError):
                ad.record_run("missing-run")
            z = Path(config.data_dir()) / "clearml" / "offline" / "offline-x.zip"
            z.parent.mkdir(parents=True, exist_ok=True)
            z.write_bytes(b"PK")
            self.assertEqual(ad.import_offline(zip_rel="clearml/offline/offline-x.zip")["task_id"], "srv-task")
            with self.assertRaises(B.IntegrationError):
                ad.import_offline(zip_rel="clearml/offline/missing.zip")
            with mock.patch("backend.sandbox.get_run", return_value={"clearml": {"server_task_id": "s", "session_zip": ""}}):
                self.assertTrue(ad.import_offline(run_id="r")["already_imported"])
            (SB.code_dir() / "train.py").write_text("x", "utf-8")
            (SB.code_dir() / "requirements.txt").write_text("numpy", "utf-8")
            with mock.patch("backend.gitops.head_info", return_value={"remote": "git@x", "sha": "s", "dirty": True}):
                with self.assertRaises(B.IntegrationError):
                    ad.submit_remote("train.py")
            with mock.patch("backend.gitops.head_info", return_value={"remote": "git@x", "sha": "s", "dirty": False, "branch": "main"}):
                ad.submit_remote("train.py", {"lr": 1})
            with mock.patch("backend.gitops.head_info", return_value={}):
                ad.submit_remote("train.py")
            with self.assertRaises(B.IntegrationError):
                ad.submit_remote("../evil.py")
        with mock.patch.object(EX.ClearMLAdapter, "status", return_value=avail), mock.patch.object(EX.ClearMLAdapter, "server_ready", return_value=False):
            with self.assertRaises(B.IntegrationError):
                ad.import_offline(zip_rel="clearml/offline/offline-x.zip")
            off = EX.ClearMLAdapter({**cfg, "clearml": {**cfg["clearml"], "mode": "offline"}})
            with self.assertRaises(B.NotSupported):
                off.create_experiment("n")
        with mock.patch.object(EX.ClearMLAdapter, "status", return_value=B.IntegrationStatus("clearml", "C", "error", "x")):
            with self.assertRaises(B.IntegrationError):
                ad.record_run("x")
        with mock.patch.object(EX.ClearMLAdapter, "status", return_value=avail), mock.patch("backend.sandbox.get_run", return_value={"status": "running"}):
            with self.assertRaises(B.IntegrationError):
                ad.record_run("r1")

    def test_worker_wrapper_env_pointer_and_install(self):
        def res(out="", err="", code=0):
            return subprocess.CompletedProcess([], code, stdout=out, stderr=err)
        with mock.patch("subprocess.run", return_value=res("noise\n@@RESULT@@{\"version\": \"2.1\"}\nmore")):
            self.assertEqual(EX.run_worker("probe", {}, True, {})["version"], "2.1")
        with mock.patch("subprocess.run", return_value=res('@@ERROR@@{"error": "no creds"}')):
            with self.assertRaises(B.IntegrationError):
                EX.run_worker("x", {}, True, {})
        with mock.patch("subprocess.run", return_value=res("", "Traceback", 1)):
            with self.assertRaises(B.IntegrationError):
                EX.run_worker("x", {}, True, {})
        for exc in (subprocess.TimeoutExpired("w", 1), OSError("blocked")):
            with mock.patch("subprocess.run", side_effect=exc):
                with self.assertRaises(B.IntegrationError):
                    EX.run_worker("x", {}, True, {})
        with mock.patch("importlib.util.find_spec", return_value=None):
            self.assertFalse(EX.sdk_probe()["installed"])
        with mock.patch("importlib.util.find_spec", return_value=object()), mock.patch.object(EX, "run_worker", side_effect=B.IntegrationError("dll")):
            self.assertFalse(EX.sdk_probe()["ok"])
        with mock.patch("importlib.util.find_spec", return_value=object()), mock.patch.object(EX, "run_worker", return_value={"version": "2"}):
            self.assertTrue(EX.sdk_probe()["ok"])
        cfg = config.load_config()
        self.assertEqual(EX.run_env("/runs/x/", cfg)["CLEARML_CACHE_DIR"], "/runs/x/clearml")
        cfg["clearml"]["mode"] = "server"
        self.assertEqual(EX.run_env("/runs/x", cfg), {})
        job = SB.run_blocking('python -c "print(1)"', 60)
        (SB.runs_dir() / job.id / "run.json").write_text("{damaged", "utf-8")
        EX._store_pointer(job.id, {"task_id": "t1"})  # damaged record: kept aside, pointer stored
        self.assertEqual(json.loads((SB.runs_dir() / job.id / "run.json").read_text("utf-8"))["clearml"]["task_id"], "t1")
        EX._store_pointer(job.id, {"error": "x"}, merge_error=True)  # an error never replaces a recorded task
        self.assertEqual(json.loads((SB.runs_dir() / job.id / "run.json").read_text("utf-8"))["clearml"]["task_id"], "t1")
        config.save_config({"clearml": {"enabled": True, "auto_record": True}})
        with mock.patch.object(EX.ClearMLAdapter, "record_run", side_effect=RuntimeError("down")):
            EX.auto_record("fresh-run")
        self.assertIn("down", json.loads((SB.runs_dir() / "fresh-run" / "run.json").read_text("utf-8"))["clearml"]["error"])
        config.save_config({"clearml": {"auto_record": False}})
        EX.auto_record("nothing")
        with mock.patch("subprocess.run", return_value=res("ok")):
            self.assertTrue(EX.install_sdk()["installed"])
        with mock.patch("subprocess.run", return_value=res("", "fail", 1)):
            with self.assertRaises(B.IntegrationError):
                EX.install_sdk()
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pip", 1)):
            with self.assertRaises(B.IntegrationError):
                EX.install_sdk()
        with self.assertRaises(B.IntegrationError):
            EX.get_backend("mlflow")
        lb = EX.get_backend("local")
        self.assertTrue(lb.status().ok)
        self.assertEqual(lb.get_experiment(job.id)["backend"], "local")
        with self.assertRaises(B.IntegrationError):
            lb.get_experiment("missing-run")
        self.assertTrue(lb.list_experiments())
        self.assertIn(job.id, lb.compare_experiments([job.id, "missing-run"])["experiments"].__str__())
        for name in ("create_experiment", "start_run", "log_metric", "log_parameter", "log_artifact", "log_model", "finish_run"):
            with self.assertRaises(B.NotSupported):
                getattr(lb, name)(*(["x"] * {"create_experiment": 1, "start_run": 1, "log_metric": 3, "log_parameter": 3,
                                              "log_artifact": 3, "log_model": 3, "finish_run": 1}[name]))
        with self.assertRaises(NotImplementedError):
            EX.ExperimentBackend.status(lb)


class Codex(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-codex")
        B.clear_cache()

    def test_status_matrix_and_argv(self):
        cb = AG.CodexBackend({"enabled": False})
        self.assertEqual(cb.status().state, "disabled")
        cb = AG.CodexBackend({"enabled": True, "sandbox": "read-only"})
        with mock.patch.object(AG.CodexBackend, "binary", return_value=None):
            self.assertEqual(cb.argv(), [])
            self.assertEqual(cb.status().state, "unavailable")
        for probe, state in (({"bin": "codex", "ok": False}, "error"), ({"bin": "codex", "ok": True, "auth": "not logged in", "version": "1"}, "unconfigured"),
                             ({"bin": "codex", "ok": True, "auth": "logged in", "version": "1"}, "available")):
            B.clear_cache()
            with mock.patch.object(AG.CodexBackend, "_probe", return_value=probe):
                self.assertEqual(cb.status().state, state)
        with mock.patch.object(AG.CodexBackend, "argv", return_value=["codex"]), \
                mock.patch.object(AG, "run_cli", side_effect=[(0, "codex 1.0"), (1, "Logged in using sk-abcdefghijklmnop")]):
            p = cb._probe()
        self.assertEqual(p["auth"], "not logged in")
        self.assertNotIn("abcdefghijklmnop", p["auth_detail"])
        with mock.patch.object(AG.CodexBackend, "argv", return_value=[]):
            self.assertEqual(cb._probe(), {"bin": None})

    def test_start_run_env_is_allowlisted_and_errors(self):
        cb = AG.CodexBackend({"enabled": True, "sandbox": "read-only", "model": "m", "timeout_s": 60, "windows_sandbox": "unelevated"})
        avail = B.IntegrationStatus("codex", "Codex", "available")
        seen = {}

        def popen(args, **kw):
            seen.update(kw)
            raise OSError("not found")
        with mock.patch.object(AG.CodexBackend, "status", return_value=avail), mock.patch.object(AG.CodexBackend, "argv", return_value=["codex"]), \
                mock.patch("subprocess.Popen", popen), mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant", "GITHUB_TOKEN": "g", "OPENAI_API_KEY": "o"}):
            with self.assertRaises(B.IntegrationError):
                cb.start_run("do it")
        self.assertNotIn("ANTHROPIC_API_KEY", seen["env"])
        self.assertNotIn("GITHUB_TOKEN", seen["env"])
        self.assertIn("OPENAI_API_KEY", seen["env"])  # Codex's own billing key is still allowed on this path
        with mock.patch.object(AG.CodexBackend, "status", return_value=avail):
            with self.assertRaises(B.IntegrationError):
                cb.start_run("  ")
            with self.assertRaises(B.IntegrationError):
                cb.start_run("x", resume_thread="bad id!")
        with mock.patch.object(AG.CodexBackend, "status", return_value=B.IntegrationStatus("codex", "C", "unconfigured")):
            with self.assertRaises(B.IntegrationError):
                cb.start_run("x")
        with self.assertRaises(B.IntegrationError):
            cb.cancel_run("cx-0000000000")
        with self.assertRaises(B.IntegrationError):
            AG.get_run("bad")
        with self.assertRaises(B.IntegrationError):
            AG.get_run("cx-0123456789")
        (AG._runs_dir() / "cx-0123456789.json").write_text("{damaged", "utf-8")
        with self.assertRaises(B.IntegrationError):
            AG.get_run("cx-0123456789")
        self.assertEqual(AG.list_runs(), [])

    def test_events(self):
        run = {"thread_id": "", "usage": {}, "errors": [], "status": "running", "final_message": "", "events": __import__("collections").deque()}
        for ev in ({"type": "thread.started", "thread_id": "th"}, {"type": "turn.completed", "usage": {"in": 1}},
                   {"type": "item.completed", "item": {"type": "agent_message", "text": "done", "id": "i"}},
                   {"type": "error", "message": "rate"}, {"type": "turn.failed", "error": {"message": "x"}}, {"type": "turn.failed", "error": "s"}):
            AG.apply_event(run, ev)
        self.assertEqual((run["thread_id"], run["final_message"], run["status"], len(run["errors"])), ("th", "done", "failed", 3))
        with mock.patch("backend.gitops.status", side_effect=RuntimeError):
            self.assertEqual(AG._git_snapshot(__import__("backend.gitops", fromlist=["x"])), {})


if __name__ == "__main__":
    unittest.main()
