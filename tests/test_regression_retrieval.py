"""Retrieval invariants across lexical fallback, remote rerank failure, filtering and context budgets."""
import _env
import asyncio
import json
import unittest
from unittest import mock
import httpx
from backend.core import config
from backend import memory as M
from backend.memory import graph as CG
from backend.providers import models as llm
from backend.memory import engine as E, retrieval as R, embeddings as EM, lod as L, compiler as C, compressor as CP, cache, knowledge as K, evidence as EV

class Retrieval(unittest.TestCase):
    def setUp(self):
        _env.fresh_project('retrieval-regression');config.save_config({'memory':{'embed_engine':'hashing','v2_pipeline':True}});cache.clear_all()
        self.cfg=config.load_config()
        self.nodes=[L.MemoryNode('HYPE-001','research','hypothesis','baseline','Baseline evidence',status='rejected',ts='2020-01-01',meta={'dataset':'ImageNet','model':'CNN','source_type':'experiment','origin':'ai'}),L.MemoryNode('lit:reference','knowledge','paper','reference','Baseline reference',links=['HYPE-001'],ts='2026-01-01')]




    def test_compressor_watermarks_and_worker_shutdown(self):
        self.assertFalse(CP.parse_memo('{"summary":""}','fallback')['structured'])
        self.assertEqual(CP.memo_markdown({'structured':False,'summary':'summary'}),'summary')
        memo=CP.parse_memo('{"summary":"result","hypotheses":[{"ref":"H1","text":"baseline","status":"testing"}]}','fallback')
        self.assertIn('Hypotheses',CP.memo_markdown(memo))
        CP._running['busy']=True
        try:self.assertIn('already running',asyncio.run(CP.compress())['skipped'])
        finally:CP._running['busy']=False
        self.assertIn('watermark',asyncio.run(CP.compress())['skipped'])
        async def go():
            stop=asyncio.Event()
            async def wait_for(*a,**k):
                a[0].close();stop.set();raise asyncio.TimeoutError()
            with mock.patch.object(M.asyncio,'sleep',mock.AsyncMock()),mock.patch.object(M.asyncio,'wait_for',wait_for),mock.patch.object(M,'tier1',return_value={'tokens':100000}),mock.patch.object(M,'summarize',mock.AsyncMock()) as summarize:
                await M.worker(stop);summarize.assert_awaited_once()
        asyncio.run(go())
