"""Adversarial checks of exported real CPU measurements; no new inference or compute."""
import _env
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tools.verify_v6_harness import VerificationError, verify_bundle

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts/upgrade-reconciliation/harness"


class HarnessVerification(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phdlab-harness-verifier-")
        self.folder = Path(self.temporary.name).resolve()
        self.assertEqual(self.folder.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.folder.name.startswith("phdlab-harness-verifier-"))
        self.addCleanup(self.temporary.cleanup)
        for name in ("harness.json", "measurements.zip"):
            shutil.copyfile(FIXTURE / name, self.folder / name)
        self.report = json.loads((self.folder / "harness.json").read_text("utf-8"))

    def save(self):
        (self.folder / "harness.json").write_text(json.dumps(self.report), "utf-8")

    def replace_zip_entry(self, name, data):
        with zipfile.ZipFile(self.folder / "measurements.zip") as archive:
            entries = {n: archive.read(n) for n in archive.namelist()}
        entries[name] = data
        with zipfile.ZipFile(self.folder / "measurements.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for key, value in entries.items():
                archive.writestr(key, value)

    def test_real_bundle_recomputes_metrics_and_discloses_old_format_limit(self):
        result = verify_bundle(self.folder, "6.3")
        self.assertTrue(result["passed"])
        self.assertEqual(result["checks"]["missions"], 8)
        self.assertEqual(result["checks"]["raw_samples"], 480)
        self.assertFalse(result["checks"]["raw_control_plane"])
        self.assertTrue(result["limitations"])
        with self.assertRaisesRegex(VerificationError, "snapshots missing"):
            verify_bundle(self.folder, "6.3", require_raw=True)

    def test_incorrect_stage_or_missing_workflow_fails_even_with_success_status(self):
        self.report["rows"].pop()
        self.save()
        with self.assertRaisesRegex(VerificationError, "workflow or mode"):
            verify_bundle(self.folder, "6.3")
        result = subprocess.run([sys.executable, "-O", "-B", str(ROOT / "tools/verify_v6_harness.py"), "--verify-only", str(self.folder), "--stage", "6.3"], capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"workflow or mode", result.stderr)

    def test_duplicate_mission_and_failed_task_are_not_hidden_by_passed_row(self):
        self.report["rows"][1]["mission_id"] = self.report["rows"][0]["mission_id"]
        self.save()
        with self.assertRaisesRegex(VerificationError, "Duplicate mission"):
            verify_bundle(self.folder, "6.3")
        self.report = json.loads((FIXTURE / "harness.json").read_text("utf-8"))
        self.report["mission_reports"][0]["mission"]["tasks"][0]["status"] = "failed"
        self.save()
        with self.assertRaisesRegex(VerificationError, "Task failed"):
            verify_bundle(self.folder, "6.3")

    def test_altered_artifact_is_detected_with_a_valid_zip_crc(self):
        trial = self.report["experiment_runs"][0]["trials"][0]
        name = f"{trial['run_id']}/{trial['id']}/observations.json"
        self.replace_zip_entry(name, b'{"forged":true}')
        with self.assertRaisesRegex(VerificationError, "checksum/size"):
            verify_bundle(self.folder, "6.3")

    def test_fabricated_metric_rejected_even_after_checksum_is_updated(self):
        trial = self.report["experiment_runs"][0]["trials"][0]
        name = f"{trial['run_id']}/{trial['id']}/observations.json"
        with zipfile.ZipFile(self.folder / "measurements.zip") as archive:
            data = json.loads(archive.read(name))
        data["observations"][0]["mse"] += 1
        raw = json.dumps(data, separators=(",", ":")).encode()
        self.replace_zip_entry(name, raw)
        trial["payload"]["artifact"].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        self.save()
        with self.assertRaisesRegex(VerificationError, "Raw MSE"):
            verify_bundle(self.folder, "6.3")

    def test_audit_chain_and_receipt_receiver_tampering_fail(self):
        with zipfile.ZipFile(self.folder / "measurements.zip") as archive:
            name = next(n for n in archive.namelist() if n.startswith("audit/"))
            audit = json.loads(archive.read(name))
        audit["events"][0]["payload"] = {"forged": True}
        self.replace_zip_entry(name, json.dumps(audit).encode())
        with self.assertRaisesRegex(VerificationError, "Audit hash chain"):
            verify_bundle(self.folder, "6.3")
        shutil.copyfile(FIXTURE / "measurements.zip", self.folder / "measurements.zip")
        collab = next(s["collaboration"] for s in self.report["mission_reports"] if s.get("collaboration", {}).get("receipts"))
        collab["receipts"][0]["receiver_team"] = "forged-team"
        self.save()
        with self.assertRaisesRegex(VerificationError, "Receipt identity"):
            verify_bundle(self.folder, "6.3")

    def test_source_manifest_and_inference_counters_cannot_be_fabricated(self):
        self.report["rows"][0]["reasoning_calls"] = 1
        self.save()
        with self.assertRaisesRegex(VerificationError, "inference/GPU"):
            verify_bundle(self.folder, "6.3")
        self.report["rows"][0]["reasoning_calls"] = 0
        executions = self.report["rows"][0]["executions"]
        self.report["rows"][0]["executions"] = 999
        self.save()
        with self.assertRaisesRegex(VerificationError, "counters differ"):
            verify_bundle(self.folder, "6.3")
        self.report["rows"][0]["executions"] = executions
        self.report["source_identity"]["source_tree_sha256"] = "f" * 64
        self.save()
        with self.assertRaisesRegex(VerificationError, "Source manifest"):
            verify_bundle(self.folder, "6.3")

    def test_invented_improvement_and_held_out_metric_are_recomputed(self):
        self.report["experiment_runs"][0]["payload"]["comparison"]["paired_psnr_gain_db"] = 999
        self.save()
        with self.assertRaisesRegex(VerificationError, "Reported improvement"):
            verify_bundle(self.folder, "6.3")
        self.report = json.loads((FIXTURE / "harness.json").read_text("utf-8"))
        self.report["experiment_runs"][0]["payload"]["test_evaluations"][0]["mean_psnr_db"] = 999
        self.save()
        with self.assertRaisesRegex(VerificationError, "Held-out metrics"):
            verify_bundle(self.folder, "6.3")

    def test_real_process_exit_preserves_uncertain_admission_and_handoff_checkpoint(self):
        env = os.environ.copy()
        env["PHDLAB_DATA_DIR"] = str(self.folder / "restart-data")
        env["PYTHONIOENCODING"] = "utf-8"
        shared = '''import asyncio,json,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from backend.core import config
from backend.agent import missions as M,collaboration as C,decision_ledger as L
from backend.agent.mission_contracts import MissionSpec
from backend.knowledge import research_store as S
from backend.research_engines import workspaces as W
root=Path(os.environ["PHDLAB_DATA_DIR"])
'''
        first = shared + '''config.save_config({"research_os":{"enabled":True,"team_enabled":True,"multi_team_enabled":True},"memory":{"embed_engine":"hashing"}})
tid=S.save_topic(S.TopicInput(title="Actual process-outage fixture"))["id"]
locations=[root/'topics'/tid/name for name in ('experiment-context','coding-context')]
for location in locations:location.mkdir(parents=True,exist_ok=True)
ws=[W.link(tid,W.WorkspaceInput(engine='phdlab',path=str(location))) for location in locations]
control={"success_criteria":["Preserve committed receipts"],"end_date":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
spec=MissionSpec(topic_id=tid,objective="Committed cross-team checkpoint",permissions=["workspace_write"],control=control,tasks=[{"id":"science","capability":"workspace.sync","args":{"workspace_id":ws[0]["id"]}},{"id":"feynman","capability":"workspace.sync","args":{"workspace_id":ws[1]["id"]}},{"id":"report","capability":"mission.report","depends_on":["science","feynman"]}])
safe=M.create(C.partition(spec));M.approve(tid,safe["id"],safe["payload"]["plan_digest"],"Approved fixture")
asyncio.run(M.tick())
before=C.monitor(tid,safe["id"])
uncertain=M.create(MissionSpec(topic_id=tid,objective="Uncertain admission at real process exit",permissions=[],control={**control,"priority":10},tasks=[{"id":"inspect","capability":"paper.inspect"}]))
M.approve(tid,uncertain["id"],uncertain["payload"]["plan_digest"],"Approved fixture")
(root/"checkpoint.json").write_text(json.dumps({"topic":tid,"safe":safe["id"],"uncertain":uncertain["id"],"pid":os.getpid(),"published":len(before["messages"]),"receipts":len(before["receipts"])}))
async def crash(*args):
    (root/"effect.txt").write_text("one\\n")
    os._exit(23)
M._dispatch=crash
asyncio.run(M.tick())
'''
        result = subprocess.run([sys.executable, "-B", "-c", first], cwd=ROOT, env=env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 23, result.stderr.decode(errors="replace"))
        second = shared + '''state=json.loads((root/"checkpoint.json").read_text())
original=M._dispatch
async def observed(m,*args):
    if m["id"]==state["uncertain"]:
        with (root/"effect.txt").open("a") as f:f.write("duplicated\\n")
    return await original(m,*args)
M._dispatch=observed
M.recover()
for _ in range(8):asyncio.run(M.tick())
view=C.monitor(state["topic"],state["safe"])
uncertain=M.get(state["uncertain"])
print(json.dumps({"pid":os.getpid(),"uncertain_status":uncertain["status"],"uncertain_attempts":uncertain["tasks"][0]["payload"]["attempts"],"resumed_status":view["mission"]["status"],"attempts":[t["payload"]["attempts"] for t in view["mission"]["tasks"]],"messages":len(view["messages"]),"receipts":len(view["receipts"]),"audit_valid":L.export(state["topic"])["project_chain_valid"]}))
'''
        result = subprocess.run([sys.executable, "-B", "-c", second], cwd=ROOT, env=env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        state = json.loads((self.folder / "restart-data/checkpoint.json").read_text())
        recovered = json.loads(result.stdout)
        self.assertNotEqual(state["pid"], recovered["pid"])
        self.assertEqual((state["published"], state["receipts"]), (1, 0))
        self.assertEqual(recovered["uncertain_status"], "interrupted")
        self.assertEqual(recovered["uncertain_attempts"], 1)
        self.assertEqual(recovered["resumed_status"], "awaiting_review")
        self.assertEqual(recovered["attempts"], [1, 1, 1])
        self.assertEqual((recovered["messages"], recovered["receipts"]), (2, 2))
        self.assertTrue(recovered["audit_valid"])
        self.assertEqual((self.folder / "restart-data/effect.txt").read_text(), "one\n")
        self.evidence = {"first_process_pid": state["pid"], "first_exit": 23, **recovered,
                         "external_effect_count": 1, "initial_messages": state["published"], "initial_receipts": state["receipts"]}


if __name__ == "__main__":
    unittest.main()
