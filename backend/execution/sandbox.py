"""Code execution engine (v3.0): Docker sandbox (GPU passthrough, resource limits) or local Python process.

Per research project (inside its data folder):
    code/<name>/           v4.2: the ACTIVE code project (code_projects.py) — the VS Code folder, a git repository,
                           mounted at /workspace in that project's own container ("phdlab-<id>-<code project id>")
    runs/<run_id>/         one folder per job: run.json, stdout.log, stderr.log, metrics.json, figures …  (mounted at /runs)
    sandbox/projects/<id>/ v4.2: settings.json + venv of each code project (a migrated v4.1 workspace keeps sandbox/)

Docker is driven through the `docker` CLI (no native Python packages — works with Docker Desktop + WSL2 on Windows).
One long-lived container per project ("phdlab-<id>") keeps installed packages between runs; every job is a
`docker exec` whose PID is recorded so ■ Stop can kill it inside the container.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from backend.core.config import data_dir

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IS_WIN = sys.platform.startswith("win")
MAX_LINES = 20000
FIG_EXT = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".pdf", ".webp"}


class SandboxError(Exception):
    pass


class VramBusyError(SandboxError):
    """GPU run refused: local LLMs are loaded in VRAM (see resources.vram_gate)."""

    def __init__(self, message: str, models: list, vram_used_mb=None):
        super().__init__(message)
        self.models, self.vram_used_mb = models, vram_used_mb


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ paths & settings
def code_dir() -> Path:
    """The active code project (v4.2). Raises code_projects.NoCodeProject when none is open."""
    from backend.execution.code_projects import active_dir
    return active_dir()


def runs_dir() -> Path:
    d = data_dir() / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sb_dir() -> Path:
    from backend.execution.code_projects import active_sandbox_dir
    return active_sandbox_dir()


DEFAULT_SETTINGS = {"mode": "local",  # v5: Python venv first; Docker only when a task needs Linux
                    "image": "", "gpu": True, "memory_gb": 8, "cpus": 4, "shm_gb": 2,
                    "network": True, "timeout_s": 6 * 3600, "self_debug_max": 4,
                    # v3.2: the local venv sees the packages of the Python that runs the app (clearml, torch, …)
                    "inherit_packages": True,
                    # v3.4 environments (envs.py): Python env = a project venv built from python_base, or python_base itself
                    # ("existing"); auto_deps installs what the code imports before every run (deps.py)
                    "python_mode": "venv", "python_base": "", "auto_deps": True, "torch_index": ""}


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    from backend.execution.code_projects import NoCodeProject
    try:
        f = sb_dir() / "settings.json"
    except NoCodeProject:  # no code project open: defaults (read-only — save_settings needs a project)
        return s
    if f.exists():
        try:
            s.update(json.loads(f.read_text("utf-8")))
        except Exception:
            pass
    return s


def save_settings(patch: dict) -> dict:
    s = load_settings()
    for k, v in patch.items():
        if k not in DEFAULT_SETTINGS:
            continue
        if k == "mode":
            s[k] = v if v in ("auto", "docker", "local") else "local"
        elif k in ("gpu", "network", "inherit_packages", "auto_deps"):
            s[k] = bool(v)
        elif k == "python_mode":
            s[k] = v if v in ("venv", "existing") else "venv"
        elif k == "python_base":
            v = str(v or "").strip().strip('"')
            if v and not (Path(v).is_file() and re.search(r"python[\d.]*(w)?(\.exe)?$", Path(v).name, re.I)):
                raise SandboxError(f"Not a Python interpreter: {v}")
            s[k] = v
        elif k == "torch_index":
            v = str(v or "").strip()
            if v and not re.match(r"^https://[\w.-]+(/[\w./-]*)?$", v):
                raise SandboxError("torch_index must be an https URL, e.g. https://download.pytorch.org/whl/cu124")
            s[k] = v
        elif k in ("memory_gb", "cpus", "shm_gb", "timeout_s", "self_debug_max"):
            try:
                s[k] = max(0, float(v)) if k in ("cpus",) else max(0, int(float(v)))
            except (TypeError, ValueError):
                pass
        elif k == "image":
            s[k] = str(v).strip()
    (sb_dir() / "settings.json").write_text(json.dumps(s, indent=1), "utf-8")
    return s


def container_name() -> str:
    from backend.execution.code_projects import active, container_for
    rec = active()
    if not rec:  # nothing to address without a code project; the name of no real container
        return "phdlab-" + hashlib.sha1(str(data_dir().resolve()).encode()).hexdigest()[:10]
    return container_for(rec)


# ------------------------------------------------------------------ docker CLI
def docker_exe() -> str | None:
    p = shutil.which("docker")
    if p:
        return p
    if IS_WIN:
        c = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        return c if os.path.exists(c) else None
    return None


def docker(args: list, timeout: int = 60) -> tuple[int, str]:
    exe = docker_exe()
    if not exe:
        return 127, "docker not installed"
    try:
        r = subprocess.run([exe] + args, capture_output=True, text=True, errors="replace", timeout=timeout,
                           creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"docker {' '.join(args[:2])} timed out"


_DOCKER_OK = {"t": 0.0, "ok": False}


def docker_running(cache_s: float = 10) -> bool:
    if time.time() - _DOCKER_OK["t"] < cache_s:
        return _DOCKER_OK["ok"]
    code, _ = docker(["info", "--format", "{{.ServerVersion}}"], 20)
    _DOCKER_OK.update(t=time.time(), ok=code == 0)
    return code == 0


def effective_mode(s: dict | None = None) -> str:
    """local | docker. 'auto' (v3.4): Docker when the code needs a GPU framework and Docker runs, else the Python env."""
    s = s or load_settings()
    if s["mode"] in ("local", "docker"):
        return s["mode"]
    return choose_mode(s)[0]


def choose_mode(s: dict | None = None) -> tuple[str, str]:
    from backend.execution import deps
    from backend.execution.envs import choose
    s = s or load_settings()
    try:
        plan = deps.plan_cached(code_dir())
    except Exception:
        plan = None
    return choose(s, plan)


def effective_image(s: dict) -> str:
    if s.get("image"):
        return s["image"]
    try:
        from backend.execution.sysinfo import scan
        return scan().get("recommendation", {}).get("sandbox", {}).get("image") or "python:3.11-slim"
    except Exception:
        return "python:3.11-slim"


def _mount(p: Path) -> str:
    return str(p.resolve())


def container_state() -> dict:
    name = container_name()
    code, out = docker(["inspect", name, "--format", "{{json .}}"], 20)
    if code != 0:
        return {"name": name, "exists": False, "running": False}
    try:
        d = json.loads(out.strip())
    except Exception:
        return {"name": name, "exists": False, "running": False}
    st, hc = d.get("State", {}), d.get("HostConfig", {})
    labels = d.get("Config", {}).get("Labels") or {}
    gpu = any((r.get("Count") == -1 or r.get("Capabilities")) for r in (hc.get("DeviceRequests") or []))
    return {"name": name, "exists": True, "running": st.get("Running", False), "status": st.get("Status"),
            "started": st.get("StartedAt"), "image": d.get("Config", {}).get("Image"), "id": d.get("Id", "")[:12],
            "gpu": gpu, "memory_gb": round((hc.get("Memory") or 0) / 2**30, 1), "cpus": (hc.get("NanoCpus") or 0) / 1e9,
            "network": hc.get("NetworkMode"), "shm_gb": round((hc.get("ShmSize") or 0) / 2**30, 1),
            "mounts": [{"src": m.get("Source"), "dst": m.get("Destination")} for m in d.get("Mounts", [])],
            "code_label": labels.get("phdlab.code", "")}


def image_present(image: str) -> bool:
    code, _ = docker(["image", "inspect", image, "--format", "{{.Id}}"], 30)
    return code == 0


def _capped_settings() -> tuple[dict, list]:
    """Sandbox settings after the v3.2 hardware policy (resources.py); never fails."""
    s = load_settings()
    try:
        from backend.execution.resources import clamp_sandbox
        return clamp_sandbox(s)
    except Exception:
        return s, []


def ensure_container(recreate: bool = False) -> dict:
    s, cap_warn = _capped_settings()
    image = effective_image(s)
    st = container_state()
    want_gpu = bool(s["gpu"])
    want_code = _code_label()
    if st["exists"] and (recreate or st.get("image") != image or st.get("gpu") != want_gpu or st.get("code_label") not in ("", want_code)):
        docker(["rm", "-f", st["name"]], 60)
        st = container_state()
    if st["exists"]:
        if not st["running"]:
            code, out = docker(["start", st["name"]], 60)
            if code != 0:
                raise SandboxError(f"Could not start the container: {out.strip()[-400:]}")
        st = container_state()
        over = [f"{k}={st.get(k) or 'unlimited'}" for k in ("memory_gb", "cpus") if s.get(k) and (not st.get(k) or st[k] > s[k] + 0.01)]
        if over:  # recreating would drop the packages installed in the container, so only warn
            st["warning"] = (f"Container limits ({', '.join(over)}) exceed the hardware policy "
                             f"({s['memory_gb']} GB, {s['cpus']} CPUs) — press ♻ Recreate to apply them.")
        return st
    if not image_present(image):
        raise SandboxError(f"NEED_IMAGE:{image}")
    args = ["run", "-d", "--name", st["name"], "--label", "phdlab=1", "--label", f"phdlab.project={data_dir().name}",
            "--label", f"phdlab.code={want_code}",
            "-v", f"{_mount(code_dir())}:/workspace", "-v", f"{_mount(runs_dir())}:/runs", "-w", "/workspace",
            "-e", "PYTHONUNBUFFERED=1", "-e", "MPLBACKEND=Agg"]
    if s["memory_gb"]:
        args += ["-m", f"{int(s['memory_gb'])}g"]
    if s["cpus"]:
        args += ["--cpus", str(s["cpus"])]
    if s["shm_gb"]:
        args += ["--shm-size", f"{int(s['shm_gb'])}g"]
    if not s["network"]:
        args += ["--network", "none"]
    if want_gpu:
        args += ["--gpus", "all"]
    args += [image, "sleep", "infinity"]
    code, out = docker(args, 180)
    if code == 0 and cap_warn:
        st = container_state()
        st["warning"] = "; ".join(cap_warn)
        return st
    if code != 0 and want_gpu and re.search(r"gpu|nvidia|device driver", out, re.I):
        args.remove("--gpus"); args.remove("all")
        docker(["rm", "-f", st["name"]], 60)  # a half-created container keeps the name
        code, out2 = docker(args, 180)
        if code == 0:
            st = container_state()
            err = [l for l in out.splitlines() if "rror" in l] or out.strip().splitlines()[-1:]
            st["warning"] = "GPU passthrough failed, the container runs on CPU: " + " ".join(err)[-300:]
            return st
        out = out2
    if code != 0:
        raise SandboxError("Could not create the container: " + out.strip()[-500:])
    return container_state()


def _code_label() -> str:
    """Which folder the container mounts (v4.2): a renamed or different code project gets a fresh container."""
    return hashlib.sha1(str(code_dir().resolve()).encode()).hexdigest()[:12]


def container_action(action: str) -> dict:
    name = container_name()
    if action == "start":
        return ensure_container()
    if action == "recreate":
        return ensure_container(recreate=True)
    if action in ("stop", "restart"):
        code, out = docker([action, "-t", "5", name], 60)
    elif action == "remove":
        code, out = docker(["rm", "-f", name], 60)
    else:
        raise SandboxError("Unknown action")
    if code != 0 and "No such container" not in out:
        raise SandboxError(out.strip()[-300:])
    return container_state()


# ------------------------------------------------------------------ jobs
class Job:
    def __init__(self, kind: str, cmd: str, title: str = ""):
        self.id = datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
        self.kind, self.cmd, self.title = kind, cmd, title or cmd[:80]
        self.status, self.exit_code = "queued", None
        self.started = self.ended = None
        self.lines: deque = deque(maxlen=MAX_LINES)
        self.seq = 0
        self.proc: subprocess.Popen | None = None
        self.mode = ""
        self.lock = threading.Lock()
        self.run_dir: Path | None = None
        self.meta: dict = {}
        self.stop_requested = False

    def add(self, stream: str, text: str):
        with self.lock:
            self.seq += 1
            self.lines.append((self.seq, stream, text))
        if self.run_dir and self.kind == "run":
            fn = "stderr.log" if stream == "err" else "stdout.log"
            try:
                with open(self.run_dir / fn, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
            except OSError:
                pass

    def since(self, seq: int) -> list:
        with self.lock:
            return [x for x in self.lines if x[0] > seq]

    def tail(self, n: int = 80, stream: str | None = None) -> str:
        with self.lock:
            items = [t for _, s, t in self.lines if stream is None or s == stream]
        return "\n".join(items[-n:])

    def info(self) -> dict:
        dur = None
        if self.started:
            end = self.ended or time.time()
            dur = round(end - self.started, 1)
        return {"id": self.id, "kind": self.kind, "cmd": self.cmd, "title": self.title, "status": self.status,
                "exit_code": self.exit_code, "started": self.started, "ended": self.ended, "duration": dur,
                "mode": self.mode, "lines": self.seq, **({"meta": self.meta} if self.meta else {})}


JOBS: dict[str, Job] = {}
_jobs_lock = threading.Lock()


def _register(job: Job) -> Job:
    with _jobs_lock:
        JOBS[job.id] = job
        if len(JOBS) > 200:
            for k in [k for k, j in JOBS.items() if j.status not in ("running", "queued")][:50]:
                JOBS.pop(k, None)
    return job


def _pump(job: Job, pipe, stream: str):
    try:
        for raw in iter(pipe.readline, ""):
            job.add(stream, raw.rstrip("\r\n"))
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def _base_python(s: dict) -> str:
    b = (s.get("python_base") or "").strip()
    return b if b and Path(b).is_file() else sys.executable


def _venv_dir(s: dict) -> Path:
    base = _base_python(s)
    if base == sys.executable:
        return sb_dir() / "venv"  # v3.0-v3.3 location (kept: existing venvs and their packages stay in use)
    return sb_dir() / ("venv-" + hashlib.sha1(str(Path(base).resolve()).lower().encode()).hexdigest()[:8])


def local_python_info() -> dict:
    s = load_settings()
    if s.get("python_mode") == "existing":
        return {"mode": "existing", "python": _base_python(s), "base": _base_python(s)}
    v = _venv_dir(s)
    return {"mode": "venv", "python": str(v / ("Scripts/python.exe" if IS_WIN else "bin/python")), "base": _base_python(s),
            "venv": str(v), "created": (v / "pyvenv.cfg").exists()}


def _local_python() -> str:
    """Python of the local environment. v3.4: python_mode 'existing' runs the chosen interpreter directly; 'venv' uses a
    private venv of the project built from the chosen base interpreter (created on first use). With
    settings.inherit_packages the venv also sees the base interpreter's packages (`include-system-site-packages`)."""
    s0 = load_settings()
    if s0.get("python_mode") == "existing":
        return _base_python(s0)
    venv = _venv_dir(s0)
    py = venv / ("Scripts/python.exe" if IS_WIN else "bin/python")
    inherit = bool(load_settings().get("inherit_packages", True))
    if not py.exists():
        args = [_base_python(s0), "-m", "venv"] + (["--system-site-packages"] if inherit else []) + [str(venv)]
        r = subprocess.run(args, capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode != 0 or not py.exists():
            return sys.executable
    _sync_venv_inherit(venv, inherit)
    return str(py)


def _sync_venv_inherit(venv: Path, inherit: bool) -> None:
    """Keep pyvenv.cfg's include-system-site-packages in line with the setting (venvs created before v3.2 too)."""
    cfg = venv / "pyvenv.cfg"
    try:
        txt = cfg.read_text("utf-8")
        want = "true" if inherit else "false"
        new = re.sub(r"(?im)^include-system-site-packages\s*=\s*\w+", f"include-system-site-packages = {want}", txt)
        if new != txt:
            cfg.write_text(new, "utf-8")
    except OSError:
        pass


def _local_cmd(cmd: str) -> tuple[list | str, dict]:
    py = _local_python()
    env = dict(os.environ, PYTHONUNBUFFERED="1", MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
    bindir = str(Path(py).parent)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    if (Path(py).parent.parent / "pyvenv.cfg").exists():  # a venv (not an interpreter chosen as "existing")
        env["VIRTUAL_ENV"] = str(Path(py).parent.parent)
    c = re.sub(r"^(python3?|py)(\s|$)", lambda m: f'"{py}"' + m.group(2), cmd.strip())
    c = re.sub(r"^pip3?(\s)", lambda m: f'"{py}" -m pip' + m.group(1), c)
    return c, env


def start_job(cmd: str, kind: str = "run", title: str = "", extra_env: dict | None = None, mode: str = "",
              meta: dict | None = None) -> Job:
    """Run a shell command in the sandbox (non-blocking). kind=run creates runs/<id>/.
    mode: '' = the code project's setting · 'local' (Python venv) · 'docker' (a task that needs Linux).
    meta: extra fields recorded in run.json from the start (research run id, idempotency key)."""
    if not cmd.strip():
        raise SandboxError("Empty command")
    s, _ = _capped_settings()
    pre_notes: list = []
    if mode:
        if mode not in ("local", "docker"):
            raise SandboxError("mode must be local or docker")
        mode, mode_why = mode, "requested by the research run"
    else:
        mode, mode_why = (s["mode"], "") if s["mode"] in ("local", "docker") else choose_mode(s)
    if kind == "run" and s.get("gpu") and (extra_env or {}).get("CUDA_VISIBLE_DEVICES") != "":
        from backend.execution.resources import VramBusy, vram_gate
        try:  # researcher's rule: no GPU training while local LLMs sit in VRAM (refused before anything is created)
            vram_gate()
        except VramBusy as e:
            from backend.core.config import load_config
            if not load_config()["resources"].get("auto_unload_for_gpu"):
                raise VramBusyError(str(e), e.models, e.vram_used_mb)
            from backend.providers.lifecycle import free_vram_for_gpu  # v4.1 opt-in: release IDLE local models, then re-check
            freed = free_vram_for_gpu(log=pre_notes.append)
            if not freed.get("ok"):
                busy = freed.get("busy") or e.models
                raise VramBusyError(str(e) + (" A local model is answering right now." if freed.get("busy") else ""), busy,
                                    e.vram_used_mb)
            try:
                vram_gate()
            except VramBusy as e2:
                raise VramBusyError(str(e2), e2.models, e2.vram_used_mb)
    job = _register(Job(kind, cmd, title))
    job.meta.update(meta or {})
    for m in pre_notes:
        job.add("sys", m)
    job.mode = mode
    if mode_why:
        job.add("sys", f"ℹ environment: auto → {'Docker' if mode == 'docker' else 'Python'} ({mode_why})")
    deps_prefix = ""
    if kind == "run" and s.get("auto_deps", True):
        try:  # v3.4: install what the code needs inside the target environment, in this same job and log
            from backend.execution import deps
            plan = deps.plan_cached(code_dir())
            if plan["count"] or plan["requirements_files"]:
                deps.write(code_dir(), plan)
                deps_prefix = "python .phdlab/ensure_deps.py && "
                job.meta["deps"] = {"imports": len(plan["imports"]), "requirements_files": plan["requirements_files"]}
        except Exception as e:
            job.add("sys", f"⚠ dependency check skipped: {e}")
    if kind == "run":
        job.run_dir = runs_dir() / job.id
        job.run_dir.mkdir(parents=True, exist_ok=True)
    env = {"RUN_ID": job.id}
    from backend.execution.code_projects import active
    job.meta["code_project"] = (active() or {}).get("name", "")
    job.meta["code_dir"] = str(code_dir())
    if kind == "run":  # v3.2: traceability (git commit) + hardware governor (thermal guard, JIT VRAM unload)
        try:
            from backend.execution.gitops import head_info
            job.meta["git"] = head_info()
            if job.meta["git"].get("dirty"):
                job.add("sys", f"ℹ code at {job.meta['git'].get('short') or 'no commit'} with uncommitted changes — commit to make this run reproducible")
        except Exception as e:
            job.meta["git"] = {"error": str(e)[:200]}
        gpu_env = {}
        if s.get("gpu") and "CUDA_VISIBLE_DEVICES" not in (extra_env or {}):
            try:
                from backend.execution.resources import prepare_gpu_run
                prep = prepare_gpu_run(s, log=lambda m: job.add("sys", m))
                gpu_env = prep["env"]
                job.meta["resources"] = {k: v for k, v in prep.items() if k != "env"}
            except Exception as e:
                job.add("sys", f"⚠ resource governor skipped: {e}")
        env.update(gpu_env)
        job.meta["environment"] = {"mode": mode, "image": effective_image(s) if mode == "docker" else "",
                                   "python": "" if mode == "docker" else _local_python(),
                                   "gpu": bool(s.get("gpu")) and (extra_env or {}).get("CUDA_VISIBLE_DEVICES", gpu_env.get("CUDA_VISIBLE_DEVICES")) != "",
                                   "memory_gb": s.get("memory_gb"), "cpus": s.get("cpus")}
    env.update(extra_env or {})
    if kind == "run":  # v3.2: a script that calls clearml Task.init records an offline session into its own run folder
        try:
            from backend.execution.tracker import run_env
            env.update(run_env(f"/runs/{job.id}" if mode == "docker" else str(job.run_dir)))
        except Exception:
            pass
    if s.get("torch_index"):
        env["PHDLAB_TORCH_INDEX"] = s["torch_index"]
    if mode == "docker":
        env["PHDLAB_IN_DOCKER"] = "1"
        cmd = deps_prefix + cmd
        st = ensure_container()
        if st.get("warning"):
            job.add("sys", "⚠ " + st["warning"])
        env["RUN_DIR"] = f"/runs/{job.id}" if job.run_dir else "/tmp"
        envargs = sum((["-e", f"{k}={v}"] for k, v in env.items()), [])
        script = (f'echo $$ > /tmp/phdlab_{job.id}.pid; '
                  # images with only python3 (e.g. Debian/Ubuntu bases): make `python` work too
                  'if ! command -v python >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then '
                  'mkdir -p /tmp/phdbin && ln -sf "$(command -v python3)" /tmp/phdbin/python; export PATH=/tmp/phdbin:$PATH; fi; '
                  'exec sh -c "$1"')
        argv = [docker_exe(), "exec", *envargs, "-w", "/workspace", st["name"], "sh", "-c", script, "sh", cmd]
        job.meta["container"] = st["name"]
        popen_kw = {}
        job.add("sys", f"$ {cmd}    [docker · {st.get('image')}{' · GPU' if st.get('gpu') else ''}]")
    else:
        env["RUN_DIR"] = str(job.run_dir) if job.run_dir else str(sb_dir())
        argv, base_env = _local_cmd(deps_prefix + cmd)
        base_env.update(env)
        popen_kw = {"shell": True, "cwd": str(code_dir()), "env": base_env}
        if not IS_WIN:
            popen_kw["start_new_session"] = True
        job.add("sys", f"$ {cmd}    [python · {_local_python()}]")
    try:
        job.proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                                    creationflags=NO_WINDOW | (subprocess.CREATE_NEW_PROCESS_GROUP if IS_WIN else 0), **popen_kw)
    except Exception as e:
        job.status, job.ended = "failed", time.time()
        job.add("err", f"Could not start: {e}")
        raise SandboxError(str(e))
    job.status, job.started = "running", time.time()
    job.meta["pid"] = job.proc.pid  # v5: a research run checks after a server restart whether the process still lives
    if job.run_dir:
        _write_run_meta(job)
    t1 = threading.Thread(target=_pump, args=(job, job.proc.stdout, "out"), daemon=True)
    t2 = threading.Thread(target=_pump, args=(job, job.proc.stderr, "err"), daemon=True)
    t1.start(); t2.start()
    threading.Thread(target=_waiter, args=(job, t1, t2, s["timeout_s"]), daemon=True).start()
    return job


def _waiter(job: Job, t1, t2, timeout_s: int):
    deadline = time.time() + (timeout_s or 10 ** 9)
    while job.proc.poll() is None:
        if time.time() > deadline:
            job.add("sys", f"⏱ Time limit ({timeout_s} s) reached — stopping")
            stop_job(job.id)
            break
        time.sleep(0.3)
    try:
        job.proc.wait(timeout=15)
    except Exception:
        pass
    t1.join(5); t2.join(5)
    job.exit_code = job.proc.returncode
    job.ended = time.time()
    job.status = "stopped" if job.stop_requested else ("done" if job.exit_code == 0 else "failed")
    job.add("sys", f"[{job.status}] exit code {job.exit_code} · {round(job.ended - job.started, 1)} s")
    if job.run_dir:
        try:
            job.meta.update(collect_run(job))
        except Exception as e:
            job.add("sys", f"(metrics extraction failed: {e})")
        _after_run(job)
        _write_run_meta(job)
        if job.kind == "run":
            threading.Thread(target=_auto_clearml, args=(job.id,), daemon=True).start()


def _auto_clearml(run_id: str) -> None:
    """Record the finished run as a ClearML offline session when clearml.auto_record is on."""
    try:
        from backend.execution.tracker import auto_record
        auto_record(run_id)
    except Exception:
        pass


def _after_run(job: Job) -> None:
    """v3.2: seal produced artifacts with provenance metadata; re-run once on CPU after a GPU fault."""
    try:
        from backend.core.config import load_config
        cfg = load_config()
        if cfg["provenance"].get("enabled", True):
            from backend.knowledge.provenance import seal_run
            job.meta["provenance"] = seal_run(job.run_dir, job.id, job.meta, csv_header=cfg["provenance"].get("csv_header", True))
    except Exception as e:
        job.add("sys", f"(provenance sealing failed: {e})")
    if job.status != "failed" or job.kind != "run":
        return
    try:
        from backend.core.config import load_config
        from backend.execution.resources import classify_failure
        kind = classify_failure(job.tail(200, "err"))
        if not kind:
            return
        job.meta["failure_class"] = kind
        if kind == "gpu_oom":
            job.add("sys", "💡 CUDA out of memory — reduce the batch size / model size, or unload local LLMs first.")
            return
        env = job.meta.get("environment") or {}
        if env.get("gpu") and load_config()["resources"].get("cpu_fallback_on_gpu_fault", True) and not job.meta.get("fallback_of"):
            nj = start_job(job.cmd, "run", f"CPU fallback of {job.id}", extra_env={"CUDA_VISIBLE_DEVICES": ""})
            nj.meta["fallback_of"] = job.id
            job.meta["fallback_run"] = nj.id
            job.add("sys", f"⚠ GPU fault detected — the run was restarted on CPU as {nj.id}")
    except Exception as e:
        job.add("sys", f"(GPU fault handling failed: {e})")


def stop_all(reason: str = "shutdown", wait_s: float = 10) -> list:
    """Stop every running job (app shutdown: no orphan process keeps the GPU). The reason is recorded in run.json so a
    research run treats the job as interrupted (retried on the next start), not as a failed experiment."""
    stopped = []
    for job in list(JOBS.values()):
        if job.status != "running":
            continue
        job.meta["stopped_by"] = reason
        try:
            stop_job(job.id)
            stopped.append(job.id)
        except SandboxError:
            pass
    end = time.time() + wait_s
    while time.time() < end and any(JOBS[j].status == "running" for j in stopped if j in JOBS):
        time.sleep(0.1)
    return stopped


def stop_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job or job.status != "running":
        raise SandboxError("Job is not running")
    job.stop_requested = True
    if job.mode == "docker":
        pidf = f"/tmp/phdlab_{job.id}.pid"
        docker(["exec", job.meta.get("container") or container_name(), "sh", "-c",
                f'P=$(cat {pidf} 2>/dev/null); [ -n "$P" ] && (pkill -TERM -P $P 2>/dev/null; kill -TERM $P 2>/dev/null); '
                f'sleep 2; [ -n "$P" ] && (pkill -KILL -P $P 2>/dev/null; kill -KILL $P 2>/dev/null); true'], 20)
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(job.proc.pid)], capture_output=True,
                           creationflags=NO_WINDOW, timeout=5)
            # A sharing/permission failure is reported by taskkill's exit code rather than an exception. Ensure the
            # process we own is also asked to stop; the waiter reports completion only after it actually exits.
            if job.proc.poll() is None:
                job.proc.kill()
        else:
            os.killpg(os.getpgid(job.proc.pid), signal.SIGTERM) if job.mode == "local" else job.proc.terminate()
    except Exception:
        try:
            job.proc.kill()
        except Exception:
            pass
    job.add("sys", "■ Stop requested")
    return job.info()


