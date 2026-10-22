"""v4.1 hooks inside existing modules: every local LLM call / stream / embedding holds a lifecycle lease with the right
purpose, cloud calls use the lifecycle HTTP client, MCP sandbox runs lease the container, and the opt-in automatic VRAM
release before GPU training (sandbox.start_job)."""
import _env  # noqa: F401  (must be first)
import asyncio
import json
import unittest
from unittest import mock

import httpx

from backend.core import config
from backend.providers import models as llm, lifecycle as LC
from backend.execution import resources as R, sandbox
from test_model_lifecycle import Fakes


def transport(handler):
    real = httpx.AsyncClient

    def factory(*a, **k):
        k.pop("limits", None)
        return real(transport=httpx.MockTransport(handler), timeout=k.get("timeout"))
    return mock.patch.object(LC.httpx, "AsyncClient", factory)


class LocalLeases(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("v41-hooks")
        LC.reset()
        config.save_config({"lifecycle": {"enabled": True, "local_background": "unload_after_task", "local_interactive": "idle_unload"},
                            "agent_modes": {"utility": "ollama", "research": "ollama"}, "ollama_model": "qwen2.5:7b",
                            "fallback_to_cloud": False})

    def tearDown(self):
        LC.reset()

    def test_call_agent_background_purpose(self):
        async def fake_chat(*a, **k):
            self.assertEqual(LC._res["local:ollama:qwen2.5:7b"].leases, 1)
            return "summary"
        with Fakes(), mock.patch.object(llm, "openai_compat_chat", fake_chat), mock.patch.object(llm, "ollama_offload_options", return_value=None):
            r = asyncio.run(llm.call_agent("utility", "sys", "text"))
        self.assertEqual(r["text"], "summary")
        res = LC._res["local:ollama:qwen2.5:7b"]
        self.assertEqual((res.leases, res.policy), (0, "unload_after_task"))

    def test_offloaded_ollama_call_and_stream(self):
        async def native(*a, **k):
            return "cpu answer"

        async def native_stream(*a, **k):
            for p in ("a", "b"):
                yield p
        with Fakes(), mock.patch.object(llm, "ollama_offload_options", return_value={"num_gpu": 0}), \
                mock.patch.object(llm, "ollama_native_chat", native), mock.patch.object(llm, "_stream_ollama_native", native_stream):
            cfg = config.load_config()
            self.assertEqual(asyncio.run(llm.local_chat(cfg, "s", [{"role": "user", "content": "q"}], 10, 0.1, "ollama", None, "background")),
                             "cpu answer")

            async def consume():
                return [p async for p in llm._stream_engine(cfg, "ollama", "s", [], 10, 0.1, None, "interactive")]
            self.assertEqual(asyncio.run(consume()), ["a", "b"])
        self.assertEqual(LC._res["local:ollama:qwen2.5:7b"].policy, "idle_unload")

    def test_stream_agent_interactive_lease_and_early_close(self):
        async def fake_stream(*a, **k):
            for p in ("Hel", "lo"):
                yield p
        with Fakes(), mock.patch.object(llm, "_stream_openai", fake_stream), mock.patch.object(llm, "ollama_offload_options", return_value=None):
            async def full():
                return [x async for x in llm.stream_agent("research", "sys", [{"role": "user", "content": "q"}])]
            out = asyncio.run(full())
            self.assertEqual(out[-1][1]["text"], "Hello")
            self.assertEqual(LC._res["local:ollama:qwen2.5:7b"].policy, "idle_unload")

            async def early():
                g = llm.stream_agent("research", "sys", [{"role": "user", "content": "q"}])
                await g.__anext__()
                await g.aclose()  # the reader left: the lease must still be released
            asyncio.run(early())
        self.assertEqual(LC._res["local:ollama:qwen2.5:7b"].leases, 0)

    def test_auto_routing_local_candidate_uses_the_lease(self):
        async def fake_chat(*a, **k):
            return "auto"
        with Fakes(), mock.patch.object(llm, "openai_compat_chat", fake_chat), mock.patch.object(llm, "ollama_offload_options", return_value=None), \
                mock.patch("backend.providers.router.plan", return_value={"kind": "summarize", "candidates": ["ollama"], "gpu_busy": False,
                                                                       "online": True, "skipped": {}}):
            config.save_config({"agent_modes": {"utility": "auto"}})
            self.assertEqual(asyncio.run(llm.call_agent("utility", "s", "u"))["text"], "auto")
        self.assertIn("local:ollama:qwen2.5:7b", LC._res)

    def test_embeddings_are_background_leases(self):
        from backend.memory import embeddings as EM
        cfg = config.load_config()
        resp = httpx.Response(200, json={"embeddings": [[0.1, 0.2]]}, request=httpx.Request("POST", "http://x"))
        with Fakes(), mock.patch.object(EM.httpx, "post", return_value=resp), mock.patch("backend.execution.resources.gpu_busy", return_value=True):
            vec = EM._ollama_embed(cfg, ["text"], 5)
        self.assertEqual(vec, [[0.1, 0.2]])
        res = LC._res["local:ollama:" + cfg["memory"]["embed_model"]]
        self.assertEqual(res.policy, "unload_after_task")


class CloudClient(unittest.TestCase):
    def setUp(self):
        LC.reset()

    def test_cloud_calls_go_through_the_lifecycle_client(self):
        seen = []

        def handler(req):
            seen.append(str(req.url))
            if req.url.path.endswith("/messages"):
                if json.loads(req.content).get("stream"):
                    body = ('data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hi"}}\n\n'
                            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n')
                    return httpx.Response(200, text=body)
                return httpx.Response(200, json={"content": [{"type": "text", "text": "claude"}], "stop_reason": "end_turn"})
            if json.loads(req.content).get("stream"):
                return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n')
            return httpx.Response(200, json={"choices": [{"message": {"content": "gpt"}, "finish_reason": "stop"}]})

        async def body():
            a = await llm.anthropic_chat("https://api.example/v1", "k", "m", "s", [{"role": "user", "content": "q"}], 10)
            o = await llm.openai_compat_chat("https://oa.example/v1", "k", "m", "s", [{"role": "user", "content": "q"}], 10, 0.1, "X")
            sa = [t async for t in llm._stream_anthropic("https://api.example/v1", "k", "m", "s", [{"role": "user", "content": "q"}], 10)]
            so = [t async for t in llm._stream_openai("https://oa.example/v1", "k", "m", "s", [{"role": "user", "content": "q"}], 10, 0.1, "X")]
            return a, o, sa, so
        with transport(handler):
            a, o, sa, so = asyncio.run(body())
        self.assertEqual((a, o, sa, so), ("claude", "gpt", ["hi"], ["ok"]))
        self.assertEqual(len(seen), 4)


class OllamaNativeAndShutdown(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("v41-native")
        LC.reset()
        config.save_config({"ollama_model": "qwen2.5:7b"})

    def test_native_ollama_chat_and_stream_use_the_lifecycle_client(self):
        def handler(req):
            if json.loads(req.content).get("stream"):
                lines = [json.dumps({"message": {"content": "st"}}), json.dumps({"done": True})]
                return httpx.Response(200, text="\n".join(lines) + "\n")
            return httpx.Response(200, json={"message": {"content": "native"}, "done_reason": "stop"})
        cfg = config.load_config()

        async def body():
            a = await llm.ollama_native_chat(cfg, "s", [{"role": "user", "content": "q"}], 10, 0.1, None, {"num_gpu": 0})
            b = [t async for t in llm._stream_ollama_native(cfg, "s", [], 10, 0.1, None, {"num_gpu": 0})]
            return a, b
        with transport(handler):
            self.assertEqual(asyncio.run(body()), ("native", ["st"]))

    def test_shutdown_never_hangs_on_the_reaper(self):
        from fastapi.testclient import TestClient
        from backend.app import app

        async def stuck(stop):
            await asyncio.sleep(3600)
        with mock.patch("backend.providers.lifecycle.reaper", stuck):
            with TestClient(app) as c:
                self.assertEqual(c.get("/api/version").status_code, 200)


class SandboxHooks(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("v41-sandbox")
        LC.reset()
        sandbox.save_settings({"mode": "local", "gpu": True, "timeout_s": 60})

    def tearDown(self):
        config.save_config({"resources": {"auto_unload_for_gpu": False}})
        LC.reset()

    def test_mcp_sandbox_tool_holds_a_container_lease(self):
        from backend.providers import mcp_server
        job = mock.Mock(id="r1", status="done", exit_code=0, mode="docker", meta={})
        job.tail.return_value = ""
        with mock.patch.object(sandbox, "effective_mode", return_value="docker"), mock.patch.object(sandbox, "container_name", return_value="phdlab-mcp"), \
                mock.patch.object(sandbox, "container_state", return_value={"running": False}), \
                mock.patch.object(sandbox, "run_blocking", return_value=job) as rb:
            out = mcp_server.call_tool("sandbox_run_code", {"command": "python -V"})
        rb.assert_called_once()
        self.assertIn("r1", json.dumps(out))
        self.assertEqual(LC._res["mcp:docker:phdlab-mcp"].leases, 0)

    def test_auto_unload_before_gpu_training(self):
        LOADED = {"ollama": ["qwen2.5:7b"], "lmstudio": []}
        with mock.patch.object(R, "loaded_local_models", return_value=LOADED), mock.patch.object(R, "gpus", return_value=[{"vram_used_mb": 9000}]):
            with self.assertRaises(sandbox.VramBusyError):  # default: refused (v3.2 rule)
                sandbox.start_job('python -c "print(1)"', "run", "gpu")
            config.save_config({"resources": {"auto_unload_for_gpu": True}})
            busy = LC.Resource("local:ollama:qwen2.5:7b", "local", "ollama", "qwen2.5:7b", leases=1)
            LC._res[busy.key] = busy
            with self.assertRaises(sandbox.VramBusyError) as cm:
                sandbox.start_job('python -c "print(1)"', "run", "gpu")
            self.assertIn("answering right now", str(cm.exception))
            busy.leases = 0
            with mock.patch.object(R, "unload_local_models", return_value={"unloaded": [], "errors": []}):
                with self.assertRaises(sandbox.VramBusyError):  # still loaded after the unload attempt
                    sandbox.start_job('python -c "print(1)"', "run", "gpu")

        def freed(*a, **k):
            (k.get("log") or (lambda _m: None))("🧹 VRAM unload: ollama:qwen2.5:7b")
            return {"ok": True, "unloaded": ["ollama:qwen2.5:7b"]}
        calls = iter([LOADED, {"ollama": [], "lmstudio": []}])
        with mock.patch.object(R, "loaded_local_models", side_effect=lambda *a: next(calls)), \
                mock.patch.object(R, "gpus", return_value=[{"vram_used_mb": 500, "temp_c": 40, "vram_total_mb": 12288}]), \
                mock.patch("backend.providers.lifecycle.free_vram_for_gpu", side_effect=freed):
            job = sandbox.start_job('python -c "print(1)"', "run", "gpu")
        self.assertIn("VRAM unload", job.tail(50, "sys"))
        sandbox.stop_job(job.id)


if __name__ == "__main__":
    unittest.main()
