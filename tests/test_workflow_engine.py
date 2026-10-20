"""v4.1 Workflow Orchestrator: modes (manual / assisted / bounded / custom), gates (approve / edit / revise / reject /
provide), budgets, retries, timeouts, conditions, pause / resume / cancel, recovery after restart, nested workflows,
every step type, templates and the harness adapter. Acceptance scenarios A–H of the v4.1 prompt are covered here.
The harness (LLM) and sandbox jobs are faked; orchestration, validation, HPO and persistence are the real code."""
import _env  # noqa: F401  (must be first)
import asyncio
import json
import time
import unittest
from unittest import mock

from backend import config
from backend.workflow import ORCH, OrchestratorError, engine as EN, harness as HA, hpo as H, steps as ST, templates as TP


class FakeHarness(HA.Harness):
    name = "fake"

    def __init__(self):
        self.calls = []

    async def plan(self, objective, context, constraints):
        self.calls.append(("plan", objective))
        return {"objective": objective, "steps": [{"title": "analyse"}], "label": HA.AI_SUGGESTION}

    async def propose_search_space(self, model_report, baseline, hint, failures):
        self.calls.append(("space", hint))
        if "invalid" in hint:
            return {"search_space": {"lr": {"type": "float", "low": 1, "high": 0}}, "rationale": "bad"}
        return {"search_space": {"x": {"type": "float", "low": -1, "high": 1}, "y": {"type": "float", "low": -1, "high": 1}},
                "rationale": "two knobs", "_engine": {"engine": "fake"}}

    async def interpret(self, results, hypothesis):
        self.calls.append(("interpret", hypothesis))
        return {"summary": "inconclusive", "supports_hypothesis": "inconclusive", "label": HA.AI_INTERPRETATION}

    async def diagnose(self, failure, similar):
        self.calls.append(("diagnose", failure["category"]))
        return {"diagnosis": "reduce batch size", "confidence": "medium", "label": HA.AI_SUGGESTION}


@ST.step("test.sleep", "deterministic", "low", "test helper", {"s": ("number", False), "fail": ("integer", False),
                                                               "value": ("", False)})
async def _sleep(ctx):
    ctx.on_cancel(lambda: ctx.state.__setitem__("cancel_fn", True))
    await asyncio.sleep(float(ctx.params.get("s") or 0))
    if ctx.params.get("fail") and ctx.step["attempts"] <= ctx.params["fail"]:
        raise RuntimeError("flaky")
    return {"value": ctx.params.get("value", 1), "slept": ctx.params.get("s")}


@ST.step("test.exec", "execution", "low", "test execution helper", {"s": ("number", False)}, idempotent=False)
async def _exec(ctx):
    await asyncio.sleep(float(ctx.params.get("s") or 0))
    return {"ok": True}


class FakeJob:
    def __init__(self, status="done", running=0, metrics=None, out="", err="", exit_code=0):
        self.id, self._status, self.running, self.exit_code = "run-test01", status, running, exit_code
        self.meta = {"metrics": metrics if metrics is not None else {"loss": 0.25}, "environment": {"mode": "local"}, "git": {}}
        self.out, self.err, self.stopped = out, err, False

    @property
    def status(self):
        if self.running > 0:
            self.running -= 1
            return "running"
        return self._status

    def tail(self, n=80, stream=None):
        return self.err if stream == "err" else self.out


def wf(steps, **kw):
    d = {"id": "t_wf", "version": 1, "name": "test", "execution_mode": "bounded", "budgets": {"max_trials": 50, "max_runtime_minutes": 30,
                                                                                          "max_workflow_cycles": 3},
         "approvals": {k: "not_required" for k in ("before_training", "before_parallel_gpu_trials", "before_research_state_writeback",
                                                   "before_conclusion")}, "steps": steps}
    d.update(kw)
    return d


async def until(run, *states, timeout=30):
    t0 = time.time()
    while run["status"] not in states:
        if time.time() - t0 > timeout:
            raise AssertionError(f"run {run['id']} stuck in {run['status']}: " + json.dumps({k: v["status"] for k, v in run["steps"].items()}))
        await asyncio.sleep(0.02)


async def step_state(run, sid, *states, timeout=30):
    t0 = time.time()
    while run["steps"][sid]["status"] not in states:
        if time.time() - t0 > timeout:
            raise AssertionError(f"step {sid} stuck in {run['steps'][sid]['status']}")
        await asyncio.sleep(0.02)


