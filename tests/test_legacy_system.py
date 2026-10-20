"""Legacy system layer (coverage pass): Docker sandbox (scripted fake docker CLI), runs, git/GitHub (real git, mocked
GitHub API), co-coding agent helpers, environments, machine scan, hardware governor, dependency planner."""
import _env  # noqa: F401  (must be first)
import asyncio
import json
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

import httpx

from backend import coder, config, deps, envs, gitops, resources as R, sandbox as SB, sysinfo as SI


class FakeDocker:
    """Scripted `docker` CLI: state of one container + recorded calls."""

    def __init__(self, exists=False, running=False, image="img:1", gpu=False, run_fail="", start_fail=False):
        self.exists, self.running, self.image, self.gpu = exists, running, image, gpu
        self.run_fail, self.start_fail, self.calls = run_fail, start_fail, []

    def __call__(self, args, timeout=60):
        self.calls.append(args)
        a = args[0]
        if a == "inspect":
            if not self.exists:
                return 1, "No such object"
            return 0, json.dumps({"Id": "abcdef123456789", "State": {"Running": self.running, "Status": "running" if self.running else "exited"},
                                  "Config": {"Image": self.image}, "HostConfig": {"DeviceRequests": [{"Count": -1}] if self.gpu else [],
                                                                                  "Memory": 32 * 2 ** 30, "NanoCpus": 16e9},
                                  "Mounts": [{"Source": "C:/x", "Destination": "/workspace"}]})
        if a == "rm":
            self.exists = self.running = False
            return 0, ""
        if a == "start":
            if self.start_fail:
                return 1, "cannot start"
            self.running = True
            return 0, ""
        if a == "image":
            return (0, "sha") if args[2] in ("img:1", "img:gpu") else (1, "missing")
        if a == "run":
            if self.run_fail and ("--gpus" in args or self.run_fail == "always"):
                return 1, "Error response: could not select device driver with capabilities: [[gpu]]" if self.run_fail != "always" else "boom"
            self.exists = self.running = True
            self.gpu = "--gpus" in args
            self.image = args[-3]
            return 0, "id"
        if a in ("stop", "restart"):
            return (0, "") if self.exists else (1, "No such container")
        if a == "stats":
            return 0, json.dumps({"CPUPerc": "1%", "MemUsage": "1GiB", "PIDs": "3"})
        if a == "images":
            return 0, json.dumps({"Repository": "img", "Tag": "1", "ID": "x", "Size": "1GB"}) + "\nnot json"
        if a == "ps":
            return 0, json.dumps({"Names": SB.container_name(), "Image": "img:1", "State": "running"}) + "\n{bad"
        if a == "info":
            return 0, "27.0"
        return 0, ""


