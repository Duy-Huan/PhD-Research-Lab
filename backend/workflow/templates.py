"""Built-in, versioned workflow templates (v4.1 §6) + the researcher's own saved workflows.

Templates are ordinary definitions (schema.py) built only from registered step types. Any template can run on its own
or be composed into a larger workflow with `workflow.call` / `workflow.repeat`; changing a template's execution mode
(manual / assisted / bounded / custom) or the mode of single steps never needs a code change.
Saved workflows: <project>/workflows/templates/<id>@<version>.json (a new version never overwrites an old one).
"""
from __future__ import annotations

import copy
import json
import re


def R(ref: str) -> dict:
    return {"$ref": ref}


ANALYTIC_DEFAULT = {"kind": "analytic", "function": "quadratic"}
QUAD_SPACE = {"x": {"type": "float", "low": -1.0, "high": 1.0}, "y": {"type": "float", "low": -1.0, "high": 1.0}}
RESTORATION_SPACE = {"lr": {"type": "float", "low": 1e-5, "high": 1e-2, "log": True, "why": "learning rate"},
                     "width": {"type": "int", "low": 16, "high": 128, "step": 16, "why": "feature channels"},
                     "depth": {"type": "int", "low": 2, "high": 16, "why": "number of blocks"},
                     "attention": {"type": "bool", "why": "channel attention on/off"}}
TINY_SPEC = {"input_shape": [3, 64, 64], "layers": [
    {"type": "conv2d", "in": 3, "out": 32, "k": 3, "padding": 1}, {"type": "act"},
    {"type": "conv2d", "in": 32, "out": 32, "k": 3, "padding": 1}, {"type": "act"},
    {"type": "conv2d", "in": 32, "out": 3, "k": 3, "padding": 1}]}

