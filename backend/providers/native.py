"""Launch installed interactive CLIs. Public websites are not native apps."""
from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path


def launch_terminal(binary: str | None, args: list[str] | None = None) -> dict:
    resolved = shutil.which(binary or '') if binary else None
    if not resolved or not Path(resolved).is_file():
        return {'launched': False, 'state': 'UNAVAILABLE', 'detail': 'Native CLI executable is not installed or not on PATH.'}
    parts = [resolved, *(args or [])]
    if sys.platform.startswith('win'):
        command = '& ' + ' '.join("'" + part.replace("'", "''") + "'" for part in parts)
        encoded = base64.b64encode(command.encode('utf-16le')).decode('ascii')
        argv = ['powershell.exe', '-NoLogo', '-NoExit', '-EncodedCommand', encoded]
        options = {'creationflags': getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)}
    else:
        terminal = shutil.which('x-terminal-emulator')
        if not terminal:
            return {'launched': False, 'state': 'UNAVAILABLE', 'command': parts,
                    'detail': 'No supported native terminal launcher is available on this platform.'}
        argv, options = [terminal, '-e', *parts], {}
    try:
        process = subprocess.Popen(argv, **options)
    except OSError as exc:
        return {'launched': False, 'state': 'ERROR', 'detail': f'Native terminal could not start: {type(exc).__name__}'}
    return {'launched': True, 'pid': process.pid, 'executable': resolved, 'command': parts,
            'state': 'LAUNCHED', 'detail': 'Native terminal process started; authentication and inference require separate verification.'}


def launch_provider(provider: str) -> dict:
    from backend.providers.cli import CONNECTORS
    if provider in ('app', 'phdlab'):
        return launch_terminal(sys.executable, ['-m', 'backend.cli'])
    if provider in CONNECTORS:
        return launch_terminal(CONNECTORS[provider].binary())
    binaries = {'feynman': 'feynman', 'opencode': 'opencode', 'paperorchestra': 'paper-orchestra', 'openscience': 'openscience'}
    return launch_terminal(binaries.get(provider))
