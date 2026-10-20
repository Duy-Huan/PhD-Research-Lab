"""v4.1 edge paths: rare orchestrator transitions (overrides, nested custom parents, child failures, interrupted waits,
idempotent re-entry), step handlers called directly with a fake context, HPO sampler corners, lifecycle corners."""
import _env  # noqa: F401  (must be first)
import asyncio
import time
import unittest
from unittest import mock

from backend import config, model_lifecycle as LC
from backend.workflow import ORCH, OrchestratorError, engine as EN, harness as HA, hpo as H, schema as S, steps as ST, templates as TP
from test_model_lifecycle import Fakes
from test_workflow_engine import FakeHarness, FakeJob, step_state, until, wf


class Ctx:
    """Minimal StepContext for calling handlers directly."""

    def __init__(self, params, stop=False, trials=10 ** 6, orch=None):
        self.params, self._stop, self._trials = params, stop, trials
        self.state, self.budgets, self.run, self.step = {}, {"max_trials": 100, "max_workflow_cycles": 5}, {"id": "wf-0000000001"}, {"id": "s"}
        self.orch = orch
        self.cancels = []

    def should_stop(self):
        return self._stop

    def reserve_trials(self, n):
        return min(n, self._trials)

    def reserve_cycle(self):
        return True

    def reserve_agent_call(self):
        pass

    def on_cancel(self, fn):
        self.cancels.append(fn)

    def emit(self, *a, **k):
        pass

    def save(self):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("edge-" + self._testMethodName[:30])
        ORCH.reset()
        HA.use(FakeHarness())
        LC.reset()

    def tearDown(self):
        ORCH.reset()
        HA.use(None)
        LC.reset()

    def go(self, c):
        return asyncio.run(c)


