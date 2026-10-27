"""Unified tool execution runtime: one interface for every tool kind.

    grant  = Grant(principal="session:abc", tools=["research_*"], permissions=["read"])
    job    = RUNTIME.submit("research_search_memory", {"query": "..."}, grant)   # async, returns a job record
    final  = RUNTIME.wait(job["id"])                                              # or RUNTIME.run(...) blocking

Authority comes ONLY from the Grant (tool patterns, permissions, mutation flag, expiry and budgets); a tool spec, a
model message or tool output can never widen it. Every call -- including denied, invalid and failed ones -- appends a
hash-chained provenance record (<project data>/tool_runs/provenance.jsonl) binding principal, grant, exact tool
version/spec digest, argument and result digests, attempts and timings, so actions are traceable and replayable.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import platform
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from backend.tools import schema as S
from backend.tools.registry import REGISTRY, Registry
from backend.tools.spec import PERMISSIONS, ToolError, ToolSpec

TERMINAL = ("succeeded", "failed", "cancelled", "timed_out", "denied")
MAX_OBSERVATIONS = 500


class Grant(BaseModel):
    """What a principal may do. Issued by application code from stored settings/approvals, never by a model."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: "tg-" + secrets.token_hex(8))
    principal: str = Field(min_length=1, max_length=200)
    tools: list[str] = Field(default_factory=lambda: ["*"], max_length=200)
    permissions: list[str] = Field(default_factory=lambda: ["read"])
    allow_mutation: bool = False
    # None = no budget (v6.6.2 agent profiles: the owner bounds agents by permissions, not by counts or time).
    # Each tool's own manifest budget (hang timeout, output cap) still applies to every call.
    max_calls: int | None = Field(default=50, ge=0, le=10_000)
    max_wall_s: float | None = Field(default=1800, gt=0, le=7 * 86400)
    max_output_bytes: int | None = Field(default=8_000_000, ge=1, le=512_000_000)
    expires_at: float = Field(default_factory=lambda: time.time() + 86400)

    def model_post_init(self, _):
        bad = [p for p in self.permissions if p not in PERMISSIONS]
        if bad:
            raise ValueError(f"Unknown permissions {bad}")


@dataclass
class Usage:
    calls: int = 0
    wall_s: float = 0.0
    output_bytes: int = 0


@dataclass
class ExecContext:
    job_id: str
    principal: str
    workdir: Path
    deadline: float
    max_output_bytes: int
    cancelled: threading.Event
    observe: callable = field(default=lambda kind, text: None)


def runs_root() -> Path:
    from backend.core.config import data_dir
    return data_dir() / "tool_runs"


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


# ------------------------------------------------------------------ provenance (hash chain)
_prov_lock = threading.Lock()


def _prov_file() -> Path:
    return runs_root() / "provenance.jsonl"


def _last_hash(path: Path) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        return "0" * 64
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - 65536))
        line = f.read().splitlines()[-1]
    return json.loads(line)["hash"]


def record_provenance(entry: dict) -> dict:
    with _prov_lock:
        path = _prov_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {**entry, "prev": _last_hash(path)}
        entry["hash"] = _digest({k: v for k, v in entry.items() if k != "hash"})
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return entry


def provenance(job_id: str = "", limit: int = 200) -> list:
    path = _prov_file()
    if not path.is_file():
        return []
    rows = [json.loads(l) for l in path.read_text("utf-8").splitlines() if l.strip()]
    if job_id:
        rows = [r for r in rows if r.get("job_id") == job_id]
    return rows[-limit:]


def verify_provenance() -> dict:
    """Recompute the hash chain; any edited, removed or reordered record breaks it."""
    path = _prov_file()
    if not path.is_file():
        return {"valid": True, "records": 0}
    prev, count = "0" * 64, 0
    for line in (l for l in path.read_text("utf-8").splitlines() if l.strip()):
        row = json.loads(line)
        if row.get("prev") != prev or row.get("hash") != _digest({k: v for k, v in row.items() if k != "hash"}):
            return {"valid": False, "records": count, "broken_at": count, "job_id": row.get("job_id")}
        prev, count = row["hash"], count + 1
    return {"valid": True, "records": count}


