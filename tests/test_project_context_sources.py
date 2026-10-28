"""FQC-COVERAGE-662: shared conversation context — selected sources (reference with PDF text, failed extraction,
memory, run, attachment, note) and approved workspace actions executed through the same services as the UI."""
import unittest

import _env
from backend.agent import project_context as P
from backend.knowledge import library
from pdfgen import make_pdf


class Sources(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"ctx-{self._testMethodName[:30]}")

    def test_reference_sources_with_pdf_text_and_failed_extraction(self):
        entry = library.ingest_pdf("paper.pdf", make_pdf([[(12, "Diffusion denoising for MRI")]]))
        key = next(e["key"] for e in library.included())
        self.assertIsNone(P.resolve_source("ref:missing"))
        brief = P.resolve_source("ref:" + key)
        self.assertNotIn("extraction", brief)
        full = P.resolve_source("ref:" + key, expanded=True)
        self.assertIn("Diffusion denoising", full["text"])
        self.assertEqual(full["extraction"]["pages_total"], 1)
        (library.refs_dir() / entry["file"]).write_bytes(b"%PDF-broken")
        failed = P.resolve_source("ref:" + key, expanded=True)
        self.assertTrue(failed["extraction"]["limited"])
        self.assertIn("error", failed["extraction"])

    def test_unknown_or_missing_records_resolve_to_nothing(self):
        for sid in ("mem:nope", "run:nope", "att:nope", "note:nope", "other:x"):
            with self.subTest(sid):
                self.assertIsNone(P.resolve_source(sid))
        from backend.memory.notes import add_note
        note = add_note("data", "Remember the baseline")
        self.assertEqual(P.resolve_source("note:" + note["id"])["text"], "Remember the baseline")
        self.assertIsNone(P.Adapter().resolve("x"))
        self.assertEqual(P.Adapter().identity()["module"], "global")


class Actions(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project(f"act-{self._testMethodName[:30]}")
        from backend.agent import sessions
        self.session = sessions.create("Context actions")

    def test_approved_actions_use_the_domain_services(self):
        from backend.execution.code_projects import active_dir
        (active_dir() / "train.py").write_text("print(1)", "utf-8")
        remote = P.execute("prepare_remote_experiment", {"files": ["train.py"]}, self.session)
        self.assertEqual(remote["status"], "awaiting_approval")
        first = P.execute("write_section", {"section": "introduction", "text": "First draft", "title": "Paper"}, self.session)
        second = P.execute("write_section", {"section": "introduction", "text": "Second draft"}, self.session)
        self.assertEqual((first["previous_kept"], second["previous_kept"]), (False, True))
        from backend.paper.writer import load_project
        project = load_project()
        self.assertEqual((project["title"], project["section_state"]["introduction"]), ("Paper", "drafted"))
        self.assertTrue(project["section_history"]["introduction"])
        self.assertTrue(P.execute("add_note", {"text": "n"}, self.session)["note"])
        self.assertTrue(P.execute("create_hypothesis", {"text": "H1 holds"}, self.session)["hypothesis"])
        self.assertTrue(P.execute("propose_gap", {"text": "No study covers X"}, self.session)["decision"])
        self.assertTrue(P.execute("pin_result", {"kind": "result", "title": "T", "research_run": "r1"}, self.session)["pin"])
        candidate = P.execute("record_result", {"text": "Accuracy 0.9", "type": "experiment"}, self.session)
        self.assertIn("candidate", candidate)


if __name__ == "__main__":
    unittest.main()
