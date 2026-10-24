"""Acceptance and integration tests for PhD Research Lab Workflow IDE & Harness Studio.

Covers:
1. 17 Node Registry and schema contracts.
2. 7 Pre-built scientific research workflow templates.
3. Graph validation (acyclic Kahn DAG validation, port contracts, bounded loops).
4. Dynamic Agent Team Builder & AI Workflow Architect.
5. Workflow execution runtime and debugger state engine.
6. HTTP API routes under /api/harness/*.
"""
from __future__ import annotations

import _env  # isolate data before importing the application

import unittest
from fastapi.testclient import TestClient

from backend.app import app
from backend.execution.workflow_nodes import (
    NODE_REGISTRY,
    validate_workflow_graph,
)
from backend.execution.workflow_templates import RESEARCH_TEMPLATES
from backend.agent.workflow_architect import (
    list_agent_profiles,
    save_agent_profile,
    auto_generate_team,
    generate_workflow_from_objective,
    PRESET_AGENTS,
)
from backend.execution.workflow_runtime import (
    execute_workflow_graph,
    get_execution_record,
)


class HarnessWorkflowIDETestSuite(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_node_registry_17_types(self):
        """Verify all 17 node types plus harnessNode are registered with valid metadata."""
        expected_types = [
            "start",
            "end",
            "agent_task",
            "multi_agent_team",
            "research_engine",
            "tool_skill",
            "mcp_tool",
            "input",
            "output",
            "condition",
            "parallel_branch",
            "join",
            "bounded_loop",
            "human_approval",
            "evaluation_gate",
            "artifact_transformation",
            "memory_read",
            "memory_write",
            "error_handler",
            "checkpoint",
            "harnessNode",
        ]
        for nt in expected_types:
            self.assertIn(nt, NODE_REGISTRY, f"Missing node type {nt} in registry")
            meta = NODE_REGISTRY[nt]
            self.assertEqual(meta.type, nt)
            self.assertTrue(meta.label)
            self.assertTrue(meta.category)
            self.assertIsInstance(meta.inputs, list)
            self.assertIsInstance(meta.outputs, list)

    def test_research_templates_validity(self):
        """Verify that all 7 research workflow templates exist and pass DAG validation."""
        self.assertEqual(len(RESEARCH_TEMPLATES), 7)

        template_ids = {t["id"] for t in RESEARCH_TEMPLATES}
        expected_ids = {
            "tpl-idea-to-hypothesis",
            "tpl-literature-review",
            "tpl-hypothesis-to-experiment",
            "tpl-deep-learning-research",
            "tpl-paper-reproduction",
            "tpl-research-to-paper",
            "tpl-autonomous-research",
        }
        self.assertEqual(expected_ids, template_ids)

        for tpl in RESEARCH_TEMPLATES:
            self.assertGreater(len(tpl["nodes"]), 0)
            self.assertGreater(len(tpl["edges"]), 0)
            val = validate_workflow_graph(tpl)
            self.assertTrue(val["valid"], f"Template {tpl['id']} failed validation: {val['errors']}")

    def test_graph_validation_errors(self):
        """Test graph validation on invalid edges, cyclic dependencies, and missing nodes."""
        # 1. Edge referencing nonexistent node
        invalid_wf = {
            "nodes": [
                {"id": "node-1", "type": "start", "data": {"node_type": "start"}},
            ],
            "edges": [
                {"id": "e1", "source": "node-1", "target": "node-does-not-exist"},
            ],
        }
        res = validate_workflow_graph(invalid_wf)
        self.assertFalse(res["valid"])
        self.assertTrue(any("node-does-not-exist" in err for err in res["errors"]))

        # 2. Cycle detection (A -> B -> A)
        cyclic_wf = {
            "nodes": [
                {"id": "n-a", "type": "agent_task", "data": {"node_type": "agent_task"}},
                {"id": "n-b", "type": "agent_task", "data": {"node_type": "agent_task"}},
            ],
            "edges": [
                {"id": "e1", "source": "n-a", "target": "n-b"},
                {"id": "e2", "source": "n-b", "target": "n-a"},
            ],
        }
        res_cycle = validate_workflow_graph(cyclic_wf)
        self.assertFalse(res_cycle["valid"])
        self.assertTrue(any("cycle" in err.lower() for err in res_cycle["errors"]))

    def test_dynamic_agent_team_builder(self):
        """Test custom agent creation, listing, and automated team synthesis."""
        profiles = list_agent_profiles()
        self.assertGreaterEqual(len(profiles), len(PRESET_AGENTS))

        # Save a custom profile
        custom_agent = {
            "name": "Specialist Quantum Theorist",
            "role": "theorist",
            "purpose": "Formulate quantum Hamiltonian formulations",
            "system_prompt": "You are a quantum algorithm theorist.",
            "provider": "anthropic",
            "model": "claude-3-7-sonnet",
            "skills": ["outline", "verify"],
        }
        saved = save_agent_profile(custom_agent)
        self.assertTrue(saved["id"].startswith("agent-"))
        self.assertEqual(saved["name"], "Specialist Quantum Theorist")

        # Automated team formation
        team = auto_generate_team(
            objective="Design and verify a new sparse mixture-of-experts training regime",
            desired_roles=["director", "coder", "reviewer"],
        )
        self.assertEqual(len(team), 3)
        roles = [m["role"] for m in team]
        self.assertIn("director", roles)
        self.assertIn("coder", roles)
        self.assertIn("reviewer", roles)

    def test_ai_workflow_architect(self):
        """Test AI Workflow Architect generating editable graphs from natural language objectives."""
        objective = "Investigate pruning efficiency in vision transformers with CIFAR-100 benchmarks"
        wf = generate_workflow_from_objective(objective, level="L3")

        self.assertTrue(wf["id"].startswith("ai"))
        self.assertFalse(wf["is_preset"])
        self.assertTrue(wf["generated_by_ai"])
        self.assertEqual(wf["execution_level"], "L3")
        self.assertGreaterEqual(len(wf["nodes"]), 6)
        self.assertGreaterEqual(len(wf["edges"]), 5)

        # Check validation inside generated graph
        val = wf["validation"]
        self.assertTrue(val["valid"], f"Generated workflow failed validation: {val['errors']}")

        node_types = [n["data"]["node_type"] for n in wf["nodes"]]
        self.assertIn("start", node_types)
        self.assertIn("end", node_types)
        self.assertIn("research_engine", node_types)
        self.assertIn("human_approval", node_types)

    def test_workflow_runtime_execution(self):
        """Test workflow runtime executing a multi-node research graph with checkpointing."""
        test_workflow = {
            "id": "wf-test-runtime",
            "name": "Test Runtime Execution",
            "nodes": [
                {
                    "id": "n-start",
                    "type": "start",
                    "data": {
                        "node_type": "start",
                        "label": "Bắt đầu",
                        "config": {"objective": "Test runtime graph"},
                    },
                },
                {
                    "id": "n-engine",
                    "type": "research_engine",
                    "data": {
                        "node_type": "research_engine",
                        "label": "Rà soát Tài liệu",
                        "config": {"engine": "feynman", "action": "synthesize_literature"},
                    },
                },
                {
                    "id": "n-condition",
                    "type": "condition",
                    "data": {
                        "node_type": "condition",
                        "label": "Kiểm tra Tiêu chí",
                        "config": {"condition_rule": "pass_count >= 1"},
                    },
                },
                {
                    "id": "n-end",
                    "type": "end",
                    "data": {
                        "node_type": "end",
                        "label": "Kết thúc",
                        "config": {},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "n-start", "target": "n-engine"},
                {"id": "e2", "source": "n-engine", "target": "n-condition"},
                {"id": "e3", "source": "n-condition", "target": "n-end", "sourceHandle": "true"},
            ],
        }

        report = execute_workflow_graph(test_workflow, level="L3", step_mode=False)

        self.assertTrue(report["execution_id"].startswith("exec-"))
        self.assertEqual(report["workflow_id"], "wf-test-runtime")
        self.assertIn(report["status"], ("completed", "waiting_approval"))
        self.assertEqual(len(report["node_statuses"]), 4)

        # Verify execution history persistence
        record = get_execution_record(report["execution_id"])
        self.assertIsNotNone(record)
        self.assertEqual(record["execution_id"], report["execution_id"])

    def test_harness_api_endpoints(self):
        """Test FastAPI /api/harness HTTP endpoints."""
        # 1. GET /api/harness/nodes
        res = self.client.get("/api/harness/nodes")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("nodes", data)
        self.assertGreaterEqual(len(data["nodes"]), 17)

        # 2. GET /api/harness/templates
        res = self.client.get("/api/harness/templates")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("templates", data)
        self.assertEqual(len(data["templates"]), 7)

        # 3. GET /api/harness/agents
        res = self.client.get("/api/harness/agents")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("agents", data)
        self.assertGreaterEqual(len(data["agents"]), 6)

        # 4. POST /api/harness/validate
        valid_payload = {
            "nodes": [
                {"id": "n1", "type": "start", "data": {"node_type": "start"}},
                {"id": "n2", "type": "end", "data": {"node_type": "end"}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
            ],
        }
        res = self.client.post("/api/harness/validate", json=valid_payload)
        self.assertEqual(res.status_code, 200)
        val = res.json()
        self.assertTrue(val["valid"])
        self.assertEqual(val["node_count"], 2)

        # 5. POST /api/harness/architect/generate
        res = self.client.post(
            "/api/harness/architect/generate",
            json={"objective": "Develop automated verification for LLM reasoning trace", "level": "L3"},
        )
        self.assertEqual(res.status_code, 200)
        wf = res.json()
        self.assertTrue(wf["generated_by_ai"])
        self.assertGreater(len(wf["nodes"]), 0)

        # 6. POST /api/harness/execute with modern DAG
        exec_res = self.client.post(
            "/api/harness/execute",
            json={"workflow": valid_payload, "level": "L3", "step_mode": False},
        )
        self.assertEqual(exec_res.status_code, 200)
        exec_data = exec_res.json()
        self.assertIn("execution_id", exec_data)
        self.assertEqual(exec_data["status"], "completed")


if __name__ == "__main__":
    unittest.main()
