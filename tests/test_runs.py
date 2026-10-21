"""Research runs: the state machine, approvals, the hardware guard, budgets, OOM recovery, durable execution (idempotent
restart), provider swap, cancellation and the link to the conversation. Experiments run REAL processes in the code
project's Python environment; only the language model is fake."""
import _env  # noqa: F401  (must be first)
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.agent import AIWSError, runs, sessions
from backend.core import config
from backend.execution import guard, sandbox
from backend.providers import research as RP

OK = "import json, os\njson.dump({'acc': 0.91, 'loss': 0.2}, open(os.path.join(os.environ['RUN_DIR'], 'metrics.json'), 'w'))\nprint('done')\n"
OOM = ("import json, os, sys\nbs = int(sys.argv[sys.argv.index('--batch-size') + 1])\n"
       "if bs > 32:\n    sys.stderr.write('RuntimeError: CUDA out of memory. Tried to allocate 2 GiB\\n'); sys.exit(1)\n"
       "json.dump({'acc': 0.8, 'batch': bs}, open(os.path.join(os.environ['RUN_DIR'], 'metrics.json'), 'w'))\n")
NOMETRICS = "print('hello')\n"
SLOW = "import time\ntime.sleep(30)\n"


def fake_llm(agent, system, user, max_tokens=6000):
    if "experiment that runs on one PC" in system:
        return ("Plan.\n```python path=x/main.py\n" + OK + "```\n```phdlab-run\npython other/main.py\n```")
    if "Write the code for this experiment" in system:
        return "```python path=main.py\n" + OK + "```"
    if agent == "reviewer":
        return "## Review\n- major: baseline missing"
    return f"[{agent}] literature: see (Smith et al., 2020), doi 10.1000/xyz123 and [S1] and [S9]."


