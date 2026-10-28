"""FQC-COVERAGE-662: PaperOrchestra mission dispatcher for every capability (outline, section, citation check,
refinement, figure integration, full orchestration) and the L4 spec with an approved experiment.

Writing back ends (which call models) return fixed text; artifacts, project sections and citation checks are real.
"""
import asyncio
import unittest
from unittest.mock import patch

import _env  # noqa: F401
from backend.agent.mission_contracts import Task
from backend.paper import writer
from backend.research_engines.paperorchestra import modes as M
from backend.research_engines.paperorchestra.contracts import PaperOutline
import test_paperorchestra as PO  # module import: its own test class is not collected twice


def outline():
    return PaperOutline.model_validate({"paper_title": "Attention survey", "abstract_summary": "Survey", "sections": [
        {"section_id": "introduction", "title": "Introduction", "bullet_points": ["motivation"], "citation_hints": ["vaswani2017"]},
        {"section_id": "methods", "title": "Methods", "bullet_points": ["model"], "citation_hints": []}]})


class Dispatch(unittest.TestCase):
    setUp = PO.TestPaperOrchestraIntegration.setUp
    tearDown = PO.TestPaperOrchestraIntegration.tearDown

    def mission(self, tasks=()):
        return {"id": "m-po", "topic_id": "top-po", "payload": {"spec": {"objective": "Survey attention", "inputs": ["vaswani2017"]}},
                "tasks": list(tasks)}

    def run_task(self, capability, args=None, tasks=()):
        task = Task(id="t-" + capability.split(".")[-1], capability=capability, args=args or {}, preferred_engine="paperorchestra")
        return asyncio.run(M.execute_mission_task(self.mission(tasks), task, "key"))

    def test_outline_and_section_writing_store_artifacts(self):
        with patch.object(M, "generate_outline", return_value=outline()):
            out = self.run_task("paperorchestra.outline", {"style": "ACM"})
        self.assertEqual((out.status, out.output["outline"]["paper_title"]), ("completed", "Attention survey"))
        previous = [{"id": "outline", "payload": {"result": {"output": {"outline": "ctx"}}}}]
        with patch.object(M, "write_section", return_value="Intro text [vaswani2017]") as write:
            out = self.run_task("paperorchestra.section_write", {"section": "introduction", "from_task": "outline"}, previous)
        self.assertIn("ctx", write.call_args.args[3], "the previous task's output is the writing context")
        self.assertEqual(out.output["section"], "introduction")
        self.assertIn("Intro text", writer.load_project()["sections"]["introduction"])

    def test_citation_check_uses_previous_text_or_the_project(self):
        previous = [{"id": "sec", "payload": {"result": {"output": {"text": "As shown in \\cite{vaswani2017}."}}}}]
        out = self.run_task("paperorchestra.cite_verify", {"from_task": "sec"}, previous)
        self.assertEqual(out.status, "completed")
        self.assertIn("report", out.output)
        project = writer.load_project()
        project.setdefault("sections", {})["introduction"] = "Uses \\cite{unknown2099}."
        writer.save_project(project)
        out = self.run_task("paperorchestra.cite_verify", {"from_task": "missing"})
        self.assertIn("unknown2099", str(out.output["report"]))

    def test_refine_figure_and_full_orchestration(self):
        project = writer.load_project()
        project.setdefault("sections", {}).update(introduction="Draft intro", experiments="Results")
        writer.save_project(project)
        with patch.object(M, "refine_and_polish", side_effect=lambda sid, text, *a: text + " (polished)"):
            out = self.run_task("paperorchestra.refine")
        self.assertIn("introduction", out.output["refined_sections"])
        out = self.run_task("paperorchestra.figure_integrate", {"figure_id": "fig1"})
        again = self.run_task("paperorchestra.figure_integrate", {"figure_id": "fig1"})
        self.assertEqual(writer.load_project()["sections"]["experiments"].count("fig:fig1"), 1, "a figure is integrated once")
        self.assertEqual(again.output["status"], "integrated")
        with patch.object(M, "generate_outline", return_value=outline()), \
                patch.object(M, "write_section", side_effect=lambda tid, sid, *a: f"Text for {sid}"):
            out = self.run_task("paperorchestra.full_orchestration")
        self.assertIn("Text for methods", out.output["manuscript"])
        self.assertIn("pending human review", out.limitations[0])
        with self.assertRaisesRegex(ValueError, "Unknown PaperOrchestra capability"):
            self.run_task("paperorchestra.translate")

    def test_l4_spec_with_an_approved_experiment_requests_compute(self):
        spec = M.create_l4_research_to_paper_mission(topic_id="top-po", objective="Study", paper_ids=["vaswani2017"],
                                                     protocol_id="p1", protocol_digest="d", approval_nonce="n")
        ids = [t.id for t in spec.tasks]
        self.assertEqual(ids[2:4], ["experiment", "verify_experiment"])
        self.assertIn("compute", spec.permissions)
        self.assertEqual(spec.tasks[4].depends_on, ["verify_experiment"])


if __name__ == "__main__":
    unittest.main()
