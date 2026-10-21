"""Durable experiment bundles and ClearML result collection. Notebook is an artifact.

Colab execution is an explicit, attended handoff; no invented unattended runtime API.
Only explicitly selected files are bundled, and every transfer requires approval.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
import zipfile
from pathlib import Path
from urllib.parse import urlsplit, quote

from backend.core.config import data_dir, load_config
from backend.agent import write_json

_lock = threading.RLock()
TARGETS = ("local-gpu", "docker", "colab-gpu")


def folder(run_id: str) -> Path:
    if not re.fullmatch(r"rc-[0-9a-f]{12}", run_id):
        raise ValueError("Invalid remote run id")
    return data_dir() / "compute" / run_id


def get(run_id: str) -> dict:
    return json.loads((folder(run_id) / "run.json").read_text("utf-8"))


def list_runs() -> list:
    root = data_dir() / "compute"
    records = []
    for path in root.glob("rc-*/run.json"):
        try:
            record = get(path.parent.name)
            if not isinstance(record, dict) or not isinstance(record.get("created"), (int, float)):
                raise ValueError("Invalid experiment record")
            records.append(record)
        except ValueError:
            from backend.memory.store import quarantine
            if not any(path.parent.glob(path.name + ".corrupt-*")):
                quarantine(path)
        except OSError:
            continue
    return sorted(records, key=lambda r: -r["created"])


def sha(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def create(spec: dict) -> dict:
    from backend.execution.code_projects import active_dir
    from backend.providers.firewall import SECRET
    from backend.execution.tools import run_cli
    root = active_dir().resolve()
    from backend.core.telemetry import redact
    serialized = json.dumps(spec)
    if redact(serialized) != serialized:
        raise ValueError("Credentials must not be included in an experiment specification")
    target = spec.get("compute_target", "colab-gpu")
    if target not in TARGETS:
        raise ValueError("Unknown compute target")
    raw_files = spec.get("files") or []
    if not isinstance(raw_files, list) or any(not isinstance(name, str) for name in raw_files):
        raise ValueError("files must be a list of relative file names")
    files = list(dict.fromkeys(raw_files))
    if not files or len(files) > 200:
        raise ValueError("Select 1–200 code/config files explicitly")
    selected, total = [], 0
    for name in files:
        rel = Path(name)
        path = (root / rel).resolve()
        if rel.is_absolute() or not path.is_relative_to(root) or not path.is_file() or (root / rel).is_symlink():
            raise ValueError("File is outside the selected code project: " + str(name))
        if any(SECRET.match(part) or part.startswith(".") or part in ("data", "credentials", "node_modules", "venv") for part in rel.parts):
            raise ValueError("Private/config/cache path refused: " + str(name))
        if path.suffix.lower() not in (".py", ".txt", ".json", ".yaml", ".yml", ".toml", ".ipynb", ".md", ".cfg"):
            raise ValueError("Only code, notebook and configuration text files belong in the bundle")
        total += path.stat().st_size
        if total > 100 * 1024 * 1024:
            raise ValueError("Code bundle exceeds 100 MiB; use a versioned dataset transfer provider for large data")
        content = path.read_text("utf-8")
        if redact(content) != content:
            raise ValueError("Possible credential in selected file: " + str(name))
        selected.append((rel.as_posix(), path))
    entry = str(spec.get("entrypoint") or "train.py")
    if entry not in files:
        raise ValueError("Entrypoint must be included in selected files")
    required = spec.get("required_artifacts") or ["metrics.json", "best.pt"]
    if not isinstance(required, list) or not required or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", n) for n in required):
        raise ValueError("Artifact names must be simple file names")
    manifest = spec.get("dataset_manifest") or []
    if not isinstance(manifest, list):
        raise ValueError("dataset_manifest must be a list of {path, sha256}")
    for item in manifest:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or Path(item["path"]).is_absolute() or ".." in Path(item["path"]).parts or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise ValueError("Dataset files need relative paths and SHA-256 checksums")
    rid = "rc-" + secrets.token_hex(6)
    rd = folder(rid)
    rd.mkdir(parents=True)
    _, commit = run_cli(["git", "-C", str(root), "rev-parse", "HEAD"], 5)
    record = {"run_id": rid, "experiment_id": str(spec.get("experiment_id") or rid), "project_id": data_dir().name,
              "hypothesis_id": str(spec.get("hypothesis_id") or ""), "clearml_task_id": "", "compute_target": target,
              "dataset_version": str(spec.get("dataset_version") or ""), "dataset_manifest": manifest,
              "code_commit": commit.strip() if re.fullmatch(r"[0-9a-f]{40,64}\s*", commit) else "",
              "status": "awaiting_approval", "created": time.time(), "metrics": {}, "artifact_refs": [],
              "required_artifacts": required, "approvals": [], "entrypoint": entry,
              "files": [{"path": name, "sha256": sha(path)} for name, path in selected],
              "evaluation": {"phase": "exploration", "held_out_test": "not_evaluated", "researcher_review": "pending"}}
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [
        {"cell_type": "markdown", "metadata": {}, "source": [f"# PhD Lab {rid}\n", "Approved bundle only. Configure ClearML credentials in the runtime, never in this notebook.\n", "Extract the bundle, verify manifest hashes, install approved requirements and mount your versioned dataset first." ]},
        {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": [
            "import torch\n", "assert torch.cuda.is_available(), 'GPU runtime required'\n", "print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))\n"]},
        {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": [
            "# After extracting the approved bundle, set cwd to its folder.\n",
            "# Configure ClearML credentials securely and PHDLAB_DATASET_DIR for the mounted dataset.\n",
            "# Install the reviewed code/requirements.txt in this runtime first.\n",
            "%run launch.py\n"]}]}
    launcher = '''"""Run the approved bundle in an attended local/Docker/Colab runtime."""
import hashlib, json, os, runpy, sys
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
for item in manifest['files']:
    path = (root / 'code' / item['path']).resolve()
    if not path.is_relative_to((root / 'code').resolve()):
        raise RuntimeError('Code path outside bundle')
    if digest(path) != item['sha256']:
        raise RuntimeError('Code/config checksum mismatch: ' + item['path'])
if manifest['dataset_manifest']:
    dataset = Path(os.environ['PHDLAB_DATASET_DIR']).resolve()
    for item in manifest['dataset_manifest']:
        path = (dataset / item['path']).resolve()
        if not path.is_relative_to(dataset):
            raise RuntimeError('Dataset path outside mount')
        if digest(path) != item['sha256']:
            raise RuntimeError('Dataset checksum mismatch: ' + item['path'])
if manifest['compute_target'] in ('local-gpu', 'colab-gpu'):
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('Approved run requires a GPU runtime')
    print('Runtime:', torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))
from clearml import Task
task = Task.init(project_name='PhD Research Lab', task_name=manifest['run_id'], reuse_last_task_id=False)
task.set_parameter('General/run_id', manifest['run_id'])
task.set_parameter('General/code_commit', manifest['code_commit'])
task.set_parameter('General/dataset_version', manifest['dataset_version'])
output = root / 'outputs'
output.mkdir(exist_ok=True)
os.environ['RUN_DIR'] = str(output)
os.chdir(root / 'code')
sys.argv = [manifest['entrypoint']]
sys.path.insert(0, str(root / 'code'))
try:
    runpy.run_path(manifest['entrypoint'], run_name='__main__')
    for name in manifest['required_artifacts']:
        path = output / name
        if not path.is_file():
            raise RuntimeError('Required output missing: ' + name)
        task.upload_artifact(name=name, artifact_object=str(path), wait_on_upload=True)
    metrics = output / 'metrics.json'
    if metrics.is_file():
        for name, value in json.loads(metrics.read_text('utf-8')).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                task.get_logger().report_single_value(name=name, value=value)
    task.close()
except BaseException as exc:
    task.mark_failed(status_reason=type(exc).__name__)
    task.close()
    raise
'''
    with zipfile.ZipFile(rd / "bundle.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name, path in selected:
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != next(f["sha256"] for f in record["files"] if f["path"] == name):
                raise ValueError("Selected file changed during bundle preparation")
            z.writestr("code/" + name, content)
        z.writestr("manifest.json", json.dumps(record, indent=2))
        z.writestr("launch.ipynb", json.dumps(notebook, indent=2))
        z.writestr("launch.py", launcher)
    record["bundle_sha256"] = sha(rd / "bundle.zip")
    write_json(rd / "run.json", record)
    return record


def approve(run_id: str) -> dict:
    with _lock:
        r = get(run_id)
        if r["status"] != "awaiting_approval":
            return r
        if sha(folder(run_id) / "bundle.zip") != r["bundle_sha256"]:
            raise ValueError("Bundle changed after review")
        r["approvals"].append({"action": "release_bundle", "by": "researcher", "at": time.time(), "sha256": r["bundle_sha256"]})
        r["status"] = "ready_for_handoff"
        write_json(folder(run_id) / "run.json", r)
        return r


def bundle(run_id: str) -> Path:
    r = get(run_id)
    if not r["approvals"]:
        raise ValueError("Review and approve the bundle before downloading/transferring")
    path = folder(run_id) / "bundle.zip"
    if sha(path) != r["bundle_sha256"]:
        raise ValueError("Bundle checksum mismatch")
    return path


def sync(run_id: str, task_id: str = "", collect: bool = False) -> dict:
    from backend.execution.tracker import run_worker
    with _lock:
        r = get(run_id)
        if not r["approvals"]:
            raise ValueError("Approve experiment first")
        tid = task_id or r["clearml_task_id"]
        if not re.fullmatch(r"[a-zA-Z0-9-]{8,80}", tid) or tid.startswith("offline-"):
            raise ValueError("A real online ClearML task id is required")
        if r["clearml_task_id"] and r["clearml_task_id"] != tid:
            raise ValueError("Cannot replace the linked task; create a new run")
        dest = folder(run_id) / "artifacts"
        out = run_worker("remote_snapshot", {"task_id": tid, "run_id": run_id, "collect": collect,
                         "required_artifacts": r["required_artifacts"], "destination": str(dest)}, online=True)
        r.update(clearml_task_id=tid, metrics=out.get("metrics") or {}, remote_status=out["status"])
        refs = out.get("artifacts") or []
        for a in refs:
            if a["name"] not in r["required_artifacts"] or sha(dest / a["name"]) != a["sha256"]:
                raise ValueError("Collected artifact verification failed")
        if refs:
            r["artifact_refs"] = refs
        for a in r["artifact_refs"]:
            if sha(dest / a["name"]) != a["sha256"]:
                raise ValueError("Previously collected artifact changed; collect again")
        complete = out["status"] == "completed" and (collect or r["status"] == "completed") and set(r["required_artifacts"]) <= {a["name"] for a in r["artifact_refs"]}
        r["status"] = "completed" if complete else ("awaiting_collection" if out["status"] == "completed" else out["status"])
        url = load_config()["clearml"].get("web_url", "").rstrip("/")
        project = out.get("project_id", "")
        if urlsplit(url).scheme in ("http", "https") and isinstance(project, str) and re.fullmatch(r"[a-zA-Z0-9-]{8,80}", project):
            r["clearml_url"] = url + "/projects/" + quote(project, safe="") + "/experiments/" + quote(tid, safe="") + "/output/execution"
        write_json(folder(run_id) / "run.json", r)
        return r
