"""AI Research OS acceptance suite — the eight criteria of the technical acceptance plan.

Principle: nothing is PASS because a screen shows it or an agent says it is done. Every test drives the real backend
(engine, guard, firewall, sandbox processes in a Python venv) — only the language model is fake — and records the
evidence it observed (states, event sequences, files, job counts). The report is written to
artifacts/acceptance/report.json; the dashboard ("Chi tiết nâng cao → Nghiệm thu") and `phdlab acceptance` read it.

    python tools/run_tests.py acceptance.test_research_os
"""
import _env  # noqa: F401  (must be first)
import functools
import json
import sys
import time
import unittest
from unittest import mock

from backend.agent import AIWSError, acceptance, context, dashboard, launch, orchestrator, outline, pins, runs, sessions
from backend.core import config
from backend.execution import guard, sandbox
from backend.memory import add_decision, research
from backend.providers import firewall, models as llm, research as RP

RESULTS: dict = {}
OK = "import json, os\njson.dump({'acc': 0.91}, open(os.path.join(os.environ['RUN_DIR'], 'metrics.json'), 'w'))\n"
OOM = ("import json, os, sys\nbs = int(sys.argv[sys.argv.index('--batch-size') + 1])\n"
       "if bs > 16:\n    sys.stderr.write('CUDA out of memory\\n'); sys.exit(1)\n"
       "json.dump({'acc': 0.8}, open(os.path.join(os.environ['RUN_DIR'], 'metrics.json'), 'w'))\n")


def criterion(key: str):
    """Record the test's outcome and the evidence it returns under one acceptance criterion."""
    def deco(fn):
        @functools.wraps(fn)
        def run(self):
            tid = f"{type(self).__name__}.{fn.__name__}"
            try:
                evidence = fn(self) or {}
            except BaseException as e:
                RESULTS.setdefault(key, {"tests": []})["tests"].append({"id": tid, "status": "failed", "error": str(e)[:300]})
                raise
            RESULTS.setdefault(key, {"tests": []})["tests"].append({"id": tid, "status": "passed", "evidence": evidence})
        return run
    return deco


def fake_llm(agent, system, user, max_tokens=6000):
    if "experiment that runs on one PC" in system:
        return "Plan.\n```python path=main.py\n" + OK + "```\n```phdlab-run\npython main.py\n```"
    return "Findings with a source (Doe, 2020) and [S1]."


async def fake_stream(agent, system, messages, max_tokens=0, temperature=0.3):
    yield ("delta", "ok")
    yield ("meta", {})


def tearDownModule():
    if RESULTS:
        acceptance.write_report(RESULTS, {"suite": "tests/acceptance/test_research_os.py"})