class Sandbox(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-sandbox")
        SB.save_settings({"mode": "local", "gpu": False, "image": "img:1", "memory_gb": 4, "cpus": 2})

    def test_settings_validation(self):
        s = SB.save_settings({"mode": "weird", "gpu": 0, "python_mode": "x", "memory_gb": "abc", "cpus": "1.5", "image": " i:1 ",
                              "unknown": 1, "network": 1})
        self.assertEqual((s["mode"], s["gpu"], s["python_mode"], s["cpus"], s["image"], s["network"]), ("auto", False, "venv", 1.5, "i:1", True))
        with self.assertRaises(SB.SandboxError):
            SB.save_settings({"python_base": "C:/not/python.exe"})
        self.assertEqual(SB.save_settings({"python_base": sys.executable})["python_base"], sys.executable)
        with self.assertRaises(SB.SandboxError):
            SB.save_settings({"torch_index": "http://insecure"})
        self.assertEqual(SB.save_settings({"torch_index": "https://download.pytorch.org/whl/cu124"})["torch_index"],
                         "https://download.pytorch.org/whl/cu124")
        (SB.sb_dir() / "settings.json").write_text("{bad", "utf-8")
        self.assertEqual(SB.load_settings()["mode"], "auto")

    def test_container_lifecycle(self):
        fd = FakeDocker()
        with mock.patch.object(SB, "docker", fd), mock.patch.object(SB, "docker_exe", return_value="docker"):
            self.assertFalse(SB.container_state()["exists"])
            with mock.patch.object(SB, "effective_image", return_value="img:missing"):
                with self.assertRaises(SB.SandboxError) as cm:
                    SB.ensure_container()
                self.assertIn("NEED_IMAGE", str(cm.exception))
            st = SB.ensure_container()
            self.assertTrue(st["running"])
            run_args = next(c for c in fd.calls if c[0] == "run")
            self.assertIn("-m", run_args)
            self.assertIn("--network", SB.save_settings({"network": False}) and ["--network"])
            fd.running = False
            st = SB.ensure_container()  # existing but stopped → started; limits above the policy → warning only
            self.assertTrue(st["running"])
            self.assertIn("warning", st)
            fd.running, fd.start_fail = False, True
            with self.assertRaises(SB.SandboxError):
                SB.ensure_container()
            fd.start_fail = False
            SB.save_settings({"gpu": True, "network": False, "shm_gb": 1})
            fd.run_fail = "gpu"
            st = SB.ensure_container(recreate=True)
            self.assertIn("GPU passthrough failed", st["warning"])
            fd.run_fail = "always"
            with self.assertRaises(SB.SandboxError):
                SB.ensure_container(recreate=True)
            fd.run_fail = ""
            for act in ("start", "recreate", "stop", "restart", "remove"):
                self.assertIn("exists", SB.container_action(act))
            fd.exists = False
            self.assertIn("exists", SB.container_action("stop"))  # "No such container" is not an error
            with self.assertRaises(SB.SandboxError):
                SB.container_action("explode")
            self.assertEqual(SB.container_stats()["pids"], "3")
            self.assertEqual(len(SB.list_images()), 1)
            self.assertTrue(SB.list_containers()[0]["mine"])
            self.assertTrue(SB.docker_running(0))
        with mock.patch.object(SB, "docker", return_value=(0, "not json")):
            self.assertFalse(SB.container_state()["exists"])
            self.assertIsNone(SB.container_stats())
        with mock.patch.object(SB, "docker", return_value=(0, "{bad")):
            self.assertIsNone(SB.container_stats())

    def test_docker_cli_wrapper(self):
        with mock.patch.object(SB, "docker_exe", return_value=None):
            self.assertEqual(SB.docker(["ps"])[0], 127)
        with mock.patch.object(SB, "docker_exe", return_value="docker"), \
                mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 1)):
            self.assertEqual(SB.docker(["ps"])[0], 124)
        with mock.patch.object(SB, "docker_exe", return_value="docker"), \
                mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="o", stderr="e")):
            self.assertEqual(SB.docker(["ps"]), (0, "oe"))
        with mock.patch("shutil.which", return_value=None), mock.patch.object(SB, "IS_WIN", True), mock.patch("os.path.exists", return_value=True):
            self.assertTrue(SB.docker_exe().endswith("docker.exe"))
        with mock.patch("shutil.which", return_value=None), mock.patch.object(SB, "IS_WIN", False):
            self.assertIsNone(SB.docker_exe())

    def test_docker_job_and_pull(self):
        fd = FakeDocker(exists=True, running=True)
        SB.save_settings({"mode": "docker", "gpu": False})
        popen = mock.MagicMock()
        popen.return_value.stdout.readline.side_effect = ["epoch 1 loss=0.5\n", ""]
        popen.return_value.stderr.readline.return_value = ""
        popen.return_value.poll.return_value = 0
        popen.return_value.returncode = 0
        popen.return_value.pid = 4242
        with mock.patch.object(SB, "docker", fd), mock.patch.object(SB, "docker_exe", return_value="docker"), \
                mock.patch("subprocess.Popen", popen), mock.patch.object(SB, "effective_image", return_value="img:1"):
            job = SB.start_job("python train.py", "run", "docker run")
            for _ in range(100):
                if job.status != "running":
                    break
                time.sleep(0.05)
            self.assertEqual(job.status, "done")
            argv = popen.call_args[0][0]
            self.assertEqual(argv[:2], ["docker", "exec"])
            self.assertIn("PHDLAB_IN_DOCKER=1", argv)
            with mock.patch("backend.envs.valid_image", return_value=False):
                with self.assertRaises(SB.SandboxError):
                    SB.pull_image("BAD IMAGE")
            pj = SB.pull_image("python:3.11-slim")
            self.assertEqual(pj.kind, "pull")
        with mock.patch.object(SB, "docker_exe", return_value=None):
            with self.assertRaises(SB.SandboxError):
                SB.pull_image("python:3.11")

    def test_local_jobs_stop_and_runs(self):
        job = SB.start_job(f'python -c "import time; print(\'epoch 1 psnr=20\'); time.sleep(20)"', "run", "slow")
        time.sleep(1.0)
        info = SB.stop_job(job.id)
        self.assertEqual(info["id"], job.id)
        for _ in range(100):
            if job.status != "running":
                break
            time.sleep(0.1)
        self.assertEqual(job.status, "stopped")
        with self.assertRaises(SB.SandboxError):
            SB.stop_job(job.id)
        with self.assertRaises(SB.SandboxError):
            SB.start_job("   ")
        j = SB.run_blocking('python -c "import json,os; json.dump({\'acc\': 0.9, \'loss\': 0.1}, open(os.path.join(os.environ[\'RUN_DIR\'],\'metrics.json\'),\'w\'))"', 120)
        self.assertEqual(j.status, "done")
        r = SB.get_run(j.id)
        self.assertEqual(r["metrics"]["acc"], 0.9)
        best = SB.best_metrics()
        self.assertEqual((best["acc"]["direction"], best["loss"]["direction"]), ("max", "min"))
        (SB.runs_dir() / j.id / "run.json").write_text("{half", "utf-8")
        (SB.runs_dir() / j.id / "metrics_parsed.json").write_text("{half", "utf-8")
        r = SB.get_run(j.id)  # damaged files no longer break the run page
        self.assertEqual((r["id"], r["parsed"]), (j.id, {}))
        self.assertIn("damaged", r["warning"])
        with self.assertRaises(SB.SandboxError):
            SB.get_run("bad id!")
        with self.assertRaises(SB.SandboxError):
            SB.get_run("missing-run")
        slow = SB.run_blocking('python -c "import time; time.sleep(30)"', timeout=1)
        self.assertIn(slow.status, ("stopped", "running"))
        self.assertIn("lines", SB.Job("x", "c").info())

    def test_metrics_parsing_and_python_env(self):
        p = SB.parse_metrics_text('epoch 1 loss=0.5\nepoch 2 loss=0.4 acc: 0.8\n{"step": 3, "loss": 0.3, "ok": true}\n{bad}\n' + "x" * 500)
        self.assertEqual(p["final"]["loss"], 0.3)
        self.assertEqual(p["series"]["loss"], [[1.0, 0.5], [2.0, 0.4], [3, 0.3]])
        info = SB.local_python_info()
        self.assertEqual(info["mode"], "venv")
        SB.save_settings({"python_mode": "existing", "python_base": sys.executable})
        self.assertEqual(SB.local_python_info()["python"], sys.executable)
        self.assertEqual(SB._local_python(), sys.executable)
        cmd, env = SB._local_cmd("pip install x")
        self.assertIn("-m pip", cmd)
        SB.save_settings({"python_mode": "venv", "python_base": ""})
        v = SB.sb_dir() / "venv-test"
        v.mkdir()
        (v / "pyvenv.cfg").write_text("include-system-site-packages = false\n", "utf-8")
        SB._sync_venv_inherit(v, True)
        self.assertIn("= true", (v / "pyvenv.cfg").read_text("utf-8"))
        SB._sync_venv_inherit(SB.sb_dir() / "none", True)  # missing venv: ignored
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1)), \
                mock.patch.object(SB, "_venv_dir", return_value=SB.sb_dir() / "never"):
            self.assertEqual(SB._local_python(), sys.executable)  # venv creation failed → app Python

    def test_after_run_gpu_fault_and_oom(self):
        job = SB.Job("run", "python t.py")
        job.run_dir = SB.runs_dir() / "fake-run"
        job.run_dir.mkdir()
        job.status = "failed"
        job.add("err", "RuntimeError: CUDA out of memory. Tried to allocate")
        SB._after_run(job)
        self.assertEqual(job.meta["failure_class"], "gpu_oom")
        job2 = SB.Job("run", "python t.py")
        job2.run_dir = SB.runs_dir() / "fake-run2"
        job2.run_dir.mkdir()
        job2.status = "failed"
        job2.meta["environment"] = {"gpu": True}
        job2.add("err", "CUDA error: an illegal memory access was encountered")
        nj = mock.Mock(id="cpu-rerun")
        nj.meta = {}
        with mock.patch.object(SB, "start_job", return_value=nj) as sj:
            SB._after_run(job2)
        self.assertEqual(job2.meta["fallback_run"], "cpu-rerun")
        self.assertEqual(sj.call_args[1]["extra_env"], {"CUDA_VISIBLE_DEVICES": ""})
        with mock.patch("backend.provenance.seal_run", side_effect=RuntimeError("disk")), \
                mock.patch("backend.resources.classify_failure", side_effect=RuntimeError("x")):
            SB._after_run(job2)
        self.assertIn("failed", job2.tail(5, "sys"))
        with mock.patch("backend.integrations.experiment.auto_record", side_effect=RuntimeError):
            SB._auto_clearml("x")  # never raises


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class Git(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-git")
        config.save_config({"github": {"token": "", "user": "me", "name": "Me", "email": ""}})

    def test_local_repository_workflow(self):
        self.assertFalse(gitops.status()["repo"])
        with self.assertRaises(gitops.GitError):
            gitops.diff("x.py")
        (SB.code_dir() / "a.py").write_text("print(1)\n", "utf-8")
        st = gitops.init()
        self.assertTrue(st["repo"])
        self.assertTrue((SB.code_dir() / ".gitignore").exists())
        self.assertEqual(gitops.init()["repo"], True)  # idempotent
        self.assertEqual(gitops.head_info()["note"], "no commit yet")
        with self.assertRaises(gitops.GitError):
            gitops.commit("  ")
        gitops.commit("first", ["a.py"])
        st = gitops.commit("first")
        self.assertEqual(st["commits"][0]["message"], "first")
        with self.assertRaises(gitops.GitError):
            gitops.commit("nothing")
        (SB.code_dir() / "a.py").write_text("print(2)\n", "utf-8")
        (SB.code_dir() / "b.py").write_text("new\n", "utf-8")
        st = gitops.status()
        self.assertEqual({f["status"] for f in st["files"]}, {"modified", "untracked"})
        d = gitops.diff("a.py")
        self.assertEqual((d["original"], d["modified"]), ("print(1)\n", "print(2)\n"))
        with self.assertRaises(gitops.GitError):
            gitops.diff("../outside.py")
        h = gitops.head_info()
        self.assertTrue(h["dirty"])
        self.assertEqual(len(h["sha"]), 40)
        for bad in ("", ".", "  ", "../x.py", "sub"):
            if bad == "sub":
                (SB.code_dir() / "sub").mkdir()
            with self.assertRaises(gitops.GitError, msg=bad):
                gitops.discard(bad)
        gitops.discard("a.py")
        self.assertEqual((SB.code_dir() / "a.py").read_text("utf-8"), "print(1)\n")
        self.assertTrue((SB.code_dir() / "b.py").exists())  # other work is untouched
        gitops.commit("all")
        with self.assertRaises(gitops.GitError):
            gitops.G(["no-such-command"])
        self.assertEqual(gitops._identity(), ("Me", "me@users.noreply.github.com"))

    def test_github_flows_without_network(self):
        with self.assertRaises(gitops.GitError):
            gitops.push()
        config.save_config({"github": {"token": "ghp_test"}})
        (SB.code_dir() / "a.py").write_text("x\n", "utf-8")
        h = gitops._auth_header("tok")
        self.assertIn("AUTHORIZATION: basic", h)
        with mock.patch("httpx.get", return_value=httpx.Response(401)):
            with self.assertRaises(gitops.GitError):
                gitops.gh_user()
        with mock.patch("httpx.get", return_value=httpx.Response(503, text="down")):
            with self.assertRaises(gitops.GitError):
                gitops.gh_user()
        user = httpx.Response(200, json={"login": "me", "html_url": "https://github.com/me"})
        pushes = []
        real_G = gitops.G

        def G(args, timeout=120, extra_config=None, check=True):
            if args[0] in ("push", "pull"):
                pushes.append((args, extra_config))
                return ""
            return real_G(args, timeout, extra_config, check)
        with mock.patch.object(gitops, "G", G), mock.patch("httpx.get", return_value=user), \
                mock.patch("httpx.post", return_value=httpx.Response(201, json={"html_url": "https://github.com/me/r", "private": True})):
            out = gitops.publish("my repo!", private=True)
        self.assertTrue(out["created"])
        self.assertIn("extraheader", pushes[0][1][0])
        self.assertNotIn("ghp_test", (SB.code_dir() / ".git" / "config").read_text("utf-8"))  # token never persisted
        exists = httpx.Response(422, json={"message": "exists"})
        with mock.patch.object(gitops, "G", G), mock.patch("httpx.get", side_effect=[user, httpx.Response(200, json={"html_url": "u"})]), \
                mock.patch("httpx.post", return_value=exists):
            self.assertFalse(gitops.publish("r")["created"])
        with mock.patch.object(gitops, "G", G), mock.patch("httpx.get", side_effect=[user, httpx.Response(404, json={"message": "no"})]), \
                mock.patch("httpx.post", return_value=exists):
            with self.assertRaises(gitops.GitError):
                gitops.publish("r")
        for code in (403, 500):
            with mock.patch.object(gitops, "G", G), mock.patch("httpx.get", return_value=user), \
                    mock.patch("httpx.post", return_value=httpx.Response(code, text="x")):
                with self.assertRaises(gitops.GitError):
                    gitops.publish("r")
        with mock.patch.object(gitops, "G", G):
            gitops.push()
            gitops.pull()
        self.assertEqual(len(pushes), 4)  # created + already-existing repo + push + pull

    def test_no_git_and_gitpython_fallback(self):
        with mock.patch.object(gitops, "git_exe", return_value=None):
            self.assertFalse(gitops.status()["git"])
            self.assertEqual(gitops.head_info(), {})
            with self.assertRaises(gitops.GitError):
                gitops.G(["status"])
        with mock.patch.object(gitops, "_gitpython", None):
            self.assertIn("git version", gitops.G(["--version"]))
            with self.assertRaises(gitops.GitError):
                gitops.G(["no-such"])
        if gitops._gitpython is not None:
            with mock.patch.object(gitops._gitpython, "Git", side_effect=RuntimeError("broken")):
                self.assertIn("git version", gitops.G(["--version"]))


class Coder(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-coder")

    def test_prompt_parse_preview_apply(self):
        (config.workspace() / "experiment_design.md").write_text("DESIGN", "utf-8")
        (SB.code_dir() / "a.py").write_text("old\n", "utf-8")
        with mock.patch.object(SB, "list_runs", return_value=[{"id": "r1", "cmd": "python a.py", "status": "failed", "exit_code": 1}]), \
                mock.patch.object(SB, "get_run", return_value={"stderr": "Traceback", "stdout": "out"}):
            s = coder.system_prompt("a.py", "EXTRA", "fix the bug")
        for frag in ("RESEARCH BLUEPRINT", "LAST RUN r1", "a.py", "EXTRA", "local Python venv"):
            self.assertIn(frag, s)
        with mock.patch.object(SB, "list_runs", return_value=[{"id": "r1"}]), mock.patch.object(SB, "get_run", side_effect=RuntimeError):
            self.assertEqual(coder._last_run(), "")
        with mock.patch.object(SB, "list_runs", return_value=[]):
            self.assertEqual(coder._last_run(), "")
        with mock.patch.object(SB, "effective_mode", return_value="docker"), mock.patch.object(SB, "effective_image", return_value="img"):
            self.assertIn("image=img", coder.system_prompt())
        text = "```python file=./a.py\nnew\n```\n```python file=a.py\ndup\n```\n```text file=b.txt\nx```\n```run\npython a.py\n```"
        p = coder.parse(text)
        self.assertEqual([f["path"] for f in p["files"]], ["a.py", "b.txt"])
        self.assertEqual(p["run"], "python a.py")
        prev = coder.preview(p["files"])
        self.assertEqual((prev[0]["added"], prev[0]["removed"], prev[1]["exists"]), (1, 1, False))
        self.assertEqual(coder.apply(p["files"]), ["a.py", "b.txt"])

    def test_run_and_wait(self):
        events = []

        async def emit(e):
            events.append(e["type"])

        async def go():
            return await coder.run_and_wait('python -c "print(\'hi\')"', emit, cpu=True)
        out = asyncio.run(go())
        self.assertIn("hi", out["stdout"])
        self.assertEqual(events[0], "run_start")
        self.assertEqual(events[-1], "run_end")

        async def cancel():
            t = asyncio.ensure_future(coder.run_and_wait('python -c "import time; time.sleep(30)"', emit))
            await asyncio.sleep(1.5)
            t.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await t
        asyncio.run(cancel())


class Environments(unittest.TestCase):
    def test_discovery_and_probe(self):
        envs._cache.clear()
        res = envs.discover_pythons(force=True)
        self.assertTrue(any(p["path"] for p in res))
        self.assertIs(envs.discover_pythons(), envs._cache["pythons"][1])
        self.assertIsNone(envs.probe("C:/no/python.exe"))
        with mock.patch.object(envs, "IS_WIN", False), mock.patch("glob.glob", return_value=["/usr/bin/python3.11"]), \
                mock.patch("shutil.which", side_effect=lambda n: "/usr/bin/conda" if n == "conda" else None), \
                mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout=json.dumps({"envs": ["/opt/env"]}))):
            self.assertIsInstance(envs._candidates(), list)
        with mock.patch("subprocess.run", side_effect=OSError), mock.patch("shutil.which", return_value="conda"):
            self.assertIsInstance(envs._candidates(), list)

    def test_images_hub_and_choice(self):
        self.assertTrue(envs.valid_image("pytorch/pytorch:2.5.1-cuda12.4"))
        self.assertFalse(envs.valid_image("Bad Image"))
        with mock.patch("backend.sandbox.docker", return_value=(0, json.dumps({"Name": "pytorch/pytorch", "StarCount": "9", "IsOfficial": "[OK]"}) + "\nbad")):
            self.assertTrue(envs.hub_search("pytorch")[0]["official"])
        with mock.patch("backend.sandbox.docker", return_value=(1, "denied")):
            with self.assertRaises(ValueError):
                envs.hub_search("pytorch")
        with self.assertRaises(ValueError):
            envs.hub_search("!")
        tags = {"results": [{"name": "2.5", "last_updated": "2024-01-01T00", "images": [{"size": 2e9}]}, {"name": "x", "images": []}]}
        with mock.patch("httpx.get", return_value=httpx.Response(200, json=tags)):
            out = envs.hub_tags("pytorch/pytorch", "2")
        self.assertEqual((out[0]["size_gb"], out[1]["size_gb"]), (2.0, None))
        with mock.patch("httpx.get", return_value=httpx.Response(200, json={"results": []})) as g:
            envs.hub_tags("python")
        self.assertIn("/library/python/", g.call_args[0][0])
        for resp in (httpx.Response(404), httpx.Response(503), httpx.ConnectError("x")):
            with mock.patch("httpx.get", side_effect=[resp] if isinstance(resp, Exception) else None, return_value=resp):
                with self.assertRaises(ValueError):
                    envs.hub_tags("pytorch/pytorch")
        with self.assertRaises(ValueError):
            envs.hub_tags("Bad Repo!")
        with mock.patch("backend.sandbox.docker_exe", return_value="docker"), mock.patch("backend.sandbox.docker_running", return_value=True), \
                mock.patch("backend.sandbox.list_images", return_value=[{"repo": "mine", "tag": "1"}, {"repo": "<none>", "tag": "x"}]), \
                mock.patch("backend.sysinfo.scan", return_value={"recommendation": {"sandbox": {"image": "custom/rec:1"}}}):
            cat = envs.docker_catalog()
        self.assertTrue(cat["catalog"][0]["recommended"])
        self.assertEqual(cat["local"][0]["image"], "mine:1")
        with mock.patch("backend.sandbox.docker_exe", return_value=None), mock.patch("backend.sysinfo.scan", side_effect=RuntimeError):
            self.assertFalse(envs.docker_catalog()["docker"])
        self.assertIsInstance(envs.summary(), dict)


