"""FQC-HARNESS-TEAM-664 (agent/PLAN_6.6.4_L3.md A9): the Harness canvas runs as a governed mission with an AI-proposed
team bound to models from the model list.

Found by Playwright (2026-10-28, output/playwright/harness-team-663/): the team came from keyword matching, the architect
filled a fixed template and the canvas runtime blocked every agent node. Owner rule: team agents use models from the
app's model list (Codex/Claude for live runs), an unavailable model is never swapped. Real missions, approvals, team
validation and step reviews in a disposable PHDLAB_DATA_DIR; the CLI gateway (research.run_coding) and the architect's
answer are replaced by fixed results, the live Codex run is separate evidence."""
import asyncio
import json
import unittest
from unittest.mock import patch

import _env
import importlib

from backend.agent import autonomy, missions as M, workflow_architect as WA
from backend.core import config
from backend.knowledge import research_store as S



class _Lazy:
    """Imported on use, so each test reports on its own (also on the commit before A9)."""

    def __init__(self, name):
        self.name = name

    def __getattr__(self, attr):
        return getattr(importlib.import_module(self.name), attr)


HC, TA = _Lazy("backend.agent.harness_compile"), _Lazy("backend.agent.team_agents")
CODEX = {"id": "cli:codex", "label": "Codex", "transport": "cli", "state": "CONNECTED", "available": True, "models": []}
LOCAL = {"id": "app:local", "label": "Local", "transport": "local", "state": "NO_MODEL", "available": False, "models": []}
TEAM = [{"id": "researcher", "role": "researcher", "purpose": "Proposes the hypothesis and design", "model": "cli:codex",
         "tools": ["library.search", "experiment.propose_protocol"]},
        {"id": "coder", "role": "coder", "purpose": "Implements the approved design", "model": "cli:codex", "tools": ["code.apply_patch"]}]


def describe(pid, cfg=None):
    found = {c["id"]: c for c in (CODEX, LOCAL)}
    if pid not in found:
        from backend.agent import AIWSError
        raise AIWSError("Unknown provider")
    return {**found[pid], "detail": "fixture"}


