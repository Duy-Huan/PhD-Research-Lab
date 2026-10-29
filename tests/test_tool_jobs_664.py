"""FQC-TOOL-JOBS-664 (agent/PLAN_6.6.4_L3.md A1): long registry tool calls return a job id that the agent polls.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): phdlab_tools_call held the HTTP request until the
tool finished, so a long sandbox run through the Codex container's MCP proxy came back as HTTP 502 while the run went
on. The call now waits a bounded time, then returns the running job; phdlab_tools_job reports or cancels it, and only
for the client that started it. Real subprocess tools in a disposable PHDLAB_DATA_DIR."""
import time
import unittest
from unittest.mock import patch

import _env  # noqa: F401
import test_tool_capability_system as TCS
from backend.tools import mcp_bridge

SLOW = '''import json, sys, time
a = json.load(sys.stdin)
time.sleep(float(a.get("fail") and 30 or 2.5))
print(json.dumps({"mean": sum(a["values"]) / len(a["values"]), "n": len(a["values"])}))
'''
CODEX = {"name": "codex", "session": "s1"}
OTHER = {"name": "claude_code", "session": "s2"}


class ToolJobs(TCS.Base):
    def setUp(self):
        super().setUp()
        patcher = patch.object(mcp_bridge, "RUNTIME", self.rt)
        patcher.start()
        self.addCleanup(patcher.stop)
        TCS.install("stats_mean")
        TCS.install("stats_slow", code=SLOW)

    def call(self, name, args, client=CODEX):
        res = mcp_bridge.call(name, args, client)
        return res, res.get("structuredContent") or {}

    def test_a_long_call_returns_its_running_job_and_the_job_tool_delivers_the_result(self):
        res, started = self.call("phdlab_tools_call", {"tool": "stats_slow", "args": {"values": [1, 5]}, "wait_s": 0.3})
        self.assertIn(started["status"], ("queued", "running"))
        self.assertFalse(res.get("isError"), started)  # still running is not an error
        self.assertIn("phdlab_tools_job", started["hint"])
        res, done = self.call("phdlab_tools_job", {"job": started["job"], "wait_s": 30})
        self.assertEqual(done["status"], "succeeded", done)
        self.assertEqual(done["result"]["mean"], 3.0)
        self.assertFalse(res.get("isError"))

    def test_a_fast_call_still_answers_in_one_step(self):
        res, ran = self.call("phdlab_tools_call", {"tool": "stats_mean", "args": {"values": [2, 4]}})
        self.assertEqual((ran["status"], ran["result"]["mean"]), ("succeeded", 3.0))
        self.assertNotIn("hint", ran)

    def test_another_client_cannot_read_or_cancel_the_job(self):
        _, started = self.call("phdlab_tools_call", {"tool": "stats_slow", "args": {"values": [1]}, "wait_s": 0})
        for action in ("status", "cancel"):
            with self.subTest(action=action):
                res, seen = self.call("phdlab_tools_job", {"job": started["job"], "action": action}, OTHER)
                self.assertTrue(res.get("isError"))
                self.assertEqual(seen["error"]["code"], "not_found")
                self.assertNotIn("result", seen)
        res, unknown = self.call("phdlab_tools_job", {"job": "tj-does-not-exist"})
        self.assertEqual(unknown["error"]["code"], "not_found")
        self.call("phdlab_tools_job", {"job": started["job"], "wait_s": 30})

    def test_the_owner_can_cancel_a_running_job(self):
        _, started = self.call("phdlab_tools_call", {"tool": "stats_slow", "args": {"values": [1], "fail": True}, "wait_s": 0.3})
        _, cancelled = self.call("phdlab_tools_job", {"job": started["job"], "action": "cancel", "wait_s": 30})
        self.assertEqual(cancelled["status"], "cancelled", cancelled)

    def test_waits_are_bounded(self):
        _, started = self.call("phdlab_tools_call", {"tool": "stats_slow", "args": {"values": [1]}, "wait_s": -5})
        self.assertIn(started["status"], ("queued", "running"))
        t0 = time.monotonic()
        _, polled = self.call("phdlab_tools_job", {"job": started["job"], "wait_s": 0})
        self.assertLess(time.monotonic() - t0, 1.0)
        self.assertIn(polled["status"], ("queued", "running", "succeeded"))
        self.assertEqual(mcp_bridge.bounded_wait(10_000), mcp_bridge.MAX_WAIT_S)
        self.assertEqual(mcp_bridge.bounded_wait(None), mcp_bridge.DEFAULT_WAIT_S)
        self.assertLess(mcp_bridge.DEFAULT_WAIT_S, 60)  # below the CLI clients' 60 s MCP tool timeout
        self.call("phdlab_tools_job", {"job": started["job"], "wait_s": 30})

    def test_every_registry_client_sees_the_job_tool(self):
        from backend.providers import hermes
        from backend.tools import chatgpt_gateway
        self.assertIn("phdlab_tools_job", mcp_bridge.NAMES)
        self.assertIn("phdlab_tools_job", hermes.REGISTRY_TOOLS)
        self.assertIn("phdlab_tools_job", chatgpt_gateway.EXPOSED_TOOLS)

    def test_polling_is_cheap(self):
        _, started = self.call("phdlab_tools_call", {"tool": "stats_mean", "args": {"values": [1]}})
        t0 = time.monotonic()
        for _ in range(200):
            self.call("phdlab_tools_job", {"job": started["job"], "wait_s": 0})
        self.assertLess(time.monotonic() - t0, 2.0)


if __name__ == "__main__":
    unittest.main()