class Machine(unittest.TestCase):
    def test_run_and_probes(self):
        self.assertEqual(SI.run(["definitely-not-a-command-xyz"])[0], 127)
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertEqual(SI.run(["x"]), (124, "timeout"))
        with mock.patch("subprocess.run", side_effect=OSError("denied")):
            self.assertEqual(SI.run(["x"])[0], 126)
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="Ubuntu".encode("utf-16-le"), stderr=b"")):
            self.assertEqual(SI.run(["wsl"])[1], "Ubuntu")
        smi = "0, NVIDIA GeForce RTX 3060, 12288, 900, 3, 45, 20.5, 560.0\nbad,line"
        with mock.patch("shutil.which", return_value="nvidia-smi"), mock.patch.object(SI, "run", side_effect=[(0, smi), (0, "CUDA Version: 12.6")]):
            g = SI.gpus()
        self.assertEqual((g[0]["vram_total_mb"], g[0]["cuda"]), (12288.0, "12.6"))
        with mock.patch("shutil.which", return_value="nvidia-smi"), mock.patch.object(SI, "run", return_value=(9, "")):
            self.assertEqual(SI.gpus(), [])
        self.assertIn("error", SI.disk("Z:/definitely/missing/drive"))
        self.assertIn("cores", SI.cpu())
        self.assertIn("total_gb", SI.memory())
        with mock.patch.object(SI, "IS_WIN", False), mock.patch.object(SI.sys, "platform", "darwin"), mock.patch.object(SI, "run", return_value=(0, str(16 * 2 ** 30))):
            self.assertEqual(SI.memory()["total_gb"], 16.0)
        with mock.patch.object(SI, "IS_WIN", False), mock.patch.object(SI.sys, "platform", "linux"), \
                mock.patch("builtins.open", mock.mock_open(read_data="MemTotal: 1000 kB\nMemAvailable: 500 kB\n")):
            self.assertEqual(SI.memory()["used_pct"], 50)

    def test_docker_wsl_toolchain_recommend(self):
        info = {"OperatingSystem": "Docker Desktop", "KernelVersion": "5.15-microsoft-standard-WSL2", "Runtimes": {"runc": {}}, "MemTotal": 2 ** 33}
        with mock.patch("shutil.which", return_value="docker"), \
                mock.patch.object(SI, "run", side_effect=[(0, json.dumps({"Client": {"Version": "27"}, "Server": {"Version": "27"}})), (0, json.dumps(info))]):
            d = SI.docker_info()
        self.assertTrue(d["running"] and d["wsl2"] and d["gpu_runtime"])
        with mock.patch("shutil.which", return_value="docker"), mock.patch.object(SI, "run", side_effect=[(0, "garbage"), (1, "Cannot connect")]):
            self.assertIn("Cannot connect", SI.docker_info()["error"])
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(SI.docker_info()["installed"])
            self.assertFalse(SI.wsl_info()["installed"])
        with mock.patch("shutil.which", return_value="wsl"), mock.patch.object(SI, "run", return_value=(0, "NAME STATE VERSION\n* Ubuntu Running 2\nx")):
            self.assertTrue(SI.wsl_info()["wsl2"])
        with mock.patch.object(SI, "IS_WIN", False):
            self.assertFalse(SI.wsl_info()["applicable"])
        self.assertIn("python", SI.toolchain())
        with mock.patch("httpx.get", side_effect=httpx.ConnectError("x")):
            self.assertEqual(SI.local_ai_servers(config.load_config()), {"lmstudio": False, "ollama": False})
        base = {"cpu": {"cores": 16}, "memory": {"total_gb": 32}, "tools": {"git": "2.4", "latex": ["pdflatex"]}, "disk": {"free_gb": 10},
                "local_ai": {"ollama": True}, "wsl": {"applicable": True, "wsl2": False}}
        for vram in (24000, 16000, 12288, 8000, 4000, 0):
            s = dict(base, gpus=[{"name": "GPU", "vram_total_mb": vram}] if vram else [],
                     docker={"running": True, "gpu_runtime": False, "server_version": "27"})
            rec = SI.recommend(s)
            self.assertTrue(rec["local_model"]["size"])
        self.assertEqual(SI.recommend(dict(base, gpus=[], docker={"installed": True}))["sandbox"]["mode"], "local")
        r = SI.recommend(dict(base, gpus=[], docker={}, local_ai={}, tools={}, disk={}))
        self.assertEqual(r["agents"]["coder"], "cloud")
        with mock.patch.object(SI, "CACHE", Path(_env.os.environ["PHDLAB_DATA_DIR"]) / "scan-test.json"):
            SI.CACHE.write_text("{bad", "utf-8")
            with mock.patch.object(SI, "docker_info", return_value={}), mock.patch.object(SI, "toolchain", return_value={}), \
                    mock.patch.object(SI, "local_ai_servers", return_value={}), mock.patch.object(SI, "gpus", return_value=[]):
                s = SI.scan()
                self.assertIn("recommendation", s)
                self.assertEqual(SI.scan()["time"], s["time"])  # cached
        self.assertIn("gpus", SI.live())


