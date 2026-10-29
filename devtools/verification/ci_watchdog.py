"""Outer deadline for a CI verification step: heartbeats, diagnostics and an owned process-tree stop.

Usage: python -m devtools.verification.ci_watchdog --deadline-s 2790 --out <dir> -- <command...>

The runner already bounds its own stages, but Windows 3.12 push runs were killed at the job limit without logs or
artifacts, so the step never ended on its own. This separate parent prints a heartbeat (elapsed, current test,
completed cases, memory, owned processes) to the console every interval. At the deadline it writes
watchdog-timeout.json, stops the whole owned tree and exits TIMEOUT_EXIT so the always() upload still runs.
The wrapped command's exit code is returned unchanged; a timeout is never reported as success.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import psutil

TIMEOUT_EXIT = 124


def _progress(path: Path | None) -> dict:
    try:
        return json.loads(path.read_text('utf-8')) if path and path.is_file() else {}
    except (OSError, ValueError):
        return {}


def _tree(pid: int) -> list[psutil.Process]:
    try:
        parent = psutil.Process(pid)
        return [parent] + parent.children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def _describe(proc: psutil.Process) -> dict:
    try:
        with proc.oneshot():
            return {'pid': proc.pid, 'name': proc.name(), 'status': proc.status(),
                    'rss_mb': round(proc.memory_info().rss / 2**20, 1), 'cpu_s': round(sum(proc.cpu_times()[:2]), 1)}
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {'pid': proc.pid, 'name': '?', 'status': 'gone'}


def guard(command: list[str], *, deadline_s: float, interval_s: float = 60, out: Path, progress: Path | None = None,
          emit: Callable[[str], None] = print) -> int:
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    process = subprocess.Popen(command)  # inherits the console: the wrapped output stays in the CI log
    next_beat = started + interval_s
    while True:
        try:
            return process.wait(timeout=max(0.05, min(next_beat, started + deadline_s) - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        if now >= started + deadline_s:
            break
        if now >= next_beat:
            p, tree = _progress(progress), _tree(process.pid)
            mem = psutil.virtual_memory()
            emit(f"watchdog heartbeat elapsed={now - started:.0f}s completed_cases={p.get('completed_cases', '?')} "
                 f"test={p.get('test', '?')} processes={len(tree)} rss_mb={sum(_describe(x).get('rss_mb', 0) for x in tree):.0f} "
                 f"free_mb={mem.available / 2**20:.0f}")
            next_beat = now + interval_s
    # Deadline: record what was running, then stop the owned tree (children first, never by executable name).
    tree = _tree(process.pid)
    records = [_describe(x) for x in tree]
    for proc in reversed(tree):
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    gone, alive = psutil.wait_procs(tree, timeout=10)
    alive_pids = {x.pid for x in alive}
    for record in records:
        record['stopped'] = record['pid'] not in alive_pids
    report = {'status': 'TIMEOUT', 'deadline_s': deadline_s, 'command': command, 'progress': _progress(progress),
              'processes': records, 'free_mb': round(psutil.virtual_memory().available / 2**20),
              'utc': datetime.now(timezone.utc).isoformat()}
    (out / 'watchdog-timeout.json').write_text(json.dumps(report, indent=2), 'utf-8')
    emit(f"watchdog TIMEOUT after {deadline_s:g}s; stopped {len(records) - len(alive_pids)}/{len(records)} owned "
         f"processes; last test {report['progress'].get('test', '?')}; see {out / 'watchdog-timeout.json'}")
    return TIMEOUT_EXIT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--deadline-s', type=float, required=True)
    parser.add_argument('--interval-s', type=float, default=60)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--progress', type=Path, help='current-test JSON written by the runner')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.deadline_s <= 0 or args.interval_s <= 0:
        parser.error('a command and positive --deadline-s/--interval-s are required')
    emit = lambda line: print(line, flush=True)  # noqa: E731 - console is the evidence channel
    return guard(command, deadline_s=args.deadline_s, interval_s=args.interval_s, out=args.out,
                 progress=args.progress or args.out / 'backend-current-test.json', emit=emit)


if __name__ == '__main__':
    sys.exit(main())
