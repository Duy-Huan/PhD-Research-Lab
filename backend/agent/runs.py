"""Research runs: durable background work started from the chat ("chạy ngầm"), with the researcher's approval.

    <project>/workspace/research_runs/<RR-id>.json          the run (state, steps, approvals, outputs, history)
    <project>/workspace/research_runs/<RR-id>.events.jsonl  progress events (one unified timeline for UI, CLI, tests)
    <project>/workspace/research_runs/<RR-id>/              files the steps produced (reports, plans, ledgers)

State of a run (90-day simulation spec §2):

    CREATED → PLANNED → APPROVAL_PENDING (when needed) → RUNNING → VERIFYING → COMPLETED
    exceptions: BLOCKED (waiting for a resource slot) · FAILED · RECOVERING · NEEDS_USER_ACTION · CANCELLED

Rules the engine enforces (not the model):
  * permissions — a run of risk ≥ runs.auto_approve_risk+1 (default: everything that writes code or computes) waits in
    APPROVAL_PENDING until the researcher accepts it; executors that write into the code project refuse to run without
    that approval;
  * resources — every step takes a slot of execution/guard.py (one GPU job at a time, VRAM gate, …);
  * budget — max_minutes of active work and max_retries per run; over budget → NEEDS_USER_ACTION, never silently more;
  * idempotency — a side-effecting step (an experiment) carries the key <run>:<step>:<attempt>; after a crash or a
    restart the engine looks for the job with that key and reuses its result instead of starting a duplicate;
  * recovery — a CUDA OOM is analysed (batch size, precision) and retried with a recorded config change when the budget
    allows it, otherwise the proposal waits for the researcher (Failed → Analyzing → Recovering → Resumed / Needs approval);
  * evidence — an experiment is COMPLETED only with valid measured metrics; synthetic numbers are labelled SYNTHETIC and
    never count as verified; sources a research step cites are checked against the library and stay "unverified"
    when they cannot be matched.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
from pathlib import Path

from backend.agent import AIWSError, new_id, now, read_json, write_json

STATES = ("CREATED", "PLANNED", "APPROVAL_PENDING", "RUNNING", "VERIFYING", "COMPLETED", "BLOCKED", "FAILED",
          "RECOVERING", "NEEDS_USER_ACTION", "CANCELLED")
TERMINAL = ("COMPLETED", "CANCELLED")
WORKING = ("RUNNING", "VERIFYING", "RECOVERING", "BLOCKED")
TRANSITIONS = {
    "CREATED": {"PLANNED", "CANCELLED", "FAILED"},
    "PLANNED": {"APPROVAL_PENDING", "RUNNING", "CANCELLED"},
    "APPROVAL_PENDING": {"RUNNING", "CANCELLED"},
    "RUNNING": {"VERIFYING", "BLOCKED", "FAILED", "NEEDS_USER_ACTION", "COMPLETED", "CANCELLED", "RECOVERING"},
    "VERIFYING": {"RUNNING", "COMPLETED", "FAILED", "NEEDS_USER_ACTION", "BLOCKED", "CANCELLED", "RECOVERING"},
    "BLOCKED": {"RUNNING", "VERIFYING", "NEEDS_USER_ACTION", "CANCELLED", "RECOVERING"},
    "FAILED": {"RECOVERING", "NEEDS_USER_ACTION", "CANCELLED"},
    "RECOVERING": {"RUNNING", "VERIFYING", "NEEDS_USER_ACTION", "FAILED", "CANCELLED", "BLOCKED"},
    "NEEDS_USER_ACTION": {"RECOVERING", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
PIPELINES = {
    "research": ("research", "verify_sources", "report"),
    "idea": ("plan", "code", "experiment", "verify_metrics", "report"),
    "code": ("code", "report"),
    "experiment": ("experiment", "verify_metrics", "report"),
    "review": ("review", "report"),
    "verify": ("verify_claims", "report"),
    "latex": ("latex", "report"),
}
LABEL = {"research": "Tổng hợp tài liệu", "verify_sources": "Kiểm chứng nguồn", "report": "Báo cáo", "plan": "Lập kế hoạch",
         "code": "Viết code", "experiment": "Chạy thí nghiệm", "verify_metrics": "Kiểm chứng metrics",
         "review": "Phản biện", "verify_claims": "Đối chiếu claim với bằng chứng", "latex": "Biên dịch LaTeX"}
SIDE_EFFECT = {"experiment", "code"}
RID_RE = re.compile(r"^RR-[0-9a-f]{8}$")
_lock = threading.RLock()
_cond = threading.Condition(_lock)
_drivers: dict = {}   # run id → {"cancel": Event}
_buf: dict = {}       # run id → recent events
_seq: dict = {}
EXECUTORS: dict = {}  # step kind → fn(ctx) (registered at the end of this module)


class StepFailure(Exception):
    """A step failed. failure_class drives recovery (gpu_oom, no_metrics, provider, lost, budget, …)."""

    def __init__(self, msg: str, failure_class: str = "", recoverable: bool = False, detail: str = ""):
        super().__init__(msg)
        self.failure_class, self.recoverable, self.detail = failure_class, recoverable, detail


# ------------------------------------------------------------------ storage
def _dir() -> Path:
    from backend.core.config import workspace
    d = workspace() / "research_runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(rid: str) -> Path:
    if not isinstance(rid, str) or not RID_RE.match(rid):
        raise AIWSError("Invalid run id")
    return _dir() / f"{rid}.json"


def out_dir(rid: str) -> Path:
    d = _dir() / rid
    d.mkdir(parents=True, exist_ok=True)
    return d


def get(rid: str) -> dict:
    r = read_json(_path(rid))
    if not isinstance(r, dict):
        raise AIWSError("Run not found")
    return r


def _save(r: dict) -> dict:
    r["updated"] = now()
    with _lock:
        write_json(_path(r["id"]), r)
    return r


def update(rid: str, fn):
    with _lock:
        r = get(rid)
        out = fn(r)
        _save(r)
        return out


def summary(r: dict) -> dict:
    cur = next((s for s in r["steps"] if s["id"] == r.get("current")), None)
    done = sum(1 for s in r["steps"] if s["status"] in ("done", "skipped"))
    return {"id": r["id"], "title": r["title"], "pipeline": r["pipeline"], "skill": r.get("skill", ""), "status": r["status"],
            "created": r["created"], "updated": r["updated"], "session_id": r.get("session_id", ""),
            "synthetic": r.get("synthetic", False), "steps": len(r["steps"]), "done": done,
            "current": cur and {"id": cur["id"], "label": cur["label"], "provider": cur["provider"], "status": cur["status"]},
            "reason": r.get("reason", ""), "next_decision": r.get("next_decision", ""),
            "approval": r.get("approval", {}).get("status", "")}


def list_runs(status: str = "", session_id: str = "", limit: int = 100) -> list:
    out = []
    for f in _dir().glob("RR-*.json"):
        r = read_json(f)
        if not isinstance(r, dict) or "steps" not in r:
            continue
        if status and r["status"] not in status.split(","):
            continue
        if session_id and r.get("session_id") != session_id:
            continue
        out.append(summary(r))
    return sorted(out, key=lambda x: -x["updated"])[:limit]


# ------------------------------------------------------------------ events (unified progress tracking)
def _events_path(rid: str) -> Path:
    return _dir() / f"{rid}.events.jsonl"


def emit(rid: str, type_: str, **data) -> dict:
    with _cond:
        if rid not in _seq:
            p = _events_path(rid)
            _seq[rid] = sum(1 for _ in p.open("r", encoding="utf-8")) if p.exists() else 0
        _seq[rid] += 1
        e = {"seq": _seq[rid], "ts": now(), "run_id": rid, "type": type_, "data": data}
        _buf.setdefault(rid, []).append(e)
        del _buf[rid][:-500]
        try:
            with open(_events_path(rid), "a", encoding="utf-8") as f:
                f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
        _cond.notify_all()
    from backend.core import bus
    bus.publish("run." + type_.split(".", 1)[-1] if type_.startswith("run.") else "run.progress", run_id=rid, type=type_)
    return e


def events(rid: str, after: int = 0) -> list:
    get(rid)
    p = _events_path(rid)
    out = []
    if p.exists():
        for line in p.read_text("utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("seq", 0) > after:
                out.append(e)
    return out


def wait_events(rid: str, after: int, timeout: float = 15.0) -> list:
    end = time.time() + timeout
    with _cond:
        while (_seq.get(rid) or 0) <= after:
            left = end - time.time()
            if left <= 0:
                break
            _cond.wait(left)
    return events(rid, after)


# ------------------------------------------------------------------ state machine
def _transition(r: dict, to: str, reason: str = "") -> None:
    frm = r["status"]
    if to == frm:
        r["reason"] = reason or r.get("reason", "")
        return
    if to not in TRANSITIONS[frm]:
        raise AIWSError(f"Run {r['id']}: {frm} → {to} is not allowed")
    r["status"] = to
    r["reason"] = reason
    r["history"].append({"ts": now(), "from": frm, "to": to, "reason": reason[:500]})


def transition(rid: str, to: str, reason: str = "") -> dict:
    out = update(rid, lambda r: (_transition(r, to, reason), summary(r))[1])
    emit(rid, "run.state", status=to, reason=reason[:500])
    _notify(rid)
    return out


def _cfg() -> dict:
    from backend.core.config import load_config
    return load_config().get("runs") or {}


def _needs_approval(risk: int) -> bool:
    return int(risk) > int(_cfg().get("auto_approve_risk", 1))


def create(pipeline: str, title: str, goal: str = "", inputs: dict | None = None, session_id: str = "", turn_id: str = "",
           skill: str = "", risk: int = 2, provider: str = "", steps: list | None = None, synthetic: bool = False,
           budget: dict | None = None, start: bool = True) -> dict:
    """A new run. It goes CREATED → PLANNED → (APPROVAL_PENDING | RUNNING) immediately; nothing runs before approval."""
    if pipeline not in PIPELINES:
        raise AIWSError(f"pipeline must be one of {', '.join(PIPELINES)}")
    cfg = _cfg()
    rid = "RR-" + new_id("x", 4)[2:]
    kinds = steps or [{"kind": k} for k in PIPELINES[pipeline]]
    if not kinds:
        raise AIWSError("A run needs at least one step")
    st = []
    for i, k in enumerate(kinds, 1):
        kind = k["kind"]
        if kind not in EXECUTORS:
            raise AIWSError(f"Unknown step kind {kind}")
        st.append({"id": f"S{i}", "kind": kind, "label": k.get("label") or LABEL.get(kind, kind),
                   "provider": k.get("provider") or _default_provider(kind, provider), "status": "pending", "attempt": 0,
                   "idempotency_key": "", "started": None, "ended": None, "inputs": [], "outputs": [], "result": {},
                   "error": "", "resource": "", "notes": [], "spec": dict(k.get("spec") or {}), "active_s": 0.0})
    b = {"max_minutes": float(cfg.get("max_minutes", 120)), "max_retries": int(cfg.get("max_retries", 1)),
         "auto_recover": bool(cfg.get("auto_recover", True))}
    for key, val in (budget or {}).items():
        if key in b:
            b[key] = type(b[key])(val)
    from backend.core.config import active_project
    r = {"id": rid, "schema": 1, "title": (title or pipeline)[:160], "pipeline": pipeline, "skill": skill, "goal": goal[:4000],
         "inputs": inputs or {}, "status": "CREATED", "reason": "", "created": now(), "updated": now(),
         "project": active_project().get("name", ""), "session_id": session_id, "turn_id": turn_id,
         "synthetic": bool(synthetic), "risk": int(risk), "budget": b, "usage": {"active_s": 0.0, "retries": 0},
         "approval": {"required": _needs_approval(risk), "status": "pending" if _needs_approval(risk) else "auto",
                      "by": "", "at": None},
         "steps": st, "current": "", "history": [{"ts": now(), "from": "", "to": "CREATED", "reason": "created"}],
         "outputs": [], "result": {}, "proposal": None, "next_decision": ""}
    with _lock:
        write_json(_path(rid), r)
    emit(rid, "run.created", title=r["title"], pipeline=pipeline, steps=[s["kind"] for s in st], synthetic=r["synthetic"])
    transition(rid, "PLANNED", f"{len(st)} bước: " + " → ".join(s["label"] for s in st))
    if r["approval"]["required"]:
        update(rid, lambda x: x.update(next_decision="Duyệt để bắt đầu chạy?"))
        transition(rid, "APPROVAL_PENDING", f"rủi ro {risk}: cần bạn duyệt trước khi chạy")
    elif start:
        transition(rid, "RUNNING", "tự chạy (rủi ro thấp)")
        spawn(rid)
    return get(rid)


def _default_provider(kind: str, preferred: str) -> str:
    if kind in ("research", "review"):
        return preferred or "app"
    if kind in ("plan", "verify_claims", "report", "verify_sources", "verify_metrics"):
        return "app" if kind in ("plan", "verify_claims") else "phdlab"
    if kind == "code":
        return preferred if preferred in ("claude_code", "codex", "gemini_cli", "antigravity") else "app"
    if kind == "experiment":
        return "python"
    if kind == "latex":
        return "latex"
    return preferred or "synthetic"


def approve(rid: str, by: str = "researcher") -> dict:
    r = get(rid)
    if r["status"] != "APPROVAL_PENDING":
        raise AIWSError(f"Run is {r['status']}, not waiting for approval")
    update(rid, lambda x: (x["approval"].update(status="approved", by=by, at=now()), x.update(next_decision="")))
    emit(rid, "run.approved", by=by)
    transition(rid, "RUNNING", f"đã được {by} duyệt")
    spawn(rid)
    return get(rid)


def _check_engine_swap(step: dict, provider: str | None) -> None:
    native = step.get("result", {}).get("engine_job_id")
    if step.get("provider") == "openscience" and provider != "openscience" and native:
        from backend.research_engines.openscience import require_settled
        require_settled(native)


def cancel(rid: str, by: str = "researcher") -> dict:
    r = get(rid)
    if r["status"] in TERMINAL:
        raise AIWSError(f"Run is already {r['status']}")
    with _lock:
        d = _drivers.get(rid)
    if d:
        d["cancel"].set()
    else:
        # A native run can still be awaiting a decision while no local driver exists.
        for step in r["steps"]:
            native = step.get("result", {}).get("engine_job_id")
            if step["provider"] == "openscience" and native and step["status"] != "done":
                try:
                    from backend.research_engines.openscience import cancel_job
                    settlement = cancel_job(native)
                except Exception as error:
                    from backend.core.telemetry import redact
                    settlement = {"state": "cancellation_unconfirmed", "detail": redact(str(error))[:500]}
                update(rid, lambda x, sid=step["id"], value=settlement: next(s for s in x["steps"] if s["id"] == sid)["result"].update(external_cancellation=value))
    job = next((s.get("result", {}).get("job_id") for s in r["steps"] if s["status"] == "running"), None)
    if job:
        try:
            from backend.execution.sandbox import stop_job
            stop_job(job)
        except Exception:
            pass
    if r["approval"]["status"] == "pending":
        update(rid, lambda x: x["approval"].update(status="rejected", by=by, at=now()))
    update(rid, lambda x: [s.update(status="skipped") for s in x["steps"] if s["status"] in ("pending", "running")])
    transition(rid, "CANCELLED", f"huỷ bởi {by}")
    return get(rid)


def resume(rid: str, accept_proposal: bool = True, patch: dict | None = None, by: str = "researcher") -> dict:
    """The researcher's answer to NEEDS_USER_ACTION: accept the proposal (recovery patch) or retry as is."""
    r = get(rid)
    if r["status"] != "NEEDS_USER_ACTION":
        raise AIWSError(f"Run is {r['status']} — only a run that needs your action can be resumed")
    prop = r.get("proposal") or {}
    step_id = prop.get("step") or next((s["id"] for s in r["steps"] if s["status"] in ("failed", "pending")), "")
    previous = next((s for s in r["steps"] if s["id"] == step_id), {})
    _check_engine_swap(previous, (patch or {}).get("provider", previous.get("provider")))

    def fn(x):
        s = next((y for y in x["steps"] if y["id"] == step_id), None)
        if s is None:
            raise AIWSError("Nothing to resume")
        if accept_proposal and prop.get("patch"):
            s["spec"].update(prop["patch"])
            s["notes"].append(f"accepted by {by}: {prop.get('text', '')[:300]}")
        if patch:
            allowed = {k: v for k, v in patch.items() if k in ("command", "provider", "topic", "gpu", "needs_linux")}
            if "provider" in allowed:
                s["provider"] = str(allowed.pop("provider"))
            s["spec"].update(allowed)
        if s["provider"] == "openscience":
            x["risk"] = max(2, x["risk"])
            x["approval"].update(required=True, status="approved", by=by, at=now())
        s.update(status="pending", error="")
        x["usage"]["retries"] += 1
        x["proposal"] = None
        x["next_decision"] = ""
        x["budget"]["max_retries"] = max(x["budget"]["max_retries"], x["usage"]["retries"])
    update(rid, fn)
    emit(rid, "run.resumed", by=by, step=step_id, accepted=bool(accept_proposal and prop.get("patch")))
    transition(rid, "RECOVERING", f"tiếp tục theo quyết định của {by}")
    transition(rid, "RUNNING", "đã khôi phục")
    spawn(rid)
    return get(rid)


