"""Workflow contracts (v4.1 M1): typed, versioned workflow definitions validated against a server-side allowlist.

A definition is plain JSON (what the UI edits and what is stored); `validate()` returns a normalised copy or a list of
errors. Nothing in a definition is ever executed as code: conditions and parameter references use a tiny declarative
language resolved by `resolve()` / `evaluate()` (no eval).

    {"id": "image_restoration_hpo", "name": "...", "version": 1, "execution_mode": "assisted",
     "inputs": {"objective": {"type": "string", "required": true}},
     "budgets": {"max_trials": 30, "max_workflow_cycles": 3, "max_parallel_trials": 1, "max_runtime_minutes": 240,
                 "max_gpu_memory_gb": 10.5, "max_agent_calls": 20},
     "approvals": {"before_training": "required", ...},
     "failure_policy": "fail_fast", "allowed_tools": [],          # [] = every registered step type
     "steps": [{"id": "inspect", "type": "model.inspect", "mode": "automatic", "depends_on": [], "params": {...},
                "when": {"ref": "steps.x.output.ok", "op": "eq", "value": true}, "retry": {"max": 1}, "timeout_s": 600}],
     "outputs": {"best": "steps.run_study.output.best"}}

References inside params: {"$ref": "inputs.objective"} or {"$ref": "steps.inspect.output.report"}.
"""
from __future__ import annotations

import copy
import re

EXECUTION_MODES = ("manual", "assisted", "bounded", "custom")
STEP_MODES = ("manual", "assisted", "automatic")
RUN_STATES = ("CREATED", "VALIDATING", "READY", "RUNNING", "WAITING_FOR_APPROVAL", "PAUSED", "SUCCEEDED", "FAILED",
              "CANCELLED", "BUDGET_EXCEEDED")
STEP_STATES = ("PENDING", "READY", "RUNNING", "WAITING_FOR_APPROVAL", "SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED")
TERMINAL_RUN = ("SUCCEEDED", "FAILED", "CANCELLED", "BUDGET_EXCEEDED")
TERMINAL_STEP = ("SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED")
FAILURE_POLICIES = ("fail_fast", "continue")
APPROVAL_KEYS = ("before_training", "before_parallel_gpu_trials", "before_research_state_writeback", "before_conclusion")
APPROVAL_VALUES = ("required", "not_required")
DEFAULT_APPROVALS = {k: "required" for k in APPROVAL_KEYS}
BUDGET_KEYS = {"max_trials": int, "max_workflow_cycles": int, "max_parallel_trials": int, "max_runtime_minutes": float,
               "max_gpu_memory_gb": float, "max_agent_calls": int}
DEFAULT_BUDGETS = {"max_trials": 20, "max_workflow_cycles": 3, "max_parallel_trials": 1, "max_runtime_minutes": 120,
                   "max_gpu_memory_gb": 0, "max_agent_calls": 20}
OPS = ("eq", "ne", "gt", "ge", "lt", "le", "in", "truthy", "falsy", "exists")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
REF_RE = re.compile(r"^(inputs|steps|last)(\.[A-Za-z0-9_\-]+)*$")
INPUT_TYPES = ("string", "number", "integer", "boolean", "object", "array", "any")
MAX_STEPS = 60


class WorkflowError(ValueError):
    pass


# ------------------------------------------------------------------ references & conditions (no eval)
def _walk(obj, path: list):
    cur = obj
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif isinstance(cur, list) and p.isdigit() and int(p) < len(cur):
            cur = cur[int(p)]
        else:
            return None, False
    return cur, True


def resolve_ref(ref: str, scope: dict):
    """'inputs.a.b' | 'steps.<id>.output.x' | 'steps.<id>.status' | 'last.x' → value (None when missing)."""
    if not isinstance(ref, str) or not REF_RE.match(ref):
        raise WorkflowError(f"invalid reference {ref!r}")
    val, _ = _walk(scope, ref.split("."))
    return copy.deepcopy(val)


def resolve(value, scope: dict):
    """Replace every {"$ref": "..."} in a params structure by the referenced value."""
    if isinstance(value, dict):
        if set(value) == {"$ref"}:
            return resolve_ref(value["$ref"], scope)
        return {k: resolve(v, scope) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, scope) for v in value]
    return value


