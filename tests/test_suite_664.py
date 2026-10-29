"""FQC-SUITE-664 (agent/PLAN_6.6.4_L3.md B1; RQ-13): the cpu-ml-v1 suite is frozen, valid and reproducible.

Owner decision 2026-10-29: small CPU-scale ML, 4 cases (2 guided, 2 open-ended), 40 turns, 2 restarts, about 2 hours per
case, Codex. The suite's digest must match its content, every dataset must regenerate byte for byte to its recorded
sha256, open-ended cases keep held-out data, and the campaign record it starts is scored NOT_RUN until measured."""
import copy
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "devtools" / "qualification" / "cpu-ml-v1"


def generator():
    spec = importlib.util.spec_from_file_location("cpu_ml_v1_generate", SUITE / "generate_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Suite(unittest.TestCase):
    def setUp(self):
        from devtools.qualification import suite as Q
        self.Q = Q

    def test_the_frozen_suite_loads_and_follows_the_owner_decision(self):
        s = self.Q.load(SUITE)
        self.assertEqual([c["kind"] for c in s["cases"]].count("guided"), 2)
        self.assertEqual([c["kind"] for c in s["cases"]].count("open-ended"), 2)
        self.assertEqual((s["budget"]["max_turns"], s["budget"]["max_restarts"], s["budget"]["max_wall_seconds"]), (40, 2, 7200))
        self.assertEqual(s["agent"]["model"], "cli:codex")
        covered = set().union(*(set(c["measures"]) for c in s["cases"]))
        self.assertEqual(covered, {f"RQ-{i:02d}" for i in range(1, 15)})  # every criterion is measured by some case

    def test_every_dataset_regenerates_to_its_recorded_sha256(self):
        g = generator()
        s = self.Q.load(SUITE)
        for did, spec in g.datasets(s).items():
            with self.subTest(dataset=did):
                raw = g.generate(**spec["generator"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), spec["sha256"])
                self.assertEqual(raw, g.generate(**spec["generator"]))  # deterministic
                self.assertNotIn(b"\r", raw)

    def test_open_ended_cases_keep_held_out_data_apart(self):
        s = self.Q.load(SUITE)
        for case in s["cases"]:
            roles = {d["role"] for d in case["data"]}
            if case["kind"] == "open-ended":
                self.assertEqual(roles, {"given", "held_out"})
                given, held = [d for d in case["data"] if d["role"] == "given"][0], [d for d in case["data"] if d["role"] == "held_out"][0]
                self.assertNotEqual(given["generator"]["seed"], held["generator"]["seed"])
            else:
                self.assertEqual(roles, {"given"})

    def test_an_edited_suite_is_refused(self):
        folder = Path(tempfile.mkdtemp()) / "cpu-ml-v1"
        shutil.copytree(SUITE, folder)
        data = json.loads((folder / "suite.json").read_text("utf-8"))
        data["budget"]["max_turns"] = 400
        (folder / "suite.json").write_text(json.dumps(data), "utf-8")
        with self.assertRaisesRegex(ValueError, "changed after it was frozen"):
            self.Q.load(folder)

    def test_invalid_suites_are_reported(self):
        s = copy.deepcopy(self.Q.load(SUITE))
        s["cases"][2]["data"] = [d for d in s["cases"][2]["data"] if d["role"] != "held_out"]
        s["cases"][0]["measures"] = ["RQ-99"]
        s["stopping_rules"] = []
        problems = " ".join(self.Q.validate(s))
        for part in ("needs held-out data", "measures must be RQ-01..RQ-14", "Stopping rules are required"):
            self.assertIn(part, problems)

    def test_the_campaign_template_is_scored_not_run_until_measured(self):
        from backend.agent import qualification
        record = self.Q.campaign_template(SUITE, "campaign-test")
        self.assertEqual((record["planned_cases"], record["suite_digest"]), (4, (SUITE / "suite-digest.txt").read_text("utf-8").strip()))
        scored = qualification.score(record, SUITE)
        self.assertEqual({v["status"] for v in scored["criteria"].values()}, {"NOT_RUN"})
        self.assertEqual(scored["denominators"], {"planned_cases": 4, "attempted_cases": 0, "cases_recorded": 4})

    def test_regenerating_all_data_is_quick(self):
        import time
        g = generator()
        t0 = time.perf_counter()
        out = Path(tempfile.mkdtemp())
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(g.main(out), 0)
        self.assertEqual(len(list(out.glob("*.csv"))), 6)
        self.assertLess(time.perf_counter() - t0, 10.0)


if __name__ == "__main__":
    unittest.main()