def swap_provider(rid: str, step_id: str, provider: str) -> dict:
    """Run a pending / failed step on another provider. Completed steps and their outputs are kept (no state lost)."""
    from backend.providers.research import CATALOG
    if provider not in CATALOG and provider not in ("phdlab", "synthetic"):
        raise AIWSError(f"Unknown provider {provider}")
    previous = next((s for s in get(rid)["steps"] if s["id"] == step_id), {})
    _check_engine_swap(previous, provider)

    def fn(x):
        s = next((y for y in x["steps"] if y["id"] == step_id), None)
        if not s:
            raise AIWSError("Step not found")
        if s["status"] in ("done", "running"):
            raise AIWSError(f"Step {step_id} is {s['status']} — only a pending or failed step can change provider")
        old = s["provider"]
        s["provider"] = provider
        s["notes"].append(f"provider {old} → {provider}")
        return old
    old = update(rid, fn)
    emit(rid, "step.provider", step=step_id, old=old, new=provider)
    return get(rid)


# ------------------------------------------------------------------ driver
def spawn(rid: str) -> bool:
    """Start the background driver of a run (one per run; a second call is a no-op)."""
    from backend.core.config import data_dir
    with _lock:
        if rid in _drivers:
            return False
        _drivers[rid] = {"cancel": threading.Event()}
    proj = str(data_dir().resolve())

    def work():
        from backend.core.config import project_scope
        with project_scope(proj):
            try:
                _drive(rid)
            except Exception as e:  # never leave a run silently stuck
                try:
                    r = get(rid)
                    if r["status"] not in TERMINAL and r["status"] != "NEEDS_USER_ACTION":
                        _needs_user(rid, "", f"lỗi nội bộ: {type(e).__name__}: {e}"[:400])
                except Exception:
                    pass
            finally:
                from backend.execution import guard
                guard.release_all(rid)
                with _lock:
                    _drivers.pop(rid, None)
    threading.Thread(target=work, daemon=True, name=f"run-{rid}").start()
    return True


