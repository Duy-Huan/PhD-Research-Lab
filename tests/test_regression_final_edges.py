"""Final fault and boundary regressions for provider processes, memory reduction and sandbox preflight."""
import _env
import asyncio
import builtins
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import httpx
from backend.core import config
from backend.execution import sandbox as S, resources, deps, gitops, files as ide_fs
from backend import memory as M
from backend.paper import results as RS
from backend.knowledge import websearch as WS
from backend.memory import notes as CH
from backend.providers import mcp_server
from backend.memory import compressor as CP, lod, research as R, trace, state, evidence as E
from backend.providers import cli as C, gateway as G, context_packet as CT
from backend.execution import tracker as EX, tools as B
from test_legacy_llm import patched, Routes
from providers.fakes import fake

class FinalEdges(unittest.TestCase):
    def setUp(self):_env.fresh_project('final-regression');config.save_config({'memory':{'embed_engine':'hashing','v2_pipeline':True}})

    def test_sandbox_preflight_errors_never_spawn_orphan_process(self):
        S.save_settings({'mode':'local','gpu':True,'auto_deps':True,'python_mode':'direct','python_base':sys.executable,'torch_index':'https://example.test/wheels'})
        for dirty in (True,False):
            with mock.patch.object(resources,'vram_gate'),mock.patch.object(resources,'prepare_gpu_run',side_effect=RuntimeError('offline')),mock.patch.object(deps,'plan_cached',side_effect=RuntimeError('invalid requirements')),mock.patch.object(gitops,'head_info',return_value={'dirty':True},side_effect=None if dirty else RuntimeError('git failed')),mock.patch.object(EX,'run_env',side_effect=RuntimeError('offline')),mock.patch.object(S,'_local_cmd',return_value=('fake',{})),mock.patch.object(S,'_local_python',return_value=sys.executable),mock.patch.object(S,'IS_WIN',False),mock.patch.object(S.subprocess,'Popen',side_effect=OSError('missing')):
                with self.assertRaises(S.SandboxError):S.start_job('fake')
        job=S.Job('run','fake','failure');job.run_dir=S.runs_dir()/job.id;job.run_dir.mkdir();job.status='failed';job.meta={'environment':{'gpu':True}}
        with mock.patch('builtins.open',side_effect=OSError('busy')):job.add('out','measured')
        with mock.patch('backend.knowledge.provenance.seal_run'):S._after_run(job)
        cfg=S.load_settings();cfg.update(gpu=True,image='img:gpu',memory_gb=0,cpus=0,shm_gb=0)
        with mock.patch.object(S,'_capped_settings',return_value=(cfg,[])),mock.patch.object(S,'container_state',return_value={'exists':False,'name':'fake'}),mock.patch.object(S,'image_present',return_value=True),mock.patch.object(S,'docker',side_effect=[(1,'GPU failed'),(0,''),(1,'second failure')]):
            with self.assertRaises(S.SandboxError):S.ensure_container()



    def test_web_source_metadata_is_merged_without_losing_richer_record(self):
        route=Routes().add('GET','/works',httpx.Response(200,json={'results':[]}))
        route.add('POST','/html/',httpx.Response(200,text='<a class="result__a" href="https://example.test/1">One</a><a class="result__a" href="https://example.test/2">Two</a>'))
        with patched(route):
            self.assertEqual(asyncio.run(WS.openalex('test',1,mailto='test@example.test')),[])
            self.assertEqual(len(asyncio.run(WS.duckduckgo('test',1))),1)
        out=WS._interleave([[{'title':'same'}],[{'title':'same','pdf_url':'https://example.test/p.pdf','abstract':'Evidence'}]])
        self.assertEqual(out[0]['pdf_url'],'https://example.test/p.pdf')

    def test_mcp_retention_unknown_tool_and_telemetry_fault(self):
        with mock.patch.dict(mcp_server.SESSIONS,{str(i):{} for i in range(501)},clear=True):
            self.assertIn('result',mcp_server.handle({'id':1,'method':'initialize'}));self.assertEqual(len(mcp_server.SESSIONS),500)
        with self.assertRaises(ValueError):mcp_server.call_tool('unknown',{})
        with mock.patch('backend.core.telemetry.record',side_effect=OSError('disk')):
            self.assertIn('result',mcp_server.handle({'id':1,'method':'tools/call','params':{'name':'sandbox_get_metrics'}}))

    def test_legacy_summarize_dispatches_to_current_pipeline(self):
        cfg=config.load_config();cfg['memory']['v2_pipeline']=True
        with mock.patch.object(M,'load_config',return_value=cfg),mock.patch.object(CP,'compress',mock.AsyncMock(return_value={'pipeline':'v2'})) as compress:
            self.assertEqual(asyncio.run(M.summarize())['pipeline'],'v2');compress.assert_awaited_once_with(force=False)
        for needle in ('',' '*10,'non matching phrase'):
            from backend.paper.review import find_span
            self.assertIsNone(find_span('Measured result',needle))

