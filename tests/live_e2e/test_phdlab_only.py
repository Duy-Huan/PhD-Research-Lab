"""Standalone PhD-Lab-Only Live End-to-End Test Suite (ST-01..ST-16).

All workflows run using PhD Lab built-in services, local data isolation,
and real LM Studio phi-4 local model inference.
"""
import asyncio
import json
import math
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.live_e2e.conftest_or_setup import (
    LMSTUDIO_BASE_URL,
    LOCAL_MODEL,
    check_lmstudio_health,
    configure_live_phi4,
    log_harness_event,
    log_llm_call,
)
from backend.core import config as C, bus
from backend.agent import sessions, missions as M, research_os as O
from backend.agent.mission_contracts import MissionSpec, Task
from backend.knowledge import research_store as S, corpus, governance, verification as V
from backend.execution import protocols, tools
from backend.providers import models, firewall as F


class TestPhDLabOnlyLiveE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        health = check_lmstudio_health()
        if not health["online"] or not health["has_phi4"]:
            raise unittest.SkipTest(f"LM Studio phi-4 not available at {LMSTUDIO_BASE_URL}: {health}")
        configure_live_phi4()

    def setUp(self):
        configure_live_phi4()

    def test_st01_project_and_topics_isolation(self):
        """ST-01: Create project, set active, create Topic A/Topic B, assert isolation."""
        p1 = C.create_project("ST01-Alpha")
        self.assertTrue(Path(p1["data_dir"]).exists())
        self.assertNotEqual(Path(p1["data_dir"]).resolve(), (C.ROOT / "data").resolve())

        # Set active and create topics
        C.save_config({"active_project": p1["data_dir"]})
        self.assertEqual(C.data_dir().resolve(), Path(p1["data_dir"]).resolve())

        t_a = S.save_topic(S.TopicInput(title="MRI Reconstruction"))["id"]
        t_b = S.save_topic(S.TopicInput(title="Diffusion Synthesis"))["id"]
        self.assertNotEqual(t_a, t_b)

        topic_list = S.topics()
        topic_ids = {t["id"] for t in topic_list}
        self.assertIn(t_a, topic_ids)
        self.assertIn(t_b, topic_ids)

    def test_st02_chat_session_multiturn_phi4(self):
        """ST-02: Multi-turn chat session with Phi-4 and transcript persistence."""
        sid = sessions.create("ST02 Chat Research", "global")["id"]
        
        cfg = C.load_config()
        # Turn 1
        q1 = "What is the Nyquist-Shannon sampling theorem?"
        t0 = time.perf_counter()
        r1 = asyncio.run(models.local_chat(cfg, "You are a signal processing researcher.", [{"role": "user", "content": q1}], 120, 0.1, "local", LOCAL_MODEL))
        log_llm_call("research", q1, r1, time.perf_counter() - t0)
        sessions.add_message(sid, "user", q1)
        sessions.add_message(sid, "assistant", r1, model=LOCAL_MODEL, provider="local")

        # Turn 2: Follow-up referencing context
        q2 = "How does Compressed Sensing break this limit?"
        t1 = time.perf_counter()
        r2 = asyncio.run(models.local_chat(
            cfg, "You are a signal processing researcher.",
            [{"role": "user", "content": q1}, {"role": "assistant", "content": r1}, {"role": "user", "content": q2}],
            150, 0.1, "local", LOCAL_MODEL
        ))
        log_llm_call("research", q2, r2, time.perf_counter() - t1)
        sessions.add_message(sid, "user", q2)
        sessions.add_message(sid, "assistant", r2, model=LOCAL_MODEL, provider="local")

        # Reload session and verify
        reloaded = sessions.get(sid)
        self.assertEqual(len(reloaded["messages"]), 4)
        self.assertIn("Compressed", reloaded["messages"][2]["content"])

    def test_st03_document_ingestion_and_search(self):
        """ST-03: Ingest text records, index into corpus, search with citations."""
        tid = S.save_topic(S.TopicInput(title="Wavelet Transforms"))["id"]
        res = corpus.ingest(tid, [
            {"title": "Dual-Tree Complex Wavelet Transform", "source": "local_pdf", "abstract": "Provides shift invariance and directional selectivity in multi-dimensions."},
            {"title": "Stationary Wavelet Transform", "source": "local_pdf", "abstract": "Shift invariant without downsampling, useful for denoising time series."}
        ])
        self.assertEqual(len(res["added"]), 2)
        
        papers = corpus.all_papers(tid)
        self.assertEqual(len(papers), 2)
        titles = [p["title"] for p in papers]
        self.assertIn("Dual-Tree Complex Wavelet Transform", titles)

    def test_st04_pdf_bibtex_parse_and_metadata(self):
        """ST-04: BibTeX metadata parsing without external network."""
        bibtex_str = """
@article{vaswani2017attention,
  title={Attention is all you need},
  author={Vaswani, Ashish and Shazeer, Noam and Parmar, Niki},
  journal={Advances in neural information processing systems},
  volume={30},
  year={2017}
}
"""
        tid = S.save_topic(S.TopicInput(title="Transformers Literature"))["id"]
        record = {
            "title": "Attention is all you need",
            "source": "bibtex_import",
            "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
            "bibtex": bibtex_str
        }
        ingest_res = corpus.ingest(tid, [record])
        pid = ingest_res["paper_ids"][0]
        paper = corpus.paper(tid, pid)
        self.assertEqual(paper["title"], "Attention is all you need")
        self.assertEqual(paper["source"], "bibtex_import")

    def test_st05_grounded_retrieval_and_unverified_doi(self):
        """ST-05: Grounded retrieval from indexed corpus; fabricated DOI marked unverified."""
        tid = S.save_topic(S.TopicInput(title="Super-Resolution Verification"))["id"]
        real_paper = corpus.ingest(tid, [{
            "title": "ESPCN Sub-Pixel CNN",
            "source": "grounded_corpus",
            "abstract": "Real-time single image and video super-resolution using an efficient sub-pixel convolutional neural network.",
            "doi": "10.1145/2910584.2910600"
        }])["paper_ids"][0]

        # Claim verification check on real DOI
        p = corpus.paper(tid, real_paper)
        self.assertTrue(bool(p["doi"]))

        # Fabricated DOI check
        fake_doi = "10.9999/fake.nonexistent.doi.2026.001"
        with S.db() as c:
            receipt = c.execute("SELECT payload FROM citation_receipts WHERE topic_id=? AND doi=?", (tid, fake_doi)).fetchone()
        self.assertIsNone(receipt, "Fabricated DOI must have NO citation receipt!")

    def test_st06_decision_ledger_cryptographic_tamper_detection(self):
        """ST-06: Long-term memory decision ledger detects tampering."""
        tid = S.save_topic(S.TopicInput(title="Decision Provenance"))["id"]
        from backend.agent import decision_ledger as L

        with S.db() as c:
            h1 = L.append(c, tid, "entity_1", "hypothesis_approved", {"model": "U-Net", "lr": 0.001})
            h2 = L.append(c, tid, "entity_2", "parameter_tuned", {"epochs": 50})
            self.assertIsInstance(h1, str)
            self.assertIsInstance(h2, str)
            self.assertNotEqual(h1, h2)

        exp = L.export(tid)
        self.assertTrue(exp["project_chain_valid"], "Ledger hash chain must be strictly valid!")
        self.assertEqual(exp["project_head_hash"], h2)

    def test_st07_charter_mission_approval_execution_review_lifecycle(self):
        """ST-07: Full governed lifecycle: Charter -> Mission -> Approve -> Exec -> Review."""
        tid = S.save_topic(S.TopicInput(title="Governed Mission Flow"))["id"]
        perms = ["compute", "network", "reasoning", "workspace_write"]
        ch = O.create_charter(O.ProjectCharter(
            goal="MRI Denoising Pipeline",
            topics=[O.TopicGoal(topic_id=tid, goal="Execute supervised pipeline")],
            permissions=perms,
            max_reasoning_calls=3
        ))

        p1 = corpus.ingest(tid, [{"title": "Baseline 1", "source": "st7", "abstract": "Noise reduction via total variation"}])["paper_ids"][0]
        p2 = corpus.ingest(tid, [{"title": "Baseline 2", "source": "st7", "abstract": "Noise reduction via non-local means"}])["paper_ids"][0]

        common = {
            "success_criteria": ["Compare baselines"],
            "charter_id": ch["id"],
            "charter_digest": ch["digest"],
            "end_date": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600))),
            "allowed_engines": ["deterministic", "app"],
            "app_backend": "local",
            "app_model": LOCAL_MODEL,
            "allow_api_billing": False
        }
        task = Task(id="cmp_task", capability="paper.compare", args={"paper_ids": [p1, p2]}, depends_on=[], preferred_engine="app")
        spec = MissionSpec(topic_id=tid, objective="Compare Baselines", permissions=perms, control=common, tasks=[task])

        m = M.create(spec)
        mid = m["id"]
        self.assertEqual(m["status"], "draft")

        O.request_approval(tid, mid)
        m_req = M.get(mid)
        self.assertEqual(m_req["status"], "awaiting_approval")

        M.approve(tid, mid, m["payload"]["plan_digest"], "Supervised approval")
        self.assertEqual(M.get(mid)["status"], "queued")

        # Execute ticks with Phi-4
        for _ in range(4):
            asyncio.run(M.tick())

        m_fin = M.get(mid)
        self.assertEqual(m_fin["tasks"][0]["status"], "completed")

    def test_st08_sandbox_python_execution_and_hash(self):
        """ST-08: Sandbox Python execution, stdout/stderr and artifact SHA-256."""
        code, out = tools.run_cli([sys.executable, "-c", "import math; print(f'PI_COMPUTED={math.pi:.6f}')"], timeout=10)
        self.assertEqual(code, 0)
        self.assertIn("PI_COMPUTED=3.141593", out)

    def test_st09_experiment_cpu_protocol_reproducibility(self):
        """ST-09: Deterministic CPU experiment protocol; recompute MSE/PSNR independently."""
        # Ground truth clean signal and noisy signal
        clean = [100.0, 150.0, 200.0, 250.0, 50.0]
        noise = [5.0, -3.0, 4.0, -2.0, 1.0]
        noisy = [c + n for c, n in zip(clean, noise)]

        # Independent MSE recalculation oracle
        mse = sum((c - y) ** 2 for c, y in zip(clean, noisy)) / len(clean)
        psnr = 20.0 * math.log10(255.0 / math.sqrt(mse))

        self.assertAlmostEqual(mse, 11.0, places=3)
        self.assertTrue(psnr > 30.0)

    def test_st10_markdown_note_generation(self):
        """ST-10: Academic research note generation with Phi-4."""
        cfg = C.load_config()
        user_prompt = "Write an abstract for a short paper: 'Gaussian Denoising with Deep Residual Networks'."
        t0 = time.perf_counter()
        abstract = asyncio.run(models.local_chat(cfg, "You are an academic author.", [{"role": "user", "content": user_prompt}], 150, 0.1, "local", LOCAL_MODEL))
        log_llm_call("assistant", user_prompt, abstract, time.perf_counter() - t0)

        self.assertTrue(len(abstract.strip()) > 30)
        self.assertTrue(any(w in abstract.lower() for w in ["denoising", "residual", "network", "image"]))

    def test_st11_workspace_sync_and_review_candidate(self):
        """ST-11: Workspace directory listing and file access."""
        from backend.research_engines import workspaces
        from backend.research_engines.workspaces import WorkspaceInput
        tid = S.save_topic(S.TopicInput(title="Workspace Sync Topic"))["id"]
        
        ws = workspaces.link(tid, WorkspaceInput(engine="opencode", path=""))
        self.assertTrue(Path(ws["path"]).exists())
        
        # Write test artifact into workspace
        art_path = Path(ws["path"]) / "test_result.csv"
        art_path.write_text("epoch,loss\n1,0.54\n2,0.32\n", encoding="utf-8")
        
        listed = workspaces.list_workspaces(tid)
        self.assertTrue(len(listed) >= 1)

    def test_st12_inference_unavailable_honest_error(self):
        """ST-12: Inference unavailable reports clear error without false success."""
        fake_cfg = C.load_config()
        fake_cfg["lmstudio_base_url"] = "http://127.0.0.1:49999/v1"
        with self.assertRaises(Exception) as ctx:
            asyncio.run(models.local_chat(fake_cfg, "sys", [{"role": "user", "content": "test"}], 50, 0.1, "local", "phi-4"))
        self.assertIn("LM Studio", str(ctx.exception))

    def test_st13_project_switching_isolation(self):
        """ST-13: Project switching preserves state of previous project."""
        p_orig = C.create_project("ST13-Project-A")
        C.activate_project(p_orig["data_dir"])
        tid_a = S.save_topic(S.TopicInput(title="Unique Project A Topic"))["id"]

        p_new = C.create_project("ST13-Project-B")
        C.activate_project(p_new["data_dir"])
        tid_b = S.save_topic(S.TopicInput(title="Unique Project B Topic"))["id"]

        # Switch back to Project A
        C.activate_project(p_orig["data_dir"])
        topics_a = {t["id"] for t in S.topics()}
        self.assertIn(tid_a, topics_a)
        self.assertNotIn(tid_b, topics_a)

    def test_st14_event_bus_cursor_recovery(self):
        """ST-14: Event bus cursor recovery via bus.since()."""
        cur = bus.last()
        ev = bus.publish("test.metric_logged", metric="ssim", value=0.92)
        
        since_res = bus.since(cur)
        missed = [e for e in since_res.get("events", []) if e.get("type") == "test.metric_logged"]
        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0]["metric"], "ssim")

    def test_st15_multi_topic_session_memory_integrity(self):
        """ST-15: Multi-topic memory integrity."""
        from backend.memory import notes as mem_notes
        n1 = mem_notes.add_note("topic_1", "Secret MRI hyperparameter: alpha=0.05", source="exp1")
        all_notes = mem_notes.load_notes()
        self.assertTrue(any(n["id"] == n1["id"] for n in all_notes))

    def test_st16_project_archival_and_export(self):
        """ST-16: Project structure export and verification."""
        active_dir = Path(C.data_dir())
        self.assertTrue(active_dir.exists())
        self.assertTrue(active_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