class HarnessTeam(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("harness team tests")
        config.save_config({"research_os": {"enabled": True, "team_enabled": True}})
        self.tid = _env.legacy_topic(S.TopicInput(title="Denoising"))["id"]
        self.real_choices = TA.model_choices  # setUp replaces it with a fixed list
        p = patch("backend.agent.team_agents.model_choices", return_value=[CODEX, LOCAL])
        p.start()
        self.addCleanup(p.stop)
        p = patch("backend.providers.registry.describe", side_effect=describe)
        p.start()
        self.addCleanup(p.stop)

    def canvas(self):
        return WA.generate_workflow_from_objective("Does smoothing reduce noise? write a paper", "L3")

    def drive(self, mid, n=12):
        for _ in range(n):
            asyncio.run(M.tick(mid))

    def approve(self, mission):
        return M.approve(self.tid, mission["id"], mission["payload"]["plan_digest"], "Reviewed the compiled canvas")

    def test_the_architect_model_proposes_and_the_app_validates_the_team(self):
        answer = "Here you go:\n```json\n" + json.dumps({"agents": TEAM, "rationale": "two roles"}) + "\n```"
        with patch("backend.agent.team_agents.ask", return_value=answer) as ask:
            team = HC.propose_team("Does smoothing reduce noise?", "cli:codex")
        self.assertEqual(ask.call_args.args[0], "cli:codex")
        self.assertIn("cli:codex (Codex; available)", ask.call_args.args[2])
        self.assertIn("app:local (Local; unavailable: NO_MODEL)", ask.call_args.args[2])
        self.assertEqual([a["id"] for a in team["agents"]], ["researcher", "coder"])
        self.assertEqual(team["unavailable"], [])
        bad = [({"agents": [{**TEAM[0], "tools": ["shell.rm_rf"]}]}, "unknown tools"),
               ({"agents": [{**TEAM[0], "model": "cli:gemini_cli"}]}, "not in the model list"),
               ({"agents": [TEAM[0], TEAM[0]]}, "must be unique"),
               ({"agents": [TEAM[0]] * 5}, "1 to 4 agents")]
        for data, message in bad:
            with self.subTest(message=message), patch("backend.agent.team_agents.ask", return_value=json.dumps(data)), \
                    self.assertRaisesRegex(ValueError, message):
                HC.propose_team("x", "cli:codex")
        with patch("backend.agent.team_agents.ask", return_value="I think a team of three would be best."), \
                self.assertRaisesRegex(ValueError, "JSON"):
            HC.propose_team("x", "cli:codex")
        with patch("backend.agent.team_agents.ask", return_value=json.dumps({"agents": [{**TEAM[0], "model": "app:local"}]})):
            self.assertEqual(HC.propose_team("x", "cli:codex")["unavailable"], ["researcher"])  # kept, marked, not swapped

    def test_the_canvas_compiles_to_a_mission_draft_with_the_bound_models(self):
        out = HC.create_mission(self.canvas(), self.tid, "L3", TEAM)
        caps = [(t["id"], t["capability"]) for t in out["spec"]["tasks"]]
        self.assertEqual(caps, [("node-literature", "paper.discover"), ("node-hypothesis", "agent.task"),
                                ("node-gate-hypothesis", "review.checkpoint"), ("node-native-code", "agent.task"),
                                ("node-evaluation", "artifact.verify"), ("node-paperorchestra", "paperorchestra.full_orchestration"),
                                ("node-gate-final", "review.checkpoint"), ("node-end", "mission.report")])
        agent_tasks = {t["id"]: t["args"] for t in out["spec"]["tasks"] if t["capability"] == "agent.task"}
        self.assertEqual({a["agent"]: a["model"] for a in agent_tasks.values()}, {"researcher": "cli:codex", "coder": "cli:codex"})
        self.assertEqual(agent_tasks["node-native-code"]["from_task"], "node-gate-hypothesis")
        self.assertTrue(any("metric threshold" in n for n in out["notes"]))
        self.assertEqual(out["mission"]["status"], "draft")
        self.assertEqual({a["id"] for a in out["spec"]["team"]["agents"]}, {"researcher", "coder", "coordinator"})

    def test_canvases_that_cannot_be_compiled_say_why(self):
        canvas = self.canvas()
        cond = dict(canvas, nodes=canvas["nodes"] + [{"id": "c1", "type": "condition", "data": {"label_en": "If", "config": {}}}],
                    edges=canvas["edges"] + [{"id": "e-c", "source": "node-start", "target": "c1"}])
        cases = [((cond, "L3", TEAM), "conditions and loops"),
                 ((canvas, "L4", TEAM), "L2 or L3"),
                 ((canvas, "L3", [TEAM[1]]), None),  # one agent takes every agent node
                 ((canvas, "L3", [TEAM[0], {**TEAM[1], "id": "writer", "role": "writer"}]), "no team agent has role 'coder'")]
        for (wf, level, team), message in cases:
            with self.subTest(message=message):
                if message is None:
                    self.assertTrue(HC.compile_workflow(wf, self.tid, level, team)["spec"]["tasks"])
                    continue
                with self.assertRaisesRegex(ValueError, message):
                    HC.compile_workflow(wf, self.tid, level, team)

    def test_agent_tasks_run_on_the_bound_model_and_checkpoints_wait_for_the_researcher(self):
        calls = []

        def run_coding(op, pid, prompt, context, out, cancelled=None, registry=None):
            calls.append((pid, prompt, context, registry))
            out.mkdir(parents=True, exist_ok=True)
            (out / "design.md").write_text("Hypothesis: smoothing lowers MSE. Design: 3 seeds.", "utf-8")
            return {"text": "Proposed hypothesis and design (unverified).", "files": ["design.md"]}
        wf = self.canvas()
        keep = {"node-start", "node-hypothesis", "node-gate-hypothesis", "node-end"}
        wf = dict(wf, nodes=[n for n in wf["nodes"] if n["id"] in keep],
                  edges=[{"id": "a", "source": "node-start", "target": "node-hypothesis"},
                         {"id": "b", "source": "node-hypothesis", "target": "node-gate-hypothesis"},
                         {"id": "c", "source": "node-gate-hypothesis", "target": "node-end"}])
        mission = self.approve(HC.create_mission(wf, self.tid, "L3", TEAM)["mission"])
        with patch("backend.providers.research.run_coding", side_effect=run_coding):
            self.drive(mission["id"])
        m = M.get(mission["id"], self.tid)
        self.assertEqual(m["status"], "awaiting_step_review", m["payload"].get("blocking_reason"))
        hypo = next(t for t in m["tasks"] if t["id"] == "node-hypothesis")
        self.assertEqual((hypo["status"], hypo["payload"]["result"]["output"]["model"]), ("completed", "cli:codex"))
        self.assertEqual(len(hypo["payload"]["result"]["artifacts"]), 1)
        self.assertEqual(calls[0][0], "codex")
        self.assertIn("Your role (researcher)", calls[0][2])
        self.assertEqual(calls[0][3], ["library.search", "experiment.propose_protocol"])  # the team's tools reach the agent
        self.assertNotEqual(next(t for t in m["tasks"] if t["id"] == "node-end")["status"], "completed")
        task = autonomy.pending_review(m)
        self.assertEqual(task["id"], "node-gate-hypothesis")
        autonomy.step_review(self.tid, m["id"], task["id"], m["payload"]["plan_digest"],
                             __import__("backend.agent.decision_ledger", fromlist=["digest"]).digest(task["payload"]["result"]),
                             True, "Hypothesis looks testable")
        self.drive(mission["id"])
        m = M.get(mission["id"], self.tid)
        self.assertEqual(next(t for t in m["tasks"] if t["id"] == "node-end")["status"], "completed")
        self.assertEqual(m["status"], "awaiting_review")  # L3: final human review stays with the researcher

    def test_an_unavailable_model_pauses_the_mission_and_nothing_else_runs(self):
        wf = self.canvas()
        keep = {"node-start", "node-hypothesis", "node-end"}
        wf = dict(wf, nodes=[n for n in wf["nodes"] if n["id"] in keep],
                  edges=[{"id": "a", "source": "node-start", "target": "node-hypothesis"},
                         {"id": "b", "source": "node-hypothesis", "target": "node-end"}])
        team = [{**TEAM[0], "model": "app:local"}]
        mission = self.approve(HC.create_mission(wf, self.tid, "L3", team)["mission"])
        with patch("backend.providers.research.run_coding") as coding, \
                patch("backend.providers.models.local_chat") as local, patch("backend.providers.models.cloud_chat") as cloud:
            self.drive(mission["id"], 4)
        m = M.get(mission["id"], self.tid)
        self.assertEqual(m["status"], "paused")
        self.assertIn("app:local is unavailable", m["payload"]["blocking_reason"])
        self.assertIn("No other model is tried", m["payload"]["blocking_reason"])
        for fake in (coding, local, cloud):
            fake.assert_not_called()

    def test_model_choices_exclude_providers_that_may_not_be_driven(self):
        listed = [{"id": i, "label": i, "state": "CONNECTED", "available": True} for i in
                  ("app:auto", "app:local", "cli:codex", "cli:claude_code", "cli:gemini_cli", "cli:antigravity", "runtime:hermes")]
        with patch("backend.providers.registry.registry", return_value=listed):
            ids = [c["id"] for c in self.real_choices()]  # the real function, with a fixed registry
        self.assertEqual(ids, ["app:local", "cli:codex", "cli:claude_code"])
        with self.assertRaisesRegex(ValueError, "cannot be bound"):
            TA.check_model("cli:gemini_cli")

    def test_a_local_engine_counts_as_available_only_when_it_answers(self):
        # Found live: LM Studio was not running but the model list said "available" (registry state UNKNOWN).
        listed = [{"id": "app:local", "label": "Local", "state": "UNKNOWN", "available": True}]
        from backend.providers import models
        TA._local.clear()
        with patch("backend.providers.registry.registry", return_value=listed),                 patch.object(models, "local_target", side_effect=models.LLMError("Cannot reach LM Studio")):
            down = self.real_choices()[0]
        self.assertEqual((down["available"], down["state"].startswith("UNREACHABLE")), (False, True))
        TA._local.clear()

        async def target(cfg, engine, model=None):
            return "http://127.0.0.1:1234/v1", "qwen-test", "LM Studio", ""
        with patch("backend.providers.registry.registry", return_value=listed), patch.object(models, "local_target", side_effect=target):
            up = self.real_choices()[0]
        self.assertEqual((up["available"], up["state"]), (True, "READY (LM Studio: qwen-test)"))
        TA._local.clear()

    def test_a_cli_agent_grant_carries_its_registry_tools_and_session_files_are_not_outputs(self):
        # Found in the live Codex run: library.search was unreachable and the session's own instruction files came
        # back as the agent's work.
        import tempfile
        from pathlib import Path
        from backend.agent import mcp_policy
        from backend.providers import research
        from backend.tools.mcp_bridge import NAMES
        plain = mcp_policy.grant_for_cli("run:a")
        self.assertNotIn("registry", mcp_policy.lookup(plain["mcp_token"]))
        team = mcp_policy.grant_for_cli("run:b", registry=["library.search"])
        self.assertEqual(mcp_policy.lookup(team["mcp_token"])["registry"], ["library.search"])
        self.assertTrue(NAMES <= set(team["mcp_tools"]))
        for g in (plain, team):
            mcp_policy.revoke(g["mcp_token"])
        from backend.core.config import data_dir
        cwd = Path(tempfile.mkdtemp(dir=data_dir()))
        before = research._snapshot(cwd)
        for name in ("AGENTS.md", "FIREWALL.md", "design.md"):
            (cwd / name).write_text("x", "utf-8")
        (cwd / "sub").mkdir()
        (cwd / "sub" / "AGENTS.md").write_text("agent's own file", "utf-8")
        self.assertEqual(sorted(research._collect(cwd, before, data_dir() / "collected")), ["design.md", "sub/AGENTS.md"])

    def test_the_api_lists_models_compiles_and_reports_errors(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)
        self.assertEqual([m["id"] for m in client.get("/api/harness/models").json()["models"]], ["cli:codex", "app:local"])
        body = {"workflow": self.canvas(), "topic_id": self.tid, "level": "L3", "team": TEAM}
        preview = client.post("/api/harness/compile", json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertNotIn("mission", preview.json())
        created = client.post("/api/harness/compile", json={**body, "create": True})
        self.assertEqual(created.json()["mission"]["status"], "draft")
        bad = client.post("/api/harness/compile", json={**body, "level": "L4"})
        self.assertEqual(bad.status_code, 400)
        with patch("backend.agent.team_agents.ask", side_effect=ValueError("cli:codex is unavailable (DISCONNECTED)")):
            r = client.post("/api/harness/team/propose", json={"objective": "x", "architect_model": "cli:codex"})
        self.assertEqual((r.status_code, "unavailable" in r.json()["detail"]), (400, True))


if __name__ == "__main__":
    unittest.main()
