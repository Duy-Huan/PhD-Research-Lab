"""FQC-CONTINUITY-664 (agent/PLAN_6.6.4_L3.md B4; RQ-07): commitments survive restarts; no duplicate experiments, no leakage.

A qualification case runs many turns and process restarts. The continuity check compares snapshots of a topic's
commitments (mission plans and approvals, frozen protocols, measured runs, the ledger) taken before and after: nothing
approved may be lost or changed, no approval may run a second experiment, the ledger only grows, and another project
never sees this topic's data. The restart here is a real second process on the same data folder."""
import asyncio
import importlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import _env
from backend.agent import missions as M
from backend.agent.mission_contracts import MissionSpec, Task
from backend.core import config
from backend.execution import protocols as P
from backend.execution.protocol_contracts import ExperimentProtocol
from backend.knowledge import research_store as S

ROOT = Path(__file__).resolve().parents[1]


class _Lazy:
    """Imported on use, so each test reports on its own (also on the commit before this module existed)."""

    def __init__(self, name):
        self.name = name

    def __getattr__(self, attr):
        return getattr(importlib.import_module(self.name), attr)


C = _Lazy("backend.agent.continuity")


class Continuity(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.project = _env.fresh_project("continuity tests", code_project=None)
        self.tid = _env.legacy_topic(S.TopicInput(title="Continuity"))["id"]

    def work(self):
        p = P.create(ExperimentProtocol(topic_id=self.tid, hypothesis="Continuity fixture",
                                        dataset={"side": 8, "train_count": 2, "validation_count": 2, "test_count": 2},
                                        alphas=[0.5], max_trials=4))
        p = P.approve(self.tid, p["id"], p["digest"], "Approved")
        m = P.mission_draft(self.tid, p["id"])
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Approved")
        for _ in range(4):
            asyncio.run(M.tick(m["id"]))
        other = M.create(MissionSpec(topic_id=self.tid, objective="Pending branch", tasks=[Task(id="look", capability="paper.inspect")]))
        return p, other

    def restart(self):
        """A new Python process on the same data folder runs the app's start-up recovery."""
        script = ("from backend.agent import missions as M; from backend.execution import protocols as P; "
                  "M.recover(); P.recover(); print('recovered')")
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120, cwd=str(ROOT), env=env)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])

    def test_commitments_survive_several_real_restarts(self):
        _, pending = self.work()
        M.approve(self.tid, pending["id"], pending["payload"]["plan_digest"], "Approved")
        with S.db() as c:  # the app stops while this mission's task is running
            c.execute("UPDATE missions SET status='running' WHERE id=?", (pending["id"],))
            c.execute("UPDATE mission_tasks SET status='running' WHERE mission_id=?", (pending["id"],))
        before = C.snapshot(self.tid)
        for _ in range(3):
            self.restart()
        after = C.snapshot(self.tid)
        self.assertEqual(after["missions"][pending["id"]]["status"], "interrupted")  # the restarts ran on this data folder
        self.assertEqual(C.compare(before, after), [])
        self.assertEqual(len(after["runs"]), 1)

    def test_a_lost_or_changed_commitment_is_reported(self):
        p, other = self.work()
        before = C.snapshot(self.tid)
        after = json.loads(json.dumps(before))
        after["missions"].pop(other["id"])
        after["protocols"][p["id"]]["digest"] = "0" * 64
        after["runs"].append({**after["runs"][0], "id": "second"})
        issues = C.compare(before, after)
        self.assertIn(f"Mission {other['id']} was lost", issues)
        self.assertIn(f"Protocol {p['id']} was lost or changed", issues)
        self.assertTrue(any("ran more than one experiment" in i for i in issues))

    def test_a_rewritten_or_broken_ledger_is_reported(self):
        self.work()
        before = C.snapshot(self.tid)
        after = json.loads(json.dumps(before))
        after["ledger_hashes"][0] = "f" * 64
        after["ledger_ok"] = False
        issues = C.compare(before, after)
        self.assertIn("Decision ledger history was rewritten", issues)
        self.assertIn("Decision ledger integrity failed", issues)

    def test_an_approval_cannot_run_a_second_experiment(self):
        p, _ = self.work()
        approved = P.get(self.tid, p["id"])
        m = P.mission_draft(self.tid, p["id"])  # the same, already used approval
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Try again with the old approval")
        for _ in range(4):
            asyncio.run(M.tick(m["id"]))
        self.assertEqual(len([r for r in P.runs(self.tid) if r["approval_nonce"] == approved["approval"]["nonce"]]), 1)
        self.assertEqual(C.compare(C.snapshot(self.tid), C.snapshot(self.tid)), [])

    def test_another_project_does_not_see_this_topic(self):
        self.work()
        other = config.create_project("continuity other project")
        config.activate_project(self.project["data_dir"])
        self.assertEqual(C.leakage(self.tid, other["data_dir"]), [])
        self.assertEqual(config.active_project()["data_dir"], self.project["data_dir"])  # the check never switches projects
        self.assertNotEqual(C.leakage(self.tid, self.project["data_dir"]), [])  # the same project does see it

    def test_snapshots_of_different_topics_are_not_compared(self):
        self.work()
        a = C.snapshot(self.tid)
        b = json.loads(json.dumps(a))
        b["topic_id"] = "another"
        self.assertIn("Snapshots belong to different projects or topics", C.compare(a, b))

    def test_snapshots_are_quick(self):
        import time
        self.work()
        t0 = time.perf_counter()
        for _ in range(20):
            C.compare(C.snapshot(self.tid), C.snapshot(self.tid))
        self.assertLess(time.perf_counter() - t0, 10.0)


if __name__ == "__main__":
    unittest.main()
