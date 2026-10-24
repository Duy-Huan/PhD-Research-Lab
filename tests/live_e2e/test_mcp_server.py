"""PhD Lab as MCP Server Test Suite.

Verifies:
  - JSON-RPC 2.0 handshake (initialize, capability negotiation, protocol version)
  - tools/list schema and exposed research/sandbox tools
  - tools/call execution with session grants
  - Security guard: non-local Origin rejection and session tracking
"""
import unittest

from tests.live_e2e.conftest_or_setup import configure_live_phi4
from backend.providers import mcp_server as S


class TestMCPServer(unittest.TestCase):
    def setUp(self):
        configure_live_phi4()

    def test_mcp_server_initialize_handshake(self):
        """Verify initialize handshake negotiates capabilities and protocol version."""
        meta = {}
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "test-live-harness", "version": "1.0.0"}
            }
        }
        resp = S.handle(req, meta=meta)
        self.assertIsNotNone(resp)
        self.assertEqual(resp["id"], 1)
        res = resp["result"]
        self.assertEqual(res["protocolVersion"], "2025-06-18")
        self.assertEqual(res["serverInfo"]["name"], "phd-research-lab")
        self.assertIn("tools", res["capabilities"])
        self.assertTrue(meta.get("session_id", "").startswith("mcp-"))

    def test_mcp_server_tools_list(self):
        """Verify tools/list exposes research and sandbox tools with inputSchema."""
        req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        resp = S.handle(req)
        self.assertIsNotNone(resp)
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("sandbox_get_metrics", tool_names)
        self.assertIn("sandbox_run_code", tool_names)
        for t in tools:
            self.assertIn("inputSchema", t)

    def test_mcp_server_tools_call_metrics(self):
        """Verify tools/call for sandbox_get_metrics returns structured text."""
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "sandbox_get_metrics", "arguments": {}}
        }
        resp = S.handle(req)
        self.assertIsNotNone(resp)
        self.assertIn("content", resp["result"])
        self.assertIsInstance(resp["result"]["content"], list)

    def test_mcp_server_guard_origin_security(self):
        """Security guard: DNS rebinding defense rejects remote Origin."""
        bad_headers = {"host": "localhost:8000", "origin": "http://malicious-attacker-site.com"}
        code, reason = S.guard(bad_headers, "127.0.0.1")
        self.assertEqual(code, 403)
        self.assertIn("Origin", reason)

        # Localhost origin allowed
        good_headers = {"host": "localhost:8000", "origin": "http://localhost:8000"}
        code_ok, _ = S.guard(good_headers, "127.0.0.1")
        self.assertEqual(code_ok, 0)


if __name__ == "__main__":
    unittest.main()
