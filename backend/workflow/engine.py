"""Workflow Orchestrator (v4.1 M2): registry → validation → state machine → step router, with approvals, budgets,
pause/resume/cancel, recovery after a restart, nested workflows and a normalised event stream.

Run states   CREATED → VALIDATING → READY → RUNNING ⇄ WAITING_FOR_APPROVAL / PAUSED → SUCCEEDED | FAILED | CANCELLED |
             BUDGET_EXCEEDED
Step states  PENDING → READY → RUNNING → (WAITING_FOR_APPROVAL) → SUCCEEDED | FAILED | SKIPPED | CANCELLED

Gates (who decides): a step waits BEFORE it runs when its mode is manual, its type always needs approval, or the
workflow's approval policy requires it (approvals.<key>); it waits AFTER it ran when its mode is assisted or its type has
an after-gate (e.g. conclusions). The researcher can Approve, Edit (params before / output after), Revise (re-run an
agent step with feedback) or Reject. Human steps (approval / input) always wait.

Budgets are a ledger on the ROOT run (shared by nested runs): trials, workflow cycles, agent calls, runtime. A budget
that runs out stops the run (BUDGET_EXCEEDED) — it is never silently extended.

Recovery: on start-up, runs that were RUNNING become PAUSED; an interrupted idempotent step is retried, a resumable
one (HPO study) continues from its checkpoint, any other step waits for the researcher ("interrupted — run again?").
Completed steps are never re-run.

Persistence: <project>/workflows/runs/<id>.json (+ <id>.events.jsonl). Events never contain secrets or raw context.
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
import secrets
import time
from pathlib import Path

from . import schema as S
from . import steps as ST
from . import templates as TP

RUN_RE = re.compile(r"^wf-[0-9a-f]{10}$")
EVENT_TYPES = ("workflow_created", "workflow_started", "step_started", "step_progress", "step_completed", "step_failed",
               "step_skipped", "approval_required", "approval_resolved", "plan_updated", "study_created", "trial_started",
               "trial_pruned", "trial_completed", "trial_failed", "evaluation_completed", "verification_completed",
               "workflow_paused", "workflow_resumed", "workflow_completed", "workflow_failed", "workflow_cancelled",
               "budget_exceeded")
MAX_EVENTS_MEM = 2000


class OrchestratorError(ValueError):
    pass


class BudgetExceeded(Exception):
    pass


def _runs_dir() -> Path:
    from ..config import data_dir
    d = data_dir() / "workflows" / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cfg() -> dict:
    from ..config import load_config
    return load_config()


class StepContext:
    """What a step handler may use — nothing else of the orchestrator is reachable from a step."""

    def __init__(self, orch: "Orchestrator", run: dict, step: dict, params: dict):
        self.orch, self.run, self.step, self.params = orch, run, step, params
        self.state = step.setdefault("checkpoint", {})
        self.budgets = orch.root(run)["budgets"]
        self._cancel_fns: list = []

    def emit(self, type_: str, **data) -> None:
        self.orch.emit(self.run, type_, step_id=self.step["id"], **data)

    def save(self) -> None:
        self.orch.persist(self.run)

    def should_stop(self) -> bool:
        rt = self.orch.rt(self.run["id"])
        return rt["cancel"] or rt["pause"] or self.orch.runtime_exceeded(self.run)

    def on_cancel(self, fn) -> None:
        self._cancel_fns.append(fn)

    def reserve_trials(self, n: int) -> int:
        return self.orch.reserve(self.run, "trials_used", "max_trials", n)

    def reserve_cycle(self) -> bool:
        return self.orch.reserve(self.run, "cycles_used", "max_workflow_cycles", 1) == 1

    def reserve_agent_call(self) -> None:
        if self.orch.reserve(self.run, "agent_calls", "max_agent_calls", 1) != 1:
            raise BudgetExceeded("agent-call budget exhausted (budgets.max_agent_calls)")


class Orchestrator:
    def __init__(self):
        self.runs: dict = {}      # id → run record (loaded lazily, cached)
        self._rt: dict = {}       # id → runtime flags {cancel, pause, task, changed(asyncio.Event), steps{sid: task}}
        self.events: dict = {}    # id → recent events (SSE)
        self._recovered: set = set()

    # ------------------------------------------------------------------ registry & validation
    def validate(self, defn: dict) -> tuple[dict, list]:
        cfg = _cfg()
        d, errs = S.validate(defn, ST.REGISTRY, cfg["workflow"], cfg["features"])
        if not errs:
            errs = TP.call_graph_ok(d)
        return d, errs

    # ------------------------------------------------------------------ runtime helpers
    def rt(self, rid: str) -> dict:
        if rid not in self._rt:
            self._rt[rid] = {"cancel": False, "pause": False, "task": None, "steps": {}, "cancel_fns": {}, "changed": None}
        return self._rt[rid]

    def _changed(self, rid: str) -> asyncio.Event:
        rt = self.rt(rid)
        if rt["changed"] is None:
            rt["changed"] = asyncio.Event()
        return rt["changed"]

    def persist(self, run: dict) -> None:
        from ..memory.store import replace_retry
        p = _runs_dir() / f"{run['id']}.json"
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(run, indent=1, default=str), "utf-8")
        replace_retry(tmp, p)

    def emit(self, run: dict, type_: str, **data) -> None:
        if type_ not in EVENT_TYPES or set(data) & {"seq", "ts", "type", "run_id"}:
            raise OrchestratorError(f"unknown event type {type_} or reserved field")
        run["seq"] = run.get("seq", 0) + 1
        ev = {"seq": run["seq"], "ts": round(time.time(), 3), "type": type_, "run_id": run["id"],
              **{k: v for k, v in data.items() if v is not None}}
        buf = self.events.setdefault(run["id"], [])
        buf.append(ev)
        del buf[:-MAX_EVENTS_MEM]
        try:
            with open(_runs_dir() / f"{run['id']}.events.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, default=str) + "\n")
        except OSError:  # pragma: no cover
            pass
        try:
            self._changed(run["id"]).set()
        except RuntimeError:  # pragma: no cover - no event loop (sync API use)
            pass
        if run.get("parent"):
            try:
                self._changed(run["parent"]["run_id"]).set()
            except (RuntimeError, KeyError):  # pragma: no cover
                pass

    def get(self, rid: str) -> dict:
        if not RUN_RE.match(rid or ""):
            raise OrchestratorError("invalid run id")
        if rid in self.runs:
            return self.runs[rid]
        p = _runs_dir() / f"{rid}.json"
        if not p.exists():
            raise OrchestratorError("run not found")
        run = json.loads(p.read_text("utf-8"))
        self.runs[rid] = run
        self._recover(run)
        return run

    def root(self, run: dict) -> dict:
        r = run
        while r.get("parent"):
            r = self.get(r["parent"]["run_id"])
        return r

    def runtime_exceeded(self, run: dict) -> bool:
        root = self.root(run)
        lim = float(root["budgets"].get("max_runtime_minutes") or 0)
        return bool(lim and root.get("started") and time.time() - root["started"] > lim * 60 + root.get("paused_s", 0))

    def reserve(self, run: dict, used_key: str, budget_key: str, n: int) -> int:
        root = self.root(run)
        cap = int(root["budgets"].get(budget_key) or 0)
        led = root.setdefault("ledger", {})
        used = int(led.get(used_key, 0))
        allowed = max(0, min(n, cap - used)) if cap else n
        led[used_key] = used + allowed
        self.persist(root)
        return allowed

    # ------------------------------------------------------------------ create
    def create(self, workflow_id: str = "", definition: dict | None = None, inputs: dict | None = None,
               overrides: dict | None = None, version: int | None = None, parent: dict | None = None) -> dict:
        cfg = _cfg()
        if not cfg["features"].get("workflow_orchestrator", True):
            raise OrchestratorError("the workflow orchestrator is switched off (features.workflow_orchestrator)")
        if definition is None:
            definition = TP.get(workflow_id, version)
            if definition is None:
                raise OrchestratorError(f"unknown workflow '{workflow_id}'")
        defn = copy.deepcopy(definition)
        ov = overrides or {}
        if ov.get("execution_mode"):
            defn["execution_mode"] = ov["execution_mode"]
        if ov.get("budgets"):
            defn["budgets"] = {**(defn.get("budgets") or {}), **ov["budgets"]}
        if ov.get("approvals"):
            defn["approvals"] = {**(defn.get("approvals") or {}), **ov["approvals"]}
        for sid, m in (ov.get("step_modes") or {}).items():
            for s in defn.get("steps", []):
                if s.get("id") == sid:
                    s["mode"] = m
        rid = "wf-" + secrets.token_hex(5)
        run = {"id": rid, "status": "VALIDATING", "created": time.time(), "workflow_id": defn.get("id"),
               "version": defn.get("version"), "name": defn.get("name"), "parent": parent, "seq": 0}
        d, errs = self.validate(defn)
        given, ierrs = S.check_inputs(d, inputs or {}) if not errs else ({}, [])
        errs += ierrs
        if errs:
            raise OrchestratorError("invalid workflow: " + "; ".join(errs[:12]))
        run.update(definition=d, inputs=given, execution_mode=d["execution_mode"], budgets=d["budgets"],
                   approvals=d["approvals"], failure_policy=d["failure_policy"], ledger={}, outputs={}, error="",
                   children=[], paused_s=0.0)
        run["steps"] = {s["id"]: {"id": s["id"], "type": s["type"], "label": s["label"], "mode": self._mode(run, s),
                                  "status": "PENDING", "attempts": 0, "depends_on": s["depends_on"], "output": None,
                                  "error": "", "warnings": [], "approval": None, "started": None, "ended": None,
                                  "provided_by": "", "params_patch": {}}
                        for s in d["steps"]}
        run["order"] = [s["id"] for s in d["steps"]]
        run["status"] = "READY"
        self.runs[rid] = run
        self.persist(run)
        self.emit(run, "workflow_created", workflow_id=d["id"], version=d["version"], mode=d["execution_mode"],
                  parent=(parent or {}).get("run_id"))
        return run

    def _mode(self, run: dict, sdef: dict) -> str:
        t = ST.REGISTRY[sdef["type"]]
        if t.kind == "human":
            return "manual"
        return sdef.get("mode") or S.default_step_mode(run["execution_mode"], t.kind, t.risk)

    def _gates(self, run: dict, sid: str) -> tuple[bool, bool]:
        st = run["steps"][sid]
        t = ST.REGISTRY[st["type"]]
        ap = self.root(run)["approvals"] | {k: v for k, v in run["approvals"].items() if v == "required"}
        sdef = self._sdef(run, sid)
        before = st["mode"] == "manual" or t.always_approve or bool(t.approval_key and ap.get(t.approval_key) == "required")
        if st["type"] == "hpo.run" and int((sdef.get("params") or {}).get("parallel") or 1) > 1 and \
                ((sdef.get("params") or {}).get("objective") or {}).get("gpu") and ap.get("before_parallel_gpu_trials") == "required":
            before = True
        after = st["mode"] == "assisted" or bool(t.after_key and ap.get(t.after_key) == "required")
        return before, after

    def _sdef(self, run: dict, sid: str) -> dict:
        return next(s for s in run["definition"]["steps"] if s["id"] == sid)

    def _scope(self, run: dict) -> dict:
        return {"inputs": run["inputs"], "steps": {k: {"status": v["status"], "output": v["output"]} for k, v in run["steps"].items()}}

    # ------------------------------------------------------------------ control
    def start(self, rid: str) -> dict:
        run = self.get(rid)
        if run["status"] not in ("READY", "PAUSED", "WAITING_FOR_APPROVAL", "RUNNING"):
            raise OrchestratorError(f"run is {run['status']}")
        rt = self.rt(rid)
        if run["status"] == "PAUSED":
            if run.get("paused_at"):
                run["paused_s"] = run.get("paused_s", 0) + time.time() - run.pop("paused_at")
            rt["pause"] = False
            self.emit(run, "workflow_resumed")
        if not run.get("started"):
            run["started"] = time.time()
            self.emit(run, "workflow_started")
        run["status"] = "RUNNING"
        self.persist(run)
        self._kick(rid)
        return self.public(run)

    def _kick(self, rid: str) -> None:
        rt = self.rt(rid)
        if rt["task"] is None or rt["task"].done():
            rt["task"] = asyncio.get_running_loop().create_task(self._drive(rid))

    def pause(self, rid: str) -> dict:
        run = self.get(rid)
        if run["status"] in S.TERMINAL_RUN:
            raise OrchestratorError(f"run is {run['status']}")
        self.rt(rid)["pause"] = True
        if not self._running_steps(run):
            self._set_paused(run)
        for c in run.get("children", []):
            try:
                self.pause(c)
            except OrchestratorError:
                pass
        return self.public(run)

    def _set_paused(self, run: dict) -> None:
        if run["status"] != "PAUSED":
            run["status"] = "PAUSED"
            run["paused_at"] = time.time()
            self.persist(run)
            self.emit(run, "workflow_paused")

    def cancel(self, rid: str) -> dict:
        run = self.get(rid)
        if run["status"] in S.TERMINAL_RUN:
            raise OrchestratorError(f"run is {run['status']}")
        rt = self.rt(rid)
        rt["cancel"] = True
        for sid, fns in list(rt["cancel_fns"].items()):
            for fn in fns:
                try:
                    fn()
                except Exception:  # pragma: no cover - best effort (job already gone)
                    pass
        for t in list(rt["steps"].values()):
            t.cancel()
        for c in run.get("children", []):
            try:
                self.cancel(c)
            except OrchestratorError:
                pass
        self._finish(run, "CANCELLED", "cancelled by the researcher")
        return self.public(run)

    def decide(self, rid: str, sid: str, decision: str, note: str = "", output: dict | None = None,
               params_patch: dict | None = None, values: dict | None = None) -> dict:
        """Approve / edit / revise / reject a waiting step (or submit a human.input / a manual result)."""
        run = self.get(rid)
        if sid not in run["steps"]:
            raise OrchestratorError("unknown step")
        st = run["steps"][sid]
        if st["status"] != "WAITING_FOR_APPROVAL" or not st.get("approval"):
            raise OrchestratorError(f"step {sid} is {st['status']}, not waiting for a decision")
        if decision not in ("approve", "reject", "revise", "provide"):
            raise OrchestratorError("decision must be approve, reject, revise or provide")
        ap = st["approval"]
        t = ST.REGISTRY[st["type"]]
        phase = ap["phase"]
        rec = {"decision": decision, "note": (note or "")[:2000], "by": "researcher", "at": time.time(), "phase": phase}
        if decision == "reject":
            st["status"], st["error"], st["ended"] = "FAILED", f"rejected by the researcher{': ' + note if note else ''}", time.time()
            self._resolve(run, st, rec)
            self._on_step_failed(run, sid)
        elif decision == "revise":
            if t.kind != "agent":
                raise OrchestratorError("revise re-runs an agent step with your feedback; use edit/approve for this step")
            st["params_patch"] = {**st.get("params_patch", {}), "feedback": (note or "")[:2000]}
            st["status"], st["approval"], st["output"] = "READY", None, None
            st["gate_before_done"] = True
            self._resolve(run, st, rec)
            self.emit(run, "plan_updated", step_id=sid, note=(note or "")[:200])
        elif t.kind == "human":
            out = {"approved": True, "note": rec["note"]} if st["type"] == "human.approval" else dict(values or output or {})
            st.update(status="SUCCEEDED", output=out, ended=time.time(), provided_by="researcher")
            self._resolve(run, st, rec)
            self.emit(run, "step_completed", step_id=sid)
        elif phase == "before":
            if decision == "provide":  # the researcher did it by hand: the result is theirs
                st.update(status="SUCCEEDED", output=dict(output or {}), ended=time.time(), provided_by="researcher")
                self._resolve(run, st, rec)
                self.emit(run, "step_completed", step_id=sid, provided_by="researcher")
            else:
                if params_patch:
                    allowed = set(t.params)
                    bad = set(params_patch) - allowed
                    if bad:
                        raise OrchestratorError(f"unknown params {', '.join(sorted(bad))}")
                    st["params_patch"] = {**st.get("params_patch", {}), **params_patch}
                    rec["edited_params"] = sorted(params_patch)
                st["status"], st["approval"], st["gate_before_done"] = "READY", None, True
                self._resolve(run, st, rec)
        else:  # after: accept the (possibly edited) result
            final = output if output is not None else st["output"]
            if t.check_output:
                errs = t.check_output(final)
                if errs:
                    raise OrchestratorError("the result is not valid yet: " + "; ".join(errs[:6]))
            if output is not None:
                rec["edited_output"] = True
            st.update(status="SUCCEEDED", output=final, ended=time.time())
            self._resolve(run, st, rec)
            self.emit(run, "step_completed", step_id=sid, edited=output is not None)
        if run["status"] == "WAITING_FOR_APPROVAL":
            run["status"] = "RUNNING"
        self.persist(run)
        if run["status"] == "RUNNING":
            self._kick(rid)
        return self.public(run)

    def _resolve(self, run: dict, st: dict, rec: dict) -> None:
        run.setdefault("approval_history", []).append({"step_id": st["id"], **rec})
        if st.get("approval"):
            st["approval"]["resolution"] = rec
        st["approval"] = None if st["status"] == "READY" else st.get("approval")
        self.emit(run, "approval_resolved", step_id=st["id"], decision=rec["decision"], phase=rec["phase"])

    # ------------------------------------------------------------------ the driver
    def _running_steps(self, run: dict) -> list:
        return [s for s in run["steps"].values() if s["status"] == "RUNNING"]

    async def _drive(self, rid: str) -> None:
        run = self.get(rid)
        rt = self.rt(rid)
        try:
            while True:
                if rt["cancel"] or run["status"] in S.TERMINAL_RUN:
                    return
                if self.runtime_exceeded(run):
                    await self._stop_all(run)
                    self._finish(run, "BUDGET_EXCEEDED", "runtime budget (max_runtime_minutes) exhausted")
                    return
                progressed = self._schedule(run)
                running = [t for t in rt["steps"].values() if not t.done()]
                if not running:
                    if rt["pause"]:
                        self._set_paused(run)
                        return
                    if not progressed:
                        break
                    continue
                waiter = asyncio.ensure_future(self._changed(rid).wait())
                try:
                    await asyncio.wait(running + [waiter], timeout=5, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    waiter.cancel()
                self._changed(rid).clear()
            self._settle(run)
        except Exception as e:  # pragma: no cover - the driver must never die silently
            self._finish(run, "FAILED", f"orchestrator error: {type(e).__name__}: {e}")

    def _schedule(self, run: dict) -> bool:
        """Advance every step that can move; start runnable ones. True when something changed."""
        rt = self.rt(run["id"])
        progressed = False
        scope = self._scope(run)
        exec_running = sum(1 for sid, t in rt["steps"].items() if not t.done()
                           and ST.REGISTRY[run["steps"][sid]["type"]].kind == "execution")
        for sid in run["order"]:
            st = run["steps"][sid]
            if st["status"] not in ("PENDING", "READY"):
                continue
            deps = [run["steps"][d]["status"] for d in st["depends_on"]]
            if any(d in ("FAILED", "CANCELLED") for d in deps) or any(run["steps"][d].get("skip_cascade") for d in st["depends_on"]):
                st.update(status="SKIPPED", ended=time.time(), error="an upstream step did not succeed", skip_cascade=True)
                self.emit(run, "step_skipped", step_id=sid, reason="upstream failed")
                progressed = True
                continue
            if not all(d in ("SUCCEEDED", "SKIPPED") for d in deps):
                continue
            sdef = self._sdef(run, sid)
            try:
                go = S.evaluate(sdef.get("when"), scope)
            except S.WorkflowError as e:  # pragma: no cover - validated earlier
                go, st["error"] = False, str(e)
            if not go:
                st.update(status="SKIPPED", ended=time.time(), error="condition not met")
                self.emit(run, "step_skipped", step_id=sid, reason="condition not met")
                progressed = True
                continue
            if rt["pause"]:
                continue
            t = ST.REGISTRY[st["type"]]
            before, _ = self._gates(run, sid)
            if t.kind == "human" or (before and not st.get("gate_before_done")):
                self._wait(run, st, "before" if t.kind != "human" else "input",
                           S.resolve((sdef.get("params") or {}).get("show"), scope) if t.kind == "human" else None)
                progressed = True
                continue
            if t.kind == "execution" and exec_running >= 1:
                continue  # one execution step at a time (sandbox / GPU)
            exec_running += t.kind == "execution"
            st["status"], st["started"] = "RUNNING", time.time()
            st["attempts"] += 1
            self.emit(run, "step_started", step_id=sid, step_type=st["type"], attempt=st["attempts"])
            rt["steps"][sid] = asyncio.ensure_future(self._exec(run, sid))
            progressed = True
        self.persist(run)
        return progressed

    def _wait(self, run: dict, st: dict, phase: str, show=None) -> None:
        if st["status"] == "WAITING_FOR_APPROVAL":
            return
        t = ST.REGISTRY[st["type"]]
        sdef = self._sdef(run, st["id"])
        st["status"] = "WAITING_FOR_APPROVAL"
        st["approval"] = {"phase": phase, "requested": time.time(), "reason": self._why(run, st, phase),
                          "question": (sdef.get("params") or {}).get("question") or (sdef.get("params") or {}).get("prompt") or "",
                          "fields": (sdef.get("params") or {}).get("fields"), "show": show, "risk": t.risk,
                          "planned_params": None if phase != "before" else self._params(run, st["id"]),
                          "budget_left": self.budget_left(run)}
        self.emit(run, "approval_required", step_id=st["id"], phase=phase, reason=st["approval"]["reason"])

    def _why(self, run: dict, st: dict, phase: str) -> str:
        t = ST.REGISTRY[st["type"]]
        if t.kind == "human":
            return "a researcher decision is part of this workflow"
        if phase == "after":
            return "result needs review (assisted step)" if st["mode"] == "assisted" else f"policy gate {t.after_key}"
        if t.always_approve:
            return "this step type always needs approval"
        if st["mode"] == "manual":
            return "manual step: you run it (or provide the result)"
        return f"approval policy: {t.approval_key}"

    def budget_left(self, run: dict) -> dict:
        root = self.root(run)
        b, led = root["budgets"], root.get("ledger", {})
        el = (time.time() - root["started"] - root.get("paused_s", 0)) / 60 if root.get("started") else 0
        return {"trials": (b["max_trials"] - led.get("trials_used", 0)) if b.get("max_trials") else None,
                "cycles": (b["max_workflow_cycles"] - led.get("cycles_used", 0)) if b.get("max_workflow_cycles") else None,
                "agent_calls": (b["max_agent_calls"] - led.get("agent_calls", 0)) if b.get("max_agent_calls") else None,
                "runtime_min": round(b["max_runtime_minutes"] - el, 1) if b.get("max_runtime_minutes") else None}

    def _params(self, run: dict, sid: str) -> dict:
        sdef = self._sdef(run, sid)
        p = S.resolve(sdef.get("params") or {}, self._scope(run))
        p.update(run["steps"][sid].get("params_patch") or {})
        return p

    async def _exec(self, run: dict, sid: str) -> None:
        st = run["steps"][sid]
        t = ST.REGISTRY[st["type"]]
        rt = self.rt(run["id"])
        ctx = StepContext(self, run, st, self._params(run, sid))
        rt["cancel_fns"][sid] = ctx._cancel_fns
        sdef = self._sdef(run, sid)
        try:
            coro = t.handler(ctx)
            out = await (asyncio.wait_for(coro, sdef["timeout_s"]) if sdef.get("timeout_s") else coro)
            if rt["cancel"]:
                return
            _, after = self._gates(run, sid)
            errs = t.check_output(out) if t.check_output else []
            if errs and not after:
                raise ST.StepFailed("invalid result: " + "; ".join(errs[:6]))
            st["output"] = out
            st["warnings"] = errs
            if after:
                st["ended"] = time.time()
                self._wait(run, st, "after", out)
            else:
                st.update(status="SUCCEEDED", ended=time.time())
                self.emit(run, "step_completed", step_id=sid)
                if st["type"].startswith("evaluation."):
                    self.emit(run, "evaluation_completed", step_id=sid)
                elif st["type"] == "verification.check":
                    self.emit(run, "verification_completed", step_id=sid, passed=out.get("passed"))
                elif st["type"] == "agent.plan":
                    self.emit(run, "plan_updated", step_id=sid)
        except ST.StepPaused:
            st["status"] = "READY"
            st["gate_before_done"] = True  # its gate was passed already; resume continues the checkpoint
            self.emit(run, "step_progress", step_id=sid, note="paused at a checkpoint")
        except asyncio.CancelledError:
            st.update(status="CANCELLED", ended=time.time(), error="cancelled")
        except BudgetExceeded as e:
            st.update(status="FAILED", ended=time.time(), error=str(e))
            self.emit(run, "budget_exceeded", step_id=sid, detail=str(e))
            self._finish(self.root(run), "BUDGET_EXCEEDED", str(e))
            if run is not self.root(run):
                self._finish(run, "BUDGET_EXCEEDED", str(e))
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"[:800] if not isinstance(e, (ST.StepFailed, asyncio.TimeoutError)) else \
                (str(e) or f"timed out after {sdef.get('timeout_s')} s")[:800]
            if st["attempts"] <= int(sdef["retry"]["max"]) and not rt["cancel"]:
                st.update(status="READY", error=msg, gate_before_done=True)
                self.emit(run, "step_progress", step_id=sid, note=f"retrying after: {msg[:200]}")
            else:
                st.update(status="FAILED", ended=time.time(), error=msg)
                self.emit(run, "step_failed", step_id=sid, error=msg[:300])
                self._on_step_failed(run, sid)
        finally:
            rt["cancel_fns"].pop(sid, None)
            self.persist(run)
            self._changed(run["id"]).set()

    def _on_step_failed(self, run: dict, sid: str) -> None:
        if run["failure_policy"] == "fail_fast":
            for t in list(self.rt(run["id"])["steps"].values()):
                if not t.done():
                    t.cancel()
            self._finish(run, "FAILED", f"step {sid} failed: {run['steps'][sid]['error']}")

    async def _stop_all(self, run: dict) -> None:
        for t in list(self.rt(run["id"])["steps"].values()):
            if not t.done():
                t.cancel()
        await asyncio.sleep(0)

    def _settle(self, run: dict) -> None:
        if run["status"] in S.TERMINAL_RUN:
            return
        states = [s["status"] for s in run["steps"].values()]
        if any(s == "WAITING_FOR_APPROVAL" for s in states):
            if run["status"] != "WAITING_FOR_APPROVAL":
                run["status"] = "WAITING_FOR_APPROVAL"
                self.persist(run)
                self._changed(run["id"]).set()
            return
        if any(s in ("PENDING", "READY") for s in states):  # pragma: no cover - blocked only by a pause
            return
        if any(s == "FAILED" for s in states):
            bad = [k for k, v in run["steps"].items() if v["status"] == "FAILED"]
            self._finish(run, "FAILED", f"failed steps: {', '.join(bad)}")
            return
        scope = self._scope(run)
        run["outputs"] = {k: S.resolve_ref(r, scope) for k, r in run["definition"].get("outputs", {}).items()}
        self._finish(run, "SUCCEEDED", "")

    def _finish(self, run: dict, status: str, error: str) -> None:
        if run["status"] in S.TERMINAL_RUN:
            return
        run["status"], run["ended"] = status, time.time()
        run["error"] = error
        for st in run["steps"].values():
            if st["status"] in ("PENDING", "READY", "WAITING_FOR_APPROVAL") and status != "SUCCEEDED":
                st["status"] = "CANCELLED" if status == "CANCELLED" else "SKIPPED"
                st["approval"] = None
        self.persist(run)
        self.emit(run, {"SUCCEEDED": "workflow_completed", "FAILED": "workflow_failed", "CANCELLED": "workflow_cancelled",
                        "BUDGET_EXCEEDED": "budget_exceeded"}[status], error=error or None)

    # ------------------------------------------------------------------ nested workflows
    async def run_child(self, ctx: StepContext, workflow_id: str, inputs: dict, version: int | None,
                        key: str = "child") -> dict:
        """Run (or, after a pause / restart, continue) a nested workflow; returns its declared outputs + child_run_id.
        The child inherits the parent's execution mode (unless the parent is custom) and every REQUIRED approval of
        the root; its trials, cycles and agent calls are charged to the root's ledger."""
        parent = ctx.run
        child = None
        if ctx.state.get(key):
            try:
                child = self.get(ctx.state[key])
            except OrchestratorError:  # pragma: no cover - deleted run file
                child = None
        if child is None:
            child_def = TP.get(workflow_id, version)
            if child_def is None:
                raise ST.StepFailed(f"unknown workflow '{workflow_id}'")
            ov = {"approvals": {k: "required" for k, v in self.root(parent)["approvals"].items() if v == "required"}}
            if parent["execution_mode"] != "custom":
                ov["execution_mode"] = parent["execution_mode"]
            try:
                child = self.create(definition=child_def, inputs=inputs, overrides=ov,
                                    parent={"run_id": parent["id"], "step_id": ctx.step["id"]})
            except OrchestratorError as e:
                raise ST.StepFailed(str(e))
            parent.setdefault("children", []).append(child["id"])
            ctx.state[key] = child["id"]
            ctx.save()
        if child["status"] not in S.TERMINAL_RUN:
            self.start(child["id"])
        ctx.on_cancel(lambda: child["status"] not in S.TERMINAL_RUN and self.cancel(child["id"]))
        try:
            while child["status"] not in S.TERMINAL_RUN:
                ev = self._changed(child["id"])
                try:
                    await asyncio.wait_for(ev.wait(), timeout=2)
                except asyncio.TimeoutError:
                    pass
                ev.clear()
                if self.rt(parent["id"])["pause"] and child["status"] == "PAUSED":
                    raise ST.StepPaused(child["id"])
        except asyncio.CancelledError:
            if child["status"] not in S.TERMINAL_RUN:
                self.cancel(child["id"])
            raise
        if child["status"] != "SUCCEEDED":
            raise ST.StepFailed(f"nested workflow {workflow_id} ({child['id']}) ended {child['status']}: {child.get('error', '')}")
        return {**child["outputs"], "child_run_id": child["id"]}

    # ------------------------------------------------------------------ recovery & listing
    def _recover(self, run: dict) -> None:
        if run["id"] in self._recovered:
            return
        self._recovered.add(run["id"])
        if run["status"] not in ("RUNNING", "WAITING_FOR_APPROVAL"):
            return
        changed = False
        for st in run["steps"].values():
            if st["status"] != "RUNNING":
                continue
            t = ST.REGISTRY[st["type"]]
            changed = True
            if t.idempotent or t.resumable:
                st.update(status="READY", gate_before_done=True, error="interrupted by an app restart — continues on resume")
            else:
                st.update(status="WAITING_FOR_APPROVAL", gate_before_done=False,
                          approval={"phase": "before", "requested": time.time(), "risk": t.risk, "question": "",
                                    "reason": "interrupted by an app restart: this step is not safe to repeat automatically — "
                                              "run it again?", "show": None, "planned_params": None})
        if run["status"] == "RUNNING" or changed:
            run["status"] = "PAUSED"
            run["paused_at"] = time.time()
            run["recovered"] = True
            self.persist(run)

    def list(self, limit: int = 50) -> list:
        out = []
        for p in sorted(_runs_dir().glob("wf-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                r = self.get(p.stem)
            except (OrchestratorError, ValueError, OSError):
                continue
            out.append(self.summary(r))
        return out

    def summary(self, r: dict) -> dict:
        return {k: r.get(k) for k in ("id", "workflow_id", "version", "name", "status", "execution_mode", "created", "started",
                                      "ended", "error", "parent")} | {
            "steps_done": sum(s["status"] in S.TERMINAL_STEP for s in r["steps"].values()), "steps": len(r["steps"]),
            "waiting": [k for k, s in r["steps"].items() if s["status"] == "WAITING_FOR_APPROVAL"]}

    def public(self, r: dict) -> dict:
        out = {k: v for k, v in r.items() if k != "definition"}
        out["steps"] = [r["steps"][sid] for sid in r["order"]]
        out["budget_left"] = self.budget_left(r)
        out["pending_approvals"] = self.pending(r)
        out["definition_id"] = (r.get("definition") or {}).get("id")
        return out

    def pending(self, r: dict) -> list:
        """Waiting decisions of this run and of its nested runs (so the parent view shows them)."""
        out = [{"run_id": r["id"], "step_id": k, "label": s["label"], "phase": (s["approval"] or {}).get("phase")}
               for k, s in r["steps"].items() if s["status"] == "WAITING_FOR_APPROVAL"]
        for c in r.get("children", []):
            try:
                out += self.pending(self.get(c))
            except OrchestratorError:  # pragma: no cover
                pass
        return out

    def events_since(self, rid: str, after: int = 0) -> list:
        run = self.get(rid)
        buf = self.events.get(rid)
        if buf is None or (buf and buf[0]["seq"] > after + 1):
            try:
                lines = (_runs_dir() / f"{rid}.events.jsonl").read_text("utf-8").splitlines()
                buf = [json.loads(l) for l in lines if l.strip()][-MAX_EVENTS_MEM:]
                self.events[rid] = buf
            except (OSError, ValueError):
                buf = []
        del run
        return [e for e in buf if e["seq"] > after]

    async def wait_change(self, rid: str, timeout: float = 15) -> None:
        ev = self._changed(rid)
        try:
            await asyncio.wait_for(ev.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        ev.clear()

    def reset(self) -> None:
        """Tests: forget cached runs (files stay)."""
        for rt in self._rt.values():
            for t in list(rt["steps"].values()) + [rt["task"]]:
                try:
                    if t is not None:
                        t.cancel()
                except RuntimeError:  # the task's event loop is already closed
                    pass
        self.runs.clear()
        self._rt.clear()
        self.events.clear()
        self._recovered.clear()


ORCH = Orchestrator()