BUILTIN = [
    {"id": "research_planning", "version": 1, "name": "Research planning",
     "description": "Turn a research request into a structured, reviewable plan. No training starts.",
     "execution_mode": "assisted",
     "inputs": {"objective": {"type": "string", "required": True}, "constraints": {"type": "object", "default": {}}},
     "steps": [
         {"id": "state", "type": "research.state", "label": "Current research state"},
         {"id": "context", "type": "research.context", "params": {"query": R("inputs.objective")}, "label": "Evidence & prior experiments"},
         {"id": "plan", "type": "agent.plan", "depends_on": ["state", "context"], "label": "Harness proposes a plan",
          "params": {"objective": R("inputs.objective"), "context": R("steps.context.output.context"),
                     "constraints": R("inputs.constraints")}},
         {"id": "approve_plan", "type": "human.approval", "depends_on": ["plan"], "label": "Researcher approves the plan",
          "params": {"question": "Approve this research plan?", "show": R("steps.plan.output.plan")}},
         {"id": "save", "type": "report.generate", "depends_on": ["approve_plan"], "label": "Save plan + provenance",
          "params": {"title": "Approved research plan", "sections": {"plan": R("steps.plan.output.plan"),
                                                                      "context_ids": R("steps.context.output.included_ids")}}}],
     "outputs": {"plan": "steps.plan.output.plan", "report": "steps.save.output.relative"}},

    {"id": "model_feasibility", "version": 1, "name": "Model feasibility audit",
     "description": "Parameters, MACs/FLOPs and memory vs. this PC before any expensive training.",
     "execution_mode": "manual",
     "inputs": {"spec": {"type": "object", "default": TINY_SPEC}, "batch_size": {"type": "integer", "default": 8},
                "precision": {"type": "string", "default": "fp32"}, "optimizer": {"type": "string", "default": "adam"}},
     "steps": [
         {"id": "inspect", "type": "model.inspect", "label": "Complexity analysis",
          "params": {"adapter": "spec", "spec": R("inputs.spec")}},
         {"id": "feasible", "type": "model.feasibility", "depends_on": ["inspect"], "label": "Hardware check",
          "params": {"report": R("steps.inspect.output.report"), "batch_size": R("inputs.batch_size"),
                     "precision": R("inputs.precision"), "optimizer": R("inputs.optimizer")}},
         {"id": "report", "type": "report.generate", "depends_on": ["feasible"], "label": "Feasibility report",
          "params": {"title": "Model feasibility audit", "sections": {"complexity": R("steps.inspect.output.report"),
                                                                       "feasibility": R("steps.feasible.output")}}}],
     "outputs": {"feasible": "steps.feasible.output.feasible", "report": "steps.inspect.output.report",
                 "file": "steps.report.output.relative"}},

    {"id": "search_space_design", "version": 1, "name": "Search-space design",
     "description": "The harness proposes tunable parameters; a deterministic validator approves the structure; you edit.",
     "execution_mode": "assisted",
     "inputs": {"objectives": {"type": "array", "default": [{"name": "loss", "direction": "minimize"}]},
                "model_report": {"type": "object", "default": {}}, "baseline": {"type": "object", "default": {}},
                "hint": {"type": "string", "default": ""}, "max_trials": {"type": "integer", "default": 20}},
     "steps": [
         {"id": "propose", "type": "hpo.propose_search_space", "label": "Harness proposes a search space",
          "params": {"objectives": R("inputs.objectives"), "model_report": R("inputs.model_report"),
                     "baseline": R("inputs.baseline"), "hint": R("inputs.hint")}},
         {"id": "validate", "type": "hpo.validate_search_space", "depends_on": ["propose"], "label": "Deterministic validation",
          "params": {"search_space": R("steps.propose.output.search_space"), "objectives": R("inputs.objectives"),
                     "max_trials": R("inputs.max_trials")}},
         {"id": "approve", "type": "human.approval", "depends_on": ["validate"], "label": "Approve the search space",
          "params": {"question": "Approve this search space (versioned artifact)?", "show": R("steps.validate.output")}}],
     "outputs": {"search_space": "steps.validate.output.params", "warnings": "steps.validate.output.warnings"}},

    {"id": "hpo", "version": 1, "name": "Hyperparameter optimisation",
     "description": "Bounded Optuna study through the local sequential runner, ranked and verified.",
     "execution_mode": "assisted", "budgets": {"max_trials": 20, "max_runtime_minutes": 60},
     "inputs": {"search_space": {"type": "object", "default": QUAD_SPACE},
                "objectives": {"type": "array", "default": [{"name": "loss", "direction": "minimize"}]},
                "objective": {"type": "object", "default": ANALYTIC_DEFAULT}, "max_trials": {"type": "integer", "default": 20},
                "sampler": {"type": "string", "default": "auto"}, "seed": {"type": "integer", "default": 0},
                "baseline": {"type": "object", "default": {}}},
     "steps": [
         {"id": "validate", "type": "hpo.validate_search_space", "label": "Validate the search space",
          "params": {"search_space": R("inputs.search_space"), "objectives": R("inputs.objectives"),
                     "max_trials": R("inputs.max_trials"), "sampler": R("inputs.sampler")}},
         {"id": "run", "type": "hpo.run", "depends_on": ["validate"], "label": "Run the study",
          "params": {"search_space": R("steps.validate.output.params"), "objectives": R("inputs.objectives"),
                     "max_trials": R("steps.validate.output.max_trials"), "sampler": R("inputs.sampler"),
                     "seed": R("inputs.seed"), "objective": R("inputs.objective")}},
         {"id": "compare", "type": "evaluation.compare_trials", "depends_on": ["run"], "label": "Rank candidates",
          "params": {"study_id": R("steps.run.output.study_id"), "baseline": R("inputs.baseline")}},
         {"id": "verify", "type": "verification.check", "depends_on": ["compare"], "label": "Verify protocol & metrics",
          "params": {"study_id": R("steps.run.output.study_id")}},
         {"id": "report", "type": "report.generate", "depends_on": ["verify"], "label": "Reproducibility report",
          "params": {"title": "HPO study", "sections": {"study": R("steps.run.output"), "ranking": R("steps.compare.output"),
                                                         "verification": R("steps.verify.output")}}}],
     "outputs": {"best": "steps.run.output.best", "ranking": "steps.compare.output.top", "study_id": "steps.run.output.study_id",
                 "report": "steps.report.output.relative"}},

    {"id": "multi_objective", "version": 1, "name": "Multi-objective optimisation",
     "description": "Quality vs. computational cost: Pareto front with explained trade-offs (no 'universal best').",
     "execution_mode": "assisted", "budgets": {"max_trials": 30, "max_runtime_minutes": 60},
     "inputs": {"search_space": {"type": "object", "default": RESTORATION_SPACE},
                "objectives": {"type": "array", "default": [{"name": "psnr", "direction": "maximize"},
                                                            {"name": "params_m", "direction": "minimize"}]},
                "objective": {"type": "object", "default": {"kind": "analytic", "function": "restoration_proxy"}},
                "max_trials": {"type": "integer", "default": 30}, "seed": {"type": "integer", "default": 0}},
     "steps": [
         {"id": "validate", "type": "hpo.validate_search_space", "label": "Validate the search space",
          "params": {"search_space": R("inputs.search_space"), "objectives": R("inputs.objectives"),
                     "max_trials": R("inputs.max_trials"), "sampler": "auto"}},
         {"id": "run", "type": "hpo.run", "depends_on": ["validate"], "label": "Multi-objective study",
          "params": {"search_space": R("steps.validate.output.params"), "objectives": R("inputs.objectives"),
                     "max_trials": R("steps.validate.output.max_trials"), "seed": R("inputs.seed"),
                     "objective": R("inputs.objective")}},
         {"id": "compare", "type": "evaluation.compare_trials", "depends_on": ["run"], "label": "Pareto front",
          "params": {"study_id": R("steps.run.output.study_id"), "top_k": 5}},
         {"id": "interpret", "type": "agent.interpret", "depends_on": ["compare"], "label": "Explain the trade-offs",
          "params": {"results": R("steps.compare.output.pareto"),
                     "hypothesis": "Which configurations trade quality against cost, and where is the knee of the front?"}}],
     "outputs": {"pareto": "steps.compare.output.pareto", "interpretation": "steps.interpret.output.interpretation"}},

    {"id": "failure_diagnosis", "version": 1, "name": "Failure diagnosis",
     "description": "Classify a failed run, find similar failures, propose safe adjustments, record it with provenance.",
     "execution_mode": "assisted",
     "inputs": {"error": {"type": "string", "required": True}, "run_id": {"type": "string", "default": ""},
                "config": {"type": "object", "default": {}}},
     "steps": [
         {"id": "diagnose", "type": "failure.diagnose", "label": "Classify & diagnose",
          "params": {"error": R("inputs.error"), "run_id": R("inputs.run_id"), "config": R("inputs.config")}},
         {"id": "approve", "type": "human.approval", "depends_on": ["diagnose"], "label": "Approve the recovery actions",
          "params": {"question": "Apply only the approved, safe adjustments?", "show": R("steps.diagnose.output")}},
         {"id": "record", "type": "memory.propose", "depends_on": ["approve"], "label": "Record the failure (candidate)",
          "params": {"kind": "failure", "text": R("inputs.error")}}],
     "outputs": {"diagnosis": "steps.diagnose.output", "candidate": "steps.record.output.candidate_id"}},

    {"id": "researcher_led_experiment", "version": 1, "name": "Researcher-led experiment",
     "description": "Automate execution, not scientific judgement: your hypothesis and config, sandboxed run, your verdict.",
     "execution_mode": "custom",
     "inputs": {"hypothesis": {"type": "string", "required": True}, "command": {"type": "string", "required": True}},
     "steps": [
         {"id": "config", "type": "human.input", "label": "Confirm hypothesis & configuration",
          "params": {"prompt": "Confirm (or edit) the hypothesis and the command to run", "fields": {"notes": "string"}}},
         {"id": "plan", "type": "agent.plan", "mode": "assisted", "depends_on": ["config"], "label": "Execution plan",
          "params": {"objective": R("inputs.hypothesis"), "constraints": R("steps.config.output")}},
         {"id": "run", "type": "sandbox.run", "mode": "manual", "depends_on": ["plan"], "label": "Sandboxed run",
          "params": {"command": R("inputs.command")}},
         {"id": "interpret", "type": "agent.interpret", "mode": "assisted", "depends_on": ["run"], "label": "Summarise vs. hypothesis",
          "params": {"results": R("steps.run.output"), "hypothesis": R("inputs.hypothesis")}},
         {"id": "verdict", "type": "human.approval", "depends_on": ["interpret"], "label": "Accept / reject the interpretation",
          "params": {"question": "Accept this interpretation as your conclusion?", "show": R("steps.interpret.output")}}],
     "outputs": {"run": "steps.run.output", "interpretation": "steps.interpret.output.interpretation"}},

    {"id": "full_bounded_loop", "version": 1, "name": "Full bounded research loop",
     "description": "Plan → feasibility → search space → bounded HPO cycles → verification → interpretation, with gates.",
     "execution_mode": "bounded",
     "budgets": {"max_trials": 40, "max_workflow_cycles": 2, "max_runtime_minutes": 120, "max_parallel_trials": 1,
                 "max_agent_calls": 10},
     "inputs": {"objective": {"type": "string", "required": True}, "spec": {"type": "object", "default": TINY_SPEC},
                "search_space": {"type": "object", "default": QUAD_SPACE},
                "objectives": {"type": "array", "default": [{"name": "loss", "direction": "minimize"}]},
                "objective_fn": {"type": "object", "default": ANALYTIC_DEFAULT}},
     "steps": [
         {"id": "context", "type": "research.context", "params": {"query": R("inputs.objective")}, "label": "Research context"},
         {"id": "plan", "type": "agent.plan", "depends_on": ["context"], "label": "Plan",
          "params": {"objective": R("inputs.objective"), "context": R("steps.context.output.context")}},
         {"id": "approve_objective", "type": "human.approval", "depends_on": ["plan"], "label": "Approve objective & budget",
          "params": {"question": "Approve the objective and the budget of this loop?", "show": R("steps.plan.output.plan")}},
         {"id": "feasibility", "type": "workflow.call", "depends_on": ["approve_objective"], "label": "Model feasibility (nested)",
          "params": {"workflow": "model_feasibility", "inputs": {"spec": R("inputs.spec")}}},
         {"id": "cycles", "type": "workflow.repeat", "depends_on": ["feasibility"], "label": "Bounded HPO cycles",
          "params": {"workflow": "hpo", "max_cycles": 2, "until": {"ref": "last.best", "op": "exists"},
                     "inputs": {"search_space": R("inputs.search_space"), "objectives": R("inputs.objectives"),
                                "objective": R("inputs.objective_fn"), "max_trials": 10}}},
         {"id": "interpret", "type": "agent.interpret", "depends_on": ["cycles"], "label": "Interpret vs. objective",
          "params": {"results": R("steps.cycles.output.last"), "hypothesis": R("inputs.objective")}}],
     "outputs": {"cycles": "steps.cycles.output.cycles", "interpretation": "steps.interpret.output.interpretation"}},

    {"id": "ablation_study", "version": 1, "name": "Ablation study",
     "description": "Variants that remove exactly one component, evaluated with one protocol; you approve the reading.",
     "execution_mode": "assisted", "budgets": {"max_trials": 30},
     "inputs": {"baseline_config": {"type": "object", "default": {"lr": 0.001, "width": 64, "depth": 8, "attention": True}},
                "components": {"type": "array", "default": ["attention"]},
                "objective": {"type": "object", "default": {"kind": "analytic", "function": "restoration_proxy"}},
                "objectives": {"type": "array", "default": [{"name": "psnr", "direction": "maximize"}]},
                "seeds": {"type": "array", "default": [1, 2, 3]}},
     "steps": [
         {"id": "variants", "type": "ablation.generate", "label": "Generate variants",
          "params": {"baseline_config": R("inputs.baseline_config"), "components": R("inputs.components")}},
         {"id": "evaluate", "type": "evaluation.run_configs", "depends_on": ["variants"], "label": "Evaluate baseline + variants",
          "params": {"configs": [{"name": "baseline", "config": R("inputs.baseline_config")}, R("steps.variants.output.variants.0")],
                     "objective": R("inputs.objective"), "objectives": R("inputs.objectives"), "seeds": R("inputs.seeds")}},
         {"id": "interpret", "type": "agent.interpret", "depends_on": ["evaluate"], "label": "Interpret the ablation",
          "params": {"results": R("steps.evaluate.output"), "hypothesis": "Each removed component lowers quality."}}],
     "outputs": {"table": "steps.evaluate.output.results"}},

    {"id": "candidate_confirmation", "version": 1, "name": "Candidate confirmation",
     "description": "Repeat the best HPO candidates with new seeds; variance, CI and baseline before any conclusion.",
     "execution_mode": "assisted",
     "inputs": {"study_id": {"type": "string", "required": True}, "top_k": {"type": "integer", "default": 2},
                "seeds": {"type": "array", "default": [101, 202, 303]}, "baseline": {"type": "object", "default": {}}},
     "steps": [
         {"id": "confirm", "type": "evaluation.confirm", "label": "Confirmation runs",
          "params": {"study_id": R("inputs.study_id"), "top_k": R("inputs.top_k"), "seeds": R("inputs.seeds"),
                     "baseline": R("inputs.baseline")}},
         {"id": "report", "type": "report.generate", "depends_on": ["confirm"], "label": "Confirmation report",
          "params": {"title": "Candidate confirmation", "sections": {"confirmation": R("steps.confirm.output")}}},
         {"id": "approve", "type": "human.approval", "depends_on": ["report"], "label": "Approve the conclusion",
          "params": {"question": "Approve this research conclusion?", "show": R("steps.confirm.output")}}],
     "outputs": {"confirmation": "steps.confirm.output", "report": "steps.report.output.relative"}},

    {"id": "planning_with_feasibility", "version": 1, "name": "Planning → feasibility → search space (nested)",
     "description": "Scenario H: the planning workflow calls the feasibility audit and only designs a search space "
                    "when the model fits this PC.",
     "execution_mode": "assisted",
     "inputs": {"objective": {"type": "string", "required": True}, "spec": {"type": "object", "default": TINY_SPEC}},
     "steps": [
         {"id": "plan", "type": "workflow.call", "label": "Research planning (nested)",
          "params": {"workflow": "research_planning", "inputs": {"objective": R("inputs.objective")}}},
         {"id": "feasibility", "type": "workflow.call", "depends_on": ["plan"], "label": "Feasibility audit (nested)",
          "params": {"workflow": "model_feasibility", "inputs": {"spec": R("inputs.spec")}}},
         {"id": "space", "type": "workflow.call", "depends_on": ["feasibility"], "label": "Search-space design (nested)",
          "when": {"ref": "steps.feasibility.output.feasible", "op": "ne", "value": False},
          "params": {"workflow": "search_space_design", "inputs": {"model_report": R("steps.feasibility.output.report")}}}],
     "outputs": {"feasible": "steps.feasibility.output.feasible", "search_space": "steps.space.output.search_space"}},
]
BUILTIN_IDS = {t["id"] for t in BUILTIN}
FILE_RE = re.compile(r"^([a-z][a-z0-9_]{1,63})@(\d{1,4})\.json$")


