"""Launch installed interactive CLIs. Public websites are not native apps."""
from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path


def _open_console(binary: str | None, args: list[str], cwd: str, extra_env: dict | None = None) -> dict:
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
        process = subprocess.Popen(argv, cwd=cwd, env={**minimal_env(), **(extra_env or {})}, **options)
    except OSError as exc:
        return {'launched': False, 'state': 'ERROR', 'detail': f'Native terminal could not start: {type(exc).__name__}'}
    return {'launched': True, 'pid': process.pid, 'executable': resolved, 'command': parts,
            'state': 'LAUNCHED', 'detail': 'Native terminal process started; authentication and inference require separate verification.'}


def launch_terminal(binary: str | None, args: list[str] | None = None) -> dict:
    """Compatibility boundary: callers cannot bypass project containment with a raw executable."""
    return {'launched': False, 'state': 'BLOCKED', 'detail': 'Unrestricted host CLI launch is disabled; use a project-scoped provider runtime.'}


def console_command(python: str, args: list[str], keep_open: bool = True) -> str:
    """One cmd.exe command line that runs `python args` in UTF-8. cmd strips the outer quotes of /k and /c, so the
    executable keeps its own quotes; args are fixed by the caller (never user text)."""
    if Path(python).name.lower() == 'pythonw.exe' and (Path(python).parent / 'python.exe').is_file():
        python = str(Path(python).parent / 'python.exe')  # a windowless interpreter would leave the console empty
    inner = f'chcp 65001 >nul & "{python}" ' + ' '.join(args)
    return f'cmd.exe /d /{"k" if keep_open else "c"} "{inner}"'


def open_chat_console(session_id: str, port: int) -> dict:
    """Continue one conversation in the phdlab terminal chat, in a new console (cmd on Windows). Only PhD Lab's own
    client starts, on the loopback port this server listens on; it talks HTTP to the same backend, so the browser and
    the console share the conversation. Credentials are not passed on (minimal_env)."""
    from backend.agent import sessions
    from backend.core.config import ROOT
    from backend.providers.cli_space import minimal_env
    sessions.get(session_id)  # validates the id format and that the conversation exists
    port = int(port)
    if not 0 < port < 65536:
        raise ValueError('Invalid server port')
    windows = sys.platform.startswith('win')
    hint = f'chat.bat --session {session_id}' if windows else f'./phdlab chat --session {session_id}'
    env = {**minimal_env(), 'PHDLAB_URL': f'http://127.0.0.1:{port}', 'PYTHONIOENCODING': 'utf-8', 'PYTHONPATH': str(ROOT)}
    env.pop('NO_COLOR', None)
    args = ['-m', 'backend.cli', 'chat', '--session', session_id]
    if windows:
        argv, options = console_command(sys.executable, args), {'creationflags': getattr(subprocess, 'CREATE_NEW_CONSOLE', 0x10)}
    else:
        terminal = shutil.which('x-terminal-emulator')
        if not terminal:
            return {'launched': False, 'command': hint, 'detail': 'No terminal launcher found; run the command yourself.'}
        argv, options = [terminal, '-e', sys.executable, *args], {}
    try:
        process = subprocess.Popen(argv, cwd=str(ROOT), env=env, **options)
    except OSError as exc:
        return {'launched': False, 'command': hint, 'detail': f'Console could not start: {type(exc).__name__}'}
    return {'launched': True, 'pid': process.pid, 'command': hint, 'detail': 'Console opened on this conversation.'}


def launch_provider(provider: str, login: bool = False) -> dict:
    from backend.core.config import ROOT
    from backend.providers.isolated_cli import claude_long_lived_token, prepare
    prepared = prepare(provider, login)
    if prepared['state'] != 'PREPARED':
        return prepared
    token = claude_long_lived_token() if provider == 'claude_code' else ''
    result = _open_console(sys.executable, [str(ROOT / 'tools/run_cli_container.py'), prepared['plan']], prepared['cwd'],
                           {'CLAUDE_CODE_OAUTH_TOKEN': token} if token else None)
    return {**prepared, **result, 'cwd': prepared['cwd'], 'context_sha256': prepared['context_sha256'],
            'isolation': prepared['isolation']}
