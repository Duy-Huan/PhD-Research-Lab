import _env
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from backend.agent import missions as M, decision_ledger as L
from backend.agent.mission_contracts import MissionSpec
from backend.core import config
from backend.knowledge import research_store as S
from backend.agent import autonomy as A
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import app


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("autonomy", code_project=None)
        config.save_config({"research_os": {"enabled": True}})
        self.tid = S.save_topic(S.TopicInput(title="Autonomy fixture"))["id"]

    def spec(self, level="L2", **changes):
        return MissionSpec.model_validate({
            "topic_id": self.tid, "objective": "Inspect bounded source metadata",
            "autonomy": {"level": level},
            "control": {"success_criteria": ["Scoped evidence"],
                        "end_date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
            "tasks": [{"id": "inspect", "capability": "paper.inspect"},
                      {"id": "inspect_again", "capability": "paper.inspect", "depends_on": ["inspect"]}],
            **changes})

    def approve(self, spec):
        m = M.create(spec)
        return M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Reviewed bounded plan")

    def test_l2_stops_at_human_gate(self):
        m = self.approve(self.spec())
        asyncio.run(M.tick(m["id"]))
        m = M.get(m["id"])
        self.assertEqual(m["status"], "awaiting_step_review")
        asyncio.run(M.tick(m["id"]))
        self.assertEqual(M.get(m["id"])["tasks"][1]["status"], "pending")

    def test_four_missions_dispatch_concurrently_once(self):
        mids = [self.approve(self.spec("L3"))["id"] for _ in range(4)]
        active, peak, calls = 0, 0, []
        original = M._dispatch

        async def dispatch(m, task, key):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            calls.append(key)
            await asyncio.sleep(.02)
            value = await original(m, task, key)
            active -= 1
            return value

        async def run():
            await asyncio.gather(*(M.tick(mid) for mid in mids), M.tick(mids[0]))

        with patch.object(M, "_dispatch", side_effect=dispatch):
            asyncio.run(run())
        self.assertEqual(peak, 4)
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(set(calls)), 4)
        self.assertTrue(L.export(self.tid)["project_chain_valid"])

    def review(self, m, accept=True, **changes):
        task = A.pending_review(m)
        return A.step_review(self.tid, m["id"], task["id"], **{
            "plan_digest": m["payload"]["plan_digest"], "result_digest": L.digest(task["payload"]["result"]),
            "accept": accept, "note": "Inspected the bounded result", **changes})

    def test_l1_and_l2_acceptance_binds_result_and_closes_after_last_review(self):
        for mode in ("L1", "L2"):
            m = self.approve(self.spec(mode))
            for _ in range(2):
                asyncio.run(M.tick(m["id"]))
                m = M.get(m["id"])
                self.assertEqual(m["status"], "awaiting_step_review")
                self.assertTrue(A.pending_review(m)["payload"]["result_digest"])
                m = self.review(m)
            asyncio.run(M.tick(m["id"]))
            self.assertEqual(M.get(m["id"])["status"], "completed")

    def test_invalid_reviews_do_not_admit_next_task(self):
        m = self.approve(self.spec())
        with self.assertRaisesRegex(ValueError, "not awaiting"):
            A.step_review(self.tid, m["id"], "inspect", "0"*64, "0"*64, True, "Premature")
        asyncio.run(M.tick(m["id"])); m = M.get(m["id"])
        for changes in ({"plan_digest": "0"*64}, {"result_digest": "0"*64}, {"note": " "}):
            with self.assertRaises(ValueError):
                self.review(m, **changes)
        other = S.save_topic(S.TopicInput(title="Other scope"))["id"]
        with self.assertRaises(ValueError):
            A.step_review(other, m["id"], "inspect", m["payload"]["plan_digest"], L.digest(m["tasks"][0]["payload"]["result"]), True, "Cross-topic")
        self.assertEqual(M.get(m["id"])["tasks"][1]["payload"]["attempts"], 0)
        self.assertEqual(self.review(m, accept=False)["status"], "cancelled")
        with self.assertRaises(ValueError): self.review(m)

    def test_l3_requires_final_human_review_and_legacy_policy_is_unchanged(self):
        from backend.agent import research_os as OS
        m = self.approve(self.spec("L3"))
        for _ in range(3): asyncio.run(M.tick(m["id"]))
        self.assertEqual(M.get(m["id"])["status"], "awaiting_review")
        self.assertEqual(OS.review(self.tid, m["id"], "Final technical review")["status"], "completed")
        old = self.approve(self.spec(autonomy=None, control=None))
        for _ in range(3): asyncio.run(M.tick(old["id"]))
        self.assertEqual(M.get(old["id"])["status"], "completed")

    def l4_spec(self, **changes):
        return self.spec("L4", permissions=["workspace_write"], tasks=[
            {"id": "inspect", "capability": "paper.inspect"},
            {"id": "report", "capability": "mission.report", "depends_on": ["inspect"]},
            {"id": "verify", "capability": "artifact.verify", "depends_on": ["report"], "args": {"from_task": "report"}}], **changes)

    def l4_before_closure(self):
        m = self.approve(self.l4_spec())
        for _ in range(3): asyncio.run(M.tick(m["id"]))
        return M.get(m["id"])

    def test_l4_checks_actual_bytes_and_retains_pending_scientific_review(self):
        m = self.l4_before_closure()
        asyncio.run(M.tick(m["id"]))
        m = M.get(m["id"])
        self.assertEqual(m["status"], "completed")
        self.assertEqual(m["payload"]["technical_closure"]["scientific_review"], "pending")
        self.assertTrue(m["payload"]["technical_closure"]["artifacts"])
        tampered = self.l4_before_closure()
        path = Path(tampered["tasks"][1]["payload"]["result"]["artifacts"][0]["path"])
        path.write_bytes(b"forged")
        asyncio.run(M.tick(tampered["id"]))
        self.assertEqual(M.get(tampered["id"])["status"], "paused")
        self.assertNotIn("technical_closure", M.get(tampered["id"])["payload"])

    def test_l4_synthesis_closes_only_with_nonempty_bounded_text_and_checked_artifact(self):
        from backend.knowledge import corpus
        from unittest.mock import AsyncMock
        ids = corpus.ingest(self.tid, [{"title": "Scoped alpha", "source": "synthetic"}, {"title": "Scoped beta", "source": "synthetic"}])["paper_ids"]
        data = self.l4_spec().model_dump()
        data["permissions"] += ["network", "reasoning"]
        data["control"]["allowed_engines"] = ["deterministic", "app"]
        data["control"]["app_backend"] = "local"
        data["control"]["app_model"] = "fixture"
        data["tasks"].insert(1, {"id": "synthesis", "capability": "paper.compare", "preferred_engine": "app", "args": {"paper_ids": ids}, "depends_on": ["inspect"]})
        data["tasks"][2]["depends_on"] = ["synthesis"]
        m = self.approve(MissionSpec.model_validate(data))
        answer = {"text": "Both synthetic sources lack measurements; scientific validity is unverified.", "engine": "local", "model": "fixture"}
        with patch('backend.agent.research_os.fixed_reasoning', new=AsyncMock(return_value=answer)) as model:
            for _ in range(5): asyncio.run(M.tick(m["id"]))
            self.assertEqual(model.await_count, 1)
        final = M.get(m["id"])
        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["payload"]["technical_closure"]["scientific_review"], "pending")

    def test_l4_refuses_missing_failed_or_corrupted_verification(self):
        for mutation in ("empty", "failed", "missing", "no_artifacts", "empty_reasoning", "truncated_reasoning", "unreproduced"):
            m = self.l4_before_closure()
            with S.db() as c:
                task = m["tasks"][2]
                if mutation in ("empty", "failed"):
                    task["payload"]["result"]["output"]["checks"] = [] if mutation == "empty" else [{"status": "failed"}]
                if mutation == "missing": task["payload"].pop("result")
                if mutation == "no_artifacts":
                    report = m["tasks"][1]; report["payload"]["result"]["artifacts"] = []
                    c.execute("UPDATE mission_tasks SET payload=? WHERE mission_id=? AND id=?", (S.dumps(report["payload"]), m["id"], report["id"]))
                if mutation in ("empty_reasoning", "truncated_reasoning"):
                    task["payload"]["spec"]["capability"] = "paper.compare"
                    task["payload"]["result"]["output"] = {"text": " " if mutation == "empty_reasoning" else "Partial answer\n% [WARNING: output truncated at max_tokens]"}
                if mutation == "unreproduced":
                    task["payload"]["spec"]["capability"] = "experiment.verify"
                    task["payload"]["result"]["output"] = {"status": "unverified"}
                c.execute("UPDATE mission_tasks SET payload=? WHERE mission_id=? AND id=?", (S.dumps(task["payload"]), m["id"], task["id"]))
            asyncio.run(M.tick(m["id"]))
            self.assertEqual(M.get(m["id"])["status"], "paused", mutation)

    def test_control_and_l1_l4_capability_boundaries(self):
        with self.assertRaisesRegex(ValueError, "supervised"): M.create(self.spec(control=None))
        with self.assertRaisesRegex(ValueError, "child"): M.create(self.spec(parent_mission_id="parent"))
        with self.assertRaisesRegex(ValueError, "L1"): M.create(self.spec("L1", tasks=[{"id": "report", "capability": "mission.report"}]))
        with self.assertRaisesRegex(ValueError, "limited"): M.create(self.spec("L4", tasks=[{"id": "x", "capability": "paper.discover"}]))
        with self.assertRaisesRegex(ValueError, "final"): M.create(self.spec("L4"))
        broken = self.l4_spec().model_dump(); broken["tasks"][1]["depends_on"] = []
        with self.assertRaisesRegex(ValueError, "every workflow branch"): M.create(MissionSpec.model_validate(broken))
        broken = self.l4_spec().model_dump(); broken["tasks"][0]["capability"] = "experiment.run"
        with self.assertRaisesRegex(ValueError, "numerical"): M.create(MissionSpec.model_validate(broken))

    def test_pause_resume_cannot_bypass_unreviewed_result(self):
        from backend.agent import research_os as OS
        m = self.approve(self.spec())
        asyncio.run(M.tick(m["id"]))
        OS.pause(self.tid, m["id"], "Inspect status")
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Reauthorize")
        asyncio.run(M.tick(m["id"]))
        self.assertEqual(M.get(m["id"])["status"], "awaiting_step_review")
        self.assertEqual(M.get(m["id"])["tasks"][1]["payload"]["attempts"], 0)

    def test_review_api_contract_and_catalog(self):
        client = TestClient(app)
        self.assertEqual(client.get("/api/research/mission-capabilities").json()["max_independent_workflows"], 4)
        self.assertEqual(client.get("/api/research/os-settings").json()["max_parallel_tasks"], 1)
        m = self.approve(self.spec()); asyncio.run(M.tick(m["id"])); m = M.get(m["id"])
        url = f"/api/research/topics/{self.tid}/missions/{m['id']}/steps/inspect/review"
        self.assertEqual(client.post(url, json={"accept": True}).status_code, 422)
        body = {"plan_digest": m["payload"]["plan_digest"], "result_digest": m["tasks"][0]["payload"]["result_digest"], "accept": True, "note": "Actually inspected"}
        self.assertEqual(client.post(url, json=body).status_code, 200)
        self.assertEqual(client.post(url, json=body).status_code, 400)

    def test_cpu_contention_waits_before_experiment_admission(self):
        from backend.execution import protocols as P, guard
        from backend.execution.protocol_contracts import ExperimentProtocol
        protocol = P.create(ExperimentProtocol(topic_id=self.tid, hypothesis="Bounded CPU"))
        protocol = P.approve(self.tid, protocol["id"], protocol["digest"], "Reviewed protocol")
        m = self.approve(self.spec("L3", permissions=["workspace_write", "compute"], tasks=[{"id": "experiment", "capability": "experiment.run", "args": {"protocol_id": protocol["id"], "protocol_digest": protocol["digest"], "approval_nonce": protocol["approval"]["nonce"]}}]))
        guard.try_acquire("cpu", "another-workflow")
        try:
            asyncio.run(M.tick(m["id"]))
            self.assertEqual(M.get(m["id"])["tasks"][0]["payload"]["attempts"], 0)
        finally: guard.release("cpu", "another-workflow")

    def test_real_process_restart_keeps_uncertain_admission_interrupted(self):
        import subprocess, sys, json
        m = self.approve(self.spec("L3"))
        with S.db() as c:
            c.execute("UPDATE missions SET status='running' WHERE id=?", (m["id"],))
            c.execute("UPDATE mission_tasks SET status='running' WHERE mission_id=? AND id='inspect'", (m["id"],))
        script = "from backend.agent import missions as M; import json; M.recover(); print(json.dumps(M.get(" + repr(m["id"]) + ")))"
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=True)
        recovered = json.loads(result.stdout)
        self.assertEqual(recovered["status"], "interrupted")
        self.assertEqual(recovered["tasks"][0]["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
