"""Regression cases for low-frequency recovery paths and optional platform capabilities."""
import _env
import asyncio
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import httpx
from backend.core import config, telemetry
from backend.memory import graph as CG
from backend import memory as M
from backend.paper import results
from backend.knowledge import library
from backend.execution import sandbox as S, resources, sysinfo, deps, envs
from backend.memory import research as R, lod, compressor as CP, embeddings as EM, working
from backend.providers import context_packet as CT, events, mcp_tools as MT, gateway as GS, cli as GC
from backend.execution import vscode as W, tools as B

class Recovery(unittest.TestCase):
    def setUp(self):
        _env.fresh_project('recovery-regression');config.save_config({'memory':{'embed_engine':'hashing','v2_pipeline':True}})

    def test_overlay_failures_and_legacy_aliases(self):
        CG._overlay_path().write_text('[]','utf-8');self.assertEqual(CG.load_overlay()['nodes'],{})
        with mock.patch.object(Path,'read_text',side_effect=OSError('busy')):self.assertEqual(CG.load_overlay()['nodes'],{})
        M.set_tier3({'hypotheses':['Unmatched']})
        self.assertTrue(any(n.id=='hyp:0' for n in lod.collect()))
        with mock.patch('backend.memory.notes.load_notes',side_effect=OSError('busy')):self.assertTrue(lod.collect())


    def test_compressor_watermark_cutoff_and_dense_cache_hit(self):
        cfg=config.load_config();cfg['memory'].update(high_watermark_tokens=1,low_watermark_tokens=99,min_keep_messages=0)
        sessions=[{'id':'s1','messages':[{'content':'x'*8}]*4},{'id':'s2','messages':[{'content':'more'}]}]
        with mock.patch.object(CP,'tier1',return_value={'tokens':100}),mock.patch.object(CP,'_sessions',return_value=sessions):
            plan=CP.plan(cfg);self.assertEqual(plan['tokens'],2)
        emb=EM.Embedder(cfg);emb.engine='ollama';emb.model='cached'
        with mock.patch.object(EM,'_ollama_embed',return_value=[[1.0]]):self.assertEqual(emb.embed(['cached text']),[[1.0]])
        # A second read is served from disk without another model request.
        with mock.patch.object(EM,'_ollama_embed',side_effect=AssertionError('must not call')):self.assertEqual(emb.embed(['cached text']),[[1.0]])
        self.assertEqual(CT._blocked_ids(()),set())

    def test_mcp_candidate_tools_numeric_bounds_and_missing_hits(self):
        for schema,value in [({'type':'number','maximum':1},2),({'type':'integer','minimum':1},0)]:
            with self.assertRaises(MT.ToolInputError):MT.validate(schema,value)
        with mock.patch('backend.memory.engine.index',return_value=(SimpleNamespace(by_id={}),False)):self.assertEqual(MT._hits({'hits':[{'id':'missing'}]},set()),[])
        self.assertTrue(MT._research_record_observation({'text':'Observed baseline'},set(),{'name':'test'})[0]['candidate'])
        self.assertTrue(MT._research_record_decision({'text':'Keep measured baseline','kind':'direction'},set(),{})[0]['candidate'])
        exp=R.add_experiment({'title':'Baseline'})
        self.assertTrue(MT._research_record_experiment_result({'experiment_id':exp['id'],'text':'Measured result'},set(),{})[0]['candidate'])
        self.assertEqual(telemetry._clean({'provider':'codex'}),{'provider':'codex'})
        self.assertEqual(events.agy({'event':'step_update','step_update':{'step_type':'tool','tool_name':'read'}})[0]['type'],'tool_call')
        self.assertEqual(events.gemini({'type':'message','text':'delta'})[0]['text'],'delta')