class RunsBase(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("runs-" + self._testMethodName[:24])
        guard.reset()
        sandbox.save_settings({"mode": "local", "python_mode": "existing", "python_base": sys.executable, "auto_deps": False,
                               "gpu": False})
        config.save_config({"runs": {"web_search": False}})
        self.p = mock.patch.object(RP, "app_complete", side_effect=fake_llm)
        self.p.start()
        self.addCleanup(self.p.stop)
        self.addCleanup(guard.reset)

    def script(self, name, body):
        (sandbox.code_dir() / name).write_text(body, "utf-8")

    def wait(self, rid, statuses=("COMPLETED", "CANCELLED", "NEEDS_USER_ACTION", "APPROVAL_PENDING"), timeout=60, idle=True):
        end = time.time() + timeout
        while time.time() < end:
            r = runs.get(rid)
            with runs._lock:
                driving = rid in runs._drivers
            if r["status"] in statuses and not (idle and driving):
                return r
            time.sleep(0.05)
        self.fail(f"run {rid} stuck in {runs.get(rid)['status']}")

    def exp(self, command, **kw):
        r = runs.create("experiment", "exp", "goal", {"command": command}, risk=2, **kw)
        self.assertEqual(r["status"], "APPROVAL_PENDING")
        runs.approve(r["id"])
        return r["id"]


class StateMachine(RunsBase):
    def test_transitions_are_enforced(self):
        r = runs.create("research", "t", "topic", {"topic": "x"}, risk=0, start=False)
        self.assertEqual(r["status"], "PLANNED")
        with self.assertRaisesRegex(AIWSError, "not allowed"):
            runs.transition(r["id"], "COMPLETED")
        self.assertEqual([h["to"] for h in runs.get(r["id"])["history"]], ["CREATED", "PLANNED"])
        runs.transition(r["id"], "PLANNED", "same state just updates the reason")
        self.assertEqual(runs.get(r["id"])["reason"], "same state just updates the reason")

    def test_create_validation(self):
        with self.assertRaises(AIWSError):
            runs.create("nope", "t")
        with self.assertRaises(AIWSError):
            runs.create("simulate", "t")  # needs explicit steps
        with self.assertRaises(AIWSError):
            runs.create("research", "t", steps=[{"kind": "teleport"}])
        with self.assertRaises(AIWSError):
            runs.get("RR-zz")
        with self.assertRaises(AIWSError):
            runs.get("RR-00000000")

    def test_low_risk_runs_start_and_complete(self):
        r = runs.create("research", "/lit vit", "vit", {"topic": "vit"}, risk=0, budget={"max_retries": 2})
        r = self.wait(r["id"])
        self.assertEqual(r["status"], "COMPLETED")
        self.assertEqual(r["budget"]["max_retries"], 2)
        self.assertEqual([s["status"] for s in r["steps"]], ["done"] * 3)
        self.assertEqual([h["to"] for h in r["history"]], ["CREATED", "PLANNED", "RUNNING", "VERIFYING", "RUNNING", "COMPLETED"])
        paths = [o["path"] for o in r["outputs"]]
        self.assertTrue(any(p.endswith("research_report.md") for p in paths))
        ledger = json.loads((config.data_dir() / next(p for p in paths if p.endswith("evidence_ledger.json"))).read_text("utf-8"))
        st = {c["citation"]: c["status"] for c in ledger["citations"]}
        self.assertEqual(st["[S1]"], "unverified")  # no search ran → nothing retrieved
        self.assertEqual(st["(Smith et al., 2020)"], "unverified")
        self.assertIn("10.1000/xyz123", st)
        ev = runs.events(r["id"])
        self.assertEqual([e["seq"] for e in ev], list(range(1, len(ev) + 1)))
        self.assertTrue(any(e["type"] == "step.started" and e["data"]["idempotency_key"].endswith(":S1:1") for e in ev))
        self.assertEqual(runs.list_runs("COMPLETED")[0]["id"], r["id"])
        self.assertEqual(runs.list_runs(session_id="as-0000000000"), [])

    def test_citations_matching_the_library_and_the_search(self):
        from backend.knowledge import library
        library.save_library({"s.pdf": {"key": "smith2020", "file": "s.pdf", "title": "T", "authors": ["J. Smith"], "year": "2020",
                                        "doi": "10.1000/xyz123", "include": True}})
        src = [{"id": "S1", "kind": "paper", "title": "Real paper", "url": "https://openalex.org/W1", "authors": ["A"], "year": 2024}]
        config.save_config({"runs": {"web_search": True}})
        with mock.patch("backend.knowledge.websearch.search", return_value={"sources": src, "errors": ["arXiv"]}):
            r = self.wait(runs.create("research", "lit", "vit", {"topic": "vit"}, risk=0)["id"])
        ledger = json.loads((config.data_dir() / next(o["path"] for o in r["outputs"] if o["path"].endswith("evidence_ledger.json")))
                            .read_text("utf-8"))
        st = {c["citation"]: c["status"] for c in ledger["citations"]}
        self.assertEqual((st["[S1]"], st["[S9]"], st["(Smith et al., 2020)"]), ("retrieved", "unverified", "in_library"))
        self.assertTrue(any(o["path"].endswith("sources.json") for o in r["outputs"]))
        self.assertTrue(any("nguồn tìm kiếm lỗi" in e["data"].get("message", "") for e in runs.events(r["id"])))

    def test_search_failure_is_logged_not_fatal(self):
        config.save_config({"runs": {"web_search": True}})
        with mock.patch("backend.knowledge.websearch.search", side_effect=RuntimeError("offline")):
            r = self.wait(runs.create("research", "lit", "vit", {"topic": "vit"}, risk=0)["id"])
        self.assertEqual(r["status"], "COMPLETED")
        self.assertTrue(any("tìm bài báo thất bại" in e["data"].get("message", "") for e in runs.events(r["id"])))

    def test_model_failure_is_retried_then_asks(self):
        calls = []

        def flaky(agent, system, user, max_tokens=6000):
            calls.append(1)
            if len(calls) == 1:
                raise ConnectionError("network down")
            return "fine (Doe, 2021)"
        with mock.patch.object(RP, "app_complete", side_effect=flaky):
            r = self.wait(runs.create("research", "lit", "x", {"topic": "x"}, risk=0)["id"])
        self.assertEqual(r["status"], "COMPLETED")
        self.assertIn("RECOVERING", [h["to"] for h in r["history"]])
        with mock.patch.object(RP, "app_complete", return_value="   "):
            r = self.wait(runs.create("research", "lit", "x", {"topic": "x"}, risk=0, budget={"max_retries": 0})["id"])
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        self.assertEqual(r["proposal"]["kind"], "retry")

    def test_approval_and_rejection(self):
        r = runs.create("experiment", "e", inputs={"command": "python ok.py"}, risk=2)
        self.assertTrue(r["approval"]["required"])
        self.assertEqual(r["next_decision"], "Duyệt để bắt đầu chạy?")
        with self.assertRaises(AIWSError):
            runs.resume(r["id"])
        c = runs.cancel(r["id"])
        self.assertEqual((c["status"], c["approval"]["status"]), ("CANCELLED", "rejected"))
        with self.assertRaises(AIWSError):
            runs.approve(r["id"])
        with self.assertRaises(AIWSError):
            runs.cancel(r["id"])

    def test_auto_approve_threshold_is_a_setting(self):
        config.save_config({"runs": {"auto_approve_risk": 0}})
        r = runs.create("latex", "pdf", risk=1, start=False)
        self.assertEqual(r["status"], "APPROVAL_PENDING")


class Experiments(RunsBase):
    def test_measured_metrics_complete_the_run(self):
        self.script("ok.py", OK)
        r = self.wait(self.exp("python ok.py"))
        self.assertEqual(r["status"], "COMPLETED")
        m = next(s for s in r["steps"] if s["kind"] == "verify_metrics")["result"]
        self.assertEqual((m["label"], m["metrics"]["acc"]), ("MEASURED", 0.91))
        job = next(s for s in r["steps"] if s["kind"] == "experiment")["result"]["job_id"]
        self.assertEqual(sandbox.get_run(job)["research_run"], r["id"])

    def test_no_metrics_never_completes(self):
        self.script("nm.py", NOMETRICS)
        r = self.wait(self.exp("python nm.py"))
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        self.assertIn("không có metrics hợp lệ", r["next_decision"] + r["reason"])
        self.assertNotIn("COMPLETED", [h["to"] for h in r["history"]])

    def test_a_crashing_script_asks_the_researcher(self):
        self.script("bad.py", "raise SystemExit(3)\n")
        r = self.wait(self.exp("python bad.py"))
        self.assertEqual((r["status"], r["proposal"]["kind"]), ("NEEDS_USER_ACTION", "manual"))
        self.script("bad.py", OK)  # the researcher fixed it in VS Code
        r = self.wait(runs.resume(r["id"], accept_proposal=False)["id"])
        self.assertEqual(r["status"], "COMPLETED")

    def test_cuda_oom_is_recovered_with_a_recorded_change(self):
        self.script("train.py", OOM)
        r = self.wait(self.exp("python train.py --batch-size 64 --grad-accum 1"))
        self.assertEqual(r["status"], "COMPLETED")
        hist = [h["to"] for h in r["history"]]
        self.assertEqual(hist[hist.index("FAILED"):hist.index("FAILED") + 3], ["FAILED", "RECOVERING", "RUNNING"])
        st = next(s for s in r["steps"] if s["kind"] == "experiment")
        self.assertEqual((st["attempt"], st["spec"]["command"]), (2, "python train.py --batch-size 32 --grad-accum 2"))
        self.assertIn("batch size 64 → 32", " ".join(st["notes"]))
        ana = next(e for e in runs.events(r["id"]) if e["type"] == "run.analysis")
        self.assertEqual(ana["data"]["proposal"]["change"], {"batch_size": [64, 32]})
        jobs = [j for j in sandbox.list_runs(50) if j.get("cmd", "").startswith("python train.py")]
        self.assertEqual(len(jobs), 2)  # one failed + one recovered — no duplicate training job

    def test_oom_without_budget_waits_for_approval_then_resumes(self):
        self.script("train.py", OOM)
        rid = runs.create("experiment", "e", inputs={"command": "python train.py --batch-size 64"}, risk=2,
                          budget={"max_retries": 0})["id"]
        runs.approve(rid)
        r = self.wait(rid)
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        self.assertEqual(r["proposal"]["patch"]["command"], "python train.py --batch-size 32")
        self.assertIn("KHÔNG còn tương đương", r["proposal"]["text"])
        r = self.wait(runs.resume(rid, accept_proposal=True)["id"])
        self.assertEqual(r["status"], "COMPLETED")

    def test_oom_proposals_when_no_batch_flag_or_batch_one(self):
        r = {"inputs": {"command": "python t.py"}}
        self.assertEqual(runs._oom(r, {"spec": {}}, None)["patch"], {})
        self.assertIn("batch size đã là 1", runs._oom(r, {"spec": {"command": "BATCH_SIZE=1 python t.py"}}, None)["text"])
        p = runs._oom(r, {"spec": {"command": "BATCH_SIZE=8 python t.py"}}, None)
        self.assertEqual(p["patch"]["command"], "BATCH_SIZE=4 python t.py")

    def test_hardware_guard_blocks_until_the_slot_is_free(self):
        self.script("ok.py", OK)
        guard.try_acquire("cpu", "another-run")
        rid = self.exp("python ok.py")
        self.wait(rid, ("BLOCKED",), 20, idle=False)
        self.assertIn("in use by another-run", runs.get(rid)["reason"])
        guard.release("cpu", "another-run")
        self.assertEqual(self.wait(rid)["status"], "COMPLETED")

    def test_budget_stops_a_long_job(self):
        self.script("slow.py", SLOW)
        rid = runs.create("experiment", "e", inputs={"command": "python slow.py"}, risk=2, budget={"max_minutes": 0.03})["id"]
        runs.approve(rid)
        r = self.wait(rid, timeout=40)
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        self.assertIn("budget", next(s for s in r["steps"] if s["kind"] == "experiment")["error"])

    def test_budget_exhausted_before_a_step(self):
        rid = runs.create("research", "t", "x", {"topic": "x"}, risk=0, start=False)["id"]
        runs.update(rid, lambda x: x["steps"][0].update(active_s=10 ** 6))
        runs.transition(rid, "RUNNING")
        runs.spawn(rid)
        r = self.wait(rid)
        self.assertEqual((r["status"], r["proposal"]["kind"]), ("NEEDS_USER_ACTION", "budget"))

    def test_cancel_stops_the_job(self):
        self.script("slow.py", SLOW)
        rid = self.exp("python slow.py")
        end = time.time() + 20
        while time.time() < end and not any(s["result"].get("job_id") for s in runs.get(rid)["steps"]):
            time.sleep(0.05)
        r = runs.cancel(rid)
        self.assertEqual(r["status"], "CANCELLED")
        self.wait(rid, ("CANCELLED",))
        job = next(s for s in r["steps"] if s["kind"] == "experiment")["result"]["job_id"]
        end = time.time() + 15
        while time.time() < end and sandbox.get_run(job).get("status") == "running":
            time.sleep(0.1)
        self.assertEqual(sandbox.get_run(job)["status"], "stopped")

    def test_docker_is_used_only_when_linux_is_needed(self):
        self.script("ok.py", OK)
        seen = {}
        real = sandbox.start_job

        def spy(cmd, kind="run", title="", extra_env=None, mode="", meta=None):
            seen["mode"] = mode
            return real(cmd, kind, title, extra_env, "local", meta)
        with mock.patch.object(sandbox, "start_job", side_effect=spy):
            self.wait(self.exp("python ok.py"))
            self.assertEqual(seen["mode"], "local")
            rid = runs.create("experiment", "e", inputs={"command": "python ok.py", "needs_linux": True}, risk=2)["id"]
            runs.approve(rid)
            self.wait(rid)
            self.assertEqual(seen["mode"], "docker")

    def test_sandbox_refusal_and_missing_command(self):
        with mock.patch.object(sandbox, "start_job", side_effect=sandbox.VramBusyError("vram", ["m"], 1)):
            r = self.wait(self.exp("python ok.py"), timeout=30)
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        rid = runs.create("experiment", "e", inputs={}, risk=2)["id"]
        runs.approve(rid)
        self.assertIn("no command", self.wait(rid)["steps"][0]["error"])

    def test_experiment_refuses_without_approval(self):
        rid = runs.create("experiment", "e", inputs={"command": "python ok.py"}, risk=2)["id"]
        runs.update(rid, lambda x: x.update(status="RUNNING"))
        runs.spawn(rid)
        r = self.wait(rid)
        self.assertIn("approval", r["steps"][0]["error"])


class Durable(RunsBase):
    """The server stops while a run works; recover_all() on the next start must not lose state or repeat side effects."""

    def crashed(self, command, key_attempt=1):
        rid = runs.create("experiment", "e", inputs={"command": command}, risk=2, start=False)["id"]
        runs.update(rid, lambda x: (x["approval"].update(status="approved"), x.update(status="RUNNING", current="S1"),
                                    x["steps"][0].update(status="running", attempt=key_attempt,
                                                         idempotency_key=f"{rid}:S1:{key_attempt}")))
        return rid

    def test_a_finished_job_is_reused_not_repeated(self):
        self.script("ok.py", OK)
        rid = self.crashed("python ok.py")
        job = sandbox.run_blocking("python ok.py", 60, "run", "before restart")
        meta = json.loads((job.run_dir / "run.json").read_text("utf-8"))
        meta["idempotency_key"] = f"{rid}:S1:1"
        (job.run_dir / "run.json").write_text(json.dumps(meta), "utf-8")
        before = len(sandbox.list_runs(100))
        self.assertEqual(runs.recover_all(), [{"id": rid, "action": "resumed"}])
        r = self.wait(rid)
        self.assertEqual(r["status"], "COMPLETED")
        self.assertEqual(len(sandbox.list_runs(100)), before)  # no new job
        self.assertEqual(r["steps"][0]["result"]["job_id"], job.id)
        self.assertTrue(any(e["type"] == "run.restart" for e in runs.events(rid)))

    def test_a_lost_job_is_retried_with_a_new_key(self):
        self.script("ok.py", OK)
        rid = self.crashed("python ok.py")
        runs.recover_all()
        r = self.wait(rid)
        self.assertEqual((r["status"], r["steps"][0]["attempt"], r["usage"]["retries"]), ("COMPLETED", 2, 1))
        self.assertTrue(any(e["type"] == "step.lost" for e in runs.events(rid)))

    def test_a_job_stopped_by_the_shutdown_counts_as_lost(self):
        self.script("slow.py", SLOW)
        rid = self.crashed("python slow.py")
        job = sandbox.start_job("python slow.py", "run", "x", meta={"idempotency_key": f"{rid}:S1:1"})
        time.sleep(0.5)
        self.assertEqual(sandbox.stop_all("shutdown"), [job.id])
        end = time.time() + 15
        while time.time() < end and (runs._find_job(f"{rid}:S1:1") or {}).get("stopped_by") != "shutdown":
            time.sleep(0.1)
        self.assertEqual(runs._job_state(runs.get(rid)["steps"][0]), "lost")

    def test_a_job_still_alive_waits_for_the_researcher(self):
        rid = self.crashed("python x.py")
        d = sandbox.runs_dir() / "fake-job-0001"
        d.mkdir(parents=True)
        (d / "run.json").write_text(json.dumps({"id": "fake-job-0001", "status": "running", "pid": os.getpid(),
                                                "idempotency_key": f"{rid}:S1:1"}), "utf-8")
        self.assertEqual(runs.recover_all(), [{"id": rid, "action": "needs_user"}])
        self.assertEqual(runs.get(rid)["status"], "NEEDS_USER_ACTION")

    def test_no_retry_left_after_a_lost_job(self):
        rid = self.crashed("python x.py")
        runs.update(rid, lambda x: x["budget"].update(max_retries=0))
        self.assertEqual(runs.recover_all(), [{"id": rid, "action": "needs_user"}])
        self.assertEqual(runs.get(rid)["proposal"]["kind"], "retry")

    def test_an_llm_step_simply_continues(self):
        rid = runs.create("research", "t", "x", {"topic": "x"}, risk=0, start=False)["id"]
        runs.update(rid, lambda x: (x.update(status="VERIFYING"), x["steps"][0].update(status="running", attempt=1)))
        (runs._dir() / "RR-broken0.json").write_text("{not json", "utf-8")
        self.assertEqual(runs.recover_all(), [{"id": rid, "action": "resumed"}])
        self.assertEqual(self.wait(rid)["status"], "COMPLETED")
        self.assertEqual(runs.recover_all(), [])


class Providers(RunsBase):
    def ready(self, ids):
        return mock.patch.object(RP, "describe", side_effect=lambda pid, cfg=None, fresh=False: {
            "id": pid, "ready": pid in ids, "state": "READY" if pid in ids else "NOT_CONFIGURED", "detail": "d", "label": pid,
            "setup": [], "category": "research"})

    def test_an_unconfigured_provider_falls_back_visibly(self):
        with self.ready(set()):
            r = self.wait(runs.create("research", "lit", "x", {"topic": "x", "workflow": "lit"}, risk=0, provider="feynman")["id"])
        s = r["steps"][0]
        self.assertEqual((r["status"], s["provider"], s["resource"]), ("COMPLETED", "app", "cloud"))
        self.assertIn("NOT_CONFIGURED", s["notes"][0])
        self.assertTrue(any(e["type"] == "step.provider" for e in runs.events(r["id"])))

    def test_feynman_runs_the_workflow(self):
        def fake_feynman(task, workflow, prompt, ctx, outdir, cancelled=None, timeout_s=0):
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / "brief.md").write_text("brief", "utf-8")
            self.assertEqual(workflow, "lit")
            self.assertIn("Research outline", ctx)
            return {"text": "Feynman says (Doe, 2022)", "files": ["brief.md"]}
        with self.ready({"feynman"}), mock.patch.object(RP, "run_feynman", side_effect=fake_feynman):
            r = self.wait(runs.create("research", "lit", "x", {"topic": "x", "workflow": "lit"}, risk=0, provider="feynman")["id"])
        self.assertEqual((r["status"], r["steps"][0]["provider"], r["steps"][0]["resource"]), ("COMPLETED", "feynman", "cli"))
        self.assertTrue(any(o["path"].endswith("feynman/brief.md") for o in r["outputs"]))

    def test_swap_provider_keeps_completed_work(self):
        with self.ready({"feynman"}), mock.patch.object(RP, "run_feynman", side_effect=RP.ProviderUnavailable("quota")):
            rid = runs.create("research", "lit", "x", {"topic": "x"}, risk=0, provider="feynman", budget={"max_retries": 0})["id"]
            r = self.wait(rid)
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        with self.assertRaises(AIWSError):
            runs.swap_provider(rid, "S1", "nope")
        with self.assertRaises(AIWSError):
            runs.swap_provider(rid, "S9", "app")
        r = runs.swap_provider(rid, "S1", "app")
        self.assertEqual(r["steps"][0]["provider"], "app")
        r = self.wait(runs.resume(rid, accept_proposal=False)["id"])
        self.assertEqual(r["status"], "COMPLETED")
        with self.assertRaisesRegex(AIWSError, "only a pending or failed"):
            runs.swap_provider(rid, "S1", "feynman")

    def test_resume_with_a_patch(self):
        self.script("bad.py", "raise SystemExit(2)\n")
        self.script("ok.py", OK)
        r = self.wait(self.exp("python bad.py"))
        r = self.wait(runs.resume(r["id"], accept_proposal=False, patch={"command": "python ok.py", "provider": "python"})["id"])
        self.assertEqual(r["status"], "COMPLETED")