class Base(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("wf-" + self._testMethodName[:30])
        ORCH.reset()
        self.h = FakeHarness()
        HA.use(self.h)
        config.save_config({"features": {"workflow_orchestrator": True, "optuna_hpo": True, "memory_writeback": True,
                                         "experiment_execution": True, "model_intelligence": True, "multi_objective_hpo": True}})

    def tearDown(self):
        ORCH.reset()
        HA.use(None)

    def go(self, coro):
        return asyncio.run(coro)


class Modes(Base):
    def test_bounded_hpo_runs_to_completion(self):
        async def body():
            run = ORCH.create("hpo", inputs={"max_trials": 6}, overrides={"execution_mode": "bounded",
                                                                           "approvals": {"before_training": "not_required"}})
            ORCH.start(run["id"])
            await until(run, "SUCCEEDED", "FAILED")
            return run
        run = self.go(body())
        self.assertEqual(run["status"], "SUCCEEDED", run["error"])
        self.assertEqual(run["ledger"]["trials_used"], 6)
        self.assertIn("loss", run["outputs"]["best"]["values"])
        types = [e["type"] for e in ORCH.events_since(run["id"])]
        for t in ("workflow_created", "workflow_started", "step_started", "study_created", "trial_completed", "evaluation_completed",
                  "verification_completed", "workflow_completed"):
            self.assertIn(t, types)
        self.assertTrue((config.data_dir() / "workflows" / "reports").exists())

    def test_assisted_gate_with_edited_params(self):
        """Scenario B core: the study waits for approval; the researcher lowers the trial count before approving."""
        async def body():
            run = ORCH.create("hpo", inputs={"max_trials": 10})
            ORCH.start(run["id"])
            await step_state(run, "run", "WAITING_FOR_APPROVAL")
            self.assertEqual(run["status"], "WAITING_FOR_APPROVAL")
            pub = ORCH.public(run)
            self.assertEqual(pub["pending_approvals"][0]["step_id"], "run")
            self.assertIn("manual step", run["steps"]["run"]["approval"]["reason"])  # high risk → manual in assisted mode
            self.assertEqual(run["steps"]["run"]["approval"]["planned_params"]["max_trials"], 10)
            with self.assertRaises(OrchestratorError):
                ORCH.decide(run["id"], "run", "approve", params_patch={"rm_rf": True})
            with self.assertRaises(OrchestratorError):
                ORCH.decide(run["id"], "run", "maybe")
            with self.assertRaises(OrchestratorError):
                ORCH.decide(run["id"], "nope", "approve")
            with self.assertRaises(OrchestratorError):
                ORCH.decide(run["id"], "validate", "approve")
            with self.assertRaises(OrchestratorError):
                ORCH.decide(run["id"], "run", "revise")  # revise is for agent steps
            ORCH.decide(run["id"], "run", "approve", note="small study first", params_patch={"max_trials": 3})
            await until(run, "SUCCEEDED", "FAILED")
            return run
        run = self.go(body())
        self.assertEqual(run["status"], "SUCCEEDED", run["error"])
        self.assertEqual(run["ledger"]["trials_used"], 3)
        self.assertEqual(run["approval_history"][0]["edited_params"], ["max_trials"])

    def test_manual_mode_reviews_every_result_and_accepts_edits(self):
        """Scenario A: manual model audit — nothing proceeds without the researcher; no training starts."""
        async def body():
            run = ORCH.create("model_feasibility")
            self.assertEqual(run["steps"]["inspect"]["mode"], "assisted")
            ORCH.start(run["id"])
            await step_state(run, "inspect", "WAITING_FOR_APPROVAL")
            self.assertEqual(run["steps"]["inspect"]["approval"]["phase"], "after")
            with self.assertRaises(OrchestratorError):  # an edited result is still validated by type — here any dict is fine
                ORCH.decide(run["id"], "feasible", "approve")
            ORCH.decide(run["id"], "inspect", "approve")
            await step_state(run, "feasible", "WAITING_FOR_APPROVAL")
            out = dict(run["steps"]["feasible"]["output"], reviewed_by_me=True)
            ORCH.decide(run["id"], "feasible", "approve", output=out)
            await step_state(run, "report", "WAITING_FOR_APPROVAL")
            ORCH.decide(run["id"], "report", "approve")
            await until(run, "SUCCEEDED")
            return run
        run = self.go(body())
        self.assertTrue(run["steps"]["feasible"]["output"]["reviewed_by_me"])
        self.assertIn(run["outputs"]["feasible"], (True, False, None))
        self.assertTrue(run["approval_history"][1]["edited_output"])

    def test_reject_fails_fast_and_skips_the_rest(self):
        async def body():
            run = ORCH.create("hpo")
            ORCH.start(run["id"])
            await step_state(run, "run", "WAITING_FOR_APPROVAL")
            ORCH.decide(run["id"], "run", "reject", note="not now")
            await until(run, "FAILED")
            return run
        run = self.go(body())
        self.assertIn("rejected", run["error"])
        self.assertEqual(run["steps"]["compare"]["status"], "SKIPPED")

    def test_custom_mode_per_step_autonomy(self):
        """Scenario G (mixed): manual hypothesis → automatic step → assisted step with revise → manual 'provide result'."""
        cmd = {"$ref": "inputs.cmd"}
        d = wf([{"id": "hyp", "type": "human.input", "params": {"prompt": "hypothesis?", "fields": {"h": "string"}}},
                {"id": "auto", "type": "test.sleep", "mode": "automatic", "depends_on": ["hyp"], "params": {"value": {"$ref": "steps.hyp.output.h"}}},
                {"id": "plan", "type": "agent.plan", "mode": "assisted", "depends_on": ["auto"], "params": {"objective": "x"}},
                {"id": "run", "type": "sandbox.run", "mode": "manual", "depends_on": ["plan"], "params": {"command": cmd}}],
               execution_mode="custom", inputs={"cmd": {"type": "string", "default": "python train.py"}},
               outputs={"v": "steps.auto.output.value", "r": "steps.run.output"})

        async def body():
            run = ORCH.create(definition=d)
            ORCH.start(run["id"])
            await step_state(run, "hyp", "WAITING_FOR_APPROVAL")
            self.assertEqual(run["steps"]["hyp"]["approval"]["fields"], {"h": "string"})
            ORCH.decide(run["id"], "hyp", "approve", values={"h": "attention helps"})
            await step_state(run, "plan", "WAITING_FOR_APPROVAL")
            ORCH.decide(run["id"], "plan", "revise", note="add an ablation")
            await step_state(run, "plan", "WAITING_FOR_APPROVAL")
            self.assertIn("add an ablation", self.h.calls[-1][1])
            ORCH.decide(run["id"], "plan", "approve")
            await step_state(run, "run", "WAITING_FOR_APPROVAL")
            self.assertTrue(run["steps"]["run"]["approval"]["reason"].startswith("this step type always"))
            ORCH.decide(run["id"], "run", "provide", output={"psnr": 31.2, "note": "ran it on the cluster"})
            await until(run, "SUCCEEDED")
            return run
        run = self.go(body())
        self.assertEqual(run["outputs"]["v"], "attention helps")
        self.assertEqual(run["steps"]["run"]["provided_by"], "researcher")
        self.assertEqual(run["outputs"]["r"]["psnr"], 31.2)


class Control(Base):
    def test_failure_policy_continue_retry_timeout_and_conditions(self):
        d = wf([{"id": "bad", "type": "model.inspect", "params": {"adapter": "spec", "spec": {"input_shape": []}}},
                {"id": "after_bad", "type": "test.sleep", "depends_on": ["bad"]},
                {"id": "after_after", "type": "test.sleep", "depends_on": ["after_bad"]},
                {"id": "flaky", "type": "test.sleep", "params": {"fail": 1}, "retry": {"max": 1}},
                {"id": "slow", "type": "test.sleep", "params": {"s": 3}, "timeout_s": 1},
                {"id": "skipme", "type": "test.sleep", "when": {"ref": "steps.flaky.output.value", "op": "eq", "value": 99},
                 "depends_on": ["flaky"]},
                {"id": "runs_anyway", "type": "test.sleep", "depends_on": ["skipme"]}],
               failure_policy="continue", outputs={})

        async def body():
            run = ORCH.create(definition=d)
            ORCH.start(run["id"])
            await until(run, "FAILED")
            return run
        run = self.go(body())
        st = {k: v["status"] for k, v in run["steps"].items()}
        self.assertEqual(st["bad"], "FAILED")
        self.assertEqual(st["after_bad"], "SKIPPED")
        self.assertEqual(st["after_after"], "SKIPPED")
        self.assertEqual(st["flaky"], "SUCCEEDED")
        self.assertEqual(run["steps"]["flaky"]["attempts"], 2)
        self.assertEqual(st["slow"], "FAILED")
        self.assertIn("timed out", run["steps"]["slow"]["error"])
        self.assertEqual(st["skipme"], "SKIPPED")
        self.assertEqual(st["runs_anyway"], "SUCCEEDED")
        self.assertIn("failed steps", run["error"])

    def test_pause_resume_and_cancel(self):
        d = wf([{"id": "a", "type": "test.sleep", "params": {"s": 0.4}}, {"id": "b", "type": "test.sleep", "depends_on": ["a"]}], outputs={})

        async def body():
            run = ORCH.create(definition=d)
            ORCH.start(run["id"])
            await step_state(run, "a", "RUNNING")
            ORCH.pause(run["id"])
            await until(run, "PAUSED")
            self.assertEqual(run["steps"]["b"]["status"], "PENDING")
            ORCH.start(run["id"])
            await until(run, "SUCCEEDED")
            self.assertGreaterEqual(run["paused_s"], 0)
            with self.assertRaises(OrchestratorError):
                ORCH.pause(run["id"])
            with self.assertRaises(OrchestratorError):
                ORCH.start(run["id"])
            c = ORCH.create(definition=wf([{"id": "x", "type": "test.sleep", "params": {"s": 5}}], outputs={}))
            ORCH.start(c["id"])
            await step_state(c, "x", "RUNNING")
            ORCH.pause(c["id"])  # pause while running: becomes PAUSED after the step
            ORCH.cancel(c["id"])
            await asyncio.sleep(0.05)
            self.assertEqual(c["status"], "CANCELLED")
            self.assertEqual(c["steps"]["x"]["status"], "CANCELLED")
            self.assertTrue(c["steps"]["x"]["checkpoint"].get("cancel_fn"))
            with self.assertRaises(OrchestratorError):
                ORCH.cancel(c["id"])
        self.go(body())

    def test_pause_mid_study_and_resume_continues_the_study(self):
        async def body():
            run = ORCH.create("hpo", inputs={"max_trials": 8, "objective": {"kind": "analytic", "function": "quadratic", "delay_s": 0.05}},
                              overrides={"execution_mode": "bounded", "approvals": {"before_training": "not_required"}})
            ORCH.start(run["id"])
            await step_state(run, "run", "RUNNING")
            await asyncio.sleep(0.15)
            ORCH.pause(run["id"])
            await until(run, "PAUSED")
            sid = run["steps"]["run"]["checkpoint"]["study_id"]
            n = len(H.load_study(sid)["trials"])
            self.assertLess(n, 8)
            ORCH.start(run["id"])
            await until(run, "SUCCEEDED")
            self.assertEqual(run["steps"]["run"]["output"]["study_id"], sid)
            self.assertEqual(len(H.load_study(sid)["trials"]), 8)
        self.go(body())

    def test_budgets(self):
        async def body():
            r = ORCH.create(definition=wf([{"id": "a", "type": "test.sleep", "params": {"s": 2}}],
                                          budgets={"max_runtime_minutes": 0.01, "max_trials": 1, "max_workflow_cycles": 1}, outputs={}))
            ORCH.start(r["id"])
            await until(r, "BUDGET_EXCEEDED", timeout=15)
            a = ORCH.create(definition=wf([{"id": "p1", "type": "agent.plan", "params": {"objective": "a"}},
                                           {"id": "p2", "type": "agent.plan", "depends_on": ["p1"], "params": {"objective": "b"}}],
                                          budgets={"max_agent_calls": 1, "max_trials": 1, "max_runtime_minutes": 5,
                                                   "max_workflow_cycles": 1}, outputs={}))
            ORCH.start(a["id"])
            await until(a, "BUDGET_EXCEEDED")
            self.assertIn("agent-call budget", a["error"])
            self.assertEqual(ORCH.budget_left(a)["agent_calls"], 0)
        self.go(body())

    def test_one_execution_step_at_a_time(self):
        d = wf([{"id": "e1", "type": "test.exec", "params": {"s": 0.3}}, {"id": "e2", "type": "test.exec", "params": {"s": 0.3}}], outputs={})

        async def body():
            run = ORCH.create(definition=d)
            ORCH.start(run["id"])
            await step_state(run, "e1", "RUNNING", "SUCCEEDED")
            self.assertNotEqual(run["steps"]["e2"]["status"], "RUNNING")
            await until(run, "SUCCEEDED")
            s1, s2 = run["steps"]["e1"], run["steps"]["e2"]
            self.assertTrue(s2["started"] >= s1["ended"] - 0.01 or s1["started"] >= s2["ended"] - 0.01)
        self.go(body())

    def test_recovery_after_restart(self):
        d = wf([{"id": "safe", "type": "test.sleep"}, {"id": "costly", "type": "test.exec"}, {"id": "done", "type": "test.sleep"}], outputs={})

        async def body():
            run = ORCH.create(definition=d)
            run.update(status="RUNNING", started=time.time())
            run["steps"]["safe"]["status"] = run["steps"]["costly"]["status"] = "RUNNING"
            run["steps"]["done"].update(status="SUCCEEDED", output={"value": 7})
            ORCH.persist(run)
            ORCH.reset()  # app restart
            r2 = ORCH.get(run["id"])
            self.assertEqual(r2["status"], "PAUSED")
            self.assertTrue(r2["recovered"])
            self.assertEqual(r2["steps"]["safe"]["status"], "READY")
            self.assertEqual(r2["steps"]["costly"]["status"], "WAITING_FOR_APPROVAL")
            self.assertIn("not safe to repeat", r2["steps"]["costly"]["approval"]["reason"])
            ORCH.start(r2["id"])
            await step_state(r2, "safe", "SUCCEEDED")
            ORCH.decide(r2["id"], "costly", "approve")
            await until(r2, "SUCCEEDED")
            self.assertEqual(r2["steps"]["done"]["attempts"], 0)  # a completed step is never re-run
            ORCH.reset()
            self.assertEqual(ORCH.get(run["id"])["status"], "SUCCEEDED")  # terminal runs are left alone
        self.go(body())

    def test_events_listing_and_errors(self):
        async def body():
            run = ORCH.create(definition=wf([{"id": "a", "type": "test.sleep"}], outputs={}))
            ORCH.start(run["id"])
            await until(run, "SUCCEEDED")
            n = len(ORCH.events_since(run["id"]))
            ORCH.reset()
            self.assertEqual(len(ORCH.events_since(run["id"])), n)  # read back from the .events.jsonl file
            self.assertEqual(ORCH.events_since(run["id"], n), [])
            await ORCH.wait_change(run["id"], 0.05)
            with self.assertRaises(OrchestratorError):
                ORCH.emit(run, "made_up_event")
            self.assertTrue(any(x["id"] == run["id"] for x in ORCH.list()))
            (EN._runs_dir() / "wf-0000000000.json").write_text("{", "utf-8")
            ORCH.list()
            self.assertEqual(ORCH.public(run)["definition_id"], "t_wf")
        self.go(body())
        for bad in ("../x", "wf-ffffffffff"):
            with self.assertRaises(OrchestratorError):
                ORCH.get(bad)

    def test_create_refusals(self):
        with self.assertRaises(OrchestratorError):
            ORCH.create("does_not_exist")
        with self.assertRaises(OrchestratorError):
            ORCH.create("research_planning")  # required input missing
        with self.assertRaises(OrchestratorError):
            ORCH.create(definition=wf([{"id": "a", "type": "shell.exec"}]))
        config.save_config({"features": {"workflow_orchestrator": False}})
        with self.assertRaises(OrchestratorError):
            ORCH.create("hpo")
        config.save_config({"features": {"workflow_orchestrator": True}})
        loops = [wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "t_wf"}}]),
                 wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "ghost"}}]),
                 wf([{"id": "c", "type": "workflow.call", "params": {"workflow": {"$ref": "inputs.w"}}}], inputs={"w": {"type": "string"}})]
        for d in loops:
            self.assertTrue(ORCH.validate(d)[1], d["steps"][0]["params"])
        self.assertTrue(TP.call_graph_ok({"id": "deep", "steps": []}, depth=5))