class Base(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("acc-" + self._testMethodName[:28])
        guard.reset()
        config.save_config({"runs": {"web_search": False}})
        sandbox.save_settings({"mode": "local", "python_mode": "existing", "python_base": sys.executable, "auto_deps": False,
                               "gpu": False})
        provider_for = launch.provider_for
        for p in (mock.patch.object(RP, "app_complete", side_effect=fake_llm), mock.patch.object(llm, "stream_agent", fake_stream),
                  mock.patch.object(launch, "provider_for", side_effect=lambda skill: "app" if skill["provider"] == "feynman" else provider_for(skill))):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(guard.reset)

    def script(self, name, body):
        (sandbox.code_dir() / name).write_text(body, "utf-8")


class P0_Permissions(Base):
    @criterion("permissions_resources")
    def test_nothing_risky_runs_without_approval(self):
        self.script("ok.py", OK)
        before = len(sandbox.list_runs(100))
        r = runs.create("experiment", "e", inputs={"command": "python ok.py"}, risk=2)
        time.sleep(0.5)
        self.assertEqual(r["status"], "APPROVAL_PENDING")
        self.assertEqual(len(sandbox.list_runs(100)), before)  # no process was started
        rid = runs.create("code", "c", "x", {"task": "x"}, risk=2)["id"]
        runs.update(rid, lambda x: x.update(status="RUNNING"))
        runs.spawn(rid)
        self.assertIn("approval", runs.wait(rid, 20)["steps"][0]["error"])  # defence in depth: the executor refuses too
        return {"approval_state": r["status"], "jobs_started": 0, "code_without_approval": "refused"}

    @criterion("permissions_resources")
    def test_hardware_guard_and_budget(self):
        guard.try_acquire("gpu", "training-A", gpu_check=False)
        with self.assertRaises(guard.Busy):
            guard.try_acquire("gpu", "training-B", gpu_check=False)
        guard.release("gpu", "training-A")
        self.script("slow.py", "import time; time.sleep(30)")
        rid = runs.create("experiment", "e", inputs={"command": "python slow.py"}, risk=2, budget={"max_minutes": 0.03})["id"]
        runs.approve(rid)
        r = runs.wait(rid, 40)
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        return {"second_gpu_job": "blocked", "budget_overrun": r["steps"][0]["error"]}

    @criterion("permissions_resources")
    def test_cli_agents_cannot_reach_the_app(self):
        src = str((config.ROOT / "backend" / "app.py")).replace("\\", "/")
        self.assertEqual(firewall.violation(f"Read {src}"), src)
        with self.assertRaises(firewall.FirewallError):
            firewall.check("config.json", "data")
        with self.assertRaises(firewall.FirewallError):
            firewall.public_url("http://127.0.0.1:8765/api/config")
        return {"app_source": "denied", "secrets": "denied", "local_network": "denied"}


class P0_Progress(Base):
    @criterion("progress_tracking")
    def test_one_timeline_for_ui_cli_and_chat(self):
        s = sessions.create("t")
        rid = runs.create("research", "lit", "x", {"topic": "x"}, session_id=s["id"], risk=0)["id"]
        r = runs.wait(rid, 30)
        ev = runs.events(rid)
        self.assertEqual([e["seq"] for e in ev], list(range(1, len(ev) + 1)))
        started = [e for e in ev if e["type"] == "step.started"]
        for e in started:
            for k in ("step", "provider", "idempotency_key"):
                self.assertTrue(e["data"][k])
        for st in r["steps"]:
            self.assertTrue(st["started"] and st["ended"] and st["provider"])
        self.assertIn("run.updated", [e["type"] for e in sessions.events(s["id"])])
        self.assertEqual(dashboard.status()["recent_runs"][0]["id"], rid)
        return {"events": len(ev), "steps": [f"{x['id']}:{x['provider']}:{x['status']}" for x in r["steps"]],
                "states": [h["to"] for h in r["history"]]}


class P0_Context(Base):
    @criterion("context_recovery")
    def test_a_new_session_after_a_restart_knows_the_project(self):
        outline.update({"topic": "Lightweight ViT for edge devices"})
        add_decision("Use ImageNet-100 with 3 seeds", "constraint")
        research.add_hypothesis("Token pruning keeps accuracy within 0.5 points")
        s1 = sessions.create("first")
        sessions.add_message(s1["id"], "user", "We decided on pruning.")
        # "restart": every in-process cache is dropped
        sessions.reset_memory()
        runs.reset_memory()
        context.clear_cache()
        from backend.memory import cache
        cache.clear_all()
        s2 = sessions.create("second")
        from backend.agent.policy import effective
        c = context.compile(sessions.get(s2["id"]), "what did we decide?", effective(sessions.get(s2["id"])))
        for needle in ("Lightweight ViT", "ImageNet-100", "Token pruning"):
            self.assertIn(needle, c["text"])
        return {"sources": len(c["manifest"]["sources"]), "recovered": ["outline", "decision", "hypothesis"]}


class P0_Recovery(Base):
    @criterion("workflow_recovery")
    def test_oom_is_recovered_without_duplicate_jobs(self):
        self.script("train.py", OOM)
        rid = runs.create("experiment", "e", inputs={"command": "python train.py --batch-size 32 --grad-accum 1"}, risk=2,
                          budget={"max_retries": 1})["id"]
        runs.approve(rid)
        r = runs.wait(rid, 60)
        self.assertEqual(r["status"], "COMPLETED")
        hist = [h["to"] for h in r["history"]]
        self.assertTrue({"FAILED", "RECOVERING"} <= set(hist))
        jobs = [j for j in sandbox.list_runs(50) if (j.get("cmd") or "").startswith("python train.py")]
        self.assertEqual(len(jobs), 2)
        return {"states": hist, "jobs": len(jobs), "change": r["steps"][0]["spec"]["command"]}

    @criterion("workflow_recovery")
    def test_restart_reuses_the_finished_job(self):
        self.script("ok.py", OK)
        rid = runs.create("experiment", "e", inputs={"command": "python ok.py"}, risk=2, start=False)["id"]
        runs.update(rid, lambda x: (x["approval"].update(status="approved"), x.update(status="RUNNING"),
                                    x["steps"][0].update(status="running", attempt=1, idempotency_key=f"{rid}:S1:1")))
        job = sandbox.start_job("python ok.py", "run", "before restart", meta={"idempotency_key": f"{rid}:S1:1"})
        while job.status == "running":
            time.sleep(0.1)
        time.sleep(0.3)
        n = len(sandbox.list_runs(100))
        runs.recover_all()
        r = runs.wait(rid, 30)
        self.assertEqual((r["status"], len(sandbox.list_runs(100))), ("COMPLETED", n))
        return {"after_restart": r["status"], "duplicate_jobs": 0}


class P1_Prompt(Base):
    @criterion("prompt_workflow")
    def test_plain_prompts_trigger_workflows(self):
        s = sessions.create("t")
        orchestrator.start(s["id"], "tìm tài liệu về token pruning cho ViT")
        m = [x for x in sessions.get(s["id"])["messages"] if x.get("run_id")]
        self.assertTrue(m)
        self.assertEqual(runs.wait(m[-1]["run_id"], 30)["status"], "COMPLETED")
        orchestrator.start(s["id"], "chạy thử ý tưởng MLP nhỏ trên dữ liệu tổng hợp")
        ap = [a for a in sessions.get(s["id"])["approvals"] if a["name"] == "start_run"]
        self.assertEqual(ap[0]["args"]["skill"], "idea")
        self.assertEqual(launch.route("viết phần results theo văn phong IEEE")["skill"], "write")
        return {"read_only": "auto-started /lit", "risky": "proposal /idea awaiting approval", "tool_chosen_by_user": False}


class P1_Providers(Base):
    @criterion("provider_swap")
    def test_swapping_providers_keeps_the_state(self):
        with mock.patch.object(RP, "pick", return_value=("feynman", "")), \
                mock.patch.object(RP, "run_feynman", side_effect=RP.ProviderUnavailable("quota exceeded")):
            rid = runs.create("research", "lit", "x", {"topic": "x"}, risk=0, provider="feynman", budget={"max_retries": 0})["id"]
            r = runs.wait(rid, 30)
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        runs.swap_provider(rid, "S1", "app")
        r = runs.wait(runs.resume(rid, accept_proposal=False)["id"], 30)
        self.assertEqual((r["status"], r["steps"][0]["provider"]), ("COMPLETED", "app"))
        async def local_engine(cfg, eng, system, msgs, *a, **k):
            yield f"answer from {eng} with {len(msgs)} messages"
        p = mock.patch.object(llm, "_stream_engine", local_engine)
        p.start()
        self.addCleanup(p.stop)
        s = sessions.create("t")
        orchestrator.start(s["id"], "hello")
        sessions.update(s["id"], lambda x: x["settings"].update(provider="app:local"))
        for _ in range(100):
            if sessions.get(s["id"])["turns"][-1]["status"] == "completed":
                break
            time.sleep(0.03)
        orchestrator.start(s["id"], "and now?")
        for _ in range(100):
            if sessions.get(s["id"])["turns"][-1]["status"] == "completed":
                break
            time.sleep(0.03)
        msgs = sessions.get(s["id"])["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user", "assistant"])
        self.assertIn("3 messages", msgs[-1]["content"])  # the new provider received the whole conversation
        return {"run_provider": "feynman → app", "conversation_messages_kept": len(msgs)}


