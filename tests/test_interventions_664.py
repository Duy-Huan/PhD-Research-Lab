"""FQC-INTERVENTIONS-664 (agent/PLAN_6.6.4_L3.md B2; RQ-14): who decided what, and every human intervention by category.

The first live run needed a hand-applied code fix, a QA-written approval and a researcher-created writing mission, and
nothing in the app counted them. The intervention report reads the topic's hash-linked decision ledger: authorization and
routine verification are expected, rescue and risk exceptions count against autonomy, and an event without a stated actor
is `unknown`, never guessed. Real missions, protocols and ledger in a disposable PHDLAB_DATA_DIR."""
import unittest

import _env
from backend.agent import decision_ledger as L, missions as M
from backend.agent.mission_contracts import MissionSpec, Task
from backend.execution import protocols as P
from backend.execution.protocol_contracts import ExperimentProtocol
from backend.knowledge import research_store as S

class _Lazy:
    """Imported on use, so each test reports on its own (also on the commit before this module existed)."""

    def __init__(self, name):
        self.name = name

    def __getattr__(self, attr):
        import importlib
        return getattr(importlib.import_module(self.name), attr)


I = _Lazy("backend.agent.interventions")
AGENT = "mcp:codex:s1"


class Interventions(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("interventions tests", code_project=None)
        self.tid = _env.legacy_topic(S.TopicInput(title="Interventions"))["id"]

    def scenario(self):
        m = M.create(MissionSpec(topic_id=self.tid, objective="Agent branch", owner=AGENT, tasks=[Task(id="look", capability="paper.inspect")]))
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Authorized")
        p = P.create(ExperimentProtocol(topic_id=self.tid, hypothesis="Smoothing lowers MSE"), by=AGENT)
        P.approve(self.tid, p["id"], p["digest"], "Design reviewed")
        M.cancel(self.tid, m["id"])
        I.record(self.tid, "scientific_rescue", "QA operator applied the agent's one-line fix by hand", decision="replan")
        return m, p

    def test_decisions_and_interventions_are_attributed(self):
        self.scenario()
        r = I.report(self.tid)
        self.assertTrue(r["ledger_ok"])
        self.assertEqual(r["counts"], {"initial_authorization": 2, "routine_scientific_verification": 0, "scientific_rescue": 1,
                                       "risk_exception": 1, "final_publication_review": 0})
        self.assertEqual(r["decided_by"]["branch"], {"human": 0, "agent": 1, "unknown": 0})
        self.assertEqual(r["decided_by"]["hypothesis"], {"human": 0, "agent": 1, "unknown": 0})
        self.assertEqual(r["decided_by"]["stop"], {"human": 1, "agent": 0, "unknown": 0})
        self.assertEqual(r["decided_by"]["replan"], {"human": 1, "agent": 0, "unknown": 0})
        self.assertEqual(r["agent_decision_share"], 0.5)
        rescue = next(i for i in r["interventions"] if i["category"] == "scientific_rescue")
        self.assertIn("by hand", rescue["note"])
        self.assertTrue(all(len(i["hash"]) == 64 for i in r["interventions"]))  # each entry points at its ledger record

    def test_a_researcher_branch_and_a_step_rejection_count_as_human(self):
        m = M.create(MissionSpec(topic_id=self.tid, objective="Researcher branch", tasks=[Task(id="look", capability="paper.inspect")]))
        with S.db() as c:
            L.append(c, self.tid, m["id"], "workflow.step_reviewed", {"task_id": "look", "accept": False, "note": "Wrong source", "by": "researcher"})
        r = I.report(self.tid)
        self.assertEqual(r["decided_by"]["branch"]["human"], 1)
        self.assertEqual(r["decided_by"]["rejection"]["human"], 1)
        self.assertEqual(r["counts"]["routine_scientific_verification"], 1)

    def test_an_event_without_an_actor_is_unknown_not_guessed(self):
        with S.db() as c:
            L.append(c, self.tid, "claim-1", "claim.proposed", {"text": "Smoothing helps"})
        r = I.report(self.tid)
        self.assertEqual(r["decided_by"]["hypothesis"], {"human": 0, "agent": 0, "unknown": 1})
        self.assertEqual((r["unknown_decisions"], r["agent_decision_share"]), (1, None))

    def test_bad_records_are_refused(self):
        for args, message in ((("magic", "x"), "Choose one of"), (("risk_exception", "  "), "Describe"),
                              (("risk_exception", "x", "guess"), "Decision must be")):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, message):
                I.record(self.tid, *args)
        with self.assertRaises((KeyError, ValueError)):
            I.record("no-such-topic", "risk_exception", "x")

    def test_a_recorded_intervention_cannot_be_edited_away(self):
        import sqlite3
        self.scenario()
        before = I.report(self.tid)["counts"]
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append only"), S.db() as c:
            c.execute("UPDATE decision_ledger SET payload=? WHERE kind='intervention.recorded'",
                      (S.dumps({"category": "initial_authorization", "note": "edited"}),))
        after = I.report(self.tid)
        self.assertEqual((after["counts"], after["ledger_ok"]), (before, True))

    def test_the_api_reports_and_records(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)
        base = f"/api/research/topics/{self.tid}/interventions"
        made = client.post(base, json={"category": "risk_exception", "note": "Stopped a run that wrote outside the project", "decision": "stop"})
        self.assertEqual(made.status_code, 200, made.text)
        self.assertEqual(client.get(base).json()["counts"]["risk_exception"], 1)
        self.assertEqual(client.post(base, json={"category": "nope", "note": "x"}).status_code, 400)

    def test_the_report_is_quick_on_a_long_ledger(self):
        import time
        with S.db() as c:
            for i in range(2000):
                L.append(c, self.tid, f"e{i}", "mission.approved", {"note": "ok", "by": "researcher"})
        t0 = time.perf_counter()
        r = I.report(self.tid)
        self.assertEqual(r["counts"]["initial_authorization"], 2000)
        self.assertLess(time.perf_counter() - t0, 5.0)


if __name__ == "__main__":
    unittest.main()