class Governor(unittest.TestCase):
    def test_policy_and_probes(self):
        cfg = config.load_config()
        cfg["resources"].update(enforce_caps=False, sandbox_memory_gb=6)
        self.assertEqual(R.clamp_sandbox({"memory_gb": 999}, cfg), ({"memory_gb": 999}, []))
        p = R.policy(cfg, {})
        self.assertEqual(p["source"]["sandbox_memory_gb"], "override")
        with mock.patch("backend.sysinfo.scan", side_effect=RuntimeError):
            self.assertEqual(R._scan(), {})
        R._gpu_cache.update(t=0, gpus=None)
        with mock.patch("backend.sysinfo.gpus", side_effect=RuntimeError):
            self.assertEqual(R.gpus(0), [])
        with mock.patch.object(R, "gpus", return_value=[{"temp_c": 90}]):
            self.assertFalse(R.preflight_gpu(cfg)["use_gpu"])
            self.assertEqual(R.prepare_gpu_run({"gpu": True}, cfg=cfg)["env"], {"CUDA_VISIBLE_DEVICES": ""})
        with mock.patch.object(R, "gpus", return_value=[]):
            self.assertFalse(R.preflight_gpu(cfg)["use_gpu"])
        self.assertFalse(R.prepare_gpu_run({"gpu": False}, cfg=cfg)["use_gpu"])
        with mock.patch.object(R, "gpu_job_running", return_value=False), mock.patch.object(R, "gpus", return_value=[{"util_pct": 95}]):
            self.assertTrue(R.gpu_busy(cfg))
        with mock.patch.dict("sys.modules", {"backend.sandbox": None}):
            self.assertFalse(R.gpu_job_running())

        async def inside():
            with self.assertRaises(RuntimeError):
                R._run_async(asyncio.sleep(0))
        asyncio.run(inside())

    def test_loaded_models_and_unload(self):
        async def ost(_):
            return {"loaded": [{"id": "q"}, {}]}

        async def lst(_):
            return {"loaded": ["m"]}

        async def inst(_):
            return [("m", "m:1"), ("k2", "k2:1"), ("", "x")]
        with mock.patch("backend.local_ai.ollama_status", ost), mock.patch("backend.local_ai.lmstudio_status", lst), \
                mock.patch("backend.local_ai.lmstudio_loaded_instances", inst):
            self.assertEqual(R.loaded_local_models(), {"ollama": ["q"], "lmstudio": ["m", "k2"]})

        async def boom(*a, **k):
            raise RuntimeError("x")
        with mock.patch("backend.local_ai.ollama_status", boom), mock.patch("backend.local_ai.lmstudio_status", boom), \
                mock.patch("backend.local_ai.lmstudio_loaded_instances", boom):
            self.assertEqual(R.loaded_local_models(), {"ollama": [], "lmstudio": []})
        cfg = config.load_config()
        cfg["resources"].update(unload_wait_s=0, unload_timeout_s=2, vram_free_target_mb=1000)
        with mock.patch.object(R, "loaded_local_models", return_value={"ollama": ["q"], "lmstudio": ["m"]}), \
                mock.patch("backend.local_ai.ollama_unload", boom), mock.patch("backend.local_ai.lmstudio_unload", boom), \
                mock.patch.object(R, "gpus", return_value=[{"vram_used_mb": 500}]):
            rep = R.unload_local_models(cfg)
        self.assertEqual(len(rep["errors"]), 2)

        async def ok(*a, **k):
            return {"ok": True, "method": "rest-v1"}
        lines = []
        with mock.patch.object(R, "loaded_local_models", return_value={"ollama": ["q"], "lmstudio": ["m"]}), \
                mock.patch("backend.local_ai.ollama_unload", ok), mock.patch("backend.local_ai.lmstudio_unload", ok), \
                mock.patch.object(R, "gpus", return_value=[{"vram_used_mb": 5000}]), mock.patch.object(R.time, "sleep"):
            rep = R.unload_local_models(cfg, lines.append)
        self.assertEqual(rep["lmstudio_method"], "rest-v1")
        self.assertTrue(any("another program" in l for l in lines))
        with mock.patch.object(R, "loaded_local_models", return_value={"ollama": [], "lmstudio": []}):
            self.assertEqual(R.unload_local_models(cfg)["unloaded"], [])
        with mock.patch.object(R, "loaded_local_models", return_value={"ollama": [], "lmstudio": []}):
            R.vram_gate(cfg)  # nothing loaded: no exception
        self.assertEqual(R.classify_failure("all good"), "")