def run_blocking(cmd: str, timeout: int = 600, kind: str = "run", title: str = "") -> Job:
    job = start_job(cmd, kind, title)
    end = time.time() + timeout
    while job.status == "running" and time.time() < end:
        time.sleep(0.2)
    if job.status == "running":
        stop_job(job.id)
        time.sleep(1)
    return job


# ------------------------------------------------------------------ runs, metrics & figures
KV_RE = re.compile(r"([A-Za-z_][\w./-]{0,40})\s*[=:]\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\b")
STEP_KEYS = ("epoch", "step", "iter", "iteration", "ep")


def parse_metrics_text(text: str) -> dict:
    """Final values + series from log lines like 'epoch 3 loss=0.12 psnr=28.4' or 'METRIC acc=0.91'."""
    series, final = {}, {}
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 400:
            continue
        if line.startswith("{") and line.endswith("}"):
            try:
                d = json.loads(line)
                pairs = [(k, v) for k, v in d.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
            except ValueError:
                pairs = []
        else:
            pairs = [(k, float(v)) for k, v in KV_RE.findall(line)]
            m = re.match(r"^\s*(?:epoch|ep)\s+(\d+)", line, re.I)
            if m and not any(k.lower() in STEP_KEYS for k, _ in pairs):
                pairs.insert(0, ("epoch", float(m.group(1))))
        if not pairs:
            continue
        step = next((v for k, v in pairs if k.lower() in STEP_KEYS), None)
        for k, v in pairs:
            if k.lower() in STEP_KEYS:
                continue
            final[k] = v
            if step is not None:
                series.setdefault(k, []).append([step, v])
    return {"final": final, "series": {k: v[-2000:] for k, v in series.items() if len(v) > 1}}


def collect_run(job: Job) -> dict:
    rd = job.run_dir
    metrics, src = {}, ""
    cd = Path(job.meta["code_dir"]) if job.meta.get("code_dir") else code_dir()  # the project the job started in
    for cand in (rd / "metrics.json", cd / "metrics.json", cd / "outputs" / "metrics.json"):
        if cand.exists() and cand.stat().st_mtime >= (job.started or 0) - 1:
            try:
                d = json.loads(cand.read_text("utf-8"))
                if isinstance(d, dict):
                    metrics, src = d, str(cand.relative_to(data_dir()))
                    if cand.parent != rd:
                        shutil.copyfile(cand, rd / "metrics.json")
                    break
            except Exception:
                pass
    parsed = parse_metrics_text(job.tail(MAX_LINES, "out"))
    final = {k: v for k, v in metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)} or parsed["final"]
    (rd / "metrics_parsed.json").write_text(json.dumps(parsed), "utf-8")
    # figures written by the code to $RUN_DIR, ./outputs or ./figures during this run
    figs = []
    for folder in (rd, cd / "outputs", cd / "figures"):
        if not folder.exists():
            continue
        for f in folder.rglob("*"):
            if f.suffix.lower() in FIG_EXT and f.is_file() and f.stat().st_mtime >= (job.started or 0) - 1:
                if folder != rd:
                    dst = rd / "figures" / f.name
                    dst.parent.mkdir(exist_ok=True)
                    shutil.copyfile(f, dst)
                    f = dst
                figs.append(str(f.relative_to(rd)).replace("\\", "/"))
    return {"metrics": final, "metrics_source": src or ("stdout" if final else ""), "figures": sorted(set(figs))[:50],
            "series": sorted(parsed["series"].keys())}