class EngineEdges(Base):
    def test_overrides_and_parallel_gpu_gate(self):
        run = ORCH.create("hpo", overrides={"budgets": {"max_trials": 7}, "step_modes": {"compare": "manual"},
                                             "approvals": {"before_training": "not_required"}})
        self.assertEqual(run["budgets"]["max_trials"], 7)
        self.assertEqual(run["steps"]["compare"]["mode"], "manual")
        d = wf([{"id": "h", "type": "hpo.run", "mode": "automatic", "params": {
            "search_space": {"x": {"type": "bool"}}, "objectives": [{"name": "loss", "direction": "minimize"}], "max_trials": 2,
            "parallel": 2, "objective": {"kind": "analytic", "function": "quadratic", "gpu": True}}}], outputs={},
            approvals={"before_parallel_gpu_trials": "required", "before_training": "not_required"})
        r = ORCH.create(definition=d)
        self.assertEqual(ORCH._gates(r, "h"), (True, False))

    def test_start_paused_without_timestamp_and_double_pause(self):
        async def body():
            r = ORCH.create(definition=wf([{"id": "a", "type": "test.sleep"}], outputs={}))
            r["status"] = "PAUSED"
            ORCH.start(r["id"])
            await until(r, "SUCCEEDED")
            p = ORCH.create(definition=wf([{"id": "a", "type": "test.sleep", "params": {"s": 0.3}}], outputs={}))
            ORCH.start(p["id"])
            ORCH.pause(p["id"])
            await until(p, "PAUSED")
            ORCH._set_paused(p)  # already paused: no second event
            n = len([e for e in ORCH.events_since(p["id"]) if e["type"] == "workflow_paused"])
            self.assertEqual(n, 1)
            ORCH._wait(p, p["steps"]["a"], "before")
            ORCH._wait(p, p["steps"]["a"], "before")  # already waiting: idempotent
            ORCH._finish(r, "FAILED", "x")  # finishing a finished run changes nothing
            self.assertEqual(r["status"], "SUCCEEDED")
            p["status"] = "WAITING_FOR_APPROVAL"
            ORCH._settle(p)
            ORCH._settle(p)
            self.assertEqual(p["status"], "WAITING_FOR_APPROVAL")
        self.go(body())

    def test_cancel_flag_after_handler_and_fail_fast_cancels_siblings(self):
        async def body():
            r = ORCH.create(definition=wf([{"id": "a", "type": "test.sleep", "params": {"s": 0.3}}], outputs={}))
            ORCH.start(r["id"])
            await step_state(r, "a", "RUNNING")
            ORCH.rt(r["id"])["cancel"] = True  # flag set while the handler runs (cancel in progress)
            await asyncio.sleep(0.5)
            self.assertEqual(r["steps"]["a"]["output"], None)
            f = ORCH.create(definition=wf([{"id": "slow", "type": "test.sleep", "params": {"s": 3}},
                                           {"id": "boom", "type": "model.inspect", "params": {"spec": {}}}], outputs={}))
            ORCH.start(f["id"])
            await until(f, "FAILED")
            await asyncio.sleep(0.05)
            self.assertEqual(f["steps"]["slow"]["status"], "CANCELLED")
        self.go(body())

    def test_budget_exceeded_inside_a_child(self):
        TP.save({"id": "agent_child", "version": 1, "execution_mode": "bounded",
                 "steps": [{"id": "p1", "type": "agent.plan", "params": {"objective": "a"}},
                           {"id": "p2", "type": "agent.plan", "depends_on": ["p1"], "params": {"objective": "b"}}]})

        async def body():
            p = ORCH.create(definition=wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "agent_child"}}],
                                          budgets={"max_agent_calls": 1, "max_trials": 1, "max_runtime_minutes": 5,
                                                   "max_workflow_cycles": 1}, outputs={}))
            ORCH.start(p["id"])
            await until(p, "BUDGET_EXCEEDED", "FAILED")
            child = ORCH.get(p["children"][0])
            self.assertEqual(child["status"], "BUDGET_EXCEEDED")
            self.assertEqual(p["status"], "BUDGET_EXCEEDED")
        self.go(body())

    def test_custom_parent_keeps_child_mode_and_bad_child_inputs(self):
        TP.save({"id": "manual_child", "version": 1, "execution_mode": "bounded", "inputs": {"n": {"type": "integer", "default": 1}},
                 "steps": [{"id": "a", "type": "test.sleep", "params": {"s": 2.2}}]})

        async def body():
            p = ORCH.create(definition=wf([{"id": "c", "type": "workflow.call", "mode": "automatic", "params": {"workflow": "manual_child"}},
                                           {"id": "bad", "type": "workflow.call", "mode": "automatic",
                                            "params": {"workflow": "manual_child", "inputs": {"n": "many"}}}],
                                          execution_mode="custom", failure_policy="continue", outputs={}))
            ORCH.start(p["id"])
            await until(p, "FAILED", timeout=40)
            child = ORCH.get(p["steps"]["c"]["checkpoint"]["child"])
            self.assertEqual(child["execution_mode"], "bounded")  # a custom parent does not impose its mode
            self.assertEqual(p["steps"]["c"]["status"], "SUCCEEDED")  # waited > 2 s for the child (timeout branch)
            self.assertIn("input n must be integer", p["steps"]["bad"]["error"])
        self.go(body())

    def test_resume_with_a_finished_child_and_cancelled_parent_step(self):
        TP.save({"id": "quick_child", "version": 1, "execution_mode": "bounded", "steps": [{"id": "a", "type": "test.sleep"}],
                 "outputs": {"v": "steps.a.output.value"}})
        TP.save({"id": "long_child", "version": 1, "execution_mode": "bounded", "steps": [{"id": "a", "type": "test.sleep", "params": {"s": 5}}]})

        async def body():
            p = ORCH.create(definition=wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "quick_child"}}],
                                          outputs={"v": "steps.c.output.v"}))
            ORCH.start(p["id"])
            await until(p, "SUCCEEDED")
            # re-enter the handler with the checkpoint of a SUCCEEDED child: no new child, outputs reused
            ctx = EN.StepContext(ORCH, p, p["steps"]["c"], {"workflow": "quick_child"})
            out = await ORCH.run_child(ctx, "quick_child", {}, None)
            self.assertEqual(out["child_run_id"], p["children"][0])
            self.assertEqual(len(p["children"]), 1)
            q = ORCH.create(definition=wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "long_child"}}], outputs={}))
            ORCH.start(q["id"])
            while not q["children"]:
                await asyncio.sleep(0.02)
            child = ORCH.get(q["children"][0])
            await until(child, "RUNNING")
            ORCH.rt(q["id"])["steps"]["c"].cancel()  # the parent step task dies (not a researcher cancel)
            await asyncio.sleep(0.2)
            self.assertEqual(child["status"], "CANCELLED")
        self.go(body())

    def test_recovery_corners_and_pending_with_missing_child(self):
        r = ORCH.create(definition=wf([{"id": "a", "type": "human.approval"}], outputs={}))
        r["status"] = "WAITING_FOR_APPROVAL"
        ORCH.persist(r)
        ORCH.reset()
        r2 = ORCH.get(r["id"])
        self.assertEqual(r2["status"], "WAITING_FOR_APPROVAL")  # nothing was running: nothing to recover
        ORCH._recover(r2)  # second call is a no-op
        r2["children"] = ["wf-0000000abc"]
        (EN._runs_dir() / "wf-0000000abc.json").write_text("{}", "utf-8")
        with mock.patch.object(ORCH, "get", side_effect=lambda i: r2 if i == r2["id"] else (_ for _ in ()).throw(OrchestratorError("run not found"))):
            self.assertEqual(ORCH.pending(r2), [])

    def test_runtime_budget_stops_a_running_step(self):
        async def body():
            r = ORCH.create(definition=wf([{"id": "a", "type": "test.sleep", "params": {"s": 30}}],
                                          budgets={"max_runtime_minutes": 0.005, "max_trials": 1, "max_workflow_cycles": 1}, outputs={}))
            ORCH.start(r["id"])
            await step_state(r, "a", "RUNNING")
            await asyncio.sleep(0.4)
            ORCH._changed(r["id"]).set()  # wake the driver now instead of after its 5 s heartbeat
            await until(r, "BUDGET_EXCEEDED", timeout=10)
            await asyncio.sleep(0.05)
            self.assertEqual(r["steps"]["a"]["status"], "CANCELLED")
            r["status"] = "SUCCEEDED"
            ORCH._settle(r)  # a terminal run is never re-settled
            self.assertEqual(r["status"], "SUCCEEDED")
        self.go(body())

    def test_pause_with_a_finished_child_and_missing_event_log(self):
        TP.save({"id": "done_child", "version": 1, "execution_mode": "bounded", "steps": [{"id": "a", "type": "test.sleep"}]})

        async def body():
            p = ORCH.create(definition=wf([{"id": "c", "type": "workflow.call", "params": {"workflow": "done_child"}},
                                           {"id": "w", "type": "human.approval", "depends_on": ["c"]}], outputs={}))
            ORCH.start(p["id"])
            await step_state(p, "w", "WAITING_FOR_APPROVAL")
            ORCH.pause(p["id"])  # the finished child refuses the pause quietly
            self.assertEqual(p["status"], "PAUSED")
        self.go(body())
        rid = ORCH.list()[0]["id"]
        (EN._runs_dir() / f"{rid}.events.jsonl").unlink()
        ORCH.reset()
        self.assertEqual(ORCH.events_since(rid), [])

    def test_reset_survives_closed_loops(self):
        class Dead:
            def cancel(self):
                raise RuntimeError("Event loop is closed")
        ORCH.rt("wf-00000000aa")["steps"]["x"] = Dead()
        ORCH.rt("wf-00000000aa")["task"] = Dead()
        ORCH.reset()
        self.assertEqual(ORCH._rt, {})


