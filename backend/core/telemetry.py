"""Structured backend telemetry (v3.3 §17, v3.4 §21) — counts, ids and latencies only, never content.

    with span("memory.retrieve", session_id=sid, agent_id="reviewer") as s:
        ...
        s.update(candidate_count=120, selected_count=12, cache_hit=False)

Every span becomes one record {request_id, ts, operation, latency_ms, ok, error?, …attrs} kept in an in-memory ring
(GET /api/telemetry) and appended to <global data>/telemetry/ops.jsonl (rotated at 5 MB). Attribute values are restricted
to numbers, booleans and short identifiers; free text (queries, memory content, prompts, credentials) is refused by
_clean(), so a careless caller cannot leak research content or secrets into the log.
"""
from __future__ import annotations

import json
import re
import secrets
import statistics
import threading
import time
from collections import deque
from contextlib import contextmanager

RING: deque = deque(maxlen=1000)
_lock = threading.Lock()
MAX_FILE = 5 * 1024 * 1024
ID_OK = re.compile(r"^[\w.:@/+-]{0,80}$")
ALLOWED = {"request_id", "session_id", "project_id", "agent_id", "provider", "role", "operation", "latency_ms", "cache_hit",
           "candidate_count", "selected_count", "dropped_count", "context_tokens", "memory_tokens", "retrieval_count",
           "streaming", "context_version", "tool", "client", "status", "blocked_count", "nodes", "tokens_budget", "error"}


def new_request_id() -> str:
    return "req-" + secrets.token_hex(6)


def _clean(attrs: dict) -> dict:
    out = {}
    for k, v in attrs.items():
        if k not in ALLOWED or v is None:
            continue
        if isinstance(v, bool) or isinstance(v, (int, float)):
            out[k] = v
        elif isinstance(v, str):
            if k == "error":
                out[k] = redact(v)[:200]
            elif ID_OK.match(v):
                out[k] = v
    return out


SECRET_RES = [re.compile(p) for p in (
    r"sk-[A-Za-z0-9_-]{8,}", r"sk-ant-[A-Za-z0-9_-]{8,}", r"ghp_[A-Za-z0-9]{20,}", r"github_pat_[A-Za-z0-9_]{20,}",
    r"AKIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_-]{30,}", r"xox[abpr]-[A-Za-z0-9-]{10,}", r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{12,}",
    r"(?i)(api[_-]?key|secret|password|refresh_token|access_token)\s*[:=]\s*['\"]?[^\s'\"]{6,}",
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")]


def redact(text: str) -> str:
    """Mask credentials in text that leaves the backend (logs, MCP results, provider context)."""
    t = text or ""
    for r in SECRET_RES:
        t = r.sub("[REDACTED]", t)
    return t


def _file():
    from backend.core.config import GLOBAL_DIR
    d = GLOBAL_DIR / "telemetry"
    d.mkdir(parents=True, exist_ok=True)
    return d / "ops.jsonl"


def record(rec: dict) -> None:
    with _lock:
        RING.append(rec)
        try:
            f = _file()
            if f.exists() and f.stat().st_size > MAX_FILE:
                f.replace(f.with_suffix(".jsonl.1"))
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError:
            pass


class Span:
    def __init__(self, operation: str, attrs: dict):
        self.operation = operation
        self.attrs = attrs

    def update(self, **attrs):
        self.attrs.update(attrs)


@contextmanager
def span(operation: str, **attrs):
    s = Span(operation, {"request_id": attrs.pop("request_id", None) or new_request_id(), **attrs})
    t0 = time.perf_counter()
    err = None
    try:
        yield s
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        raise
    finally:
        rec = {"ts": round(time.time(), 3), "operation": operation, "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
               "ok": err is None, **_clean(s.attrs)}
        if err:
            rec["error"] = redact(err)[:200]
        try:
            from backend.core.config import data_dir
            rec.setdefault("project_id", data_dir().name[:80])
        except Exception:
            pass
        record(rec)


def summary() -> dict:
    """p50/p95 latency, error count and cache-hit rate per operation (in-memory window)."""
    by: dict = {}
    for r in list(RING):
        by.setdefault(r["operation"], []).append(r)
    out = {}
    for op, rs in sorted(by.items()):
        lat = sorted(r["latency_ms"] for r in rs)
        hits = [r["cache_hit"] for r in rs if "cache_hit" in r]
        out[op] = {"count": len(rs), "p50_ms": round(statistics.median(lat), 2),
                   "p95_ms": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 2),
                   "errors": sum(1 for r in rs if not r["ok"]),
                   "cache_hit_rate": round(sum(hits) / len(hits), 3) if hits else None}
    return out
