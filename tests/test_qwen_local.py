import _env
import asyncio
import unittest
from contextlib import asynccontextmanager
from unittest.mock import patch
import httpx
from backend.providers import models as M


class QwenLocalTests(unittest.TestCase):
    def invoke(self, response, requests):
        def handler(request):
            import json
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=response)

        @asynccontextmanager
        async def client(_):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
                yield c

        async def call():
            token = M.REASONING.set('off')
            try:
                with patch.object(M.LC, 'http_client', client):
                    return await M.openai_compat_chat('http://localhost:1234/v1', '', 'qwen/qwen3.5-9b', 'Bounded assistance', [{'role': 'user', 'content': 'Ready?'}], 64, 0, 'LM Studio', 'local')
            finally:
                M.REASONING.reset(token)
        return asyncio.run(call())

    def test_nonstream_local_qwen35_uses_hard_thinking_switch(self):
        requests = []
        self.assertEqual(self.invoke({'choices': [{'message': {'content': 'READY'}, 'finish_reason': 'stop'}]}, requests), 'READY')
        self.assertEqual(requests[0]['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(requests[0]['reasoning_effort'], 'none')

    def test_reasoning_only_truncation_is_not_a_successful_answer(self):
        with self.assertRaisesRegex(M.LLMError, 'no answer content'):
            self.invoke({'choices': [{'message': {'content': '', 'reasoning_content': 'private'}, 'finish_reason': 'length'}]}, [])
