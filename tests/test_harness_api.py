import unittest
import _env  # noqa: F401
from fastapi.testclient import TestClient
from backend.app import app
from backend.execution import harness as H


class TestHarnessAPI(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(app)

    def test_tools_catalog(self):
        resp = self.c.get("/api/harness/tools")
        self.assertEqual(resp.status_code, 200)
        tools = resp.json()["tools"]
        tool_ids = {t["id"] for t in tools}
        self.assertIn("lm_evaluation_harness", tool_ids)
        self.assertIn("inspect_ai", tool_ids)
        self.assertIn("promptfoo", tool_ids)
        self.assertIn("ragas", tool_ids)
        self.assertIn("swe_bench", tool_ids)
        self.assertIn("pytest_harness", tool_ids)
        self.assertIn("phdlab_research_harness", tool_ids)

    def test_workflow_crud_and_execute(self):
        # 1. List presets
        resp = self.c.get("/api/harness/workflows")
        self.assertEqual(resp.status_code, 200)
        workflows = resp.json()["workflows"]
        self.assertGreaterEqual(len(workflows), 3)

        # 2. Create custom workflow
        custom_wf = {
            "name": "Custom Test Drag-Drop Pipeline",
            "description": "Integration pipeline with LM-Eval and Pytest",
            "nodes": [
                {
                    "id": "node-1",
                    "type": "harnessNode",
                    "data": {
                        "label": "LM Evaluation",
                        "tool": "lm_evaluation_harness",
                        "params": {"tasks": "gsm8k", "min_pass_score": 0.70},
                    },
                },
                {
                    "id": "node-2",
                    "type": "harnessNode",
                    "data": {
                        "label": "Pytest Gate",
                        "tool": "pytest_harness",
                        "params": {"min_coverage_pct": 80.0},
                    },
                },
            ],
            "edges": [{"id": "e1-2", "source": "node-1", "target": "node-2"}],
        }
        res_create = self.c.post("/api/harness/workflows", json=custom_wf)
        self.assertEqual(res_create.status_code, 200)
        saved = res_create.json()
        wid = saved["id"]
        self.assertTrue(wid.startswith("hw-"))

        # 3. Retrieve single
        res_get = self.c.get(f"/api/harness/workflows/{wid}")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["name"], "Custom Test Drag-Drop Pipeline")

        # 4. Update workflow
        res_update = self.c.put(f"/api/harness/workflows/{wid}", json={"name": "Updated Pipeline", "nodes": saved["nodes"], "edges": saved["edges"]})
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()["name"], "Updated Pipeline")

        # 5. Execute workflow
        res_exec = self.c.post("/api/harness/execute", json={"workflow": res_update.json()})
        self.assertEqual(res_exec.status_code, 200)
        exec_report = res_exec.json()
        self.assertEqual(exec_report["status"], "blocked")
        self.assertFalse(exec_report["passed"])
        self.assertTrue(all(not n['metrics'] for n in exec_report['node_results'].values()))
        self.assertEqual(len(exec_report["node_results"]), 2)
        self.assertIn("node-1", exec_report["node_results"])
        self.assertIn("node-2", exec_report["node_results"])

        # 6. Check executions listing
        res_list = self.c.get("/api/harness/executions")
        self.assertEqual(res_list.status_code, 200)
        self.assertGreaterEqual(len(res_list.json()["executions"]), 1)

        # 7. Delete workflow
        res_del = self.c.delete(f"/api/harness/workflows/{wid}")
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.json()["ok"])

        # Verify not found after delete
        self.assertEqual(self.c.get(f"/api/harness/workflows/{wid}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
