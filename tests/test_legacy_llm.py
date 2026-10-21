"""Legacy LLM layer (coverage pass): provider calls, streaming, fallbacks, auto routing, LM Studio / Ollama control.
All HTTP goes through httpx.MockTransport routes; nothing leaves the machine."""
import _env  # noqa: F401  (must be first)
import asyncio
import json
import subprocess
import unittest
from unittest import mock

import httpx

from backend.core import config
from backend.providers import models as llm, router as RT, local as LA, lifecycle as LC


class Routes:
    """route(method, path-suffix) → response or callable(request) → response."""

    def __init__(self):
        self.routes, self.seen = [], []

    def add(self, method, suffix, resp):
        self.routes.append((method, suffix, resp))
        return self

    def __call__(self, req):
        self.seen.append((req.method, str(req.url)))
        for i, (m, suf, resp) in enumerate(self.routes):
            if m == req.method and req.url.path.endswith(suf):
                if isinstance(resp, list):  # a queue of answers for repeated calls
                    r = resp.pop(0) if len(resp) > 1 else resp[0]
                else:
                    r = resp
                return r(req) if callable(r) else r
        return httpx.Response(404, json={"error": {"message": "no route"}})


def patched(routes):
    real = httpx.AsyncClient

    def factory(*a, **k):
        k.pop("limits", None)
        return real(transport=httpx.MockTransport(routes), timeout=k.get("timeout"))
    return mock.patch("httpx.AsyncClient", factory)


def run(c):
    return asyncio.run(c)


MSG = [{"role": "user", "content": "q"}]


class Helpers(unittest.TestCase):

    def test_gateway_headers(self):
        config.save_config({"routing": {"provider_headers": {"ninerouter": {"X-Skill": "a", "Authorization": "x", "X-Bad": "a\nb"}}}})
        self.assertEqual(llm.gateway_headers("ninerouter"), {"X-Skill": "a"})
        with mock.patch.object(llm, "load_config", side_effect=RuntimeError):
            self.assertEqual(llm.gateway_headers("x"), {})


