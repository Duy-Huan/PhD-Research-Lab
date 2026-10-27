"""FQC-PROVIDER-POOL-661: provider failover for agent loops (owner-approved option 2).

Provider calls are MOCKED (scripted members); the agent loop, registry and runtime are real. These prove failover
semantics and attribution only -- not that any real provider's quota message is recognised, which needs live runs.
"""
import json
import unittest
from unittest.mock import patch

import _env

try:
    from backend.tools import agent_loop, provider_pool as P, registry as R
    from backend.tools.runtime import Grant, Runtime
    from backend.tools.spec import ToolError
    MISSING = None
except ImportError as missing:  # RED before implementation
    MISSING = missing

QUOTA_MSG = "You've hit your usage limit. Upgrade to Pro or try again at 4:32 AM."


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def scripted(plan):
    """plan: provider -> list of replies or exceptions (consumed in order); records what each member saw."""
    seen = []

    def call(member, system, messages):
        seen.append((member["provider"], [dict(m) for m in messages]))
        item = plan[member["provider"]].pop(0)
        if isinstance(item, Exception):
            raise item
        return item(messages) if callable(item) else item
    return call, seen


class Base(unittest.TestCase):
    def setUp(self):
        if MISSING is not None:
            raise MISSING
        _env.isolate_config(self)
        _env.fresh_project(f"pool-{self._testMethodName[:40]}")
        self.clock, self.rest = Clock(), {}

    def pool(self, members, call, cooldown=600):
        return P.ProviderPool(members, call, cooldown_s=cooldown, clock=self.clock, rest_until=self.rest)


class PoolRules(Base):
    def test_pool_rotates_providers_never_accounts_and_excludes_antigravity(self):
        self.assertEqual(P.normalize(["cli:claude_code", {"provider": "app:gemini", "model": "gemini-3.8-flash"}]),
                         [{"provider": "cli:claude_code", "model": ""}, {"provider": "app:gemini", "model": "gemini-3.8-flash"}])
        for bad in (["cli:codex", "cli:codex"], ["cli:antigravity"], ["codex"], []):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                P.ProviderPool(bad, lambda *a: "")

    def test_only_quota_errors_fail_over_and_exhausted_providers_rest(self):
        call, seen = scripted({"cli:claude_code": [RuntimeError(QUOTA_MSG)], "cli:codex": ["a", "b"],
                               "app:local": []})
        pool = self.pool(["cli:claude_code", "cli:codex", "app:local"], call)
        self.assertEqual(pool.complete("s", [{"role": "user", "content": "q"}]), "a")
        self.assertEqual(pool.complete("s", [{"role": "user", "content": "q"}]), "b")
        self.assertEqual([p for p, _ in seen], ["cli:claude_code", "cli:codex", "cli:codex"])
        self.assertEqual([h["outcome"] for h in pool.history], ["quota", "ok", "ok"])
        self.assertNotIn("cli:claude_code", [m["provider"] for m in pool.available()])
        self.clock.t += 601
        self.assertIn("cli:claude_code", [m["provider"] for m in pool.available()], "rests only for the cooldown")
        call, _ = scripted({"cli:codex": [RuntimeError("model returned malformed JSON")], "app:local": ["x"]})
        with self.assertRaises(RuntimeError):
            self.pool(["cli:codex", "app:local"], call).complete("s", [])

    def test_all_exhausted_is_unavailable_not_success(self):
        call, _ = scripted({"cli:claude_code": [RuntimeError("HTTP 429 Too Many Requests")],
                            "cli:codex": [RuntimeError(QUOTA_MSG)]})
        with self.assertRaises(ToolError) as e:
            self.pool(["cli:claude_code", "cli:codex"], call).complete("s", [])
        self.assertEqual(e.exception.code, "unavailable")

    def test_quota_knowledge_is_shared_across_runs(self):
        call, _ = scripted({"cli:claude_code": [RuntimeError(QUOTA_MSG)], "cli:codex": ["one", "two"]})
        self.pool(["cli:claude_code", "cli:codex"], call).complete("s", [])
        second = self.pool(["cli:claude_code", "cli:codex"], call)
        self.assertEqual(second.complete("s", []), "two")
        self.assertEqual([h["provider"] for h in second.history], ["cli:codex"], "exhausted provider skipped without a call")


