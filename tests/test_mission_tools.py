"""FQC-MISSION-TOOLS-662: mission capabilities are registry tools (one tool system for agents).

Each capability of backend.agent.capabilities is discoverable as `mission.<capability>` with its real input schema and
permissions. Calling one creates a governed single-task mission in the topic; mission plan approval stays with the
researcher (existing mission governance), so the result says what to approve instead of claiming completion.
"""
import unittest

import _env

try:
    from backend.tools import mission_tools
    MISSING = None
except ImportError as missing:  # RED before implementation
    MISSING = missing


class Base(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING
        _env.isolate_config(self)
        _env.fresh_project(f"mission-tools-{self._testMethodName[:30]}")


class MissionTools(Base):
    def test_every_capability_is_a_discoverable_registry_tool(self):
        from backend.agent import capabilities as CAP
        from backend.tools import registry as R
        reg = R.Registry()
        ids = {t["id"] for t in reg.listing()["tools"]}
        for cap in CAP.catalog():
            with self.subTest(cap=cap["id"]):
                self.assertIn("mission." + cap["id"], ids)
        spec = reg.resolve("mission.paper.discover")
        self.assertIn("workspace_write", spec.permissions)
        self.assertIn("args", spec.input_schema["properties"])
        found = [t["id"] for t in reg.search("discover papers literature", limit=10)]
        self.assertIn("mission.paper.discover", found, "capability search finds mission tools")

    def test_call_creates_a_governed_mission_awaiting_researcher_approval(self):
        from backend.agent import missions
        from backend.knowledge import research_store as store
        from backend.tools import registry as R
        from backend.tools.runtime import Grant, Runtime
        topic = store.save_topic(store.TopicInput(title="Mission tools topic"))
        rt = Runtime(R.Registry(), workers=1)
        self.addCleanup(rt.pool.shutdown, wait=True)
        g = Grant(principal="session:t", permissions=["read", "compute", "network", "workspace_write"], allow_mutation=True,
                  max_calls=None, max_wall_s=None, max_output_bytes=None)
        job = rt.run("mission.mission.report", {"topic_id": topic["id"], "objective": "Summarise evidence so far",
                                                "args": {"title": "Evidence so far"}}, g)
        self.assertEqual(job["status"], "succeeded", job.get("error"))
        result = job["result"]
        self.assertEqual(result["status"], "awaiting_approval")
        mission = missions.get(result["mission_id"], topic["id"])
        self.assertEqual([t["capability"] for t in mission["payload"]["spec"]["tasks"]], ["mission.report"])
        self.assertEqual(mission["status"], result["status_detail"])

    def test_invalid_capability_arguments_are_structured_errors(self):
        from backend.tools import registry as R
        from backend.tools.runtime import Grant, Runtime
        rt = Runtime(R.Registry(), workers=1)
        self.addCleanup(rt.pool.shutdown, wait=True)
        g = Grant(principal="t", permissions=["read", "compute", "network", "workspace_write"], allow_mutation=True)
        job = rt.run("mission.paper.discover", {"topic_id": "no-such-topic", "objective": "x", "args": {"limit": 5}}, g)
        self.assertEqual(job["status"], "failed")
        self.assertIn(job["error"]["code"], ("invalid_input", "not_found"))

    def test_read_only_grant_cannot_create_missions(self):
        from backend.tools import registry as R
        from backend.tools.runtime import Grant, Runtime
        rt = Runtime(R.Registry(), workers=1)
        self.addCleanup(rt.pool.shutdown, wait=True)
        job = rt.run("mission.mission.report", {"topic_id": "t", "objective": "x", "args": {}},
                     Grant(principal="t", permissions=["read"]))
        self.assertEqual(job["status"], "denied")


if __name__ == "__main__":
    unittest.main()