def _cancelled(rid: str) -> bool:
    with _lock:
        d = _drivers.get(rid)
    return bool(d and d["cancel"].is_set())


def wait(rid: str, timeout: float = 60) -> dict:
    """Tests / CLI: wait until the run leaves the working states."""
    end = time.time() + timeout
    while time.time() < end:
        r = get(rid)
        with _lock:
            driving = rid in _drivers
        if r["status"] not in WORKING and not driving:
            return r
        time.sleep(0.05)
    return get(rid)


class Ctx:
    """What an executor sees: the run (read-only copy), its step, an output folder, cancellation and logging."""

    def __init__(self, rid: str, step: dict):
        self.rid, self.step = rid, step
        self.run = get(rid)
        self.out = out_dir(rid)

    def cancelled(self) -> bool:
        return _cancelled(self.rid)

    def log(self, msg: str, **data) -> None:
        emit(self.rid, "step.log", step=self.step["id"], message=str(msg)[:1000], **data)

    def set(self, **fields) -> None:
        sid = self.step["id"]
        update(self.rid, lambda x: next(y for y in x["steps"] if y["id"] == sid)["result"].update(fields))
        self.step["result"].update(fields)

    def prior(self, kind: str) -> dict:
        """Result of the last completed step of this kind (plan → code → experiment chain)."""
        r = get(self.rid)
        s = next((y for y in reversed(r["steps"]) if y["kind"] == kind and y["status"] == "done"), None)
        return (s or {}).get("result") or {}

    def write(self, name: str, text: str) -> str:
        f = self.out / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, "utf-8")
        return self.rel(f)

    @staticmethod
    def rel(f: Path) -> str:
        """Path of a project file relative to the research project folder (what the UI and the CLI open)."""
        from backend.core.config import data_dir
        return str(Path(f).resolve().relative_to(data_dir().resolve())).replace("\\", "/")


def _resource(r: dict, s: dict) -> str:
    if s["provider"] == "openscience":
        from backend.core.config import load_config
        return "gpu" if load_config()["openscience"].get("allow_execution") else "cli"
    if s["kind"] == "experiment":
        return "gpu" if s["spec"].get("gpu", r["inputs"].get("gpu")) else "cpu"
    if s["kind"] == "synthetic":
        return "none"
    if s["provider"] in ("feynman", "claude_code", "codex", "gemini_cli", "antigravity"):
        return "cli"
    if s["provider"] == "app" and s["kind"] in ("research", "plan", "code", "review", "verify_claims"):
        from backend.core.config import load_config
        from backend.providers.models import resolve_engine
        eng = resolve_engine(load_config(), "reviewer" if s["kind"] in ("review", "verify_claims") else "research")
        return "local_llm" if eng in ("local", "ollama") else "cloud"
    return "none"


def _resolve_provider(rid: str, step: dict) -> dict:
    """A research / review / code step whose provider is not set up moves to the app model BEFORE it takes a resource
    slot — with the reason recorded on the step (shown in the timeline), never silently."""
    if step["kind"] not in ("research", "review", "code") or step["provider"] in ("app", "phdlab", "synthetic"):
        return step
    from backend.providers import research as RP
    pid, note = RP.pick(step["provider"])
    if pid == step["provider"]:
        return step
    if step["provider"] == "openscience":
        _needs_user(rid, step["id"], note + "; OpenScience is not automatically replaced",
                    {"kind": "provider", "text": "Configure the runtime or explicitly select another research engine", "patch": {}})
        return step
    from backend.core.config import load_config
    if load_config()["routing"].get("capability_aware", True):
        _needs_user(rid, step["id"], note + "; choose a verified provider or wait; completed steps are retained",
                    {"kind": "provider", "text": "Restore quota or select a capable provider, then resume this step", "patch": {}})
        return step

    def fn(x):
        s = next(y for y in x["steps"] if y["id"] == step["id"])
        s["provider"] = pid
        s["notes"].append(note)
        return dict(s)
    out = update(rid, fn)
    emit(rid, "step.provider", step=step["id"], old=step["provider"], new=pid, reason=note)
    return out


def _active_s(r: dict) -> float:
    return sum(float(s.get("active_s") or 0) for s in r["steps"])