def refs_in(value) -> list:
    out = []
    if isinstance(value, dict):
        if set(value) == {"$ref"}:
            return [value["$ref"]]
        for v in value.values():
            out += refs_in(v)
    elif isinstance(value, list):
        for v in value:
            out += refs_in(v)
    return out


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def evaluate(cond, scope: dict) -> bool:
    if cond is None:
        return True
    if "all" in cond:
        return all(evaluate(c, scope) for c in cond["all"])
    if "any" in cond:
        return any(evaluate(c, scope) for c in cond["any"])
    if "not" in cond:
        return not evaluate(cond["not"], scope)
    _, found = _walk(scope, cond["ref"].split("."))
    v = resolve_ref(cond["ref"], scope)
    op, want = cond["op"], cond.get("value")
    if op == "exists":
        return found and v is not None
    if op == "truthy":
        return bool(v)
    if op == "falsy":
        return not v
    if op == "eq":
        return v == want
    if op == "ne":
        return v != want
    if op == "in":
        return isinstance(want, list) and v in want
    if not (_num(v) and _num(want)):
        return False
    return {"gt": v > want, "ge": v >= want, "lt": v < want, "le": v <= want}[op]


def cond_refs(cond) -> list:
    if cond is None:
        return []
    for k in ("all", "any"):
        if k in cond:
            return [r for c in cond[k] for r in cond_refs(c)]
    if "not" in cond:
        return cond_refs(cond["not"])
    return [cond["ref"]]


def check_cond(cond, where: str, errors: list) -> None:
    if cond is None:
        return
    if not isinstance(cond, dict):
        errors.append(f"{where}: condition must be an object")
        return
    for k in ("all", "any"):
        if k in cond:
            if not isinstance(cond[k], list) or not cond[k]:
                errors.append(f"{where}: '{k}' needs a non-empty list")
                return
            for c in cond[k]:
                check_cond(c, where, errors)
            return
    if "not" in cond:
        check_cond(cond["not"], where, errors)
        return
    if not isinstance(cond.get("ref"), str) or not REF_RE.match(cond["ref"]):
        errors.append(f"{where}: condition needs a valid 'ref'")
    if cond.get("op") not in OPS:
        errors.append(f"{where}: op must be one of {', '.join(OPS)}")


# ------------------------------------------------------------------ validation
def _ref_target_ok(ref: str, ancestors: set, inputs: dict, where: str, errors: list) -> None:
    parts = ref.split(".")
    if parts[0] == "inputs":
        if len(parts) < 2 or parts[1] not in inputs:
            errors.append(f"{where}: reference to unknown input '{ref}'")
    elif parts[0] == "steps":
        if len(parts) < 3 or parts[1] not in ancestors or parts[2] not in ("output", "status"):
            errors.append(f"{where}: '{ref}' must point to steps.<an upstream step>.output|status")


def _topo(steps: list) -> list | None:
    deps = {s["id"]: set(s["depends_on"]) for s in steps}
    order, ready = [], [s["id"] for s in steps if not deps[s["id"]]]
    while ready:
        n = ready.pop(0)
        order.append(n)
        for s in steps:
            if n in deps[s["id"]]:
                deps[s["id"]].discard(n)
                if not deps[s["id"]] and s["id"] not in order and s["id"] not in ready:
                    ready.append(s["id"])
    return order if len(order) == len(steps) else None


def _ancestors(sid: str, by_id: dict, memo: dict) -> set:
    if sid in memo:
        return memo[sid]
    out = set()
    for d in by_id[sid]["depends_on"]:
        out |= {d} | _ancestors(d, by_id, memo)
    memo[sid] = out
    return out