def _dir():
    from ..config import data_dir
    d = data_dir() / "workflows" / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def saved() -> list:
    out = []
    for f in _dir().glob("*.json"):
        if not FILE_RE.match(f.name):
            continue
        try:
            d = json.loads(f.read_text("utf-8"))
            d["builtin"] = False
            out.append(d)
        except (OSError, ValueError):
            continue
    return out


def all_templates() -> list:
    return [dict(copy.deepcopy(t), builtin=True) for t in BUILTIN] + saved()


def get(workflow_id: str, version: int | None = None) -> dict | None:
    cands = [t for t in all_templates() if t["id"] == workflow_id and (version is None or int(t["version"]) == int(version))]
    if not cands:
        return None
    return max(cands, key=lambda t: int(t["version"]))


def save(defn: dict) -> dict:
    """Store a validated user workflow. Built-in ids cannot be shadowed; an existing version is never overwritten."""
    if defn["id"] in BUILTIN_IDS:
        raise ValueError(f"'{defn['id']}' is a built-in template — save your variant under another id")
    f = _dir() / f"{defn['id']}@{int(defn['version'])}.json"
    if f.exists():
        raise ValueError(f"{defn['id']} version {defn['version']} already exists — bump the version")
    clean = {k: v for k, v in defn.items() if k != "builtin"}
    f.write_text(json.dumps(clean, indent=1, ensure_ascii=False), "utf-8")
    return clean