class Nested(Base):
    def test_planning_calls_feasibility_then_search_space(self):
        """Scenario H: the parent uses the child's structured result to decide whether to design a search space."""
        async def body():
            run = ORCH.create("planning_with_feasibility", inputs={"objective": "denoise HSI cubes"})
            ORCH.start(run["id"])
            seen = set()
            t0 = time.time()
            while run["status"] not in ("SUCCEEDED", "FAILED") and time.time() - t0 < 60:
                for p in ORCH.pending(run):
                    if (p["run_id"], p["step_id"]) in seen:
                        continue
                    seen.add((p["run_id"], p["step_id"]))
                    ORCH.decide(p["run_id"], p["step_id"], "approve")
                await asyncio.sleep(0.03)
            return run, seen
        run, seen = self.go(body())
        self.assertEqual(run["status"], "SUCCEEDED", run["error"])
        self.assertEqual(len(run["children"]), 3)
        self.assertTrue(all(c != run["id"] for c, _ in seen))  # decisions happened inside the nested runs
        child = ORCH.get(run["children"][1])
        self.assertEqual(child["parent"]["run_id"], run["id"])
        self.assertEqual(child["approvals"]["before_training"], "required")  # root policy inherited
        self.assertIn("x", run["outputs"]["search_space"])

    def test_infeasible_model_skips_the_search_space(self):
        huge = {"input_shape": [3, 512, 512], "layers": [{"type": "conv2d", "out": 4096, "k": 7, "padding": 3},
                                                         {"type": "conv2d", "out": 4096, "k": 7, "padding": 3}]}

        async def body():
            run = ORCH.create("planning_with_feasibility", inputs={"objective": "x", "spec": huge})
            ORCH.start(run["id"])
            t0 = time.time()
            while run["status"] not in ("SUCCEEDED", "FAILED") and time.time() - t0 < 60:
                for p in ORCH.pending(run):
                    try:
                        ORCH.decide(p["run_id"], p["step_id"], "approve")
                    except OrchestratorError:
                        pass
                await asyncio.sleep(0.03)
            return run
        with mock.patch("backend.resources.policy", return_value={"vram_safety_cap_gb": 11.0, "gpu": "RTX 3060"}):
            run = self.go(body())
        self.assertEqual(run["status"], "SUCCEEDED", run["error"])
        self.assertFalse(run["outputs"]["feasible"])
        self.assertEqual(run["steps"]["space"]["status"], "SKIPPED")

    def test_full_bounded_loop_with_repeat(self):
        """Scenario C: bounded automation stops at its gates and its cycle cap; no conclusion without approval."""
        async def body():
            run = ORCH.create("full_bounded_loop", inputs={"objective": "beat the baseline"})
            ORCH.start(run["id"])
            await step_state(run, "approve_objective", "WAITING_FOR_APPROVAL")
            ORCH.decide(run["id"], "approve_objective", "approve")
            t0 = time.time()
            while run["status"] not in ("SUCCEEDED", "FAILED") and time.time() - t0 < 90:
                for p in ORCH.pending(run):
                    ORCH.decide(p["run_id"], p["step_id"], "approve")
                await asyncio.sleep(0.03)
            return run
        run = self.go(body())
        self.assertEqual(run["status"], "SUCCEEDED", run["error"])
        cyc = run["steps"]["cycles"]["output"]
        self.assertEqual(cyc["stopped_because"], "condition met")
        self.assertEqual(len(cyc["cycles"]), 1)
        self.assertEqual(run["ledger"]["cycles_used"], 1)
        self.assertGreater(run["ledger"]["trials_used"], 0)
        hist = [h["step_id"] for h in run["approval_history"]]
        self.assertIn("interpret", hist)  # the AI interpretation needed the researcher (before_conclusion)

    def test_child_failure_and_cancel_propagate(self):
        bad = {"id": "bad_child", "version": 1, "execution_mode": "bounded",
               "steps": [{"id": "x", "type": "model.inspect", "params": {"spec": {}}}]}
        TP.save(bad)
        d = wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "bad_child"}}], outputs={})
        slow = {"id": "slow_child", "version": 1, "execution_mode": "bounded", "steps": [{"id": "s", "type": "test.sleep", "params": {"s": 5}}]}
        TP.save(slow)

        async def body():
            run = ORCH.create(definition=d)
            ORCH.start(run["id"])
            await until(run, "FAILED")
            self.assertIn("nested workflow bad_child", run["steps"]["c"]["error"])
            p = ORCH.create(definition=wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "slow_child"}}], outputs={}))
            ORCH.start(p["id"])
            await step_state(p, "c", "RUNNING")
            while not p["children"]:
                await asyncio.sleep(0.02)
            child = ORCH.get(p["children"][0])
            await until(child, "RUNNING")
            ORCH.cancel(p["id"])
            await asyncio.sleep(0.1)
            self.assertEqual(child["status"], "CANCELLED")
        self.go(body())

    def test_parent_pause_pauses_the_child_and_resume_reuses_it(self):
        slow = {"id": "pausable_child", "version": 1, "execution_mode": "bounded",
                "steps": [{"id": "a", "type": "test.sleep", "params": {"s": 0.3}}, {"id": "b", "type": "test.sleep", "depends_on": ["a"]}]}
        TP.save(slow)

        async def body():
            p = ORCH.create(definition=wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "pausable_child"}}],
                                          outputs={"v": "steps.c.output"}))
            ORCH.start(p["id"])
            while not p["children"]:
                await asyncio.sleep(0.02)
            ORCH.pause(p["id"])
            await until(p, "PAUSED")
            child_id = p["children"][0]
            ORCH.start(p["id"])
            await until(p, "SUCCEEDED")
            self.assertEqual(p["children"], [child_id])  # resumed the same child, no duplicate run
        self.go(body())


