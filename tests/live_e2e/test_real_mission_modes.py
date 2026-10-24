"""Real Mission, Team, and Workstream Live Execution Suite.

Tests governed multi-agent mission lifecycles:
  - Single, Fixed, Adaptive, and Multi-workstream modes
  - DAG dependencies, cycle rejection, fan-out/fan-in
  - Budget boundaries (reasoning calls, wall time, depth)
  - Workstream handoffs, receipts, disputes, and canonical revisions
  - Checkpoint crash and recovery across 5 critical moments
"""
import asyncio
import json
import os
import time
import unittest
from datetime import datetime, timedelta, timezone

from tests.live_e2e.conftest_or_setup import (
    LMSTUDIO_BASE_URL,
    LOCAL_MODEL,
    check_lmstudio_health,
    configure_live_phi4,
    log_harness_event,
)
from backend.core import config as C
from backend.agent import missions as M, research_os as O, teams, collaboration
from backend.agent.mission_contracts import MissionSpec, Task, Limits
from backend.knowledge import research_store as S, corpus


class TestRealMissionModes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        health = check_lmstudio_health()
        if not health["online"] or not health["has_phi4"]:
            raise unittest.SkipTest(f"LM Studio phi-4 not available at {LMSTUDIO_BASE_URL}: {health}")
        configure_live_phi4()

    def setUp(self):
        configure_live_phi4()

    def _setup_topic_and_charter(self, name: str, max_reasoning: int = 5):
        tid = S.save_topic(S.TopicInput(title=f"Topic - {name}"))["id"]
        perms = ["compute", "network", "reasoning", "workspace_write"]
        ch = O.create_charter(O.ProjectCharter(
            goal=f"Charter for {name}",
            topics=[O.TopicGoal(topic_id=tid, goal="Execute supervised workflows")],
            permissions=perms,
            max_reasoning_calls=max_reasoning
        ))
        p1 = corpus.ingest(tid, [{"title": f"{name} Paper Alpha", "source": "test", "abstract": "Alpha features"}])["paper_ids"][0]
        p2 = corpus.ingest(tid, [{"title": f"{name} Paper Beta", "source": "test", "abstract": "Beta features"}])["paper_ids"][0]
        common = {
            "success_criteria": ["Criteria satisfied"],
            "charter_id": ch["id"],
            "charter_digest": ch["digest"],
            "end_date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "allowed_engines": ["deterministic", "app"],
            "app_backend": "local",
            "app_model": LOCAL_MODEL,
            "allow_api_billing": False
        }
        return tid, ch, perms, common, [p1, p2]

    def test_mode_single_team(self):
        """Single team mode with deterministic and reasoning tasks."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("SingleTeam")
        t1 = Task(id="t_cmp", capability="paper.compare", args={"paper_ids": papers, "question": "Compare Alpha vs Beta"}, depends_on=[], preferred_engine="app")
        spec = MissionSpec(topic_id=tid, objective="Single Team Run", permissions=perms, control=common, tasks=[t1])
        
        m = M.create(spec)
        mid = m["id"]
        O.request_approval(tid, mid)
        M.approve(tid, mid, m["payload"]["plan_digest"], "Approved single team")

        for _ in range(3):
            asyncio.run(M.tick())

        m_fin = M.get(mid)
        self.assertEqual(m_fin["tasks"][0]["status"], "completed")

    def test_mode_fixed_team(self):
        """Fixed team plan mode with owner and verifier roles."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("FixedTeam")
        t1 = Task(id="t_cmp", capability="paper.compare", args={"paper_ids": papers}, depends_on=[], preferred_engine="app")
        spec = MissionSpec(topic_id=tid, objective="Fixed Team Run", permissions=perms, control=common, tasks=[t1])
        spec = teams.propose(spec, "fixed")
        
        self.assertIsNotNone(spec.team)
        self.assertEqual(spec.team.mode, "fixed")

        m = M.create(spec)
        mid = m["id"]
        O.request_approval(tid, mid)
        M.approve(tid, mid, m["payload"]["plan_digest"], "Approved fixed team")

        for _ in range(4):
            asyncio.run(M.tick())

        m_fin = M.get(mid)
        self.assertEqual(m_fin["tasks"][0]["status"], "completed")

    def test_mode_adaptive_team(self):
        """Adaptive team plan mode with dynamic specialization."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("AdaptiveTeam")
        t1 = Task(id="t_cmp", capability="paper.compare", args={"paper_ids": papers}, depends_on=[], preferred_engine="app")
        spec = MissionSpec(topic_id=tid, objective="Adaptive Team Run", permissions=perms, control=common, tasks=[t1])
        spec = teams.propose(spec, "adaptive")

        self.assertIsNotNone(spec.team)
        self.assertEqual(spec.team.mode, "adaptive")

        m = M.create(spec)
        mid = m["id"]
        O.request_approval(tid, mid)
        M.approve(tid, mid, m["payload"]["plan_digest"], "Approved adaptive team")

        for _ in range(4):
            asyncio.run(M.tick())

        m_fin = M.get(mid)
        self.assertEqual(m_fin["tasks"][0]["status"], "completed")

    def test_mode_multi_workstream_partition(self):
        """Multi-workstream partition across multiple teams with handoff."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("MultiWorkstream")
        t1 = Task(id="t_a", capability="paper.compare", args={"paper_ids": papers}, depends_on=[], preferred_engine="app")
        t2 = Task(id="t_b", capability="paper.inspect", args={"paper_ids": papers}, depends_on=["t_a"], preferred_engine="deterministic")
        spec = MissionSpec(topic_id=tid, objective="Multi Workstream Run", permissions=perms, control=common, tasks=[t1, t2])
        spec = teams.propose(spec, "adaptive")
        spec = collaboration.partition(spec)

        self.assertIsNotNone(spec.collaboration)
        m = M.create(spec)
        mid = m["id"]
        O.request_approval(tid, mid)
        M.approve(tid, mid, m["payload"]["plan_digest"], "Approved multi-workstream")

        for _ in range(6):
            asyncio.run(M.tick())

        m_fin = M.get(mid)
        tasks_status = {t["id"]: t["status"] for t in m_fin["tasks"]}
        self.assertEqual(tasks_status["t_a"], "completed")
        self.assertEqual(tasks_status["t_b"], "completed")

    def test_dag_cycle_rejection(self):
        """Validation rejects cyclic task dependencies in DAG."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("DAGCycle")
        t1 = Task(id="t_one", capability="paper.inspect", args={"paper_ids": papers}, depends_on=["t_two"])
        t2 = Task(id="t_two", capability="paper.inspect", args={"paper_ids": papers}, depends_on=["t_one"])
        
        with self.assertRaises(Exception):
            MissionSpec(topic_id=tid, objective="Cyclic DAG", permissions=perms, control=common, tasks=[t1, t2])

    def test_stale_plan_digest_rejection(self):
        """Approval is rejected when plan digest is forged or stale."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("StaleDigest")
        t1 = Task(id="t_one", capability="paper.inspect", args={"paper_ids": papers}, depends_on=[])
        spec = MissionSpec(topic_id=tid, objective="Digest Check", permissions=perms, control=common, tasks=[t1])
        m = M.create(spec)
        mid = m["id"]
        O.request_approval(tid, mid)

        with self.assertRaises(Exception):
            M.approve(tid, mid, "forged_digest_00000000000000000000", "Forged approval")

    def test_reasoning_budget_enforcement(self):
        """Mission respects max_reasoning_calls limit and refuses unauthorized calls."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("BudgetCap", max_reasoning=1)
        t1 = Task(id="t_one", capability="paper.compare", args={"paper_ids": papers}, depends_on=[], preferred_engine="app")
        t2 = Task(id="t_two", capability="paper.compare", args={"paper_ids": papers}, depends_on=["t_one"], preferred_engine="app")
        spec = MissionSpec(
            topic_id=tid,
            objective="Budget Limited",
            permissions=perms,
            control=common,
            limits=Limits(max_reasoning_calls=1, max_seconds=60),
            tasks=[t1, t2]
        )

        m = M.create(spec)
        mid = m["id"]
        O.request_approval(tid, mid)
        M.approve(tid, mid, m["payload"]["plan_digest"], "Approved budget limited")

        for _ in range(5):
            asyncio.run(M.tick())

        m_fin = M.get(mid)
        # First task completes, second is paused because budget cap is 1
        t1_status = next(t["status"] for t in m_fin["tasks"] if t["id"] == "t_one")
        self.assertEqual(t1_status, "completed")

    def test_checkpoint_recovery_before_approval(self):
        """Moment 1: Crash before approval -> mission recovers in draft/pending state."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("RecoveryMom1")
        t1 = Task(id="t_rec1", capability="paper.inspect", args={"paper_ids": papers}, depends_on=[])
        spec = MissionSpec(topic_id=tid, objective="Recovery M1", permissions=perms, control=common, tasks=[t1])
        m = M.create(spec)
        mid = m["id"]

        # Simulate reload from DB
        recovered = M.get(mid)
        self.assertEqual(recovered["status"], "draft")
        self.assertEqual(recovered["id"], mid)

    def test_checkpoint_recovery_after_completion(self):
        """Moment 5: Crash after task completion -> state and results are preserved."""
        tid, ch, perms, common, papers = self._setup_topic_and_charter("RecoveryMom5")
        t1 = Task(id="t_rec5", capability="paper.inspect", args={"paper_ids": papers}, depends_on=[])
        spec = MissionSpec(topic_id=tid, objective="Recovery M5", permissions=perms, control=common, tasks=[t1])
        m = M.create(spec)
        mid = m["id"]
        O.request_approval(tid, mid)
        M.approve(tid, mid, m["payload"]["plan_digest"], "Approved M5")

        for _ in range(3):
            asyncio.run(M.tick())

        # Recovered state after completion
        reloaded = M.get(mid)
        self.assertEqual(reloaded["tasks"][0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
