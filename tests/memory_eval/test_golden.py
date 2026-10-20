"""Golden-task regression gate: retrieval/context quality must not fall below the v3.3 levels (and must beat v3.2).

v3.2 baseline (docs/benchmarks/data/v32-baseline.json, 300 distractors): dev recall@5 0.556 / MRR 0.494,
held-out recall@5 0.583 / MRR 0.479. Thresholds sit a little under the measured v3.3 values so a real regression fails
while harmless reordering does not.
"""
import _env  # noqa: F401  (must be first)
import unittest

from backend import config
from backend.memory import compiler, engine
from memory_eval import golden


class GoldenTasks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _env.fresh_project("golden")
        config.save_config({"memory": {"embed_engine": "hashing"}})
        cls.ids = golden.seed()
        golden.scale(300)
        cfg = config.load_config()

        def retrieve(t):
            return [h["id"] for h in engine.retrieve(engine.build_context(t["query"], role=t["role"]), cfg=cfg)["hits"]]

        def comp(t):
            return compiler.compile_context("data", "", t["query"], 3500, None, cfg, role=t["role"])["text"]
        cls.dev = golden.evaluate(retrieve, comp)
        cls.held = golden.evaluate(retrieve, comp, tasks=golden.resolve(golden.HELD_OUT, cls.ids))

    def test_dev_tasks(self):
        m = self.dev["mean"]
        self.assertGreaterEqual(m["recall@5"], 0.85, self.dev)
        self.assertGreaterEqual(m["mrr"], 0.8, self.dev)
        self.assertGreaterEqual(m["ids_in_context"], 0.95, self.dev)
        self.assertGreaterEqual(m["fact_fidelity"], 0.95, self.dev)

    def test_held_out_tasks_beat_v32(self):
        m = self.held["mean"]
        self.assertGreater(m["recall@5"], 0.583, self.held)
        self.assertGreater(m["mrr"], 0.479, self.held)
        self.assertGreaterEqual(m["fact_fidelity"], 0.85, self.held)

    def test_context_efficiency(self):
        self.assertLess(self.dev["mean"]["context_tokens"], 2000)   # v3.2: ~2970 tokens at this size
        self.assertGreater(self.dev["mean"]["efficiency"], 1.2)     # v3.2: 0.57 useful hits / 1k tokens

    def test_latency_budget(self):
        self.assertLess(self.dev["mean"]["retrieve_ms"], 500)
        self.assertLess(self.dev["mean"]["compile_ms"], 300)


if __name__ == "__main__":
    unittest.main()
