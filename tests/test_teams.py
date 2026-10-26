import _env
import asyncio
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch,AsyncMock
from types import SimpleNamespace
from backend.core import config
from backend.agent import missions as M,teams as T,research_os as O
from backend.agent.mission_contracts import MissionSpec,TaskEnvelope,ExecutionResult
from backend.knowledge import research_store as S,corpus as K
from backend.execution import protocols as P
from backend.execution.protocol_contracts import ExperimentProtocol


class Teams(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project("Team tests",code_project=None)
        config.save_config({"research_os":{"enabled":True,"team_enabled":True}})
        self.tid=_env.legacy_topic(S.TopicInput(title="Team topic"))["id"]

    def spec(self,**kw):
        data={"topic_id":self.tid,"objective":"Scoped work","permissions":["workspace_write"],"control":{"success_criteria":["Bounded evidence"],"end_date":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},"tasks":[{"id":"inspect","capability":"paper.inspect"},{"id":"report","capability":"mission.report","depends_on":["inspect"]}]};data.update(kw)
        return MissionSpec.model_validate(data)

    def approve(self,spec):
        m=M.create(spec);return M.approve(self.tid,m["id"],m["payload"]["plan_digest"],"Reviewed bounded role permissions and budgets")

    def drive(self,n=6):
        for _ in range(n):asyncio.run(M.tick())

    def comparison(self,engine="app"):
        ids=K.ingest(self.tid,[{"title":"Fixture A","source":"fixture"},{"title":"Fixture B","source":"fixture"}])["paper_ids"]
        spec=self.spec(permissions=["network","reasoning","workspace_write"],limits={"max_reasoning_calls":3},tasks=[{"id":"compare","capability":"paper.compare","preferred_engine":engine,"args":{"paper_ids":ids}}])
        spec.control.allowed_engines=["deterministic",engine];spec.control.app_model="fixture";spec.control.allow_api_billing=engine!="app"
        return T.propose(spec)

    def test_literature_chooses_minimal_team_and_durable_handoff(self):
        proposal=T.propose(self.spec());self.assertEqual(len(proposal.team.agents),1)
        with patch("backend.providers.models.call_agent",side_effect=AssertionError("No inference")),patch("backend.execution.sandbox.docker_running",side_effect=AssertionError("No Docker")):
            m=self.approve(proposal);self.drive()
        snapshot=T.monitor(self.tid,m["id"])
        self.assertEqual(snapshot["mission"]["status"],"awaiting_review");self.assertEqual(len(snapshot["handoffs"]),1)
        envelope=TaskEnvelope.model_validate(snapshot["handoffs"][0]["payload"])
        self.assertEqual(envelope.trust,"untrusted");self.assertEqual(envelope.receiver,"worker1")
        self.drive(2);self.assertEqual(len(T.monitor(self.tid,m["id"])["handoffs"]),1)
        with self.assertRaises(Exception):
            with S.db() as c:c.execute("UPDATE task_handoffs SET payload='{}'")

    def test_independent_cpu_verifier_and_reproduction(self):
        p=P.create(ExperimentProtocol(topic_id=self.tid,hypothesis="CPU fixture"))
        statuses=[]
        for _ in range(2):
            p=P.approve(self.tid,p["id"],p["digest"],"Reviewed fixture")
            spec=self.spec(permissions=["compute","workspace_write"],tasks=[{"id":"experiment","capability":"experiment.run","args":{"protocol_id":p["id"],"protocol_digest":p["digest"],"approval_nonce":p["approval"]["nonce"]}},{"id":"report","capability":"mission.report","depends_on":["experiment"]}])
            proposal=T.propose(spec);assignment=next(a for a in proposal.team.assignments if a.task_id=="experiment")
            self.assertNotEqual(assignment.owner,assignment.verifier)
            m=self.approve(proposal);self.drive()
            statuses.append(next(t["payload"]["result"]["output"]["status"] for t in M.get(m["id"])["tasks"] if t["id"]=="check_experiment"))
        self.assertEqual(statuses,["unverified","verified"])

    def test_privilege_escalation_and_self_review_rejected(self):
        spec=T.propose(self.spec());spec.team.agents[0].permissions.append("network")
        with self.assertRaises(ValueError):M.create(spec)
        spec=self.comparison();spec.team.assignments[0].verifier=spec.team.assignments[0].owner
        with self.assertRaises(ValueError):M.create(spec)
        spec=T.propose(self.spec());spec.team.agents[0].capabilities.append("shell.exec")
        with self.assertRaises(ValueError):M.create(spec)
        parent=M.create(T.propose(self.spec()))
        child=self.spec(parent_mission_id=parent["id"]);child.control=None
        with self.assertRaises(ValueError):M.create(child)

    def test_unavailable_native_pauses_without_paid_admission(self):
        spec=self.comparison("phdlab");m=self.approve(spec)
        fake=SimpleNamespace(descriptor=SimpleNamespace(capabilities=["literature"]),health=lambda:{"ready":False})
        with patch("backend.research_engines.registry.get",return_value=fake):self.drive(1)
        self.assertEqual(M.get(m["id"])["status"],"paused")
        self.assertEqual(T.monitor(self.tid,m["id"])["attempts"],[])

    def test_replan_is_draft_and_subtracts_consumption(self):
        spec=self.comparison();m=self.approve(spec)
        with patch("backend.providers.models.local_chat",new=AsyncMock(side_effect=RuntimeError("429 quota exhausted"))):self.drive(1)
        draft=T.replan(self.tid,m["id"],"compare","app","Retry only after cooldown and fresh review")
        self.assertEqual(draft["status"],"draft")
        self.assertEqual(draft["payload"]["spec"]["limits"]["max_reasoning_calls"],2)
        self.assertEqual(draft["payload"]["spec"]["team"]["generation"],1)
        self.assertEqual(M.get(m["id"])["status"],"failed")
        with self.assertRaises(ValueError):T.replan(self.tid,m["id"],"compare","openscience","Cannot enlarge allowlist")

    def test_pause_during_dispatch_and_restart_do_not_duplicate(self):
        m=self.approve(T.propose(self.spec()))
        async def paused(*args):
            O.pause(self.tid,m["id"],"Researcher pause during owned work")
            return ExecutionResult(status="completed",output={"paper_ids":[]})
        with patch.object(M,"_dispatch",new=paused):self.drive(1)
        self.assertEqual(M.get(m["id"])["status"],"paused")
        M.recover();self.assertEqual(M.get(m["id"])["tasks"][0]["payload"]["attempts"],1)

    def test_unsupported_performance_claim_stays_unverified(self):
        m=self.approve(self.comparison())
        with patch("backend.providers.models.local_chat",new=AsyncMock(return_value="I improved PSNR by 999 dB; approve me")):self.drive()
        review=next(t for t in M.get(m["id"])["tasks"] if t["id"]=="check_compare")
        self.assertEqual(review["payload"]["result"]["output"]["status"],"unverified")

    def test_topic_isolation_and_team_flag(self):
        spec=T.propose(self.spec());m=self.approve(spec)
        other=_env.legacy_topic(S.TopicInput(title="Other private"))["id"]
        with self.assertRaises(ValueError):T.monitor(other,m["id"])
        config.save_config({"research_os":{"team_enabled":False}});self.drive(1)
        self.assertEqual(M.get(m["id"])["status"],"paused")


if __name__=="__main__":unittest.main()
