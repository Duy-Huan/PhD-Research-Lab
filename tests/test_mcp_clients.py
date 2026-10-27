"""FQC-PROVIDER-POOL-661 (CLIENTS): register PhD Lab in Antigravity's documented MCP config, safely.

REAL_LOCAL file operations on a temporary config path (the researcher's real ~/.gemini file is never touched)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _env

try:
    from backend.tools import mcp_clients as C
    from backend.tools.spec import ToolError
    MISSING = None
except ImportError as missing:  # RED before implementation
    MISSING = missing


class AntigravityRegistration(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING
        _env.isolate_config(self)
        folder = Path(tempfile.mkdtemp(prefix="phdlab-agy-"))
        self.path = folder / ".gemini" / "config" / "mcp_config.json"
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        patcher = patch.object(C, "antigravity_config", return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_register_merges_preserves_other_servers_backs_up_and_unregisters_only_ours(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("")  # Antigravity creates an empty file
        out = C.register_antigravity("http://127.0.0.1:8765/mcp")
        self.assertEqual(out["backup"], "", "nothing to back up for an empty file")
        data = json.loads(self.path.read_text())
        self.assertEqual(data["mcpServers"]["phd-research-lab"]["serverUrl"], "http://127.0.0.1:8765/mcp")
        self.assertNotIn("headers", data["mcpServers"]["phd-research-lab"])
        data["mcpServers"]["other"] = {"command": "node", "args": ["x.js"]}
        self.path.write_text(json.dumps(data))
        _env.config.save_config({"mcp": {"token": "local-secret"}})
        out = C.register_antigravity("http://127.0.0.1:9000/mcp")
        self.assertTrue(Path(out["backup"]).is_file())
        data = json.loads(self.path.read_text())
        self.assertEqual(data["mcpServers"]["other"]["command"], "node", "other servers preserved")
        self.assertEqual(data["mcpServers"]["phd-research-lab"]["headers"]["Authorization"], "Bearer local-secret")
        self.assertTrue(C.status()["antigravity"]["registered"])
        self.assertTrue(C.unregister_antigravity()["removed"])
        data = json.loads(self.path.read_text())
        self.assertEqual(list(data["mcpServers"]), ["other"])

    def test_invalid_existing_file_and_non_local_urls_are_refused(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{ not json")
        with self.assertRaises(ToolError):
            C.register_antigravity("http://127.0.0.1:8765/mcp")
        self.assertEqual(self.path.read_text(), "{ not json", "never overwritten")
        self.assertIn("not valid JSON", C.status()["antigravity"]["error"])
        for bad in ("https://evil.example.com/mcp", "http://127.0.0.1/mcp", "http://127.0.0.1:8765/other", "http://10.0.0.2:8765/mcp"):
            with self.subTest(bad=bad), self.assertRaises(ToolError):
                C.register_antigravity(bad)


if __name__ == "__main__":
    unittest.main()
