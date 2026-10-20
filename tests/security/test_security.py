import _env  # noqa: F401  (must be first)
import json
import unittest
import warnings

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

from backend import telemetry as T  # noqa: E402
from backend.app import app  # noqa: E402

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "t"}}}


class Security(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app)

    def setUp(self):
        _env.fresh_project("sec34")
        _env.config.save_config({"mcp": {"token": "", "rate_limit_per_min": 0, "enabled": True, "expose_sandbox": True}})

    def test_remote_host_rejected_by_default(self):
        self.assertEqual(self.c.post("/mcp", json=INIT, headers={"host": "lab.example.com"}).status_code, 421)

    def test_foreign_origin_rejected(self):
        self.assertEqual(self.c.post("/mcp", json=INIT, headers={"origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(self.c.post("/mcp", json=INIT, headers={"origin": "http://localhost:8765"}).status_code, 200)
        self.assertEqual(self.c.post("/mcp", json=INIT).status_code, 200)  # CLI clients send no Origin

    def test_token_required_when_configured(self):
        _env.config.save_config({"mcp": {"token": "s3cret-token-value"}})
        self.assertEqual(self.c.post("/mcp", json=INIT).status_code, 401)
        self.assertEqual(self.c.post("/mcp", json=INIT, headers={"authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.c.post("/mcp", json=INIT, headers={"authorization": "Bearer s3cret-token-value"}).status_code, 200)
        pub = self.c.get("/api/config").json()
        self.assertNotIn("s3cret-token-value", json.dumps(pub))  # masked in the UI config
        self.assertTrue(pub["mcp"]["has_token"])

    def test_rate_limit(self):
        _env.config.save_config({"mcp": {"rate_limit_per_min": 3}})
        codes = [self.c.post("/mcp", json={"jsonrpc": "2.0", "id": i, "method": "ping"}).status_code for i in range(5)]
        self.assertEqual(codes[:3], [200, 200, 200])
        self.assertEqual(codes[-1], 429)
        from backend import mcp_server
        mcp_server._rl.clear()

    def test_disabled_mcp(self):
        _env.config.save_config({"mcp": {"enabled": False}})
        self.assertEqual(self.c.post("/mcp", json=INIT).status_code, 403)

    def test_malicious_parameters(self):
        r = self.c.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                      "params": {"name": "sandbox_manage_files", "arguments": {"action": "read", "path": "../../config.json"}}}).json()
        self.assertTrue(r["result"]["isError"])
        self.assertEqual(self.c.post("/mcp", content=b"not json", headers={"content-type": "application/json"}).status_code, 400)
        self.assertEqual(self.c.post("/mcp", json="string").status_code, 400)

    def test_telemetry_refuses_content_and_redacts(self):
        with T.span("test.op", agent_id="reviewer", provider="codex") as s:
            s.update(selected_count=3, context_tokens=1200)
            s.update(query="what is our secret method?", prompt="full prompt text", agent_id="has spaces and text")
        rec = T.recent(1, "test.op")[0]
        self.assertEqual(rec["selected_count"], 3)
        self.assertNotIn("query", rec)
        self.assertNotIn("prompt", rec)
        self.assertNotIn("agent_id", rec)  # free text refused even in an allowed field
        try:
            with T.span("test.err"):
                raise ValueError("failed with key sk-abcdefghijklmnopqrstuvwx")
        except ValueError:
            pass
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwx", T.recent(1, "test.err")[0]["error"])
        for s in ("ghp_abcdefghijklmnopqrstuvwxyz0123", "AKIAABCDEFGHIJKLMNOP", "Bearer abcdefghijklmnop.qrstuvwx",
                  "password = hunter2hunter2", "AIzaSyA1234567890abcdefghijklmnopqrstu"):
            self.assertIn("[REDACTED]", T.redact(f"x {s} y"), s)

    def test_gateway_never_logs_credentials_or_prompt(self):
        r = self.c.post("/api/memory/v3/compile", json={"query": "anything", "trace": True})
        self.assertEqual(r.status_code, 200)
        raw = (_env.config.GLOBAL_DIR / "telemetry" / "ops.jsonl").read_text("utf-8")
        self.assertNotIn("anything", raw)


if __name__ == "__main__":
    unittest.main()
