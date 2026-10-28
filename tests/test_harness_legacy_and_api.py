"""FQC-COVERAGE-662: Harness workflow storage, the legacy benchmark harness (never invents results) and the
/api/harness routes for agents, workflow CRUD, execution and debugger actions, on the real app and project files."""
import json
import unittest
from unittest.mock import patch

import _env
from fastapi.testclient import TestClient

from backend.app import app
from backend.execution import harness as H


def chain(*tools, edges=None):
    nodes = [{"id": f"n{i}", "data": {"tool": t, "label": t}} for i, t in enumerate(tools)]
    edges = edges if edges is not None else [{"source": f"n{i}", "target": f"n{i + 1}"} for i in range(len(tools) - 1)]
    return {"id": "wf-legacy", "name": "Legacy", "nodes": nodes, "edges": edges}


class LegacyHarness(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"harness-{self._testMethodName[:28]}", code_project=None)

    def test_invalid_graphs_fail_without_running(self):
        for graph in (chain(), chain("phdlab_research_harness", edges=[{"source": "n0", "target": "ghost"}]),
                      chain("phdlab_research_harness", "ragas", edges=[{"source": "n0", "target": "n1"}, {"source": "n1", "target": "n0"}])):
            with self.subTest(graph=graph["edges"]):
                report = H.execute_workflow(graph)
                self.assertEqual((report["status"], report["passed"]), ("failed", False))
                self.assertIn("no cycles", report["error"])

    def test_known_adapters_are_blocked_and_downstream_is_blocked_too(self):
        report = H.execute_workflow(chain("ragas", "unknown_tool"), "topic-1")
        first, second = report["node_results"]["n0"], report["node_results"]["n1"]
        self.assertEqual((first["status"], first["execution_mode"], first["metrics"]), ("blocked", "NOT_EXECUTED", {}))
        self.assertEqual(second["status"], "blocked", "an upstream adapter that did not run blocks its dependants")
        self.assertEqual((report["status"], report["passed"]), ("blocked", False))
        alone = H.execute_workflow(chain("not_a_harness"))
        self.assertEqual(alone["node_results"]["n0"]["status"], "unsupported")
        self.assertEqual(alone["status"], "failed")
        self.assertEqual(H.get_execution(report["execution_id"])["workflow_id"], "wf-legacy")
        self.assertEqual(len(H.list_executions("wf-legacy")), 2)
        self.assertIsNone(H.get_execution("exec-missing"))

    def test_adapter_detection_covers_every_catalog_entry(self):
        with patch("shutil.which", return_value=None), patch("importlib.util.find_spec", return_value=None):
            detected = {tool: H._is_tool_available(tool) for tool in
                        ("lm_evaluation_harness", "inspect_ai", "ragas", "promptfoo", "swe_bench", "pytest_harness", "other")}
        self.assertEqual(detected, {"lm_evaluation_harness": False, "inspect_ai": False, "ragas": False, "promptfoo": False,
                                    "swe_bench": False, "pytest_harness": False, "other": False})
        self.assertTrue(H._is_tool_available("phdlab_research_harness"))

    def test_storage_survives_damaged_files(self):
        saved = H.save_workflow({"name": "Mine", "topic_id": "t1", "nodes": [], "edges": []})
        self.assertEqual(H.get_workflow(saved["id"])["name"], "Mine")
        self.assertIn(saved["id"], [w["id"] for w in H.list_workflows("t1")])
        self.assertNotIn(saved["id"], [w["id"] for w in H.list_workflows("t2")])
        self.assertTrue(H.delete_workflow(saved["id"]))
        self.assertFalse(H.delete_workflow(saved["id"]))
        for damaged in ("{not json", json.dumps({"a": 1})):
            H._workflows_file().write_text(damaged, "utf-8")
            H._executions_file().write_text(damaged, "utf-8")
            self.assertEqual([w["id"] for w in H.list_workflows()], [w["id"] for w in H._get_preset_workflows()])
            self.assertFalse(H.delete_workflow("x"))
            self.assertEqual(H.list_executions(), [])
            self.assertEqual(H.save_workflow({"id": "fresh"})["id"], "fresh")
        H._executions_file().write_text("{bad", "utf-8")
        H.execute_workflow(chain("phdlab_research_harness"))
        self.assertEqual(len(H.list_executions()), 1, "a damaged history is replaced, not appended to")


class HarnessApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = TestClient(app, headers={"X-PhDLab-Client": "ui"})
        cls.c.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.c.__exit__(None, None, None)

    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"harness-api-{self._testMethodName[:24]}", code_project=None)

    def test_agents_team_and_architect(self):
        saved = self.c.post("/api/harness/agents", json={"name": "Scout", "role": "literature"})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertIn("Scout", json.dumps(self.c.get("/api/harness/agents").json()))
        self.assertIn("team", self.c.post("/api/harness/architect/team", json={"objective": "Survey denoising"}).json())
        self.assertEqual(self.c.post("/api/harness/architect/generate", json={"objective": " "}).status_code, 400)
        generated = self.c.post("/api/harness/architect/generate", json={"objective": "Benchmark MRI denoisers"})
        self.assertEqual(generated.status_code, 200)
        self.assertIn("nodes", generated.json())

    def test_workflow_crud_and_templates(self):
        listed = self.c.get("/api/harness/workflows").json()["workflows"]
        template = next(w for w in listed if w.get("id"))
        self.assertEqual(self.c.get(f"/api/harness/workflows/{template['id']}").json()["id"], template["id"])
        self.assertEqual(self.c.get("/api/harness/workflows/none-such").status_code, 404)
        created = self.c.post("/api/harness/workflows", json={"name": "Mine", "nodes": [], "edges": []}).json()
        updated = self.c.put(f"/api/harness/workflows/{created['id']}", json={"name": "Renamed"}).json()
        self.assertEqual((updated["id"], updated["name"]), (created["id"], "Renamed"))
        self.assertTrue(self.c.delete(f"/api/harness/workflows/{created['id']}").json()["ok"])
        self.assertEqual(self.c.delete(f"/api/harness/workflows/{created['id']}").status_code, 404)

    def test_execution_routes_and_debugger_actions(self):
        legacy = self.c.post("/api/harness/execute", json={"workflow": {"id": "legacy", "edges": []}}).json()
        self.assertEqual(legacy["status"], "failed", "a legacy graph without nodes never runs")
        legacy = self.c.post("/api/harness/execute", json={"workflow": {"id": "legacy2", "nodes": "x"}}).json()
        self.assertEqual(legacy["status"], "failed", "a malformed graph is reported, never a server error")
        self.assertEqual(self.c.get(f"/api/harness/executions/{legacy['execution_id']}").status_code, 404, "invalid graphs are not kept")
        legacy = H.execute_workflow(chain("phdlab_research_harness"))  # only stored legacy history is served
        self.assertEqual(self.c.get(f"/api/harness/executions/{legacy['execution_id']}").json()["workflow_id"], "wf-legacy")
        self.assertEqual(self.c.get("/api/harness/executions/exec-nope").status_code, 404)
        self.assertEqual(self.c.post("/api/harness/execute/action", json={"execution_id": "nope"}).status_code, 404)
        record = {"execution_id": "e1", "status": "awaiting_approval", "node_statuses": [{"node_id": "gate", "status": "waiting"}]}
        saved = []
        with patch("backend.execution.workflow_runtime.get_execution_record", side_effect=lambda eid: json.loads(json.dumps(record))), \
                patch("backend.execution.workflow_runtime.save_execution_record", side_effect=saved.append), \
                patch("backend.execution.workflow_runtime.list_all_executions", return_value=[{"execution_id": "e1"}]):
            approved = self.c.post("/api/harness/execute/action", json={"execution_id": "e1", "action": "approve", "node_id": "gate",
                                                                       "feedback": "ok"}).json()
            self.assertEqual(approved["execution"]["node_statuses"][0]["status"], "completed")
            rejected = self.c.post("/api/harness/execute/action", json={"execution_id": "e1", "action": "reject", "node_id": "gate"}).json()
            self.assertEqual(rejected["execution"]["status"], "failed")
            cancelled = self.c.post("/api/harness/execute/action", json={"execution_id": "e1", "action": "cancel"}).json()
            self.assertEqual(cancelled["execution"]["status"], "cancelled")
            self.assertEqual(self.c.post("/api/harness/execute/action", json={"execution_id": "e1", "action": "peek"}).json(),
                             {"ok": True, "status": "awaiting_approval"})
            ids = [e["execution_id"] for e in self.c.get("/api/harness/executions").json()["executions"]]
        self.assertEqual(len(saved), 3)
        self.assertEqual(ids[0], "e1")
        self.assertIn(legacy["execution_id"], ids, "legacy history is merged after modern executions")


if __name__ == "__main__":
    unittest.main()
