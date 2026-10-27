"""Durable approved compute bundles and native result collection. Notebook is an artifact.

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
import stat
import shutil
import tempfile
import math
from pathlib import Path

from backend.core.config import data_dir
from backend.agent import write_json

_lock = threading.RLock()
TARGETS = ("local-gpu", "docker", "colab-gpu")


def folder(run_id: str) -> Path:
    if not re.fullmatch(r"rc-[0-9a-f]{12}", run_id):
        raise ValueError("Invalid remote run id")
    from backend.knowledge.research_store import safe_child
    return safe_child(data_dir(), 'compute/' + run_id)


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
        if '\\' in name or ':' in name or any(part in ('','.', '..') for part in name.split('/')):
            raise ValueError('Use canonical project-relative file paths with / separators')
        rel = Path(name)
        from backend.knowledge.research_store import safe_child
        path = safe_child(root, name)
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
    if not isinstance(required, list) or not required or len(required)>200 or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", n) for n in required):
        raise ValueError("Artifact names must be simple file names")
    required = list(dict.fromkeys(required))
    if any(name.endswith('.') or name.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *('COM'+str(n) for n in range(1,10)), *('LPT'+str(n) for n in range(1,10))} for name in required):
        raise ValueError('Reserved device names are not portable artifact names')
    seconds = spec.get('max_seconds', 3600)
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 86400:
        raise ValueError('max_seconds must be an integer between 1 and 86400')
    manifest = spec.get("dataset_manifest") or []
    if not isinstance(manifest, list):
        raise ValueError("dataset_manifest must be a list of {path, sha256}")
    for item in manifest:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or '\\' in item['path'] or ':' in item['path'] or any(part in ('','.', '..') for part in item['path'].split('/')) or Path(item["path"]).is_absolute() or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise ValueError("Dataset files need relative paths and SHA-256 checksums")
    if len(manifest)>10000 or len({item['path'].casefold() for item in manifest})!=len(manifest):
        raise ValueError('Dataset manifest contains duplicate paths or exceeds 10000 files')
    rid = "rc-" + secrets.token_hex(6)
    rd = folder(rid)
    rd.mkdir(parents=True)
    _, commit = run_cli(["git", "-C", str(root), "rev-parse", "HEAD"], 5)
    record = {"run_id": rid, "experiment_id": str(spec.get("experiment_id") or rid), "project_id": data_dir().name,
              "hypothesis_id": str(spec.get("hypothesis_id") or ""), "backend": "native", "compute_target": target,
              "dataset_version": str(spec.get("dataset_version") or ""), "dataset_manifest": manifest,
              "code_commit": commit.strip() if re.fullmatch(r"[0-9a-f]{40,64}\s*", commit) else "",
              "status": "awaiting_approval", "created": time.time(), "metrics": {}, "artifact_refs": [],
              "required_artifacts": required, "approvals": [], "entrypoint": entry, "max_seconds": seconds,
              "files": [{"path": name, "sha256": sha(path)} for name, path in selected],
              "evaluation": {"phase": "exploration", "held_out_test": "not_evaluated", "researcher_review": "pending"}}
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [
        {"cell_type": "markdown", "metadata": {}, "source": [f"# PhD Lab {rid}\n", "Approved bundle only. No tracking service credentials are required.\n", "Extract the bundle, verify manifest hashes, install approved requirements and mount your versioned dataset first." ]},
        {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": [
            "import torch\n", "assert torch.cuda.is_available(), 'GPU runtime required'\n", "print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))\n"]},
        {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": [
            "# After extracting the approved bundle, set cwd to its folder.\n",
            "# Set PHDLAB_DATASET_DIR for the mounted versioned dataset.\n",
            "# Install the reviewed code/requirements.txt in this runtime first.\n",
            "%run launch.py\n"]}]}
    launcher = Path(__file__).with_name('remote_runner.py').read_text('utf-8')
    manifest_json = json.dumps(record, indent=2, allow_nan=False)
    with zipfile.ZipFile(rd / "bundle.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for name, path in selected:
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != next(f["sha256"] for f in record["files"] if f["path"] == name):
                raise ValueError("Selected file changed during bundle preparation")
            z.writestr("code/" + name, content)
        z.writestr("manifest.json", manifest_json)
        z.writestr("launch.ipynb", json.dumps(notebook, indent=2))
        z.writestr("launch.py", launcher)
    record["bundle_sha256"] = sha(rd / "bundle.zip")
    record["manifest_sha256"] = hashlib.sha256(manifest_json.encode('utf-8')).hexdigest()
    write_json(rd / "run.json", record)
    return record


def approve(run_id: str) -> dict:
    with _lock:
        r = get(run_id)
        if r.get('backend')!='native':
            raise ValueError('Historical software-service handoffs are read-only; create a native bundle')
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
    """Historical route remains explicit; never contact the retired tracking service."""
    from backend.execution.tools import IntegrationError
    get(run_id)
    raise IntegrationError("ClearML synchronization is retired. Upload the native results.zip from the approved bundle; old task references remain preserved.")


def imported_file(run_id: str, digest: str, name: str) -> Path:
    from backend.knowledge.research_store import safe_child
    record = get(run_id)
    if not re.fullmatch(r'[0-9a-f]{64}',digest) or not any(item['sha256']==digest for item in record.get('imports', [])):
        raise ValueError('Unknown retained native import')
    root = safe_child(folder(run_id),'imports',digest)
    receipt_path = safe_child(root,'execution.json')
    with zipfile.ZipFile(safe_child(root,'results.zip')) as archive:
        expected = json.loads(archive.read('execution.json'))
    if sha(safe_child(root,'results.zip'))!=digest or json.loads(receipt_path.read_text('utf-8'))!=expected:
        raise ValueError('Retained import or receipt changed; preserve it for review')
    artifact = next((item for item in expected['artifacts'] if item['name']==name), None)
    if artifact is None:raise ValueError('Unknown imported artifact')
    path = safe_child(root,'artifacts',name)
    if sha(path)!=artifact['sha256']:raise ValueError('Imported artifact changed')
    return path


def import_results(run_id: str, archive_path: Path) -> dict:
    """Validate a returned bundle without running its code or trusting remote claims.

    Preserve each import and failed result. Hashes establish transfer/lineage integrity,
    not remote authenticity, reproducibility, held-out validity or scientific approval.
    """
    with _lock:
        record = get(run_id)
        bundle(run_id)  # exact reviewed bundle must still be intact
        if record.get('backend') != 'native' or not record.get('manifest_sha256'):
            raise ValueError('Historical service runs are read-only; create a native handoff to import results')
        if archive_path.stat().st_size > 256*1024*1024:
            raise ValueError('Results archive exceeds 256 MiB')
        archive_hash = sha(archive_path)
        imports = record.get('imports') or []
        prior = next((item for item in imports if item['sha256']==archive_hash), None)
        if prior:
            from backend.knowledge.research_store import safe_child
            original = safe_child(folder(run_id), prior['path'])
            if sha(safe_child(original, 'results.zip'))!=archive_hash:
                raise ValueError('Previously imported archive changed; preserve it for review')
            with zipfile.ZipFile(safe_child(original,'results.zip')) as archive:
                receipt=json.loads(archive.read('execution.json'))
            if json.loads(safe_child(original,'execution.json').read_text('utf-8'))!=receipt:
                raise ValueError('Previously imported receipt changed; preserve it for review')
            for item in receipt['artifacts']:
                if sha(safe_child(original,'artifacts',item['name']))!=item['sha256']:
                    raise ValueError('Previously imported artifact changed; preserve it for review')
            return record
        from backend.knowledge.research_store import safe_child
        parent = safe_child(folder(run_id), 'imports')
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.import-', dir=parent) as temporary:
            staged = Path(temporary)
            with zipfile.ZipFile(archive_path) as archive:
                members = archive.infolist()
                names = [item.filename for item in members]
                if len(names)>202 or len(names)!=len(set(names)) or len(names)!=len({name.casefold() for name in names}):
                    raise ValueError('Duplicate, colliding or excessive result entries')
                if 'execution.json' not in names or archive.getinfo('execution.json').file_size>1024*1024:
                    raise ValueError('Missing or oversized execution receipt')
                if sum(item.file_size for item in members)>256*1024*1024:
                    raise ValueError('Expanded results exceed 256 MiB')
                for item in members:
                    mode = item.external_attr >> 16
                    if item.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                        raise ValueError('Result bundle must contain regular files only')
                receipt = json.loads(archive.read('execution.json'),
                    parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite result value')))
                if not isinstance(receipt, dict) or receipt.get('schema_version')!=1 or receipt.get('backend')!='native' or receipt.get('run_id')!=run_id or receipt.get('manifest_sha256')!=record['manifest_sha256']:
                    raise ValueError('Result receipt does not match the approved native run/manifest')
                if receipt.get('status') not in ('completed','failed') or not isinstance(receipt.get('metrics'), dict):
                    raise ValueError('Invalid result status or metrics')
                if receipt.get('code_checksums_verified') is not True or not isinstance(receipt.get('environment'),dict):
                    raise ValueError('Worker did not report verified code inputs and its environment')
                if any(type(receipt.get(key)) not in (int,float) or not math.isfinite(receipt[key]) for key in ('started','ended')) or receipt['ended']<receipt['started']:
                    raise ValueError('Invalid worker execution interval')
                if record['dataset_manifest'] and receipt.get('dataset_checksums_verified') is not True:
                    raise ValueError('Worker did not report dataset checksum validation')
                if receipt['status']=='completed' and (type(receipt.get('exit_code')) is not int or receipt['exit_code']!=0 or receipt.get('missing_artifacts') or receipt.get('failure')):
                    raise ValueError('Completed result requires exit zero and all required outputs')
                refs = receipt.get('artifacts')
                if not isinstance(refs, list) or len(refs)>201:
                    raise ValueError('Invalid artifact manifest')
                seen = set()
                for ref in refs:
                    if not isinstance(ref, dict):raise ValueError('Invalid artifact entry')
                    name = ref.get('name')
                    if not isinstance(name, str) or name not in record['required_artifacts']+['execution.log'] or name in seen:
                        raise ValueError('Unexpected or duplicate result artifact')
                    seen.add(name)
                    member = 'artifacts/'+name
                    if member not in names or not re.fullmatch(r'[0-9a-f]{64}', str(ref.get('sha256',''))) or type(ref.get('bytes')) is not int or ref['bytes']!=archive.getinfo(member).file_size:
                        raise ValueError('Missing artifact or invalid digest/size')
                    target = safe_child(staged, member)
                    target.parent.mkdir(exist_ok=True)
                    with archive.open(member) as source, target.open('xb') as destination:
                        shutil.copyfileobj(source, destination, 1024*1024)
                    if sha(target)!=ref['sha256']:
                        raise ValueError('Artifact checksum mismatch: '+name)
                if set(names)!={'execution.json'}|{'artifacts/'+name for name in seen}:
                    raise ValueError('Unlisted files in result bundle')
                if receipt['status']=='completed' and not set(record['required_artifacts'])<=seen:
                    raise ValueError('Completed receipt is missing required artifacts')
                if 'metrics.json' in seen:
                    if safe_child(staged,'artifacts/metrics.json').stat().st_size>1024*1024:
                        raise ValueError('Metrics exceed the 1 MiB JSON limit; retain large measurements as separate artifacts')
                    metrics = json.loads(safe_child(staged,'artifacts/metrics.json').read_text('utf-8'),
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite metric')))
                    if metrics!=receipt['metrics']:
                        raise ValueError('Receipt metrics differ from the raw metrics artifact')
                elif receipt['metrics']:
                    raise ValueError('Metrics require the raw metrics.json artifact')
                write_json(staged/'execution.json', receipt)
            destination = safe_child(parent, archive_hash)
            if destination.exists():
                raise ValueError('Unpublished import folder exists; preserve it for recovery review')
            shutil.copyfile(archive_path, staged/'results.zip')
            if sha(staged/'results.zip')!=archive_hash:
                raise ValueError('Upload changed during import')
            staged.rename(destination)
        imports.append({'sha256': archive_hash, 'at': time.time(), 'status': receipt['status'],
                        'path': 'imports/'+archive_hash, 'execution_origin':'worker_reported'})
        record.update(imports=imports, status=receipt['status'], metrics=receipt['metrics'],
            remote_status=receipt['status'], artifact_refs=[{**item,'path':'imports/'+archive_hash+'/artifacts/'+item['name']} for item in refs],
            execution_receipt='imports/'+archive_hash+'/execution.json',
            verification={'transfer_integrity':'VERIFIED', 'remote_authenticity':'NOT_VERIFIED',
                          'reproduction':'NOT_RUN','scientific_review':'pending'})
        write_json(folder(run_id)/'run.json', record)
        return record
