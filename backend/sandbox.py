"""Code execution engine (v3.0): Docker sandbox (GPU passthrough, resource limits) or local Python process.

Per research project (inside its data folder):
    code/                  the IDE workspace (mounted at /workspace in the container; a git repository)
    runs/<run_id>/         one folder per job: run.json, stdout.log, stderr.log, metrics.json, figures …  (mounted at /runs)
    sandbox/settings.json  engine settings (mode, image, GPU, RAM/CPU limits, network, timeout)
    sandbox/venv/          private virtual environment used in local mode

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

from .config import data_dir

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IS_WIN = sys.platform.startswith("win")
MAX_LINES = 20000
FIG_EXT = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".pdf", ".webp"}


class SandboxError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ paths & settings
def code_dir() -> Path:
    d = data_dir() / "code"
    d.mkdir(parents=True, exist_ok=True)
    return d


def runs_dir() -> Path:
    d = data_dir() / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sb_dir() -> Path:
    d = data_dir() / "sandbox"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULT_SETTINGS = {"mode": "auto", "image": "", "gpu": True, "memory_gb": 8, "cpus": 4, "shm_gb": 2,
                    "network": True, "timeout_s": 6 * 3600, "self_debug_max": 4}


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    f = sb_dir() / "settings.json"
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
            s[k] = v if v in ("auto", "docker", "local") else "auto"
        elif k in ("gpu", "network"):
            s[k] = bool(v)
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
    return "phdlab-" + hashlib.sha1(str(data_dir().resolve()).encode()).hexdigest()[:10]


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
    s = s or load_settings()
    if s["mode"] == "local":
        return "local"
    if s["mode"] == "docker":
        return "docker"
    return "docker" if docker_exe() and docker_running() else "local"


def effective_image(s: dict) -> str:
    if s.get("image"):
        return s["image"]
    try:
        from .sysinfo import scan
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
    gpu = any((r.get("Count") == -1 or r.get("Capabilities")) for r in (hc.get("DeviceRequests") or []))
    return {"name": name, "exists": True, "running": st.get("Running", False), "status": st.get("Status"),
            "started": st.get("StartedAt"), "image": d.get("Config", {}).get("Image"), "id": d.get("Id", "")[:12],
            "gpu": gpu, "memory_gb": round((hc.get("Memory") or 0) / 2**30, 1), "cpus": (hc.get("NanoCpus") or 0) / 1e9,
            "network": hc.get("NetworkMode"), "shm_gb": round((hc.get("ShmSize") or 0) / 2**30, 1),
            "mounts": [{"src": m.get("Source"), "dst": m.get("Destination")} for m in d.get("Mounts", [])]}


def image_present(image: str) -> bool:
    code, _ = docker(["image", "inspect", image, "--format", "{{.Id}}"], 30)
    return code == 0


def ensure_container(recreate: bool = False) -> dict:
    s = load_settings()
    image = effective_image(s)
    st = container_state()
    want_gpu = bool(s["gpu"])
    if st["exists"] and (recreate or st.get("image") != image or st.get("gpu") != want_gpu):
        docker(["rm", "-f", st["name"]], 60)
        st = container_state()
    if st["exists"]:
        if not st["running"]:
            code, out = docker(["start", st["name"]], 60)
            if code != 0:
                raise SandboxError(f"Could not start the container: {out.strip()[-400:]}")
        return container_state()
    if not image_present(image):
        raise SandboxError(f"NEED_IMAGE:{image}")
    args = ["run", "-d", "--name", st["name"], "--label", "phdlab=1", "--label", f"phdlab.project={data_dir().name}",
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


def container_stats() -> dict | None:
    code, out = docker(["stats", "--no-stream", "--format", "{{json .}}", container_name()], 30)
    if code != 0 or not out.strip().startswith("{"):
        return None
    try:
        d = json.loads(out.strip().splitlines()[0])
    except Exception:
        return None
    return {"cpu_pct": d.get("CPUPerc"), "mem": d.get("MemUsage"), "mem_pct": d.get("MemPerc"),
            "net": d.get("NetIO"), "block": d.get("BlockIO"), "pids": d.get("PIDs")}


def list_images() -> list:
    code, out = docker(["images", "--format", "{{json .}}"], 30)
    res = []
    for line in out.splitlines():
        try:
            d = json.loads(line)
            res.append({"repo": d.get("Repository"), "tag": d.get("Tag"), "id": d.get("ID"), "size": d.get("Size"),
                        "created": d.get("CreatedSince")})
        except Exception:
            pass
    return res


def list_containers() -> list:
    code, out = docker(["ps", "-a", "--filter", "label=phdlab=1", "--format", "{{json .}}"], 30)
    res = []
    for line in out.splitlines():
        try:
            d = json.loads(line)
            res.append({"name": d.get("Names"), "image": d.get("Image"), "status": d.get("Status"), "state": d.get("State"),
                        "id": d.get("ID"), "mine": d.get("Names") == container_name()})
        except Exception:
            pass
    return res


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


def _local_python() -> str:
    """Private venv for local mode (created on first use)."""
    venv = sb_dir() / "venv"
    py = venv / ("Scripts/python.exe" if IS_WIN else "bin/python")
    if not py.exists():
        r = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode != 0 or not py.exists():
            return sys.executable
    return str(py)


def _local_cmd(cmd: str) -> tuple[list | str, dict]:
    py = _local_python()
    env = dict(os.environ, PYTHONUNBUFFERED="1", MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
    bindir = str(Path(py).parent)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = str(Path(py).parent.parent)
    c = re.sub(r"^(python3?|py)(\s|$)", lambda m: f'"{py}"' + m.group(2), cmd.strip())
    c = re.sub(r"^pip3?(\s)", lambda m: f'"{py}" -m pip' + m.group(1), c)
    return c, env


def start_job(cmd: str, kind: str = "run", title: str = "", extra_env: dict | None = None) -> Job:
    """Run a shell command in the sandbox (non-blocking). kind=run creates runs/<id>/."""
    if not cmd.strip():
        raise SandboxError("Empty command")
    s = load_settings()
    mode = effective_mode(s)
    job = _register(Job(kind, cmd, title))
    job.mode = mode
    if kind == "run":
        job.run_dir = runs_dir() / job.id
        job.run_dir.mkdir(parents=True, exist_ok=True)
    env = {"RUN_ID": job.id, **(extra_env or {})}
    if mode == "docker":
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
        popen_kw = {}
        job.add("sys", f"$ {cmd}    [docker · {st.get('image')}{' · GPU' if st.get('gpu') else ''}]")
    else:
        env["RUN_DIR"] = str(job.run_dir) if job.run_dir else str(sb_dir())
        argv, base_env = _local_cmd(cmd)
        base_env.update(env)
        popen_kw = {"shell": True, "cwd": str(code_dir()), "env": base_env}
        if not IS_WIN:
            popen_kw["start_new_session"] = True
        job.add("sys", f"$ {cmd}    [local · {Path(_local_python()).parent.parent.name}]")
    try:
        job.proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                                    creationflags=NO_WINDOW | (subprocess.CREATE_NEW_PROCESS_GROUP if IS_WIN else 0), **popen_kw)
    except Exception as e:
        job.status, job.ended = "failed", time.time()
        job.add("err", f"Could not start: {e}")
        raise SandboxError(str(e))
    job.status, job.started = "running", time.time()
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
            job.meta = collect_run(job)
        except Exception as e:
            job.add("sys", f"(metrics extraction failed: {e})")
        _write_run_meta(job)


def stop_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job or job.status != "running":
        raise SandboxError("Job is not running")
    job.stop_requested = True
    if job.mode == "docker":
        pidf = f"/tmp/phdlab_{job.id}.pid"
        docker(["exec", container_name(), "sh", "-c",
                f'P=$(cat {pidf} 2>/dev/null); [ -n "$P" ] && (pkill -TERM -P $P 2>/dev/null; kill -TERM $P 2>/dev/null); '
                f'sleep 2; [ -n "$P" ] && (pkill -KILL -P $P 2>/dev/null; kill -KILL $P 2>/dev/null); true'], 20)
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(job.proc.pid)], capture_output=True, creationflags=NO_WINDOW)
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


def pull_image(image: str) -> Job:
    if not docker_exe():
        raise SandboxError("Docker is not installed")
    job = _register(Job("pull", f"docker pull {image}", f"Pull {image}"))
    job.mode = "docker"
    job.proc = subprocess.Popen([docker_exe(), "pull", image], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace", bufsize=1, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
    job.status, job.started = "running", time.time()
    t1 = threading.Thread(target=_pump, args=(job, job.proc.stdout, "out"), daemon=True)
    t2 = threading.Thread(target=_pump, args=(job, job.proc.stderr, "err"), daemon=True)
    t1.start(); t2.start()
    threading.Thread(target=_waiter, args=(job, t1, t2, 6 * 3600), daemon=True).start()
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
    for cand in (rd / "metrics.json", code_dir() / "metrics.json", code_dir() / "outputs" / "metrics.json"):
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
    for folder in (rd, code_dir() / "outputs", code_dir() / "figures"):
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
                out.append({k: r.get(k) for k in ("id", "cmd", "title", "status", "exit_code", "started", "duration", "mode", "metrics", "figures")})
            except Exception:
                pass
    return out


def get_run(run_id: str) -> dict:
    if not re.fullmatch(r"[\w-]{6,60}", run_id or ""):
        raise SandboxError("Invalid run id")
    d = runs_dir() / run_id
    if not d.exists():
        raise SandboxError("Run not found")
    r = json.loads((d / "run.json").read_text("utf-8")) if (d / "run.json").exists() else {"id": run_id}
    if run_id in JOBS:
        r.update(JOBS[run_id].info())
    p = d / "metrics_parsed.json"
    r["parsed"] = json.loads(p.read_text("utf-8")) if p.exists() else {}
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
