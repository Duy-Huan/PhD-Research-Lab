import _env  # noqa: F401  (must be first)
import json
import unittest
import warnings

warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient  # noqa: E402

from backend.core import telemetry as T  # noqa: E402
from backend.app import app  # noqa: E402

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "t"}}}


class Security(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app)

    def setUp(self):
        _env.fresh_project("sec34")
        _env.config.save_config({"mcp": {"token": "", "rate_limit_per_min": 0, "enabled": True, "expose_sandbox": True}})
        self.addCleanup(_env.config.save_config, {"mcp": {"token": "", "rate_limit_per_min": 240}})

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
        from backend.providers import mcp_server
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




if __name__ == "__main__":
    unittest.main()
