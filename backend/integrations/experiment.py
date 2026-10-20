"""ExperimentBackend abstraction (Target §9-10, Milestone 4).

    ExperimentBackend
      ├── LocalRunsBackend   the built-in sandbox runs (runs/<id>/run.json, metrics.json, figures) — always available
      └── ClearMLAdapter     ClearML Server through the official `clearml` SDK (optional; imported lazily, only here)

PhD Lab keeps the research meaning (memory/research.py) and only POINTERS to the tracker (task id, web URL); the tracker
keeps scalars, logs, artifacts. MLflow could be added as another subclass without touching the Research Core.

ClearML status is `available` only after GET <api_host>/debug.ping answered — never assumed.
"""
from __future__ import annotations

import importlib.util
import json
import os
from abc import ABC
from pathlib import Path

import httpx

from ..config import load_config
from .base import IntegrationError, IntegrationStatus, NotSupported, cached


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
def _clearml_conf_file() -> bool:
    p = os.environ.get("CLEARML_CONFIG_FILE") or str(Path.home() / "clearml.conf")
    return Path(p).is_file()


class ClearMLAdapter(ExperimentBackend):
    name = "clearml"
    capabilities = ("create_experiment", "log_metric", "log_parameter", "log_artifact", "log_model", "finish_run",
                    "get_experiment", "list_experiments", "compare_experiments", "sync_run", "submit_remote")

    def __init__(self, cfg: dict | None = None):
        self.cfg = (cfg or load_config())["clearml"]

    # ---- configuration & health
    def sdk_installed(self) -> bool:
        return importlib.util.find_spec("clearml") is not None

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

    def status(self) -> IntegrationStatus:
        setup = ["Self-host ClearML Server: docker compose -f docker-compose.yml up -d (https://clear.ml/docs/latest/docs/deploying_clearml/clearml_server_linux_mac)",
                 "pip install clearml   (into the Python that runs PhD Research Lab)",
                 "ClearML Web UI → Settings → Workspace → Create new credentials → paste API host, access key, secret key here"]
        if not self.cfg.get("enabled"):
            return IntegrationStatus("clearml", "ClearML", "disabled", "Disabled in the configuration.", setup=setup)
        if not self.sdk_installed():
            return IntegrationStatus("clearml", "ClearML", "unavailable", "Python package `clearml` is not installed.", setup=setup)
        if not self.configured():
            return IntegrationStatus("clearml", "ClearML", "unconfigured", "No API host / credentials (and no clearml.conf).", setup=setup)
        ok, why = cached("clearml_ping:" + self.api_host(), 15, self.ping)
        if not ok:
            return IntegrationStatus("clearml", "ClearML", "unavailable", f"API server {self.api_host()} not answering ({why}).", setup=setup)
        return IntegrationStatus("clearml", "ClearML", "available", f"API {self.api_host()} · Web {self.web_host()}",
                                 capabilities=list(self.capabilities), extra={"web_host": self.web_host(), "project": self.cfg.get("project")})

    def _require(self):
        st = self.status()
        if not st.ok:
            raise IntegrationError(f"ClearML is {st.state}: {st.detail}")
        from clearml import Task  # noqa: WPS433 — the only place the SDK is imported
        c = self.cfg
        if c.get("api_host") and c.get("access_key") and c.get("secret_key"):
            Task.set_credentials(api_host=c["api_host"], web_host=c.get("web_host") or None, files_host=c.get("files_host") or None,
                                 key=c["access_key"], secret=c["secret_key"])
        return Task

    # ---- core API
    def create_experiment(self, name: str, project: str = "", params: dict | None = None, tags: list | None = None) -> dict:
        Task = self._require()
        t = Task.create(project_name=project or self.cfg.get("project") or "PhD Research Lab", task_name=name[:200],
                        task_type=Task.TaskTypes.training)
        if params:
            t.set_parameters({f"General/{k}": v for k, v in params.items()})
        if tags:
            t.add_tags([str(x)[:60] for x in tags])
        return {"id": t.id, "url": t.get_output_log_web_page()}

    def _task(self, experiment_id: str):
        Task = self._require()
        t = Task.get_task(task_id=experiment_id)
        if t is None:
            raise IntegrationError(f"ClearML task {experiment_id} not found")
        return t

    def start_run(self, experiment_id: str) -> dict:
        t = self._task(experiment_id)
        t.mark_started(force=True)
        return {"id": t.id, "status": t.get_status()}

    def log_metric(self, experiment_id: str, name: str, value: float, step: int = 0) -> None:
        self._task(experiment_id).get_logger().report_scalar(title=name, series=name, value=float(value), iteration=int(step))

    def log_parameter(self, experiment_id: str, name: str, value) -> None:
        self._task(experiment_id).set_parameters({f"General/{name}": value})

    def log_artifact(self, experiment_id: str, name: str, path: str) -> dict:
        t = self._task(experiment_id)
        t.upload_artifact(name=name, artifact_object=Path(path), wait_on_upload=True)
        return {"name": name}

    def log_model(self, experiment_id: str, name: str, path: str) -> dict:
        from clearml import OutputModel
        t = self._task(experiment_id)
        m = OutputModel(task=t, name=name)
        m.update_weights(weights_filename=str(path))
        return {"model_id": m.id}

    def finish_run(self, experiment_id: str, status: str = "completed") -> dict:
        t = self._task(experiment_id)
        t.flush(wait_for_uploads=True)
        (t.mark_failed if status == "failed" else t.mark_completed)(status_message=f"set by PhD Research Lab ({status})")
        return {"id": t.id, "status": t.get_status()}

    def get_experiment(self, experiment_id: str) -> dict:
        t = self._task(experiment_id)
        last = {}
        try:
            for title, series in (t.get_last_scalar_metrics() or {}).items():
                for s, v in series.items():
                    last[title if s == title else f"{title}/{s}"] = v.get("last")
        except Exception:
            pass
        script = {}
        try:
            sc = t.data.script
            script = {"repository": getattr(sc, "repository", ""), "branch": getattr(sc, "branch", ""),
                      "commit": getattr(sc, "version_num", ""), "entry_point": getattr(sc, "entry_point", ""),
                      "working_dir": getattr(sc, "working_dir", "")}
        except Exception:
            pass
        return {"id": t.id, "name": t.name, "status": t.get_status(), "project": t.get_project_name(), "url": t.get_output_log_web_page(),
                "parameters": t.get_parameters() or {}, "metrics": last, "artifacts": sorted((t.artifacts or {}).keys()),
                "script": script, "backend": self.name}

    def list_experiments(self, limit: int = 50) -> list:
        Task = self._require()
        tasks = Task.get_tasks(project_name=self.cfg.get("project") or None) or []
        return [{"id": t.id, "name": t.name, "status": t.get_status()} for t in tasks[:limit]]

    # ---- PhD Lab specific
    def sync_run(self, run_id: str) -> dict:
        """Publish a finished local sandbox run to ClearML (params, scalar series, final values, figures, log tail) and
        store the task pointer in the run record + Research Memory. Returns {task_id, url}."""
        from ..sandbox import SandboxError, get_run, runs_dir
        Task = self._require()
        try:
            r = get_run(run_id)
        except SandboxError as e:
            raise IntegrationError(f"Run {run_id}: {e}")
        if r.get("status") in ("running", "queued"):
            raise IntegrationError("The run is still running — sync it when it has finished")
        if (r.get("clearml") or {}).get("task_id"):
            return {**r["clearml"], "already_synced": True}
        git = r.get("git") or {}
        t = Task.create(project_name=self.cfg.get("project") or "PhD Research Lab", task_name=f"{(r.get('title') or r.get('cmd') or run_id)[:120]} [{run_id}]",
                        task_type=Task.TaskTypes.training)
        t.set_parameters({"General/cmd": r.get("cmd", ""), "General/run_id": run_id, "General/git_sha": git.get("sha", ""),
                          "General/git_dirty": str(bool(git.get("dirty"))), "General/environment": json.dumps(r.get("environment") or {})})
        t.add_tags(["phd-research-lab", f"run:{run_id}"] + ([f"git:{git['sha'][:10]}"] if git.get("sha") else []))
        t.mark_started(force=True)
        log = t.get_logger()
        for name, points in ((r.get("parsed") or {}).get("series") or {}).items():
            for step, val in points:
                log.report_scalar(title=name, series=name, value=float(val), iteration=int(step))
        for name, val in (r.get("metrics") or {}).items():
            if isinstance(val, (int, float)):
                try:
                    log.report_single_value(name=name, value=float(val))
                except AttributeError:  # older SDK
                    log.report_scalar(title="final", series=name, value=float(val), iteration=0)
        if r.get("stdout"):
            log.report_text(r["stdout"][-20000:])
        rd = runs_dir() / run_id
        for rel in (r.get("figures") or [])[:20]:
            f = rd / rel
            if f.is_file():
                t.upload_artifact(name=rel.replace("/", "_"), artifact_object=f, wait_on_upload=True)
        if (rd / "metrics.json").exists():
            t.upload_artifact(name="metrics.json", artifact_object=rd / "metrics.json", wait_on_upload=True)
        t.flush(wait_for_uploads=True)
        (t.mark_failed if r.get("status") == "failed" else t.mark_completed)(status_message="synced from PhD Research Lab")
        info = {"task_id": t.id, "url": t.get_output_log_web_page(), "project": self.cfg.get("project")}
        _store_pointer(run_id, info)
        return info

    def submit_remote(self, script: str, args: dict | None = None, queue: str = "") -> dict:
        """Create a ClearML task for a script of the code workspace and enqueue it for a ClearML Agent (remote compute)."""
        from .. import gitops
        from ..sandbox import code_dir
        Task = self._require()
        p = (code_dir() / script).resolve()
        if code_dir().resolve() not in p.parents or not p.is_file():
            raise IntegrationError("Script must be a file inside the code workspace")
        git = gitops.head_info()
        kw = {"project_name": self.cfg.get("project") or "PhD Research Lab", "task_name": f"remote: {script}",
              "task_type": Task.TaskTypes.training, "script": str(p.relative_to(code_dir().resolve())).replace("\\", "/"),
              "working_directory": ".", "argparse_args": [(str(k), str(v)) for k, v in (args or {}).items()] or None}
        if git.get("remote") and git.get("sha"):
            if git.get("dirty"):
                raise IntegrationError("Commit and push your changes first: a remote agent clones the repository at a commit")
            kw.update(repo=git["remote"], branch=git.get("branch") or None, commit=git["sha"])
        else:
            kw["script"] = str(p)  # no remote repository: ClearML stores the single script file
        if (code_dir() / "requirements.txt").exists():
            kw["requirements_file"] = str(code_dir() / "requirements.txt")
        t = Task.create(**kw)
        Task.enqueue(t, queue_name=queue or self.cfg.get("queue") or "default")
        return {"task_id": t.id, "url": t.get_output_log_web_page(), "queue": queue or self.cfg.get("queue") or "default"}


def _store_pointer(run_id: str, info: dict) -> None:
    from ..sandbox import JOBS, runs_dir
    f = runs_dir() / run_id / "run.json"
    d = json.loads(f.read_text("utf-8")) if f.exists() else {"id": run_id}
    d["clearml"] = info
    f.write_text(json.dumps(d, indent=1), "utf-8")
    if run_id in JOBS:
        JOBS[run_id].meta["clearml"] = info
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


def get_backend(name: str = "local", cfg: dict | None = None) -> ExperimentBackend:
    if name == "clearml":
        return ClearMLAdapter(cfg)
    if name == "local":
        return LocalRunsBackend()
    raise IntegrationError(f"Unknown experiment backend {name}")
