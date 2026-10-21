import _env  # noqa: F401  (must be first)
import json
import threading
import unittest

from backend import memory as M
from backend.memory import cache, compiler, engine, evidence, lifecycle, policy, research, state, trace
from memory_eval import golden


def _hashing():
    _env.config.save_config({"memory": {"embed_engine": "hashing"}})


class ResearchState(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("state33")
        _hashing()
        self.ids = golden.seed()

    def test_state_fields(self):
        st = state.current()
        self.assertEqual(st["active_hypotheses"][0]["id"], "HYPE-002")  # the one under test
        self.assertEqual(st["current_experiment"]["id"], "EXP-004")
        self.assertIn("FAIL-001", [f["id"] for f in st["known_failures"]])
        self.assertTrue(st["hardware"])
        self.assertEqual(st["best_results"]["PSNR"]["value"], 31.42)  # validated evidence
        self.assertIn("CAVE-v2", st["datasets"])


    def test_superseded_decision_leaves_state_but_is_kept(self):
        new = M.add_decision("Use CAVE-v2 and ICVL for every comparison", supersedes=self.ids["dec_dataset"])
        st = state.current()
        ids = [d["id"] for d in st["recent_decisions"]]
        self.assertIn(new["id"], ids)
        self.assertNotIn(self.ids["dec_dataset"], ids)
        old = next(d for d in M.load()["decisions"] if d["id"] == self.ids["dec_dataset"])
        self.assertEqual(old["superseded_by"], new["id"])  # never deleted


class Policies(unittest.TestCase):
    def test_roles_and_budget(self):
        self.assertEqual(policy.resolve_role("", "lit2plan"), "literature")
        self.assertEqual(policy.resolve_role("paper_reviewer"), "reviewer")
        self.assertEqual(policy.resolve_role("nonsense", "nonsense"), "default")
        b = policy.Budget(max_tokens=4000, reserved_tokens=500, system_tokens=300, task_tokens=200, safety_margin=0.1)
        self.assertEqual(b.memory_budget, int(3000 * 0.9))
        sec = b.split(policy.POLICIES["reviewer"])
        self.assertLessEqual(sum(sec.values()), b.memory_budget)
        self.assertGreater(sec["evidence"], sec["working"])  # reviewer: evidence very high
        lit = policy.Budget(4000).split(policy.POLICIES["literature"])
        self.assertGreater(lit["knowledge"], lit["working"])


class RetrievalV33(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("retr33")
        _hashing()
        golden.seed()

    def test_every_hit_is_explained(self):
        res = engine.retrieve(engine.build_context("Why did model SwinIR-large fail?", role="experiment_designer"))
        top = res["hits"][0]
        self.assertEqual(top["id"], "FAIL-001")
        for k in ("relevance", "importance", "recency", "confidence", "evidence_strength", "research_centrality",
                  "failure_prevention", "task_fit", "low_confidence"):
            self.assertIn(k, top["components"])
        self.assertTrue(top["reasons"])
        self.assertTrue(any(v for v in top["ranks"].values()))

    def test_metadata_filters(self):
        ctx = engine.build_context("PSNR results", filters={"dataset": "ICVL", "types": ["experiment"]})
        ids = [h["id"] for h in engine.retrieve(ctx)["hits"]]
        self.assertEqual(ids, ["EXP-005"])
        with self.assertRaises(ValueError):
            engine.build_context("x", filters={"colour": "red"})

    def test_temporal_current_penalises_refuted_but_history_keeps_it(self):
        cur = engine.retrieve(engine.build_context("current hypothesis total variation prior"))
        hist = engine.retrieve(engine.build_context("history of the total variation prior hypothesis"))
        c = next(h for h in cur["hits"] if h["id"] == "HYPE-003")
        h = next(h for h in hist["hits"] if h["id"] == "HYPE-003")
        self.assertGreater(c["components"]["low_confidence"], 0)
        self.assertEqual(h["components"]["low_confidence"], 0)

    def test_failure_memory_is_found_when_planning(self):
        research.add_failure("CUDA OOM with Restormer at 512px", model="Restormer", dataset="CAVE-v2",
                             environment="RTX 3060 12GB", configuration="patch 512, batch 6", error="CUDA out of memory",
                             cause="activation memory", lesson="use patch 256 under 12 GB", avoidance_rule="patch <= 256")
        ids = [h["id"] for h in engine.retrieve(engine.build_context("Plan a Restormer experiment on CAVE", role="experiment_designer"))["hits"][:5]]
        self.assertIn("FAIL-003", ids)
        with self.assertRaises(research.ResearchError):
            research.add_failure("x", colour="red")


    def test_deterministic(self):
        q = engine.build_context("Should we use Swin Transformer?", role="experiment_designer")
        a = [h["id"] for h in engine.retrieve(q)["hits"]]
        cache.clear_all()
        b = [h["id"] for h in engine.retrieve(engine.build_context("Should we use Swin Transformer?", role="experiment_designer"))["hits"]]
        self.assertEqual(a, b)


class CacheInvalidation(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("cache33")
        _hashing()
        golden.seed()

    def test_write_invalidates_and_repeat_hits(self):
        q = "Restormer patch size failure"
        r1 = engine.retrieve(engine.build_context(q))
        r2 = engine.retrieve(engine.build_context(q))
        self.assertTrue(r2["diagnostics"]["cache_hit"])
        research.add_failure("Restormer patch size 512 crashed", reason="OOM")
        r3 = engine.retrieve(engine.build_context(q))
        self.assertFalse(r3["diagnostics"]["cache_hit"])
        self.assertIn("FAIL-003", [h["id"] for h in r3["hits"]])
        self.assertNotIn("FAIL-003", [h["id"] for h in r1["hits"]])

    def test_external_edit_invalidates(self):
        q = "Mamba state space model"
        engine.retrieve(engine.build_context(q))
        p = M.mem_dir() / "research.json"
        d = json.loads(p.read_text("utf-8"))
        d["hypotheses"].append({"id": "HYPE-077", "text": "Mamba state space model beats Swin", "status": "testing",
                                "source": "hand", "plan_key": "", "created": "2026-01-01T00:00:00+00:00", "updated": "2026-01-01T00:00:00+00:00"})
        p.write_text(json.dumps(d), "utf-8")  # written by "another process": no generation bump
        ids = [h["id"] for h in engine.retrieve(engine.build_context(q))["hits"]]
        self.assertIn("HYPE-077", ids)



class CompilerV33(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("comp33")
        _hashing()
        golden.seed()

    def test_state_first_sections_trace(self):
        c = compiler.compile_context("experiment", "", "Should we use Swin Transformer?", 2500, role="experiment_designer")
        t = c["text"]
        self.assertTrue(t.startswith("[CONTEXT SYSTEM INJECTION]\n### RESEARCH STATE"))
        for h in ("### CURRENT WORKING STATE", "### RELATED EXPERIMENT EVIDENCE (ClearML Pointer)", "### EVIDENCE & CLAIMS",
                  "### FOUNDATIONAL SCIENTIFIC KNOWLEDGE"):
            self.assertIn(h, t)
        self.assertIn("HYPE-002", t)
        self.assertIn("FAIL-001", t)
        self.assertEqual(c["role"], "experiment_designer")
        tr = c["trace"]
        self.assertTrue(tr["selected"])
        self.assertTrue(all(s["reasons"] for s in tr["selected"]))
        self.assertLessEqual(c["tokens"], 2500 * 1.1)
        txt = compiler.trace_text(c)
        self.assertIn("CONTEXT TRACE", txt)
        self.assertIn("Dropped:", txt)

    def test_duplicates_dropped_and_small_budget_compresses(self):
        for _ in range(2):
            M.add_decision("Train every model with the L1 loss and cosine learning-rate schedule", kind="constraint", locked=False)
        c = compiler.compile_context("data", "", "L1 loss cosine learning-rate schedule", 3000)
        self.assertTrue(any(d["reason"].startswith("duplicate of") for d in c["trace"]["dropped"]))
        small = compiler.compile_context("data", "", "Should we use Swin Transformer?", 500, role="experiment_designer")
        self.assertLessEqual(small["tokens"], 650)
        self.assertIn("HYPE-002", small["text"])  # research state survives a tiny budget



class EvidenceLayer(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("evid33")
        golden.seed()

    def test_claim_status_and_ai_cannot_validate(self):
        c = evidence.add_claim("TV prior improves PSNR at sigma 50", hypothesis_id="HYPE-003", source_refs=["lit:rudin1992tv"])
        ai = evidence.add_evidence({"claim_id": c["id"], "experiment_id": "EXP-005", "stance": "supports", "status": "validated"},
                                   origin="provider:codex")
        self.assertEqual(ai["status"], "candidate")
        self.assertEqual(evidence.get(c["id"])["status"], "proposed")
        h = evidence.add_evidence({"claim_id": c["id"], "experiment_id": "EXP-005", "stance": "refutes", "status": "validated"})
        self.assertEqual(h["git_sha"], "5e6f708192a3b4c5")  # provenance copied from the experiment
        self.assertEqual(h["dataset_version"], "ICVL-v1")
        self.assertEqual(evidence.get(c["id"])["status"], "refuted")
        with self.assertRaises(evidence.EvidenceError):
            evidence.delete(h["id"])  # validated evidence is kept for provenance
        with self.assertRaises(evidence.EvidenceError):
            evidence.add_claim("x", source_refs=["../../etc/passwd"])
        with self.assertRaises(evidence.EvidenceError):
            evidence.add_evidence({"metric": {"name": "PSNR", "value": "high"}})



class Lifecycle(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("life33")
        golden.seed()

    def test_candidate_never_memory_until_approved(self):
        n0 = len(M.load()["decisions"])
        c = lifecycle.propose("decision", {"text": "Switch to SwinIR-small for all CAVE runs", "evidence_ids": ["EVID-001"]},
                              origin="provider", provider="codex", session="gs-12345678", request_id="gw-0123456789")
        self.assertEqual(c["classification"], "ai_suggestion")
        self.assertEqual(len(M.load()["decisions"]), n0)
        out = lifecycle.approve(c["id"])
        d = next(x for x in M.load()["decisions"] if x["id"] == out["committed"]["id"])
        self.assertEqual(d["provider"], "codex")
        self.assertEqual(d["evidence_ids"], ["EVID-001"])
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.approve(c["id"])

    def test_dedup_and_reject(self):
        a = lifecycle.propose("failure", {"text": "CUDA OOM: SwinIR-large with attention window 16 and batch 8 on RTX 3060 12GB"},
                              origin="provider", provider="claude_code")
        self.assertEqual(a["status"], "duplicate")
        self.assertEqual(a["duplicate_of"], "FAIL-001")
        b = lifecycle.propose("observation", {"text": "Training loss plateaus after epoch 40", "experiment_id": "EXP-004"},
                              origin="provider", provider="antigravity")
        lifecycle.reject(b["id"], "not reproducible")
        self.assertEqual(lifecycle.get(b["id"])["status"], "rejected")
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.propose("observation", {"text": "x", "experiment_id": "../etc"})

    def test_experiment_result_updates_experiment_and_evidence(self):
        c = lifecycle.propose("experiment_result", {"experiment_id": "EXP-003", "text": "Re-run with gradient checkpointing fits",
                                                    "metric": {"name": "PSNR", "value": 31.6}, "verdict": "supports"},
                              origin="provider", provider="codex")
        out = lifecycle.approve(c["id"])
        e = next(x for x in research.load()["experiments"] if x["id"] == "EXP-003")
        self.assertEqual(e["verdict"], "supports")
        ev = evidence.get(out["committed"]["id"])
        self.assertEqual(ev["status"], "validated")
        self.assertEqual(ev["metric"]["value"], 31.6)


class Reliability(unittest.TestCase):
    def setUp(self):
        _env.fresh_project("rel33")

    def test_concurrent_writes_unique_ids_no_lost_updates(self):
        h = research.add_hypothesis("concurrency")
        errs = []

        def worker(i):
            try:
                for j in range(10):
                    research.add_experiment({"title": f"w{i}-{j}", "hypothesis_id": h["id"]})
                    lifecycle.propose("note", {"text": f"note {i} {j} unique-{i * 100 + j}"}, origin="human")
                    M.add_decision(f"decision {i}-{j}", locked=False)
            except Exception as e:  # pragma: no cover
                errs.append(e)
        ts = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errs, [])
        exps = research.load()["experiments"]
        self.assertEqual(len(exps), 60)
        self.assertEqual(len({e["id"] for e in exps}), 60)
        self.assertEqual(len(M.load()["decisions"]), 60)
        self.assertEqual(len(lifecycle.list_candidates(limit=1000)), 60)

    def test_v32_files_migrate_transparently(self):
        (M.mem_dir() / "research.json").write_text(json.dumps({"seq": {"FAIL": 1}, "hypotheses": [], "experiments": [],
            "failures": [{"id": "FAIL-001", "text": "old failure", "hypothesis_id": "", "run_id": "", "reason": "old reason",
                          "validated": True, "created": "2025-01-01T00:00:00+00:00"}]}), "utf-8")
        M.save({**M.load(), "decisions": [{"id": "Dabcdef", "text": "old decision", "kind": "direction", "locked": True,
                                           "source": "", "created": "2025-01-01T00:00:00+00:00"}]})
        from backend.memory import lod
        nodes = {n.id: n for n in lod.collect()}
        self.assertIn("FAIL-001", nodes)
        self.assertIn("Dabcdef", nodes)
        self.assertEqual(state.current()["recent_decisions"][0]["id"], "Dabcdef")
        f = research.add_failure("new one", model="X")
        self.assertEqual(f["id"], "FAIL-002")
        self.assertIn("Dabcdef", trace.chain("Dabcdef")["root"])

    def test_corrupt_store_is_quarantined_not_overwritten(self):
        research.add_hypothesis("precious")
        p = M.mem_dir() / "research.json"
        p.write_text("{ broken json", "utf-8")
        self.assertEqual(research.load()["hypotheses"], [])
        copies = list(p.parent.glob("research.json.corrupt-*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_text("utf-8"), "{ broken json")

    def test_leftover_tmp_file_is_ignored(self):
        research.add_hypothesis("kept")
        (M.mem_dir() / "research.json.tmp").write_text("garbage", "utf-8")  # crash between write and replace
        self.assertEqual(research.load()["hypotheses"][0]["text"], "kept")

    def test_consolidation_keeps_provenance(self):
        from unittest import mock

        def eps(st):
            for i in range(45):
                st["tier2"].append({"id": f"E{i:06d}", "created": f"2026-01-{i % 28 + 1:02d}T00:00:00+00:00", "source": "chat",
                                    "title": f"ep {i}", "summary": f"summary {i}", "pages": [f"P{i:08x}"], "links": [f"EXP-{i + 1:03d}"]})
        M.update(eps)

        async def fake(*a, **k):
            return {"text": "TITLE: Period\nmerged", "engine": "fake"}
        with mock.patch("backend.providers.models.call_agent", side_effect=fake):
            _env.run_async(M._consolidate(max_episodes=40, batch=12))
        st = M.load()
        merged = st["tier2"][0]
        self.assertEqual(len(merged["merged"]), 12)
        self.assertEqual(len(merged["pages"]), 12)
        self.assertIn("EXP-001", merged["links"])
        self.assertEqual(len(st["tier2_archive"]), 12)


if __name__ == "__main__":
    unittest.main()