# ------------------------------------------------------------------ runtime
class Runtime:
    def __init__(self, registry: Registry = REGISTRY, workers: int = 4):
        self.registry = registry
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="phdlab-tool")
        self.jobs: dict[str, dict] = {}
        self.cancels: dict[str, threading.Event] = {}
        self.usage: dict[str, Usage] = {}
        self.lock = threading.Condition()

    # -------------------------------------------------------------- authorization
    def authorize(self, spec: ToolSpec, grant: Grant) -> None:
        if time.time() > grant.expires_at:
            raise ToolError("permission_denied", "The tool grant has expired")
        if not any(fnmatch.fnmatchcase(spec.id, p) for p in grant.tools):
            raise ToolError("permission_denied", f"{spec.id} is not in this grant's tool allowlist",
                            hint="Choose a tool allowed for this task or ask the researcher to extend the grant")
        missing = sorted(set(spec.permissions) - set(grant.permissions))
        if missing:
            raise ToolError("permission_denied", f"{spec.id} needs permissions {missing} not granted",
                            details={"missing": missing})
        if spec.mutates and not grant.allow_mutation:
            raise ToolError("permission_denied", f"{spec.id} changes state; this grant is read-only")
        use = self.usage.setdefault(grant.id, Usage())
        if grant.max_calls is not None and use.calls >= grant.max_calls:
            raise ToolError("budget_exceeded", f"Call budget of {grant.max_calls} tool calls is exhausted")
        if grant.max_wall_s is not None and use.wall_s >= grant.max_wall_s:
            raise ToolError("budget_exceeded", f"Execution time budget of {grant.max_wall_s:g}s is exhausted")
        if grant.max_output_bytes is not None and use.output_bytes >= grant.max_output_bytes:
            raise ToolError("budget_exceeded", "Tool output byte budget is exhausted")

    # -------------------------------------------------------------- job records
    def _observe(self, job_id: str, kind: str, text: str) -> None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return
            obs = job["observations"]
            seq = (obs[-1]["seq"] + 1) if obs else 1
            obs.append({"seq": seq, "ts": round(time.time(), 3), "kind": kind[:30], "text": str(text)[:4000]})
            del obs[:-MAX_OBSERVATIONS]
            self.lock.notify_all()

    def _set(self, job_id: str, **fields) -> dict:
        with self.lock:
            self.jobs[job_id].update(fields)
            self.lock.notify_all()
            return dict(self.jobs[job_id])

    def get(self, job_id: str) -> dict:
        with self.lock:
            if job_id in self.jobs:
                return json.loads(json.dumps(self.jobs[job_id], default=str))
        path = runs_root() / job_id / "job.json"
        if job_id.startswith("tj-") and path.is_file():
            return json.loads(path.read_text("utf-8"))
        raise ToolError("not_found", f"No tool job {job_id}")

    def events(self, job_id: str, after: int = 0, timeout: float = 0) -> dict:
        """Observations newer than `after`; with timeout>0 block until one arrives or the job ends (streaming)."""
        end = time.monotonic() + timeout
        with self.lock:
            while True:
                job = self.jobs.get(job_id) or self.get(job_id)
                new = [o for o in job["observations"] if o["seq"] > after]
                if new or job["status"] in TERMINAL or time.monotonic() >= end:
                    return {"status": job["status"], "observations": new}
                self.lock.wait(min(1.0, max(0.01, end - time.monotonic())))

    def cancel(self, job_id: str) -> dict:
        ev = self.cancels.get(job_id)
        if ev is None:
            raise ToolError("not_found", f"No running tool job {job_id}")
        ev.set()
        self._observe(job_id, "status", "cancellation requested")
        return self.get(job_id)

    def wait(self, job_id: str, timeout: float | None = None) -> dict:
        end = None if timeout is None else time.monotonic() + timeout
        with self.lock:
            while job_id in self.jobs and self.jobs[job_id]["status"] not in TERMINAL:
                if end is not None and time.monotonic() >= end:
                    break
                self.lock.wait(0.5 if end is None else max(0.01, min(0.5, end - time.monotonic())))
        return self.get(job_id)

    # -------------------------------------------------------------- execution
    def submit(self, tool_id: str, args: dict, grant: Grant, *, version: str = "", parent: str = "", actor: str = "") -> dict:
        """Validate, authorize and start a tool call asynchronously. Rejections still produce a terminal job and a
        provenance record, so a denied attempt is as traceable as a successful one."""
        job_id = "tj-" + secrets.token_hex(10)
        job = {"id": job_id, "tool": tool_id, "version": version, "principal": grant.principal, "grant_id": grant.id,
               "parent": parent, "actor": actor[:120], "status": "queued", "args": args, "observations": [], "attempts": [],
               "result": None, "error": None, "created": time.time(), "started": None, "finished": None}
        with self.lock:
            self.jobs[job_id] = job
            self.cancels[job_id] = threading.Event()
        try:
            spec = self.registry.resolve(tool_id, version)
            self._set(job_id, version=spec.version, kind=spec.kind, spec_digest=spec.digest())
            self.authorize(spec, grant)
            if not isinstance(args, dict):
                raise ToolError("invalid_input", "Tool arguments must be a JSON object")
            errors = S.validate(args, spec.input_schema)
            if errors:
                raise ToolError("invalid_input", f"Arguments do not match {spec.ref} input schema",
                                hint="Call describe for the schema and correct the arguments", details={"errors": errors[:20]})
            state = self.registry.probe(spec)
            if not state["available"]:
                raise ToolError("unavailable", f"{spec.ref} is unavailable: {state['reason']}",
                                hint="Search the registry for an alternative tool")
        except ToolError as e:
            status = "denied" if e.code in ("permission_denied", "budget_exceeded") else "failed"
            return self._finish(job_id, grant, None, status, None, e)
        with self.lock:
            self.usage[grant.id].calls += 1
        self.pool.submit(self._execute, job_id, spec, args, grant)
        return self.get(job_id)

    def run(self, tool_id: str, args: dict, grant: Grant, *, version: str = "", parent: str = "", actor: str = "") -> dict:
        job = self.submit(tool_id, args, grant, version=version, parent=parent, actor=actor)
        return job if job["status"] in TERMINAL else self.wait(job["id"])

    def _execute(self, job_id: str, spec: ToolSpec, args: dict, grant: Grant) -> None:
        try:
            self._attempts(job_id, spec, args, grant)
        except Exception as e:  # infrastructure failure (disk, provenance) still ends the job visibly
            if self.jobs[job_id]["status"] not in TERMINAL:
                self._set(job_id, status="failed", finished=time.time(),
                          error=ToolError("execution_failed", f"runtime failure: {type(e).__name__}").as_dict())
                with self.lock:
                    self.cancels.pop(job_id, None)

    def _attempts(self, job_id: str, spec: ToolSpec, args: dict, grant: Grant) -> None:
        from backend.tools.adapters import ADAPTERS
        workdir = runs_root() / job_id / "work"
        workdir.mkdir(parents=True, exist_ok=True)
        use = self.usage[grant.id]
        started = time.monotonic()
        self._set(job_id, status="running", started=time.time())
        self._observe(job_id, "status", f"running {spec.ref}")
        cancelled = self.cancels[job_id]
        result, error, status = None, None, "failed"
        for attempt in range(spec.max_retries + 1):
            budget = spec.budget.timeout_s if grant.max_wall_s is None else min(
                spec.budget.timeout_s, max(0.0, grant.max_wall_s - use.wall_s - (time.monotonic() - started)))
            ctx = ExecContext(job_id=job_id, principal=grant.principal, workdir=workdir,
                              deadline=time.monotonic() + budget, cancelled=cancelled,
                              max_output_bytes=spec.budget.max_output_bytes if grant.max_output_bytes is None else
                              min(spec.budget.max_output_bytes, grant.max_output_bytes - use.output_bytes),
                              observe=lambda kind, text: self._observe(job_id, kind, text))
            t0 = time.time()
            try:
                if budget <= 0:
                    raise ToolError("budget_exceeded", "No execution time remains in this grant")
                result = self._call(ADAPTERS[spec.kind], spec, args, ctx)
                if spec.output_schema:
                    errors = S.validate(result, spec.output_schema)
                    if errors:
                        raise ToolError("invalid_output", f"{spec.ref} returned output violating its schema",
                                        details={"errors": errors[:20]})
                error, status = None, "succeeded"
            except ToolError as e:
                error, result = e, None
                status = {"cancelled": "cancelled", "timeout": "timed_out"}.get(e.code, "failed")
            except Exception as e:  # adapter bugs become structured failures, never silent success
                error, result, status = ToolError("execution_failed", f"{type(e).__name__}: {e}"[:500]), None, "failed"
            with self.lock:
                self.jobs[job_id]["attempts"].append({"attempt": attempt + 1, "started": t0, "finished": time.time(),
                                                      "status": status, "error": error.as_dict() if error else None})
            if status == "succeeded" or not (error and error.retryable and spec.idempotent) or cancelled.is_set() \
                    or attempt >= spec.max_retries:
                break
            self._observe(job_id, "retry", f"attempt {attempt + 1} failed ({error.code}); retrying")
            time.sleep(min(4.0, 0.5 * 2 ** attempt))
        with self.lock:
            use.wall_s += time.monotonic() - started
            use.output_bytes += len(json.dumps(result, default=str)) if result is not None else 0
        self._finish(job_id, grant, spec, status, result, error)

    @staticmethod
    def _call(adapter, spec: ToolSpec, args: dict, ctx: ExecContext) -> dict:
        """Process adapters enforce their own deadlines; in-process native handlers run in a helper thread so a hung
        handler is abandoned (and reported as timeout/cancel) instead of blocking the agent."""
        if spec.kind != "native":
            return adapter.execute(spec, args, ctx)
        box: dict = {}

        def target():
            try:
                box["result"] = adapter.execute(spec, args, ctx)
            except BaseException as e:  # re-raised in the caller thread
                box["error"] = e
        t = threading.Thread(target=target, daemon=True, name=f"native-{ctx.job_id}")
        t.start()
        while t.is_alive():
            if ctx.cancelled.is_set():
                raise ToolError("cancelled", "Tool execution was cancelled (native handler abandoned)")
            if time.monotonic() >= ctx.deadline:
                raise ToolError("timeout", "Tool exceeded its time budget", retryable=True)
            t.join(0.02)
        if "error" in box:
            raise box["error"]
        return box["result"]

    def _finish(self, job_id: str, grant: Grant, spec: ToolSpec | None, status: str, result, error) -> dict:
        """Persist provenance and the job record BEFORE publishing the terminal status, so a waiter that sees the
        job finished can always read its provenance."""
        from backend.core.config import APP_VERSION
        job = self._set(job_id, result=result, error=error.as_dict() if error else None, finished=time.time())
        entry = record_provenance({
            "job_id": job_id, "ts": time.time(), "principal": grant.principal, "grant_id": grant.id,
            "grant_digest": _digest(grant.model_dump()), "tool": job["tool"], "version": job.get("version", ""),
            "kind": spec.kind if spec else job.get("kind", ""), "spec_digest": spec.digest() if spec else "",
            "parent": job.get("parent", ""), "actor": job.get("actor", ""), "args_sha256": _digest(job["args"]),
            "args": json.dumps(job["args"], default=str, ensure_ascii=False)[:4000], "status": status,
            "error": error.as_dict() if error else None, "result_sha256": _digest(result) if result is not None else "",
            "attempts": len(job["attempts"]), "started": job.get("started"), "finished": job["finished"],
            "app_version": APP_VERSION, "python": platform.python_version()})
        self._observe(job_id, "status", status if not error else f"{status}: {error.code}")
        job = {**self.get(job_id), "status": status, "provenance_hash": entry["hash"]}
        folder = runs_root() / job_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "job.json").write_text(json.dumps(job, default=str, ensure_ascii=False, indent=1), "utf-8")
        with self.lock:
            self.cancels.pop(job_id, None)
        self._set(job_id, status=status, provenance_hash=entry["hash"])
        return self.get(job_id)

    def replay(self, job_id: str, grant: Grant) -> dict:
        """Re-run a recorded call with the same tool version and arguments; compare result digests."""
        original = self.get(job_id)
        if original["status"] != "succeeded":
            raise ToolError("invalid_input", "Only a succeeded job can be replayed for reproducibility")
        again = self.run(original["tool"], original["args"], grant, version=original["version"], parent=job_id)
        same = again["status"] == "succeeded" and _digest(again["result"]) == _digest(original["result"])
        return {"original": job_id, "replay": again["id"], "status": again["status"], "result_identical": same}


RUNTIME = Runtime()
