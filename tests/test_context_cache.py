"""Context caching follows durable research inputs, including updates inside existing run folders."""
import _env
import json
import unittest
from unittest import mock

from backend.agent import context, outline, pins, policy, runs, sessions
from backend.core import config
from backend.memory import cache


class ContextCache(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("context-cache")
        context.clear_cache()
        cache.clear_all()
        self.s = sessions.create("Current", settings={"context_mode": "selected"})
        self.enterContext(mock.patch("backend.execution.resources.policy", return_value={"cpu": 1}))

    def compile(self):
        session = sessions.get(self.s["id"])
        return context.compile(session, "what is the research state?", policy.effective(session))

    def test_memory_compilation_keeps_starting_project_during_project_switch(self):
        from backend import memory
        from backend.memory import compiler, engine

        first = config.data_dir()
        memory.set_tier3({"goals": ["PROJECT_A_KEEP_THIS_RESEARCH_GOAL"]})
        second = _env.fresh_project("context-switch-other")
        memory.set_tier3({"goals": ["PROJECT_B_PRIVATE_RESEARCH_GOAL"]})
        config.activate_project(str(first))
        original = engine.build_context

        def switch_then_build(*args, **kwargs):
            config.activate_project(second["data_dir"])
            return original(*args, **kwargs)

        # Only the concurrent UI selection is controlled; memory reads and retrieval are real.
        with mock.patch.object(engine, "build_context", side_effect=switch_then_build):
            result = compiler.compile_context(query="research goal", budget_tokens=3500)
        self.assertIn("PROJECT_A_KEEP_THIS_RESEARCH_GOAL", result["text"])
        self.assertNotIn("PROJECT_B_PRIVATE_RESEARCH_GOAL", result["text"])
        self.assertEqual(str(config.data_dir()), second["data_dir"])

    def test_empty_project_reuses_context_after_reads_and_manifest_event_writes(self):
        first = self.compile()
        self.assertEqual(first["manifest"]["cache"], "miss")
        self.assertEqual(self.compile()["manifest"]["cache"], "hit")
        sessions.update(self.s["id"], lambda x: x.update(last_manifest=first["manifest"], summary="my own summary"))
        sessions.emit(self.s["id"], "status.updated", manifest=first["manifest"]["id"])
        cached = self.compile()
        self.assertEqual(cached["manifest"]["cache"], "hit")
        self.assertEqual(cached["text"], first["text"])

    def test_pins_and_outline_invalidate_context(self):
        before = self.compile()["manifest"]["version"]
        pins.add("method", "Use token pruning", "Keep the 2W device limit")
        after_pin = self.compile()
        self.assertNotEqual(after_pin["manifest"]["version"], before)
        self.assertIn("Keep the 2W device limit", after_pin["text"])
        self.assertEqual(self.compile()["manifest"]["cache"], "hit")
        outline.update({"topic": "Hyperspectral transformer denoising"})
        after_outline = self.compile()
        self.assertNotEqual(after_outline["manifest"]["version"], after_pin["manifest"]["version"])
        self.assertIn("Hyperspectral transformer denoising", after_outline["text"])

    def test_updating_an_existing_experiment_refreshes_metrics(self):
        folder = config.data_dir() / "runs" / "run-cache01"
        folder.mkdir(parents=True)
        path = folder / "run.json"
        record = {"id": "run-cache01", "status": "done", "metrics": {"acc": 0.5}}
        path.write_text(json.dumps(record), "utf-8")
        first = self.compile()
        self.assertIn("0.5", first["text"])
        directory_version = folder.parent.stat().st_mtime_ns
        record["metrics"]["acc"] = 0.987654
        path.write_text(json.dumps(record), "utf-8")
        self.assertEqual(folder.parent.stat().st_mtime_ns, directory_version)
        second = self.compile()
        self.assertEqual(second["manifest"]["cache"], "miss")
        self.assertIn("0.987654", second["text"])
        self.assertNotEqual(second["manifest"]["version"], first["manifest"]["version"])

    def test_research_runs_and_other_conversation_summaries_invalidate_context(self):
        first = self.compile()
        run = runs.create("research", "Literature run", "pruning", {"topic": "pruning"}, risk=0, start=False)
        second = self.compile()
        self.assertNotEqual(first["manifest"]["version"], second["manifest"]["version"])
        self.assertIn("Literature run", second["text"])
        runs.update(run["id"], lambda r: r.update(status="NEEDS_USER_ACTION"))
        self.assertIn("NEEDS_USER_ACTION", self.compile()["text"])
        other = sessions.create("Earlier work")
        sessions.update(other["id"], lambda s: s.update(summary="Three seeds were required for each comparison."))
        folder = sessions.create_chat_project('Explicit shared research')
        sessions.organize(self.s['id'], chat_project=folder['id'])
        sessions.organize(other['id'], chat_project=folder['id'])
        summary = self.compile()
        self.assertIn("Three seeds", summary["text"])
        sessions.update(other["id"], lambda s: s.update(summary="Five seeds were required for each comparison."))
        self.assertIn("Five seeds", self.compile()["text"])
        self.assertEqual(self.compile()["manifest"]["cache"], "hit")

    def test_legacy_knowledge_file_changes_retrieval_version(self):
        before = cache.version()
        path = config.data_dir() / "memory" / "knowledge.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text('{"concepts": [{"name": "PSNR", "text": "Quality metric"}]}', "utf-8")
        self.assertNotEqual(cache.version(), before)


if __name__ == "__main__":
    unittest.main()
