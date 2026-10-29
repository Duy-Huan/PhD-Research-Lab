"""FQC-MISSIONS-LIVE-664 (agent/PLAN_6.6.4_L3.md A8): every mission state change reaches open Missions views.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): a mission the agent created appeared only after a page
reload, because the event bus was told only when a task finished. Creation, approval, cancellation, retry and step
review now publish research.mission (after the write). The UI side (live refresh, Topic kept over a reload, narrow
drawer) is covered by frontend/e2e/missions_live.spec.ts."""
import unittest

import _env
from backend.agent import autonomy, decision_ledger as L, missions as M
from backend.agent.mission_contracts import MissionSpec, Task
from backend.core import bus
from backend.knowledge import research_store as S


class MissionEvents(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("mission events tests", code_project=None)
        self.tid = _env.legacy_topic(S.TopicInput(title="Live missions"))["id"]

    def events(self, after):
        return [e for e in bus.since(after)["events"] if e["type"] == "research.mission"]

    def mission(self):
        return M.create(MissionSpec(topic_id=self.tid, objective="Inspect", tasks=[Task(id="look", capability="paper.inspect")]))

    def test_creation_approval_and_cancellation_are_published(self):
        start = bus.since()["last"]
        m = self.mission()
        created = self.events(start)
        self.assertEqual([(e["mission_id"], e["topic_id"], e["status"]) for e in created], [(m["id"], self.tid, "draft")])
        mark = bus.since()["last"]
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Approve")
        self.assertEqual([e["status"] for e in self.events(mark)], ["queued"])
        mark = bus.since()["last"]
        M.cancel(self.tid, m["id"])
        self.assertEqual([e["status"] for e in self.events(mark)], ["cancelled"])

    def test_events_carry_ids_and_status_only(self):
        start = bus.since()["last"]
        self.mission()
        [event] = self.events(start)
        self.assertEqual(set(event) - {"seq", "ts", "type", "client"}, {"mission_id", "topic_id", "status"})
        self.assertNotIn("Inspect", str(event))  # no objective, plan or result content on the bus

    def test_publishing_is_cheap(self):
        import time
        t0 = time.perf_counter()
        for _ in range(50):
            self.mission()
        self.assertLess(time.perf_counter() - t0, 5.0)

    def test_a_failed_change_publishes_nothing(self):
        m = self.mission()
        mark = bus.since()["last"]
        with self.assertRaises(ValueError):
            M.approve(self.tid, m["id"], "0" * 64, "Wrong digest")
        self.assertEqual(self.events(mark), [])

    def test_a_step_review_is_published(self):
        from backend.core import config
        config.save_config({"research_os": {"enabled": True}})
        spec = MissionSpec.model_validate({
            "topic_id": self.tid, "objective": "Inspect with review",
            "control": {"success_criteria": ["Reviewed"], "allowed_engines": ["deterministic"], "end_date": "2099-01-01T00:00:00+00:00"},
            "autonomy": {"level": "L2"}, "tasks": [{"id": "look", "capability": "paper.inspect"}]})
        m = M.create(spec)
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Approve")
        import asyncio
        for _ in range(3):
            asyncio.run(M.tick(m["id"]))
        m = M.get(m["id"], self.tid)
        self.assertEqual(m["status"], "awaiting_step_review")
        task = autonomy.pending_review(m)
        mark = bus.since()["last"]
        autonomy.step_review(self.tid, m["id"], task["id"], m["payload"]["plan_digest"], L.digest(task["payload"]["result"]), True, "Looks right")
        self.assertEqual([e["mission_id"] for e in self.events(mark)], [m["id"]])


if __name__ == "__main__":
    unittest.main()
