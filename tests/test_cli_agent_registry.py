"""FQC-CLI-AGENT-REGISTRY-662: CLI agents (Codex, Claude Code) and Hermes reach the registry in agent mode.

Found by the owner's live Codex acceptance run: a CLI agent in agent mode received only the read-only MCP allowlist, a
Topic chat received no tools at all, the registry meta-tools were refused even to Hermes, and Codex's own bubblewrap
sandbox broke every shell command inside the PhD-Lab container. The grants, the real MCP JSON-RPC handler, the real
runtime and the argv rewrite run here; Docker, the model and the CLI binary are not started.
"""
import json
import re
import unittest
from unittest.mock import patch

import _env
import test_tool_capability_system as TCS

from backend.agent import mcp_policy, orchestrator, policy
from backend.core import config
from backend.providers import cli, isolated_cli
from backend.tools import mcp_bridge

BRIDGE = {"phdlab_tools_search", "phdlab_tools_describe", "phdlab_tools_call", "phdlab_tools_job"}  # job: 6.6.4 A1


def turn(settings, topic_id=""):
    session = {"binding": {"module": "global"}, "settings": settings}
    if topic_id:
        session["topic_id"] = topic_id
    eff = policy.effective(session)
    return {"effective": eff}, policy.values(eff)


class CliAgentGrant(TCS.Base):
    def test_legacy_mode_keeps_the_read_only_allowlist(self):
        t, v = turn({"provider": "cli:codex", "tool_mode": "legacy"})
        allow, registry, profile = orchestrator._cli_grant("s1", t, v, "codex")
        self.assertEqual(allow, mcp_policy.allowed([]))
        self.assertFalse(BRIDGE & set(allow))
        self.assertIsNone(registry)
        self.assertEqual(profile, "review")

    def test_agent_mode_adds_the_registry_under_the_agent_profile(self):
        t, v = turn({"provider": "cli:codex"})
        allow, registry, profile = orchestrator._cli_grant("s1", t, v, "codex")
        self.assertTrue(BRIDGE <= set(allow))
        self.assertEqual(registry, ["*"], "the owner's agent profile, not the read-only MCP list")
        self.assertEqual(profile, "assisted", "workspace_write in the profile -> writable session workspace")

    def test_agent_profile_without_workspace_write_keeps_the_review_workspace(self):
        config.save_config({"tools": {"agent_profile": {"permissions": ["read", "compute"], "tools": ["*"]}}})
        t, v = turn({"provider": "cli:codex"})
        self.assertEqual(orchestrator._cli_grant("s1", t, v, "codex")[2], "review")

    def test_provider_without_an_enforced_writable_profile_keeps_review(self):
        # Gemini CLI has no enforced "assisted" isolation: the registry is granted, the workspace stays review.
        t, v = turn({"provider": "cli:gemini_cli"})
        allow, registry, profile = orchestrator._cli_grant("s1", t, v, "gemini_cli")
        self.assertTrue(BRIDGE <= set(allow))
        self.assertEqual((registry, profile), (["*"], "review"))

    def test_topic_hides_project_scope_tools_but_not_the_registry(self):
        TCS.install("stats_mean")
        t, v = turn({"provider": "cli:codex"}, topic_id="topic-1")
        allow, registry, _ = orchestrator._cli_grant("s1", t, v, "codex")
        project = {x["name"] for x in mcp_policy.catalog()}
        self.assertEqual(set(allow), BRIDGE, "no project memory, files or sandbox tools in a Topic")
        self.assertIn("stats_mean", registry)
        self.assertIn("mission.paper.discover", registry)
        self.assertFalse(project & set(registry))

    def test_topic_scope_never_probes_tool_availability(self):
        from backend.tools import registry
        t, v = turn({"provider": "cli:codex"}, topic_id="topic-1")
        with patch.object(registry.Registry, "probe", side_effect=AssertionError("availability probe on every turn")):
            self.assertIn("mission.paper.discover", orchestrator._cli_grant("s1", t, v, "codex")[1])

    def test_explicit_no_tools_still_removes_everything(self):
        t, v = turn({"provider": "cli:codex", "mcp_tools": ["-"]})
        allow, registry, profile = orchestrator._cli_grant("s1", t, v, "codex")
        self.assertEqual((allow, registry, profile), ([], None, "review"))

    def test_app_agent_in_a_topic_gets_the_same_registry_scope(self):
        t, v = turn({"provider": "app:local"}, topic_id="topic-1")
        scope = orchestrator._agent_tools(t, v)
        self.assertIn("mission.paper.discover", scope)
        self.assertNotIn("research_search_memory", scope)
        t, v = turn({"provider": "app:local"})
        self.assertEqual(orchestrator._agent_tools(t, v), [])