class Pipelines(RunsBase):
    def test_idea_runs_research_code_experiment(self):
        rid = runs.create("idea", "/idea mlp", "mlp", {"idea": "mlp"}, risk=2)["id"]
        runs.approve(rid)
        r = self.wait(rid, timeout=90)
        self.assertEqual(r["status"], "COMPLETED", r["reason"])
        code = next(s for s in r["steps"] if s["kind"] == "code")["result"]
        self.assertEqual(code["files"], [f"ideas/{rid}/main.py"])
        self.assertEqual(code["command"], f"python ideas/{rid}/main.py")  # path rewritten to the file actually written
        self.assertTrue((sandbox.code_dir() / code["files"][0]).exists())

    def test_code_with_a_coding_provider_and_with_the_app_model(self):
        def fake_coding(task, pid, prompt, ctx, outdir, cancelled=None):
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / "train.py").write_text(OK, "utf-8")
            return {"text": "done\n```phdlab-run\npython train.py\n```", "files": ["train.py", "notes.bin"]}
        with mock.patch.object(RP, "pick", return_value=("claude_code", "")), \
                mock.patch.object(RP, "run_coding", side_effect=fake_coding):
            rid = runs.create("code", "/code x", "x", {"task": "x"}, risk=2, provider="claude_code")["id"]
            runs.approve(rid)
            r = self.wait(rid)
        self.assertEqual(r["status"], "COMPLETED")
        self.assertEqual(r["steps"][0]["result"]["files"], [f"ideas/{rid}/train.py"])
        rid = runs.create("code", "/code y", "y", {"task": "y"}, risk=2)["id"]
        runs.approve(rid)
        self.assertEqual(self.wait(rid)["steps"][0]["result"]["command"], f"python ideas/{rid}/main.py")

    def test_code_errors(self):
        with mock.patch.object(RP, "app_complete", return_value="no files here"):
            rid = runs.create("code", "c", "x", {"task": "x"}, risk=2, budget={"max_retries": 0})["id"]
            runs.approve(rid)
            self.assertIn("no code file", self.wait(rid)["steps"][0]["error"])
        rid = runs.create("code", "c", "x", {"task": "x"}, risk=2)["id"]
        runs.update(rid, lambda x: x.update(status="RUNNING"))
        runs.spawn(rid)
        self.assertIn("approval", self.wait(rid)["steps"][0]["error"])

    def test_review_verify_and_latex(self):
        rid = runs.create("review", "r", "", {"text": "A paper about ViT with 91% accuracy."}, risk=0)["id"]
        r = self.wait(rid)
        self.assertEqual(r["status"], "COMPLETED")
        self.assertTrue(any(o["path"].endswith("review_report.md") for o in r["outputs"]))
        self.assertIn("nothing to review", self.wait(runs.create("review", "r", "", {}, risk=0, budget={"max_retries": 0})["id"])
                      ["steps"][0]["error"])
        self.script("ok.py", OK)
        self.wait(self.exp("python ok.py"))
        (config.data_dir() / "draft.md").write_text("Our model reaches 91% accuracy. Loss is 0.2. Published 2024.", "utf-8")
        r = self.wait(runs.create("verify", "v", "", {"path": "draft.md"}, risk=0)["id"])
        res = r["steps"][0]["result"]
        self.assertEqual((res["claims"], res["supported"]), (2, 2))
        with mock.patch("backend.paper.latex.compile_pdf", return_value={"ok": True, "engine": "tectonic", "pages": 3}):
            r = self.wait(runs.create("latex", "pdf", risk=1)["id"])
        self.assertEqual(r["status"], "COMPLETED")
        with mock.patch("backend.paper.latex.compile_pdf", return_value={"ok": False, "errors": [{"message": "Undefined control"}]}):
            r = self.wait(runs.create("latex", "pdf", risk=1, budget={"max_retries": 0})["id"])
        self.assertIn("Undefined control", r["steps"][0]["error"])

    def test_review_of_a_project_file_and_of_the_written_paper(self):
        (config.data_dir() / "paper.md").write_text("draft text", "utf-8")
        self.assertEqual(self.wait(runs.create("review", "r", "", {"path": "paper.md"}, risk=0)["id"])["status"], "COMPLETED")
        r = self.wait(runs.create("review", "r", "", {"path": "../outside.md"}, risk=0, budget={"max_retries": 0})["id"])
        self.assertIn("not found", r["steps"][0]["error"])
        from backend.paper.writer import load_project, save_project
        p = load_project()
        p["sections"]["introduction"] = "We study ViTs."
        save_project(p)
        self.assertEqual(self.wait(runs.create("review", "r", "", {}, risk=0)["id"])["status"], "COMPLETED")

    def test_review_on_feynman(self):
        with mock.patch.object(RP, "pick", return_value=("feynman", "")), \
                mock.patch.object(RP, "run_feynman", return_value={"text": "critique", "files": []}):
            r = self.wait(runs.create("review", "r", "", {"text": "paper"}, risk=0, provider="feynman")["id"])
        self.assertEqual(r["status"], "COMPLETED")