class StepEdges(Base):
    def test_sandbox_objective_branches(self):
        from backend import sandbox
        from backend.sandbox import code_dir
        (code_dir() / "t.py").write_text("", "utf-8")
        ctx = Ctx({})
        envs = []

        def start(cmd, kind, title, env):
            envs.append(env)
            return FakeJob(running=1, out="step=1 loss=0.9\nstep=1 loss=0.9\n")

        async def body():
            with mock.patch.object(sandbox, "start_job", side_effect=start), mock.patch.object(sandbox, "stop_job"):
                gpu = ST._sandbox_objective(ctx, {"script": "t.py", "gpu": True}, "loss", True)
                await gpu({"x": 1}, 0, lambda *_: False)  # repeated step → no new report
                plain = ST._sandbox_objective(ctx, {"script": "t.py"}, "loss", False)
                await plain({"x": 1}, 0, lambda *_: False)
        self.go(body())
        self.assertNotIn("CUDA_VISIBLE_DEVICES", envs[0])
        self.assertEqual(envs[1]["CUDA_VISIBLE_DEVICES"], "")

    def test_confirm_and_configs_stop_and_no_baseline(self):
        async def mk():
            return await H.run_study({"search_space": {"x": {"type": "float", "low": 0, "high": 1}},
                                      "objectives": [{"name": "loss", "direction": "minimize"}], "max_trials": 2,
                                      "objective": {"kind": "analytic", "function": "quadratic"}}, features={"optuna_hpo": False})
        sid = self.go(mk())["study_id"]
        conf = ST.REGISTRY["evaluation.confirm"].handler
        out = self.go(conf(Ctx({"study_id": sid, "top_k": 1, "seeds": [1]})))
        self.assertNotIn("vs_baseline", out["candidates"][0])
        with self.assertRaises(ST.StepFailed):
            self.go(conf(Ctx({"study_id": sid}, stop=True)))
        rc = ST.REGISTRY["evaluation.run_configs"].handler
        with self.assertRaises(ST.StepFailed):
            self.go(rc(Ctx({"configs": [{"config": {"x": 1}}], "objective": {"kind": "analytic", "function": "quadratic"},
                            "objectives": [{"name": "loss", "direction": "minimize"}]}, stop=True)))

    def test_repeat_stops_when_asked(self):
        class Orch:
            async def run_child(self, ctx, wid, inputs, version, key="child"):
                return {"child_run_id": "wf-000000000c", "best": None}
        rep = ST.REGISTRY["workflow.repeat"].handler
        out = self.go(rep(Ctx({"workflow": "x", "max_cycles": 4}, stop=True, orch=Orch())))
        self.assertEqual(len(out["cycles"]), 1)