class StepTypes(Base):
    def run_def(self, steps, **kw):
        async def body():
            run = ORCH.create(definition=wf(steps, outputs={}, **kw))
            ORCH.start(run["id"])
            await until(run, "SUCCEEDED", "FAILED", "WAITING_FOR_APPROVAL")
            return run
        return self.go(body())

    def test_research_state_context_report_memory(self):
        run = self.run_def([{"id": "st", "type": "research.state"},
                            {"id": "cx", "type": "research.context", "params": {"query": "baseline"}},
                            {"id": "rep", "type": "report.generate", "depends_on": ["st"], "params": {"title": "T", "sections": {"s": {"$ref": "steps.st.output"}}}},
                            {"id": "mem", "type": "memory.propose", "params": {"kind": "observation", "text": "PSNR plateaued at 31 dB"}},
                            {"id": "mem_bad", "type": "memory.propose", "params": {"kind": "gossip", "text": "x"}}], failure_policy="continue")
        st = run["steps"]
        self.assertEqual(st["st"]["status"], "SUCCEEDED")
        self.assertIn("context_version", st["cx"]["output"])
        self.assertTrue(st["rep"]["output"]["relative"].endswith(".md"))
        self.assertTrue(st["mem"]["output"]["candidate_id"].startswith("CAND-"))
        self.assertEqual(st["mem_bad"]["status"], "FAILED")
        from backend.memory import lifecycle
        self.assertEqual(lifecycle.get(st["mem"]["output"]["candidate_id"])["status"], "pending")  # never durable by itself

    def test_inspect_variants_and_feasibility_errors(self):
        run = self.run_def([{"id": "onnx", "type": "model.inspect", "params": {"adapter": "onnx", "path": "m.onnx"}},
                            {"id": "pt", "type": "model.inspect", "params": {"adapter": "pytorch"}},
                            {"id": "fe", "type": "model.feasibility", "params": {"report": {"params": {"value": 10}}, "precision": "fp8"}}],
                           failure_policy="continue")
        self.assertIn("onnx", run["steps"]["onnx"]["error"])
        self.assertIn("model.profile", run["steps"]["pt"]["error"])
        self.assertIn("precision", run["steps"]["fe"]["error"])

    def test_model_profile_through_the_sandbox(self):
        from backend.sandbox import code_dir
        (code_dir() / "net.py").write_text("class Net: pass\n", "utf-8")
        prof = {"params": 10, "trainable": 10, "macs": 20, "latency_ms_median": 1.0, "latency_ms_p95": 1.2, "peak_mb": None,
                "device": "cpu", "torch": "x", "gpu": ""}
        jobs = [FakeJob(out="PHDLAB_PROFILE " + json.dumps(prof), running=1), FakeJob(status="failed", err="ImportError: torch"),
                FakeJob(out="no tag")]
        with mock.patch("backend.sandbox.start_job", side_effect=jobs), mock.patch("backend.sandbox.effective_mode", return_value="local"):
            run = self.run_def([{"id": "p", "type": "model.profile", "params": {"model_path": "net.py", "class_name": "Net",
                                                                                 "input_shape": [3, 8, 8], "gpu": False}},
                                {"id": "p2", "type": "model.profile", "depends_on": ["p"], "params": {"model_path": "net.py", "class_name": "Net", "input_shape": [3, 8, 8]}},
                                {"id": "p3", "type": "model.profile", "depends_on": ["p"], "params": {"model_path": "net.py", "class_name": "Net", "input_shape": [3, 8, 8]}},
                                {"id": "p4", "type": "model.profile", "params": {"model_path": "../x.py", "class_name": "Net", "input_shape": [3]}}],
                               failure_policy="continue")
        st = run["steps"]
        self.assertEqual(st["p"]["output"]["report"]["latency_ms"]["label"], "MEASURED")
        self.assertIn("torch", st["p2"]["error"])
        self.assertIn("no result", st["p3"]["error"])
        self.assertIn("code folder", st["p4"]["error"])

    def test_sandbox_run_and_docker_lease(self):
        from backend import model_lifecycle as LC
        LC.reset()
        with mock.patch("backend.sandbox.start_job", side_effect=[FakeJob(), FakeJob(status="failed", exit_code=1, err="boom"),
                                                                    __import__("backend.sandbox", fromlist=["x"]).SandboxError("VRAM busy")]), \
                mock.patch("backend.sandbox.effective_mode", return_value="docker"), \
                mock.patch("backend.sandbox.container_name", return_value="phdlab-wf"), \
                mock.patch("backend.sandbox.container_state", return_value={"running": False}):
            run = self.run_def([{"id": "ok", "type": "sandbox.run", "mode": "automatic", "params": {"command": "python a.py"}},
                                {"id": "bad", "type": "sandbox.run", "mode": "automatic", "depends_on": ["ok"], "params": {"command": "python b.py", "gpu": True}},
                                {"id": "busy", "type": "sandbox.run", "mode": "automatic", "depends_on": ["ok"], "params": {"command": "python c.py"}}],
                               failure_policy="continue", execution_mode="custom")
            # sandbox.run always waits for approval
            self.assertEqual(run["steps"]["ok"]["status"], "WAITING_FOR_APPROVAL")

            async def body():
                r = ORCH.get(run["id"])
                ORCH.decide(r["id"], "ok", "approve")
                await step_state(r, "bad", "WAITING_FOR_APPROVAL")
                await step_state(r, "busy", "WAITING_FOR_APPROVAL")
                ORCH.decide(r["id"], "bad", "approve")
                ORCH.decide(r["id"], "busy", "approve")
                await until(r, "FAILED")
                return r
            run = self.go(body())
        st = run["steps"]
        self.assertEqual(st["ok"]["output"]["status"], "done")
        self.assertIn("exit 1", st["bad"]["error"])
        self.assertIn("VRAM busy", st["busy"]["error"])
        self.assertIn("mcp:docker:phdlab-wf", LC._res)
        LC.reset()

    def test_hpo_with_a_sandbox_script_objective(self):
        from backend.sandbox import code_dir
        (code_dir() / "train.py").write_text("print('loss=0.1')\n", "utf-8")
        jobs = [FakeJob(metrics={"loss": 0.3}), FakeJob(metrics={"loss": 0.2}, running=1, out="step=1 loss=0.5\nstep=2 loss=0.4\n"),
                FakeJob(status="failed", err="RuntimeError: CUDA out of memory"), FakeJob(metrics={})]
        with mock.patch("backend.sandbox.start_job", side_effect=jobs), mock.patch("backend.sandbox.stop_job"):
            run = self.run_def([{"id": "h", "type": "hpo.run", "params": {"search_space": {"x": {"type": "float", "low": 0, "high": 1}},
                                                                          "objectives": [{"name": "loss", "direction": "minimize"}],
                                                                          "max_trials": 4, "objective": {"kind": "sandbox_script", "script": "train.py"}}}])
        out = run["steps"]["h"]["output"]
        self.assertEqual(out["n_complete"], 2)
        self.assertEqual(out["n_failed"], 2)
        self.assertEqual(out["measurement"], "MEASURED")
        trials = H.load_study(out["study_id"])["trials"]
        self.assertTrue(any("gpu_oom" in (t.get("error") or "") for t in trials))
        self.assertEqual(trials[0]["run_id"], "run-test01")

    def test_hpo_refusals(self):
        run = self.run_def([{"id": "k", "type": "hpo.run", "params": {"search_space": {"x": {"type": "bool"}}, "objectives": [{"name": "loss", "direction": "minimize"}],
                                                                        "max_trials": 2, "objective": {"kind": "shell"}}},
                            {"id": "s", "type": "hpo.run", "params": {"search_space": {"x": {"type": "bool"}}, "objectives": [{"name": "loss", "direction": "minimize"}],
                                                                        "max_trials": 2, "objective": {"kind": "sandbox_script", "script": "../../evil.py"}}},
                            {"id": "r", "type": "hpo.run", "params": {"search_space": {"x": {"type": "bool"}}, "objectives": [{"name": "loss", "direction": "minimize"}],
                                                                        "max_trials": 2, "runner": "ray", "objective": {"kind": "analytic", "function": "quadratic"}}}],
                           failure_policy="continue")
        self.assertIn("objective.kind", run["steps"]["k"]["error"])
        self.assertIn("code folder", run["steps"]["s"]["error"])
        self.assertIn("local sequential runner", run["steps"]["r"]["error"])
        config.save_config({"features": {"experiment_execution": False}})
        run = self.run_def([{"id": "s", "type": "hpo.run", "params": {"search_space": {"x": {"type": "bool"}}, "objectives": [{"name": "loss", "direction": "minimize"}],
                                                                        "max_trials": 2, "objective": {"kind": "sandbox_script", "script": "t.py"}}}])
        self.assertIn("switched off", run["steps"]["s"]["error"])

    def test_sandbox_objective_edge_paths(self):
        from backend import sandbox
        from backend.sandbox import code_dir
        (code_dir() / "t.py").write_text("", "utf-8")

        class Ctx:
            def on_cancel(self, fn):
                self.fn = fn
        ctx = Ctx()
        run = ST._sandbox_objective(ctx, {"kind": "sandbox_script", "script": "t.py", "timeout_s": 1}, "loss", True)
        prune_run = ST._sandbox_objective(ctx, {"kind": "sandbox_script", "script": "t.py"}, "loss", True)

        async def body():
            with mock.patch.object(sandbox, "start_job", return_value=FakeJob(running=10 ** 6)), mock.patch.object(sandbox, "stop_job") as stop:
                with self.assertRaises(H.HPOError):
                    await run({"x": 1}, 0, lambda *_: False)  # time limit
                stop.assert_called()
            j = FakeJob(running=3, out="step=1 loss=0.9\nstep=2 loss=0.8\n")  # a series needs ≥ 2 points
            with mock.patch.object(sandbox, "start_job", return_value=j), mock.patch.object(sandbox, "stop_job") as stop:
                await prune_run({"x": 1}, 0, lambda v, s: True)  # pruned → the job is stopped
                stop.assert_called_with("run-test01")
            with mock.patch.object(sandbox, "start_job", side_effect=sandbox.SandboxError("no python")):
                with self.assertRaises(H.HPOError):
                    await run({"x": 1}, 0, lambda *_: False)
            with mock.patch.object(sandbox, "start_job", return_value=FakeJob(running=10 ** 6)), mock.patch.object(sandbox, "stop_job") as stop:
                t = asyncio.ensure_future(run({"x": 1}, 0, lambda *_: False))
                await asyncio.sleep(0.2)
                t.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await t
                stop.assert_called()
        self.go(body())

    def test_evaluation_verification_ablation_diagnosis(self):
        async def mk():
            return await H.run_study({"search_space": {"lr": {"type": "float", "low": 1e-4, "high": 1e-2, "log": True},
                                                       "width": {"type": "int", "low": 16, "high": 64}},
                                      "objectives": [{"name": "psnr", "direction": "maximize"}, {"name": "params_m", "direction": "minimize"}],
                                      "max_trials": 6, "objective": {"kind": "analytic", "function": "restoration_proxy"}},
                                     features={"optuna_hpo": True})
        sid = self.go(mk())["study_id"]
        from backend.memory import research
        research.add_failure("CUDA out of memory with batch 64 on the denoiser", error="CUDA out of memory")
        run = self.run_def([
            {"id": "cmp", "type": "evaluation.compare_trials", "params": {"study_id": sid, "rank_by": "psnr", "baseline": {"psnr": 30.0}, "top_k": 2}},
            {"id": "conf", "type": "evaluation.confirm", "params": {"study_id": sid, "top_k": 2, "seeds": [1, 2, 3], "baseline": {"psnr": 30.0}}},
            {"id": "ver", "type": "verification.check", "params": {"study_id": sid, "min_complete": 3, "expect_files": ["metrics.json"]}},
            {"id": "ver_fail", "type": "verification.check", "params": {"study_id": sid, "min_complete": 99, "fail_on_error": False}},
            {"id": "ver_strict", "type": "verification.check", "params": {"study_id": sid, "min_complete": 99}},
            {"id": "ab", "type": "ablation.generate", "params": {"baseline_config": {"attention": True, "width": 64}, "components": ["attention", "width"]}},
            {"id": "ab_bad", "type": "ablation.generate", "params": {"baseline_config": {"a": 1}, "components": ["b"]}},
            {"id": "rc", "type": "evaluation.run_configs", "depends_on": ["ab"], "params": {"configs": [{"name": "base", "config": {"lr": 1e-3, "width": 64, "attention": True}},
                                                                                                         {"$ref": "steps.ab.output.variants.0"}],
                                                                                             "objective": {"kind": "analytic", "function": "restoration_proxy"},
                                                                                             "objectives": [{"name": "psnr", "direction": "maximize"}], "seeds": [1, 2]}},
            {"id": "rc_bad", "type": "evaluation.run_configs", "params": {"configs": ["x"], "objective": {"kind": "analytic", "function": "quadratic"},
                                                                          "objectives": [{"name": "loss", "direction": "minimize"}]}},
            {"id": "rc_obj", "type": "evaluation.run_configs", "params": {"configs": [{"config": {}}], "objective": {"kind": "analytic", "function": "nope"},
                                                                          "objectives": [{"name": "loss", "direction": "minimize"}]}},
            {"id": "rc_objs", "type": "evaluation.run_configs", "params": {"configs": [{"config": {}}], "objective": {}, "objectives": []}},
            {"id": "diag", "type": "failure.diagnose", "params": {"error": "RuntimeError: CUDA out of memory. Tried to allocate"}},
            {"id": "diag2", "type": "failure.diagnose", "params": {"error": "loss became nan at step 400"}},
            {"id": "diag3", "type": "failure.diagnose", "params": {"error": "something odd"}},
            {"id": "bad_study", "type": "evaluation.compare_trials", "params": {"study_id": "study-00000000"}}],
            failure_policy="continue", budgets={"max_trials": 100, "max_runtime_minutes": 30, "max_workflow_cycles": 1})
        st = run["steps"]
        self.assertEqual(len(st["cmp"]["output"]["top"]), 2)
        self.assertIn("delta_vs_baseline", st["cmp"]["output"]["top"][0])
        self.assertTrue(st["cmp"]["output"]["pareto"])
        c0 = st["conf"]["output"]["candidates"][0]
        self.assertEqual(c0["stats"]["psnr"]["n"], 3)
        self.assertIn("ci_excludes_baseline", c0["vs_baseline"]["psnr"])
        self.assertFalse(st["ver"]["output"] and st["ver"]["output"].get("passed"))  # analytic trials have no run files
        self.assertFalse(st["ver_fail"]["output"]["passed"])
        self.assertEqual(st["ver_strict"]["status"], "FAILED")
        self.assertEqual([v["name"] for v in st["ab"]["output"]["variants"]], ["without_attention", "without_width"])
        self.assertEqual(st["ab_bad"]["status"], "FAILED")
        self.assertEqual(len(st["rc"]["output"]["results"]), 2)
        self.assertEqual(st["rc_bad"]["status"], "FAILED")
        self.assertEqual(st["rc_obj"]["status"], "FAILED")
        self.assertEqual(st["rc_objs"]["status"], "FAILED")
        self.assertEqual(st["diag"]["output"]["category"], "gpu_oom")
        self.assertTrue(st["diag"]["output"]["similar_failures"])
        self.assertEqual(st["diag2"]["output"]["category"], "numerical_instability")
        self.assertEqual(st["diag3"]["output"]["category"], "unknown")
        self.assertEqual(st["bad_study"]["status"], "FAILED")

    def test_confirm_and_configs_respect_the_trial_budget(self):
        async def mk():
            return await H.run_study({"search_space": {"x": {"type": "float", "low": 0, "high": 1}}, "objectives": [{"name": "loss", "direction": "minimize"}],
                                      "max_trials": 3, "objective": {"kind": "analytic", "function": "quadratic"}}, features={"optuna_hpo": False})
        sid = self.go(mk())["study_id"]
        run = self.run_def([{"id": "conf", "type": "evaluation.confirm", "params": {"study_id": sid, "top_k": 2, "seeds": [1, 2]}},
                            {"id": "rc", "type": "evaluation.run_configs", "params": {"configs": [{"config": {"x": 1}}], "seeds": [1, 2, 3],
                                                                                      "objective": {"kind": "analytic", "function": "quadratic"},
                                                                                      "objectives": [{"name": "loss", "direction": "minimize"}]}}],
                           failure_policy="continue", budgets={"max_trials": 3, "max_runtime_minutes": 5, "max_workflow_cycles": 1})
        errs = [run["steps"][k]["error"] for k in ("conf", "rc")]
        self.assertTrue(any("trial budget" in e for e in errs), errs)

    def test_search_space_proposal_gate_validates_edits(self):
        """Search-Space Design: an invalid AI proposal can only pass after the researcher fixes it."""
        async def body():
            run = ORCH.create("search_space_design", inputs={"hint": "invalid please"})
            ORCH.start(run["id"])
            await step_state(run, "propose", "WAITING_FOR_APPROVAL")
            self.assertTrue(run["steps"]["propose"]["warnings"])
            with self.assertRaises(OrchestratorError):
                ORCH.decide(run["id"], "propose", "approve")
            fixed = dict(run["steps"]["propose"]["output"], search_space={"lr": {"type": "float", "low": 1e-5, "high": 1e-2, "log": True}})
            ORCH.decide(run["id"], "propose", "approve", output=fixed)
            await step_state(run, "approve", "WAITING_FOR_APPROVAL")
            ORCH.decide(run["id"], "approve", "approve")
            await until(run, "SUCCEEDED")
            return run
        run = self.go(body())
        self.assertIn("lr", run["outputs"]["search_space"])

    def test_invalid_proposal_fails_without_a_gate_and_validator_refuses(self):
        run = self.run_def([{"id": "p", "type": "hpo.propose_search_space", "params": {"objectives": [{"name": "loss", "direction": "minimize"}],
                                                                                         "hint": "invalid"}},
                            {"id": "v", "type": "hpo.validate_search_space", "params": {"search_space": {"a": {"type": "x"}},
                                                                                         "objectives": [{"name": "loss", "direction": "minimize"}]}}],
                           failure_policy="continue")
        self.assertIn("invalid result", run["steps"]["p"]["error"])
        self.assertIn("rejected", run["steps"]["v"]["error"])
        self.assertEqual(ST._check_space_output("x"), ["output.search_space must be an object"])

    def test_repeat_with_invalid_condition_and_cycle_budget(self):
        TP.save({"id": "tiny_child", "version": 1, "execution_mode": "bounded", "steps": [{"id": "a", "type": "test.sleep"}],
                 "outputs": {"value": "steps.a.output.value"}})
        run = self.run_def([{"id": "r", "type": "workflow.repeat", "params": {"workflow": "tiny_child", "max_cycles": 5, "until": {"ref": "x", "op": "eq"}}},
                            {"id": "r2", "type": "workflow.repeat", "params": {"workflow": "tiny_child", "max_cycles": 5}},
                            {"id": "r3", "type": "workflow.repeat", "depends_on": ["r2"], "params": {"workflow": "tiny_child", "max_cycles": 5,
                                                                                                    "until": {"ref": "last.value", "op": "eq", "value": 2}}}],
                           failure_policy="continue", budgets={"max_workflow_cycles": 3, "max_trials": 1, "max_runtime_minutes": 5})
        st = run["steps"]
        self.assertIn("valid 'ref'", st["r"]["error"])
        self.assertEqual(len(st["r2"]["output"]["cycles"]), 3)
        self.assertIn("cycle cap", st["r2"]["output"]["stopped_because"])
        self.assertEqual(st["r3"]["output"]["cycles"], [])  # the cycle budget is shared and spent

    def test_unknown_nested_workflow_at_run_time(self):
        d = wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "gone_later"}}], outputs={})
        TP.save({"id": "gone_later", "version": 1, "steps": [{"id": "a", "type": "test.sleep"}]})
        run = ORCH.create(definition=d)
        TP.delete("gone_later", 1)

        async def body():
            ORCH.start(run["id"])
            await until(run, "FAILED")
        self.go(body())
        self.assertIn("unknown workflow", run["steps"]["c"]["error"])