class EphemeralGrantOverMcp(TCS.Base):
    """The real /mcp JSON-RPC handler with a PhD-Lab-issued session token (as Codex, Claude Code and Hermes use it)."""

    rpc = TCS.McpRegistryBridge.rpc
    call = TCS.McpRegistryBridge.call

    def meta(self, token):
        return {"grant": mcp_policy.lookup(token)}

    def test_agent_grant_lists_and_runs_registry_tools(self):
        TCS.install("stats_mean")
        token = mcp_policy.issue("s1", sorted(BRIDGE), registry=["*"])
        listed = {t["name"] for t in self.rpc("tools/list", meta=self.meta(token))["result"]["tools"]}
        self.assertEqual(listed, BRIDGE)
        res, ran = self.call("phdlab_tools_call", {"tool": "stats_mean", "args": {"values": [1, 5]}}, self.meta(token))
        self.assertFalse(res.get("isError"), ran)
        self.assertEqual(ran["result"]["mean"], 3.0)

    def test_registry_scope_narrows_what_the_meta_tool_may_run(self):
        TCS.install("stats_mean")
        TCS.install("stats_other")
        token = mcp_policy.issue("s1", sorted(BRIDGE), registry=["stats_other"])
        res, denied = self.call("phdlab_tools_call", {"tool": "stats_mean", "args": {"values": [1]}}, self.meta(token))
        self.assertTrue(res.get("isError"))
        self.assertEqual(denied["status"], "denied")

    def test_grant_without_registry_scope_keeps_its_own_tool_list(self):
        token = mcp_policy.issue("s1", ["research_get_current_state"])
        self.assertNotIn("registry", mcp_policy.lookup(token))
        self.assertEqual(mcp_bridge.grant_for({"grant": mcp_policy.lookup(token)}).tools, ["research_get_current_state"])


class PermissionsUi(unittest.TestCase):
    def test_ai_tools_tab_offers_every_backend_permission(self):
        from backend.tools.spec import PERMISSIONS
        source = (config.ROOT / "frontend/src/features/settings/AiToolsSettings.tsx").read_text(encoding="utf-8")
        block = source.split("const PERMS = [", 1)[1].split("] as const", 1)[0]
        self.assertEqual(set(re.findall(r"id: '(\w+)'", block)), set(PERMISSIONS),
                         "a permission without a toggle can never be granted (sandbox_run_code needs process)")


class CodexInsideTheContainer(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)

    def argv(self, args, profile="review"):
        plan = config.data_dir() / "runtime-plan.json"
        plan.write_text("{}", encoding="utf-8")
        context = {"cwd": str(config.data_dir() / "workspace"), "profile": profile}
        with patch.object(isolated_cli, "prepare", return_value={"state": "PREPARED", "plan": str(plan)}) as prep, \
                patch.object(cli.CodexConnector, "_prefix", return_value=["codex"]):
            cli.CodexConnector().process_argv(args, context)
        return json.loads(plan.read_text(encoding="utf-8"))["command"], prep.call_args.kwargs["profile"]

    def test_inner_bubblewrap_sandbox_is_replaced_by_the_container_boundary(self):
        command, profile = self.argv(["codex", "exec", "--json", "--sandbox", "read-only", "-"])
        self.assertEqual(command[command.index("--sandbox") + 1], "danger-full-access")
        self.assertNotIn("read-only", command)
        self.assertEqual(profile, "review", "the container still mounts a review workspace read-only")

    def test_resume_form_is_rewritten_too(self):
        command, _ = self.argv(["codex", "exec", "resume", "--json", "-c", "sandbox_mode=workspace-write", "abc123", "-"],
                               profile="assisted")
        self.assertIn("sandbox_mode=danger-full-access", command)
        self.assertNotIn("sandbox_mode=workspace-write", command)

    def test_other_connectors_are_not_rewritten(self):
        plan = config.data_dir() / "runtime-plan.json"
        plan.write_text("{}", encoding="utf-8")
        context = {"cwd": str(config.data_dir() / "workspace")}
        with patch.object(isolated_cli, "prepare", return_value={"state": "PREPARED", "plan": str(plan)}):
            cli.ClaudeCodeConnector().process_argv(["claude", "-p", "--sandbox", "read-only"], context)
        self.assertEqual(json.loads(plan.read_text(encoding="utf-8"))["command"][-2:], ["--sandbox", "read-only"])


if __name__ == "__main__":
    unittest.main()