class P1_Evidence(Base):
    @criterion("evidence")
    def test_claims_need_evidence(self):
        self.script("nm.py", "print('no metrics')")
        rid = runs.create("experiment", "e", inputs={"command": "python nm.py"}, risk=2)["id"]
        runs.approve(rid)
        r = runs.wait(rid, 30)
        self.assertNotIn("COMPLETED", [h["to"] for h in r["history"]])
        with self.assertRaises(AIWSError):
            pins.add("result", "unbacked", "acc 99%", "verified", {"run_id": ""})
        lit = runs.wait(runs.create("research", "lit", "x", {"topic": "x"}, risk=0)["id"], 30)
        led = json.loads((config.data_dir() / next(o["path"] for o in lit["outputs"] if "ledger" in o["path"])).read_text("utf-8"))
        self.assertTrue(all(c["status"] == "unverified" for c in led["citations"]))
        return {"no_metrics": r["status"], "verified_pin_without_run": "refused",
                "unmatched_citations": len(led["citations"])}


class P1_EndToEnd(Base):
    @criterion("research_code_experiment")
    def test_idea_to_measured_result(self):
        rid = runs.create("idea", "/idea mlp", "mlp", {"idea": "tiny mlp"}, risk=2)["id"]
        runs.approve(rid)
        r = runs.wait(rid, 90)
        self.assertEqual(r["status"], "COMPLETED", r["reason"])
        m = next(s for s in r["steps"] if s["kind"] == "verify_metrics")["result"]
        self.assertEqual(m["label"], "MEASURED")
        return {"steps": [f"{s['kind']}:{s['provider']}" for s in r["steps"]], "metrics": m["metrics"], "job": m["job_id"]}