class ChatLink(RunsBase):
    def test_the_conversation_sees_approvals_results_and_pin_proposals(self):
        s = sessions.create("t")
        self.script("ok.py", OK)
        rid = runs.create("experiment", "e", inputs={"command": "python ok.py"}, session_id=s["id"], risk=2)["id"]
        msgs = sessions.get(s["id"])["messages"]
        self.assertIn("Cần bạn duyệt", msgs[-1]["content"])
        self.assertEqual(msgs[-1]["run_id"], rid)
        runs.approve(rid)
        self.wait(rid)
        s2 = sessions.get(s["id"])
        self.assertIn("Hoàn tất", s2["messages"][-1]["content"])
        pins = [a for a in s2["approvals"] if a["name"] == "pin_result"]
        self.assertEqual(len(pins), 1)
        self.assertTrue(pins[0]["args"]["run_id"])
        evs = [e["type"] for e in sessions.events(s["id"])]
        self.assertIn("run.updated", evs)
        runs._notify(rid)  # the same status twice: no duplicate message
        self.assertEqual(len(sessions.get(s["id"])["messages"]), len(s2["messages"]))

    def test_a_deleted_conversation_does_not_break_the_run(self):
        rid = runs.create("research", "t", "x", {"topic": "x"}, session_id="as-0000000000", risk=0)["id"]
        self.assertEqual(self.wait(rid)["status"], "COMPLETED")

    def test_internal_errors_end_in_needs_user_action(self):
        with mock.patch.object(runs, "_run_step", side_effect=RuntimeError("boom")):
            rid = runs.create("research", "t", "x", {"topic": "x"}, risk=0)["id"]
            r = self.wait(rid)
        self.assertEqual(r["status"], "NEEDS_USER_ACTION")
        self.assertIn("lỗi nội bộ", r["next_decision"])

    def test_misc_helpers(self):
        self.assertEqual(runs.valid_metrics({"a": 1, "b": True, "c": float("nan"), "d": "x", "e": 2.5}), {"a": 1, "e": 2.5})
        runs.reset_memory()
        self.assertIn("Research outline", runs.project_brief())


if __name__ == "__main__":
    unittest.main()