def _drive(rid: str) -> None:
    from backend.execution import guard
    while True:
        r = get(rid)
        if _cancelled(rid) or r["status"] not in ("RUNNING", "VERIFYING", "RECOVERING", "BLOCKED"):
            return
        step = next((s for s in r["steps"] if s["status"] in ("pending", "running")), None)
        if step is None:
            return _finish(rid)
        if _active_s(r) > r["budget"]["max_minutes"] * 60:
            return _needs_user(rid, step["id"], f"vượt ngân sách {r['budget']['max_minutes']:g} phút — tăng ngân sách hoặc dừng",
                               {"kind": "budget"})
        want = "VERIFYING" if step["kind"].startswith("verify") else "RUNNING"
        step = _resolve_provider(rid, step)
        r = get(rid)
        if r["status"] == "NEEDS_USER_ACTION":
            return
        res = _resource(r, step)

        def waiting(reason, rid=rid):
            if get(rid)["status"] != "BLOCKED":
                transition(rid, "BLOCKED", reason)
            else:
                update(rid, lambda x: x.update(reason=reason))
                emit(rid, "run.state", status="BLOCKED", reason=reason)
        try:
            guard.acquire(res, rid, on_wait=waiting, cancelled=lambda: _cancelled(rid))
        except guard.Busy:
            return  # cancelled while waiting
        try:
            if get(rid)["status"] != want:
                transition(rid, want, f"{step['label']} · {step['provider']}")
            if not _run_step(rid, step["id"], res):
                return
        finally:
            guard.release(res, rid)


def _run_step(rid: str, step_id: str, res: str) -> bool:
    """True when the driver may continue with the next step."""
    def start(x):
        s = next(y for y in x["steps"] if y["id"] == step_id)
        if s["status"] == "pending":
            s["attempt"] += 1
        s.update(status="running", started=s["started"] or now(), resource=res, error="")
        s["idempotency_key"] = f"{x['id']}:{s['id']}:{s['attempt']}"
        x["current"] = s["id"]
        return dict(s)
    step = update(rid, start)
    emit(rid, "step.started", step=step_id, kind=step["kind"], label=step["label"], provider=step["provider"],
         attempt=step["attempt"], idempotency_key=step["idempotency_key"], resource=res)
    _notify(rid)
    t0 = time.time()
    try:
        result = EXECUTORS[step["kind"]](Ctx(rid, step)) or {}
    except StepFailure as f:
        _account(rid, step_id, t0)
        if _cancelled(rid):
            return False
        return _failed(rid, step_id, f)
    _account(rid, step_id, t0)
    if _cancelled(rid):
        return False

    def finish(x):
        s = next(y for y in x["steps"] if y["id"] == step_id)
        s["result"].update(result.get("result") or {})
        s["outputs"] = list(dict.fromkeys(s["outputs"] + list(result.get("outputs") or [])))
        s.update(status="done", ended=now())
        for o in result.get("outputs") or []:
            if o not in [y["path"] for y in x["outputs"]]:
                x["outputs"].append({"path": o, "step": step_id, "label": s["label"]})
        if result.get("note"):
            s["notes"].append(result["note"])
    update(rid, finish)
    emit(rid, "step.completed", step=step_id, outputs=result.get("outputs") or [], note=result.get("note", ""))
    return True


def _account(rid: str, step_id: str, t0: float) -> None:
    dt = round(time.time() - t0, 3)
    update(rid, lambda x: next(y for y in x["steps"] if y["id"] == step_id).update(
        active_s=round(float(next(y for y in x["steps"] if y["id"] == step_id).get("active_s") or 0) + dt, 3)))


def _failed(rid: str, step_id: str, f: StepFailure) -> bool:
    """Failed → Analyzing → Recovering → Resumed, or Needs approval (simulation spec §6)."""
    update(rid, lambda x: next(y for y in x["steps"] if y["id"] == step_id).update(
        status="failed", error=str(f)[:1000], ended=now(), failure_class=f.failure_class))
    emit(rid, "step.failed", step=step_id, error=str(f)[:500], failure_class=f.failure_class)
    r = get(rid)
    step = next(y for y in r["steps"] if y["id"] == step_id)
    if f.failure_class.startswith("engine_"):
        return _needs_user(rid, step_id, str(f),
                           {"kind": "engine_decision" if f.failure_class == "engine_decision" else "engine_recovery",
                            "job_id": f.detail, "text": str(f), "patch": {}})
    from backend.providers.cli import classify_error
    if f.failure_class == "provider" and classify_error(str(f)) in ("RATE_LIMITED", "AUTH_EXPIRED"):
        return _needs_user(rid, step_id, "Provider quota/auth unavailable; previous outputs and failed step are checkpointed",
                           {"kind": "provider", "text": "Restore quota or select a verified provider; resume only this step", "patch": {}})
    transition(rid, "FAILED", f"{step['label']}: {str(f)[:300]}")
    proposal = RECOVERY.get(f.failure_class, lambda *_: None)(r, step, f)
    if proposal is None and f.recoverable:
        proposal = {"kind": "retry", "text": "thử lại bước này", "patch": {}}
    if proposal is None:
        return _needs_user(rid, step_id, f"{step['label']} thất bại: {str(f)[:300]}",
                           {"kind": "manual", "text": "Sửa nguyên nhân (code / cấu hình / provider) rồi tiếp tục, hoặc huỷ run",
                            "patch": {}})
    emit(rid, "run.analysis", step=step_id, failure_class=f.failure_class, proposal=proposal)
    retries = r["usage"]["retries"]
    if r["budget"]["auto_recover"] and retries < r["budget"]["max_retries"]:
        def apply(x):
            s = next(y for y in x["steps"] if y["id"] == step_id)
            s["spec"].update(proposal.get("patch") or {})
            s["notes"].append("tự phục hồi: " + proposal["text"][:300])
            s.update(status="pending")
            x["usage"]["retries"] += 1
        update(rid, apply)
        transition(rid, "RECOVERING", "phân tích lỗi → " + proposal["text"][:300])
        transition(rid, "VERIFYING" if step["kind"].startswith("verify") else "RUNNING",
                   f"tiếp tục (lần thử {retries + 2})")
        return True
    return _needs_user(rid, step_id, "cần bạn duyệt cách phục hồi: " + proposal["text"][:300], proposal)


def _needs_user(rid: str, step_id: str, reason: str, proposal: dict | None = None) -> bool:
    def fn(x):
        x["proposal"] = dict(proposal or {}, step=step_id) if proposal else None
        x["next_decision"] = reason[:300]
    update(rid, fn)
    r = get(rid)
    if r["status"] == "RECOVERING":
        transition(rid, "NEEDS_USER_ACTION", reason)
    elif "NEEDS_USER_ACTION" in TRANSITIONS[r["status"]]:
        transition(rid, "NEEDS_USER_ACTION", reason)
    return False


def _finish(rid: str) -> None:
    r = get(rid)
    if any(s["status"] not in ("done", "skipped") for s in r["steps"]):
        return
    summary_text = next((s["result"].get("summary") for s in reversed(r["steps"]) if s["result"].get("summary")), "")
    update(rid, lambda x: x["result"].update(summary=summary_text, finished=now()))
    if r["status"] == "BLOCKED":
        transition(rid, "RUNNING", "")
    transition(rid, "COMPLETED", "SYNTHETIC — mô phỏng, không phải kết quả thật" if r["synthetic"] else "hoàn tất")


# ------------------------------------------------------------------ recovery policies
BATCH_RE = re.compile(r"(--batch[-_]size[ =])(\d+)|(\bBATCH_SIZE=)(\d+)")


