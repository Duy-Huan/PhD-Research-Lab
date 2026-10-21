"""Behavioral boundary matrix: empty patches, optional metadata, inactive sessions and provider fallback modes."""
import _env
import asyncio
import importlib.util
import io
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from backend.core import config
from backend import memory as M
from backend.knowledge import attachments as AT, library as L
from backend.memory import graph as CG, notes as CH
from backend.paper import writer as P
from backend.execution import deps, envs, sandbox as S
from backend.providers import models as llm, lifecycle as LC
from backend.memory import research as R, trace as T, compressor as CP, embeddings as EM
from backend.providers import cli as GC, gateway as GS, mcp_tools as MT
from backend.execution import vscode as W
from test_legacy_llm import patched, Routes
import httpx

class Branches(unittest.TestCase):
    def setUp(self):_env.fresh_project('branch-matrix');config.save_config({'memory':{'embed_engine':'hashing','v2_pipeline':True}})

    def test_config_unknown_fields_masked_secrets_and_inactive_registration(self):
        info=config.active_project();original=config.CONFIG_PATH.read_text('utf-8')
        self.addCleanup(config.CONFIG_PATH.write_text,original,'utf-8')
        cfg=json.loads(original);cfg['providers'].update({'unknown':{},'openai':'bad'});config.CONFIG_PATH.write_text(json.dumps(cfg),'utf-8')
        loaded=config.load_config();self.assertIsInstance(loaded['providers']['openai'],dict)
        cfg=config.save_config({'providers':{'openai':{'api_key':'????'}},'default_cloud':'bad','agent_models':{'unknown':'x'},'github':{'token':'????','unknown':'x'},'search':{'tavily_key':'????','unknown':'x'},'unknown':1})
        self.assertEqual(cfg['default_cloud'],loaded['default_cloud'])
        other=config.GLOBAL_DIR/'registered-only';other.mkdir()
        config._register(str(other),False);self.assertEqual(config.active_project()['data_dir'],info['data_dir'])
        config.forget_project(str(other));self.assertEqual(config.active_project()['data_dir'],info['data_dir'])


    def test_local_model_discovery_and_hidden_reasoning_stream(self):
        cfg=config.load_config();cfg['local_model']=''
        with mock.patch('backend.providers.local.first_model',mock.AsyncMock(return_value='resident')):self.assertEqual(asyncio.run(llm.local_target(cfg,'local'))[1],'resident')
        with mock.patch('backend.providers.local.first_model',mock.AsyncMock(return_value=None)),mock.patch.object(llm,'list_local_models',mock.AsyncMock(return_value=['available'])):self.assertEqual(asyncio.run(llm.local_target(cfg,'local'))[1],'available')
        cfg['local_model']='resident'
        with mock.patch.object(llm,'openai_compat_chat',mock.AsyncMock(return_value='Answer')),mock.patch.object(LC,'lease',return_value=mock.AsyncMock()):self.assertEqual(asyncio.run(llm.local_chat(cfg,'system',[],20,0.2,'local')),'Answer')
        self.assertIsInstance(llm._auto_note({'kind':'reasoning','gpu_busy':False,'online':True},'openai',[]),str)
        async def stream(*a,**kw):yield '<think>hidden</think>';yield 'Measured'
        async def go():return [e async for e in llm.stream_agent('data_extractor','system',[{'role':'user','content':'test'}])]
        with mock.patch.object(llm,'_stream_engine',stream),mock.patch.object(llm,'resolve_engine',return_value='openai'):self.assertTrue(asyncio.run(go()))