class Simulation90Days(Base):
    """The 90-day experience simulation as a dry run on the real engine (tests/acceptance/simulation.py)."""

    def test_dry_run(self):
        from acceptance import simulation
        rid = simulation.create()["id"]
        r = runs.wait(rid, 60)
        self.assertEqual(r["status"], "COMPLETED")
        self.assertTrue(r["synthetic"])
        hist = [h["to"] for h in r["history"]]
        self.assertTrue({"FAILED", "RECOVERING"} <= set(hist))
        day53 = next(s for s in r["steps"] if s["spec"].get("day") == 53)
        self.assertEqual((day53["attempt"], day53["spec"]["command"].split("--batch-size ")[1].split()[0]), (2, "32"))
        ev = runs.events(rid)
        self.assertEqual(sorted(e["data"]["checkpoint"] for e in ev if e["data"].get("checkpoint")), [1, 21, 48, 70, 88])
        lines = (runs.out_dir(rid) / "simulation" / "executions.jsonl").read_text("utf-8").splitlines()
        keys = [json.loads(x)["step"] for x in lines]
        self.assertEqual(len(keys), len(set(keys)))  # every step executed once (the OOM attempt fails before its side effect)
        rep = (runs.out_dir(rid) / "simulation" / "lightweight_vit" / "reports" / "acceptance_evaluation.md").read_text("utf-8")
        self.assertIn("SYNTHETIC", rep)
        verdicts = {c["verdict"] for c in r["steps"][-1]["result"]["acceptance"]}
        self.assertTrue(verdicts <= {"PASS", "FAIL", "SIMULATED", "NOT VERIFIED"})
        self.assertIn("Gap report", (runs.out_dir(rid) / "simulation" / "lightweight_vit" / "reports" / "gap_report.md").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
