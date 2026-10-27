"""Portable native launcher, copied into an explicitly approved compute bundle.

No PhD backend imports, service account or tracking SDK is required on the worker.
The returned receipt is worker-reported execution evidence, not scientific review
or an authenticated attestation of the remote machine.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import zipfile

MAX_RESULT_BYTES = 256 * 1024 * 1024


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def contained(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError('Path outside approved bundle: ' + str(name))
    return path


def main():
    root = Path(__file__).resolve().parent
    manifest_path = root / 'manifest.json'
    manifest = json.loads(manifest_path.read_text('utf-8'))
    code = root / 'code'
    for item in manifest['files']:
        if digest(contained(code, item['path'])) != item['sha256']:
            raise RuntimeError('Code/config checksum mismatch: ' + item['path'])
    if manifest['dataset_manifest']:
        dataset = Path(os.environ['PHDLAB_DATASET_DIR']).resolve()
        for item in manifest['dataset_manifest']:
            if digest(contained(dataset, item['path'])) != item['sha256']:
                raise RuntimeError('Dataset checksum mismatch: ' + item['path'])
    environment = {'python': sys.version, 'platform': platform.platform()}
    if manifest['compute_target'] in ('local-gpu', 'colab-gpu'):
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('Approved run requires a GPU runtime')
        environment.update(torch=torch.__version__, cuda=torch.version.cuda,
                           gpu=torch.cuda.get_device_name(0))
    output = root / 'outputs'
    if output.exists():
        raise RuntimeError('outputs/ already exists; retain it and extract a fresh bundle for a new execution')
    output.mkdir()
    started = time.time()
    receipt = {'schema_version': 1, 'backend': 'native', 'run_id': manifest['run_id'],
               'manifest_sha256': digest(manifest_path), 'started': started,
               'environment': environment, 'dataset_checksums_verified': bool(manifest['dataset_manifest']),
               'code_checksums_verified': True, 'artifacts': [], 'metrics': {},
               'scientific_review': 'pending', 'execution_origin': 'worker_reported'}
    log = output / 'execution.log'
    failure = ''
    exit_code = None
    try:
        with log.open('wb') as stream:
            options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session': True}
            proc = subprocess.Popen([sys.executable, str(contained(code, manifest['entrypoint']))],
                cwd=code, env={**os.environ, 'RUN_DIR': str(output)}, stdout=stream,
                stderr=subprocess.STDOUT, **options)
            try:
                proc.wait(timeout=manifest.get('max_seconds', 3600))
            except subprocess.TimeoutExpired:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
                else:
                    try:os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:pass
                proc.wait(timeout=15)
                raise
        exit_code = proc.returncode
        if exit_code != 0:
            failure = 'Process exited with code ' + str(exit_code)
    except subprocess.TimeoutExpired:
        failure = 'Approved execution time limit exceeded'
    except OSError as exc:
        failure = type(exc).__name__ + ': ' + str(exc)
    for item in manifest['files']:
        path = contained(code, item['path'])
        if not path.is_file() or digest(path)!=item['sha256']:
            failure = failure or 'Approved source changed during execution: '+item['path']
    names = list(dict.fromkeys(manifest['required_artifacts'] + ['execution.log']))
    selected = []
    total = 0
    missing = []
    for name in names:
        path = contained(output, name)
        if not path.is_file() or path.is_symlink():
            if name in manifest['required_artifacts']:
                missing.append(name)
            continue
        size = path.stat().st_size
        total += size
        if total > MAX_RESULT_BYTES:
            raise RuntimeError('Results exceed 256 MiB; retain outputs and use an explicitly reviewed larger transfer')
        selected.append((name, path))
        receipt['artifacts'].append({'name': name, 'bytes': size, 'sha256': digest(path)})
    metrics_path = output / 'metrics.json'
    if metrics_path.is_file():
        try:
            metrics = json.loads(metrics_path.read_text('utf-8'),
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite metric: ' + value)))
            if not isinstance(metrics, dict):
                raise ValueError('metrics.json must be an object')
            receipt['metrics'] = metrics
        except (ValueError, UnicodeError) as exc:
            failure = failure or 'Invalid metrics.json: ' + str(exc)
    if missing:
        failure = failure or 'Required outputs missing: ' + ', '.join(missing)
    receipt.update(status='failed' if failure else 'completed', exit_code=exit_code,
                   failure=failure, ended=time.time(), missing_artifacts=missing)
    serialized = json.dumps(receipt, ensure_ascii=False, allow_nan=False, indent=2)
    (root / 'execution.json').write_text(serialized, 'utf-8')
    with zipfile.ZipFile(root / 'results.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('execution.json', serialized)
        for name, path in selected:
            if digest(path) != next(item['sha256'] for item in receipt['artifacts'] if item['name'] == name):
                raise RuntimeError('Output changed while collecting results: ' + name)
            archive.write(path, 'artifacts/' + name)
    print('Return results.zip to the originating PhD project. Scientific review is still pending.')
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