def delete(workflow_id: str, version: int) -> bool:
    if workflow_id in BUILTIN_IDS:
        raise ValueError("built-in templates cannot be deleted")
    f = _dir() / f"{workflow_id}@{int(version)}.json"
    if not FILE_RE.match(f.name) or not f.exists():
        return False
    f.unlink()
    return True


def call_graph_ok(defn: dict, depth: int = 0, seen: tuple = ()) -> list:
    """Nested workflows must exist and must not call themselves (directly or indirectly); depth ≤ 4."""
    errs = []
    if depth > 4:
        return [f"nesting deeper than 4 levels at {defn['id']}"]
    for s in defn.get("steps", []):
        if s.get("type") in ("workflow.call", "workflow.repeat"):
            wid = (s.get("params") or {}).get("workflow")
            if not isinstance(wid, str):
                errs.append(f"step {s.get('id')}: params.workflow must be a literal workflow id")
                continue
            if wid == defn["id"] or wid in seen:
                errs.append(f"step {s.get('id')}: workflow '{wid}' would call itself")
                continue
            child = get(wid)
            if child is None:
                errs.append(f"step {s.get('id')}: unknown workflow '{wid}'")
                continue
            errs += call_graph_ok(child, depth + 1, seen + (defn["id"],))
    return errs
