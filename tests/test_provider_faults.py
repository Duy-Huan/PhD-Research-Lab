"""Offline protocol, privacy and recovery regressions for provider boundaries."""
import _env  # noqa: F401
import asyncio
import contextlib
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend.core import config
from backend.providers import context_packet as CP, events as E, firewall as F, gateway as G, lifecycle as LC
from backend.providers import mcp_server as MS, mcp_tools as MT, privacy as P, registry as PR, research as RP, router as RT
from backend.providers import cli as C


class Faults(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("provider-faults")
        config.save_config({"mcp": {"enabled": True, "expose_research": True, "expose_sandbox": True,
                                    "allow_writes": True, "token": "", "rate_limit_per_min": 0},
                            "gateway": {"enabled": True, "block_source_code": True},
                            "memory": {"embed_engine": "hashing", "v2_pipeline": True}})
        self.cfg = config.load_config()
        G.REQS.clear()
        RT._cache.clear()
        RP._health.clear()
        LC.reset()
        self.addCleanup(G.REQS.clear)
        self.addCleanup(LC.reset)

    def test_privacy_classification_reset_and_validation(self):
        self.cfg["gateway"].update(allow_internal=False, allow_sensitive=True, block_source_code=False)
        self.assertEqual(P.allowed_classes(self.cfg), ("PUBLIC", "SENSITIVE"))
        self.assertEqual(P.sanitize("```literal```", self.cfg), ("```literal```", []))
        self.assertEqual(P.set_sensitivity("record:1", "SENSITIVE")["sensitivity"], "SENSITIVE")
        self.assertEqual(P.set_sensitivity("record:1", "")["sensitivity"], "(type default)")
        for record, level in (("a", "UNKNOWN"), ("../bad?", "PUBLIC")):
            with self.assertRaises(ValueError):
                P.set_sensitivity(record, level)

    def test_registry_configuration_probe_and_setting_failures(self):
        self.cfg["providers"]["custom"].update(base_url="ftp://wrong", model="m")
        self.assertEqual(PR.describe("app:custom", self.cfg)["state"], "ERROR")
        with self.assertRaisesRegex(Exception, "Unknown provider"):
            PR.describe("app:unknown", self.cfg)
        conn = C.CONNECTORS["codex"]
        with mock.patch.object(conn, "health", side_effect=OSError("probe failed")):
            self.assertFalse(PR.describe("cli:codex", self.cfg)["available"])
        caps = {"reasoning_controls": [], "sandbox_options": [{"profile": "review"}], "model_override": False}
        with mock.patch.object(PR, "describe", return_value={"capabilities": caps}):
            self.assertEqual(PR.check_setting("app:custom", "reasoning", "off"), "")
            self.assertIn("no reasoning", PR.check_setting("app:custom", "reasoning", "high"))
            self.assertIn("refused", PR.check_setting("cli:codex", "security_profile", "assisted"))
            self.assertIn("model choice", PR.check_setting("app:custom", "model", "model"))
            self.assertEqual(PR.check_setting("cli:codex", "security_profile", "review"), "")

    def test_router_offline_busy_duplicate_and_invalid_targets(self):
        c = copy.deepcopy(self.cfg)
        c["default_cloud"] = "openai"
        c["providers"]["openai"]["api_key"] = "test-key"
        c["routing"].update(online_check=False, capability_aware=False, chains={"general": ["ollama", "local", "@cloud", "missing", "ollama"]})
        with mock.patch.object(RT, "local_up", return_value=True), \
                mock.patch("backend.execution.resources.gpu_busy", return_value=True):
            plan = RT.plan(c, "unknown")
        self.assertEqual(plan["candidates"], ["openai", "ollama"])
        self.assertIn("GPU busy", plan["skipped"]["local"])
        self.assertFalse(RT.provider_ready(c, "missing", True))
        c["providers"]["openai"]["base_url"] = "bad-url"
        self.assertFalse(RT.provider_ready(c, "openai", True))
        c["routing"].update(online_check=True)
        with mock.patch.object(RT, "online", return_value=False), mock.patch.object(RT, "local_up", return_value=False), \
                mock.patch("backend.execution.resources.gpu_busy", side_effect=OSError):
            plan = RT.plan(c, "unknown")
        self.assertEqual(plan["candidates"], [])
        self.assertEqual(plan["skipped"]["openai"], "offline")

    def test_research_health_disabled_missing_install_and_cancellation(self):
        self.cfg["clearml"]["enabled"] = False
        self.assertEqual(RP._exec_health("clearml", self.cfg)["state"], "DISABLED")
        self.cfg["clearml"]["enabled"] = True
        with mock.patch("importlib.util.find_spec", return_value=None):
            self.assertEqual(RP._exec_health("clearml", self.cfg)["state"], "UNAVAILABLE")
        self.cfg["research_providers"]["feynman_share_app_key"] = True
        self.cfg["providers"]["anthropic"]["api_key"] = ""
        self.cfg["providers"]["openai"]["api_key"] = ""
        self.assertEqual(RP._shared_key(self.cfg), {})
        connector = mock.Mock()
        connector.stream_message.return_value = iter([{"type": "request_started"}, {"type": "text_delta", "text": "late"}])
        with mock.patch.dict(C.CONNECTORS, {"codex": connector}):
            out = RP.run_coding("cancelled-provider", "codex", "q", "ctx", config.data_dir() / "out", cancelled=lambda: True)
        self.assertEqual(out["text"], "")

    def test_mcp_guard_audit_disabled_and_token_failure(self):
        with mock.patch.object(MS, "_mcfg", return_value={"enabled": False}):
            self.assertEqual(MS.guard({}, "test")[0], 403)
        with mock.patch.object(MS, "_mcfg", return_value={"enabled": True, "token": "required"}):
            self.assertEqual(MS.guard({"authorization": "Bearer wrong"}, "test")[0], 401)
        with mock.patch.object(MS, "_mcfg", return_value={"audit": False}), mock.patch("builtins.open") as opened:
            MS.audit({"tool": "x"})
            opened.assert_not_called()
        with mock.patch.object(MS, "_mcfg", return_value={"audit": True}), mock.patch("builtins.open", side_effect=OSError):
            MS.audit({"tool": "x"})

    def test_mcp_sandbox_commands_files_and_metrics(self):
        job = SimpleNamespace(id="job", status="done", exit_code=0, mode="local", meta={"metrics": {"acc": 1}},
                              tail=lambda *args: "output")
        with mock.patch.object(MS.sandbox, "run_blocking", return_value=job) as run, \
                mock.patch.object(LC, "sandbox_lease", return_value=contextlib.nullcontext()):
            data = json.loads(MS.call_tool("sandbox_run_code", {"code": "print(1)", "timeout": 9999})["content"][0]["text"])
        self.assertEqual(data["run_id"], "job")
        self.assertEqual(run.call_args.args[1], 3600)
        self.assertTrue(MS.ide_fs.read("_mcp_snippet.py")["content"].startswith("print"))
        with self.assertRaisesRegex(ValueError, "code.*command"):
            MS.call_tool("sandbox_run_code", {})
        MS.call_tool("sandbox_manage_files", {"action": "write", "path": "note.txt", "content": "needle"})
        self.assertIn("note.txt", MS.call_tool("sandbox_manage_files", {"action": "list"})["content"][0]["text"])
        self.assertIn("needle", MS.call_tool("sandbox_manage_files", {"action": "search", "query": "needle"})["content"][0]["text"])
        config.save_config({"gateway": {"block_source_code": False}})
        with mock.patch.object(MS.ide_fs, "read", return_value={}):
            self.assertEqual(MS.call_tool("sandbox_manage_files", {"action": "read", "path": "binary"})["content"][0]["text"], "(binary file)")
        MS.call_tool("sandbox_manage_files", {"action": "delete", "path": "note.txt"})
        with self.assertRaisesRegex(ValueError, "Unknown action"):
            MS.call_tool("sandbox_manage_files", {"action": "unknown"})
        with mock.patch.object(MS.sandbox, "get_run", return_value={"id": "job", "status": "done"}):
            self.assertIn("job", MS.call_tool("sandbox_get_metrics", {"run_id": "job"})["content"][0]["text"])
        with mock.patch.object(MS.sandbox, "best_metrics", return_value={}), mock.patch.object(MS.sandbox, "list_runs", return_value=[]):
            self.assertIn("recent_runs", MS.call_tool("sandbox_get_metrics", {})["content"][0]["text"])
        with self.assertRaisesRegex(ValueError, "Unknown tool"):
            MS.call_tool("not-a-tool", {})

    def test_mcp_jsonrpc_errors_and_telemetry_failure_preserve_response(self):
        with mock.patch.object(MS, "tool_list", side_effect=RuntimeError("broken registry")):
            self.assertEqual(MS.handle({"id": 1, "method": "tools/list"})["error"]["code"], -32603)
        with mock.patch.object(MS, "call_tool", return_value={"content": []}), \
                mock.patch("backend.core.telemetry.record", side_effect=OSError):
            response = MS.handle({"id": 2, "method": "tools/call", "params": {"name": "fake"}})
        self.assertEqual(response["result"], {"content": []})

    def test_gateway_storage_errors_and_reloaded_request_refusal(self):
        with mock.patch("builtins.open", side_effect=OSError):
            G.audit("offline")
        with mock.patch.object(Path, "write_text", side_effect=OSError):
            G._persist({"id": "gw-0123456789"})
        with self.assertRaisesRegex(G.GatewayError, "Invalid session"):
            G._session("invalid")
        sid = G._session()
        (G._dir("sessions") / (sid + ".json")).write_text("{bad", "utf-8")
        G._session_add(sid, "gw-0123456789", "codex")
        self.assertEqual(json.loads((G._dir("sessions") / (sid + ".json")).read_text())["requests"][0]["provider"], "codex")
        record = {"id": "gw-0123456789", "provider": "codex", "status": "ready"}
        G._persist(record)
        self.assertEqual(G.get(record["id"])["status"], "ready")
        with self.assertRaisesRegex(G.GatewayError, "no longer active"):
            G.send(record["id"])
        with self.assertRaisesRegex(G.GatewayError, "not found"):
            G.get("gw-fffffffffe")

    def test_gateway_failures_close_requests_and_keep_finished_state(self):
        record = {"id": "gw-0123456789", "provider": "codex", "session_id": "gs-01234567", "context_tokens": 1,
                  "context_version": 1, "prompt": "q", "answer": "", "events": [], "errors": [], "status": "running"}
        for exception in (C.ProviderError("auth", "AUTH_EXPIRED"), RuntimeError("reader failed")):
            r = copy.deepcopy(record)
            conn = mock.Mock()
            conn.stream_message.side_effect = exception
            G._run_inner(r, conn, {})
            self.assertEqual(r["status"], "failed")
            self.assertIsNotNone(r["ended"])
            self.assertTrue(r["errors"])
        r = copy.deepcopy(record)
        r["status"] = "cancelled"
        conn = mock.Mock()
        conn.stream_message.return_value = iter([])
        G._run_inner(r, conn, {})
        self.assertEqual(r["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
