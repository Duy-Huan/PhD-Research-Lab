import _env
import asyncio
import json
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch,AsyncMock
from backend.core import config
from backend.agent import missions as M,research_os as O,decision_ledger as L
from backend.agent.mission_contracts import MissionSpec
from backend.knowledge import research_store as S,corpus as K


class ResearchOS(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project("Research OS",code_project=None)
        config.save_config({"research_os":{"enabled":True}})
        self.tid=S.save_topic(S.TopicInput(title="MRI"))["id"]
        self.other=S.save_topic(S.TopicInput(title="CT"))["id"]

    def spec(self,**values):
        data={"topic_id":self.tid,"objective":"Inspect and report","permissions":["workspace_write"],"control":{"success_criteria":["Hashed report"],"end_date":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},"tasks":[{"id":"inspect","capability":"paper.inspect"},{"id":"report","capability":"mission.report","depends_on":["inspect"]}]}
        data.update(values);return MissionSpec.model_validate(data)

    def approve(self,spec):
        m=M.create(spec);O.request_approval(self.tid,m["id"])
        return M.approve(self.tid,m["id"],m["payload"]["plan_digest"],"Researcher reviewed exact scope, engine and budgets")

    def drive(self,n=4):
        for _ in range(n):asyncio.run(M.tick())

    def test_supervised_lifecycle_report_review_and_artifact(self):
        m=self.approve(self.spec())
        with patch("backend.providers.models.call_agent",side_effect=AssertionError("No inference")):self.drive()
        self.assertEqual(M.get(m["id"])["status"],"awaiting_review")
        with self.assertRaises(ValueError):O.review(self.other,m["id"],"Wrong Topic")
        O.review(self.tid,m["id"],"Inspected evidence; claims remain separately pending")
        self.assertEqual(M.get(m["id"])["status"],"completed")
        self.assertTrue(O.artifact(self.tid,m["id"],"report",0).is_file())
        self.assertTrue(O.report(self.tid,m["id"])["audit"]["project_chain_valid"])

    def test_schedule_deadline_opt_in_and_pause(self):
        spec=self.spec();spec.control.not_before=datetime.now(timezone.utc)+timedelta(minutes=5)
        m=self.approve(spec);self.drive(1)
        self.assertEqual(M.get(m["id"])["status"],"scheduled")
        O.pause(self.tid,m["id"],"Wait for manual input")
        config.save_config({"research_os":{"enabled":False}})
        with self.assertRaises(ValueError):M.approve(self.tid,m["id"],m["payload"]["plan_digest"],"Cannot enable implicitly")
        expired=self.spec();expired.control.end_date=datetime.now(timezone.utc)-timedelta(seconds=1)
        with self.assertRaises(ValueError):M.create(expired)

    def test_cross_topic_charter_explicit_retrieval_and_budget(self):
        ch=O.create_charter(O.ProjectCharter(goal="Image restoration",topics=[O.TopicGoal(topic_id=self.tid,goal="MRI"),O.TopicGoal(topic_id=self.other,parent_topic_id=self.tid,goal="CT")],max_active_seconds=1))
        spec=self.spec();spec.control.charter_id=ch["id"];spec.control.charter_digest=ch["digest"]
        m=M.create(spec);self.assertEqual(O.report(self.tid,m["id"])["related_topics"],[])
        grant=O.ProjectCharter.model_validate({**ch["payload"],"retrieval":[{"requester_topic":self.tid,"source_topic":self.other}],"predecessor_id":ch["id"]})
        allowed=O.create_charter(grant);spec.control.charter_id=allowed["id"];spec.control.charter_digest=allowed["digest"]
        m=self.approve(spec);self.assertEqual(len(O.report(self.tid,m["id"])["related_topics"]),1)
        with S.db() as c:c.execute("UPDATE charter_usage SET active_seconds=2 WHERE charter_id=?",(allowed["id"],))
        self.drive(1);self.assertEqual(M.get(m["id"])["status"],"paused")
        with self.assertRaises(ValueError):O.ProjectCharter(goal="cycle",topics=[O.TopicGoal(topic_id=self.tid,parent_topic_id=self.other,goal="a"),O.TopicGoal(topic_id=self.other,parent_topic_id=self.tid,goal="b")])

    def comparison(self):
        ids=K.ingest(self.tid,[{"title":"fixture A","source":"fixture"},{"title":"fixture B","source":"fixture"}])["paper_ids"]
        spec=self.spec(tasks=[{"id":"compare","capability":"paper.compare","preferred_engine":"app","args":{"paper_ids":ids}}],permissions=["workspace_write","network","reasoning"])
        spec.control.allowed_engines=["app"];spec.control.app_model="fixture-model";return spec

    def test_no_hidden_billing_and_quota_cooldown(self):
        spec=self.comparison();spec.control.app_backend="anthropic"
        with self.assertRaises(ValueError):M.create(spec)
        spec.control.app_backend="ollama";m=self.approve(spec)
        with patch("backend.providers.models.local_chat",new=AsyncMock(side_effect=RuntimeError("429 quota exhausted"))) as local,patch("backend.providers.models.cloud_chat",new=AsyncMock(side_effect=AssertionError("No fallback billing"))):
            self.drive(1);self.assertEqual(local.await_count,1)
            other=self.approve(spec);self.drive(1)
            self.assertEqual(M.get(other["id"])["status"],"paused");self.assertEqual(local.await_count,1)
        self.assertEqual(M.get(m["id"])["status"],"failed")

    def test_restart_never_repeats_uncertain_admission(self):
        m=self.approve(self.spec())
        with S.db() as c:
            c.execute("UPDATE missions SET status='running' WHERE id=?",(m["id"],))
            c.execute("UPDATE mission_tasks SET status='running' WHERE mission_id=? AND id='inspect'",(m["id"],))
        M.recover();self.drive(2)
        self.assertEqual(M.get(m["id"])["status"],"interrupted")
        with self.assertRaises(ValueError):M.retry(self.tid,m["id"],"inspect")

    def test_native_no_opaque_billing_without_approval(self):
        spec=self.comparison();spec.tasks[0].preferred_engine="feynman";spec.control.allowed_engines=["feynman"]
        with self.assertRaises(ValueError):M.create(spec)


if __name__=="__main__":unittest.main()
