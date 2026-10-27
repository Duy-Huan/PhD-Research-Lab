"""FQC-COVERAGE-662: every /api/tools route maps to its registry/runtime/proposal/client function and maps tool
errors to HTTP status codes. The real registry answers listing, search and describe; side-effecting back ends
(MCP servers, Google, ChatGPT gateway, proposals, jobs) are replaced at their module boundary."""
import json
import unittest
from unittest import mock

import _env  # noqa: F401
from fastapi.testclient import TestClient

from backend.app import app
from backend.tools import chatgpt_gateway, google_mcp, mcp_clients, proposals, registry
from backend.tools.runtime import RUNTIME
from backend.tools.spec import ToolError


class ToolsApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app, headers={"X-PhDLab-Client": "ui"})
        cls.c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def setUp(self):
        _env.isolate_config(self)

    def test_registry_listing_search_and_describe(self):
        tools = self.c.get("/api/tools").json()["tools"]
        self.assertTrue(tools)
        first = tools[0]["id"]
        self.assertEqual(self.c.get(f"/api/tools/{first}").json()["id"], first)
        self.assertIsInstance(self.c.get("/api/tools/search", params={"q": first, "limit": 999}).json()["results"], list)
        missing = self.c.get("/api/tools/does.not.exist")
        self.assertEqual((missing.status_code, missing.json()["detail"]["code"]), (404, "not_found"))
        self.assertIn("records", self.c.get("/api/tools/provenance", params={"limit": 0}).json())
        self.assertEqual(self.c.get("/api/tools/provenance/verify").status_code, 200)

    def test_tool_and_value_errors_become_http_errors(self):
        with mock.patch.object(RUNTIME, "get", side_effect=ToolError("permission_denied", "no")):
            self.assertEqual(self.c.get("/api/tools/jobs/j1").status_code, 403)
        with mock.patch.object(RUNTIME, "get", side_effect=ToolError("timeout", "slow")):
            self.assertEqual(self.c.get("/api/tools/jobs/j1").status_code, 400, "unmapped codes are request errors")
        with mock.patch.object(RUNTIME, "cancel", side_effect=ValueError("bad id")):
            response = self.c.post("/api/tools/jobs/j1/cancel")
        self.assertEqual((response.status_code, response.json()["detail"]["code"]), (400, "invalid_input"))

    def test_jobs_events_stream_and_invoke(self):
        events = [{"status": "running", "observations": [{"seq": 1, "kind": "stdout", "text": "hi"}]},
                  {"status": "succeeded", "observations": []}]
        with mock.patch.object(RUNTIME, "get", return_value={"id": "j1"}), \
                mock.patch.object(RUNTIME, "events", side_effect=lambda *a: events.pop(0) if len(events) > 1 else events[0]):
            self.assertEqual(self.c.get("/api/tools/jobs/j1/events", params={"timeout": 99}).json()["status"], "running")
            events.insert(0, {"status": "running", "observations": [{"seq": 1, "kind": "stdout", "text": "hi"}]})
            with self.c.stream("GET", "/api/tools/jobs/j1/stream") as response:
                frames = [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]
        self.assertEqual([f["type"] for f in frames], ["observation", "done"])
        self.assertEqual(frames[-1]["status"], "succeeded")
        with mock.patch.object(RUNTIME, "run", return_value={"status": "succeeded"}) as run, \
                mock.patch.object(RUNTIME, "submit", return_value={"status": "queued"}) as submit:
            self.assertEqual(self.c.post("/api/tools/x/invoke", json={"args": {"a": 1}}).json(), {"status": "succeeded"})
            grant = run.call_args.args[2]
            self.assertEqual((grant.principal, grant.permissions, grant.max_calls), ("api:ui", ["read"], 1))
            self.assertEqual(self.c.post("/api/tools/x/invoke", json={"wait": False, "permissions": ["compute"]}).json(),
                             {"status": "queued"})
            self.assertEqual(submit.call_args.args[2].permissions, ["compute"])
        with mock.patch.object(RUNTIME, "cancel", return_value={"status": "cancelled"}):
            self.assertEqual(self.c.post("/api/tools/jobs/j1/cancel").json(), {"status": "cancelled"})

    def test_mcp_servers_google_and_clients(self):
        with mock.patch.object(registry, "mcp_servers", return_value=[{"name": "s"}]), \
                mock.patch.object(registry, "add_mcp_server", return_value={"name": "s"}) as add, \
                mock.patch.object(registry, "discover_mcp", return_value={"tools": 2}):
            self.assertEqual(self.c.get("/api/tools/mcp-servers").json(), {"servers": [{"name": "s"}]})
            self.c.post("/api/tools/mcp-servers", json={"name": "s", "url": "http://127.0.0.1:1/mcp"})
            self.assertEqual(add.call_args.args, ("s", "http://127.0.0.1:1/mcp"))
            self.assertEqual(self.c.post("/api/tools/mcp-servers/s/discover").json(), {"tools": 2})
        with mock.patch.multiple(google_mcp, status=mock.Mock(return_value={"ok": 1}), save_settings=mock.Mock(return_value={"saved": 1}),
                                 save_oauth_client=mock.Mock(return_value={"client": 1}), oauth_start=mock.Mock(return_value={"url": "u"}),
                                 oauth_finish=mock.Mock(return_value=None), discover=mock.Mock(return_value={"tools": 1}),
                                 stop_servers=mock.Mock(return_value=2)):
            self.assertEqual(self.c.get("/api/tools/google").json(), {"ok": 1})
            self.assertEqual(self.c.post("/api/tools/google/settings", json={"a": 1}).json(), {"saved": 1})
            self.assertEqual(self.c.post("/api/tools/google/drive/oauth-client", json={"client_id": "i"}).json(), {"client": 1})
            self.assertEqual(self.c.post("/api/tools/google/drive/oauth/start").json(), {"url": "u"})
            self.assertTrue(google_mcp.oauth_start.call_args.args[0].endswith("/api/tools/google/drive/oauth/callback"))
            self.assertEqual(self.c.get("/api/tools/google/drive/oauth/callback", params={"error": "denied"}).status_code, 400)
            self.assertIn("connected", self.c.get("/api/tools/google/drive/oauth/callback", params={"code": "c", "state": "s"}).text)
            self.assertEqual(self.c.post("/api/tools/google/drive/discover").json(), {"tools": 1})
            self.assertEqual(self.c.post("/api/tools/google/stop").json(), {"stopped": 2})
        with mock.patch.multiple(mcp_clients, status=mock.Mock(return_value={"antigravity": {}}),
                                 register_antigravity=mock.Mock(return_value={"registered": True}),
                                 unregister_antigravity=mock.Mock(return_value={"registered": False})):
            self.assertEqual(self.c.get("/api/tools/clients").json(), {"antigravity": {}})
            self.assertEqual(self.c.post("/api/tools/clients/antigravity/register").json(), {"registered": True})
            self.assertTrue(mcp_clients.register_antigravity.call_args.args[0].endswith("/mcp"))
            self.assertEqual(self.c.post("/api/tools/clients/antigravity/unregister").json(), {"registered": False})

    def test_chatgpt_owner_controls(self):
        with mock.patch.multiple(chatgpt_gateway, enable=mock.Mock(return_value={"enabled": True}),
                                 kill_switch=mock.Mock(return_value={"enabled": False}),
                                 refresh_ranges=mock.Mock(return_value={"prefixes": 3}),
                                 approve=mock.Mock(return_value={"approved": "r"}), deny=mock.Mock(return_value={"denied": "r"})):
            self.assertEqual(self.c.post("/api/tools/clients/chatgpt/enable").json(), {"enabled": True})
            self.assertEqual(self.c.post("/api/tools/clients/chatgpt/disable").json(), {"enabled": False})
            self.assertEqual(self.c.post("/api/tools/clients/chatgpt/kill").json(), {"enabled": False})
            self.assertEqual(self.c.post("/api/tools/clients/chatgpt/refresh-ranges").json(), {"prefixes": 3})
            self.assertEqual(self.c.post("/api/tools/clients/chatgpt/approve", json={"request_id": "r"}).json(), {"approved": "r"})
            self.assertEqual(self.c.post("/api/tools/clients/chatgpt/deny", json={"request_id": "r"}).json(), {"denied": "r"})
            self.assertEqual(self.c.post("/api/tools/clients/chatgpt/launch").status_code, 404)

    def test_proposal_lifecycle_routes(self):
        with mock.patch.multiple(proposals, listing=mock.Mock(return_value=[]), propose=mock.Mock(return_value={"id": "t"}),
                                 validate=mock.Mock(return_value={"valid": True}), promote=mock.Mock(return_value={"active": True}),
                                 rollback=mock.Mock(return_value={"version": "1"})):
            self.assertEqual(self.c.get("/api/tools/proposals").json(), {"proposals": []})
            self.c.post("/api/tools/proposals", json={"manifest": {"id": "t"}, "proposer": "p" * 200})
            self.assertEqual(proposals.propose.call_args.kwargs["proposer"], "p" * 80)
            self.assertEqual(self.c.post("/api/tools/proposals/t/2/validate").json(), {"valid": True})
            self.assertEqual(self.c.post("/api/tools/proposals/t/2/promote", json={"approved_by": "owner"}).json(), {"active": True})
            self.assertEqual(self.c.post("/api/tools/t/rollback", json={"to_version": "1", "approved_by": "owner"}).json(), {"version": "1"})
            self.assertEqual(proposals.rollback.call_args.args, ("t", "1", "owner"))


if __name__ == "__main__":
    unittest.main()
