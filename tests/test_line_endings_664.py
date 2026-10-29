"""FQC-LINE-ENDINGS-664 (agent/PLAN_6.6.4_L3.md A11): approvals do not depend on line endings.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): the run's approval was a file the QA operator wrote,
and the agent's own code hashed a CRLF copy of it, so an LF approval failed. Since A2 an approval is the app's digest of
canonical JSON over a frozen byte snapshot: an editor or git converting the working copy's line endings after approval
neither breaks the approved run nor changes what runs, and a new proposal records the new bytes."""
import asyncio
import json
import sys
import unittest

import _env
from backend.agent import missions as M
from backend.execution import code_projects, protocols as P, sandbox
from backend.knowledge import research_store as S, verification as V
from backend.tools import mission_tools

EXPERIMENT = ("import json, os\r\nseed = int(os.environ['PHDLAB_SEED'])\r\nbase = {'baseline': 0.7, 'method': 0.8}[os.environ['PHDLAB_CONDITION']]\r\n"
              "json.dump({'metrics': {'accuracy': base + seed / 1000}}, open(os.path.join(os.environ['PHDLAB_OUT'], 'metrics.json'), 'w'))\r\n")


class LineEndings(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("line endings tests")
        sandbox.save_settings({"python_mode": "existing", "python_base": sys.executable})
        self.tid = _env.legacy_topic(S.TopicInput(title="Line endings"))["id"]
        self.file = code_projects.active_dir() / "experiment.py"
        self.file.write_bytes(EXPERIMENT.encode())

    def propose(self):
        made = mission_tools.propose_protocol({"topic_id": self.tid, "hypothesis": "Method beats baseline", "entrypoint": "experiment.py",
                                               "conditions": ["baseline", "method"], "baseline": "baseline", "metrics": ["accuracy"],
                                               "primary_metric": "accuracy", "seeds": [1, 2, 3]}, None)
        return P.get(self.tid, made["protocol_id"])

    def test_converting_the_working_copy_after_approval_keeps_the_approved_run(self):
        p = self.propose()
        approved = P.approve(self.tid, p["id"], p["digest"], "Reviewed the frozen CRLF code")
        self.file.write_bytes(EXPERIMENT.replace("\r\n", "\n").encode())  # an editor or git converts to LF
        m = P.mission_draft(self.tid, approved["id"])
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Run")
        for _ in range(6):
            asyncio.run(M.tick())
        run = P.runs(self.tid)[0]
        self.assertEqual(run["status"], "completed", run["payload"].get("error"))
        self.assertEqual(V.verify_run(self.tid, run["id"])["status"], "passed")
        frozen = next(f for f in approved["payload"]["code_manifest"] if f["path"] == "experiment.py")
        self.assertEqual(frozen["bytes"], len(EXPERIMENT.encode()))  # the CRLF bytes that were approved are what ran

    def run_approved(self, p):
        m = P.mission_draft(self.tid, p["id"])
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Run")
        for _ in range(6):
            asyncio.run(M.tick())
        return M.get(m["id"], self.tid)

    def test_converting_the_frozen_copy_is_refused(self):
        from backend.execution import agent_protocols as AP
        p = self.propose()
        p = P.approve(self.tid, p["id"], p["digest"], "Reviewed")
        frozen = AP._code_store(p["payload"]["code_digest"]) / "experiment.py"
        frozen.write_bytes(frozen.read_bytes().replace(b"\r\n", b"\n"))
        mission = self.run_approved(p)
        self.assertEqual(P.runs(self.tid), [])
        self.assertIn("Frozen code changed", json.dumps(mission))

    def test_mixed_line_endings_are_copied_byte_for_byte(self):
        mixed = EXPERIMENT.replace("\r\n", "\n", 1).encode()  # first line LF, the rest CRLF
        self.file.write_bytes(mixed)
        p = self.propose()
        self.run_approved(P.approve(self.tid, p["id"], p["digest"], "Reviewed"))
        trial = P.runs(self.tid)[0]["trials"][0]
        from pathlib import Path
        self.assertEqual((Path(trial["payload"]["folder"]) / "code" / "experiment.py").read_bytes(), mixed)

    def test_a_converted_result_file_fails_verification(self):
        p = self.propose()
        self.run_approved(P.approve(self.tid, p["id"], p["digest"], "Reviewed"))
        run = P.runs(self.tid)[0]
        from pathlib import Path
        artifact = Path(run["trials"][0]["payload"]["artifact"]["path"])
        artifact.write_bytes(artifact.read_bytes().replace(b"\n", b"\r\n") + b"\r\n")
        failed = {c["check"] for c in V.verify_run(self.tid, run["id"])["checks"] if c["status"] == "failed"}
        self.assertIn(run["trials"][0]["trial_key"] + ":sha256", failed)  # integrity is byte-exact

    def test_the_approval_digest_is_canonical_json_and_new_bytes_need_a_new_protocol(self):
        p = self.propose()
        from backend.agent import decision_ledger as L
        self.assertEqual(p["digest"], L.digest(p["payload"]))
        self.assertEqual(L.digest(json.loads(json.dumps(p["payload"]))), p["digest"])  # independent of how it is stored
        self.file.write_bytes(EXPERIMENT.replace("\r\n", "\n").encode())
        again = self.propose()
        self.assertNotEqual(again["payload"]["code_digest"], p["payload"]["code_digest"])  # different bytes, new approval


if __name__ == "__main__":
    unittest.main()
