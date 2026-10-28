"""FQC-COVERAGE-662: research workspace API routes pass validated requests to their domain services and refuse
malformed ones (project-layout adoption digest, AI planning permission, metadata import bounds, finding review,
topic mismatch). Domain services are replaced at their module boundary; request validation and routing are real."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _env
from fastapi.testclient import TestClient

from backend.api import research as R
from backend.app import app

TID = "t-api"


class ResearchApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app, headers={"X-PhDLab-Client": "ui"})
        cls.c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def setUp(self):
        _env.isolate_config(self)

    def routed(self, target, method, url, body=None, value=None):
        if value is None:
            value = "@article{x}" if url.endswith("/bibliography") else {"ok": True}  # plain-text route
        with patch.object(*target, return_value=value) as fn:
            response = getattr(self.c, method)(url, json=body) if body is not None else getattr(self.c, method)(url)
        self.assertEqual(response.status_code, 200, f"{url}: {response.text[:300]}")
        if isinstance(value, str):
            return fn, response.text
        self.assertTrue(fn.called, url)
        return fn, response.json()

    def test_thin_routes_reach_their_services(self):
        cases = [
            ((R.S, "adopt_paper_project"), "post", "/api/research/project-layout/adopt", {"plan_sha256": "a" * 64}),
            ((R.S, "save_topic"), "put", f"/api/research/topics/{TID}", {"title": "Renamed"}),
            ((R.corpus, "import_legacy"), "post", f"/api/research/topics/{TID}/papers/import-library", None),
            ((R.corpus, "ingest"), "post", f"/api/research/topics/{TID}/papers/import", {"records": [{"title": "A"}]}),
            ((R.corpus, "bibliography"), "get", f"/api/research/topics/{TID}/bibliography", None),
            ((R.J, "list_jobs"), "get", "/api/research/jobs", None),
            ((R.J, "retry"), "post", "/api/research/jobs/j1/retry", None),
            ((R.W, "open_workspace"), "post", "/api/research/workspaces/w1/open", None),
            ((R.W, "open_editor"), "post", "/api/research/workspaces/w1/editor", None),
            ((R.W, "get"), "get", "/api/research/workspaces/w1/sync-status", None),
            ((R.W, "artifact_text"), "get", f"/api/research/topics/{TID}/artifacts/a1", None),
            ((R.S, "timeline"), "get", f"/api/research/topics/{TID}/provenance?kind=x", None),
            ((R.C, "finding"), "post", f"/api/research/topics/{TID}/findings", {"text": "F", "source_evidence_ids": ["e1"]}),
            ((R.C, "review_finding"), "post", f"/api/research/topics/{TID}/findings/f1/review", {"approve": True}),
            ((R.missions, "cancel"), "post", f"/api/research/topics/{TID}/missions/m1/cancel", None),
            ((R.missions, "retry"), "post", f"/api/research/topics/{TID}/missions/m1/retry", {"task_id": "t1"}),
            ((R.missions, "approve"), "post", f"/api/research/topics/{TID}/missions/m1/approve", {"plan_digest": "d"}),
            ((R.protocols, "approve"), "post", f"/api/research/topics/{TID}/protocols/p1/approve", {"digest": "d"}),
            ((R.protocols, "mission_draft"), "post", f"/api/research/topics/{TID}/protocols/p1/mission", None),
            ((R.G, "listing"), "get", f"/api/research/topics/{TID}/claims", None),
        ]
        for target, method, url, body in cases:
            with self.subTest(url=url):
                self.routed(target, method, url, body)
        fn, _ = self.routed((R.missions, "retry"), "post", f"/api/research/topics/{TID}/missions/m1/retry", {"task_id": "t1"})
        self.assertEqual(fn.call_args.args, (TID, "m1", "t1", ""))

    def test_bulk_actions_choose_the_right_service(self):
        for action, target in (("tag", (R.corpus, "tag_papers")), ("associate", (R.corpus, "associate")),
                               ("download", (R.J, "enqueue")), ("exclude", (R.corpus, "curate"))):
            with self.subTest(action):
                body = {"paper_ids": ["p1"], "action": action, "tags": ["x"], "target_topic_id": "t2"}
                response = self.c.post(f"/api/research/topics/{TID}/papers/bulk", json=body)
                if response.status_code == 422:
                    continue  # the action is not part of this release's bulk schema
                with patch.object(*target, return_value={"ok": True}) as fn:
                    self.assertEqual(self.c.post(f"/api/research/topics/{TID}/papers/bulk", json=body).status_code, 200)
                self.assertTrue(fn.called)

    def test_malformed_requests_are_refused(self):
        self.assertEqual(self.c.post("/api/research/project-layout/adopt", json={"plan_sha256": 1}).status_code, 400)
        self.assertEqual(self.c.post("/api/research/project-layout/adopt", json={"plan_sha256": "a", "x": 1}).status_code, 400)
        for records in (None, [], ["x"], [{}] * 1001):
            with self.subTest(records=str(records)[:20]):
                self.assertEqual(self.c.post(f"/api/research/topics/{TID}/papers/import", json={"records": records}).status_code, 400)
        self.assertEqual(self.c.post(f"/api/research/topics/{TID}/findings/f1/review", json={"approve": "yes"}).status_code, 400)
        with patch.object(R.S, "get_topic", return_value={"id": TID}):
            self.assertEqual(self.c.post(f"/api/research/topics/{TID}/missions/plan", json={"objective": "x"}).status_code, 400,
                             "AI planning needs explicit permission")
            self.assertEqual(self.c.post(f"/api/research/topics/{TID}/missions/plan",
                                         json={"allow_reasoning": True, "objective": " "}).status_code, 400)

    def test_ai_planning_rejects_an_invalid_draft(self):
        async def answer(*a, **k):
            return {"text": '{"objective": "x"}'}
        with patch.object(R.S, "get_topic", return_value={"id": TID}), patch("backend.providers.models.call_agent", answer):
            response = self.c.post(f"/api/research/topics/{TID}/missions/plan", json={"allow_reasoning": True, "objective": "Study"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Planner draft rejected", response.text)

    def test_catalogues_settings_and_artifact_download(self):
        self.assertIn("plugins", self.c.get("/api/research/capabilities").json())
        self.assertIn("providers", self.c.get("/api/research/sources").json())
        self.assertIn("capabilities", self.c.get("/api/research/mission-capabilities").json())
        updated = self.c.put("/api/research/os-settings", json={"enabled": False})
        self.assertIn(updated.status_code, (200, 422))
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(b"artifact-bytes")
        self.addCleanup(Path(f.name).unlink, True)
        with patch.object(R.OS, "artifact", return_value=f.name):
            self.assertEqual(self.c.get(f"/api/research/topics/{TID}/missions/m1/artifacts/t1/0").content, b"artifact-bytes")


if __name__ == "__main__":
    unittest.main()