class LoopContinuity(Base):
    def test_agent_loop_continues_the_same_research_on_the_next_provider(self):
        folder = R.tools_root() / "stats_mean" / "1.0.0"
        folder.mkdir(parents=True)
        (folder / "tool.json").write_text(json.dumps({"id": "stats_mean", "kind": "python", "description": "mean of values",
                                                      "permissions": ["compute"], "execution": {"entry": "tool.py"},
                                                      "input_schema": {"type": "object", "properties": {"values": {"type": "array"}}}}))
        (folder / "tool.py").write_text('import json,sys\na=json.load(sys.stdin)\nprint(json.dumps({"mean":sum(a["values"])/len(a["values"])}))\n')
        act = lambda **a: "```phdlab-tool\n" + json.dumps(a) + "\n```"
        call, seen = scripted({
            "cli:claude_code": [act(action="call", tool="stats_mean", args={"values": [3, 5, 10]}), RuntimeError(QUOTA_MSG)],
            "cli:codex": [lambda m: act(action="final", answer="Mean 6.0", evidence_jobs=[json.loads(m[-1]["content"].split("\n", 1)[1])["job"]])]})
        pool = self.pool(["cli:claude_code", "cli:codex"], call)
        rt = Runtime(R.Registry(), workers=1)
        self.addCleanup(rt.pool.shutdown, wait=True)
        out = agent_loop.run("mean of 3,5,10", pool.complete, Grant(principal="t", permissions=["compute"]),
                             registry=rt.registry, runtime=rt)
        self.assertEqual((out["status"], out["answer"]), ("completed", "Mean 6.0"))
        self.assertEqual(len(out["verified_evidence"]), 1, "evidence from the first provider's job is cited by the second")
        codex_view = seen[-1][1]
        self.assertTrue(any(m["content"].startswith("OBSERVATION") for m in codex_view), "full conversation carried over")
        summary = pool.summary()
        self.assertEqual(summary["providers_used"], ["cli:claude_code", "cli:codex"])
        self.assertTrue(summary["mixed_models"])

    def test_default_call_uses_existing_provider_paths(self):
        async def fake_stream(*a, **k):
            yield "cli-"
            yield "reply"

        async def fake_local(*a, **k):
            return "local reply"

        async def fake_cloud(*a, **k):
            return "cloud reply"
        call = P.default_call({})
        with patch("backend.providers.models._stream_cli", fake_stream), patch("backend.providers.models.local_chat", fake_local), \
                patch("backend.providers.models.cloud_chat", fake_cloud):
            self.assertEqual(call({"provider": "cli:codex", "model": ""}, "s", []), "cli-reply")
            self.assertEqual(call({"provider": "app:local", "model": "spark-x2.5-4b"}, "s", []), "local reply")
            self.assertEqual(call({"provider": "app:gemini", "model": "gemini-3.8-flash"}, "s", []), "cloud reply")


class Integration(Base):
    def test_owner_config_rejects_account_rotation_and_antigravity(self):
        for bad in (["cli:codex", "cli:codex"], ["cli:antigravity"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _env.config.save_config({"tools": {"provider_pool": bad}})
        saved = _env.config.save_config({"tools": {"provider_pool": ["cli:claude_code", "cli:codex"], "pool_cooldown_s": 5}})
        self.assertEqual([m["provider"] for m in saved["tools"]["provider_pool"]], ["cli:claude_code", "cli:codex"])
        self.assertEqual(saved["tools"]["pool_cooldown_s"], 60, "cooldown is bounded")

    def test_chat_agent_mode_fails_over_and_attributes_each_tool_call(self):
        from backend.agent import orchestrator, sessions
        from backend.tools.runtime import RUNTIME, provenance
        _env.config.save_config({"tools": {"provider_pool": ["cli:claude_code", "cli:codex"]}})
        s = sessions.create("Pool", settings={"provider": "app:local", "tool_mode": "agent",
                                              "mcp_tools": ["research_get_current_state"], "summaries": False,
                                              "collect_artifacts": False, "memory_mode": "off"})
        with patch.object(orchestrator, "_spawn"):
            turn = orchestrator.start(s["id"], "What is the current research state?")
        act = lambda **a: "```phdlab-tool\n" + json.dumps(a) + "\n```"
        call, _ = scripted({"cli:claude_code": [act(action="call", tool="research_get_current_state", args={}), RuntimeError(QUOTA_MSG)],
                            "cli:codex": ["The project has no recorded state yet."]})
        with patch.object(orchestrator.providers, "describe", return_value={"available": True, "label": "x", "state": "ok", "detail": ""}), \
                patch("backend.tools.provider_pool.default_call", return_value=call), \
                patch("backend.tools.provider_pool.REST", {}):
            orchestrator.run(s["id"], turn["id"], "start")
        loop = next(x for x in sessions.get(s["id"])["turns"] if x["id"] == turn["id"])["tool_loop"]
        self.assertEqual(loop["status"], "completed")
        self.assertEqual(loop["providers"]["providers_used"], ["cli:claude_code", "cli:codex"])
        self.assertTrue(loop["providers"]["mixed_models"], "mixed-model answers are flagged")
        job = RUNTIME.get(loop["jobs"][0])
        self.assertEqual(job["actor"], "cli:claude_code:")
        self.assertEqual(provenance(job["id"])[-1]["actor"], "cli:claude_code:")


if __name__ == "__main__":
    unittest.main()
