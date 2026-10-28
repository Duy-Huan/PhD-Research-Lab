"""FQC-AGENT-PROFILE-662: the agent is bounded by the owner's tool permissions only, not by step/call/time budgets.

Owner decisions (2026-10-27): one configurable agent profile (default read, compute, network, workspace_write inside the
project; whole registry visible) replaces hardcoded grants; no step, call or wall-clock budget for agent work (Stop,
per-tool hang timeouts and a no-progress hint remain); chat defaults to tool_mode=agent with legacy as a fallback;
external MCP clients get per-client profiles. Models are MOCKED (scripted); registry, runtime, sessions are real.
"""
import json
import sys
import unittest
from unittest.mock import patch

import _env

try:
    from backend.tools import agent_loop, profiles, registry as R
    from backend.tools.runtime import Grant, Runtime
    MISSING = None
except ImportError as missing:  # RED before implementation
    MISSING = missing

ECHO = 'import json,sys\na=json.load(sys.stdin)\nprint(json.dumps({"n": a.get("n", 0)}))\n'


def act(**a):
    return "```phdlab-tool\n" + json.dumps(a) + "\n```"


class Base(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING
        _env.isolate_config(self)
        _env.fresh_project(f"profile-{self._testMethodName[:40]}")

    def install(self, tool_id="echo_n", permissions=("compute",), mutates=False):
        folder = R.tools_root() / tool_id / "1.0.0"
        folder.mkdir(parents=True)
        (folder / "tool.json").write_text(json.dumps({
            "id": tool_id, "kind": "python", "description": "echo a number", "permissions": list(permissions),
            "mutates": mutates, "execution": {"entry": "tool.py"},
            "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}}}))
        (folder / "tool.py").write_text(ECHO)

    def runtime(self):
        rt = Runtime(R.Registry(), workers=2)
        self.addCleanup(rt.pool.shutdown, wait=True)
        return rt


class ProfileConfig(Base):
    def test_default_profile_is_native_and_chat_defaults_to_agent_mode(self):
        cfg = _env.config.load_config()
        self.assertEqual(cfg["tools"]["agent_profile"],
                         {"permissions": ["read", "compute", "network", "workspace_write"], "tools": ["*"]})
        self.assertEqual(cfg["aiws"]["tool_mode"], "agent")
        for client in ("chatgpt", "hermes", "antigravity"):
            self.assertEqual(cfg["tools"]["client_profiles"][client], "agent")

    def test_profile_validation_refuses_unknown_permissions_and_keeps_lists_clean(self):
        with self.assertRaises(ValueError):
            _env.config.save_config({"tools": {"agent_profile": {"permissions": ["read", "root"], "tools": ["*"]}}})
        saved = _env.config.save_config({"tools": {"agent_profile": {"permissions": ["compute", "read", "read"],
                                                                      "tools": ["stats_*", "stats_*"]}}})
        self.assertEqual(saved["tools"]["agent_profile"], {"permissions": ["read", "compute"], "tools": ["stats_*"]})
        with self.assertRaises(ValueError):
            _env.config.save_config({"tools": {"client_profiles": {"chatgpt": {"permissions": ["sudo"], "tools": ["*"]}}}})

    def test_agent_grant_has_no_budgets_and_follows_the_profile(self):
        g = profiles.agent_grant("session:s1")
        self.assertIsNone(g.max_calls)
        self.assertIsNone(g.max_wall_s)
        self.assertEqual(g.permissions, ["read", "compute", "network", "workspace_write"])
        self.assertTrue(g.allow_mutation, "workspace_write allows tools that change project state")
        _env.config.save_config({"tools": {"agent_profile": {"permissions": ["read"], "tools": ["*"]}}})
        g = profiles.agent_grant("session:s1")
        self.assertEqual(g.permissions, ["read"])
        self.assertFalse(g.allow_mutation)

    def test_session_isolation_and_explicit_narrowing_still_apply(self):
        self.assertEqual(profiles.agent_grant("s", session_tools=["-"]).tools, [], "isolated topic: no tools")
        self.assertEqual(profiles.agent_grant("s", session_tools=["research_get_current_state"]).tools,
                         ["research_get_current_state"])
        self.assertEqual(profiles.agent_grant("s", session_tools=[]).tools, ["*"], "default: whole registry")

    def test_client_profiles_for_external_mcp_clients(self):
        g = profiles.client_grant("chatgpt", "mcp:chatgpt:x")
        self.assertEqual(g.permissions, ["read", "compute", "network", "workspace_write"])
        self.assertIsNone(g.max_calls)
        unknown = profiles.client_grant("some-other-client", "mcp:other:x")
        self.assertEqual(unknown.permissions, ["read", "compute"], "unknown clients keep tools.mcp_permissions")
        self.assertFalse(unknown.allow_mutation)


class NoBudgets(Base):
    def test_unbudgeted_grant_runs_beyond_the_old_call_limit(self):
        self.install()
        rt = self.runtime()
        g = profiles.agent_grant("session:many")
        results = [rt.run("echo_n", {"n": i}, g)["status"] for i in range(60)]
        self.assertEqual(results, ["succeeded"] * 60)

    def test_explicit_budgets_are_still_enforced_when_set(self):
        self.install()
        rt = self.runtime()
        g = Grant(principal="t", permissions=["compute"], max_calls=1)
        self.assertEqual(rt.run("echo_n", {"n": 1}, g)["status"], "succeeded")
        self.assertEqual(rt.run("echo_n", {"n": 2}, g)["error"]["code"], "budget_exceeded")

    def test_loop_has_no_step_limit_and_hints_on_repeated_identical_calls(self):
        self.install()
        rt = self.runtime()
        replies = [act(action="call", tool="echo_n", args={"n": i}) for i in range(14)]
        replies += [act(action="call", tool="echo_n", args={"n": 7})] * 3 + [act(action="final", answer="done")]
        seen, events = [], []

        def model(system, messages):
            seen.append(messages[-1]["content"])
            return replies.pop(0)
        out = agent_loop.run("count", model, profiles.agent_grant("s"), registry=rt.registry, runtime=rt,
                             on_event=lambda k, d: events.append(k))
        self.assertEqual(out["status"], "completed")
        self.assertEqual(len(out["steps"]), 18, "more than the former 12-step limit")
        self.assertTrue(any("NO PROGRESS" in m for m in seen), "the model is told it is repeating itself")
        self.assertIn("tool.no_progress", events)

    def test_cancel_still_stops_an_unbounded_loop(self):
        self.install()
        rt = self.runtime()
        calls = {"n": 0}

        def model(system, messages):
            calls["n"] += 1
            return act(action="call", tool="echo_n", args={"n": calls["n"]})
        out = agent_loop.run("forever", model, profiles.agent_grant("s"), registry=rt.registry, runtime=rt,
                             cancelled=lambda: calls["n"] >= 25)
        self.assertEqual(out["status"], "cancelled")
        self.assertEqual(calls["n"], 25)


class ChatAgent(Base):
    def run_chat(self, settings, replies):
        from backend.agent import orchestrator, sessions
        s = sessions.create("Native", settings={"provider": "app:local", "summaries": False,
                                                "collect_artifacts": False, "memory_mode": "off", **settings})
        with patch.object(orchestrator, "_spawn"):
            turn = orchestrator.start(s["id"], "compute something")
        it = iter(replies)
        with patch.object(orchestrator.providers, "describe", return_value={"available": True, "label": "x", "state": "ok", "detail": ""}), \
                patch.object(orchestrator, "_model_text", side_effect=lambda *a, **k: (next(it), "")):
            orchestrator.run(s["id"], turn["id"], "start")
        return next(x for x in sessions.get(s["id"])["turns"] if x["id"] == turn["id"])

    def test_default_chat_runs_compute_tools_from_the_registry_without_a_time_budget(self):
        self.install()
        _env.config.save_config({"aiws": {"max_turn_s": 1}})
        turn = self.run_chat({}, [act(action="call", tool="echo_n", args={"n": 5}), "n is 5"])
        from backend.tools.runtime import RUNTIME
        loop = turn["tool_loop"]
        self.assertEqual(loop["status"], "completed")
        self.assertEqual([RUNTIME.get(j)["status"] for j in loop["jobs"]], ["succeeded"],
                         "compute tool found in the registry and allowed by the default profile")

    def test_agent_mode_streams_prose_live_but_never_tool_protocol_blocks(self):
        import asyncio
        from backend.agent import orchestrator, sessions
        from backend.providers import models as llm
        self.install()
        replies = [[act(action="call", tool="echo_n", args={"n": 3})[:10], act(action="call", tool="echo_n", args={"n": 3})[10:]],
                   ["The measured value ", "is 3, taken from the echo tool job."]]

        async def engine(cfg, eng, system, msgs, mt, temp, model, purpose):
            for chunk in replies.pop(0):
                await asyncio.sleep(0)
                yield chunk
        s = sessions.create("Stream", settings={"provider": "app:ollama", "summaries": False,
                                                "collect_artifacts": False, "memory_mode": "off"})
        with patch.object(orchestrator, "_spawn"):
            turn = orchestrator.start(s["id"], "what is n")
        with patch.object(orchestrator.providers, "describe", return_value={"available": True, "label": "x", "state": "ok", "detail": ""}), \
                patch.object(llm, "_stream_engine", engine):
            orchestrator.run(s["id"], turn["id"], "start")
        deltas = "".join(e["data"].get("text", "") for e in sessions.events(s["id"]) if e["type"] == "message.delta")
        self.assertEqual(deltas, "The measured value is 3, taken from the echo tool job.", "prose streamed once")
        self.assertNotIn("phdlab-tool", deltas)
        saved = sessions.get(s["id"])
        self.assertEqual(saved["messages"][-1]["content"], "The measured value is 3, taken from the echo tool job.")
        self.assertEqual(saved["messages"][-1]["status"], "complete")

    def test_legacy_mode_remains_available(self):
        from backend.agent import orchestrator
        with patch.object(orchestrator, "_app_agent", side_effect=AssertionError("agent loop in legacy mode")):
            turn = self.run_chat({"tool_mode": "legacy", "mcp_tools": ["-"]}, ["plain answer"])
        self.assertNotIn("tool_loop", turn)


if __name__ == "__main__":
    unittest.main()