def _write_run_meta(job: Job):
    if not job.run_dir:
        return
    d = job.info()
    d.update(job.meta or {})
    d["stdout_tail"] = job.tail(40, "out")
    d["stderr_tail"] = job.tail(40, "err")
    try:
        (job.run_dir / "run.json").write_text(json.dumps(d, indent=1), "utf-8")
    except OSError:
        pass


def list_runs(limit: int = 100) -> list:
    out = []
    for d in sorted(runs_dir().iterdir(), reverse=True)[:limit]:
        f = d / "run.json"
        if f.exists():
            try:
                r = json.loads(f.read_text("utf-8"))
                live = JOBS.get(r["id"])
                if live:
                    r.update(live.info())
                out.append({k: r.get(k) for k in ("id", "cmd", "title", "status", "exit_code", "started", "duration", "mode", "metrics",
                                                  "figures", "git", "environment", "clearml", "fallback_run", "fallback_of")})
            except Exception:
                pass
    return out


def get_run(run_id: str) -> dict:
    if not re.fullmatch(r"[\w-]{6,60}", run_id or ""):
        raise SandboxError("Invalid run id")
    d = runs_dir() / run_id
    if not d.exists():
        raise SandboxError("Run not found")
    def _json(f: Path, default):  # a run interrupted mid-write must not make the run (or its provenance) unreadable
        try:
            return json.loads(f.read_text("utf-8")) if f.exists() else default
        except (OSError, ValueError):
            return default
    r = _json(d / "run.json", None) or {"id": run_id, "warning": "run.json is missing or damaged"}
    r["id"] = run_id
    if run_id in JOBS:
        r.update(JOBS[run_id].info())
    r["parsed"] = _json(d / "metrics_parsed.json", {})
    r["stdout"] = (d / "stdout.log").read_text("utf-8", "replace")[-60000:] if (d / "stdout.log").exists() else ""
    r["stderr"] = (d / "stderr.log").read_text("utf-8", "replace")[-30000:] if (d / "stderr.log").exists() else ""
    return r


def best_metrics(limit: int = 200) -> dict:
    """Best value of each metric over all successful runs (min for loss/error-like names, else max)."""
    best = {}
    for r in list_runs(limit):
        if r.get("status") != "done":
            continue
        for k, v in (r.get("metrics") or {}).items():
            if not isinstance(v, (int, float)):
                continue
            lower = bool(re.search(r"loss|err|mse|mae|rmse|time|latency|flops|params|ppl|perplexity|sam|ergas", k, re.I))
            cur = best.get(k)
            if cur is None or (v < cur["value"] if lower else v > cur["value"]):
                best[k] = {"value": v, "run": r["id"], "direction": "min" if lower else "max"}
    return best
