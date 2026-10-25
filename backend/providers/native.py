"""Launch installed interactive CLIs. Public websites are not native apps."""
from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path


def _open_console(binary: str | None, args: list[str], cwd: str) -> dict:
    from backend.providers.cli_space import minimal_env
    resolved = shutil.which(binary or '') if binary else None
    if not resolved or not Path(resolved).is_file():
        return {'launched': False, 'state': 'UNAVAILABLE', 'detail': 'Native CLI executable is not installed or not on PATH.'}
    parts = [resolved, *(args or [])]
    if sys.platform.startswith('win'):
        command = '& ' + ' '.join("'" + part.replace("'", "''") + "'" for part in parts)
        encoded = base64.b64encode(command.encode('utf-16le')).decode('ascii')
        argv = ['powershell.exe', '-NoLogo', '-NoProfile', '-NoExit', '-EncodedCommand', encoded]
        options = {'creationflags': getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)}
    else:
        terminal = shutil.which('x-terminal-emulator')
        if not terminal:
            return {'launched': False, 'state': 'UNAVAILABLE', 'command': parts,
                    'detail': 'No supported native terminal launcher is available on this platform.'}
        argv, options = [terminal, '-e', *parts], {}
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=minimal_env(), **options)
    except OSError as exc:
        return {'launched': False, 'state': 'ERROR', 'detail': f'Native terminal could not start: {type(exc).__name__}'}
    return {'launched': True, 'pid': process.pid, 'executable': resolved, 'command': parts,
            'state': 'LAUNCHED', 'detail': 'Native terminal process started; authentication and inference require separate verification.'}


def launch_terminal(binary: str | None, args: list[str] | None = None) -> dict:
    """Compatibility boundary: callers cannot bypass project containment with a raw executable."""
    return {'launched': False, 'state': 'BLOCKED', 'detail': 'Unrestricted host CLI launch is disabled; use a project-scoped provider runtime.'}


def launch_provider(provider: str, login: bool = False) -> dict:
    from backend.core.config import ROOT
    from backend.providers.isolated_cli import prepare
    prepared = prepare(provider, login)
    if prepared['state'] != 'PREPARED':
        return prepared
    result = _open_console(sys.executable, [str(ROOT / 'tools/run_cli_container.py'), prepared['plan']], prepared['cwd'])
    return {**prepared, **result, 'cwd': prepared['cwd'], 'context_sha256': prepared['context_sha256'],
            'isolation': prepared['isolation']}
