import _env
import asyncio
import json
import time
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from backend.core import config
from backend.agent import missions as M,teams as T,collaboration as C,research_os as O,decision_ledger as L
from backend.agent.mission_contracts import MissionSpec,CollaborationPlan,Workstream
from backend.knowledge import research_store as S,governance as G
from backend.research_engines import workspaces as W
from backend.execution import protocols as P,guard
from backend.execution.protocol_contracts import ExperimentProtocol


class Workstreams(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project("Collaboration tests",code_project=None)
        config.save_config({"research_os":{"enabled":True,"team_enabled":True,"multi_team_enabled":True}})
        self.tid=S.save_topic(S.TopicInput(title="Workstream topic"))["id"]

    def spec(self,tasks,**kw):
        data={"topic_id":self.tid,"objective":"Bounded multi-domain work","permissions":["workspace_write"],"control":{"success_criteria":["Evidence and receipts preserved"],"end_date":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},"tasks":tasks};data.update(kw)
        return MissionSpec.model_validate(data)

    def multi(self):
        a=W.link(self.tid,W.WorkspaceInput(engine="openscience"));b=W.link(self.tid,W.WorkspaceInput(engine="feynman"))
        return C.partition(self.spec([{"id":"science","capability":"workspace.sync","args":{"workspace_id":a["id"]}},{"id":"feynman","capability":"workspace.sync","args":{"workspace_id":b["id"]}},{"id":"report","capability":"mission.report","depends_on":["science","feynman"]}]))

    def approve(self,spec):
        m=M.create(spec);return M.approve(self.tid,m["id"],m["payload"]["plan_digest"],"PI reviewed bounded workstreams and artifact contracts")

    def drive(self,n=7):
        for _ in range(n):asyncio.run(M.tick())

    def test_simple_fallback_and_useful_partition(self):
        simple=C.partition(self.spec([{"id":"inspect","capability":"paper.inspect"},{"id":"report","capability":"mission.report","depends_on":["inspect"]}]))
        self.assertEqual(len(simple.collaboration.workstreams),1)
        multi=self.multi();self.assertEqual(len(multi.collaboration.workstreams),3)
        m=self.approve(multi);self.drive();view=C.monitor(self.tid,m["id"])
        self.assertEqual(view["mission"]["status"],"awaiting_review")
        self.assertEqual(len(view["messages"]),2);self.assertEqual(len(view["receipts"]),2)
        self.assertTrue(all(x["status"]=="acknowledged" for x in view["messages"]))

    def test_outage_between_publish_and_ack_reconciles_exactly_once(self):
        m=self.approve(self.multi());self.drive(1)
        before=C.monitor(self.tid,m["id"]);self.assertEqual(len(before["messages"]),1)
        self.assertEqual(before["receipts"],[])
        M.recover();self.assertEqual(M.get(m["id"])["status"],"queued")
        self.drive();after=C.monitor(self.tid,m["id"])
        self.assertEqual(len(after["messages"]),2);self.assertEqual(len(after["receipts"]),2)
        self.assertTrue(all(t["payload"]["attempts"]==1 for t in after["mission"]["tasks"]))
        message=after["messages"][0];receiver=message["payload"]["target_team"]
        C.receive(self.tid,m["id"],message["id"],receiver)
        self.assertEqual(len(C.monitor(self.tid,m["id"])["receipts"]),2)

    def test_wrong_receiver_and_forged_handoff_rejected(self):
        m=self.approve(self.multi());self.drive(1);message=C.monitor(self.tid,m["id"])["messages"][0]
        with self.assertRaises(ValueError):C.receive(self.tid,m["id"],message["id"],"invented_team")
        with self.assertRaises(Exception):
            with S.db() as c:c.execute("UPDATE collaboration_messages SET payload='{}'")
        from backend.agent.mission_contracts import WorkOrder
        with self.assertRaises(ValueError):WorkOrder.model_validate({**message["payload"],"approved":True})

    def test_canonical_version_conflict_keeps_original_and_distinct_files(self):
        spec=T.propose(self.spec([{"id":"left","capability":"mission.report"},{"id":"right","capability":"mission.report"}]),"fixed")
        spec.collaboration=CollaborationPlan(rationale="Explicit competing report proposals",workstreams=[Workstream(id=name,topic_id=self.tid,objective=name,task_ids=[name],permissions=["workspace_write"],max_active_seconds=300,max_artifact_mb=16,deliverables=["Owned report"]) for name in ("left","right")])
        m=self.approve(spec);self.drive()
        a=O.artifact(self.tid,m["id"],"left",0);b=O.artifact(self.tid,m["id"],"right",0)
        self.assertNotEqual(a,b)
        C.canonical(self.tid,m["id"],"left","canonical-report","left",0,0,"PI selected candidate")
        with self.assertRaises(ValueError):C.canonical(self.tid,m["id"],"right","canonical-report","right",0,0,"Stale competing update")
        view=C.monitor(self.tid,m["id"])
        self.assertEqual(view["canonical_outputs"][0]["payload"]["owner_team"],"left")
        self.assertTrue(any(e["kind"]=="workstream.canonical_conflict" for e in L.export(self.tid)["events"]))

    def test_dispute_blocks_review_and_never_approves_claim(self):
        m=self.approve(self.multi());self.drive()
        team=m["payload"]["spec"]["collaboration"]["workstreams"][0]["id"]
        claim=C.finding(self.tid,m["id"],team,G.ClaimInput(text="I claim a large improvement without data",kind="tentative_interpretation"))
        self.assertEqual(claim["status"],"proposed")
        dispute=C.dispute(self.tid,m["id"],team,"Unsupported result",[claim["id"]])
        with self.assertRaises(ValueError):O.review(self.tid,m["id"],"Cannot hide dispute")
        C.resolve(self.tid,m["id"],dispute["id"],1,"PI leaves claim unverified, follow-up required")
        with self.assertRaises(ValueError):C.resolve(self.tid,m["id"],dispute["id"],1,"Stale decision")
        O.review(self.tid,m["id"],"Technical work reviewed; claim not approved")
        self.assertEqual(G.get(self.tid,claim["id"])["status"],"proposed")

    def test_topic_and_project_isolation_and_escalation_audit(self):
        spec=self.multi();m=self.approve(spec)
        other=S.save_topic(S.TopicInput(title="Private other Topic"))["id"]
        with self.assertRaises(ValueError):C.monitor(other,m["id"])
        spec.collaboration.workstreams[0].topic_id=other
        with self.assertRaises(ValueError):M.create(spec)
        self.assertTrue(any(e["kind"]=="policy.mission_rejected" for e in L.export(self.tid)["events"]))
        _env.fresh_project("Separate project",code_project=None)
        with self.assertRaises(ValueError):C.monitor(self.tid,m["id"])

    def test_central_gpu_limit_and_workstream_accounting(self):
        with self.assertRaises(ValueError):ExperimentProtocol(topic_id=self.tid,hypothesis="No implicit GPU",gpu=True)
        guard.try_acquire("gpu","workstream-fixture-a",gpu_check=False)
        try:
            with self.assertRaises(guard.Busy):guard.try_acquire("gpu","workstream-fixture-b",gpu_check=False)
        finally:guard.release("gpu","workstream-fixture-a")
        m=self.approve(self.multi())
        with S.db() as c:c.execute("UPDATE workstream_usage SET active_seconds=10000 WHERE mission_id=?",(m["id"],))
        self.drive(1);self.assertEqual(M.get(m["id"])["status"],"paused")

    def test_failed_native_domain_does_not_fake_other_domain_completion(self):
        m=self.approve(self.multi());original=W.sync
        def failed(wid,*args,**kwargs):
            if W.get(wid)["engine"]=="openscience":raise ValueError("Native workspace unavailable")
            return original(wid,*args,**kwargs)
        with patch.object(W,"sync",side_effect=failed):self.drive(1)
        tasks=M.get(m["id"])["tasks"]
        self.assertEqual(tasks[0]["status"],"failed");self.assertEqual(tasks[1]["status"],"pending")
        self.assertEqual(C.monitor(self.tid,m["id"])["messages"],[])

    def test_verifier_opens_dispute_on_unsupported_performance_output(self):
        from backend.knowledge import corpus as K
        from unittest.mock import AsyncMock
        ids=K.ingest(self.tid,[{"title":"Fixture a","source":"fixture"},{"title":"Fixture b","source":"fixture"}])["paper_ids"]
        spec=self.spec([{"id":"inspect","capability":"paper.inspect"},{"id":"compare","capability":"paper.compare","preferred_engine":"app","args":{"paper_ids":ids}},{"id":"report","capability":"mission.report","depends_on":["inspect","compare"]}],permissions=["network","reasoning","workspace_write"])
        spec.control.allowed_engines=["deterministic","app"];spec.control.app_model="fixture"
        m=self.approve(C.partition(spec))
        with patch("backend.providers.models.local_chat",new=AsyncMock(return_value="My result improves PSNR by 999 dB without raw data")):self.drive()
        view=C.monitor(self.tid,m["id"])
        self.assertTrue(any(d["status"]=="open" for d in view["disputes"]))
        with self.assertRaises(ValueError):O.review(self.tid,m["id"],"Cannot accept unsupported science")

    def test_download_preflight_denies_overallocated_storage_before_network(self):
        from backend.knowledge import corpus as K
        ids=K.ingest(self.tid,[{"title":"Fixture pdf a","source":"fixture"},{"title":"Fixture pdf b","source":"fixture"}])["paper_ids"]
        spec=C.partition(self.spec([{"id":"download","capability":"paper.download","args":{"paper_ids":ids,"limit":2}}],permissions=["network","workspace_write"]))
        m=self.approve(spec)
        with patch("backend.knowledge.download.pdf_bytes_limited",side_effect=AssertionError("No network when budget cannot fit")):self.drive(1)
        current=M.get(m["id"]);self.assertEqual(current["status"],"paused")
        self.assertIn("PDF worst-case",current["payload"]["blocking_reason"])

    def test_download_charges_actual_content_bytes_after_indexing(self):
        from backend.knowledge import corpus as K
        from unittest.mock import AsyncMock
        from pdfgen import make_pdf
        pid=K.ingest(self.tid,[{"title":"PDF fixture","source":"fixture"}])["paper_ids"][0]
        pdf=make_pdf([[(12,"Actual indexed fixture page")]])
        spec=C.partition(self.spec([{"id":"download","capability":"paper.download","args":{"paper_ids":[pid],"limit":1}}],permissions=["network","workspace_write"]))
        m=self.approve(spec)
        location={"url":"https://example.org/fixture.pdf","license":"cc0-fixture","version":"fixture"}
        with patch("backend.knowledge.sources.resolve_oa",new=AsyncMock(return_value=[location])),patch("backend.knowledge.download.pdf_bytes_limited",new=AsyncMock(return_value=pdf)):
            self.drive(3)
        view=C.monitor(self.tid,m["id"])
        self.assertEqual(view["mission"]["status"],"awaiting_review")
        self.assertEqual(view["usage"][0]["artifact_bytes"],len(pdf))

    def test_schema6_migration_preserves_pending_team_mission_and_backup(self):
        import sqlite3
        pending=M.create(T.propose(self.spec([{"id":"inspect","capability":"paper.inspect"},{"id":"report","capability":"mission.report","depends_on":["inspect"]}])))
        path=S.store_dir()/"research.sqlite3"
        with sqlite3.connect(path) as old:
            for table in ("handoff_receipts","collaboration_messages","collaboration_disputes","canonical_revisions","canonical_outputs","workstream_usage"):old.execute("DROP TABLE "+table)
            old.execute("PRAGMA user_version=6");old.execute("UPDATE meta SET value='6' WHERE key='schema'")
        restored=M.get(pending["id"],self.tid)
        self.assertEqual(restored["payload"]["plan_digest"],pending["payload"]["plan_digest"])
        with sqlite3.connect(S.store_dir()/"research.v6.sqlite3.bak") as backup:
            self.assertEqual(backup.execute("PRAGMA user_version").fetchone()[0],6)
            self.assertEqual(backup.execute("SELECT status FROM missions WHERE id=?",(pending["id"],)).fetchone()[0],"draft")
        M.approve(self.tid,pending["id"],pending["payload"]["plan_digest"],"Existing team mission remains reviewable after migration")
        self.drive();self.assertEqual(M.get(pending["id"])["status"],"awaiting_review")


if __name__=="__main__":unittest.main()
