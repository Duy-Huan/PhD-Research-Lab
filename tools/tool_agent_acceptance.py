"""LIVE_PROVIDER acceptance for the native tool capability system (separate from mandatory software CI).

A real local model (default LM Studio spark-x2.5-4b) receives a research goal that names NO tool. It must discover tools
in the registry, choose and chain them, survive an unavailable tool, execute a real numerical experiment and report a
measured result citing its job ids. The script then recomputes every measurement independently from the raw job
arguments and checks the agent's reported value. Exit 0 = PASS, 1 = FAIL, 2 = BLOCKED (model/server unavailable).

    python tools/tool_agent_acceptance.py --model spark-x2.5-4b --out output/playwright/<run>/tool-agent

Everything runs in a disposable PHDLAB_DATA_DIR. A PASS here is one bounded live run of one model on one task: it
is not scientific L3/L4 qualification and not proof for other models.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOAL = ("Empirically determine the order of convergence of the composite trapezoid rule for the integral of exp(x) "
        "from 0 to 1. Measure the absolute error at several resolutions, estimate the order from the measurements, and "
        "report the measured order together with the job ids that produced the data. Use the research environment.")

QUAD = '''import json, math, sys
a = json.load(sys.stdin)
n, rule = a["n"], a.get("rule", "trapezoid")
h = 1.0 / n
if rule == "trapezoid":
    s = 0.5 * (math.exp(0.0) + math.exp(1.0)) + sum(math.exp(i * h) for i in range(1, n))
    approx = h * s
else:
    approx = h * sum(math.exp((i + 0.5) * h) for i in range(n))
print(json.dumps({"n": n, "rule": rule, "h": h, "approx": approx, "abs_error": abs(approx - (math.e - 1.0))}))
'''
FIT = '''import json, math, sys
a = json.load(sys.stdin)
x, y = a["x"], a["y"]
if len(x) != len(y) or len(x) < 2 or min(x) <= 0 or min(y) <= 0:
    print("x and y need equal length >= 2 and positive values", file=sys.stderr); sys.exit(2)
lx, ly = [math.log(v) for v in x], [math.log(v) for v in y]
mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
sxx = sum((v - mx) ** 2 for v in lx)
slope = sum((u - mx) * (v - my) for u, v in zip(lx, ly)) / sxx
icpt = my - slope * mx
ss = sum((v - my) ** 2 for v in ly)
res = sum((v - (icpt + slope * u)) ** 2 for u, v in zip(lx, ly))
print(json.dumps({"slope": slope, "intercept": icpt, "r2": 1 - res / ss if ss else 1.0, "points": len(x)}))
'''
DESCRIBE = '''import json, statistics, sys
a = json.load(sys.stdin)
v = a["values"]
print(json.dumps({"mean": statistics.fmean(v), "stdev": statistics.pstdev(v), "n": len(v)}))
'''


def tools(root: Path) -> None:
    specs = {
        "numerics.quadrature_error": (QUAD, "Numerically integrate exp(x) on [0,1] with n panels (trapezoid or midpoint "
                                      "rule) and return the approximation and its absolute error against the exact value.",
                                      ["numerics", "integration", "experiment"],
                                      {"type": "object", "required": ["n"], "additionalProperties": False, "properties": {
                                          "n": {"type": "integer", "minimum": 1, "maximum": 1000000},
                                          "rule": {"type": "string", "enum": ["trapezoid", "midpoint"]}}}),
        "stats.powerlaw_fit": (FIT, "Least-squares fit of log(y) = a + b*log(x); returns slope b (power-law exponent), "
                               "intercept and r2. Use it to estimate scaling exponents or convergence orders.",
                               ["statistics", "regression", "analysis"],
                               {"type": "object", "required": ["x", "y"], "additionalProperties": False, "properties": {
                                   "x": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 200},
                                   "y": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 200}}}),
        "stats.describe": (DESCRIBE, "Mean, population standard deviation and count of a list of numbers.",
                           ["statistics", "summary"],
                           {"type": "object", "required": ["values"], "properties": {"values": {"type": "array", "items": {"type": "number"}}}}),
    }
    for tool_id, (code, desc, caps, schema) in specs.items():
        folder = root / tool_id / "1.0.0"
        folder.mkdir(parents=True)
        (folder / "tool.py").write_text(code, "utf-8")
        (folder / "tool.json").write_text(json.dumps({"id": tool_id, "version": "1.0.0", "kind": "python", "description": desc,
                                                      "capabilities": caps, "permissions": ["compute"], "input_schema": schema,
                                                      "execution": {"entry": "tool.py"}, "budget": {"timeout_s": 30}}), "utf-8")
    gpu = root / "numerics.quadrature_gpu" / "1.0.0"
    gpu.mkdir(parents=True)
    (gpu / "tool.json").write_text(json.dumps({"id": "numerics.quadrature_gpu", "kind": "cli", "permissions": ["compute"],
                                               "description": "GPU-accelerated numerical integration error for exp(x) on [0,1] (fast).",
                                               "capabilities": ["numerics", "integration", "experiment", "gpu"],
                                               "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}},
                                               "execution": {"binary": "phdlab-cuda-quadrature-not-installed", "args": ["{n}"]}}), "utf-8")


def exact_error(n: int, rule: str) -> float:
    h = 1.0 / n
    if rule == "trapezoid":
        approx = h * (0.5 * (1 + math.e) + sum(math.exp(i * h) for i in range(1, n)))
    else:
        approx = h * sum(math.exp((i + 0.5) * h) for i in range(n))
    return abs(approx - (math.e - 1))


ORDER = re.compile(r"(?i)\border\b[^.\d]{0,80}?(?:is|of|=|≈|~|about|approximately)\s*(?:p\s*=\s*)?(\d+(?:\.\d+)?)")


def score(result: dict) -> dict:
    """Pre-registered checks. Only the agent's own statement of the ORDER counts as its reported value (numbers that
    merely restate the task, such as the integration bounds, are not the result)."""
    quad = [j for j in result["jobs"] if j["tool"] == "numerics.quadrature_error" and j["status"] == "succeeded"]
    fits = [j for j in result["jobs"] if j["tool"] == "stats.powerlaw_fit" and j["status"] == "succeeded"]
    recomputed = [{"job": j["id"], "n": j["args"]["n"], "rule": j["args"].get("rule", "trapezoid"),
                   "tool_error": j["result"]["abs_error"], "independent_error": exact_error(j["args"]["n"], j["args"].get("rule", "trapezoid"))}
                  for j in quad]
    trap = sorted({(r["n"], r["independent_error"]) for r in recomputed if r["rule"] == "trapezoid"})
    independent_order = None
    if len(trap) >= 3:
        lx, ly = [math.log(1 / n) for n, _ in trap], [math.log(e) for _, e in trap]
        mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
        independent_order = sum((u - mx) * (v - my) for u, v in zip(lx, ly)) / sum((u - mx) ** 2 for u in lx)
    stated = ORDER.search(result["answer"] or "")
    reported = float(stated.group(1)) if stated else None
    checks = {
        "loop_completed": result["status"] == "completed",
        "searched_registry": any(s["action"] == "search" for s in result["steps"]),
        "at_least_3_trapezoid_measurements": len(trap) >= 3,
        "measurements_independently_reproduced": bool(recomputed) and all(
            math.isclose(r["tool_error"], r["independent_error"], rel_tol=1e-9, abs_tol=1e-15) for r in recomputed),
        "independent_order_near_2": independent_order is not None and abs(independent_order - 2) < 0.1,
        "reported_order_matches_measurement": reported is not None and independent_order is not None
                                              and abs(reported - independent_order) < 0.15,
        "cited_evidence_verified": bool(result["verified_evidence"]),
        "no_unsupported_claims": not result["unsupported_claims"],
    }
    return {"recomputed": recomputed, "independent_order": independent_order, "reported_order": reported,
            "fit_jobs": [j["id"] for j in fits], "checks": checks,
            "observed": {"unavailable_tool_attempted": any(j["tool"] == "numerics.quadrature_gpu" for j in result["jobs"]),
                         "failed_then_continued": any(j["status"] != "succeeded" for j in result["jobs"]) and result["status"] == "completed",
                         "describe_used": any(s["action"] == "describe" for s in result["steps"])},
            "decision": "PASS" if all(checks.values()) else "FAIL"}


def rescore(path: Path) -> int:
    """Re-evaluate a saved run with the current scorer WITHOUT calling any model; the original verdict is kept."""
    report = json.loads(path.read_text("utf-8"))
    again = score(report["loop"])
    out = {"report": str(path), "original_decision": report.get("decision"), "original_checks": report.get("checks"),
           "rescored_decision": again["decision"], "rescored_checks": again["checks"],
           "reported_order": again["reported_order"], "independent_order": again["independent_order"]}
    path.with_name("rescore.json").write_text(json.dumps(out, indent=1), "utf-8")
    print(json.dumps(out))
    return 0 if again["decision"] == "PASS" else 1


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--rescore":
        return rescore(Path(sys.argv[2]))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["local", "codex", "antigravity", "gemini"], default="local",
                        help="local = LM Studio; codex/antigravity = installed native CLI through the project gateway; "
                             "gemini = Google AI Studio API key configured in Settings (the route Google recommends for apps)")
    parser.add_argument("--model", default="spark-x2.5-4b", help="exact model id; '' lets a CLI use its own default")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-steps", type=int, default=16)
    parser.add_argument("--deadline", type=float, default=900)
    parser.add_argument("--max-tokens", type=int, default=8000)  # reasoning models spend tokens on thinking first
    parser.add_argument("--reasoning", choices=["auto", "off", "low", "medium", "high"], default="auto",
                        help="the application's reasoning level (local streaming path sends reasoning_effort)")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="phdlab-tool-agent-"))
    os.environ["PHDLAB_DATA_DIR"] = str(data)
    sys.path.insert(0, str(ROOT))
    from backend.core import config
    from backend.providers import models
    from backend.tools import agent_loop, registry as R
    from backend.tools.runtime import Runtime, Grant, provenance, verify_provenance
    config.save_config({"memory": {"embed_engine": "hashing"}, "lifecycle": {"cloud_preconnect": False}})
    config.create_project("tool-agent-acceptance")
    report = {"mode": "LIVE_PROVIDER", "provider": args.provider, "model": args.model, "reasoning": args.reasoning,
              "goal": GOAL, "started": time.time(),
              "bounds": {"max_steps": args.max_steps, "deadline_s": args.deadline, "max_tokens_per_call": args.max_tokens}}
    try:
        cfg = config.load_config()
        if args.provider == "local":
            base, resolved, _, _ = asyncio.run(models.local_target(cfg, "local", args.model))
            report.update(endpoint=base, resolved_model=resolved, listed_models=asyncio.run(models.list_local_models(base)))
            if resolved != args.model:
                report.update(decision="BLOCKED", reason=f"requested {args.model} but endpoint resolved {resolved}; no substitution")
                return finish(out, report, data, 2)
        elif args.provider == "gemini":
            _, key, default_model, base = models.provider_settings(cfg, "gemini")
            report.update(endpoint=base, resolved_model=args.model or default_model)
            if not key:
                report.update(decision="BLOCKED", reason="No Google AI Studio API key configured (Settings > Providers > Google Gemini)")
                return finish(out, report, data, 2)
        else:
            from backend.providers import registry as providers
            state = providers.describe("cli:" + args.provider)
            report["provider_state"] = {k: state.get(k) for k in ("available", "state", "detail", "label")}
            if not state.get("available") and state.get("state") != "UNKNOWN":  # UNKNOWN: the first request decides
                report.update(decision="BLOCKED", reason=f"{args.provider} CLI unavailable: {state.get('detail')}")
                return finish(out, report, data, 2)
        tools(R.tools_root())
        rt = Runtime(R.Registry(), workers=2)
        grant = Grant(principal="acceptance:tool-agent", tools=["numerics.*", "stats.*"], permissions=["compute", "read"],
                      max_calls=24, max_wall_s=args.deadline)
        transcript, started = [], time.monotonic()

        def complete(system, messages):
            remaining = args.deadline - (time.monotonic() - started)
            if remaining <= 5:
                raise TimeoutError("acceptance deadline reached")
            t0 = time.monotonic()
            async def collect():
                models.REASONING.set(args.reasoning)
                if args.provider == "gemini":
                    return await models.cloud_chat(cfg, "gemini", system, messages, args.max_tokens, 0.2, args.model or None)
                if args.provider == "local" and args.reasoning == "auto":
                    return await models.local_chat(cfg, system, messages, args.max_tokens, 0.2, "local", args.model, "interactive")
                stream = models._stream_engine(cfg, "local", system, messages, args.max_tokens, 0.2, args.model, "interactive") \
                    if args.provider == "local" else models._stream_cli(cfg, args.provider, system, messages, args.model or None)
                return "".join([c async for c in stream])
            call = collect()
            reply = models.strip_think(asyncio.run(asyncio.wait_for(call, remaining)))
            transcript.append({"system_chars": len(system), "messages": len(messages), "reply": reply,
                               "seconds": round(time.monotonic() - t0, 2)})
            return reply

        result = agent_loop.run(GOAL, complete, grant, max_steps=args.max_steps, registry=rt.registry, runtime=rt)
        report.update(loop=result, transcript=transcript, provenance=provenance(limit=200),
                      provenance_chain=verify_provenance(), elapsed_s=round(time.monotonic() - started, 1))
        if not transcript:
            report["decision"] = "BLOCKED"
            report["reason"] = "model produced no completion: " + json.dumps(result["steps"])[:500]
            return finish(out, report, data, 2)
        report.update(score(result))
        return finish(out, report, data, 0 if report["decision"] == "PASS" else 1)
    except Exception as e:  # model server down, etc.: BLOCKED is never reported as PASS
        report.update(decision="BLOCKED", reason=f"{type(e).__name__}: {e}"[:1000])
        return finish(out, report, data, 2)


def finish(out: Path, report: dict, data: Path, code: int) -> int:
    report["finished"] = time.time()
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str, ensure_ascii=False), "utf-8")
    shutil.rmtree(data, ignore_errors=True)
    print(json.dumps({"decision": report["decision"], "checks": report.get("checks"), "reason": report.get("reason", ""),
                      "report": str(out / "report.json")}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
