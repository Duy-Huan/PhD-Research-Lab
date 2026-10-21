import _env
import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.core import config
from backend.knowledge import research_store as S
from backend.agent import missions as M
from backend.execution import protocols as P
from backend.execution.protocol_contracts import ExperimentProtocol


class Protocols(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self);_env.fresh_project("protocol tests",code_project=None)
        self.tid=S.save_topic(S.TopicInput(title="Denoising acceptance"))["id"]

    def protocol(self,**patches):
        p=P.create(ExperimentProtocol.model_validate({"topic_id":self.tid,"hypothesis":"Fixed smoothing improves a generated noisy image",**patches}))
        return P.approve(self.tid,p["id"],p["digest"],"Reviewed generated fixture rights, split separation, baseline and CPU limits")

    def execute(self,p):
        m=P.mission_draft(self.tid,p["id"]);M.approve(self.tid,m["id"],m["payload"]["plan_digest"],"Approve bounded offline CPU computation")
        for _ in range(4):asyncio.run(M.tick())
        return M.get(m["id"]),P.runs(self.tid)[0]

    def test_measured_multi_seed_protocol_reproduction(self):
        p=self.protocol();m,r=self.execute(p)
        self.assertEqual(m["status"],"completed");self.assertEqual(r["status"],"completed")
        self.assertEqual(r["payload"]["comparison"]["repeat_count"],3)
        self.assertEqual(r["payload"]["comparison"]["recommendation"],"candidate_improvement")
        self.assertFalse(r["payload"]["comparison"]["held_out_used_for_selection"])
        self.assertTrue(all(t["payload"]["artifact"]["sha256"] for t in r["trials"]))
        first=r["payload"]["comparison"]
        p=P.approve(self.tid,p["id"],p["digest"],"Independent clean worker reproduction of the same immutable protocol")
        _,reproduced=self.execute(p)
        self.assertEqual(first,reproduced["payload"]["comparison"])
        self.assertNotEqual(r["id"],reproduced["id"])

    def test_single_seed_cannot_recommend_improvement(self):
        _,r=self.execute(self.protocol(seeds=[11]))
        self.assertEqual(r["payload"]["comparison"]["recommendation"],"no_supported_improvement")
        self.assertIsNone(r["payload"]["comparison"]["normal_approx_ci95"])

    def test_protocol_drift_and_reuse_approval_blocked(self):
        p=self.protocol();m,r=self.execute(p)
        second=P.mission_draft(self.tid,p["id"]);M.approve(self.tid,second["id"],second["payload"]["plan_digest"],"Attempt duplicated approval")
        asyncio.run(M.tick());self.assertEqual(M.get(second["id"])["status"],"failed")
        self.assertEqual(len(P.runs(self.tid)),1)
        newer=P.create(ExperimentProtocol.model_validate({**p["payload"]["spec"],"alphas":[0.75]}),p["id"])
        self.assertEqual(newer["revision"],2);self.assertIsNone(newer["approval"])
        self.assertEqual(P.get(self.tid,p["id"])["digest"],p["digest"])

    def test_gpu_split_and_budget_mutations_rejected(self):
        for patch_value in ({"gpu":True},{"selection_split":"test"},{"seeds":[1,1]},{"max_trials":4},{"alphas":[-1]},{"engine":"docker","docker_image":"python:latest"}):
            with self.assertRaises(ValueError):self.protocol(**patch_value)

    def test_worker_revision_and_topic_boundaries(self):
        p=self.protocol()
        other=S.save_topic(S.TopicInput(title="Other"))["id"]
        with self.assertRaises(ValueError):P.get(other,p["id"])
        m=P.mission_draft(self.tid,p["id"]);M.approve(self.tid,m["id"],m["payload"]["plan_digest"],"Reviewed")
        with patch.object(P,"worker_hash",return_value="0"*64):asyncio.run(M.tick())
        self.assertEqual(M.get(m["id"])["status"],"failed")
        self.assertEqual(P.runs(self.tid),[])

    def test_restart_retains_negative_and_interrupted_runs(self):
        p=self.protocol();_,r=self.execute(p)
        with S.db() as c:c.execute("UPDATE experiment_runs SET status='running' WHERE id=?",(r["id"],))
        P.recover();updated=P.run(self.tid,r["id"])
        self.assertEqual(updated["status"],"interrupted")
        self.assertEqual(len(updated["trials"]),len(r["trials"]))


if __name__=="__main__":unittest.main()