class Templates(Base):
    def test_every_builtin_template_validates(self):
        for t in TP.BUILTIN:
            self.assertEqual(ORCH.validate(t)[1], [], t["id"])
        self.assertEqual(len(TP.BUILTIN), 11)

    def test_save_versions_and_delete(self):
        d = {"id": "my_flow", "version": 1, "steps": [{"id": "a", "type": "research.state"}]}
        with self.assertRaises(ValueError):
            TP.save({**d, "id": "hpo"})
        TP.save(d)
        with self.assertRaises(ValueError):
            TP.save(d)
        TP.save({**d, "version": 2})
        self.assertEqual(TP.get("my_flow")["version"], 2)
        self.assertEqual(TP.get("my_flow", 1)["version"], 1)
        (TP._dir() / "junk.json").write_text("{}", "utf-8")
        (TP._dir() / "broken@1.json").write_text("{", "utf-8")
        self.assertIn("my_flow", [t["id"] for t in TP.saved()])
        self.assertTrue(TP.delete("my_flow", 1))
        self.assertFalse(TP.delete("my_flow", 1))
        with self.assertRaises(ValueError):
            TP.delete("hpo", 1)
        self.assertIsNone(TP.get("nope"))


class Harness(unittest.TestCase):
    def test_llm_harness_contract(self):
        HA.use(None)
        h = HA.get()
        self.assertIsInstance(h, HA.LLMHarness)
        self.assertIs(HA.get(), h)
        replies = iter(['{"objective": "o"}', "not json at all", '{"search_space": {}}', '{"summary": "s"}', '{"diagnosis": "d"}'])

        async def fake_call(agent, system, user, max_tokens=0, temperature=0):
            from backend.model_lifecycle import _PURPOSE
            assert _PURPOSE.get() == "background"
            return {"text": next(replies), "engine": "fake", "model": "m"}

        async def body():
            with mock.patch("backend.llm.call_agent", fake_call):
                a = await h.plan("o", "ctx", {})
                b = await h.plan("o", "ctx", {})
                c = await h.propose_search_space({}, {}, "", [])
                d = await h.interpret({}, "h")
                e = await h.diagnose({"category": "x"}, [])
            return a, b, c, d, e
        a, b, c, d, e = asyncio.run(body())
        self.assertEqual(a["label"], HA.AI_SUGGESTION)
        self.assertIn("parse_error", b)
        self.assertEqual(c["label"], HA.AI_SUGGESTION)
        self.assertEqual(d["label"], HA.AI_INTERPRETATION)
        self.assertEqual(e["_engine"]["engine"], "fake")
        base = HA.Harness()
        for coro in (base.plan("", "", {}), base.propose_search_space({}, {}, "", []), base.interpret({}, ""), base.diagnose({}, [])):
            with self.assertRaises(NotImplementedError):
                asyncio.run(coro)
        HA.use(None)


if __name__ == "__main__":
    unittest.main()