def _oom(r: dict, step: dict, f: StepFailure) -> dict | None:
    """CUDA OOM: halve the batch size (and double gradient accumulation when the script accepts it), mixed precision."""
    cmd = step["spec"].get("command") or r["inputs"].get("command") or ""
    m = BATCH_RE.search(cmd)
    if not m:
        return {"kind": "oom", "text": "CUDA out of memory: không tìm thấy --batch-size trong lệnh — giảm batch size / "
                                       "dùng mixed precision / gradient accumulation trong code rồi tiếp tục", "patch": {}}
    old = int(m.group(2) or m.group(4))
    if old <= 1:
        return {"kind": "oom", "text": "batch size đã là 1 — cần giảm kích thước mô hình hoặc độ phân giải", "patch": {}}
    new = max(1, old // 2)
    pre = m.group(1) or m.group(3)
    new_cmd = cmd[:m.start()] + f"{pre}{new}" + cmd[m.end():]
    acc = re.search(r"--grad[-_]accum(?:ulation)?[-_]?(?:steps)?[ =](\d+)", new_cmd)
    equiv = "batch hiệu dụng giảm một nửa — kết quả KHÔNG còn tương đương hoàn toàn với cấu hình gốc"
    if acc:
        new_cmd = new_cmd[:acc.start(1)] + str(int(acc.group(1)) * 2) + new_cmd[acc.end(1):]
        equiv = "gradient accumulation ×2 giữ nguyên batch hiệu dụng (tương đương về tối ưu hoá, khác về BatchNorm)"
    return {"kind": "oom", "text": f"CUDA OOM → batch size {old} → {new}; {equiv}",
            "patch": {"command": new_cmd, "env": {"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}},
            "change": {"batch_size": [old, new]}, "equivalence": equiv}


def _lost(r: dict, step: dict, f: StepFailure) -> dict | None:
    return {"kind": "retry", "text": "tiến trình bị mất khi khởi động lại — chạy lại bước với khoá idempotency mới",
            "patch": {}}


RECOVERY = {"gpu_oom": _oom, "lost": _lost}


# ------------------------------------------------------------------ chat link
def _notify(rid: str) -> None:
    """Mirror the run into its conversation: a live status event; a message when the researcher must act or it ended."""
    r = get(rid)
    sid = r.get("session_id")
    if not sid:
        return
    from backend.agent import sessions
    try:
        sessions.emit(sid, "run.updated", r.get("turn_id", ""), run_id=rid, status=r["status"], reason=r.get("reason", ""))
    except AIWSError:
        return
    if r["status"] in ("APPROVAL_PENDING", "NEEDS_USER_ACTION", "COMPLETED", "CANCELLED"):
        key = f"{r['status']}:{len(r['history'])}"
        if r.get("_notified") == key:
            return
        update(rid, lambda x: x.update(_notified=key))
        text = _message(r)
        try:
            sessions.add_message(sid, "assistant", text, r.get("turn_id", ""), kind="run", run_id=rid, run_status=r["status"])
        except AIWSError:
            pass


def _message(r: dict) -> str:
    st = r["status"]
    head = {"APPROVAL_PENDING": "⏸ **Cần bạn duyệt** trước khi chạy", "NEEDS_USER_ACTION": "⚠ **Cần bạn quyết định**",
            "COMPLETED": "✅ **Hoàn tất**", "CANCELLED": "⏹ **Đã huỷ**"}[st]
    lines = [f"{head} — {r['title']} (`{r['id']}`)"]
    if r.get("synthetic"):
        lines.append("> SYNTHETIC — kết quả mô phỏng, không dùng làm kết quả nghiên cứu.")
    if st in ("APPROVAL_PENDING",):
        lines.append("Các bước: " + " → ".join(f"{s['label']} ({s['provider']})" for s in r["steps"]))
    if st == "NEEDS_USER_ACTION":
        lines.append(r.get("next_decision") or r.get("reason", ""))
    if st == "COMPLETED":
        if r["result"].get("summary"):
            lines.append(r["result"]["summary"])
        if r["outputs"]:
            lines.append("Kết quả: " + ", ".join(f"`{o['path'].rsplit('/', 1)[-1]}`" for o in r["outputs"][:8]))
    return "\n\n".join(x for x in lines if x)


# ------------------------------------------------------------------ restart recovery (durable execution)
def recover_all() -> list:
    """After a server restart every run that was working continues from its last committed step. A side-effecting step
    is never repeated blindly: its job is looked up by idempotency key — finished → its result is reused (same key);
    still alive → the researcher decides; gone → retried under the budget with a NEW key (attempt + 1)."""
    out = []
    for f in _dir().glob("RR-*.json"):
        r = read_json(f)
        if not isinstance(r, dict) or r.get("status") not in WORKING:
            continue
        rid = r["id"]
        with _lock:
            if rid in _drivers:
                continue
        running = next((s for s in r["steps"] if s["status"] == "running"), None)
        emit(rid, "run.restart", step=running and running["id"])
        if r["status"] != "RECOVERING":
            transition(rid, "RECOVERING", "worker khởi động lại — khôi phục từ trạng thái đã lưu")
        if running and running["kind"] in SIDE_EFFECT:
            verdict = _job_state(running)
            if verdict == "alive":
                _needs_user(rid, running["id"], "một tiến trình của run vẫn đang chạy từ trước khi khởi động lại — đợi nó "
                                                "xong hoặc dừng nó rồi tiếp tục", {"kind": "alive", "text": "đợi / dừng", "patch": {}})
                out.append({"id": rid, "action": "needs_user"})
                continue
            if verdict == "lost":
                emit(rid, "step.lost", step=running["id"], idempotency_key=running["idempotency_key"])
                if r["usage"]["retries"] >= r["budget"]["max_retries"]:
                    update(rid, lambda x: next(y for y in x["steps"] if y["id"] == running["id"]).update(status="failed"))
                    _needs_user(rid, running["id"], "tiến trình bị mất khi khởi động lại và đã hết lượt thử lại",
                                {"kind": "retry", "text": "chạy lại bước", "patch": {}})
                    out.append({"id": rid, "action": "needs_user"})
                    continue
                update(rid, lambda x: (next(y for y in x["steps"] if y["id"] == running["id"]).update(status="pending"),
                                       x["usage"].update(retries=x["usage"]["retries"] + 1)))
        transition(rid, "RUNNING", "tiếp tục từ bước đã commit cuối cùng")
        spawn(rid)
        out.append({"id": rid, "action": "resumed"})
    return out


def _job_state(step: dict) -> str:
    """'finished' (the executor reuses the result through the same key) · 'alive' · 'lost'."""
    from backend.execution import guard
    from backend.execution.sandbox import JOBS
    if step["kind"] != "experiment":
        return "lost"
    job = _find_job(step.get("idempotency_key") or "")
    if not job:
        return "lost"
    if job.get("stopped_by") == "shutdown":
        return "lost"
    if job.get("status") in ("done", "failed", "stopped"):
        return "finished"
    live = JOBS.get(job["id"])
    if (live and live.status == "running") or (not live and guard.pid_alive(job.get("pid"))):
        return "alive"
    return "lost"


def _find_job(key: str) -> dict | None:
    from backend.execution.sandbox import runs_dir
    try:
        dirs = list(runs_dir().iterdir())
    except OSError:
        return None
    for d in dirs:
        f = d / "run.json"
        if not f.exists():
            continue
        try:
            j = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if j.get("idempotency_key") == key:
            return j
    return None


def _job_result(job: dict) -> dict:
    m = {k: v for k, v in (job.get("metrics") or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return {"job_id": job["id"], "status": job.get("status"), "exit_code": job.get("exit_code"), "metrics": m,
            "failure_class": job.get("failure_class", ""), "figures": job.get("figures") or []}


# ------------------------------------------------------------------ executors
def project_brief(limit: int = 12000) -> str:
    """Provider-independent research context (objective, outline, decisions, hypotheses, library, recent runs)."""
    from backend.agent import project_context as adapters
    parts = []
    try:
        from backend.agent.outline import brief
        parts.append(brief())
    except Exception:
        pass
    for s in adapters.get("global").state(None):
        if s["kind"] == "conversation":
            continue
        parts.append(f"## {s['title']} [{s['trust']}]\n{s['text']}")
    return "\n\n".join(p for p in parts if p)[:limit]


def _llm(agent: str, system: str, user: str) -> str:
    from backend.providers import research as RP
    try:
        return RP.app_complete(agent, system, user)
    except Exception as e:
        raise StepFailure(f"model call failed: {type(e).__name__}: {e}"[:400], "provider", recoverable=True)


def _skill_text(ctx: Ctx) -> str:
    if not ctx.run.get("skill"):
        return ""
    from backend.agent import skills
    try:
        return skills.get(ctx.run["skill"])["instructions"]
    except AIWSError:
        return ""


def _research(ctx: Ctx) -> dict:
    from backend.providers import research as RP
    topic = ctx.step["spec"].get("topic") or ctx.run["inputs"].get("topic") or ctx.run["goal"]
    brief = project_brief()
    pid, note = ctx.step["provider"], ""  # already resolved by _resolve_provider (fallback recorded on the step)
    files = []
    from backend.research_engines import registry as engines
    if pid in engines.FACTORIES:
        from backend.research_engines.contracts import EngineTask, EngineFailure
        from backend.core.config import data_dir
        capability = "review" if ctx.step["kind"] == "review" else "analysis" if ctx.run.get("skill") == "science" else "literature"
        task = EngineTask(operation_id=f"{ctx.rid}:{ctx.step['id']}", attempt=ctx.step["attempt"],
                          project_id=data_dir().name, workflow_id=ctx.rid, step_id=ctx.step["id"], question=topic,
                          context=brief, capability=capability,
                          native_workflow=ctx.step["spec"].get("workflow") or ctx.run["inputs"].get("workflow") or "",
                          output_dir=ctx.out / ("feynman" if pid == "feynman" else "openscience-" + ctx.step["id"]),
                          time_limit_s=max(1, min(7200, ctx.run["budget"]["max_minutes"] * 60 - _active_s(ctx.run))),
                          approved=ctx.run["approval"]["status"] == "approved", hypothesis_id=ctx.run["inputs"].get("hypothesis_id", ""),
                          experiment_id=ctx.run["inputs"].get("experiment_id", ""))
        def progress(event):
            emit(ctx.rid, "engine.event", step=ctx.step["id"], **event.model_dump(mode="json"))
            if event.data.get("job_id"):
                ctx.set(engine_job_id=event.data["job_id"])
            if event.type == "text_delta":
                current = ctx.step["result"].get("engine_partial", "")
                ctx.set(engine_partial=(current + event.data.get("text", ""))[-8000:])
                _notify(ctx.rid)
        try:
            result = engines.get(pid).execute(task, progress, ctx.cancelled)
        except EngineFailure as e:
            if e.job_id:
                ctx.set(engine_job_id=e.job_id)
            raise StepFailure(str(e), "provider" if pid == "feynman" else "engine_" + e.kind,
                              recoverable=pid == "feynman", detail=e.job_id) from e
        text, files = result.text, [ctx.rel(Path(f["path"])) for f in result.artifact_refs]
        ctx.set(engine_provenance=result.provenance, artifact_refs=result.artifact_refs,
                native_session_id=result.native_session_id, native_run_id=result.native_run_id)
        if pid == "openscience":
            manifest = ctx.write(f"engine-evidence-{ctx.step['id']}.json", json.dumps({
                "schema_version": "1.0", "research_run": ctx.rid, "step_id": ctx.step["id"],
                "engine": pid, "native_session_id": result.native_session_id, "native_run_id": result.native_run_id,
                "provenance": result.provenance, "artifact_refs": result.artifact_refs,
                "scientific_review": "pending", "clearml_task_id": None,
            }, ensure_ascii=False, indent=2))
            files.append(manifest)
            ctx.set(evidence_manifest=manifest)
    elif pid in RP.CODING:
        try:
            res = RP.run_coding(f"{ctx.rid}-{ctx.step['id']}-{ctx.step['attempt']}", pid, topic, brief, ctx.out / pid,
                                ctx.cancelled)
        except RP.ProviderUnavailable as e:
            raise StepFailure(str(e), "provider", recoverable=True)
        text = res["text"]
    else:
        agent = "reviewer" if ctx.run.get("pipeline") == "review" else "research"
        system = ("You are the research agent of PhD Research Lab. Work only from the project context and sources you can "
                  "name; mark every claim you cannot support as UNVERIFIED; never invent citations, numbers or results. "
                  "Answer in the researcher's language.\n\n" + _skill_text(ctx) + "\n\n# Project context\n" + brief)
        sources = _search(ctx, topic) if ctx.run.get("pipeline") == "research" else []
        if sources:
            from backend.knowledge import websearch as WS
            system += WS.WEB_RULES + "\n" + WS.sources_block(sources)
            files.append(ctx.write("sources.json", json.dumps(WS.compact(sources), ensure_ascii=False, indent=1)))
            ctx.set(sources=WS.compact(sources))
        text = _llm(agent, system, topic)
    if not text.strip():
        raise StepFailure("provider returned no text", "provider", recoverable=True)
    ref = ctx.write("review_report.md" if ctx.step["kind"] == "review" else "research_report.md", text)
    return {"outputs": [ref] + files, "result": {"text": text[:20000], "provider": pid}, "note": note}


def _search(ctx: Ctx, topic: str) -> list:
    """Real scholarly metadata for the topic (OpenAlex, Semantic Scholar, arXiv) — the model may cite only these."""
    if not _cfg().get("web_search", True):
        return []
    import asyncio

    from backend.knowledge import websearch as WS
    try:
        query = re.sub(r"\s+", " ", topic)[:300]
        res = asyncio.run(asyncio.wait_for(WS.search("both", [query], [query]), 90))
    except Exception as e:
        ctx.log(f"tìm bài báo thất bại: {type(e).__name__}: {e}"[:300])
        return []
    if res.get("errors"):
        ctx.log("nguồn tìm kiếm lỗi: " + ", ".join(res["errors"])[:300])
    return res.get("sources") or []


CITE_RE = re.compile(r"(10\.\d{4,9}/[^\s\]\)>,;]+)|arXiv:\s?(\d{4}\.\d{4,5})|\(([A-Z][A-Za-z-]+)(?: et al\.)?,? (\d{4})\)"
                     r"|\[(S\d{1,3})\]")


def _verify_sources(ctx: Ctx) -> dict:
    """Every citation-like mention in the research text is checked against the project's library."""
    prior = ctx.prior("research")
    text = prior.get("text") or ""
    retrieved = {s.get("id"): s for s in prior.get("sources") or []}
    from backend.knowledge.library import included
    lib = included()
    ledger = []
    for m in CITE_RE.finditer(text):
        doi, arxiv, author, year, sref = m.groups()
        if sref:
            s = retrieved.get(sref)
            ledger.append({"citation": m.group(0), "status": "retrieved" if s else "unverified",
                           "title": (s or {}).get("title", ""), "url": (s or {}).get("url", "")})
            continue
        hit = None
        for e in lib:
            if doi and doi.lower().rstrip(".") == str(e.get("doi") or "").lower():
                hit = e
            elif arxiv and arxiv in str(e.get("arxiv") or e.get("url") or e.get("eprint") or ""):
                hit = e
            elif author and year and author.lower() in str(e.get("authors") or "").lower() and str(year) == str(e.get("year")):
                hit = e
            if hit:
                break
        ledger.append({"citation": m.group(0), "status": "in_library" if hit else "unverified",
                       "library_key": (hit or {}).get("key", "")})
    uniq = list({x["citation"]: x for x in ledger}.values())
    ok = sum(1 for x in uniq if x["status"] in ("in_library", "retrieved"))
    ref = ctx.write("evidence_ledger.json", json.dumps({"citations": uniq, "checked": now(),
                                                        "rule": "in_library = matches the project library · retrieved = "
                                                                "a real record returned by the scholarly search for this run · "
                                                                "unverified = neither"},
                                                       ensure_ascii=False, indent=1))
    msg = (f"{ok}/{len(uniq)} trích dẫn khớp thư viện / kết quả tìm kiếm thật; {len(uniq) - ok} chưa kiểm chứng" if uniq else
           "không có trích dẫn nào để đối chiếu — mọi nhận định đều ở trạng thái chưa kiểm chứng")
    return {"outputs": [ref], "result": {"citations": len(uniq), "verified": ok, "summary_line": msg}, "note": msg}


def _plan(ctx: Ctx) -> dict:
    idea = ctx.run["inputs"].get("idea") or ctx.run["goal"]
    folder = f"ideas/{ctx.rid}"
    system = ("You are the research agent of PhD Research Lab. Turn the researcher's idea into a SMALL, quick experiment "
              "that runs on one PC (RTX 3060 12 GB, 32 GB RAM) in minutes. Write: 1) a short plan (hypothesis, data, "
              "metric, baseline); 2) the code as fenced blocks with a path, e.g. ```python path=" + folder + "/main.py; "
              "the script must write its final metrics as JSON to os.environ['RUN_DIR']/metrics.json; 3) one fenced block "
              "```phdlab-run\\n<command run from the code project root>\\n``` (expose --batch-size if it trains). "
              "Use only packages likely installed (numpy, torch if needed). Do not download large datasets.\n\n"
              + _skill_text(ctx) + "\n\n# Project context\n" + project_brief(6000))
    text = _llm("research", system, idea)
    ref = ctx.write("plan.md", text)
    return {"outputs": [ref], "result": {"text": text[:40000], "summary_line": "đã lập kế hoạch thí nghiệm"}}


FILE_RE = re.compile(r"```[\w+-]*\s+path=([^\s`]+)\s*\n(.*?)```", re.S)
RUN_RE = re.compile(r"```phdlab-run\s*\n(.*?)```", re.S)


def _code(ctx: Ctx) -> dict:
    """Materialise code into the active code project, only inside the run's own folder ideas/<run> (files outside it are
    never touched; a retry of this step rewrites the same folder)."""
    if ctx.run["approval"]["status"] != "approved":
        raise StepFailure("writing code needs the researcher's approval of this run", "permission")
    from backend.execution.code_projects import NoCodeProject, active_dir
    try:
        root = active_dir()
    except NoCodeProject:
        raise StepFailure("no code project is open — create one (Experiment → VS Code) first", "no_code_project")
    folder = f"ideas/{ctx.rid}"
    source = ctx.prior("plan").get("text") or ""
    pid = ctx.step["provider"]
    if pid != "app" or not FILE_RE.search(source):
        from backend.providers import research as RP
        task = (ctx.run["inputs"].get("task") or ctx.run["goal"]) + "\n\n" + source[:20000]
        if pid in RP.CODING:
            pid2, note = RP.pick(pid)
            if pid2 == pid:
                try:
                    res = RP.run_coding(f"{ctx.rid}-{ctx.step['id']}-{ctx.step['attempt']}", pid, task + f"\n\nWrite every file "
                                        f"under {folder}/ and print a ```phdlab-run``` block with the command.", project_brief(6000),
                                        ctx.out / pid, ctx.cancelled)
                except RP.ProviderUnavailable as e:
                    raise StepFailure(str(e), "provider", recoverable=True)
                source = res["text"] + "\n" + "\n".join(
                    f"```text path={folder}/{f}\n{(ctx.out / pid / f).read_text('utf-8', 'replace')}\n```"
                    for f in res["files"] if (ctx.out / pid / f).suffix in (".py", ".txt", ".yaml", ".yml", ".json", ".md"))
            else:
                ctx.log(note)
        if not FILE_RE.search(source):
            source = _llm("research", "Write the code for this experiment as fenced blocks with path= under " + folder +
                          "/ and one ```phdlab-run``` block. The script writes metrics JSON to $RUN_DIR/metrics.json.\n\n"
                          + _skill_text(ctx), task)
    written = []
    for path, body in FILE_RE.findall(source):
        rel = path.strip().lstrip("./").replace("\\", "/")
        if not rel.startswith(folder + "/"):
            rel = f"{folder}/{rel.split('/')[-1]}"
        if ".." in rel.split("/"):
            continue
        dst = (root / rel).resolve()
        if root.resolve() not in dst.parents:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(body, "utf-8")
        written.append(rel)
    if not written:
        raise StepFailure("no code file was produced", "no_code", recoverable=True)
    cmd = (RUN_RE.findall(source) or [""])[-1].strip().splitlines()
    command = cmd[0].strip() if cmd else ""
    if not command:
        main = next((w for w in written if w.endswith("main.py")), next((w for w in written if w.endswith(".py")), ""))
        command = f"python {main}" if main else ""

    def fix(m):  # a script path the model wrote relative to somewhere else → the file this step actually wrote
        tok = m.group(0)
        if (root / tok).exists():
            return tok
        hit = next((w for w in written if w.rsplit("/", 1)[-1] == tok.replace("\\", "/").rsplit("/", 1)[-1]), "")
        return hit or tok
    command = re.sub(r"[\w./\\-]+\.py\b", fix, command)
    ref = ctx.write("code_files.json", json.dumps({"folder": folder, "written": written, "command": command},
                                                  indent=1))
    try:
        from backend.execution import gitops
        gitops.commit(f"research run {ctx.rid}: code for '{ctx.run['title'][:60]}'", written)
    except Exception as e:
        ctx.log(f"git commit skipped: {e}"[:200])
    return {"outputs": [ref], "result": {"files": written, "command": command, "folder": folder,
                                         "summary_line": f"{len(written)} file trong {folder}/"}}


def _experiment(ctx: Ctx) -> dict:
    if ctx.run["approval"]["status"] != "approved" and not ctx.run.get("synthetic"):
        raise StepFailure("an experiment needs the researcher's approval of this run", "permission")
    from backend.execution import sandbox as SB
    spec = ctx.step["spec"]
    cmd = spec.get("command") or ctx.prior("code").get("command") or ctx.run["inputs"].get("command") or ""
    if not cmd:
        raise StepFailure("no command to run", "no_command")
    key = ctx.step["idempotency_key"]
    prev = _find_job(key)
    if prev and prev.get("status") in ("done", "failed", "stopped") and prev.get("stopped_by") != "shutdown":
        job_id, res = prev["id"], _job_result(prev)
        ctx.log(f"reusing job {job_id} (idempotency key {key})")
    else:
        from backend.providers.research import needs_linux
        mode = "docker" if (spec.get("needs_linux") or ctx.run["inputs"].get("needs_linux") or needs_linux(cmd)) else "local"
        env = dict(spec.get("env") or {})
        if not spec.get("gpu", ctx.run["inputs"].get("gpu")):
            env["CUDA_VISIBLE_DEVICES"] = ""
        try:
            job = SB.start_job(cmd, "run", f"{ctx.rid} · {ctx.run['title'][:50]}", extra_env=env, mode=mode,
                               meta={"research_run": ctx.rid, "idempotency_key": key})
        except SB.SandboxError as e:
            fc = "vram_busy" if isinstance(e, SB.VramBusyError) else "sandbox"
            raise StepFailure(str(e), fc, recoverable=fc == "vram_busy")
        ctx.set(job_id=job.id)
        ctx.log(f"job {job.id} started ({mode}) $ {cmd}")
        limit = ctx.run["budget"]["max_minutes"] * 60 - _active_s(get(ctx.rid))
        t0 = time.time()
        while job.status == "running" or job.status == "queued":
            if ctx.cancelled():
                SB.stop_job(job.id)
                raise StepFailure("cancelled", "cancelled")
            if time.time() - t0 > limit:
                SB.stop_job(job.id)
                raise StepFailure(f"budget of {ctx.run['budget']['max_minutes']:g} min reached — job stopped", "budget")
            time.sleep(0.25)
        for _ in range(400):  # the job's waiter thread writes the final run.json right after collecting metrics
            j = _find_job(key)
            if j and j.get("status") == job.status:
                break
            time.sleep(0.05)
        j = SB.get_run(job.id)
        job_id, res = job.id, _job_result(j)
        res["failure_class"] = j.get("failure_class") or ""
        res["stderr_tail"] = (j.get("stderr") or "")[-2000:]
    ctx.set(**res)
    if res.get("status") != "done":
        from backend.execution.resources import classify_failure
        fc = res.get("failure_class") or classify_failure(res.get("stderr_tail", ""))
        raise StepFailure(f"job {job_id} {res.get('status')} (exit {res.get('exit_code')})"
                          + (f" — {fc}" if fc else ""), fc, detail=res.get("stderr_tail", ""))
    return {"outputs": [f"runs/{job_id}/run.json"], "result": dict(res, summary_line=f"job {job_id} xong")}


def valid_metrics(m: dict) -> dict:
    return {k: v for k, v in (m or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}


def _verify_metrics(ctx: Ctx) -> dict:
    exp = ctx.prior("experiment") or ctx.prior("synthetic")
    m = valid_metrics(exp.get("metrics") or {})
    if not m:
        raise StepFailure("thí nghiệm không có metrics hợp lệ — run KHÔNG được đánh dấu hoàn tất", "no_metrics")
    label = "SYNTHETIC" if ctx.run.get("synthetic") or exp.get("synthetic") else "MEASURED"
    ref = ctx.write("metrics_verified.json", json.dumps({"label": label, "metrics": m, "job_id": exp.get("job_id", "")},
                                                        indent=1))
    return {"outputs": [ref], "result": {"metrics": m, "label": label, "job_id": exp.get("job_id", ""),
                                         "summary_line": f"{label}: " + ", ".join(f"{k}={v:g}" for k, v in list(m.items())[:6])}}


def _verify_claims(ctx: Ctx) -> dict:
    """Numbers in a text are matched against measured runs; anything without a matching run stays unsupported."""
    from backend.execution.sandbox import list_runs as sb_runs
    text = ctx.run["inputs"].get("text") or ctx.prior("research").get("text") or ""
    if not text and ctx.run["inputs"].get("path"):
        from backend.core.config import data_dir
        p = (data_dir() / ctx.run["inputs"]["path"]).resolve()
        if data_dir().resolve() in p.parents and p.is_file():
            text = p.read_text("utf-8", "replace")
    measured = []
    for r in sb_runs(200):
        for k, v in valid_metrics(r.get("metrics") or {}).items():
            measured.append((r["id"], k, float(v)))
    claims = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        nums = [float(x.replace(",", ".")) for x in re.findall(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s?%?", sent)]
        nums = [n for n in nums if not (1900 <= n <= 2100)]
        if not nums:
            continue
        support = [{"run": rid, "metric": k, "value": v} for rid, k, v in measured
                   for n in nums if abs(n - v) < 1e-6 or abs(n - v * 100) < 0.05 or abs(n - v) <= abs(v) * 0.001]
        claims.append({"claim": sent.strip()[:400], "status": "supported" if support else "unsupported", "evidence": support[:5]})
    sup = sum(1 for c in claims if c["status"] == "supported")
    lines = [f"# Claim–evidence report ({ctx.rid})", "", f"{sup}/{len(claims)} claims có số liệu khớp với một run đã đo.", ""]
    lines += [f"- **{c['status'].upper()}** — {c['claim']}" + (f"  ← {c['evidence'][0]['run']} {c['evidence'][0]['metric']}"
                                                                if c["evidence"] else "") for c in claims]
    ref = ctx.write("claim_evidence_report.md", "\n".join(lines))
    return {"outputs": [ref], "result": {"claims": len(claims), "supported": sup, "items": claims[:200],
                                         "summary_line": f"{sup}/{len(claims)} claim có bằng chứng đo được"}}


def _review(ctx: Ctx) -> dict:
    text = ctx.run["inputs"].get("text") or ""
    if ctx.step["spec"].get("review_prior"):
        text = ctx.prior("research").get("text") or ""
    if not text and ctx.run["inputs"].get("path"):
        from backend.core.config import data_dir
        p = (data_dir() / ctx.run["inputs"]["path"]).resolve()
        if data_dir().resolve() not in p.parents or not p.is_file():
            raise StepFailure("file to review not found in the project", "input")
        text = p.read_text("utf-8", "replace")
    if not text:
        from backend.paper.writer import assemble, load_project
        if any((load_project().get("sections") or {}).values()):  # the paper written in the chat (/write)
            text = assemble()[0]
    if not text.strip():
        raise StepFailure("nothing to review — write a draft or attach a paper", "input")
    from backend.research_engines.registry import FACTORIES
    if ctx.step["provider"] in FACTORIES:
        ctx.step["spec"].setdefault("workflow", "review")
        ctx.step["spec"].setdefault("topic", "Review this artifact as a strict reviewer:\n\n" + text[:59000])
        return _research(ctx)
    system = ("You are the Reviewer agent of PhD Research Lab: a strict peer reviewer. Assess novelty, methodology, "
              "fairness of baselines, statistics (seeds, CIs), reproducibility and citation consistency. For each issue: "
              "severity (major/minor), location, why, concrete fix. Never invent facts about the paper.\n\n" + _skill_text(ctx))
    rep = _llm("reviewer", system, text[:60000])
    ref = ctx.write("review_report.md", rep)
    return {"outputs": [ref], "result": {"text": rep[:20000], "summary_line": "đã có báo cáo phản biện"}}


def _latex(ctx: Ctx) -> dict:
    from backend.paper.latex import compile_pdf
    r = compile_pdf()
    if not r.get("ok"):
        raise StepFailure("LaTeX: " + "; ".join(e.get("message", "") if isinstance(e, dict) else str(e)
                                                 for e in (r.get("errors") or [])[:3])[:400], "latex")
    return {"outputs": ["workspace/build/main.pdf"], "result": {"engine": r.get("engine"), "pages": r.get("pages"),
                                                                "summary_line": f"PDF ({r.get('engine')})"}}


def _report(ctx: Ctx) -> dict:
    r = get(ctx.rid)
    lines = [s["result"].get("summary_line") for s in r["steps"] if s["status"] == "done" and s["result"].get("summary_line")]
    m = ctx.prior("verify_metrics")
    body = "\n".join(f"- {x}" for x in lines)
    if r.get("synthetic"):
        body = "**SYNTHETIC — mô phỏng.**\n" + body
    ref = ctx.write("report.md", f"# {r['title']}\n\n{body}\n")
    _propose_pins(r, m, ctx)
    return {"outputs": [ref], "result": {"summary": body}}


def _propose_pins(r: dict, m: dict, ctx: Ctx) -> None:
    """Results become proposals in the conversation: the researcher accepts (pin) or rejects them."""
    sid = r.get("session_id")
    if not sid:
        return
    from backend.agent import sessions
    props = []
    if m.get("metrics"):
        props.append({"name": "pin_result", "args": {"kind": "result", "title": f"{r['title'][:100]} — {m['label']}",
                                                     "body": ", ".join(f"{k}={v:g}" for k, v in m["metrics"].items())[:3000],
                                                     "run_id": m.get("job_id", ""), "research_run": r["id"]}})
    rep = ctx.prior("research") or ctx.prior("review")
    if rep.get("text"):
        props.append({"name": "pin_result", "args": {"kind": "note" if r["pipeline"] == "review" else "source",
                                                     "title": r["title"][:120], "body": rep["text"][:3000],
                                                     "run_id": "", "research_run": r["id"]}})
    for p in props:
        ap = {"id": new_id("ap", 4), "turn_id": r.get("turn_id", ""), "kind": "action", "name": p["name"], "args": p["args"],
              "risk": 1, "status": "pending", "created": now(), "reason": f"kết quả của run {r['id']}"}
        try:
            sessions.update(sid, lambda x, ap=ap: x["approvals"].append(ap))
            sessions.emit(sid, "action.approval_required", r.get("turn_id", ""), approval=ap["id"], action=ap["name"], risk=1)
        except AIWSError:
            return


EXECUTORS.update({"research": _research, "verify_sources": _verify_sources, "plan": _plan, "code": _code,
                  "experiment": _experiment, "verify_metrics": _verify_metrics, "verify_claims": _verify_claims,
                  "review": _review, "latex": _latex, "report": _report})


def reset_memory() -> None:
    """Tests / project switch: forget in-process buffers (files stay)."""
    with _lock:
        _buf.clear()
        _seq.clear()