class SchemaHpoEdges(unittest.TestCase):
    def test_schema_corners(self):
        d = {"id": "e", "version": 1, "steps": [{"id": "Bad", "type": "research.state"}]}
        self.assertIn("steps[0]: invalid id", S.validate(d, ST.REGISTRY)[1])
        ok = {"id": "e", "version": 1, "steps": [{"id": "a", "type": "test.sleep", "params": {"value": {"$ref": "last.best"}}}]}
        self.assertEqual(S.validate(ok, ST.REGISTRY)[1], [])

    def test_conditional_chain_order_and_sampler_corners(self):
        sp = {"c": {"type": "bool", "condition": {"param": "b", "equals": True}},
              "b": {"type": "bool", "condition": {"param": "a", "equals": True}}, "a": {"type": "bool"}}
        v = H.validate_space(sp, [{"name": "loss", "direction": "minimize"}])
        self.assertTrue(v["valid"])
        self.assertEqual(H._cond_order(v["params"]), ["a", "b", "c"])
        b = H.BuiltinEngine(H.validate_space({"a": {"type": "bool"}}, [{"name": "loss", "direction": "minimize"}])["params"],
                            [{"name": "loss", "direction": "minimize"}], "random", 0, [])
        pts = [b.ask()[1] for _ in range(3)]  # only two distinct points exist: the third is a repeat after 50 tries
        self.assertEqual(len(pts), 3)

    def test_multi_objective_reports_skip_pruning_and_parallel_gather(self):
        _env.fresh_project("edge-hpo")
        objs = [{"name": "psnr", "direction": "maximize"}, {"name": "params_m", "direction": "minimize"}]
        s = asyncio.run(H.run_study({"search_space": {"width": {"type": "int", "low": 16, "high": 64}}, "objectives": objs,
                                     "max_trials": 3, "objective": {"kind": "analytic", "function": "restoration_proxy", "steps": 2,
                                                                    "delay_s": 0.01}}, features={"optuna_hpo": True}))
        self.assertEqual(s["n_complete"], 3)
        p = asyncio.run(H.run_study({"search_space": {"x": {"type": "float", "low": 0, "high": 1}},
                                     "objectives": [{"name": "loss", "direction": "minimize"}], "max_trials": 2, "parallel": 3,
                                     "objective": {"kind": "analytic", "function": "quadratic", "delay_s": 0.05}},
                                    features={"optuna_hpo": False}))
        self.assertEqual(p["n_complete"], 2)


class LifecycleEdges(unittest.TestCase):
    def setUp(self):
        LC.reset()

    def tearDown(self):
        LC.reset()
        config.save_config({"lifecycle": {"single_model_vram": True}})

    def test_ollama_entry_without_id_and_no_single_model_rule(self):
        async def ost(_):
            return {"online": True, "loaded": [{"id": None}, {"id": "m"}]}

        async def lst(_):
            return {"online": False}
        with mock.patch("backend.local_ai.ollama_status", ost), mock.patch("backend.local_ai.lmstudio_status", lst):
            self.assertEqual(list(asyncio.run(LC.resident_local(max_age=0))["ollama"]), ["m"])
        config.save_config({"lifecycle": {"single_model_vram": False, "local_background": "keep_loaded"}})
        with Fakes() as f:
            async def go():
                await LC.release(await LC.acquire("local", "ollama", "a", "background"))
                await LC.release(await LC.acquire("local", "ollama", "b", "background"))
            asyncio.run(go())
        self.assertNotIn(("ollama_unload", "a"), f.calls)  # both may stay when the rule is off
        self.assertIn("local:ollama:a", LC._res)


if __name__ == "__main__":
    unittest.main()
