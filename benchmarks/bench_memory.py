"""Context Memory benchmark: golden-task quality + latency at several memory sizes.

    .venv/Scripts/python benchmarks/bench_memory.py --pipeline v32 --out docs/benchmarks/data/v32-baseline.json
    .venv/Scripts/python benchmarks/bench_memory.py --pipeline v33 --out docs/benchmarks/data/v33.json

Runs on a throw-away data folder (tests/_env.py) with the lexical (hashing) embedder, so numbers are deterministic and
comparable across versions. Pipelines:
    v32  retrieval.search(query, lod.collect())  + compiler.compile_context — the v3.2 *API*. On a v3.3 tree this still
         runs the v3.3 compiler; the true v3.2 baseline (docs/benchmarks/data/v32-baseline.json) was produced by running
         this script inside a git worktree of the unmodified v3.2 HEAD.
    v33  engine.retrieve(RetrievalContext)       + compiler.compile_context(role=…)  (state-aware, role-aware)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
import _env  # noqa: E402,F401  (throw-away data folder)

from backend import config  # noqa: E402
from backend.memory import compiler, lod, research, retrieval  # noqa: E402
from memory_eval import golden  # noqa: E402

config.save_config({"memory": {"embed_engine": "hashing"}})


def _ms(fn, n: int = 5) -> dict:
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    return {"first_ms": round(ts[0], 2), "median_ms": round(statistics.median(ts), 2), "max_ms": round(max(ts), 2)}


def pipelines(name: str):
    cfg = config.load_config()
    if name == "v32":
        def retrieve(t):
            return [h["id"] for h in retrieval.search(t["query"], lod.collect(), cfg, k=24)["hits"]]

        def comp(t):
            return compiler.compile_context("data", "", t["query"], cfg["memory"]["context_budget_tokens"], None, cfg)["text"]
        return retrieve, comp
    from backend.memory import engine

    def retrieve(t):
        return [h["id"] for h in engine.retrieve(engine.build_context(t["query"], role=t["role"]), cfg=cfg)["hits"]]

    def comp(t):
        return compiler.compile_context("data", "", t["query"], cfg["memory"]["context_budget_tokens"], None, cfg,
                                        role=t["role"])["text"]
    return retrieve, comp


def run(pipeline: str, sizes: list) -> dict:
    out = {"pipeline": pipeline, "python": platform.python_version(), "machine": platform.processor() or platform.machine(),
           "sizes": []}
    for n in sizes:
        _env.fresh_project(f"bench-{pipeline}-{n}")
        ids = golden.seed()
        if n:
            golden.scale(n)
        retrieve, comp = pipelines(pipeline)
        nodes = lod.collect()
        row = {"distractors": n, "nodes": len(nodes)}
        row["collect"] = _ms(lod.collect)
        q = golden.TASKS[-1]
        row["retrieve"] = _ms(lambda: retrieve(q))
        row["compile"] = _ms(lambda: comp(q))
        row["write_experiment"] = _ms(lambda: research.add_experiment({"title": "bench write", "dataset_version": "X"}), 5)
        tracemalloc.start()
        comp(q)
        row["compile_peak_kb"] = round(tracemalloc.get_traced_memory()[1] / 1024, 1)
        tracemalloc.stop()
        row["quality"] = golden.evaluate(retrieve, comp)
        row["quality_held_out"] = golden.evaluate(retrieve, comp, tasks=golden.resolve(golden.HELD_OUT, ids))
        row["quality_held_out_2"] = golden.evaluate(retrieve, comp, tasks=golden.resolve(golden.HELD_OUT_2, ids))
        out["sizes"].append(row)
        print(f"[{pipeline}] n={n} nodes={len(nodes)} retrieve={row['retrieve']} compile={row['compile']}", flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", default="v33", choices=("v32", "v33"))
    ap.add_argument("--sizes", default="0,300,1500")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    res = run(a.pipeline, [int(x) for x in a.sizes.split(",")])
    text = json.dumps(res, indent=1)
    if a.out:
        p = ROOT / a.out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
    for s in res["sizes"]:
        print(s["distractors"], "dev     ", json.dumps(s["quality"]["mean"]), flush=True)
        print(s["distractors"], "held-out", json.dumps(s["quality_held_out"]["mean"]), flush=True)
        print(s["distractors"], "held-out-2", json.dumps(s["quality_held_out_2"]["mean"]), flush=True)
    os._exit(0)  # background threads of the app modules never keep the benchmark alive
