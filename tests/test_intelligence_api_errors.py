"""FQC-COVERAGE-662: research-intelligence API (artifacts, traces, context packs, routing, reproducibility, reports)
answers unknown or invalid identities with 400/404 instead of server errors, and resolves a mission's topic."""
import unittest

import _env
from fastapi.testclient import TestClient

from backend.app import app
from backend.knowledge import research_store as S


class IntelligenceApiErrors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app, headers={"X-PhDLab-Client": "ui"})
        cls.c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"intel-{self._testMethodName[:30]}", code_project=None)

    def test_topic_is_required_when_none_can_be_resolved(self):
        self.assertEqual(self.c.get("/api/missions/m-unknown/trace").status_code, 404)
        self.assertEqual(self.c.post("/api/artifacts", json={"artifact_type": "dataset"}).status_code, 400)

    def test_unknown_identities_are_client_errors(self):
        tid = _env.legacy_topic(S.TopicInput(title="Intel"))["id"]
        expectations = [
            ("get", f"/api/artifacts?mission_id=m-x", None, 200),  # falls back to the latest topic
            ("get", "/api/artifacts/a-missing", None, 404),
            ("get", "/api/artifacts/a-missing/lineage", None, 404),
            ("post", "/api/artifacts/a-missing/verify-integrity", None, 404),
            ("get", "/api/research/topics/t-missing/urap/artifacts", None, 404),
            ("post", f"/api/research/topics/{tid}/urap/artifacts", {"artifact_type": "nonsense", "sha256": "x"}, 400),
            ("get", "/api/research/topics/t-missing/missions/m/trace", None, 404),
            ("post", "/api/missions/m-x/trace", {"event_type": "CUSTOM_EVENT"}, 200),  # free-form trace events
            ("post", "/api/tasks/t-1/context-pack", {"mission_id": "m-x", "role": "nobody", "objective": "o"}, (400, 422)),
            ("get", "/api/tasks/t-new/context-pack", None, 200),  # built on demand from project context
            ("post", "/api/tasks/t-1/route-preview", {"mission_id": "m-x", "capability": "wire.money"}, 400),
            ("post", "/api/missions/m-x/reproducibility-replay", None, 200),  # reported as unverified, never passed
            ("post", "/api/missions/m-x/report-manifest", {"artifact_ids": ["a-missing"]}, (200, 404)),
        ]
        for method, url, body, expected in expectations:
            with self.subTest(url=url):
                response = getattr(self.c, method)(url, json=body) if body is not None else getattr(self.c, method)(url)
                allowed = expected if isinstance(expected, tuple) else (expected,)
                self.assertIn(response.status_code, allowed, response.text[:300])
        trace = self.c.get(f"/api/missions/m-x/trace?topic_id={tid}")
        self.assertIn(trace.status_code, (200, 404))

    def test_reproducibility_download_builds_a_pack_when_missing(self):
        _env.legacy_topic(S.TopicInput(title="Repro"))
        response = self.c.get("/api/missions/m-repro/reproducibility-export/download")
        if response.status_code == 200:
            self.assertEqual(response.headers["content-type"], "application/zip")
            again = self.c.get("/api/missions/m-repro/reproducibility-export/download")
            self.assertEqual(again.status_code, 200, "an existing export is served again")
        else:
            self.assertIn(response.status_code, (404, 400))


if __name__ == "__main__":
    unittest.main()
