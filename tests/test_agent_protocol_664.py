"""FQC-AGENT-PROTOCOL-664 (agent/PLAN_6.6.4_L3.md A2): governed execution of agent-written experiment code.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): experiment.run only ran the built-in denoising
protocol, so Codex's own experiment ran outside approval, freezing and independent verification. An agent now freezes
its code-project code as a protocol (code digest + pinned environment); the researcher approves that digest; the mission
runs every condition x seed in a fresh process; experiment.verify recomputes everything from the raw metric files.
Real subprocesses in a disposable PHDLAB_DATA_DIR; the code project's environment is the test interpreter."""
import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import _env
from backend.agent import missions as M
from backend.execution import code_projects, protocols as P, sandbox
from backend.knowledge import research_store as S, verification as V
from backend.tools import mission_tools
from backend.tools.spec import ToolError

EXPERIMENT = '''import json, os, random
seed = int(os.environ["PHDLAB_SEED"]); condition = os.environ["PHDLAB_CONDITION"]
from helper import score
rng = random.Random(seed)
noise = [rng.gauss(0, 0.01) for _ in range(5)]
acc = score(condition) + sum(noise) / len(noise)
json.dump({"metrics": {"accuracy": acc, "loss": 1 - acc}}, open(os.path.join(os.environ["PHDLAB_OUT"], "metrics.json"), "w"))
print("ran", condition, seed)
'''
HELPER = 'def score(condition):\n    return {"baseline": 0.70, "method": 0.80}[condition]\n'


