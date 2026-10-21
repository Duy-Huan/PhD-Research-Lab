"""Derived-data caches of the retrieval path (v3.3) — introduced after profiling (docs/benchmarks/backend-v3.3-benchmark.md):
at ~4k nodes v3.2 spent ~90 % of a retrieval re-building 512-d hashing vectors and computing dense cosines in Python, and
re-reading every store on each call.

Correctness rule: a cache key contains EVERYTHING that can change the result.
    fingerprint()  = active project folder + in-process write generation (store.bump on every memory write)
                     + (mtime_ns, size) of every file that feeds lod.collect() — catches writes by other processes,
                     the library/notes/overlay modules that do not go through JsonStore, and hand edits.
Every cached value is keyed by (fingerprint, …inputs…), so a write anywhere invalidates it on the next read; nothing is
ever served across projects. Caches hold derived data only (safe to drop at any time).
"""
from __future__ import annotations

import threading
from collections import OrderedDict

from backend.memory.store import GENERATION

_lock = threading.Lock()


def _sources() -> list:
    from backend.core.config import data_dir
    from backend.memory import mem_dir
    d, m = data_dir(), mem_dir()
    files = [m / "project_state.json", m / "research.json", m / "evidence.json", m / "knowledge.json", d / "library.json"]
    try:
        from backend.memory.notes import _notes_path
        files.append(_notes_path())
    except Exception:
        pass
    try:
        from backend.memory.graph import _overlay_path
        files.append(_overlay_path())
    except Exception:
        pass
    return files


def fingerprint() -> tuple:
    from backend.core.config import data_dir
    sig = []
    for f in _sources():
        try:
            s = f.stat()
            sig.append((f.name, s.st_mtime_ns, s.st_size))
        except OSError:
            sig.append((f.name, 0, 0))
    return (str(data_dir()), GENERATION["n"], tuple(sig))


def version() -> str:
    """Short, stable id of the current memory state (exposed as context_version)."""
    import hashlib
    return hashlib.sha1(repr(fingerprint()).encode()).hexdigest()[:12]


class LRU:
    def __init__(self, size: int = 64):
        self.size = size
        self.data: OrderedDict = OrderedDict()
        self.hits = self.misses = 0

    def get(self, key):
        with _lock:
            if key in self.data:
                self.data.move_to_end(key)
                self.hits += 1
                return self.data[key]
            self.misses += 1
            return None

    def put(self, key, value):
        with _lock:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)
        return value

    def clear(self):
        with _lock:
            self.data.clear()


NODES = LRU(4)        # fingerprint → (nodes, per-index structures)
RESULTS = LRU(128)    # (fingerprint, retrieval-context hash, cfg) → retrieval result
VECTORS = LRU(8000)   # (engine, sha1(text)) → unit vector (content-addressed: never stale; ~30 MB at full size)


def clear_all() -> None:
    """Drop every in-process cache (a project switch: nothing of the previous project may be served)."""
    for c in (NODES, RESULTS, VECTORS):
        c.clear()


def stats() -> dict:
    out = {}
    for name, c in (("nodes", NODES), ("results", RESULTS), ("vectors", VECTORS)):
        total = c.hits + c.misses
        out[name] = {"hits": c.hits, "misses": c.misses, "hit_rate": round(c.hits / total, 3) if total else None,
                     "size": len(c.data), "capacity": c.size}
    return out
