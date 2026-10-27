"""Controlled native model-role adapter contracts; not a multi-agent/live qualification."""
import _env
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.research_engines.contracts import EngineTask, EngineFailure
from backend.research_engines import registry
from backend.providers import research as RP
from backend.agent import skills
from backend.core import config


class TestPhDLabNativeWorkflow(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project('native-role-adapter')
    def test_phdlab_engine_registry_and_plan(self):
        # 1. Registered in FACTORIES
        self.assertIn("phdlab", registry.FACTORIES)

        # 2. Can instantiate engine
        engine = registry.get("phdlab")
        self.assertEqual(engine.descriptor.id, "phdlab")
        self.assertIn("literature", engine.descriptor.capabilities)
        self.assertIn("review", engine.descriptor.capabilities)
        self.assertIn("analysis", engine.descriptor.capabilities)

        # 3. plan with mode="phdlab" returns ["phdlab"]
        self.assertEqual(registry.plan("phdlab", "literature"), ["phdlab"])
        self.assertEqual(registry.plan("phdlab", "review"), ["phdlab"])
        self.assertEqual(registry.plan("phdlab", "analysis"), ["phdlab"])

        # 4. plan with preferred="phdlab" returns ["phdlab"]
        self.assertEqual(registry.plan("auto", "literature", preferred="phdlab"), ["phdlab"])

    def test_retired_opencode_is_absent_and_integrated_engines_are_preserved(self):
        self.assertNotIn('opencode',RP.CATALOG)
        self.assertIn('paperorchestra',RP.CATALOG)
        self.assertIn('paperorchestra',registry.FACTORIES)
        with self.assertRaises(EngineFailure):registry.plan('auto','prototype',preferred='opencode')

    def test_phdlab_provider_describe(self):
        self.assertIn("phdlab", RP.CATALOG)
        d = RP.describe("phdlab")
        self.assertEqual(d["state"], "READY")
        self.assertTrue(d["ready"])

        pid, note = RP.pick("phdlab")
        self.assertEqual(pid, "phdlab")

    def test_phdlab_engine_execute(self):
        engine = registry.get("phdlab")
        events = []

        with tempfile.TemporaryDirectory(dir=config.data_dir()) as td:
            out_dir = Path(td)
            task = EngineTask(
                operation_id="RR-12345678:S1",
                attempt=1,
                project_id="test-proj",
                workflow_id="wf-1",
                step_id="S1",
                question="Survey token pruning techniques for Vision Transformers",
                context="Background context on ViT",
                capability="literature",
                output_dir=out_dir,
            )

            mock_llm_response = "# Survey Report\n\nToken pruning reduces ViT FLOPs significantly."
            mock_sources = [{
                "id": "S1",
                "kind": "paper",
                "title": "Fast ViT",
                "url": "https://doi.org/10.1234/vit",
                "authors": ["John Doe"],
                "year": 2024,
                "venue": "NeurIPS",
                "citations": 42,
                "abstract": "Token pruning in ViT."
            }]
            with patch("backend.providers.research.app_complete", return_value=mock_llm_response), \
                 patch("backend.knowledge.websearch.search", return_value={"sources": mock_sources}):
                result = engine.execute(task, emit=lambda ev: events.append(ev), cancelled=lambda: False)

            self.assertEqual(result.engine, "phdlab")
            self.assertEqual(result.text, mock_llm_response)
            self.assertTrue(len(result.artifact_refs) >= 1)
            self.assertTrue((out_dir / "phdlab_research_report.md").is_file())
            self.assertEqual((out_dir / "phdlab_research_report.md").read_text(encoding="utf-8"), mock_llm_response)

    def test_phdlab_skill_registered(self):
        skill_names = [s["name"] for s in skills.catalog()]
        self.assertIn("phdlab", skill_names)
        s = skills.get("phdlab")
        self.assertEqual(s["provider"], "phdlab")
        self.assertEqual(s["pipeline"], "research")
