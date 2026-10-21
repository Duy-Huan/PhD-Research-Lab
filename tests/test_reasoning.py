"""Reasoning level ("cấp độ tư duy"): what reaches each engine, what the registry advertises, and the chat setting."""
import _env  # noqa: F401  (must be first)
import asyncio
import contextlib
import json
import unittest
from unittest import mock

import httpx

from backend.agent import AIWSError, policy, sessions
from backend.core import config
from backend.providers import lifecycle as LC, models as M, registry

SSE_OPENAI = 'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'
SSE_ANTHROPIC = ('data: {"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"hmm"}}\n\n'
                 'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hi"}}\n\n')


class Capture:
    def __init__(self, body: str):
        self.body, self.requests = body, []

    def client(self, timeout=None):
        def handler(req):
            self.requests.append(json.loads(req.content))
            return httpx.Response(200, text=self.body)

        @contextlib.asynccontextmanager
        async def cm():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
                yield c
        return cm()


def run(gen_fn, level):
    async def go():
        M.REASONING.set(level)
        return [x async for x in gen_fn()]
    return asyncio.run(go())


class Engines(unittest.TestCase):
    def test_anthropic_thinking_budget(self):
        cap = Capture(SSE_ANTHROPIC)
        with mock.patch.object(LC, "http_client", cap.client):
            out = run(lambda: M._stream_anthropic("https://a", "k", "claude", "sys", [{"role": "user", "content": "q"}], 1000), "high")
            self.assertEqual(out, ["hi"])  # thinking is never shown as the answer
            run(lambda: M._stream_anthropic("https://a", "k", "claude", "sys", [{"role": "user", "content": "q"}], 1000), "auto")
        self.assertEqual(cap.requests[0]["thinking"], {"type": "enabled", "budget_tokens": 24000})
        self.assertGreater(cap.requests[0]["max_tokens"], 24000)
        self.assertNotIn("thinking", cap.requests[1])

    def test_openai_and_local_effort_and_qwen_no_think(self):
        cap = Capture(SSE_OPENAI)
        msgs = [{"role": "user", "content": "q"}]
        with mock.patch.object(LC, "http_client", cap.client):
            run(lambda: M._stream_openai("https://o", "k", "gpt-5", "s", msgs, 100, 0.2, "OpenAI", "openai"), "off")
            run(lambda: M._stream_openai("http://l", "", "qwen3-8b", "s", msgs, 100, 0.2, "LM", "local"), "off")
            run(lambda: M._stream_openai("https://d", "k", "deepseek-chat", "s", msgs, 100, 0.2, "DS", "deepseek"), "high")
            run(lambda: M._stream_openai("http://l", "", "llama", "s", msgs, 100, 0.2, "LM", "local"), "auto")
        self.assertEqual(cap.requests[0]["reasoning_effort"], "minimal")
        self.assertEqual(cap.requests[1]["reasoning_effort"], "minimal")
        self.assertTrue(cap.requests[1]["messages"][-1]["content"].endswith("/no_think"))
        self.assertNotIn("reasoning_effort", cap.requests[2])  # no control: nothing invented
        self.assertNotIn("reasoning_effort", cap.requests[3])
        self.assertEqual(cap.requests[3]["messages"][-1]["content"], "q")

    def test_ollama_think_flag(self):
        cap = Capture('{"message":{"content":"hi"},"done":true}\n')
        cfg = config.load_config()
        with mock.patch.object(LC, "http_client", cap.client), \
                mock.patch.object(M, "local_target", mock.AsyncMock(return_value=("http://o/v1", "qwen3", "Ollama", "h"))):
            run(lambda: M._stream_ollama_native(cfg, "s", [{"role": "user", "content": "q"}], 50, 0.2, None, {}), "medium")
            run(lambda: M._stream_ollama_native(cfg, "s", [{"role": "user", "content": "q"}], 50, 0.2, None, {}), "off")
            run(lambda: M._stream_ollama_native(cfg, "s", [{"role": "user", "content": "q"}], 50, 0.2, None, {}), "auto")
        self.assertEqual([r.get("think") for r in cap.requests], [True, False, None])

    def test_bad_values_mean_auto(self):
        async def go():
            M.REASONING.set("ultra")
            return M._reasoning()
        self.assertEqual(asyncio.run(go()), "auto")
        self.assertEqual(M._no_think([], "qwen"), [])


class Setting(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("reasoning")

    def test_registry_and_session_setting(self):
        caps = {p["id"]: p["capabilities"]["reasoning_controls"] for p in registry.registry()}
        self.assertEqual(caps["app:anthropic"], ["off", "low", "medium", "high"])
        self.assertEqual(caps["app:auto"], ["off", "low", "medium", "high"])
        self.assertEqual(caps["app:deepseek"], [])
        self.assertNotIn("web:chatgpt", caps)
        s = sessions.create("t", settings={"provider": "app:deepseek", "reasoning": "high"})
        notes = policy.check_provider(policy.effective(s))
        self.assertTrue(any(n["setting"] == "reasoning" for n in notes))
        with self.assertRaises(AIWSError):
            policy.clean_settings({"reasoning": "extreme"})


if __name__ == "__main__":
    unittest.main()
