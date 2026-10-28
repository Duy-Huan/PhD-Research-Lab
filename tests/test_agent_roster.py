"""FQC-AGENT-ROSTER-662: one live roster of every agent for 3D Lab, Harness and the status views.

Owner requirement (2026-10-27): 3D Lab must show every agent with its real state — the configured roles, every agent
the Harness created (custom profiles and agent nodes of saved workflows), Hermes and connected MCP clients — derived
from actual runtime records (tool jobs, chat turns, harness executions, gateway requests), streamed over SSE.
"""
import json
import time
import unittest
from unittest.mock import patch

import _env

try:
    from backend.agent import roster
    MISSING = None
except ImportError as missing:  # RED before implementation
    MISSING = missing


def workflow(wid, nodes):
    return {"id": wid, "name": "Saved study", "nodes": nodes, "edges": []}


AGENT_TASK = {"id": "n1", "type": "agent_task", "data": {"label": "Literature scout", "config": {"agent_role": "literature"}}}
TEAM = {"id": "n2", "type": "multi_agent_team", "data": {"label": "Team", "config": {}}}


class Base(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING
        _env.isolate_config(self)
        _env.fresh_project(f"roster-{self._testMethodName[:30]}")
        patch.object(roster, "_hermes_state", return_value=("offline", "Hermes runtime not started")).start()
        self.addCleanup(patch.stopall)

    def by_id(self):
        return {a["id"]: a for a in roster.roster()["agents"]}

    def save_workflow(self, nodes, wid="wf-study"):
        from backend.execution import harness as H
        H.save_workflow(workflow(wid, nodes))


class Sources(Base):
    def test_configured_roles_are_always_present_and_idle(self):
        agents = self.by_id()
        for role in ("assistant", "research", "reviewer", "utility"):
            with self.subTest(role=role):
                self.assertEqual(agents[f"role:{role}"]["state"], "idle")
                self.assertEqual(agents[f"role:{role}"]["kind"], "role")

    def test_every_agent_the_harness_created_appears_and_presets_do_not(self):
        before = roster.roster()["counts"]["harness"]
        self.save_workflow([AGENT_TASK, TEAM])
        from backend.agent.workflow_architect import save_agent_profile
        save_agent_profile({"id": "stats-checker", "name": "Statistics checker", "role": "reviewer"})
        agents = self.by_id()
        self.assertIn("harness:wf-study:n1", agents)
        team = [a for a in agents if a.startswith("harness:wf-study:n2:")]
        self.assertEqual(len(team), 3, "a team node contributes one agent per member (default Lead/Coder/Reviewer)")
        self.assertIn("harness-profile:stats-checker", agents)
        self.assertEqual(roster.roster()["counts"]["harness"], before + 5)
        self.save_workflow([AGENT_TASK, TEAM, {"id": "n3", "type": "agent_task", "data": {"label": "Coder", "config": {}}}])
        self.assertEqual(roster.roster()["counts"]["harness"], before + 6, "adding a node adds an agent")

    def test_connected_mcp_clients_and_hermes_are_listed(self):
        from backend.providers import mcp_server
        with patch.dict(mcp_server.SESSIONS, {"mcp-a": {"name": "antigravity", "started": time.time()},
                                              "mcp-old": {"name": "stale", "started": time.time() - 7200}}, clear=True), \
                patch.object(roster, "_hermes_state", return_value=("idle", "Runtime ready")):
            agents = self.by_id()
        self.assertEqual(agents["mcp:antigravity"]["kind"], "mcp_client")
        self.assertNotIn("mcp:stale", agents, "clients inactive for over 30 minutes are not shown as connected")
        self.assertEqual(agents["hermes"]["state"], "idle")


class LiveStates(Base):
    def test_tool_jobs_mark_the_requesting_agent_busy_with_the_tool(self):
        from backend.tools.runtime import RUNTIME
        jobs = {"j1": {"id": "j1", "status": "running", "tool": "stats_mean", "principal": "session:as-1",
                       "actor": "app:local:spark", "started": time.time()},
                "j2": {"id": "j2", "status": "running", "tool": "phdlab_x", "principal": "mcp:chatgpt:s1", "started": time.time()}}
        with patch.dict(RUNTIME.jobs, jobs, clear=True):
            agents = self.by_id()
        self.assertEqual(agents["role:assistant"]["state"], "tool")
        self.assertEqual(agents["role:assistant"]["tool"], "stats_mean")
        self.assertEqual(agents["role:assistant"]["job"], "j1", "links to the job's provenance")
        self.assertEqual(agents["mcp:chatgpt"]["state"], "tool")

    def test_running_chat_turn_makes_the_assistant_think(self):
        from backend.agent import orchestrator
        with patch.dict(orchestrator._running, {"t-1": {"cancel": None, "rid": ""}}, clear=True):
            self.assertEqual(self.by_id()["role:assistant"]["state"], "thinking")

    def test_harness_execution_drives_node_agent_states(self):
        self.save_workflow([AGENT_TASK, TEAM])
        from backend.execution import workflow_runtime as WR
        WR.save_execution_record({"execution_id": "ex-1", "workflow_id": "wf-study", "status": "waiting_approval",
                                  "node_statuses": [{"node_id": "n1", "status": "waiting_approval"},
                                                    {"node_id": "n2", "status": "failed"}],
                                  "created_at": "2026-10-27T00:00:00+00:00"})
        agents = self.by_id()
        self.assertEqual(agents["harness:wf-study:n1"]["state"], "waiting")
        self.assertEqual(agents["harness:wf-study:n2:0"]["state"], "error")

    def test_digest_changes_only_when_something_changes(self):
        first = roster.roster()["digest"]
        self.assertEqual(roster.roster()["digest"], first)
        from backend.agent import orchestrator
        with patch.dict(orchestrator._running, {"t-1": {"cancel": None, "rid": ""}}, clear=True):
            self.assertNotEqual(roster.roster()["digest"], first)


class Api(Base):
    def test_snapshot_and_stream_endpoints(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        with TestClient(app, headers={"X-PhDLab-Client": "ui"}) as client:
            snap = client.get("/api/agents/roster").json()
            self.assertGreaterEqual(snap["counts"]["total"], 4)
            with client.stream("GET", "/api/agents/roster/stream?once=1") as r:
                body = "".join(r.iter_text())
        self.assertIn("event: roster", body)
        payload = json.loads(body.split("data: ", 1)[1].split("\n", 1)[0])
        self.assertEqual(payload["digest"], snap["digest"])


if __name__ == "__main__":
    unittest.main()
