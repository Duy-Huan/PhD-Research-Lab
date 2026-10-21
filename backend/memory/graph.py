"""Context overlay the researcher controls (memory/context_graph.json): per record (node id) —
    pinned       injected into EVERY agent as must-follow context
    purged       excluded from what the agents see (the source data itself is not deleted)
    sensitivity  privacy level override (providers/privacy.py)
"""
from __future__ import annotations

import json
import threading

from backend import memory as M

_lock = threading.Lock()


def _overlay_path():
    return M.mem_dir() / "context_graph.json"


def load_overlay() -> dict:
    d = {"nodes": {}, "custom": [], "edges": []}
    f = _overlay_path()
    if f.exists():
        try:
            saved = json.loads(f.read_text("utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("overlay is not an object")
            d.update(saved)
        except ValueError:
            # The overlay holds purges (records hidden from every AI) and sensitivity overrides: keep the damaged file
            # so the next save cannot silently erase the researcher's privacy choices.
            from backend.memory.store import quarantine
            quarantine(f)
        except OSError:
            pass
    return d


def save_overlay(ov: dict):
    from backend.memory.store import replace_retry
    with _lock:
        f = _overlay_path()
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(ov, ensure_ascii=False, indent=1), "utf-8")
        replace_retry(tmp, f)


def purged_ids(ov: dict | None = None) -> set:
    ov = ov or load_overlay()
    return {k for k, v in ov["nodes"].items() if v.get("purged")}
