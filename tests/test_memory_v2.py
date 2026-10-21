import _env  # noqa: F401  (must be first)
import json
import unittest
from unittest import mock

from backend import memory as M
from backend.memory import compiler, compressor, lod, pages, research, retrieval
from backend.memory.embeddings import hashing_vector, tokenize


def cosine(a: list, b: list) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    return dot / ((math.sqrt(sum(x * x for x in a)) or 1.0) * (math.sqrt(sum(y * y for y in b)) or 1.0))


def _session(sid, tool, msgs, updated="2026-01-01T00:00:00+00:00"):
    from backend.agent.sessions import _dir as _sess_dir
    d = _sess_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sid}.json").write_text(json.dumps({"id": sid, "tool": tool, "title": f"chat {sid}", "updated": updated,
                                                "messages": msgs}), "utf-8")


class ResearchMemory(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("research-mem")

    def test_plan_sync_keeps_stable_ids(self):
        a = research.sync_from_plan(["H1: Attention improves PSNR", "H2: Noise hurts SAM"])
        self.assertEqual([h["id"] for h in a], ["HYPE-001", "HYPE-002"])
        b = research.sync_from_plan(["H1: Attention improves PSNR on Pavia", "H2: Noise hurts SAM", "H3: New idea"])
        self.assertEqual([h["id"] for h in b], ["HYPE-001", "HYPE-002", "HYPE-003"])
        self.assertIn("Pavia", research.load()["hypotheses"][0]["text"])


    def test_failure_validation(self):
        with self.assertRaises(research.ResearchError):
            research.add_failure("  ")
        f = research.add_failure("Dropout 0.5 diverges", reason="loss NaN")
        self.assertTrue(f["validated"])




class Retrieval(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("retrieval")
        research.add_hypothesis("Spectral attention improves hyperspectral super-resolution")
        h2 = research.add_hypothesis("Larger batch size reduces SAM error")
        research.add_experiment({"title": "batch sweep", "hypothesis_id": h2["id"], "clearml_task_id": "f" * 32,
                                 "interpretation": "batch 64 lowest SAM"})
        M.add_decision("Use the Pavia University dataset only", "constraint")

    def test_bm25_and_vectors(self):
        bm = retrieval.BM25(["alpha beta", "gamma delta", "alpha alpha"]).scores("alpha")
        self.assertGreater(bm[2], bm[0])
        self.assertEqual(bm[1], 0.0)
        self.assertGreater(cosine(hashing_vector("spectral attention"), hashing_vector("attention spectral model")), 0.3)
        self.assertIn("hype-001", tokenize("see HYPE-001 now"))

    def test_exact_id_and_graph_hit(self):
        nodes = lod.collect()
        cfg = _env.config.load_config()
        res = retrieval.search("f" * 32, nodes, cfg)
        self.assertEqual(res["hits"][0]["id"], "EXP-001")  # keyword index catches the ClearML task id
        ids = [h["id"] for h in res["hits"]]
        self.assertIn("HYPE-002", ids)  # graph expansion: experiment → hypothesis
        self.assertIn("hashing", res["diagnostics"]["vector_engine"])

    def test_rrf_is_deterministic(self):
        self.assertEqual(retrieval.rrf([["a", "b"], ["b", "a"]]), retrieval.rrf([["b", "a"], ["a", "b"]]))

    def test_compiler_format_budget_and_determinism(self):
        a = compiler.compile_context("lit2plan", "", "batch size SAM", 1200)
        b = compiler.compile_context("lit2plan", "", "batch size SAM", 1200)
        self.assertEqual(a["text"], b["text"])
        t = a["text"]
        self.assertTrue(t.startswith("[CONTEXT SYSTEM INJECTION]"))
        for h in ("### CURRENT WORKING STATE", "### RELATED EXPERIMENT EVIDENCE (ClearML Pointer)", "### FOUNDATIONAL SCIENTIFIC KNOWLEDGE"):
            self.assertIn(h, t)
        self.assertIn("ClearML task `" + "f" * 32 + "`", t)
        self.assertLessEqual(a["tokens"], 1200 * 1.15)
        self.assertIn("research", a["skeleton"])

    def test_purged_nodes_are_excluded(self):
        out = compiler.compile_context("x", "", "batch size", 2000, purged={"EXP-001"})
        self.assertNotIn("EXP-001", out["text"])


class Compressor(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("compress")
        self.cfg = _env.config.load_config()
        self.cfg["memory"].update(high_watermark_tokens=300, low_watermark_tokens=50, chunk_tokens=120, min_keep_messages=2)
        msgs = [{"role": "user" if i % 2 == 0 else "assistant",
                 "content": f"turn {i} run 20260101-120000-ab{i:02x} commit a1b2c3d{i} " + "word " * 60} for i in range(12)]
        _session("sA", "lit2plan", msgs)

    def test_plan_respects_watermarks_and_keeps_recent(self):
        p = compressor.plan(self.cfg)
        self.assertTrue(p["trigger"])
        sp = p["spans"][0]
        self.assertEqual(sp["start"], 0)
        self.assertLessEqual(sp["end"], 10)  # last 2 messages stay raw
        self.cfg["memory"]["high_watermark_tokens"] = 10 ** 9
        self.assertFalse(compressor.plan(self.cfg)["trigger"])


    def test_failed_chunk_does_not_advance_pointer(self):
        async def boom(*a, **k):
            raise RuntimeError("model offline")
        with mock.patch("backend.providers.models.call_agent", side_effect=boom):
            rep = _env.run_async(compressor.compress(cfg=self.cfg))
        self.assertEqual(rep["episodes"], 0)
        self.assertTrue(rep["errors"])
        self.assertNotIn("sA", M.load()["summarized"])

    def test_markdown_fallback_and_entities(self):
        m = compressor.parse_memo("TITLE: Free text\nNot JSON at all", "fb")
        self.assertFalse(m["structured"])
        self.assertEqual(m["title"], "Free text")
        ents = compressor.entities("task " + "0123456789abcdef" * 2 + " HYPE-004 sha deadbeef1 run 20250101-101010-00ff")
        self.assertIn("clearml:" + "0123456789abcdef" * 2, ents)
        self.assertIn("HYPE-004", ents)
        self.assertIn("run:20250101-101010-00ff", ents)


if __name__ == "__main__":
    unittest.main()
