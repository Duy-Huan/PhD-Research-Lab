"""FQC-PAPER-EVIDENCE-664 (agent/PLAN_6.6.4_L3.md A6): the paper writer works from the library and measured runs.

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): full orchestration wrote from the objective only, so the
draft had no citations and no measured numbers; an agent-style answer (an approval plan) was stored as a section; the gates
passed a draft with zero citations; when no model answered, the writer stored template prose claiming confirmed hypotheses;
and the agent had no tool to list the library. Real topic, papers, protocol run and verification in a disposable
PHDLAB_DATA_DIR; only the writing model is replaced by fixed answers."""
import asyncio
import time
import unittest
from unittest.mock import patch

import _env
from backend.agent import missions as MI
from backend.agent.mission_contracts import Task
from backend.execution import protocols as P
from backend.execution.protocol_contracts import ExperimentProtocol
from backend.knowledge import corpus, research_store as S
from backend.paper import writer
from backend.research_engines.paperorchestra import modes as M
from backend.tools import registry
from backend.tools.spec import ToolError

APPROVAL_PLAN = ("Kế hoạch phê duyệt:\n1. Viết phần giới thiệu\n2. Chờ bạn duyệt trước khi chạy\n"
                 "→ /accept <số|all> · /reject <số|all>")


def bib_key(pid: str) -> str:
    """The key corpus.bibliography has always written; the writer and the citation check must use the same one."""
    return "skb_" + pid.replace("-", "")[:12]


