"""Stateful memory regression: preserve raw evidence, manual decisions, and graph mutations."""
import _env
import asyncio
import json
import unittest
from unittest import mock
import httpx
from backend import memory as M
from backend.memory import graph as CG
from backend.core import config
from backend.execution import sandbox as SB
from backend.providers import models as llm
from backend.memory import research as RM, embeddings as EM, cache

class MemoryRegression(unittest.TestCase):
    def setUp(self):
        _env.fresh_project('memory-regression')
        config.save_config({'memory':{'v2_pipeline':False,'keep_recent_turns':1,'embed_engine':'hashing'}})
        M._running['busy']=False
        self.enterContext(mock.patch.object(llm,'call_agent',mock.AsyncMock(return_value={'text':'TITLE: Measured summary\nKeep baseline evidence.','engine':'fake'})))

    def go(self,coro):return asyncio.run(coro)



    def test_embedding_cache_and_remote_failure_contracts(self):
        cfg=config.load_config();cfg['memory'].update(embed_engine='ollama',embed_model='embed-test')
        EM._probe.update(t=0,ok=False,model='')
        response=httpx.Response(200,json={'models':[{'name':'embed-test:latest'}]},request=httpx.Request('GET','http://localhost'))
        with mock.patch.object(EM.httpx,'get',return_value=response):
            self.assertTrue(EM.ollama_available(cfg));self.assertTrue(EM.ollama_available(cfg))
        EM._probe['t']=0
        with mock.patch.object(EM.httpx,'get',side_effect=RuntimeError('offline')):self.assertFalse(EM.ollama_available(cfg))
        cfg['memory']['embed_model']='';self.assertFalse(EM.ollama_available(cfg));cfg['memory']['embed_model']='embed-test'
        emb=EM.Embedder(cfg);self.assertIn('ollama',emb.label)
        with mock.patch.object(EM,'_ollama_embed',return_value=[[3.,4.],[0.,1.]]):
            self.assertEqual(emb.embed(['one','two']),[[3.,4.],[0.,1.]])
            self.assertEqual(emb.embed(['one','two']),[[3.,4.],[0.,1.]])
            vectors=emb.embed_unit(['one','two']);self.assertAlmostEqual(vectors[0][0],0.6,places=5)
            self.assertEqual(len(emb.embed_unit(['one','two'])),2)
        with mock.patch.object(EM,'_ollama_embed',return_value=[[1.]]),mock.patch.object(EM,'MAX_CACHE',1):emb.embed(['three']);self.assertEqual(len(EM._cache.load()['vectors']),1)
        with mock.patch.object(EM,'_ollama_embed',return_value=[[1.]]):self.assertEqual(emb.embed(['four'],cache=False),[[1.]])
        with mock.patch('backend.execution.resources.gpu_busy',return_value=True),mock.patch('backend.providers.lifecycle.lease_sync'),mock.patch.object(EM.httpx,'post',return_value=httpx.Response(200,json={'embeddings':[[1.]]},request=httpx.Request('POST','http://localhost'))) as post:
            self.assertEqual(EM._ollama_embed(cfg,['x'],1),[[1.]])
            self.assertEqual(post.call_args.kwargs['json']['options'],{'num_gpu':0})
        with mock.patch('backend.execution.resources.gpu_busy',side_effect=RuntimeError('offline')),mock.patch('backend.providers.lifecycle.lease_sync'),mock.patch.object(EM.httpx,'post',return_value=httpx.Response(200,json={'embeddings':[]},request=httpx.Request('POST','http://localhost'))):
            with self.assertRaises(ValueError):EM._ollama_embed(cfg,['x'],1)