def validate(defn: dict, step_types: dict, caps: dict | None = None, features: dict | None = None) -> tuple[dict, list]:
    """(normalised definition, errors). step_types: registry {name: StepType}; caps: config.workflow hard caps."""
    errors: list = []
    if not isinstance(defn, dict):
        return {}, ["definition must be an object"]
    d = copy.deepcopy(defn)
    caps = caps or {}
    if not isinstance(d.get("id"), str) or not ID_RE.match(d["id"]):
        errors.append("id: lowercase letters, digits and _ (2-64 chars, starting with a letter)")
    d["name"] = str(d.get("name") or d.get("id") or "")[:120]
    try:
        d["version"] = int(d.get("version", 1))
        if d["version"] < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("version must be a positive integer")
        d["version"] = 1
    d["description"] = str(d.get("description") or "")[:2000]
    mode = d.setdefault("execution_mode", "assisted")
    if mode not in EXECUTION_MODES:
        errors.append(f"execution_mode must be one of {', '.join(EXECUTION_MODES)}")
    if d.setdefault("failure_policy", "fail_fast") not in FAILURE_POLICIES:
        errors.append(f"failure_policy must be one of {', '.join(FAILURE_POLICIES)}")
    # inputs
    inputs = d.setdefault("inputs", {})
    if not isinstance(inputs, dict):
        errors.append("inputs must be an object")
        inputs = d["inputs"] = {}
    for name, spec in inputs.items():
        if not ID_RE.match(name) or not isinstance(spec, dict) or spec.get("type", "any") not in INPUT_TYPES:
            errors.append(f"inputs.{name}: needs a valid name and type ({', '.join(INPUT_TYPES)})")
    # budgets
    b = dict(DEFAULT_BUDGETS)
    for k, v in (d.get("budgets") or {}).items():
        if k not in BUDGET_KEYS:
            errors.append(f"budgets.{k}: unknown budget")
            continue
        try:
            b[k] = BUDGET_KEYS[k](v)
            if b[k] < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"budgets.{k}: must be a non-negative number")
    for k, capk in (("max_trials", "max_trials_cap"), ("max_runtime_minutes", "max_runtime_minutes_cap"),
                    ("max_parallel_trials", "max_parallel_trials_cap"), ("max_workflow_cycles", "max_workflow_cycles_cap")):
        if caps.get(capk) and b[k] > caps[capk]:
            errors.append(f"budgets.{k}={b[k]} exceeds the hard cap {caps[capk]} (Settings → workflow)")
    if mode == "bounded":
        for k in ("max_trials", "max_runtime_minutes", "max_workflow_cycles"):
            if not b[k]:
                errors.append(f"bounded automation needs an explicit budgets.{k} > 0")
    d["budgets"] = b
    # approvals
    ap = dict(DEFAULT_APPROVALS)
    for k, v in (d.get("approvals") or {}).items():
        if k not in APPROVAL_KEYS or v not in APPROVAL_VALUES:
            errors.append(f"approvals.{k}: must be one of {', '.join(APPROVAL_VALUES)} for a known gate")
        else:
            ap[k] = v
    d["approvals"] = ap
    allowed = d.setdefault("allowed_tools", [])
    if not isinstance(allowed, list) or any(t not in step_types for t in allowed):
        errors.append("allowed_tools must list registered step types")
        allowed = d["allowed_tools"] = []
    # steps
    steps = d.get("steps")
    if not isinstance(steps, list) or not steps:
        return d, errors + ["steps: at least one step is required"]
    if len(steps) > MAX_STEPS:
        errors.append(f"steps: at most {MAX_STEPS}")
    seen = set()
    for i, s in enumerate(steps):
        where = f"steps[{i}]"
        if not isinstance(s, dict):
            errors.append(f"{where}: must be an object")
            steps[i] = s = {"id": f"invalid_{i}", "type": "", "depends_on": []}
        sid = s.get("id")
        if not isinstance(sid, str) or not ID_RE.match(sid):
            errors.append(f"{where}: invalid id")
        elif sid in seen:
            errors.append(f"{where}: duplicate id '{sid}'")
        seen.add(sid)
        st = step_types.get(s.get("type"))
        if st is None:
            errors.append(f"{where} ({sid}): step type '{s.get('type')}' is not on the server allowlist")
        elif allowed and s["type"] not in allowed:
            errors.append(f"{where} ({sid}): step type '{s['type']}' is not in allowed_tools")
        elif features is not None and st.feature and not features.get(st.feature, True):
            errors.append(f"{where} ({sid}): '{s['type']}' needs the feature flag {st.feature}")
        if "mode" in s and s["mode"] not in STEP_MODES:
            errors.append(f"{where} ({sid}): mode must be one of {', '.join(STEP_MODES)}")
        if mode == "custom" and st is not None and st.kind != "human" and "mode" not in s:
            errors.append(f"{where} ({sid}): a custom workflow sets the mode of every step")
        s["depends_on"] = list(s.get("depends_on") or [])
        s["params"] = s.get("params") or {}
        if not isinstance(s["params"], dict):
            errors.append(f"{where} ({sid}): params must be an object")
            s["params"] = {}
        try:
            s["retry"] = {"max": max(0, min(5, int((s.get("retry") or {}).get("max", 0))))}
            s["timeout_s"] = max(0, int(s.get("timeout_s") or 0))
        except (TypeError, ValueError, AttributeError):
            errors.append(f"{where} ({sid}): retry.max / timeout_s must be integers")
            s["retry"], s["timeout_s"] = {"max": 0}, 0
        s["label"] = str(s.get("label") or sid)[:120]
        check_cond(s.get("when"), f"{where} ({sid}).when", errors)
        if st is not None:
            for pname, (ptype, required) in st.params.items():
                v = s["params"].get(pname)
                if v is None:
                    if required:
                        errors.append(f"{where} ({sid}): params.{pname} is required")
                    continue
                if isinstance(v, dict) and set(v) == {"$ref"}:
                    continue
                if ptype and not _type_ok(v, ptype):
                    errors.append(f"{where} ({sid}): params.{pname} must be {ptype}")
            unknown = set(s["params"]) - set(st.params)
            if unknown:
                errors.append(f"{where} ({sid}): unknown params {', '.join(sorted(unknown))}")
    by_id = {s.get("id"): s for s in steps if isinstance(s, dict)}
    for s in steps:
        for dep in s["depends_on"]:
            if dep not in by_id or dep == s["id"]:
                errors.append(f"step {s['id']}: depends_on '{dep}' is not another step")
    if errors:
        return d, errors
    if _topo(steps) is None:
        return d, ["steps: dependency cycle"]
    memo: dict = {}
    for s in steps:
        anc = _ancestors(s["id"], by_id, memo)
        for r in refs_in(s["params"]) + cond_refs(s.get("when")):
            if not REF_RE.match(r):
                errors.append(f"step {s['id']}: invalid reference {r!r}")
            else:
                _ref_target_ok(r, anc, inputs, f"step {s['id']}", errors)
    outs = d.setdefault("outputs", {})
    if not isinstance(outs, dict):
        errors.append("outputs must map names to references")
    else:
        for k, r in outs.items():
            if not isinstance(r, str) or not REF_RE.match(r) or not r.startswith("steps."):
                errors.append(f"outputs.{k}: must be a 'steps.<id>.output…' reference")
            elif r.split(".")[1] not in by_id:
                errors.append(f"outputs.{k}: unknown step in {r}")
    return d, errors


