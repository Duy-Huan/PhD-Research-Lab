"""Small JSON document store shared by the v3.2 memory modules: one lock per file, atomic writes (tmp + os.replace)."""
from __future__ import annotations

import copy
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_locks: dict = {}
_locks_guard = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lock_for(path: Path) -> threading.RLock:
    key = str(path)
    with _locks_guard:
        if key not in _locks:
            _locks[key] = threading.RLock()
        return _locks[key]


class JsonStore:
    """A JSON file holding one dict. `path_fn` is resolved on every call, so the store follows the active project."""

    def __init__(self, path_fn: Callable[[], Path], default: dict):
        self.path_fn = path_fn
        self.default = default

    def load(self) -> dict:
        d = copy.deepcopy(self.default)
        p = self.path_fn()
        if p.exists():
            try:
                saved = json.loads(p.read_text("utf-8"))
                if isinstance(saved, dict):
                    d.update(saved)
            except (OSError, ValueError):
                pass
        return d

    def _write(self, p: Path, d: dict) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, p)

    def update(self, fn: Callable[[dict], object]):
        """Read-modify-write under the file's lock; returns whatever fn returns."""
        p = self.path_fn()
        with _lock_for(p):
            d = self.load()
            out = fn(d)
            self._write(p, d)
            return out
