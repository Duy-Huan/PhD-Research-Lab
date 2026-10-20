"""ExperimentBackend abstraction (Target §9-10, Milestone 4).

    ExperimentBackend
      ├── LocalRunsBackend   the built-in sandbox runs (runs/<id>/run.json, metrics.json, figures) — always available
      └── ClearMLAdapter     ClearML through the official `clearml` Python SDK, in one of two modes:
            offline (default)  no server: every run is recorded as a ClearML offline session (zip) inside the project
                               (<project>/clearml/offline/); it can be imported into a ClearML Server later, unchanged
            server             a self-hosted / hosted ClearML Server (API host + credentials); `available` only after
                               GET <api_host>/debug.ping answered

The SDK is never imported by the web server: every SDK call runs in clearml_worker.py as a separate Python process
(Task.init hooks its process; the SDK's native dependencies may be blocked by Windows Smart App Control). Offline
sessions are read back here as plain JSON (task.json, metrics.jsonl), without the SDK.

PhD Lab keeps the research meaning (memory/research.py) and only POINTERS to the tracker (task id, web URL / session
zip); ClearML keeps scalars, logs, artifacts. MLflow could be added as another subclass without touching the core.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import zipfile
from abc import ABC
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..config import data_dir, load_config
from .base import NO_WINDOW, IntegrationError, IntegrationStatus, NotSupported, cached

WORKER = Path(__file__).with_name("clearml_worker.py")
SDK_PIN = "clearml>=2.0"
OFFLINE_ID = re.compile(r"^offline-[0-9a-f]{32}$")
SERVER_ID = re.compile(r"^[0-9a-f]{32}$")


class ExperimentBackend(ABC):
    name = "abstract"
    capabilities: tuple = ()

    def status(self) -> IntegrationStatus:
        raise NotImplementedError

    def _no(self, what: str):
        raise NotSupported(f"{self.name} does not support {what}")

    def create_experiment(self, name: str, project: str = "", params: dict | None = None, tags: list | None = None) -> dict:
        self._no("create_experiment")

    def start_run(self, experiment_id: str) -> dict:
        self._no("start_run")

    def log_metric(self, experiment_id: str, name: str, value: float, step: int = 0) -> None:
        self._no("log_metric")

    def log_parameter(self, experiment_id: str, name: str, value) -> None:
        self._no("log_parameter")

    def log_artifact(self, experiment_id: str, name: str, path: str) -> dict:
        self._no("log_artifact")

    def log_model(self, experiment_id: str, name: str, path: str) -> dict:
        self._no("log_model")

    def finish_run(self, experiment_id: str, status: str = "completed") -> dict:
        self._no("finish_run")

    def get_experiment(self, experiment_id: str) -> dict:
        self._no("get_experiment")

    def list_experiments(self, limit: int = 50) -> list:
        self._no("list_experiments")

    def compare_experiments(self, ids: list) -> dict:
        """Metric table {metric: {id: value}} built from get_experiment()."""
        table: dict = {}
        for i in ids:
            for k, v in (self.get_experiment(i).get("metrics") or {}).items():
                table.setdefault(k, {})[i] = v
        return {"ids": ids, "metrics": table}


# ------------------------------------------------------------------ built-in runs
class LocalRunsBackend(ExperimentBackend):
    name = "local"
    capabilities = ("get_experiment", "list_experiments", "compare_experiments")

    def status(self) -> IntegrationStatus:
        from ..sandbox import runs_dir
        return IntegrationStatus("local_runs", "Local runs (sandbox)", "available", f"{runs_dir()}", capabilities=list(self.capabilities))

    def get_experiment(self, experiment_id: str) -> dict:
        from ..sandbox import SandboxError, get_run
        try:
            r = get_run(experiment_id)
        except SandboxError as e:
            raise IntegrationError(str(e))
        return {"id": r["id"], "name": r.get("title") or r.get("cmd", ""), "status": r.get("status"), "metrics": r.get("metrics") or {},
                "git": r.get("git") or {}, "environment": r.get("environment") or {}, "figures": r.get("figures") or [],
                "clearml": r.get("clearml") or {}, "backend": self.name}

    def list_experiments(self, limit: int = 50) -> list:
        from ..sandbox import list_runs
        return list_runs(limit)


# ------------------------------------------------------------------ ClearML
def clearml_dir() -> Path:
    """Per-project ClearML cache (CLEARML_CACHE_DIR of the worker); offline sessions land in <this>/offline/."""
    d = data_dir() / "clearml"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _clearml_conf_file() -> bool:
    p = os.environ.get("CLEARML_CONFIG_FILE") or str(Path.home() / "clearml.conf")
    return Path(p).is_file()


def sdk_probe() -> dict:
    """{installed, ok, version, error} — import tested in a subprocess (a blocked native DLL must not hit the server)."""
    if importlib.util.find_spec("clearml") is None:
        return {"installed": False, "ok": False, "version": "", "error": "Python package `clearml` is not installed"}
    try:
        out = run_worker("probe", {}, offline=True, env_extra={}, timeout=120)
        return {"installed": True, "ok": True, "version": out.get("version", ""), "error": ""}
    except IntegrationError as e:
        return {"installed": True, "ok": False, "version": "", "error": str(e)}


def run_worker(cmd: str, args: dict, offline: bool, env_extra: dict, timeout: int = 900, cwd: str | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLEARML_", "TRAINS_"))}
    env.update(PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", CLEARML_CACHE_DIR=str(clearml_dir()), **env_extra)
    try:
        r = subprocess.run([sys.executable, str(WORKER)], input=json.dumps({"cmd": cmd, "args": args, "offline": offline}),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env,
                           cwd=cwd or str(data_dir()), creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise IntegrationError(f"ClearML {cmd} timed out after {timeout} s")
    except OSError as e:
        raise IntegrationError(f"Could not start the ClearML worker: {e}")
    # the SDK keeps printing at interpreter exit, so the marker is not always the last line
    marked = [l for l in (r.stdout or "").splitlines() if l.startswith(("@@RESULT@@", "@@ERROR@@"))]
    last = marked[-1] if marked else ""
    if last.startswith("@@RESULT@@"):
        return json.loads(last[len("@@RESULT@@"):])
    if last.startswith("@@ERROR@@"):
        raise IntegrationError("ClearML: " + json.loads(last[len("@@ERROR@@"):]).get("error", "unknown error"))
    tail = (r.stderr or r.stdout or "").strip()[-400:]
    raise IntegrationError(f"ClearML worker exited with code {r.returncode}: {tail or 'no output'}")


def read_offline_session(path: Path) -> dict:
    """Summary of an offline session (folder or .zip) from its task.json / metrics.jsonl — no SDK needed."""
    path = Path(path)

    def from_folder(read):
        task = json.loads(read("task.json"))
        last, series = {}, {}
        try:
            for line in read("metrics.jsonl").splitlines():
                if not line.strip():
                    continue
                for ev in json.loads(line):
                    if ev.get("type") == "training_stats_scalar":
                        key = ev["metric"] if ev.get("variant") in (None, ev.get("metric")) else f"{ev['metric']}/{ev['variant']}"
                        last[key] = ev.get("value")
                        series[key] = series.get(key, 0) + 1
        except KeyError:
            pass
        params = {f"{sec}/{k}": v.get("value") for sec, kv in (task.get("hyperparams") or {}).items() for k, v in (kv or {}).items()}
        sc = task.get("script") or {}
        return {"id": task.get("id"), "name": task.get("name"), "project": task.get("project_name"), "parameters": params,
                "metrics": last, "points": series, "script": {"repository": sc.get("repository", ""), "branch": sc.get("branch", ""),
                                                              "commit": sc.get("version_num", ""), "entry_point": sc.get("entry_point", "")},
                "run_id": params.get("General/run_id", ""), "status": params.get("General/status", "")}

    if path.is_dir():
        def read_dir(n):
            f = path / n
            if not f.is_file():  # same contract as the zip reader: a session without metrics.jsonl is still readable
                raise KeyError(n)
            return f.read_text("utf-8")
        return from_folder(read_dir)
    with zipfile.ZipFile(path) as z:
        names = {Path(n).name: n for n in z.namelist() if n.count("/") <= 1}

        def read(n):
            if n not in names:
                raise KeyError(n)
            return z.read(names[n]).decode("utf-8")
        return from_folder(read)


class ClearMLAdapter(ExperimentBackend):
    name = "clearml"
    capabilities = ("record_run", "offline_sessions", "get_experiment", "compare_experiments")
    server_capabilities = ("create_experiment", "log_metric", "log_parameter", "log_artifact", "log_model", "finish_run",
                           "list_experiments", "import_offline", "submit_remote")

    def __init__(self, cfg: dict | None = None):
        self.cfg = (cfg or load_config())["clearml"]

    @property
    def mode(self) -> str:
        return self.cfg.get("mode") or "offline"

    # ---- configuration & health
    def sdk_installed(self) -> bool:
        return importlib.util.find_spec("clearml") is not None

    def sdk(self) -> dict:
        return cached("clearml_sdk", 300, sdk_probe)

    def configured(self) -> bool:
        c = self.cfg
        return bool(c.get("api_host") and c.get("access_key") and c.get("secret_key")) or _clearml_conf_file() \
            or bool(os.environ.get("CLEARML_API_HOST") and os.environ.get("CLEARML_API_ACCESS_KEY"))

    def api_host(self) -> str:
        return (self.cfg.get("api_host") or os.environ.get("CLEARML_API_HOST") or "http://localhost:8008").rstrip("/")

    def web_host(self) -> str:
        return (self.cfg.get("web_host") or os.environ.get("CLEARML_WEB_HOST") or "http://localhost:8080").rstrip("/")

    def ping(self) -> tuple[bool, str]:
        try:
            r = httpx.get(self.api_host() + "/debug.ping", timeout=4)
            return r.status_code == 200, f"HTTP {r.status_code}"
        except httpx.HTTPError as e:
            return False, type(e).__name__

    def server_ready(self) -> bool:
        return self.configured() and cached("clearml_ping:" + self.api_host(), 15, self.ping)[0]

    def _server_env(self) -> dict:
        c = self.cfg
        env = {}
        for key, var in (("api_host", "CLEARML_API_HOST"), ("web_host", "CLEARML_WEB_HOST"), ("files_host", "CLEARML_FILES_HOST"),
                         ("access_key", "CLEARML_API_ACCESS_KEY"), ("secret_key", "CLEARML_API_SECRET_KEY")):
            if c.get(key):
                env[var] = c[key]
        for var in ("CLEARML_API_HOST", "CLEARML_WEB_HOST", "CLEARML_FILES_HOST", "CLEARML_API_ACCESS_KEY", "CLEARML_API_SECRET_KEY",
                    "CLEARML_CONFIG_FILE"):  # settings from the researcher's environment still apply
            if os.environ.get(var) and var not in env:
                env[var] = os.environ[var]
        return env

    def status(self) -> IntegrationStatus:
        setup_sdk = [f"pip install {SDK_PIN}   (or Control Center → Integrations → ⤓ Install ClearML SDK; setup.bat installs it)"]
        setup_server = ["Optional server: ClearML Server via its official docker compose (https://clear.ml/docs/latest/docs/deploying_clearml/clearml_server)",
                        "ClearML Web UI → Settings → Workspace → Create new credentials → paste API host, access key, secret key here"]
        if not self.cfg.get("enabled"):
            return IntegrationStatus("clearml", "ClearML", "disabled", "Disabled in the configuration.", setup=setup_sdk)
        if not self.sdk_installed():
            return IntegrationStatus("clearml", "ClearML", "unavailable", "Python package `clearml` is not installed.", setup=setup_sdk,
                                     extra={"mode": self.mode, "can_install": True})
        sdk = self.sdk()
        if not sdk["ok"]:
            return IntegrationStatus("clearml", "ClearML", "error", f"The ClearML SDK is installed but cannot be imported: {sdk['error']}",
                                     setup=setup_sdk, extra={"mode": self.mode, "can_install": True})
        if self.mode == "offline":
            ready = self.server_ready()
            caps = list(self.capabilities) + (["import_offline"] if ready else [])
            return IntegrationStatus("clearml", "ClearML", "available",
                                     f"offline mode (no server needed) · sessions in {clearml_dir() / 'offline'}"
                                     + (" · server reachable for import" if ready else ""), version=sdk["version"], capabilities=caps,
                                     setup=[] if ready else setup_server, extra={"mode": "offline", "server_ready": ready,
                                                                                 "offline_dir": str(clearml_dir() / "offline")})
        if not self.configured():
            return IntegrationStatus("clearml", "ClearML", "unconfigured", "Server mode: no API host / credentials (and no clearml.conf).",
                                     version=sdk["version"], setup=setup_server, extra={"mode": "server"})
        ok, why = cached("clearml_ping:" + self.api_host(), 15, self.ping)
        if not ok:
            return IntegrationStatus("clearml", "ClearML", "unavailable", f"API server {self.api_host()} not answering ({why}).",
                                     version=sdk["version"], setup=setup_server, extra={"mode": "server"})
        return IntegrationStatus("clearml", "ClearML", "available", f"server mode · API {self.api_host()} · Web {self.web_host()}",
                                 version=sdk["version"], capabilities=list(self.capabilities + self.server_capabilities),
                                 extra={"mode": "server", "web_host": self.web_host(), "project": self.cfg.get("project")})

    def _require(self, server: bool = False) -> IntegrationStatus:
        st = self.status()
        if not st.ok:
            raise IntegrationError(f"ClearML is {st.state}: {st.detail}")
        if server and not (self.mode == "server" or self.server_ready()):
            raise NotSupported("This needs a ClearML Server (offline mode records sessions locally; switch to server mode "
                               "or configure a reachable server)")
        return st

    def _server(self, cmd: str, args: dict, timeout: int = 900) -> dict:
        self._require(server=True)
        return run_worker(cmd, args, offline=False, env_extra=self._server_env(), timeout=timeout)

    # ---- fine-grained ExperimentBackend operations (server only: an offline session is one Task.init lifecycle)
    def create_experiment(self, name: str, project: str = "", params: dict | None = None, tags: list | None = None) -> dict:
        return self._server("op", {"op": "create", "name": name, "project": project or self.cfg.get("project"), "params": params or {},
                                   "tags": tags or []})

    def start_run(self, experiment_id: str) -> dict:
        return self._server("op", {"op": "start", "id": experiment_id})

    def log_metric(self, experiment_id: str, name: str, value: float, step: int = 0) -> None:
        self._server("op", {"op": "log_metric", "id": experiment_id, "name": name, "value": value, "step": step})

    def log_parameter(self, experiment_id: str, name: str, value) -> None:
        self._server("op", {"op": "log_parameter", "id": experiment_id, "name": name, "value": value})

    def log_artifact(self, experiment_id: str, name: str, path: str) -> dict:
        return self._server("op", {"op": "log_artifact", "id": experiment_id, "name": name, "path": str(path)})

    def log_model(self, experiment_id: str, name: str, path: str) -> dict:
        return self._server("op", {"op": "log_model", "id": experiment_id, "name": name, "path": str(path)})

    def finish_run(self, experiment_id: str, status: str = "completed") -> dict:
        return self._server("op", {"op": "finish", "id": experiment_id, "status": status})

    def list_experiments(self, limit: int = 50) -> list:
        return self._server("op", {"op": "list", "project": self.cfg.get("project"), "limit": limit})["tasks"]

    def get_experiment(self, experiment_id: str) -> dict:
        if OFFLINE_ID.match(experiment_id or ""):
            s = next((x for x in self.offline_sessions() if x["id"] == experiment_id), None)
            if not s:
                raise IntegrationError(f"Offline session {experiment_id} not found in this project")
            return {**read_offline_session(Path(s["path"])), "offline": True, "zip": s["zip"], "backend": self.name}
        if not SERVER_ID.match(experiment_id or ""):
            raise IntegrationError("Invalid ClearML task id")
        return {**self._server("get_task", {"id": experiment_id}), "backend": self.name}

    # ---- PhD Lab specific
    def record_run(self, run_id: str) -> dict:
        """Record a finished sandbox run in ClearML: offline session (offline mode) or a task on the server.
        If the training script itself created an offline session in its run folder, that session is linked instead."""
        from ..sandbox import SandboxError, get_run, runs_dir
        self._require()
        try:
            r = get_run(run_id)
        except SandboxError as e:
            raise IntegrationError(f"Run {run_id}: {e}")
        if r.get("status") in ("running", "queued"):
            raise IntegrationError("The run is still running — record it when it has finished")
        if (r.get("clearml") or {}).get("task_id"):
            return {**r["clearml"], "already_recorded": True}
        rd = runs_dir() / run_id
        own = sorted((rd / "clearml" / "offline").glob("offline-*.zip")) if (rd / "clearml" / "offline").is_dir() else []
        if own:  # the script used Task.init itself (CLEARML_OFFLINE_MODE was set for the run)
            info = {"mode": "offline", "task_id": own[-1].stem, "session_zip": self._rel(own[-1]), "source": "training script"}
        else:
            files = [str(rd / f) for f in (r.get("figures") or []) if (rd / f).is_file()]
            files += [str(p) for p in (rd / "metrics.json", rd / "provenance.json") if p.is_file()]
            files += [str(p) for p in rd.glob("*.csv")]
            payload = {"project": self.cfg.get("project"), "run": {
                "id": run_id, "title": r.get("title"), "cmd": r.get("cmd"), "status": r.get("status"), "git": r.get("git") or {},
                "environment": r.get("environment") or {}, "metrics": r.get("metrics") or {},
                "series": (r.get("parsed") or {}).get("series") or {}, "stdout_tail": (r.get("stdout") or "")[-20000:], "files": files}}
            offline = self.mode == "offline"
            out = run_worker("record_run", payload, offline=offline, env_extra={} if offline else self._server_env())
            info = {"mode": "offline" if offline else "server", "task_id": out["task_id"]}
            if offline:
                info["session_zip"] = self._rel(Path(out["session_zip"])) if out.get("session_zip") else ""
            else:
                info.update(url=out.get("url", ""), project=self.cfg.get("project"))
        info["recorded"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _store_pointer(run_id, info)
        return info

    sync_run = record_run  # v3.2 name used by the API

    def import_offline(self, run_id: str = "", zip_rel: str = "") -> dict:
        """Upload an offline session to the configured ClearML Server (needs a reachable server)."""
        from ..sandbox import get_run
        if run_id:
            ptr = (get_run(run_id).get("clearml") or {})
            zip_rel = ptr.get("session_zip", "")
            if ptr.get("server_task_id"):
                return {**ptr, "already_imported": True}
        z = self._abs(zip_rel)
        if not z.is_file():
            raise IntegrationError("Offline session zip not found")
        if not self.server_ready():
            raise IntegrationError("No reachable ClearML Server — fill API host and credentials (Integrations → ClearML) first")
        out = run_worker("import_offline", {"zip": str(z)}, offline=False, env_extra=self._server_env())
        if run_id:
            _store_pointer(run_id, {**ptr, "server_task_id": out["task_id"], "url": out.get("url", "")})
        return out

    def offline_sessions(self) -> list:
        """Offline sessions of this project: recorded by the app (<project>/clearml/offline) or by training scripts
        (<project>/runs/<id>/clearml/offline)."""
        from ..sandbox import runs_dir
        zips = list((clearml_dir() / "offline").glob("offline-*.zip")) + list(runs_dir().glob("*/clearml/offline/offline-*.zip"))
        out = []
        for z in sorted(zips, key=lambda p: p.stat().st_mtime, reverse=True):
            folder = z.with_suffix("")
            try:
                s = read_offline_session(folder if folder.is_dir() else z)
            except Exception as e:
                s = {"id": z.stem, "error": f"{type(e).__name__}: {e}"[:200]}
            out.append({**s, "id": s.get("id") or z.stem, "zip": self._rel(z), "path": str(folder if folder.is_dir() else z),
                        "size": z.stat().st_size, "created": datetime.fromtimestamp(z.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")})
        return out

    def submit_remote(self, script: str, args: dict | None = None, queue: str = "") -> dict:
        """Create a ClearML task for a script of the code workspace and enqueue it for a ClearML Agent (remote compute)."""
        from .. import gitops
        from ..sandbox import code_dir
        p = (code_dir() / script).resolve()
        if code_dir().resolve() not in p.parents or not p.is_file():
            raise IntegrationError("Script must be a file inside the code workspace")
        git = gitops.head_info()
        a = {"project": self.cfg.get("project"), "script": str(p.relative_to(code_dir().resolve())).replace("\\", "/"),
             "argparse_args": [[str(k), str(v)] for k, v in (args or {}).items()], "queue": queue or self.cfg.get("queue") or "default"}
        if git.get("remote") and git.get("sha"):
            if git.get("dirty"):
                raise IntegrationError("Commit and push your changes first: a remote agent clones the repository at a commit")
            a.update(repo=git["remote"], branch=git.get("branch") or "", commit=git["sha"])
        else:
            a["script"] = str(p)  # no remote repository: ClearML stores the single script file
        if (code_dir() / "requirements.txt").exists():
            a["requirements_file"] = str(code_dir() / "requirements.txt")
        return self._server("submit_remote", a)

    # ---- helpers
    @staticmethod
    def _rel(p: Path) -> str:
        try:
            return str(Path(p).resolve().relative_to(data_dir().resolve())).replace("\\", "/")
        except ValueError:
            return str(p)

    @staticmethod
    def _abs(rel: str) -> Path:
        p = (data_dir() / rel).resolve()
        if data_dir().resolve() not in p.parents:
            raise IntegrationError("Session path outside the project")
        return p


def run_env(run_dir_in_sandbox: str, cfg: dict | None = None) -> dict:
    """Environment for a sandbox run so a training script that calls Task.init records an offline session into its
    own run folder (no credentials are passed to user code)."""
    c = (cfg or load_config())["clearml"]
    if not c.get("enabled") or (c.get("mode") or "offline") != "offline":
        return {}
    return {"CLEARML_OFFLINE_MODE": "1", "CLEARML_CACHE_DIR": run_dir_in_sandbox.rstrip("/\\") + "/clearml"}


def auto_record(run_id: str) -> None:
    """Called after every finished sandbox run (background thread): record it when clearml.auto_record is on."""
    cfg = load_config()
    c = cfg["clearml"]
    if not (c.get("enabled") and c.get("auto_record")):
        return
    try:
        ClearMLAdapter(cfg).record_run(run_id)
    except Exception as e:
        _store_pointer(run_id, {"error": f"{type(e).__name__}: {e}"[:300]}, merge_error=True)


def _store_pointer(run_id: str, info: dict, merge_error: bool = False) -> None:
    from ..sandbox import JOBS, runs_dir
    from ..memory.store import quarantine, replace_retry
    f = runs_dir() / run_id / "run.json"
    d = {"id": run_id}
    if f.exists():
        try:
            d = json.loads(f.read_text("utf-8"))
        except ValueError:
            quarantine(f)  # keep the damaged record; the pointer is still stored
    if merge_error:
        if (d.get("clearml") or {}).get("task_id"):
            return
        d["clearml"] = info
    else:
        d["clearml"] = info
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=1), "utf-8")
    replace_retry(tmp, f)
    if run_id in JOBS:
        JOBS[run_id].meta["clearml"] = d["clearml"]
    if merge_error or not info.get("task_id"):
        return
    try:
        from ..memory.research import record_clearml
        record_clearml(run_id, info["task_id"], info.get("url", ""))
    except Exception:
        pass
    try:  # re-seal the run's artifacts so they carry the task id too
        from ..provenance import seal_run
        cfg = load_config()
        if cfg["provenance"].get("enabled", True):
            seal_run(runs_dir() / run_id, run_id, d, csv_header=cfg["provenance"].get("csv_header", True))
    except Exception:
        pass


def install_sdk() -> dict:
    """pip install the ClearML SDK into the Python that runs the app (explicit researcher action)."""
    from .base import clear_cache
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", SDK_PIN], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise IntegrationError("pip install clearml timed out")
    clear_cache()
    importlib.invalidate_caches()
    if r.returncode != 0:
        raise IntegrationError("pip install clearml failed: " + (r.stderr or r.stdout).strip()[-500:])
    return {"installed": True, "output": (r.stdout or "").strip()[-600:], "python": sys.executable}


def get_backend(name: str = "local", cfg: dict | None = None) -> ExperimentBackend:
    if name == "clearml":
        return ClearMLAdapter(cfg)
    if name == "local":
        return LocalRunsBackend()
    raise IntegrationError(f"Unknown experiment backend {name}")
