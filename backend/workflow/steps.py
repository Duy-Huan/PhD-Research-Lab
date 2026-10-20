"""Step types of the workflow orchestrator (v4.1): the server-side allowlist. A workflow can only combine these.

kind          deterministic (computed here) · agent (harness proposes) · human (researcher acts) · execution (runs code in
              the sandbox / spends compute) · composite (nested workflows)
risk          high = consequential (compute, durable research state); gates follow the workflow's approval policy
approval_key  gate BEFORE the step (approvals.<key> = required) · after_key: gate AFTER (the result needs review)
always_approve  never runs without an explicit approval, whatever the mode (e.g. arbitrary sandbox commands)
idempotent    safe to repeat after an interrupted run; otherwise the researcher decides after a restart
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable

from . import hpo as H
from . import model_intel as MI
from .harness import AI_SUGGESTION, get as harness


class StepFailed(Exception):
    pass


class StepPaused(Exception):
    """A resumable step stopped between units of work (pause requested); it continues from its checkpoint."""


@dataclass(frozen=True)
class StepType:
    name: str
    kind: str
    risk: str
    description: str
    params: dict = field(default_factory=dict)       # name → (type | "", required)
    handler: Callable | None = None
    idempotent: bool = True
    resumable: bool = False
    approval_key: str = ""
    after_key: str = ""
    always_approve: bool = False
    feature: str = ""
    check_output: Callable | None = None

    def public(self) -> dict:
        return {"name": self.name, "kind": self.kind, "risk": self.risk, "description": self.description,
                "params": {k: {"type": t, "required": r} for k, (t, r) in self.params.items()}, "idempotent": self.idempotent,
                "approval_key": self.approval_key, "after_key": self.after_key, "always_approve": self.always_approve,
                "feature": self.feature}


REGISTRY: dict = {}


def step(name, kind, risk, description, params=None, **kw):
    def deco(fn):
        REGISTRY[name] = StepType(name, kind, risk, description, params or {}, fn, **kw)
        return fn
    return deco


def _register_human(name, description, params):
    REGISTRY[name] = StepType(name, "human", "low", description, params, None)


_register_human("human.approval", "The researcher approves (or rejects) before the workflow continues.",
                {"question": ("string", False), "show": ("", False)})
_register_human("human.input", "The researcher provides values (hypothesis, configuration, selected candidate…).",
                {"prompt": ("string", False), "fields": ("object", False), "show": ("", False)})


# ------------------------------------------------------------------ research context
@step("research.context", "deterministic", "low", "Retrieve the compiled research context (state, evidence, failures).",
      {"query": ("string", True), "role": ("string", False), "budget_tokens": ("integer", False)})
async def _context(ctx):
    from ..gateway.context import provider_context
    p = ctx.params
    pc = await asyncio.to_thread(provider_context, p["query"], "workflow", p.get("role") or "",
                                 budget_tokens=p.get("budget_tokens") or 3000)
    return {"context": pc["prompt"][-12000:], "context_version": pc["context_version"], "included_ids": pc["included_ids"],
            "tokens": pc["context_tokens"], "blocked_count": len(pc["blocked"])}


@step("research.state", "deterministic", "low", "Read the current research state (objective, hypothesis, constraints).")
async def _state(ctx):
    from ..context_graph import purged_ids
    from ..memory import state as S
    st = await asyncio.to_thread(S.current, set(purged_ids()))
    return {"state": st}


# ------------------------------------------------------------------ agent steps
@step("agent.plan", "agent", "low", "The harness proposes a structured plan (no training starts).",
      {"objective": ("string", True), "context": ("", False), "constraints": ("object", False), "feedback": ("string", False)})
async def _plan(ctx):
    ctx.reserve_agent_call()
    p = ctx.params
    obj = p["objective"] + (f"\n\nResearcher feedback on the previous proposal: {p['feedback']}" if p.get("feedback") else "")
    ctxt = p.get("context")
    out = await harness().plan(obj, ctxt if isinstance(ctxt, str) else json.dumps(ctxt or {}, default=str),
                               p.get("constraints") or {})
    return {"plan": out, "label": AI_SUGGESTION}


@step("agent.interpret", "agent", "low", "The harness interprets VALIDATED results against the hypothesis.",
      {"results": ("", True), "hypothesis": ("string", False), "feedback": ("string", False)},
      after_key="before_conclusion")
async def _interpret(ctx):
    ctx.reserve_agent_call()
    p = ctx.params
    hyp = (p.get("hypothesis") or "") + (f"\nResearcher feedback: {p['feedback']}" if p.get("feedback") else "")
    out = await harness().interpret(p["results"], hyp)
    return {"interpretation": out, "label": out.get("label")}


# ------------------------------------------------------------------ model intelligence
@step("model.inspect", "deterministic", "low", "Inspect a model: parameters, MACs/FLOPs, activations (spec / ONNX).",
      {"adapter": ("string", False), "spec": ("object", False), "path": ("string", False)}, feature="model_intelligence")
async def _inspect(ctx):
    p = ctx.params
    a = p.get("adapter") or "spec"
    try:
        if a == "spec":
            return {"report": MI.analyze_spec(p.get("spec") or {})}
        if a == "onnx":
            return {"report": MI.analyze_onnx(p.get("path") or "")}
    except MI.ModelError as e:
        raise StepFailed(str(e))
    raise StepFailed("adapter must be spec or onnx (use model.profile for PyTorch models)")


@step("model.feasibility", "deterministic", "low", "Compare memory needs with this PC's GPU/RAM and the workflow budget.",
      {"report": ("object", True), "batch_size": ("integer", False), "precision": ("string", False),
       "optimizer": ("string", False)}, feature="model_intelligence")
async def _feasibility(ctx):
    p = ctx.params
    try:
        f = await asyncio.to_thread(MI.feasibility, p["report"], int(p.get("batch_size") or 1), p.get("precision") or "fp32",
                                    p.get("optimizer") or "adam", None, float(ctx.budgets.get("max_gpu_memory_gb") or 0))
    except MI.ModelError as e:
        raise StepFailed(str(e))
    return f


@step("model.profile", "execution", "high", "Measure a PyTorch model in the sandbox (params, latency, peak memory).",
      {"model_path": ("string", True), "class_name": ("string", True), "input_shape": ("array", True),
       "batch_size": ("integer", False), "precision": ("string", False), "gpu": ("boolean", False),
       "warmup": ("integer", False), "repeats": ("integer", False), "kwargs": ("object", False)},
      idempotent=True, approval_key="before_training", feature="model_intelligence")
async def _profile(ctx):
    from .. import sandbox
    p = ctx.params
    try:
        script = MI.profiling_script(p["model_path"], p["class_name"], p["input_shape"], int(p.get("batch_size") or 1),
                                     p.get("precision") or "fp32", bool(p.get("gpu", True)), int(p.get("warmup") or 5),
                                     int(p.get("repeats") or 20), p.get("kwargs"))
    except MI.ModelError as e:
        raise StepFailed(str(e))
    f = sandbox.code_dir() / ".phdlab" / "profile_model.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(script, "utf-8")
    env = {} if p.get("gpu", True) else {"CUDA_VISIBLE_DEVICES": ""}
    job = await _run_job(ctx, "python .phdlab/profile_model.py", "Model profile", env)
    if job.status != "done":
        raise StepFailed(f"profiling run {job.status}: {job.tail(20, 'err')[-800:]}")
    try:
        rep = MI.parse_profile(job.tail(200, "out"), int(p.get("batch_size") or 1), int(p.get("warmup") or 5),
                               int(p.get("repeats") or 20), p.get("precision") or "fp32")
    except (MI.ModelError, ValueError) as e:
        raise StepFailed(str(e))
    return {"report": rep, "run_id": job.id}


async def _run_job(ctx, cmd: str, title: str, env: dict | None = None):
    """Start a sandbox job (lifecycle `mcp` lease on the container) and wait for it; cancellable."""
    from .. import model_lifecycle as LC, sandbox
    res = None
    try:
        if await asyncio.to_thread(sandbox.effective_mode) == "docker":
            res = await LC.acquire("mcp", "docker", sandbox.container_name(), "background")
        try:
            job = await asyncio.to_thread(sandbox.start_job, cmd, "run", title, env)
        except sandbox.SandboxError as e:
            raise StepFailed(str(e))
        ctx.on_cancel(lambda: sandbox.stop_job(job.id))
        while job.status == "running":
            await asyncio.sleep(0.5)
        return job
    finally:
        await LC.release(res)


# ------------------------------------------------------------------ HPO
def _check_space_output(out: dict) -> list:
    """An (edited) proposal is only accepted when the deterministic validator accepts it."""
    if not isinstance(out, dict) or not isinstance(out.get("search_space"), dict):
        return ["output.search_space must be an object"]
    return H.validate_space(out["search_space"], out.get("objectives") or [])["errors"]


@step("hpo.propose_search_space", "agent", "low", "The harness proposes a bounded search space; it is validated "
      "deterministically before anything can run.",
      {"model_report": ("", False), "baseline": ("object", False), "hint": ("string", False), "objectives": ("array", True),
       "feedback": ("string", False)}, check_output=_check_space_output, feature="optuna_hpo")
async def _propose_space(ctx):
    ctx.reserve_agent_call()
    p = ctx.params
    hint = (p.get("hint") or "") + (f"\nResearcher feedback: {p['feedback']}" if p.get("feedback") else "")
    out = await harness().propose_search_space(p.get("model_report") or {}, p.get("baseline") or {}, hint, [])
    space = out.get("search_space") if isinstance(out.get("search_space"), dict) else {}
    v = H.validate_space(space, p["objectives"])
    return {"search_space": v["params"] if v["valid"] else space, "objectives": p["objectives"], "validation": v,
            "rationale": out.get("rationale", ""), "label": AI_SUGGESTION, "engine": out.get("_engine")}


@step("hpo.validate_search_space", "deterministic", "low", "Validate types, bounds, conditions, budget and leakage.",
      {"search_space": ("object", True), "objectives": ("array", True), "max_trials": ("integer", False),
       "sampler": ("string", False), "est_trial_minutes": ("number", False)}, feature="optuna_hpo")
async def _validate_space(ctx):
    p = ctx.params
    mt = min(int(p.get("max_trials") or ctx.budgets.get("max_trials") or 0), int(ctx.budgets.get("max_trials") or 10 ** 6))
    v = H.validate_space(p["search_space"], p["objectives"], mt, p.get("sampler") or "auto",
                         float(p.get("est_trial_minutes") or 0), float(ctx.budgets.get("max_runtime_minutes") or 0))
    if not v["valid"]:
        raise StepFailed("search space rejected: " + "; ".join(v["errors"]))
    return {**v, "max_trials": mt}


def _script_path(script: str) -> str:
    from ..sandbox import code_dir
    root = code_dir().resolve()
    p = (root / (script or "")).resolve()
    if root not in p.parents or p.suffix != ".py" or not p.is_file():
        raise StepFailed("objective.script must be an existing .py file inside the project's code folder")
    return p.relative_to(root).as_posix()


def _sandbox_objective(ctx, ocfg: dict, primary: str, pruning: bool):
    from .. import sandbox
    script = _script_path(ocfg.get("script", ""))
    timeout = int(ocfg.get("timeout_s") or 0)

    async def run(params, seed, report):
        env = {"PHDLAB_TRIAL_PARAMS": json.dumps(params), "PHDLAB_TRIAL_SEED": str(seed)}
        if not ocfg.get("gpu"):
            env["CUDA_VISIBLE_DEVICES"] = ""
        try:
            job = await asyncio.to_thread(sandbox.start_job, f'python "{script}"', "run", f"HPO trial seed {seed}", env)
        except sandbox.SandboxError as e:
            raise H.HPOError(str(e))
        ctx.on_cancel(lambda: sandbox.stop_job(job.id))
        t0, last, pruned = time.time(), 0, False
        try:
            while not pruned and job.status == "running":
                await asyncio.sleep(1.0)
                if timeout and time.time() - t0 > timeout:
                    sandbox.stop_job(job.id)
                    raise H.HPOError(f"trial exceeded its time limit ({timeout} s)")
                if pruning:
                    ser = sandbox.parse_metrics_text(job.tail(400, "out"))["series"].get(primary) or []
                    for s, val in ser:
                        if s > last:
                            last = s
                            if report(val, int(s)):  # pruned: stop the run, keep its partial record
                                sandbox.stop_job(job.id)
                                pruned = True
                                break
        except asyncio.CancelledError:
            sandbox.stop_job(job.id)
            raise
        while job.status == "running":  # stop_job is asynchronous: wait for the process to end
            await asyncio.sleep(0.2)
        meta = {"run_id": job.id, "exit_code": job.exit_code, "environment": job.meta.get("environment"),
                "git": job.meta.get("git")}
        if job.status == "failed":
            from ..resources import classify_failure
            kind = classify_failure(job.tail(80, "err")) or "error"
            raise H.HPOError(f"trial run failed ({kind}): {job.tail(6, 'err')[-400:]}")
        return job.meta.get("metrics") or {}, meta
    return run


@step("hpo.run", "execution", "high", "Run a bounded Optuna study (local sequential runner; optional Ray Tune).",
      {"search_space": ("object", True), "objectives": ("array", True), "max_trials": ("integer", True),
       "sampler": ("string", False), "seed": ("integer", False), "pruning": ("boolean", False), "parallel": ("integer", False),
       "objective": ("object", True), "runner": ("string", False)},
      idempotent=False, resumable=True, approval_key="before_training", feature="optuna_hpo")
async def _hpo_run(ctx):
    from ..config import load_config
    p = dict(ctx.params)
    p["max_trials"] = min(int(p["max_trials"]), int(ctx.budgets.get("max_trials") or p["max_trials"]))
    p["parallel"] = min(int(p.get("parallel") or 1), int(ctx.budgets.get("max_parallel_trials") or 1))
    ocfg = p["objective"] or {}
    if ocfg.get("kind", "analytic") not in ("analytic", "sandbox_script"):
        raise StepFailed("objective.kind must be analytic or sandbox_script")
    features = load_config()["features"]
    if ocfg.get("kind") == "sandbox_script" and not features.get("experiment_execution", True):
        raise StepFailed("experiment execution is switched off (features.experiment_execution)")
    objs = p["objectives"]
    runner = None
    if ocfg.get("kind") == "sandbox_script":
        runner = _sandbox_objective(ctx, ocfg, (objs[0] or {}).get("name", ""), bool(p.get("pruning", True)))
    try:
        summary = await H.run_study(p, study_id=ctx.state.get("study_id", ""), run_id=ctx.run["id"],
                                    should_stop=ctx.should_stop, on_event=ctx.emit, reserve_trials=ctx.reserve_trials,
                                    objective_runner=runner, features=features)
    except H.HPOError as e:
        raise StepFailed(str(e))
    ctx.state["study_id"] = summary["study_id"]
    ctx.save()
    if summary["status"] == "paused":
        raise StepPaused(summary["study_id"])
    return summary


def _load(study_id: str) -> dict:
    try:
        return H.load_study(study_id)
    except H.HPOError as e:
        raise StepFailed(str(e))


@step("evaluation.compare_trials", "deterministic", "low", "Validate trial metrics, rank candidates, Pareto front, baseline.",
      {"study_id": ("string", True), "rank_by": ("string", False), "baseline": ("object", False), "top_k": ("integer", False)})
async def _compare(ctx):
    p = ctx.params
    st = _load(p["study_id"])
    objs = st["objectives"]
    prim = next((o for o in objs if o["name"] == p.get("rank_by")), objs[0])
    excluded = [{"trial": t["number"], "state": t["state"], "why": t.get("error") or t["state"].lower()}
                for t in st["trials"] if t["state"] != "COMPLETE"]
    ranked = H.rank(st["trials"], prim)
    k = max(1, int(p.get("top_k") or 3))
    base = p.get("baseline") or {}
    vs = []
    for t in ranked[:k]:
        row = {"trial": t["number"], "params": t["params"], "values": t["values"]}
        if base:
            row["delta_vs_baseline"] = {m: t["values"][m] - b for m, b in base.items() if H._finite(b) and m in t["values"]}
        vs.append(row)
    return {"study_id": st["id"], "rank_by": prim, "top": vs, "pareto": [{"trial": t["number"], "values": t["values"],
                                                                         "params": t["params"]}
                                                                        for t in H.pareto_front(st["trials"], objs)],
            "excluded": excluded, "n_valid": len(ranked), "measurement": (ranked[0].get("measurement") if ranked else ""),
            "rule": f"rank by {prim['name']} ({prim['direction']}); failed/pruned/non-finite trials excluded"}


@step("evaluation.confirm", "execution", "high", "Repeat the top candidates with new seeds; mean, std and 95 % CI.",
      {"study_id": ("string", True), "top_k": ("integer", False), "seeds": ("array", False), "baseline": ("object", False)},
      idempotent=False, approval_key="before_training", feature="optuna_hpo")
async def _confirm(ctx):
    p = ctx.params
    st = _load(p["study_id"])
    objs = st["objectives"]
    seeds = [int(s) for s in (p.get("seeds") or [101, 202, 303])][:10]
    top = H.rank(st["trials"], objs[0])[:max(1, int(p.get("top_k") or 2))]
    need = len(top) * len(seeds)
    if ctx.reserve_trials(need) < need:
        raise StepFailed(f"confirmation needs {need} runs but the workflow's trial budget does not allow it")
    ocfg = st["objective"]
    run = _sandbox_objective(ctx, ocfg, objs[0]["name"], False) if ocfg.get("kind") == "sandbox_script" else \
        H._analytic_runner({**ocfg, "steps": 0})
    out = []
    for t in top:
        per = []
        for s in seeds:
            if ctx.should_stop():
                raise StepFailed("stopped during confirmation")
            vals, _ = await run(t["params"], s, lambda *_: False)
            per.append({"seed": s, "values": {o["name"]: vals.get(o["name"]) for o in objs}})
        stats = {o["name"]: H.summary_stats([r["values"][o["name"]] for r in per]) for o in objs}
        row = {"trial": t["number"], "params": t["params"], "runs": per, "stats": stats}
        base = p.get("baseline") or {}
        if base:
            row["vs_baseline"] = {m: {"mean_delta": stats[m]["mean"] - b, "ci_excludes_baseline":
                                      bool(stats[m]["ci95"] and not stats[m]["ci95"][0] <= b <= stats[m]["ci95"][1])}
                                  for m, b in base.items() if m in stats and stats[m]["mean"] is not None}
        out.append(row)
    return {"study_id": st["id"], "seeds": seeds, "candidates": out,
            "note": "Repeated runs on the same validation split are not independent evidence of generalisation."}


@step("evaluation.run_configs", "execution", "high", "Evaluate fixed configurations (ablation variants) with the same "
      "objective and seeds.",
      {"configs": ("array", True), "objective": ("object", True), "objectives": ("array", True), "seeds": ("array", False)},
      idempotent=False, approval_key="before_training", feature="optuna_hpo")
async def _run_configs(ctx):
    p = ctx.params
    objs = p["objectives"]
    v = H.validate_space({"_": {"type": "bool"}}, objs)
    if not v["valid"]:
        raise StepFailed("; ".join(v["errors"]))
    seeds = [int(s) for s in (p.get("seeds") or [0])][:10]
    cfgs = [c for c in p["configs"] if isinstance(c, dict) and isinstance(c.get("config"), dict)]
    if not cfgs:
        raise StepFailed("configs must be a list of {name, config}")
    need = len(cfgs) * len(seeds)
    if ctx.reserve_trials(need) < need:
        raise StepFailed(f"{need} runs exceed the workflow's trial budget")
    ocfg = p["objective"]
    if ocfg.get("kind", "analytic") == "analytic" and ocfg.get("function") not in H.ANALYTIC:
        raise StepFailed("objective.function must be one of " + ", ".join(H.ANALYTIC))
    run = _sandbox_objective(ctx, ocfg, objs[0]["name"], False) if ocfg.get("kind") == "sandbox_script" else \
        H._analytic_runner({**ocfg, "steps": 0})
    rows = []
    for c in cfgs:
        per = []
        for sd in seeds:
            if ctx.should_stop():
                raise StepFailed("stopped")
            clean = {k: (0 if val is None else val) for k, val in c["config"].items()}
            vals, _ = await run(clean, sd, lambda *_: False)
            per.append({o["name"]: vals.get(o["name"]) for o in objs})
        rows.append({"name": c.get("name", ""), "config": c["config"],
                     "stats": {o["name"]: H.summary_stats([r[o["name"]] for r in per]) for o in objs}})
    return {"results": rows, "seeds": seeds, "protocol": "same objective, metrics and seeds for every configuration"}


@step("verification.check", "deterministic", "low", "Verify protocol compliance, metrics and artifacts before interpretation.",
      {"study_id": ("string", True), "min_complete": ("integer", False), "expect_files": ("array", False),
       "fail_on_error": ("boolean", False)})
async def _verify(ctx):
    from ..sandbox import runs_dir
    p = ctx.params
    st = _load(p["study_id"])
    checks = []
    comp = [t for t in st["trials"] if t["state"] == "COMPLETE"]
    checks.append({"check": "enough complete trials", "ok": len(comp) >= int(p.get("min_complete") or 1),
                   "detail": f"{len(comp)} complete"})
    names = [o["name"] for o in st["objectives"]]
    bad = [t["number"] for t in comp if not all(H._finite(t["values"].get(n)) for n in names)]
    checks.append({"check": "objective metrics finite", "ok": not bad, "detail": f"bad trials: {bad}" if bad else "all finite"})
    checks.append({"check": "single declared protocol", "ok": True,
                   "detail": f"one search space and objective set for {len(st['trials'])} trials (study {st['id']})"})
    with_runs = [t for t in comp if t.get("run_id")]
    for f in p.get("expect_files") or []:
        missing = [t["number"] for t in with_runs if not (runs_dir() / t["run_id"] / str(f)).exists()]
        checks.append({"check": f"artifact {f}", "ok": bool(with_runs) and not missing,
                       "detail": "no trial ran in the sandbox (synthetic objective): no artifacts to verify" if not with_runs
                       else f"missing in trials {missing}" if missing else "present"})
    passed = all(c["ok"] for c in checks)
    if not passed and p.get("fail_on_error", True):
        raise StepFailed("verification failed: " + "; ".join(f"{c['check']} ({c['detail']})" for c in checks if not c["ok"]))
    return {"passed": passed, "checks": checks}


@step("failure.diagnose", "agent", "low", "Classify a failure, find similar ones, propose SAFE adjustments.",
      {"error": ("string", True), "run_id": ("string", False), "config": ("object", False)})
async def _diagnose(ctx):
    from ..resources import classify_failure
    p = ctx.params
    err = p["error"][-6000:]
    cat = classify_failure(err) or next((c for c, rx in (
        ("timeout", r"(?i)time ?limit|timed? ?out"), ("numerical_instability", r"(?i)\bnan\b|inf(inity)?|diverg"),
        ("invalid_configuration", r"(?i)keyerror|valueerror|invalid|shape mismatch|size mismatch"),
        ("invalid_data", r"(?i)filenotfound|no such file|corrupt|decode")) if re.search(rx, err)), "unknown")
    similar = []
    try:
        from ..memory import research
        toks = set(re.findall(r"[a-z]{4,}", err.lower()))
        for f in research.load().get("failures", []):
            overlap = len(toks & set(re.findall(r"[a-z]{4,}", (f.get("text", "") + " " + f.get("error", "")).lower())))
            if overlap >= 2:
                similar.append({"id": f["id"], "text": f["text"][:200], "lesson": f.get("lesson", ""), "overlap": overlap})
        similar.sort(key=lambda x: -x["overlap"])
    except Exception:  # pragma: no cover - memory store unreadable
        similar = []
    ctx.reserve_agent_call()
    d = await harness().diagnose({"category": cat, "error": err, "run_id": p.get("run_id"), "config": p.get("config")}, similar)
    return {"category": cat, "similar_failures": similar[:6], "diagnosis": d, "label": AI_SUGGESTION,
            "rule": "Changes to dataset semantics, the evaluation protocol or the hypothesis need the researcher's approval."}


@step("ablation.generate", "deterministic", "low", "Generate ablation variants that change exactly one component each.",
      {"baseline_config": ("object", True), "components": ("array", True)})
async def _ablation(ctx):
    p = ctx.params
    base = p["baseline_config"]
    variants = []
    for c in p["components"]:
        if c not in base:
            raise StepFailed(f"component {c!r} is not a key of baseline_config")
        v = dict(base)
        cur = base[c]
        v[c] = (not cur) if isinstance(cur, bool) else None
        changed = [k for k in base if v.get(k) != base[k]]
        if changed != [c]:  # pragma: no cover - by construction exactly one key changes
            raise StepFailed(f"variant for {c} changes {changed}")
        variants.append({"name": f"without_{c}", "removed": c, "config": v})
    return {"baseline": base, "variants": variants, "rule": "each variant differs from the baseline in exactly one factor"}


# ------------------------------------------------------------------ reports, memory, execution
@step("report.generate", "deterministic", "low", "Write a Markdown report (measured / estimated / AI labels kept).",
      {"title": ("string", True), "sections": ("object", True)})
async def _report(ctx):
    from ..config import data_dir
    p = ctx.params
    lines = [f"# {p['title']}", "", f"Workflow run `{ctx.run['id']}` · step `{ctx.step['id']}` · "
             f"{time.strftime('%Y-%m-%d %H:%M')}", "",
             "> Values keep their labels: MEASURED (observed in a run), ESTIMATED (computed), SYNTHETIC (benchmark "
             "function), AI_SUGGESTION / AI_INTERPRETATION (model output — not verified research facts).", ""]
    for name, content in (p["sections"] or {}).items():
        lines += [f"## {name}", "", "```json", json.dumps(content, indent=2, ensure_ascii=False, default=str)[:20000], "```", ""]
    d = data_dir() / "workflows" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{ctx.run['id']}-{ctx.step['id']}.md"
    f.write_text("\n".join(lines), "utf-8")
    return {"path": str(f), "relative": f"workflows/reports/{f.name}", "chars": sum(len(x) + 1 for x in lines)}


@step("memory.propose", "deterministic", "high", "Propose a memory CANDIDATE (never durable memory: the researcher "
      "approves it in Context → Candidates).",
      {"kind": ("string", True), "text": ("string", True), "evidence_ids": ("array", False), "experiment_id": ("string", False),
       "metric": ("object", False), "verdict": ("string", False)},
      idempotent=False, approval_key="before_research_state_writeback", feature="memory_writeback")
async def _memory(ctx):
    from ..memory import lifecycle
    p = {k: v for k, v in ctx.params.items() if k != "kind"}
    try:
        c = await asyncio.to_thread(lifecycle.propose, ctx.params["kind"], p, "workflow", "", ctx.run["id"], ctx.step["id"],
                                    "workflow_orchestrator")
    except lifecycle.LifecycleError as e:
        raise StepFailed(str(e))
    return {"candidate_id": c["id"], "status": c["status"], "classification": c["classification"]}


@step("sandbox.run", "execution", "high", "Run a researcher-written command in the sandbox (always needs approval).",
      {"command": ("string", True), "gpu": ("boolean", False), "title": ("string", False)},
      idempotent=False, always_approve=True, approval_key="before_training", feature="experiment_execution")
async def _sandbox_run(ctx):
    p = ctx.params
    env = {} if p.get("gpu") else {"CUDA_VISIBLE_DEVICES": ""}
    job = await _run_job(ctx, p["command"], p.get("title") or "Workflow run", env)
    out = {"run_id": job.id, "status": job.status, "exit_code": job.exit_code, "metrics": job.meta.get("metrics", {}),
           "stderr_tail": job.tail(20, "err")[-1500:]}
    if job.status != "done":
        raise StepFailed(f"sandbox run {job.status} (exit {job.exit_code}): {out['stderr_tail'][-300:]}")
    return out


# ------------------------------------------------------------------ composition
@step("workflow.call", "composite", "low", "Run another workflow with explicit inputs; returns its declared outputs.",
      {"workflow": ("string", True), "version": ("integer", False), "inputs": ("object", False)})
async def _call(ctx):
    return await ctx.orch.run_child(ctx, ctx.params["workflow"], ctx.params.get("inputs") or {}, ctx.params.get("version"))


@step("workflow.repeat", "composite", "low", "Repeat a workflow until a condition holds (hard cap: max_workflow_cycles).",
      {"workflow": ("string", True), "inputs": ("object", False), "max_cycles": ("integer", False), "until": ("object", False)})
async def _repeat(ctx):
    from .schema import check_cond, evaluate
    p = ctx.params
    errs: list = []
    check_cond(p.get("until"), "until", errs)
    if errs:
        raise StepFailed("; ".join(errs))
    cycles, last = [], {}
    cap = min(int(p.get("max_cycles") or 1), int(ctx.budgets.get("max_workflow_cycles") or 1))
    for i in range(cap):
        key = f"cycle{i + 1}"
        if not ctx.state.get(key) and not ctx.reserve_cycle():  # a resumed cycle was already charged
            break
        out = await ctx.orch.run_child(ctx, p["workflow"], {**(p.get("inputs") or {})}, None, key=key)
        cycles.append({"cycle": i + 1, "child_run_id": out.get("child_run_id")})
        last = out
        if p.get("until") and evaluate(p["until"], {"last": out}):  # validated above: cannot raise
            return {"cycles": cycles, "last": last, "stopped_because": "condition met"}
        if ctx.should_stop():
            break
    return {"cycles": cycles, "last": last, "stopped_because": f"cycle cap ({cap}) reached"}


def public_registry() -> list:
    return [t.public() for t in REGISTRY.values()]
