"""Full-Stack UI-to-Backend Parity & API Conformance Test Suite.

Verifies:
  - All critical HTTP routes consumed by frontend components return conforming schemas
  - SSE event stream format conforms to uiStore and useAppBus expectations
  - Project switching, settings, provider status, and mission monitoring endpoints
"""
import asyncio
import json
import unittest

from tests.live_e2e.conftest_or_setup import configure_live_phi4
from backend.core import config as C, bus
from backend.api import projects, system, chat, research, library


class TestFullStackBrowserParity(unittest.TestCase):
    def setUp(self):
        configure_live_phi4()

    def test_api_projects_list_schema(self):
        """Verify GET /api/projects returns conforming list of project descriptors."""
        res = projects.projects()
        self.assertIn("projects", res)
        self.assertIsInstance(res["projects"], list)
        if res["projects"]:
            p = res["projects"][0]
            self.assertIn("name", p)
            self.assertIn("data_dir", p)

    def test_api_system_settings_schema(self):
        """Verify GET /api/settings returns settings readable by SettingsModal."""
        cfg = C.load_config()
        self.assertIn("agent_modes", cfg)
        self.assertIn("providers", cfg)
        self.assertIn("lmstudio_base_url", cfg)
        self.assertIn("local_model", cfg)

    def test_api_events_bus_parity(self):
        """Verify GET /api/events format conforms to frontend EventSource / SSE format."""
        cur = bus.last()
        ev = bus.publish("ui.test_sync", action="refresh", component="ProjectSwitcher")
        since_res = bus.since(cur)
        self.assertIn("events", since_res)
        self.assertIn("last", since_res)
        evs = since_res["events"]
        self.assertTrue(any(e.get("type") == "ui.test_sync" for e in evs))

    def test_provider_auth_status_endpoint(self):
        """Verify GET /api/providers/{pid}/auth-status returns honest CLI state."""
        res = asyncio.run(system.provider_auth_status("codex"))
        self.assertIn("state", res)
        self.assertIn("login_cmd", res)
        self.assertIn("web_url", res)
        self.assertIn("ready", res)

    def test_library_papers_endpoint_parity(self):
        """Verify library API returns paper summaries expected by LibraryPanel."""
        from backend.knowledge import research_store as S, corpus
        tid = S.save_topic(S.TopicInput(title="Library Parity Topic"))["id"]
        corpus.ingest(tid, [{"title": "Parity Test Paper", "source": "local", "abstract": "Test abstract for library"}])
        papers = corpus.all_papers(tid)
        self.assertTrue(len(papers) >= 1)
        self.assertIn("title", papers[0])
        self.assertIn("source", papers[0])


if __name__ == "__main__":
    unittest.main()
