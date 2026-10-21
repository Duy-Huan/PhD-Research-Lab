"""Integration contract (v3.2, Milestone 2).

Every external platform (VS Code, Docker, Jupyter, ClearML, Codex, …) is reached only through an adapter in this package,
and every adapter reports an honest IntegrationStatus:

    disabled      switched off in the configuration
    unconfigured  enabled but required settings (URL, credentials) are missing
    unavailable   CLI/SDK not installed or the server does not answer
    available     probed successfully just now
    error         probed, but the platform returned an error

Nothing in the app may claim an operation succeeded unless the adapter actually performed it.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field

STATES = ("disabled", "unconfigured", "unavailable", "available", "error")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class IntegrationError(Exception):
    """An adapter could not perform the requested operation (message is safe to show: no secrets)."""


class NotSupported(IntegrationError):
    """The backend does not implement this capability (shown explicitly instead of faking it)."""


@dataclass
class IntegrationStatus:
    name: str
    label: str
    state: str
    detail: str = ""
    version: str = ""
    capabilities: list = field(default_factory=list)
    setup: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.state not in STATES:
            raise ValueError(f"bad integration state {self.state}")

    @property
    def ok(self) -> bool:
        return self.state == "available"

    def to_dict(self) -> dict:
        return {**asdict(self), "ok": self.ok, "checked": time.time()}


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


def clear_cache():
    _cache.clear()
