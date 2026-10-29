"""FQC-DISCOVERY-PARTIAL-664 (agent/PLAN_6.6.4_L3.md A7): one rate-limited provider no longer fails a mission's discovery.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): OpenAlex answered HTTP 429, the other providers
returned papers, the discovery job ended `partial`, and the mission's paper.discover step failed because only
`completed` was accepted. The step now keeps what was found and names the provider that did not answer; with nothing
found it still fails, naming the errors. Real topic, jobs, mission and the real provider wrapper; only the provider HTTP
calls are replaced."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

import _env
from backend.agent import missions as M
from backend.agent.mission_contracts import MissionSpec, Task
from backend.knowledge import research_store as S, websearch as WS


def too_many(*_a, **_k):
    request = httpx.Request("GET", "https://api.openalex.org/works")
    raise httpx.HTTPStatusError("429", request=request, response=httpx.Response(429, request=request))


ARXIV = [{"title": f"Smoothing filters for noise {i}", "abstract": "Local averaging.", "year": 2021, "source": "arXiv",
          "arxiv_id": f"2101.0000{i}"} for i in range(3)]


class PartialDiscovery(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("partial discovery tests", code_project=None)
        self.tid = _env.legacy_topic(S.TopicInput(title="Denoising", keywords=["smoothing"], sources=["openalex", "arxiv"]))["id"]

    def run_discovery(self):
        spec = MissionSpec(topic_id=self.tid, objective="Find sources", permissions=["network", "workspace_write"],
                           tasks=[Task(id="find", capability="paper.discover", args={"limit": 5})])
        m = M.create(spec)
        M.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Discover sources")
        for _ in range(3):
            asyncio.run(M.tick(m["id"]))
        return M.get(m["id"], self.tid)

    def test_papers_from_the_other_providers_are_kept_and_the_429_is_reported(self):
        with patch.object(WS, "openalex", AsyncMock(side_effect=too_many)), patch.object(WS, "arxiv", AsyncMock(return_value=ARXIV)):
            m = self.run_discovery()
        task = m["tasks"][0]
        self.assertEqual(task["status"], "completed", m["payload"].get("blocking_reason"))
        result = task["payload"]["result"]
        self.assertEqual(len(result["output"]["paper_ids"]), 3)
        self.assertTrue(result["output"]["partial"])
        self.assertIn("openalex: HTTP 429", result["output"]["provider_errors"])
        self.assertIn("openalex: HTTP 429", result["limitations"][0])

    def test_nothing_found_still_fails_and_names_the_errors(self):
        with patch.object(WS, "openalex", AsyncMock(side_effect=too_many)), patch.object(WS, "arxiv", AsyncMock(return_value=[])):
            m = self.run_discovery()
        task = m["tasks"][0]
        self.assertNotEqual(task["status"], "completed")
        self.assertIn("openalex: HTTP 429", str(task["payload"]))

    def test_the_rate_limited_provider_is_asked_once_not_hammered(self):
        openalex = AsyncMock(side_effect=too_many)
        with patch.object(WS, "openalex", openalex), patch.object(WS, "arxiv", AsyncMock(return_value=ARXIV)):
            m = self.run_discovery()
        self.assertEqual(m["tasks"][0]["status"], "completed")
        self.assertEqual(openalex.await_count, 1)  # no hidden retry loop against a 429

    def test_a_complete_discovery_is_not_marked_partial(self):
        with patch.object(WS, "openalex", AsyncMock(return_value=[])), patch.object(WS, "arxiv", AsyncMock(return_value=ARXIV)):
            m = self.run_discovery()
        result = m["tasks"][0]["payload"]["result"]
        self.assertEqual((result["output"]["partial"], result["output"]["provider_errors"], result["limitations"]), (False, [], []))


if __name__ == "__main__":
    unittest.main()
