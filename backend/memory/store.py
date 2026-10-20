"""Small JSON document store shared by the v3.2 memory modules: one lock per file, atomic writes (tmp + os.replace)."""
from __future__ import annotations

import copy
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_locks: dict = {}
_locks_guard = threading.Lock()
GENERATION = {"n": 0}  # v3.3: bumped on every write of any memory store → in-process cache invalidation (cache.py)


def bump() -> int:
    with _locks_guard:
        GENERATION["n"] += 1
        return GENERATION["n"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lock_for(path: Path) -> threading.RLock:
    key = str(path)
    with _locks_guard:
        if key not in _locks:
            _locks[key] = threading.RLock()
        return _locks[key]


def replace_retry(src: Path, dst: Path, tries: int = 40) -> None:
    """os.replace that survives Windows sharing violations (a reader or an antivirus scanner holding the target open
    for a moment raises PermissionError instead of waiting). Found by the v3.3 concurrency test."""
    for i in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.005 * (i + 1))


def read_retry(p: Path, tries: int = 40) -> str:
    for i in range(tries):
        try:
            return p.read_text("utf-8")
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.005 * (i + 1))
    return ""


def quarantine(p: Path) -> Path | None:
    """Keep a copy of an unreadable store file (<name>.corrupt-<UTC time>) before the app falls back to defaults, so the
    next write cannot destroy the only copy of the researcher's data. Returns the copy's path."""
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        dst = p.with_name(f"{p.name}.corrupt-{stamp}")
        if not dst.exists():
            dst.write_bytes(p.read_bytes())
            print(f"[memory] {p.name} is not valid JSON — kept a copy as {dst.name}")
        return dst
    except OSError:
        return None


class JsonStore:
    """A JSON file holding one dict. `path_fn` is resolved on every call, so the store follows the active project."""

    def __init__(self, path_fn: Callable[[], Path], default: dict, versioned: bool = True):
        """versioned=False for stores that do not feed retrieval (working state, derived caches, page index): their
        writes must not invalidate the retrieval caches (cache.py)."""
        self.path_fn = path_fn
        self.default = default
        self.versioned = versioned

    def load(self) -> dict:
        """Reads take the file's lock too: in-process readers never see (or block) a replace in progress."""
        p = self.path_fn()
        with _lock_for(p):
            return self._load(p)

    def _load(self, p: Path) -> dict:
        d = copy.deepcopy(self.default)
        if p.exists():
            try:
                saved = json.loads(read_retry(p))
                if isinstance(saved, dict):
                    d.update(saved)
                else:
                    quarantine(p)
            except ValueError:
                quarantine(p)  # v3.3: never let the next write silently overwrite a damaged store
            except OSError:
                pass
        return d

    def _write(self, p: Path, d: dict) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
        replace_retry(tmp, p)
        if self.versioned:
            bump()

    def update(self, fn: Callable[[dict], object]):
        """Read-modify-write under the file's lock; returns whatever fn returns."""
        p = self.path_fn()
        with _lock_for(p):
            d = self._load(p)
            out = fn(d)
            self._write(p, d)
            return out
