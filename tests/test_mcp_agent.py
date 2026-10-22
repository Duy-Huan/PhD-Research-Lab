"""Offline MCP inference contract and credential/model binding regressions."""
import _env  # noqa: F401
import asyncio
import json
import threading
import time
import unittest
from copy import deepcopy
from unittest.mock import patch

import httpx

from backend.core import config as C
from backend.providers import mcp_agent as M, models as L


class Chunked(httpx.AsyncByteStream):
    def __init__(self, raw):
        self.raw = raw

    async def __aiter__(self):
        for byte in self.raw:
            yield bytes([byte])


class MCPAgent(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        self.cfg = deepcopy(C.DEFAULTS)
        self.cfg['mcp_agent'].update(enabled=True, token='private-mcp-token', tool='infer', models=['own-model'])
        self.calls = []
        self.mode = ''

    def handler(self, request):
        body = json.loads(request.content)
        self.calls.append((request, body))
        method, rid = body['method'], body.get('id')
        if method == 'notifications/initialized':
            return httpx.Response(202)
        if method == 'initialize':
            result = {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}}}
        elif method == 'tools/list':
            result = {'tools': [{'name': 'infer', 'inputSchema': {'type': 'object', 'properties': {
                'system': {'type': 'string'}, 'messages': {'type': 'array'}, 'model': {'type': 'string'},
                'max_tokens': {'type': 'integer'}, 'temperature': {'type': 'number'}}, 'required': ['messages']}}]}
            if self.mode == 'general-tool':
                result['tools'][0]['inputSchema']['properties'] = {'path': {'type': 'string'}}
            elif self.mode == 'unsupported-required':
                result['tools'][0]['inputSchema']['required'] = ['unknown']
            elif self.mode == 'no-model':
                del result['tools'][0]['inputSchema']['properties']['model']
            elif self.mode == 'paginated' and not body['params'].get('cursor'):
                result = {'tools': [], 'nextCursor': 'page-two'}
        else:
            result = {'content': [{'type': 'text', 'text': 'Kết quả local'}, {'type': 'image', 'data': 'ignored'}]}
            if self.mode == 'tool-error':
                result['isError'] = True
            elif self.mode == 'no-text':
                result['content'] = []
        response = {'jsonrpc': '2.0', 'id': rid, 'result': result}
        if self.mode == 'wrong-id':
            response['id'] = 999
        elif self.mode == 'rpc-error':
            response = {'id': rid, 'error': {'message': 'secret response must not leak'}}
        elif self.mode == 'bad-version' and method == 'initialize':
            result['protocolVersion'] = 'unknown'
        if self.mode == 'redirect':
            return httpx.Response(307, headers={'location': 'https://other-host.test'})
        if self.mode == 'oversize':
            return httpx.Response(200, content=b' ' * (M.LIMIT + 1))
        if self.mode == 'invalid-json':
            return httpx.Response(200, content=b'not-json private-token')
        headers = {'Mcp-Session-Id': 'session-one'} if method == 'initialize' else {}
        if self.mode == 'sse':
            headers['Content-Type'] = 'text/event-stream'
            raw = ('event: message\ndata: ' + json.dumps(response, ensure_ascii=False) + '\n\n').encode()
            return httpx.Response(200, headers=headers, stream=Chunked(raw))
        return httpx.Response(200, headers=headers, json=response)

    async def complete(self, model='own-model'):
        factory = httpx.AsyncClient
        def client(**kwargs):
            self.assertFalse(kwargs['follow_redirects'])
            self.assertFalse(kwargs['trust_env'])
            return factory(**kwargs, transport=httpx.MockTransport(self.handler))
        with patch.object(M.httpx, 'AsyncClient', side_effect=client):
            return await M.complete(self.cfg, 'Research system', [{'role': 'user', 'content': 'Explain evidence'}], model, 256, 0.2)

    def test_json_session_scoped_token_and_exact_model(self):
        self.assertEqual(asyncio.run(self.complete()), 'Kết quả local')
        self.assertEqual([body['method'] for _, body in self.calls], ['initialize', 'notifications/initialized', 'tools/list', 'tools/call'])
        request, body = self.calls[-1]
        self.assertEqual(request.headers['Authorization'], 'Bearer private-mcp-token')
        self.assertEqual(request.headers['Mcp-Session-Id'], 'session-one')
        self.assertEqual(body['params']['name'], 'infer')
        self.assertEqual(body['params']['arguments']['model'], 'own-model')
        self.assertNotIn('providers', body['params']['arguments'])

    def test_sse_split_unicode_and_paginated_catalog(self):
        for mode in ('sse', 'paginated', 'no-model'):
            self.mode = mode
            self.assertEqual(asyncio.run(self.complete(None if mode == 'no-model' else 'own-model')), 'Kết quả local')

    def test_refuses_general_tools_errors_redirects_and_oversize_without_secret_leaks(self):
        for mode in ('general-tool', 'unsupported-required', 'no-model', 'tool-error', 'no-text', 'wrong-id',
                     'rpc-error', 'bad-version', 'redirect', 'oversize', 'invalid-json'):
            with self.subTest(mode=mode):
                self.mode = mode
                self.calls.clear()
                with self.assertRaises(L.LLMError) as raised:
                    asyncio.run(self.complete())
                self.assertNotIn('private-token', str(raised.exception))
                self.assertNotIn('secret response', str(raised.exception))
                if mode in ('general-tool', 'unsupported-required', 'no-model'):
                    self.assertNotIn('tools/call', [b['method'] for _, b in self.calls])

    def test_endpoint_policy_disabled_and_cancellation(self):
        for url in ('http://remote.test/mcp', 'https://user:password@host/mcp', 'file:///tmp/mcp', 'https://host/mcp?token=secret'):
            with self.assertRaises(ValueError):
                M.endpoint(url)
        self.assertEqual(M.endpoint('http://[::1]:9000/mcp'), 'http://[::1]:9000/mcp')
        self.cfg['mcp_agent']['enabled'] = False
        with self.assertRaisesRegex(L.LLMError, 'disabled'):
            asyncio.run(self.complete())
        async def cancel():
            with patch.object(M, '_complete', side_effect=asyncio.CancelledError):
                with self.assertRaises(asyncio.CancelledError):
                    await M.complete(self.cfg, '', [], '', 10, 0)
        asyncio.run(cancel())

    def test_model_binding_is_reset_atomically_and_tokens_are_masked(self):
        C.save_config({'agent_modes': {'research': 'openai'}, 'agent_models': {'research': 'gpt-saved'}})
        C.save_config({'agent_modes': {'research': 'ollama'}})
        self.assertNotIn('research', C.load_config()['agent_models'])
        cfg = C.save_config({'agent_models': {'research': 'qwen-local'}, 'agent_modes': {'research': 'local'}})
        self.assertEqual(cfg['agent_models']['research'], 'qwen-local')
        C.save_config({'agent_modes': {'research': 'mcp'}, 'mcp_agent': self.cfg['mcp_agent']})
        public = C.public_config(C.load_config())
        self.assertEqual(public['agent_modes']['research'], 'mcp')
        self.assertNotIn('private-mcp-token', json.dumps(public))
        self.assertTrue(public['mcp_agent']['has_token'])
        C.save_config({'mcp_agent': {'token': public['mcp_agent']['token']}})
        self.assertEqual(C.load_config()['mcp_agent']['token'], 'private-mcp-token')

    def test_invalid_mcp_configuration_is_rejected_without_writing_secrets(self):
        before = C.CONFIG_PATH.read_bytes()
        for patch_value in ({'url': 'http://remote.invalid/mcp'}, {'tool': 'bad tool'}, {'models': [{}]}):
            with self.subTest(patch=patch_value), self.assertRaises(ValueError):
                C.save_config({'mcp_agent': patch_value})
            self.assertEqual(C.CONFIG_PATH.read_bytes(), before)
        saved = json.loads(before)
        saved['mcp_agent'] = {'enabled': True, 'url': 'http://remote.invalid/mcp'}
        C.CONFIG_PATH.write_text(json.dumps(saved), encoding='utf-8')
        self.assertFalse(C.load_config()['mcp_agent']['enabled'])

    def test_default_cloud_change_preserves_explicit_anthropic_agent_model(self):
        C.save_config({'default_cloud': 'openai', 'providers': {'anthropic': {'api_key': 'test-only-key'}},
                       'agent_modes': {'research': 'cloud', 'reviewer': 'claude'},
                       'agent_models': {'research': 'openai-custom', 'reviewer': 'anthropic-custom'}})
        cfg = C.save_config({'default_cloud': 'gemini'})
        self.assertNotIn('research', cfg['agent_models'])
        self.assertEqual(cfg['agent_models']['reviewer'], 'anthropic-custom')

    def test_call_and_stream_agent_use_mcp_without_cloud_fallback(self):
        cfg = self.cfg
        cfg['agent_modes']['research'] = 'mcp'
        cfg['agent_models']['research'] = 'mcp-model'
        async def run():
            with patch.object(L, 'load_config', return_value=cfg), patch.object(M, 'complete', return_value='<think>hidden</think>Answer') as invoke:
                answer = await L.call_agent('research', 'system', user='question')
                self.assertEqual(answer['text'], 'Answer')
                self.assertEqual(answer['model'], 'mcp-model')
                chunks = [chunk async for chunk in L.stream_agent('research', 'system', [{'role': 'user', 'content': 'q'}])]
                self.assertEqual(chunks[0], ('delta', 'Answer'))
                self.assertEqual(chunks[-1][1]['engine'], 'mcp')
                self.assertEqual(invoke.call_count, 2)
            with patch.object(L, 'load_config', return_value=cfg), patch.object(M, 'complete', side_effect=L.LLMError('tool failed')), patch.object(L, 'cloud_chat') as cloud:
                with self.assertRaisesRegex(L.LLMError, 'tool failed'):
                    await L.call_agent('research', 'system', user='q')
                cloud.assert_not_called()
        asyncio.run(run())

    def test_chat_stop_and_time_budget_interrupt_buffered_inference(self):
        from backend.agent import orchestrator as O
        for cancelled in (True, False):
            with self.subTest(cancelled=cancelled):
                closed = threading.Event()
                async def blocked(*args, **kwargs):
                    try:
                        await asyncio.Future()  # tool may not emit incremental model output
                        yield ('delta', 'must not arrive')
                    finally:
                        closed.set()
                cfg = deepcopy(self.cfg)
                cfg['aiws']['max_turn_s'] = 1 if cancelled else 0.01
                with patch.object(C, 'load_config', return_value=cfg), patch.object(L, 'stream_agent', blocked), \
                     patch.object(O, '_history', return_value=[]), patch.object(O, '_cancelled', return_value=cancelled):
                    start = time.monotonic()
                    text, error, stopped = O._app('session', 'turn', {'binding': {'module': 'research'}},
                                                 {'question': 'q'}, {'provider': 'app:auto', 'reasoning': 'auto', 'model': ''})
                    self.assertLess(time.monotonic() - start, 1)
                    self.assertTrue(closed.is_set())
                    self.assertEqual(text, '')
                    self.assertEqual(stopped, cancelled)
                    self.assertEqual('aiws.max_turn_s' in error, not cancelled)
