"""Small but user-visible failure contracts around imports, saved state and output packaging."""
import _env
import asyncio
import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest import mock
import httpx
from backend.core import config
from backend.knowledge import attachments as AT, library as L
from backend.memory import notes as CH
from backend.paper import results as RS
from backend.paper import writer as P, review as RX, latex as LB
from backend.execution import files as ide_fs
from backend.providers import models as llm, local as LA, lifecycle as LC
from test_legacy_llm import Routes, patched
from pdfgen import make_pdf

class SmallFaults(unittest.TestCase):
    def setUp(self):
        _env.fresh_project('small-faults');LC.reset()
        info=config.active_project()
        self.enterContext(mock.patch.object(config,'active_project',return_value=info))
    def tearDown(self):LC.reset()


    def test_openai_payload_and_http_failure_contract(self):
        cfg=config.load_config();cfg['providers']['openai']['api_key']='fake'
        seen=[]
        def response(request):
            seen.append(json.loads(request.content));return httpx.Response(200,json={'choices':[{'message':{'content':'Measured answer'}}]})
        rt=Routes().add('POST','/chat/completions',response)
        with patched(rt):self.assertEqual(asyncio.run(llm.cloud_chat(cfg,'openai','system',[{'role':'user','content':'test'}],100)),'Measured answer')
        self.assertIn('max_completion_tokens',seen[0]);self.assertNotIn('temperature',seen[0])
        rt=Routes().add('POST','/chat/completions',httpx.Response(400,json={'error':{'message':'bad request'}}))
        with patched(rt):
            with self.assertRaises(llm.LLMError):asyncio.run(llm.openai_compat_chat('http://localhost/v1','fake','model','system',[],100,0.2,'Test','openai'))
        rt=Routes().add('POST','/chat/completions',httpx.Response(200,text='data: {"choices":[{"delta":{"content":"Measured"}}]}\n\ndata: [DONE]\n\n'))
        async def stream():return [e async for e in llm._stream_openai('http://localhost/v1','fake','model','system',[],100,0.2,'Test','openai')]
        with patched(rt):self.assertTrue(asyncio.run(stream()))


    def test_preserved_review_records(self):
        meta=RX.create_review('paper.md',b'# Measured study\n'+b'Measured accuracy is 0.9. '*30)
        RX.update_state(meta['id'],lambda state:state['issues'].append({'id':'ISS-1','title':'Missing detail','severity':'major','location':'methods','status':'open'}))
        self.assertIsInstance(RX.fixes_md(meta['id']),str)
        with mock.patch.object(RX,'get_active',return_value=meta['id']):RX.delete_review(meta['id'])
        self.assertEqual(RX.get_active(),'')

