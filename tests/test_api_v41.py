"""v4.1 HTTP API: lifecycle status / unload / release, CLI space, model analysis, HPO validation, workflow registry,
runs (create, decide, pause/resume/cancel, events, SSE, export) — through FastAPI's TestClient (real app, real routes)."""
import _env  # noqa: F401  (must be first)
import json
import time
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend import config, model_lifecycle as LC
from backend.app import app
from backend.workflow import ORCH, harness as HA
from test_model_lifecycle import Fakes
from test_workflow_engine import FakeHarness


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cm = TestClient(app)
        cls.c = cls.cm.__enter__()  # runs the lifespan: memory worker + lifecycle reaper

    @classmethod
    def tearDownClass(cls):
        cls.cm.__exit__(None, None, None)

    def setUp(self):
        _env.fresh_project("api41-" + self._testMethodName[:20])
        ORCH.reset()
        HA.use(FakeHarness())
        LC.reset()

    def tearDown(self):
        HA.use(None)

    def test_lifecycle_endpoints(self):
        with Fakes(ollama=["qwen2.5:7b"], lm=["lm-x"]):
            st = self.c.get("/api/lifecycle/status").json()
            self.assertEqual({m["model"] for m in st["local"]["models"]}, {"qwen2.5:7b", "lm-x"})
            r = self.c.post("/api/lifecycle/unload", json={"engine": "ollama", "model": "qwen2.5:7b"}).json()
            self.assertEqual(r["unloaded"], ["qwen2.5:7b"])
            r = self.c.post("/api/lifecycle/unload", json={}).json()
            self.assertEqual(r["unloaded"], ["lmstudio:lm-x"])
        self.assertEqual(self.c.post("/api/lifecycle/unload", json={"engine": "vllm"}).status_code, 400)
        self.assertEqual(self.c.post("/api/lifecycle/release", json={"key": "nope"}).status_code, 404)
        r = LC.Resource("cli:codex:gs-00000077", "cli", "codex", "gs-00000077", leases=1)
        LC._res[r.key] = r
        self.assertEqual(self.c.post("/api/lifecycle/release", json={"key": r.key}).status_code, 409)
        r.leases = 0
        self.assertTrue(self.c.post("/api/lifecycle/release", json={"key": r.key}).json()["ok"])
        cfg = self.c.post("/api/config", json={"lifecycle": {"local_background": "keep_loaded", "local_idle_min": 3}}).json()
        self.assertEqual(cfg["lifecycle"]["local_background"], "keep_loaded")
        self.assertEqual(self.c.get("/api/config").json()["lifecycle"]["local_idle_min"], 3)

    def test_cli_space(self):
        d = self.c.get("/api/cli-space").json()
        self.assertTrue(d["isolation"]["codex"]["assisted"]["enforced"])
        self.assertFalse(d["isolation"]["gemini_cli"]["assisted"]["supported"])
        self.assertIn("removed", self.c.post("/api/cli-space/prune").json())

    def test_model_and_hpo_tools(self):
        spec = {"input_shape": [3, 32, 32], "layers": [{"type": "conv2d", "out": 8, "k": 3, "padding": 1}]}
        r = self.c.post("/api/model/analyze", json={"spec": spec, "batch_size": 4}).json()
        self.assertEqual(r["report"]["params"]["label"], "ESTIMATED")
        self.assertIn("feasible", r["feasibility"])
        self.assertEqual(self.c.post("/api/model/analyze", json={"spec": {}}).status_code, 400)
        config.save_config({"features": {"model_intelligence": False}})
        self.assertEqual(self.c.post("/api/model/analyze", json={"spec": spec}).status_code, 403)
        config.save_config({"features": {"model_intelligence": True}})
        self.assertEqual([a["id"] for a in self.c.get("/api/model/adapters").json()["adapters"]], ["spec", "pytorch", "onnx"])
        v = self.c.post("/api/hpo/validate", json={"search_space": {"x": {"type": "float", "low": 0, "high": 1}},
                                                   "objectives": [{"name": "loss", "direction": "minimize"}]}).json()
        self.assertTrue(v["valid"])
        self.assertEqual(self.c.post("/api/hpo/validate", json={"max_trials": "many"}).status_code, 400)

    def test_registry(self):
        t = self.c.get("/api/workflows/templates").json()
        self.assertEqual(len([x for x in t["templates"] if x["builtin"]]), 11)
        self.assertIn("hpo.run", {s["name"] for s in t["step_types"]})
        self.assertEqual(self.c.get("/api/workflows/templates/hpo").json()["id"], "hpo")
        self.assertEqual(self.c.get("/api/workflows/templates/nope").status_code, 404)
        d = {"id": "api_flow", "version": 1, "steps": [{"id": "a", "type": "research.state"}]}
        self.assertTrue(self.c.post("/api/workflows/validate", json={"definition": d}).json()["valid"])
        self.assertFalse(self.c.post("/api/workflows/validate", json={"id": "x"}).json()["valid"])
        self.assertEqual(self.c.post("/api/workflows/templates", json={"definition": d}).json()["id"], "api_flow")
        self.assertEqual(self.c.post("/api/workflows/templates", json={"definition": d}).status_code, 400)  # version exists
        self.assertEqual(self.c.post("/api/workflows/templates", json={"definition": {"id": "x"}}).status_code, 400)
        self.assertEqual(self.c.delete("/api/workflows/templates/api_flow/1").json(), {"deleted": True})
        self.assertEqual(self.c.delete("/api/workflows/templates/api_flow/1").status_code, 404)
        self.assertEqual(self.c.delete("/api/workflows/templates/hpo/1").status_code, 400)

    def test_run_lifecycle_over_http(self):
        r = self.c.post("/api/workflows/runs", json={"workflow_id": "hpo", "inputs": {"max_trials": 4}}).json()
        rid = r["id"]
        for _ in range(300):
            r = self.c.get(f"/api/workflows/runs/{rid}").json()
            if r["status"] == "WAITING_FOR_APPROVAL":
                break
            time.sleep(0.02)
        self.assertEqual(r["pending_approvals"][0]["step_id"], "run")
        self.assertEqual(self.c.post(f"/api/workflows/runs/{rid}/steps/run/decision", json={"decision": "nope"}).status_code, 400)
        self.c.post(f"/api/workflows/runs/{rid}/steps/run/decision", json={"decision": "approve"})
        for _ in range(500):
            r = self.c.get(f"/api/workflows/runs/{rid}").json()
            if r["status"] in ("SUCCEEDED", "FAILED"):
                break
            time.sleep(0.02)
        self.assertEqual(r["status"], "SUCCEEDED", r["error"])
        ev = self.c.get(f"/api/workflows/runs/{rid}/events?after=0").json()["events"]
        self.assertEqual(ev[0]["type"], "workflow_created")
        with self.c.stream("GET", f"/api/workflows/runs/{rid}/stream?after=0") as s:
            lines = [l for l in s.iter_lines() if l.startswith("data:")]
        self.assertEqual(json.loads(lines[-1][5:])["type"], "end")
        self.assertEqual(len(lines) - 1, len(ev))
        exp = self.c.get(f"/api/workflows/runs/{rid}/export").json()
        self.assertEqual(exp["definition"]["id"], "hpo")
        sid = r["outputs"]["study_id"]
        self.assertEqual(self.c.get(f"/api/workflows/studies/{sid}").json()["summary"]["n_trials"], 4)
        self.assertTrue(self.c.get("/api/workflows/studies").json()["studies"])
        self.assertEqual(self.c.get("/api/workflows/studies/study-00000000").status_code, 404)
        self.assertTrue(self.c.get("/api/workflows/runs").json()["runs"])
        self.assertEqual(self.c.post(f"/api/workflows/runs/{rid}/cancel").status_code, 400)  # already finished

    def test_pause_resume_cancel_and_errors(self):
        r = self.c.post("/api/workflows/runs", json={"workflow_id": "hpo", "start": False, "inputs": {"max_trials": 2},
                                                     "overrides": {"execution_mode": "bounded"}}).json()
        self.assertEqual(r["status"], "READY")
        rid = r["id"]
        self.assertEqual(self.c.post(f"/api/workflows/runs/{rid}/start").json()["status"], "RUNNING")
        self.assertIn(self.c.post(f"/api/workflows/runs/{rid}/pause").json()["status"], ("RUNNING", "PAUSED", "WAITING_FOR_APPROVAL"))
        self.assertEqual(self.c.post(f"/api/workflows/runs/{rid}/cancel").json()["status"], "CANCELLED")
        self.assertEqual(self.c.post(f"/api/workflows/runs/{rid}/explode").status_code, 404)
        self.assertEqual(self.c.post(f"/api/workflows/runs/{rid}/resume").status_code, 400)
        self.assertEqual(self.c.get("/api/workflows/runs/wf-ffffffffff").status_code, 404)
        self.assertEqual(self.c.get("/api/workflows/runs/wf-ffffffffff/events").status_code, 404)
        self.assertEqual(self.c.get("/api/workflows/runs/wf-ffffffffff/stream").status_code, 404)
        self.assertEqual(self.c.get("/api/workflows/runs/wf-ffffffffff/export").status_code, 404)
        self.assertEqual(self.c.post("/api/workflows/runs", json={"workflow_id": "ghost"}).status_code, 400)
        self.assertEqual(self.c.post("/api/workflows/runs/wf-ffffffffff/steps/x/decision", json={"decision": "approve"}).status_code, 404)
        with self.c.stream("GET", f"/api/workflows/runs/{rid}/stream?once=1") as s:
            self.assertTrue(any('"end"' in l for l in s.iter_lines()))

    def test_live_stream_waits_for_changes(self):
        from test_workflow_engine import wf
        r = self.c.post("/api/workflows/runs", json={"definition": wf([{"id": "a", "type": "test.sleep", "params": {"s": 0.3}}], outputs={})}).json()
        with self.c.stream("GET", f"/api/workflows/runs/{r['id']}/stream") as s:
            types = [json.loads(l[5:])["type"] for l in s.iter_lines() if l.startswith("data:")]
        self.assertEqual(types[-2:], ["workflow_completed", "end"])

    def test_page_ships_the_v41_ui(self):
        html = self.c.get("/").text
        for needle in ('data-tab="workflows"', "/app/workflows.js?v=4.1.0", "/app/lifecycle.js?v=4.1.0", "/app/wfcore.js?v=4.1.0",
                       "/app/v41.css?v=4.1.0", 'id="tab-workflows"'):
            self.assertIn(needle, html)
        for f in ("workflows.js", "lifecycle.js", "wfcore.js", "v41.css"):
            self.assertEqual(self.c.get(f"/app/{f}").status_code, 200)

    def test_gateway_profile_over_http(self):
        from backend.gateway import connectors as C
        from providers.fakes import fake
        with mock.patch.dict(C.CONNECTORS, {"gemini_cli": fake("gemini_cli")}):
            r = self.c.post("/api/gateway/requests", json={"query": "q", "provider": "gemini_cli", "profile": "assisted"})
            self.assertEqual(r.status_code, 400)
            r = self.c.post("/api/gateway/requests", json={"query": "q", "provider": "gemini_cli", "profile": "review"}).json()
            self.assertEqual(r["profile"], "review")
            cmp = self.c.post("/api/gateway/compare", json={"query": "q", "providers": ["gemini_cli", "codex"], "profile": "assisted"}).json()
            self.assertTrue(cmp["requests"])


if __name__ == "__main__":
    unittest.main()
