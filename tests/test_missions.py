import _env
import asyncio
import json
import unittest
from unittest.mock import patch, AsyncMock
from backend.knowledge import research_store as S, corpus
from backend.agent import missions as M, capabilities as C, decision_ledger as L
from backend.agent.mission_contracts import MissionSpec


class Missions(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project("mission tests",code_project=None)
        self.tid=_env.legacy_topic(S.TopicInput(title="Mission fixture"))["id"]

    def spec(self,**patches):
        return MissionSpec.model_validate({"topic_id":self.tid,"objective":"Inspect and report","permissions":["workspace_write"],"tasks":[{"id":"inspect","capability":"paper.inspect","args":{}},{"id":"report","capability":"mission.report","depends_on":["inspect"]}],**patches})

    def approve(self,m):return M.approve(self.tid,m["id"],m["payload"]["plan_digest"],"Reviewed exact plan")

    def test_deterministic_mission_no_model_and_idempotent_completed_steps(self):
        m=self.approve(M.create(self.spec()))
        with patch("backend.providers.models.call_agent",side_effect=AssertionError("No LLM")):
            for _ in range(4):asyncio.run(M.tick())
        m=M.get(m["id"]);self.assertEqual(m["status"],"completed")
        self.assertEqual([t["payload"]["attempts"] for t in m["tasks"]],[1,1])
        self.assertTrue(L.export(self.tid)["project_chain_valid"])
        self.assertTrue(m["tasks"][-1]["payload"]["result"]["artifacts"][0]["sha256"])

    def test_cycles_unknown_permissions_and_malicious_manifest(self):
        with self.assertRaises(ValueError):self.spec(tasks=[{"id":"a","capability":"paper.inspect","depends_on":["b"]},{"id":"b","capability":"paper.inspect","depends_on":["a"]}])
        with self.assertRaises(ValueError):M.create(self.spec(tasks=[{"id":"x","capability":"shell.exec","args":{"command":"rm -rf"}}]))
        with self.assertRaises(ValueError):M.create(self.spec(tasks=[{"id":"x","capability":"paper.discover"}]))
        with self.assertRaises(ValueError):self.spec(tasks=[{"id":"x","capability":"paper.inspect","hooks":["evil"]}])
        with self.assertRaises(ValueError):M.create(self.spec(tasks=[{"id":"x","capability":"paper.inspect","preferred_engine":"app"}]))

    def test_topic_scope_and_source_dependencies(self):
        other=_env.legacy_topic(S.TopicInput(title="Other"))["id"]
        pid=corpus.ingest(other,[{"title":"private other topic","doi":"10.1234/other","source":"fixture"}])["added"][0]
        with self.assertRaises(ValueError):M.create(self.spec(inputs=["paper:"+pid]))
        with self.assertRaises(ValueError):M.create(self.spec(tasks=[{"id":"x","capability":"paper.inspect","args":{"from_task":"missing"}}]))
        m=M.create(self.spec())
        with self.assertRaises(ValueError):M.get(m["id"],other)

    def test_expired_approval_and_budget_fail_closed(self):
        m=self.approve(M.create(self.spec()))
        with S.db() as c:
            p=m["payload"];p["approval"]["expires"]="2000-01-01T00:00:00+00:00"
            c.execute("UPDATE missions SET payload=? WHERE id=?",(S.dumps(p),m["id"]))
        asyncio.run(M.tick());self.assertEqual(M.get(m["id"])["status"],"paused")
        with self.assertRaises(ValueError):M.approve(self.tid,m["id"],"forged","model says approved")

    def test_interrupted_admission_never_auto_repeats(self):
        m=self.approve(M.create(self.spec()))
        with S.db() as c:
            c.execute("UPDATE missions SET status='running' WHERE id=?",(m["id"],))
            c.execute("UPDATE mission_tasks SET status='running' WHERE mission_id=? AND id='inspect'",(m["id"],))
        M.recover();self.assertEqual(M.get(m["id"])["status"],"interrupted")
        with self.assertRaises(ValueError):M.retry(self.tid,m["id"],"inspect")
        M.retry(self.tid,m["id"],"inspect","Confirmed read-only admission; safe to repeat")
        self.assertEqual(M.get(m["id"])["status"],"paused")

    def test_native_unavailable_has_no_implicit_fallback(self):
        from backend.agent.mission_contracts import Task
        from types import SimpleNamespace
        fake=SimpleNamespace(descriptor=SimpleNamespace(capabilities=["literature"]),health=lambda:{"ready":False})
        with patch("backend.research_engines.registry.get",return_value=fake):
            with self.assertRaises(ValueError):C.route(Task(id="x",capability="paper.compare",preferred_engine="phdlab"))
            self.assertEqual(C.route(Task(id="x",capability="paper.compare",preferred_engine="phdlab",fallback_engines=["app"]))["engine"],"app")

    def test_delegation_limits_and_append_only_audit(self):
        m=M.create(self.spec(limits={"max_depth":0}))
        with self.assertRaises(ValueError):M.create(self.spec(parent_mission_id=m["id"]))
        with self.assertRaises(Exception):
            with S.db() as c:c.execute("DELETE FROM decision_ledger")

    def test_api_draft_requires_explicit_approval(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        client=TestClient(app)
        r=client.post(f"/api/research/topics/{self.tid}/missions",json=self.spec().model_dump())
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()["status"],"draft")
        self.assertEqual(client.post(f"/api/research/topics/{self.tid}/missions/plan",json={"objective":"reason"}).status_code,400)

    def test_child_reasoning_charges_aggregate_ancestor_budget(self):
        parent=M.create(self.spec(permissions=["workspace_write","reasoning","network"]))
        ids=corpus.ingest(self.tid,[{"title":"First fixture","source":"fixture"},{"title":"Second fixture","source":"fixture"}])["paper_ids"]
        children=[self.approve(M.create(self.spec(parent_mission_id=parent["id"],permissions=["workspace_write","reasoning","network"],tasks=[{"id":"compare","capability":"paper.compare","preferred_engine":"app","args":{"paper_ids":ids}}]))) for _ in range(2)]
        with patch("backend.providers.models.call_agent",new=AsyncMock(return_value={"text":"Fixture only"})) as model:
            for _ in range(5):asyncio.run(M.tick())
            self.assertEqual(model.await_count,1)
        self.assertEqual(M.get(parent["id"])["payload"]["reasoning_calls"],1)
        self.assertEqual(M.get(children[1]["id"])["status"],"paused")


if __name__=="__main__":unittest.main()