def _type_ok(v, t: str) -> bool:
    return {"string": isinstance(v, str), "number": _num(v), "integer": isinstance(v, int) and not isinstance(v, bool),
            "boolean": isinstance(v, bool), "object": isinstance(v, dict), "array": isinstance(v, list)}.get(t, True)


def check_inputs(defn: dict, given: dict) -> tuple[dict, list]:
    out, errors = {}, []
    given = given or {}
    for name, spec in defn.get("inputs", {}).items():
        if name in given:
            if not _type_ok(given[name], spec.get("type", "any")):
                errors.append(f"input {name} must be {spec.get('type')}")
            out[name] = given[name]
        elif "default" in spec:
            out[name] = copy.deepcopy(spec["default"])
        elif spec.get("required"):
            errors.append(f"input {name} is required")
    extra = set(given) - set(defn.get("inputs", {}))
    if extra:
        errors.append(f"unknown inputs: {', '.join(sorted(extra))}")
    return out, errors


def default_step_mode(exec_mode: str, kind: str, risk: str) -> str:
    """Execution mode → default autonomy of one step (an explicit step mode always wins)."""
    if exec_mode == "bounded":
        return "automatic"
    if exec_mode == "manual":
        return "manual" if risk == "high" else "assisted"
    # assisted (and custom steps without a mode — only human steps reach this)
    if risk == "high":
        return "manual"
    return "assisted" if kind == "agent" else "automatic"
