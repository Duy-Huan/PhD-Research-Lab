"""Helpers for external tools (VS Code and coding CLIs): run a CLI without a console window,
find a binary, resolve an npm shim to `node <pkg>.js`, a tiny TTL cache. An adapter that cannot do what was asked raises
IntegrationError (message safe to show: no secrets) — nothing may claim an operation succeeded unless it really ran.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class IntegrationError(Exception):
    """An adapter could not perform the requested operation (message is safe to show: no secrets)."""


def run_cli(args: list, timeout: float = 15, cwd: str | None = None, input_text: str | None = None) -> tuple[int, str]:
    """Run a CLI without a console window; (exit code, stdout+stderr). 127 = not found, 124 = timeout."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           cwd=cwd, input=input_text, stdin=None if input_text is not None else subprocess.DEVNULL,
                           creationflags=NO_WINDOW)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except OSError as e:
        return 126, str(e)


def node_argv(binary: str | None, package_js: str) -> list:
    """Command prefix for an npm-installed CLI. On Windows npm installs a .cmd shim and cmd.exe re-parses every argument
    passed through a batch file (quotes, &, |, newlines), so the shim's own target is run instead: node <pkg>.js."""
    if not binary:
        return []
    p = Path(binary)
    if p.suffix.lower() in (".cmd", ".bat", ".ps1", "") and sys.platform.startswith("win"):
        js = p.parent / "node_modules" / Path(package_js)
        node = p.parent / "node.exe" if (p.parent / "node.exe").is_file() else which("node")
        if js.is_file() and node:
            return [str(node), str(js)]
    return [binary]


def which(*names: str) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


_cache: dict = {}


def cached(key: str, ttl: float, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val