class AgentProtocol(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("agent protocol tests")
        sandbox.save_settings({"python_mode": "existing", "python_base": sys.executable})
        self.tid = _env.legacy_topic(S.TopicInput(title="Agent experiments"))["id"]
        self.code = code_projects.active_dir()
        (self.code / "experiment.py").write_text(EXPERIMENT, "utf-8")
        (self.code / "helper.py").write_text(HELPER, "utf-8")

    def args(self, **extra):
        return {"topic_id": self.tid, "hypothesis": "The method beats the baseline", "entrypoint": "experiment.py",
                "conditions": ["baseline", "method"], "baseline": "baseline", "metrics": ["accuracy", "loss"],
                "primary_metric": "accuracy", "min_effect": 0.05, **extra}

    def propose(self, **extra):
        made = mission_tools.propose_protocol(self.args(**extra), None)
        return P.get(self.tid, made["protocol_id"]), made

    def run_once(self, p):
        p = P.approve(self.tid, p["id"], p["digest"], "Reviewed the frozen agent code")
        m = P.mission_draft(self.tid, p["id"])
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Run the approved agent experiment")
        for _ in range(6):
            asyncio.run(M.tick())
        runs = P.runs(self.tid)
        return (runs[0] if runs else None), M.get(m["id"], self.tid)

    def test_agent_code_runs_frozen_and_verifies_with_a_reproduction(self):
        p, made = self.propose()
        self.assertEqual((made["status"], made["files"], made["trials"]), ("awaiting_approval", 2, 6))
        first, mission = self.run_once(p)
        self.assertEqual(first["status"], "completed", first["payload"].get("error"))
        self.assertEqual(mission["status"], "completed")
        comparison = first["payload"]["comparison"]
        self.assertEqual(comparison["selected_condition"], "method")
        self.assertEqual(comparison["effects"]["method"]["recommendation"], "candidate_improvement")
        self.assertAlmostEqual(comparison["effects"]["method"]["paired_improvement"], 0.10, places=6)
        alone = V.verify_run(self.tid, first["id"])
        self.assertEqual(alone["status"], "passed", [c for c in alone["checks"] if c["status"] != "passed"])
        self.assertIsNone(alone["reproduction_run_id"])
        second, _ = self.run_once(p)  # a second, separately approved run of the same digest
        report = V.verify_run(self.tid, second["id"])
        self.assertEqual((report["status"], report["reproduction_run_id"]), ("passed", first["id"]))
        self.assertEqual(report["verifier"], "agent-code-recompute-v1")

    def test_later_edits_never_change_the_frozen_code(self):
        p, _ = self.propose()
        (self.code / "helper.py").write_text('def score(condition):\n    return 0.99\n', "utf-8")
        run, _ = self.run_once(p)
        self.assertEqual(run["payload"]["comparison"]["per_condition"]["baseline"]["mean"]["accuracy"] < 0.8, True)
        again, made = self.propose()
        self.assertNotEqual(again["payload"]["code_digest"], p["payload"]["code_digest"])

    def test_tampered_snapshot_or_environment_drift_refuses_to_run(self):
        from backend.execution import agent_protocols as AP
        p, _ = self.propose()
        frozen = AP._code_store(p["payload"]["code_digest"]) / "helper.py"
        frozen.write_text('def score(condition):\n    return 1.0\n', "utf-8")
        run, mission = self.run_once(p)
        self.assertIsNone(run)  # refused before admission: no run recorded
        self.assertNotEqual(mission["status"], "completed")
        self.assertIn("Frozen code changed", json.dumps(mission))
        frozen.write_text(HELPER, "utf-8")
        p2, _ = self.propose(seeds=[1, 2, 3])
        with patch.object(AP, "environment", return_value={"engine": "python", "digest": "other"}):
            run, mission = self.run_once(p2)
        self.assertIsNone(run)
        self.assertIn("pinned environment changed", json.dumps(mission))

    def test_failing_code_and_missing_metric_fail_the_run(self):
        (self.code / "experiment.py").write_text('import sys\nsys.exit(3)\n', "utf-8")
        p, _ = self.propose()
        run, mission = self.run_once(p)
        self.assertEqual(run["status"], "failed")
        self.assertIn("exited with 3", run["payload"]["error"])
        self.assertTrue(Path(run["trials"][0]["payload"]["folder"], "stderr.log").is_file())
        (self.code / "experiment.py").write_text(EXPERIMENT.replace('"loss": 1 - acc', '"lose": 1'), "utf-8")
        p, _ = self.propose()
        run, _ = self.run_once(p)
        self.assertIn("Registered metric loss", run["payload"]["error"])
        self.assertEqual(V.verify_run(self.tid, run["id"])["status"], "failed")

    def test_falsified_summary_or_metric_file_fails_verification(self):
        run, _ = self.run_once(self.propose()[0])
        with S.db() as c:
            payload = run["payload"]
            payload["comparison"]["effects"]["method"]["paired_improvement"] += 0.5
            c.execute("UPDATE experiment_runs SET payload=? WHERE id=?", (S.dumps(payload), run["id"]))
        failed = {c["check"] for c in V.verify_run(self.tid, run["id"])["checks"] if c["status"] == "failed"}
        self.assertIn("comparison_recomputed", failed)
        artifact = Path(run["trials"][0]["payload"]["artifact"]["path"])
        artifact.write_text(json.dumps({"metrics": {"accuracy": 0.99, "loss": 0.01}}), "utf-8")
        failed = {c["check"] for c in V.verify_run(self.tid, run["id"])["checks"] if c["status"] == "failed"}
        self.assertIn(run["trials"][0]["trial_key"] + ":sha256", failed)

    def test_invalid_protocols_are_rejected(self):
        for bad in ({"baseline": "other"}, {"entrypoint": "../outside.py"}, {"entrypoint": "C:/x.py"},
                    {"entrypoint": "missing.py"}, {"primary_metric": "f1"}, {"conditions": ["baseline"]},
                    {"engine": "docker", "docker_image": "python:latest"}):
            with self.subTest(bad=bad), self.assertRaises(ToolError) as e:
                mission_tools.propose_protocol(self.args(**bad), None)
            self.assertEqual(e.exception.code, "invalid_input")
        code_projects.close()
        with self.assertRaises(ToolError) as e:
            mission_tools.propose_protocol(self.args(), None)
        self.assertEqual(e.exception.code, "unavailable")

    def test_status_tool_reveals_the_run_reference_only_after_approval(self):
        p, _ = self.propose()
        ask = {"topic_id": self.tid, "protocol_id": p["id"]}
        self.assertEqual(mission_tools.protocol_status(ask, None), {"protocol_id": p["id"], "status": "awaiting_approval"})
        with self.assertRaises(ValueError):
            P.mission_draft(self.tid, p["id"])  # no mission before the researcher approves
        approved = P.approve(self.tid, p["id"], p["digest"], "Reviewed")
        ref = mission_tools.protocol_status(ask, None)
        self.assertEqual(ref["experiment_run_args"]["approval_nonce"], approved["approval"]["nonce"])
        m = P.mission_draft(self.tid, p["id"])
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Run")
        for _ in range(6):
            asyncio.run(M.tick())
        self.assertEqual(mission_tools.protocol_status(ask, None)["status"], "approval_used")
        with self.assertRaises(ToolError):
            mission_tools.protocol_status({"topic_id": self.tid, "protocol_id": "nope"}, None)

    def test_a_trial_over_its_budget_is_stopped(self):
        (self.code / "experiment.py").write_text('import time\ntime.sleep(30)\n', "utf-8")
        p, _ = self.propose(trial_seconds=1)
        t0 = time.monotonic()
        run, _ = self.run_once(p)
        self.assertLess(time.monotonic() - t0, 25)
        self.assertIn("1 s budget", run["payload"]["error"])

    def test_the_api_accepts_an_agent_code_protocol(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        r = TestClient(app).post(f"/api/research/topics/{self.tid}/protocols", json={**self.args(), "kind": "agent_code_v1"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["payload"]["kind"], "agent_code_v1")
        r = TestClient(app).post(f"/api/research/topics/{self.tid}/protocols", json={"topic_id": self.tid, "hypothesis": "Fixture"})
        self.assertEqual(r.status_code, 200, r.text)  # the built-in protocol is unchanged
        self.assertNotIn("kind", r.json()["payload"])


if __name__ == "__main__":
    unittest.main()
