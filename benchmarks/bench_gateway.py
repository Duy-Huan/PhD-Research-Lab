"""Context Gateway / MCP benchmark (v3.4 §19): MCP tool latency, context preparation, stream start-up, cache hit rate.

    .venv/Scripts/python benchmarks/bench_gateway.py --out docs/benchmarks/data/v34-gateway.json

Runs through the real HTTP stack (FastAPI TestClient → /mcp, /api/gateway/*) on a throw-away data folder. Vendor CLIs are
replaced by tests/providers/fake_cli.py, so "stream start-up" measures PhD-Lab's own overhead (process spawn, stdin,
JSONL parsing), not the vendor's model latency, which this benchmark cannot and does not claim to measure.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
import _env  # noqa: E402,F401

warnings.filterwarnings("ignore")
from unittest import mock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend import config  # noqa: E402
from backend.app import app  # noqa: E402
from backend.gateway import connectors as C, service as GS  # noqa: E402
from backend.memory import cache  # noqa: E402
from memory_eval import golden  # noqa: E402
from providers.fakes import fake  # noqa: E402

CALLS = [("research_get_current_state", {}), ("research_search_memory", {"query": "Why did SwinIR-large fail?"}),
         ("research_get_experiment", {"id": "EXP-004"}), ("research_get_evidence", {"query": "Swin window attention PSNR"}),
         ("research_get_failures", {"query": "OOM"}), ("research_get_decisions", {}),
         ("research_get_context", {"query": "Should I test SwinIR next?", "role": "experiment_designer"}),
         ("research_get_provenance", {"id": "EVID-001"}), ("research_record_observation", {"text": "bench observation"})]


def stats(ts: list) -> dict:
    return {"median_ms": round(statistics.median(ts), 2), "max_ms": round(max(ts), 2), "n": len(ts)}


def run(sizes: list) -> dict:
    c = TestClient(app)
    out = {"sizes": []}
    for n in sizes:
        _env.fresh_project(f"gw-bench-{n}")
        config.save_config({"memory": {"embed_engine": "hashing"}, "mcp": {"token": "", "rate_limit_per_min": 0},
                            "gateway": {"review_before_external": False}})
        golden.seed()
        if n:
            golden.scale(n)
        cache.clear_all()
        row = {"distractors": n, "mcp": {}}
        init = c.post("/mcp", json={"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"clientInfo": {"name": "bench"}}})
        sess = {"Mcp-Session-Id": init.headers["mcp-session-id"]}
        for i, (name, args) in enumerate(CALLS):
            ts = []
            for j in range(5):
                if name == "research_record_observation":
                    args = {"text": f"bench observation {i}-{j} unique {time.time()}"}
                t0 = time.perf_counter()
                r = c.post("/mcp", json={"jsonrpc": "2.0", "id": i * 10 + j, "method": "tools/call",
                                         "params": {"name": name, "arguments": args}}, headers=sess).json()
                ts.append((time.perf_counter() - t0) * 1000)
                assert not r["result"].get("isError"), (name, r)
            row["mcp"][name] = {"cold_ms": round(ts[0], 2), **stats(ts[1:])}
        with mock.patch.dict(C.CONNECTORS, {p: fake(p) for p in C.CONNECTORS}):
            prep, start, total = [], [], []
            for j in range(5):
                q = f"Should I test SwinIR next? (variant {j})"
                t0 = time.perf_counter()
                r = GS.prepare(q, "claude_code", role="experiment_designer")
                prep.append((time.perf_counter() - t0) * 1000)
                t1 = time.perf_counter()
                GS.send(r["id"])
                req = GS.REQS[r["id"]]
                while not req["events"]:
                    time.sleep(0.001)
                start.append((time.perf_counter() - t1) * 1000)
                req["thread"].join(30)
                total.append((time.perf_counter() - t1) * 1000)
            row["gateway_prepare"] = stats(prep)
            row["stream_startup_first_event"] = stats(start)
            row["fake_provider_roundtrip"] = stats(total)
        row["cache"] = cache.stats()
        tel = c.get("/api/telemetry?limit=1").json()["summary"]
        row["telemetry"] = {k: v for k, v in tel.items() if k in ("memory.retrieve", "memory.compile", "gateway.request", "mcp.tool")}
        out["sizes"].append(row)
        print(f"n={n}", json.dumps({k: v["median_ms"] for k, v in row["mcp"].items()}), "prepare", row["gateway_prepare"],
              "startup", row["stream_startup_first_event"], flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="0,300,1500")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    res = run([int(x) for x in a.sizes.split(",")])
    if a.out:
        p = ROOT / a.out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=1), "utf-8")
    sys.stdout.flush()
    os._exit(0)
