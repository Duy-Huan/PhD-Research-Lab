"""Provider connection regressions: real HTTP adapters and API routes with offline MockTransport responses."""
import _env  # noqa: F401
import asyncio
import contextlib
import json
import subprocess
import unittest
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from backend.app import app
from backend.core import config
from backend.execution import tools
from backend.providers import cli as C, lifecycle as LC, local as L, models as M, registry as PR, research as RP, router as RT


class Transport:
    def __init__(self, handler):
        self.handler, self.requests = handler, []
        self.real_client = httpx.AsyncClient

    def client(self, *args, **kwargs):
        def handle(req):
            self.requests.append(req)
            return self.handler(req)
        return self.real_client(transport=httpx.MockTransport(handle), timeout=kwargs.get("timeout", 10))

    @contextlib.asynccontextmanager
    async def lease(self, timeout):
        async with self.client(timeout=timeout) as client:
            yield client


async def drain(generator):
    return [part async for part in generator]


class Connectivity(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        LC.reset()
        RP._health.clear()
        RT._cache.clear()
        tools._cache.clear()
        C._last_error.clear()
        self.addCleanup(C._last_error.clear)
        self.addCleanup(RP._health.clear)
        self.addCleanup(RT._cache.clear)
        config.save_config({"providers": {"anthropic": {"api_key": "test-key", "model": "claude-sonnet-5-5"},
                                          "openai": {"api_key": "test-key"},
                                          "ninerouter": {"model": "gateway-model", "api_key": ""}},
                            "routing": {"provider_headers": {"ninerouter": {"X-Route": "research"}}}})
        self.cfg = config.load_config()

    def test_provider_url_normalization_and_validation(self):
        for supplied, expected in ((" https://api.anthropic.com/ ", "https://api.anthropic.com/v1"),
                                   ("https://proxy.example/v1/messages", "https://proxy.example/v1")):
            self.cfg["providers"]["anthropic"]["base_url"] = supplied
            self.assertEqual(M.provider_settings(self.cfg, "anthropic")[3], expected)
        self.cfg["providers"]["custom"].update(base_url="http://localhost:9000/v1/chat/completions", model="m")
        self.assertEqual(M.provider_settings(self.cfg, "custom")[3], "http://localhost:9000/v1")
        for bad in ("ftp://example.org", "https://host:bad", "https://user:pass@host/v1", "https://host/v1?key=x"):
            with self.subTest(bad), self.assertRaises(M.LLMError):
                M.normalize_base_url(bad)

    def test_keyless_gateways_are_selectable_and_auth_is_unverified(self):
        for pid in ("ninerouter", "omniroute"):
            row = PR.describe("app:" + pid, self.cfg)
            self.assertTrue(row["available"])
            self.assertEqual(row["state"], "UNKNOWN")
        self.assertEqual(PR.describe("app:anthropic", self.cfg)["state"], "UNKNOWN")
        self.cfg["providers"]["custom"].update(base_url="http://localhost:9000/v1", model="m", api_key="")
        self.assertTrue(PR.describe("app:custom", self.cfg)["available"])
        self.cfg["providers"]["custom"]["base_url"] = "https://remote.example/v1"
        self.assertFalse(PR.describe("app:custom", self.cfg)["available"])

    def test_gateway_model_discovery_uses_extra_headers(self):
        def handler(req):
            self.assertEqual(req.headers["x-route"], "research")
            self.assertNotIn("authorization", req.headers)
            return httpx.Response(200, json={"data": [{"id": "m"}, {"id": "m"}, {}, None]})
        transport = Transport(handler)
        with mock.patch("httpx.AsyncClient", transport.client):
            self.assertEqual(asyncio.run(M.list_provider_models(self.cfg, "ninerouter")), ["m"])

    def test_invalid_model_lists_are_actionable_errors(self):
        for response in (httpx.Response(200, text="<html>login</html>"), httpx.Response(200, json={"error": "bad"}),
                         httpx.Response(200, json={"data": None}), httpx.Response(200, json=42)):
            with self.subTest(response=response):
                transport = Transport(lambda req: response)
                with mock.patch("httpx.AsyncClient", transport.client), self.assertRaises(M.LLMError):
                    asyncio.run(M.list_provider_models(self.cfg, "openai"))

    def test_local_root_and_v1_give_same_chat_target(self):
        self.cfg.update(local_model="lm", lmstudio_base_url=" http://localhost:1234/ ")
        self.assertEqual(asyncio.run(M.local_target(self.cfg, "local"))[0], "http://localhost:1234/v1")
        transport = Transport(lambda req: httpx.Response(200, json={"data": [{"id": "lm"}]}))
        with mock.patch("httpx.AsyncClient", transport.client):
            self.assertEqual(asyncio.run(M.list_local_models("http://localhost:1234")), ["lm"])
        self.assertEqual(transport.requests[0].url.path, "/v1/models")

    def test_local_model_status_survives_html_and_excludes_embeddings(self):
        def handler(req):
            if req.url.path == "/api/v0/models":
                return httpx.Response(200, text="<html>not the API</html>")
            if req.url.path == "/v1/models":
                return httpx.Response(200, json={"data": [{"id": "lm"}]})
            return httpx.Response(200, json=[])
        transport = Transport(handler)
        with mock.patch("httpx.AsyncClient", transport.client), mock.patch.object(L, "lms_cli", return_value=None):
            self.assertEqual(asyncio.run(L.lmstudio_status("http://lm"))["api"], "openai")
            self.assertFalse(asyncio.run(L.ollama_status("http://ol"))["online"])
        transport = Transport(lambda req: httpx.Response(200, json={"data": [{"id": "e", "type": "embedding"},
                                                                                           {}, {"id": "m", "state": "loaded"}]}))
        with mock.patch("httpx.AsyncClient", transport.client), mock.patch.object(L, "lms_cli", return_value=None):
            self.assertEqual(asyncio.run(L.lmstudio_status("http://lm"))["loaded"], ["m"])

    def test_anthropic_current_models_use_adaptive_effort_in_both_transports(self):
        def handler(req):
            body = json.loads(req.content)
            self.assertEqual(body["thinking"], {"type": "adaptive"})
            self.assertEqual(body["output_config"], {"effort": "high"})
            self.assertEqual(body["max_tokens"], 1000)
            if body.get("stream"):
                return httpx.Response(200, text='data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"OK"}}\n\n')
            return httpx.Response(200, json={"content": [{"type": "text", "text": "OK"}]})
        transport = Transport(handler)
        async def check():
            token = M.REASONING.set("high")
            try:
                self.assertEqual(await M.anthropic_chat("https://a/v1", "k", "claude-sonnet-5-5", "s", [], 1000), "OK")
                self.assertEqual(await drain(M._stream_anthropic("https://a/v1", "k", "claude-sonnet-5-5", "s", [], 1000)), ["OK"])
            finally:
                M.REASONING.reset(token)
        with mock.patch.object(LC, "http_client", transport.lease):
            asyncio.run(check())

    def test_always_on_thinking_is_reported_instead_of_an_invalid_request(self):
        self.cfg["providers"]["anthropic"]["model"] = "claude-opus-5-5"
        self.assertNotIn("off", PR.describe("app:anthropic", self.cfg)["capabilities"]["reasoning_controls"])
        token = M.REASONING.set("off")
        try:
            with self.assertRaisesRegex(M.LLMError, "always-on"):
                M._anthropic_body("claude-opus-5-5", "s", [], 1000)
            self.assertEqual(M._anthropic_body("claude-sonnet-5-5", "s", [], 1000)["thinking"]["type"], "between_tools")
        finally:
            M.REASONING.reset(token)

    def test_openai_stream_error_is_not_silent_success(self):
        transport = Transport(lambda req: httpx.Response(200, text='data: {"error":{"message":"quota exhausted"}}\n\n'))
        with mock.patch.object(LC, "http_client", transport.lease), self.assertRaisesRegex(M.LLMError, "quota exhausted"):
            asyncio.run(drain(M._stream_openai("https://a/v1", "k", "m", "s", [], 1000, None, "Gateway")))

    def test_malformed_success_messages_are_provider_errors(self):
        for response in ({"choices": [{"message": "wrong"}]}, {"choices": [{"message": {"content": 42}}]}):
            transport = Transport(lambda req: httpx.Response(200, json=response))
            with mock.patch.object(LC, "http_client", transport.lease), self.assertRaises(M.LLMError):
                asyncio.run(M.openai_compat_chat("https://a/v1", "k", "m", "s", [], 10, None, "Gateway"))

    def test_stream_target_validation_precedes_network(self):
        self.cfg["providers"]["custom"].update(api_key="k", base_url="", model="m")
        with mock.patch.object(LC, "http_client") as client, self.assertRaisesRegex(M.LLMError, "base URL is empty"):
            asyncio.run(drain(M._stream_engine(self.cfg, "custom", "s", [], 10, None)))
        client.assert_not_called()

    def test_gateway_router_checks_model_and_authenticates_reachability(self):
        self.cfg["providers"]["ninerouter"]["api_key"] = "gateway-key"
        with mock.patch.object(RT, "_reachable", return_value=True) as reachable:
            self.assertTrue(RT.provider_ready(self.cfg, "ninerouter", False))
            self.assertEqual(reachable.call_args.args[1]["Authorization"], "Bearer gateway-key")
            self.cfg["providers"]["ninerouter"]["model"] = ""
            self.assertFalse(RT.provider_ready(self.cfg, "ninerouter", False))
        for status in (401, 404, 503):
            with mock.patch("httpx.get", return_value=httpx.Response(status)):
                self.assertFalse(RT._reachable("http://gateway/" + str(status)))

    def test_health_refresh_reprobes_login_and_configuration_changes(self):
        connector = C.CodexConnector()
        probes = [{"bin": "codex", "ok": True, "login_code": 1},
                  {"bin": "codex", "ok": True, "login_code": 0, "login": "Logged in using ChatGPT"}]
        with mock.patch.object(connector, "binary", return_value="codex"), mock.patch.object(connector, "_probe", side_effect=probes):
            self.assertEqual(connector.health()["state"], "AUTH_EXPIRED")
            C._last_error["codex"] = ("AUTH_EXPIRED", "old failure")
            self.assertEqual(connector.health(fresh=True)["state"], "CONNECTED")
        with mock.patch.object(RP, "_coding_health", return_value={"state": "READY"}) as probe:
            self.assertTrue(RP.describe("codex", self.cfg, fresh=True)["ready"])
            self.cfg["research_providers"]["coding_default"] = 'gemini_cli'
            RP.describe("codex", self.cfg)
            self.assertEqual(probe.call_count, 2)

    def test_windows_cancel_falls_back_when_taskkill_fails(self):
        proc = mock.Mock(pid=123)
        proc.poll.return_value = None
        with mock.patch.object(C.sys, "platform", "win32"), mock.patch.object(C.subprocess, "run", side_effect=subprocess.TimeoutExpired("taskkill", 5)):
            C.kill_tree(proc)
        proc.kill.assert_called_once()

    def test_claude_auth_probe_preserves_only_status_fields(self):
        connector = C.ClaudeCodeConnector()
        status = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "email": "private@example.org"}
        with mock.patch.object(connector, "binary", return_value="claude"), \
                mock.patch.object(C, "run_cli", side_effect=[(0, "1.0"), (0, json.dumps(status))]):
            probe = connector._probe()
        self.assertNotIn("email", probe["auth"])
        self.assertEqual(connector.auth_state(probe)[0], "CONNECTED")
        self.assertEqual(connector.auth_state({"auth": {"loggedIn": False}})[0], "AUTH_EXPIRED")
        self.assertEqual(connector.auth_state({"auth": {"loggedIn": True, "authMethod": "api_key"}, "auth_code": 0})[0], "ERROR")
        self.assertEqual(connector.auth_state({})[0], "UNKNOWN")

    def test_claude_native_install_is_discovered_when_path_is_stale(self):
        from pathlib import Path
        connector = C.ClaudeCodeConnector()
        with mock.patch.object(C.CLIConnector, "binary", return_value=None), \
                mock.patch.object(Path, "is_file", return_value=True):
            self.assertIn(".local", connector.binary())

    def test_sign_in_launch_delegates_to_project_isolated_native_runtime(self):
        connector = C.ClaudeCodeConnector()
        with mock.patch('backend.providers.native.launch_provider', return_value={'launched': True, 'state': 'LAUNCHED'}) as launch:
            self.assertTrue(connector.connect(launch=True)["launched"])
        launch.assert_called_once_with('claude_code', True)

    def test_connection_endpoint_exercises_actual_stream_and_model_override(self):
        def handler(req):
            body = json.loads(req.content)
            self.assertTrue(body["stream"])
            self.assertEqual(body["model"], "selected-model")
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"OK"}}]}\n\ndata: [DONE]\n\n')
        transport = Transport(handler)
        with mock.patch.object(LC, "http_client", transport.lease), TestClient(app, headers={"X-PhDLab-Client": "ui"}) as client:
            response = client.post("/api/models/test", json={"provider": "app:ninerouter", "model": "selected-model"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["reply"], "OK")

    def test_connection_endpoint_rejects_empty_stream_and_errors(self):
        for text in ("<html>gateway login</html>", 'data: {"error":{"message":"invalid key"}}\n\n'):
            transport = Transport(lambda req: httpx.Response(200, text=text))
            with mock.patch.object(LC, "http_client", transport.lease), TestClient(app, headers={"X-PhDLab-Client": "ui"}) as client:
                response = client.post("/api/models/test", json={"provider": "ninerouter"})
            self.assertEqual(response.status_code, 502, response.text)

    def test_connection_deadline_cancels_upstream_stream(self):
        cancelled = []
        async def slow(*args, **kwargs):
            try:
                await asyncio.Event().wait()
                yield "unreachable"
            finally:
                cancelled.append(True)
        original = asyncio.wait_for
        async def short_deadline(coro, timeout):
            self.assertEqual(timeout, 60)
            return await original(coro, timeout=0.01)
        with mock.patch.object(M, "_stream_engine", slow), mock.patch("backend.api.system.wait_for", short_deadline), \
                TestClient(app, headers={"X-PhDLab-Client": "ui"}) as client:
            response = client.post("/api/models/test", json={"provider": "ninerouter"})
        self.assertEqual(response.status_code, 504, response.text)
        self.assertEqual(cancelled, [True])


if __name__ == "__main__":
    unittest.main()