def section(key: str = "", words: int = 40) -> str:
    cite = f" as shown by \\cite{{{key}}}" if key else ""
    return ("Here is the section:\n```latex\n" + " ".join(["Measured denoising evidence"] * (words // 3)) + cite +
            ".\n```\nLet me know if you want changes.")


class PaperEvidence(unittest.TestCase):
    def setUp(self):
        _env.isolate_config(self)
        _env.fresh_project("paper evidence tests", code_project=None)
        self.tid = _env.legacy_topic(S.TopicInput(title="Denoising"))["id"]
        ids = corpus.ingest(self.tid, [
            {"title": "Smoothing filters for Gaussian noise", "abstract": "Local averaging reduces Gaussian noise.", "year": 2019,
             "venue": "Signal Letters", "source": "fixture"},
            {"title": "A candidate not yet reviewed", "abstract": "Unreviewed.", "year": 2021, "source": "fixture"}])["paper_ids"]
        corpus.curate(self.tid, ids[:1], "accept")
        self.accepted, self.candidate = ids
        self.key = bib_key(self.accepted)

    def mission(self):
        return {"id": "m-pe", "topic_id": self.tid, "payload": {"spec": {"objective": "Does smoothing reduce noise?", "inputs": []}}, "tasks": []}

    def run_task(self, capability, args=None):
        task = Task(id="t", capability=capability, args=args or {}, preferred_engine="paperorchestra")
        return asyncio.run(M.execute_mission_task(self.mission(), task, "key"))

    def measured_run(self):
        p = P.create(ExperimentProtocol(topic_id=self.tid, hypothesis="Smoothing reduces synthetic noise"))
        p = P.approve(self.tid, p["id"], p["digest"], "Reviewed fixed protocol")
        m = P.mission_draft(self.tid, p["id"])
        MI.approve(self.tid, m["id"], m["payload"]["plan_digest"], "Offline CPU approved")
        for _ in range(4):
            asyncio.run(MI.tick())
        return P.runs(self.tid)[0]

    def test_full_orchestration_gives_the_writer_the_library_and_measured_runs(self):
        run = self.measured_run()
        prompts = []

        def model(role, system, user, max_tokens=0):
            prompts.append(user)
            return section(self.key)
        with patch("backend.providers.research.app_complete", side_effect=model):
            out = self.run_task("paperorchestra.full_orchestration")
        writer_prompts = [p for p in prompts if "Evidence:" in p]
        self.assertTrue(writer_prompts)
        evidence = writer_prompts[0]
        self.assertIn(f"- {self.key}: Smoothing filters for Gaussian noise (2019, Signal Letters)", evidence)
        self.assertIn(f"{bib_key(self.candidate)} [not yet accepted into the bibliography]", evidence)
        self.assertIn(f"experiment:{run['id']} [verified, not reproduced]", evidence)
        self.assertIn(f"{run['payload']['comparison']['paired_psnr_gain_db']:.6g} dB", evidence)
        report = out.output["quality_report"]
        self.assertTrue(report["manuscript"]["passed"], report["manuscript"])
        self.assertTrue(report["citations"]["passed"])
        self.assertNotIn("Here is the section", out.output["manuscript"])
        self.assertIn(f"\\cite{{{self.key}}}", out.output["manuscript"])
        self.assertIn(self.key, corpus.bibliography(self.tid))  # the cite key is the bibliography's key

    def test_without_a_model_the_writer_fails_instead_of_inventing_text(self):
        for capability, args in (("paperorchestra.section_write", {"section": "introduction"}), ("paperorchestra.full_orchestration", {})):
            with self.subTest(capability=capability), \
                    patch("backend.providers.research.app_complete", side_effect=RuntimeError("no engine")), \
                    self.assertRaisesRegex(ValueError, "unavailable"):
                self.run_task(capability, args)
        sections = writer.load_project().get("sections", {})
        self.assertFalse(any("hypotheses hold" in text for text in sections.values()))
        self.assertNotIn("introduction", sections)

    def test_agent_text_is_rejected_and_chat_around_latex_is_removed(self):
        with patch("backend.providers.research.app_complete", return_value=APPROVAL_PLAN), \
                self.assertRaisesRegex(ValueError, "agent text"):
            self.run_task("paperorchestra.section_write", {"section": "introduction"})
        with patch("backend.providers.research.app_complete",
                   return_value="Sure! I'll write it now.\n" + section(self.key) + "\nWould you like a shorter version?"):
            out = self.run_task("paperorchestra.section_write", {"section": "introduction"})
        text = writer.load_project()["sections"]["introduction"]
        self.assertTrue(text.startswith("\\section{"), text[:80])
        for chat in ("Sure!", "Here is", "Let me know", "Would you like", "```"):
            self.assertNotIn(chat, text)
        self.assertEqual(out.status, "completed")

    def test_gates_reject_empty_agent_and_uncited_drafts(self):
        from backend.research_engines.paperorchestra.quality_gates import check_manuscript, evaluate_quality_gates
        good = {"introduction": section(self.key).split("```latex\n")[1].split("\n```")[0]}
        self.assertTrue(check_manuscript(self.tid, good).passed)
        cases = {"empty": {"introduction": good["introduction"], "methods": "\\section{Methods}"},
                 "agent": {"introduction": good["introduction"], "methods": APPROVAL_PLAN},
                 "uncited": {"introduction": " ".join(["Plain text without any reference"] * 12)},
                 "nothing": {}}
        for name, sections in cases.items():
            with self.subTest(name=name):
                report = evaluate_quality_gates(self.tid, sections)
                self.assertFalse(report.manuscript.passed, report.manuscript)
                self.assertFalse(report.overall_readiness)
        self.assertEqual(check_manuscript(self.tid, cases["empty"]).empty_sections, ["methods"])
        self.assertEqual(check_manuscript(self.tid, cases["agent"]).agent_text_sections, ["methods"])
        self.assertIn("cites none", " ".join(check_manuscript(self.tid, cases["uncited"]).issues))
        empty_topic = _env.legacy_topic(S.TopicInput(title="No library"))["id"]
        self.assertTrue(check_manuscript(empty_topic, cases["uncited"]).passed)  # no library: no citation is required

    def test_library_tools_list_papers_and_passages_with_cite_keys(self):
        from backend.tools import library_tools as LT
        listed = LT.search({"topic_id": self.tid}, None)
        self.assertEqual(listed["total"], 2)
        first = next(p for p in listed["papers"] if p["paper_id"] == self.accepted)
        self.assertEqual((first["cite_key"], first["in_bibliography"], first["full_text"]), (self.key, True, False))
        found = LT.search({"topic_id": self.tid, "query": "Gaussian"}, None)
        self.assertEqual([p["paper_id"] for p in found["papers"]], [self.accepted])
        passages = LT.passages({"topic_id": self.tid, "query": "Gaussian noise"}, None)["passages"]
        self.assertEqual((passages[0]["cite_key"], passages[0]["trust"]), (self.key, "untrusted"))
        self.assertIn("Local averaging", passages[0]["text"])
        for fn, args in ((LT.search, {"topic_id": "nope"}), (LT.passages, {"topic_id": "nope", "query": "x"})):
            with self.subTest(fn=fn.__name__), self.assertRaises(ToolError) as e:
                fn(args, None)
            self.assertEqual(e.exception.code, "not_found")
        specs = {s.id: s for s in registry.builtin_specs()}
        for tid in ("library.search", "library.passages"):
            self.assertEqual((specs[tid].mutates, specs[tid].permissions), (False, []))

    def test_evidence_is_bounded_and_quick(self):
        from backend.research_engines.paperorchestra.evidence import MAX_CHARS, gather
        corpus.ingest(self.tid, [{"title": f"Paper {i}", "abstract": "x " * 400, "source": "fixture"} for i in range(60)])
        t0 = time.monotonic()
        pack = gather(self.tid)
        self.assertLess(time.monotonic() - t0, 5.0)
        self.assertLessEqual(len(pack.text), MAX_CHARS)
        self.assertEqual(len(pack.keys), 40)
        self.assertEqual(gather("unknown-topic").keys, [])


if __name__ == "__main__":
    unittest.main()
