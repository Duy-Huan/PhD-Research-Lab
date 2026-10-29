"""FQC-QUALIFICATION-664 (agent/PLAN_6.6.4_L3.md B5): criteria are scored only from measured, resolvable evidence.

The objectives file says L3 is not demonstrated (all criteria NOT_RUN). It may change only from a measured campaign: a
criterion qualifies only when every planned case measured and passed it with evidence that resolves to its sha256; one
failure disqualifies, a missing measurement or changed evidence is inconclusive, human rescue disqualifies RQ-14, and L3
needs all 14. Real files in a temporary folder; the repository's objectives file is never written by these tests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

class _Lazy:
    """Imported on use, so each test reports on its own (also on the commit before this module existed)."""

    def __init__(self, name):
        self.name = name

    def __getattr__(self, attr):
        import importlib
        return getattr(importlib.import_module(self.name), attr)


Q = _Lazy("backend.agent.qualification")


class Scoring(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        (self.base / "ev").mkdir()

    def evidence(self, name="run.json", body=b'{"measured": true}'):
        path = self.base / "ev" / name
        path.write_bytes(body)
        return [{"path": f"ev/{name}", "sha256": hashlib.sha256(body).hexdigest()}]

    def campaign(self, cases=2, passed=True, interventions=None, skip=None):
        ev = self.evidence()
        out = {"campaign_id": "c1", "suite_digest": "a" * 64, "planned_cases": cases, "cases": []}
        for i in range(cases):
            measurements = {cid: {"passed": passed, "note": "", "evidence": ev} for cid in Q.CRITERIA if cid != skip}
            out["cases"].append({"case_id": f"case-{i}", "attempts": [{"n": 1}], "interventions": interventions or {},
                                 "measurements": measurements})
        return out

    def test_all_criteria_measured_and_passed_qualify_scoped_l3(self):
        s = Q.score(self.campaign(), self.base)
        self.assertEqual({v["status"] for v in s["criteria"].values()}, {"QUALIFIED"})
        self.assertEqual((s["achieved_level"], s["qualification_status"]), ("L3", "QUALIFIED_SCOPED_L3"))
        self.assertEqual(s["denominators"], {"planned_cases": 2, "attempted_cases": 2, "cases_recorded": 2})

    def test_one_failure_disqualifies_and_names_the_case(self):
        c = self.campaign()
        c["cases"][1]["measurements"]["RQ-08"] = {"passed": False, "note": "Claim contradicted by the raw metrics", "evidence": []}
        s = Q.score(c, self.base)
        self.assertEqual(s["criteria"]["RQ-08"]["status"], "NOT_QUALIFIED")
        self.assertIn("case-1: Claim contradicted", s["criteria"]["RQ-08"]["reasons"][0])
        self.assertIsNone(s["achieved_level"])

    def test_missing_measurements_and_changed_evidence_are_inconclusive(self):
        c = self.campaign()
        del c["cases"][0]["measurements"]["RQ-07"]
        s = Q.score(c, self.base)
        self.assertEqual(s["criteria"]["RQ-07"]["status"], "INCONCLUSIVE")
        c = self.campaign()
        (self.base / "ev" / "run.json").write_bytes(b'{"measured": "edited"}')  # changed after the campaign recorded it
        s = Q.score(c, self.base)
        self.assertEqual({v["status"] for v in s["criteria"].values()} - {"NOT_QUALIFIED"}, {"INCONCLUSIVE"})

    def test_evidence_outside_the_campaign_folder_never_counts(self):
        c = self.campaign()
        outside = Path(tempfile.mkdtemp()) / "x.json"
        outside.write_bytes(b"x")
        c["cases"][0]["measurements"]["RQ-01"]["evidence"] = [{"path": str(outside), "sha256": hashlib.sha256(b"x").hexdigest()}]
        self.assertEqual(Q.score(c, self.base)["criteria"]["RQ-01"]["status"], "INCONCLUSIVE")

    def test_human_rescue_disqualifies_rq14_and_an_unfrozen_suite_rq13(self):
        s = Q.score(self.campaign(interventions={"scientific_rescue": 1, "initial_authorization": 3}), self.base)
        self.assertEqual(s["criteria"]["RQ-14"]["status"], "NOT_QUALIFIED")
        self.assertEqual(s["interventions"], {"scientific_rescue": 2, "risk_exception": 0})  # one in each of 2 cases
        c = self.campaign()
        c["suite_digest"] = ""
        self.assertEqual(Q.score(c, self.base)["criteria"]["RQ-13"]["status"], "NOT_QUALIFIED")
        c = self.campaign()
        c["planned_cases"] = 3
        s = Q.score(c, self.base)
        self.assertEqual(s["criteria"]["RQ-01"]["status"], "INCONCLUSIVE")  # 2 of 3 planned cases

    def test_nothing_measured_is_not_run(self):
        s = Q.score({"campaign_id": "empty", "planned_cases": 0, "cases": []}, self.base)
        self.assertEqual({v["status"] for v in s["criteria"].values()}, {"NOT_RUN"})

    def test_apply_writes_only_measured_status_into_a_copy_of_the_objectives(self):
        objectives = self.base / "objectives.json"
        objectives.write_text(Q.OBJECTIVES.read_text("utf-8"), "utf-8")
        record = self.base / "campaign.json"
        record.write_text(json.dumps(self.campaign(skip="RQ-02")), "utf-8")
        scored = Q.apply(record, objectives)
        data = json.loads(objectives.read_text("utf-8"))
        by_id = {c["id"]: c for c in data["criteria"]}
        self.assertEqual((by_id["RQ-01"]["status"], by_id["RQ-02"]["status"]), ("QUALIFIED", "NOT_RUN"))
        self.assertEqual(by_id["RQ-01"]["measured_by"]["campaign_sha256"], hashlib.sha256(record.read_bytes()).hexdigest())
        self.assertEqual((data["achieved_level"], data["qualification_status"]), (None, "NOT_DEMONSTRATED"))
        self.assertEqual(scored["criteria"]["RQ-02"]["status"], "NOT_RUN")
        # The repository's own objectives file still says L3 is not demonstrated.
        repo = json.loads(Q.OBJECTIVES.read_text("utf-8"))
        self.assertEqual((repo["achieved_level"], repo["qualification_status"]), (None, "NOT_DEMONSTRATED"))


if __name__ == "__main__":
    unittest.main()