class Deps(unittest.TestCase):
    def test_planner_edges(self):
        _env.fresh_project("legacy-deps")
        root = SB.code_dir()
        (root / "pkg").mkdir()
        (root / "pkg" / "__init__.py").write_text("", "utf-8")
        (root / "main.py").write_text("import numpy\nimport pkg\nfrom sklearn import svm\nimport cv2\nimport os\n", "utf-8")
        (root / "broken.py").write_text("def (:\n", "utf-8")
        (root / "nb.ipynb").write_text(json.dumps({"cells": [{"cell_type": "code", "source": ["import pandas\n", "!pip install x"]}]}), "utf-8")
        (root / "bad.ipynb").write_text("{", "utf-8")
        (root / "pyproject.toml").write_text('[project]\ndependencies = ["torch>=2", "einops"]\n', "utf-8")
        (root / "environment.yml").write_text("dependencies:\n  - python=3.11\n  - pip:\n    - timm\n  - scipy\n", "utf-8")
        plan = deps.detect(root)
        names = {i["pip"] for i in plan["imports"]}
        self.assertTrue({"numpy", "scikit-learn", "opencv-python", "pandas"} <= names)
        self.assertNotIn("pkg", names)
        out = deps.write(root, plan)
        self.assertTrue((root / ".phdlab" / "ensure_deps.py").exists())
        self.assertIn("count", out)
        self.assertIs(deps.plan_cached(root), deps.plan_cached(root))
        self.assertIn("ensure_deps.py", deps.command("py"))
        (root / "pyproject.toml").write_text("not toml [", "utf-8")
        self.assertIsInstance(deps.detect(root), dict)


if __name__ == "__main__":
    unittest.main()
