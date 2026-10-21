"""ClearML offline recording (background, no server): every finished run is recorded as a ClearML offline session
(zip) inside the project — <project>/clearml/offline/ — that can be imported into a ClearML Server later, unchanged.

The SDK is never imported by the web server: the SDK call runs in clearml_worker.py as a separate Python process
(Task.init hooks its process; the SDK's native dependencies may be blocked by Windows Smart App Control). PhD Lab keeps
the research meaning (memory/research.py) and only a POINTER to the session (task id + zip path).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.core.config import data_dir, load_config
from backend.execution.tools import NO_WINDOW, IntegrationError

WORKER = Path(__file__).with_name("clearml_worker.py")


def clearml_dir() -> Path:
    """Per-project ClearML cache (CLEARML_CACHE_DIR of the worker); offline sessions land in <this>/offline/."""
    d = data_dir() / "clearml"
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_worker(cmd: str, args: dict, timeout: int = 900, online: bool = False) -> dict:
    if online and not load_config()["clearml"].get("server_enabled"):
        raise IntegrationError("Enable ClearML Server integration and configure clearml.conf first")
    env = {k: v for k, v in os.environ.items() if online or not k.startswith(("CLEARML_", "TRAINS_"))}
    if online:
        env["CLEARML_OFFLINE_MODE"] = "0"
    env.update(PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", CLEARML_CACHE_DIR=str(clearml_dir()))
    try:
        r = subprocess.run([sys.executable, str(WORKER)], input=json.dumps({"cmd": cmd, "args": args, "offline": not online}),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env,
                           cwd=str(data_dir()), creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise IntegrationError(f"ClearML {cmd} timed out after {timeout} s")
    except OSError as e:
        raise IntegrationError(f"Could not start the ClearML worker: {e}")
    # the SDK keeps printing at interpreter exit, so the marker is not always the last line
    marked = [ln for ln in (r.stdout or "").splitlines() if ln.startswith(("@@RESULT@@", "@@ERROR@@"))]
    last = marked[-1] if marked else ""
    if last.startswith("@@RESULT@@"):
        return json.loads(last[len("@@RESULT@@"):])
    if last.startswith("@@ERROR@@"):
        raise IntegrationError("ClearML: " + json.loads(last[len("@@ERROR@@"):]).get("error", "unknown error"))
    tail = (r.stderr or r.stdout or "").strip()[-400:]
    raise IntegrationError(f"ClearML worker exited with code {r.returncode}: {tail or 'no output'}")


def _rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(data_dir().resolve())).replace("\\", "/")
    except ValueError:
        return str(p)


def record_run(run_id: str, project: str = "PhD Research Lab") -> dict:
    """Record a finished run as an offline session. If the training script itself created an offline session in its run
    folder (CLEARML_OFFLINE_MODE was set for the run), that session is linked instead."""
    from backend.execution.sandbox import get_run, runs_dir
    r = get_run(run_id)
    if (r.get("clearml") or {}).get("task_id"):
        return {**r["clearml"], "already_recorded": True}
    rd = runs_dir() / run_id
    own = sorted((rd / "clearml" / "offline").glob("offline-*.zip"))
    if own:
        info = {"mode": "offline", "task_id": own[-1].stem, "session_zip": _rel(own[-1]), "source": "training script"}
    else:
        files = [str(rd / f) for f in (r.get("figures") or []) if (rd / f).is_file()]
        files += [str(p) for p in (rd / "metrics.json", rd / "provenance.json") if p.is_file()]
        files += [str(p) for p in rd.glob("*.csv")]
        payload = {"project": project, "run": {
            "id": run_id, "title": r.get("title"), "cmd": r.get("cmd"), "status": r.get("status"), "git": r.get("git") or {},
            "environment": r.get("environment") or {}, "metrics": r.get("metrics") or {},
            "series": (r.get("parsed") or {}).get("series") or {}, "stdout_tail": (r.get("stdout") or "")[-20000:], "files": files}}
        out = run_worker("record_run", payload)
        info = {"mode": "offline", "task_id": out["task_id"], "session_zip": _rel(Path(out["session_zip"])) if out.get("session_zip") else ""}
    info["recorded"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _store_pointer(run_id, info)
    return info


def run_env(run_dir_in_sandbox: str, cfg: dict | None = None) -> dict:
    """Environment for a run so a training script that calls Task.init records an offline session into its own run
    folder (no credentials are passed to user code)."""
    if not (cfg or load_config())["clearml"].get("enabled"):
        return {}
    return {"CLEARML_OFFLINE_MODE": "1", "CLEARML_CACHE_DIR": run_dir_in_sandbox.rstrip("/\\") + "/clearml"}


def auto_record(run_id: str) -> None:
    """Called after every finished run (background thread): record it when clearml.auto_record is on and the SDK exists."""
    c = load_config()["clearml"]
    if not (c.get("enabled") and c.get("auto_record")) or importlib.util.find_spec("clearml") is None:
        return
    try:
        record_run(run_id, c.get("project") or "PhD Research Lab")
    except Exception as e:
        _store_pointer(run_id, {"error": f"{type(e).__name__}: {e}"[:300]})


def _store_pointer(run_id: str, info: dict) -> None:
    from backend.execution.sandbox import JOBS, runs_dir
    from backend.memory.store import quarantine, replace_retry
    f = runs_dir() / run_id / "run.json"
    d = {"id": run_id}
    if f.exists():
        try:
            d = json.loads(f.read_text("utf-8"))
        except ValueError:
            quarantine(f)  # keep the damaged record; the pointer is still stored
    if "error" in info and (d.get("clearml") or {}).get("task_id"):
        return
    d["clearml"] = info
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=1), "utf-8")
    replace_retry(tmp, f)
    if run_id in JOBS:
        JOBS[run_id].meta["clearml"] = d["clearml"]
    if not info.get("task_id"):
        return
    from backend.memory.research import record_clearml
    record_clearml(run_id, info["task_id"], info.get("url", ""))
    cfg = load_config()
    if cfg["provenance"].get("enabled", True):  # re-seal the run's artifacts so they carry the task id too
        from backend.knowledge.provenance import seal_run
        seal_run(runs_dir() / run_id, run_id, d, csv_header=cfg["provenance"].get("csv_header", True))
