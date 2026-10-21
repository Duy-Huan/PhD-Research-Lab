"""Scientific integrity: invalid records fail closed, evidence provenance survives approval and editing."""
import _env
import json
import unittest
from unittest import mock
from types import SimpleNamespace
from backend.core import config
from backend import memory as M
from backend.execution import sandbox as SB
from backend.knowledge import library
from backend.memory import research as R, evidence as E, lifecycle as L, trace as T, working as W, knowledge as K

class Integrity(unittest.TestCase):
    def setUp(self):_env.fresh_project('integrity-regression')



    def test_candidate_validation_classification_and_all_commit_types(self):
        for kind,payload in [('bad',{'text':'x'}),('decision',{}),('decision',{'text':'x','hypothesis_id':'bad'}),('decision',{'text':'x','evidence_ids':'bad'}),('observation',{'text':'x','metric':'bad'}),('observation',{'text':'x','metric':{'name':'loss'}}),('observation',{'text':'x','stance':'bad'}),('experiment_result',{'text':'x','verdict':'bad'})]:
            with self.subTest(kind=kind,payload=payload),self.assertRaises(L.LifecycleError):L.propose(kind,payload)
        exp=R.add_experiment({'title':'Measured'})
        for kind in L.KINDS:
            payload={'text':'Distinct '+kind+' result'}
            if kind=='experiment_result':payload.update(experiment_id=exp['id'],metric={'name':'accuracy','value':0.9},verdict='supports')
            c=L.propose(kind,payload,'provider','fake')
            self.assertEqual(c['status'],'pending')
            approved=L.approve(c['id'],{'text':payload['text']+' reviewed'})
            self.assertEqual(approved['status'],'approved')
            with self.assertRaises(L.LifecycleError):L.approve(c['id'])
            with self.assertRaises(L.LifecycleError):L.reject(c['id'])
        for ident in ('bad','CAND-999'):
            with self.assertRaises(L.LifecycleError):L.get(ident)
        for kind,origin,payload in [('decision','human',{}),('experiment_result','provider',{}),('observation','human',{}),('claim','human',{}),('claim','provider',{}),('note','human',{})]:
            self.assertTrue(L.classify(kind,origin,payload))
        self.assertEqual(L.propose('claim',{'text':'Distinct claim result reviewed'})['status'],'duplicate')
        self.assertTrue(L.list_candidates('approved'))

    def test_trace_graph_with_artifacts_unknown_sources_and_supersession(self):
        h=R.add_hypothesis('Hypothesis')
        folder=SB.runs_dir()/'run-valid';folder.mkdir()
        (folder/'run.json').write_text(json.dumps({'id':'run-valid','status':'done','git':{'sha':'abc'},'metrics':{'loss':0.2},'environment':{'python':'3.14'}}),'utf-8')
        (folder/'provenance.json').write_text(json.dumps({'files':{'curve.png':'deadbeef'}}),'utf-8')
        exp=R.add_experiment({'run_id':'run-valid','hypothesis_id':h['id']})
        c=E.add_claim('Measured claim',h['id'],['lit:unknown'])
        e=E.add_evidence({'claim_id':c['id'],'experiment_id':exp['id'],'paper_key':'paper2026','metric':{'name':'loss','value':0.2}})
        d=M.add_decision('Keep baseline',evidence_ids=[e['id']]);M.add_decision('Updated baseline',supersedes=d['id'],evidence_ids=[exp['id']])
        failure=R.add_failure('OOM',h['id'],'run-valid',experiment_id=exp['id'])
        with mock.patch.object(K,'papers',return_value=[{'key':'paper2026','title':'Reference'},{'key':''}]):
            chain=T.chain(c['id'])
            self.assertEqual(chain['answers']['commits'],['abc']);self.assertTrue(chain['answers']['artifacts'])
            self.assertTrue(T.chain(failure['id'])['edges']);self.assertTrue(T.chain(d['id'])['edges'])
        self.assertTrue(T.decisions_based_on(exp['id']))
        self.assertEqual(T._run_info('bad'),{})
        self.assertTrue(T._run_info('missing-run')['missing'])
        (folder/'provenance.json').write_text('{broken','utf-8');self.assertEqual(T._run_info('run-valid')['artifacts'],[])
        with self.assertRaises(KeyError):T.chain('missing')
        self.assertTrue(T.chain('run:missing-run')['nodes'])
        self.assertEqual(T.chain(c['id'],-1)['nodes'],[])