class Cloud(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-llm")
        LC.reset()
        config.save_config({"providers": {"anthropic": {"api_key": "sk-ant", "model": "claude-x"}, "openai": {"api_key": "sk-oa"},
                                          "deepseek": {"api_key": ""}}, "default_cloud": "anthropic"})

    def test_cloud_chat_and_adaptation(self):
        rt = Routes().add("POST", "/messages", [httpx.Response(200, json={"content": [{"type": "text", "text": "hi"}], "stop_reason": "max_tokens"}),
                                                httpx.Response(500, json={"error": {"message": "overloaded"}}), httpx.Response(200, text="html")])
        rt.add("POST", "/chat/completions", [httpx.Response(400, text="unsupported max_tokens"), httpx.Response(400, text="bad temperature"),
                                             httpx.Response(200, json={"choices": [{"message": {"content": [{"text": "parts"}]}, "finish_reason": "length"}]}),
                                             httpx.Response(200, text="html"), httpx.Response(200, json={"weird": 1})])
        cfg = config.load_config()
        with patched(rt):
            self.assertIn("truncated", run(llm.cloud_chat(cfg, "anthropic", "s", MSG, 10)))
            with self.assertRaises(llm.LLMError):
                run(llm.cloud_chat(cfg, "anthropic", "s", MSG, 10))
            with self.assertRaises(llm.LLMError):
                run(llm.cloud_chat(cfg, "anthropic", "s", MSG, 10))
            out = run(llm.cloud_chat(cfg, "deepinfra", "s", MSG, 10)) if False else run(llm.openai_compat_chat("https://x/v1", "k", "m", "s", MSG, 10, 0.2, "X", "openrouter"))
            self.assertTrue(out.startswith("parts"))
            with self.assertRaises(llm.LLMError):
                run(llm.openai_compat_chat("https://x/v1", "k", "m", "s", MSG, 10, 0.2, "X"))
            with self.assertRaises(llm.LLMError):
                run(llm.openai_compat_chat("https://x/v1", "k", "m", "s", MSG, 10, 0.2, "X"))
        for pid in ("deepseek",):
            with self.assertRaises(llm.LLMError):
                run(llm.cloud_chat(cfg, pid, "s", MSG, 10))
        cfg["providers"]["custom"].update(api_key="k", base_url="", model="m")
        with self.assertRaises(llm.LLMError):
            run(llm.cloud_chat(cfg, "custom", "s", MSG, 10))
        cfg["providers"]["custom"].update(base_url="http://h", model="")
        with self.assertRaises(llm.LLMError):
            run(llm.cloud_chat(cfg, "custom", "s", MSG, 10))

    def test_network_errors(self):
        def boom(req):
            raise httpx.ConnectError("down")
        def timeout(req):
            raise httpx.ReadTimeout("slow")
        for h in (boom, timeout):
            with patched(h):
                with self.assertRaises(llm.LLMError):
                    run(llm.anthropic_chat("https://a", "k", "m", "s", MSG, 10))
                with self.assertRaises(llm.LLMError):
                    run(llm.openai_compat_chat("https://a", "k", "m", "s", MSG, 10, None, "X"))
                with self.assertRaises(llm.LLMError):
                    run(llm.list_provider_models(config.load_config(), "openai"))

                async def drain(g):
                    return [x async for x in g]
                with self.assertRaises(llm.LLMError):
                    run(drain(llm._stream_anthropic("https://a", "k", "m", "s", MSG, 10)))
                with self.assertRaises(llm.LLMError):
                    run(drain(llm._stream_openai("https://a", "k", "m", "s", MSG, 10, 0.1, "X")))

    def test_list_models(self):
        rt = Routes().add("GET", "/models", [httpx.Response(200, json={"data": [{"id": "models/gemini-x"}, {"name": "b"}, "c", {}]}),
                                             httpx.Response(401, json={"error": {"message": "bad key"}}),
                                             httpx.Response(200, json=[{"id": "gw-model"}])])
        cfg = config.load_config()
        with patched(rt):
            self.assertEqual(run(llm.list_provider_models(cfg, "anthropic")), ["b", "c", "gemini-x"])
            with self.assertRaises(llm.LLMError):
                run(llm.list_provider_models(cfg, "openai"))
            self.assertEqual(run(llm.list_provider_models(cfg, "ninerouter")), ["gw-model"])  # key optional
        self.assertNotIn("authorization", {k.lower() for k in rt.seen[-1]})
        with self.assertRaises(llm.LLMError):
            run(llm.list_provider_models(cfg, "deepseek"))

    def test_streaming(self):
        a_sse = ('data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"He"}}\n\n'
                 'data: [DONE]\n\ndata: not json\n\n: comment\n\n'
                 'data: {"type":"message_delta","delta":{"stop_reason":"max_tokens"}}\n\n')
        o_sse = ('data: {"choices":[{"delta":{"content":[{"text":"A"}]}}]}\n\n data: \n\n'
                 'data: {"choices":[]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n')
        rt = Routes().add("POST", "/messages", [httpx.Response(200, text=a_sse), httpx.Response(200, text='data: {"type":"error","error":{"message":"x"}}\n\n'),
                                                httpx.Response(529, json={"error": {"message": "busy"}})])
        rt.add("POST", "/chat/completions", [httpx.Response(400, text="max_tokens not supported"), httpx.Response(400, text="temperature unsupported"),
                                             httpx.Response(200, text=o_sse), httpx.Response(503, text="down")])

        async def drain(g):
            return [x async for x in g]
        with patched(rt):
            self.assertEqual(run(drain(llm._stream_anthropic("https://a", "k", "m", "s", MSG, 10)))[0], "He")
            with self.assertRaises(llm.LLMError):
                run(drain(llm._stream_anthropic("https://a", "k", "m", "s", MSG, 10)))
            with self.assertRaises(llm.LLMError):
                run(drain(llm._stream_anthropic("https://a", "k", "m", "s", MSG, 10)))
            out = run(drain(llm._stream_openai("https://o", "k", "m", "s", MSG, 10, 0.1, "X", "groq")))
            self.assertEqual(out[0], "A")
            self.assertIn("truncated", out[-1])
            with self.assertRaises(llm.LLMError):
                run(drain(llm._stream_openai("https://o", "", "m", "s", MSG, 10, None, "X", "openrouter")))

    def test_stream_engine_cloud_and_key_errors(self):
        cfg = config.load_config()

        async def drain(g):
            return [x async for x in g]
        with mock.patch.object(llm, "_stream_anthropic", lambda *a: _agen("claude")), mock.patch.object(llm, "_stream_openai", lambda *a: _agen("gpt")):
            self.assertEqual(run(drain(llm._stream_engine(cfg, "anthropic", "s", MSG, 10, 0.1))), ["claude"])
            self.assertEqual(run(drain(llm._stream_engine(cfg, "openai", "s", MSG, 10, 0.1))), ["gpt"])
        with self.assertRaises(llm.LLMError):
            run(drain(llm._stream_engine(cfg, "deepseek", "s", MSG, 10, 0.1)))


async def _agen(*parts):
    for p in parts:
        yield p


class Agents(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("legacy-agents")
        LC.reset()
        config.save_config({"providers": {"anthropic": {"api_key": "sk-ant"}}, "default_cloud": "anthropic", "fallback_to_cloud": True,
                            "agent_modes": {"summarizer": "local", "chat_lit2plan": "claude", "lit2plan": "auto", "author": "ollama"},
                            "agent_models": {"author": "big-model"}, "local_model": "lm-1", "ollama_model": "ol-1"})


    def test_local_targets(self):
        cfg = config.load_config()
        self.assertEqual(run(llm.local_target(cfg, "ollama"))[1], "ol-1")
        cfg["ollama_model"] = ""
        with mock.patch("backend.providers.local.first_model", return_value=None):
            with self.assertRaises(llm.LLMError):
                run(llm.local_target(cfg, "ollama"))
        cfg["local_model"] = ""
        with mock.patch("backend.providers.local.first_model", side_effect=RuntimeError), \
                mock.patch.object(llm, "list_local_models", return_value=["m-first"]):
            self.assertEqual(run(llm.local_target(cfg, "local"))[1], "m-first")
        with mock.patch("backend.providers.local.first_model", return_value=None), mock.patch.object(llm, "list_local_models", return_value=[]):
            with self.assertRaises(llm.LLMError):
                run(llm.local_target(cfg, "local"))
        rt = Routes().add("GET", "/models", [httpx.Response(200, json={"data": [{"id": "a"}, {}]}), httpx.Response(500)])
        with patched(rt):
            self.assertEqual(run(llm.list_local_models("http://lm/v1")), ["a"])
            with self.assertRaises(llm.LLMError):
                run(llm.list_local_models("http://lm/v1"))
        with mock.patch("backend.execution.resources.gpu_busy", side_effect=RuntimeError):
            self.assertIsNone(llm.ollama_offload_options(cfg))
        with mock.patch("backend.execution.resources.gpu_busy", return_value=True):
            self.assertEqual(llm.ollama_offload_options(cfg)["num_gpu"], 0)

    def test_ollama_native_errors(self):
        cfg = config.load_config()
        rt = Routes().add("POST", "/api/chat", [httpx.Response(500, json={"error": "oom"}), httpx.Response(200, json={"message": {"content": "x"}, "done_reason": "length"}),
                                                httpx.Response(200, text=json.dumps({"error": "model gone"}) + "\n"),
                                                httpx.Response(500, text="nope"),
                                                httpx.Response(200, text="junk\n\n" + json.dumps({"done": True, "done_reason": "length"}) + "\n")])
        msgs = [{"role": "user", "content": "q", "images": [{"data": "AAA"}]}]

        async def drain(g):
            return [x async for x in g]
        with patched(rt):
            with self.assertRaises(llm.LLMError):
                run(llm.ollama_native_chat(cfg, "s", msgs, 10, 0.1, None, {}))
            self.assertIn("truncated", run(llm.ollama_native_chat(cfg, "s", msgs, 10, 0.1, None, {})))
            with self.assertRaises(llm.LLMError):
                run(drain(llm._stream_ollama_native(cfg, "s", msgs, 10, 0.1, None, {})))
            with self.assertRaises(llm.LLMError):
                run(drain(llm._stream_ollama_native(cfg, "s", msgs, 10, 0.1, None, {})))
            self.assertIn("truncated", run(drain(llm._stream_ollama_native(cfg, "s", msgs, 10, 0.1, None, {})))[-1])
        for exc in (httpx.ConnectError("x"), httpx.ReadTimeout("y")):
            def h(req, e=exc):
                raise e
            with patched(h):
                with self.assertRaises(llm.LLMError):
                    run(llm.ollama_native_chat(cfg, "s", msgs, 10, 0.1, None, {}))
                with self.assertRaises(llm.LLMError):
                    run(drain(llm._stream_ollama_native(cfg, "s", msgs, 10, 0.1, None, {})))




async def _c(v):
    return v


def _coro(v):
    return _c(v)


class Router(unittest.TestCase):
    def setUp(self):
        RT._cache.clear()


    def test_probes(self):
        with mock.patch("socket.create_connection", side_effect=OSError):
            self.assertFalse(RT.online())
        RT._cache.clear()
        cm = mock.MagicMock()
        with mock.patch("socket.create_connection", return_value=cm):
            self.assertTrue(RT.online())
        with mock.patch("httpx.get", return_value=httpx.Response(200)):
            self.assertTrue(RT._reachable("http://a"))
        with mock.patch("httpx.get", side_effect=httpx.ConnectError("x")):
            self.assertFalse(RT._reachable("http://b"))
        with mock.patch.object(RT, "_reachable", return_value=True) as r:
            RT.local_up({"ollama_base_url": "http://o:11434"}, "ollama")
            RT.local_up({"lmstudio_base_url": "http://l:1234/v1"}, "local")
        self.assertEqual(r.call_args_list[1][0][0], "http://l:1234/v1/models")


class LocalServers(unittest.TestCase):
    def test_roots_and_cli(self):
        self.assertEqual(LA.lms_root("http://h:1/v1/"), "http://h:1")
        self.assertEqual(LA.ollama_root(""), "http://localhost:11434")
        with mock.patch("shutil.which", return_value=None), mock.patch("os.path.isfile", return_value=False):
            self.assertIsNone(LA.lms_cli())
        with mock.patch("shutil.which", return_value=None), mock.patch("os.path.isfile", return_value=True):
            self.assertTrue(LA.lms_cli())
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="o", stderr="e")):
            self.assertEqual(LA._run_cli(["x"]), (0, "oe"))

    def test_lmstudio(self):
        v0 = {"data": [{"id": "m1", "state": "loaded", "type": "llm"}, {"id": "emb", "type": "embeddings"}, {"id": "m2", "state": "not-loaded"}]}
        rt = Routes().add("GET", "/api/v0/models", [httpx.Response(200, json=v0), httpx.Response(404), httpx.Response(404)])
        rt.add("GET", "/v1/models", [httpx.Response(200, json={"data": [{"id": "x"}]}), httpx.Response(500)])
        with patched(rt):
            st = run(LA.lmstudio_status("http://lm/v1"))
            self.assertEqual((st["api"], st["loaded"]), ("v0", ["m1"]))
            self.assertEqual(run(LA.lmstudio_status("http://lm/v1"))["api"], "openai")
            self.assertIn("not reachable", run(LA.lmstudio_status("http://lm/v1"))["error"])

    def test_lmstudio_load_paths(self):
        rt = Routes().add("POST", "/api/v1/models/load", [httpx.Response(200), httpx.Response(404), httpx.Response(404), httpx.Response(404)])
        rt.add("POST", "/v1/chat/completions", [httpx.Response(200), httpx.Response(400, text="no jit")])
        with patched(rt):
            self.assertEqual(run(LA.lmstudio_load("http://lm/v1", "m", 8192))["method"], "rest")
            with mock.patch.object(LA, "lms_cli", return_value="lms"), mock.patch.object(LA, "_run_cli", return_value=(0, "ok")):
                self.assertEqual(run(LA.lmstudio_load("http://lm/v1", "m", 4096))["method"], "lms")
            with mock.patch.object(LA, "lms_cli", return_value="lms"), mock.patch.object(LA, "_run_cli", return_value=(1, "fail")):
                self.assertEqual(run(LA.lmstudio_load("http://lm/v1", "m"))["method"], "jit")
            with mock.patch.object(LA, "lms_cli", return_value="lms"), mock.patch.object(LA, "_run_cli", side_effect=OSError):
                with self.assertRaises(LA.LocalAIError):
                    run(LA.lmstudio_load("http://lm/v1", "m"))

        def down(req):
            raise httpx.ConnectError("x")
        with patched(down), mock.patch.object(LA, "lms_cli", return_value=None):
            with self.assertRaises(LA.LocalAIError):
                run(LA.lmstudio_load("http://lm/v1", "m"))

    def test_lmstudio_unload_paths(self):
        inst = {"models": [{"key": "m1", "loaded_instances": [{"id": "m1:1"}, {}]}, {"key": "m2", "loaded_instances": None}]}
        rt = Routes().add("GET", "/api/v1/models", [httpx.Response(200, json=inst), httpx.Response(200, json={"models": []}),
                                                    httpx.Response(200, json=inst), httpx.Response(500), httpx.Response(500)])
        rt.add("POST", "/api/v1/models/unload", [httpx.Response(200), httpx.Response(500), httpx.Response(200), httpx.Response(404), httpx.Response(404)])
        with patched(rt):
            self.assertEqual(run(LA.lmstudio_unload("http://lm/v1", "m1"))["unloaded"], ["m1:1"])
            self.assertEqual(run(LA.lmstudio_unload("http://lm/v1", "ghost"))["unloaded"], [])  # nothing loaded: not an error
            self.assertEqual(run(LA.lmstudio_unload("http://lm/v1"))["method"], "rest")  # instance unload failed → older API
            with mock.patch.object(LA, "lms_cli", return_value="lms"), mock.patch.object(LA, "_run_cli", return_value=(0, "")):
                self.assertEqual(run(LA.lmstudio_unload("http://lm/v1"))["method"], "lms")
            with mock.patch.object(LA, "lms_cli", return_value="lms"), mock.patch.object(LA, "_run_cli", return_value=(1, "err")):
                with self.assertRaises(LA.LocalAIError):
                    run(LA.lmstudio_unload("http://lm/v1"))

        def down(req):
            raise httpx.ConnectError("x")
        with patched(down), mock.patch.object(LA, "lms_cli", return_value=None):
            with self.assertRaises(LA.LocalAIError):
                run(LA.lmstudio_unload("http://lm/v1", "m"))


    def test_first_model(self):
        cfg = config.load_config()
        cases = [({"loaded": [{"id": "a"}], "models": []}, "a"), ({"loaded": [], "models": [{"id": "b"}]}, "b"), ({"loaded": [], "models": []}, None)]
        for st, want in cases:
            with mock.patch.object(LA, "ollama_status", return_value=st):
                self.assertEqual(run(LA.first_model("ollama", cfg)), want)
        cases = [({"loaded": ["x"], "models": []}, "x"), ({"loaded": [], "models": [{"id": "y"}]}, "y"), ({"loaded": [], "models": []}, None)]
        for st, want in cases:
            with mock.patch.object(LA, "lmstudio_status", return_value=st):
                self.assertEqual(run(LA.first_model("local", cfg)), want)


if __name__ == "__main__":
    unittest.main()
