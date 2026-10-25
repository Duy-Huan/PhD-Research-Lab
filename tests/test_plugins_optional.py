"""Unit tests for Optional Plugins catalog and AI-Scientist-v2 optional plugin behavior."""
import unittest
from fastapi.testclient import TestClient
from backend.app import app


class TestPluginsOptionalCatalog(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, base_url="http://localhost:8765")

    def test_plugins_list_contains_optional_catalog(self):
        res = self.client.get("/api/plugins")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("optional_plugins", data)
        self.assertIn("primary_writing_engine", data)
        self.assertEqual(data["primary_writing_engine"], "paperorchestra")

        # Check AI-Scientist-v2 is in optional plugins
        ais = next((p for p in data["optional_plugins"] if p["id"] == "sakanaai-ai-scientist-v2"), None)
        self.assertIsNotNone(ais)
        self.assertEqual(ais["name"], "AI-Scientist-v2")
        self.assertEqual(ais["repo"], "SakanaAI/AI-Scientist-v2")
        self.assertIn("/ais-write", ais["skills"])

    def test_plugins_catalog_endpoint(self):
        res = self.client.get("/api/plugins/catalog")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("optional_plugins", data)
        self.assertEqual(data["primary_writing_engine"], "paperorchestra")
        self.assertTrue(len(data["optional_plugins"]) >= 3)

    def test_ais_writeup_when_not_installed_returns_informative_400(self):
        from unittest.mock import patch
        with patch("backend.plugins.ai_scientist.status", return_value={"installed": False, "url": "https://github.com/SakanaAI/AI-Scientist-v2"}):
            res = self.client.post("/api/paper/ais/writeup", json={"template": "icml"})
            self.assertEqual(res.status_code, 400)
            self.assertIn("optional plugin", res.json()["detail"].lower())
            self.assertIn("paperorchestra", res.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
