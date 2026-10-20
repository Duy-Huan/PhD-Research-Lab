"""Semantic research tools of the MCP gateway (v3.4 §5-6) — the same research brain for Claude Code, Codex (ChatGPT plan),
Antigravity / Gemini CLI and any other MCP client.

Names use underscores (research_get_current_state …) because several clients only accept ^[A-Za-z0-9_-]{1,64}$ tool
names; the dotted spelling of the spec (research.get_current_state) is accepted as an alias in tools/call.

Every tool: strict JSON schema (additionalProperties: false) validated server-side, minimal permission (read tools never
write; record tools only create review CANDIDATES — lifecycle.py), structured output (structuredContent + text),
provenance (record ids, context_version, project) and the sensitivity policy (MCP clients are external models:
records the policy blocks are never returned; text is sanitised). No raw database / filesystem access.
"""
from __future__ import annotations

import json
import re
import time

ID = {"type": "string", "pattern": r"^(HYPE|EXP|FAIL|CLM|EVID)-\d{3,6}$"}
METRIC = {"type": "object", "additionalProperties": False, "required": ["name", "value"],
          "properties": {"name": {"type": "string", "maxLength": 60}, "value": {"type": "number"}, "unit": {"type": "string", "maxLength": 20}}}
ROLE = {"type": "string", "enum": ["literature", "experiment_designer", "coder", "reviewer", "writer", "director", "default"]}
Q = {"type": "string", "minLength": 1, "maxLength": 2000}


def _obj(props: dict, required=()) -> dict:
    return {"type": "object", "additionalProperties": False, "properties": props, "required": list(required)}


TOOLS = [
    {"name": "research_get_current_state", "group": "read",
     "description": "The project's current research state: objective, active hypothesis, current experiment, constraints, "
                    "locked decisions, known failures, best results. Call this first.",
     "inputSchema": _obj({})},
    {"name": "research_search_memory", "group": "read",
     "description": "Research-state-aware hybrid search over the project memory (experiments, failures, decisions, evidence, "
                    "claims, papers). Every hit explains why it was retrieved.",
     "inputSchema": _obj({"query": Q, "role": ROLE, "k": {"type": "integer", "minimum": 1, "maximum": 50},
                          "filters": _obj({"types": {"type": "array", "items": {"type": "string", "maxLength": 20}, "maxItems": 10},
                                           "dataset": {"type": "string", "maxLength": 80}, "model": {"type": "string", "maxLength": 80},
                                           "source_type": {"type": "string", "maxLength": 20},
                                           "evidence_status": {"type": "string", "enum": ["candidate", "validated", "rejected"]},
                                           "since": {"type": "string", "maxLength": 30}, "until": {"type": "string", "maxLength": 30}})},
                         ["query"])},
    {"name": "research_get_hypothesis", "group": "read",
     "description": "One hypothesis (HYPE-…) with its experiments, claims and failures.",
     "inputSchema": _obj({"id": {"type": "string", "pattern": r"^HYPE-\d{3,6}$"}}, ["id"])},
    {"name": "research_get_experiment", "group": "read",
     "description": "One experiment (EXP-…) with metrics, conclusion, evidence, failures and provenance (git commit, dataset "
                    "version, environment, ClearML task, run, artifacts).",
     "inputSchema": _obj({"id": {"type": "string", "pattern": r"^EXP-\d{3,6}$"}}, ["id"])},
    {"name": "research_get_evidence", "group": "read",
     "description": "Evidence and claims: by claim id, by experiment id, or the evidence most relevant to a question.",
     "inputSchema": _obj({"query": Q, "claim_id": {"type": "string", "pattern": r"^CLM-\d{3,6}$"},
                          "experiment_id": {"type": "string", "pattern": r"^EXP-\d{3,6}$"},
                          "status": {"type": "string", "enum": ["candidate", "validated", "rejected"]}})},
    {"name": "research_get_decisions", "group": "read",
     "description": "Research decisions (chosen / rejected directions, constraints) with the evidence they rely on.",
     "inputSchema": _obj({"include_superseded": {"type": "boolean"}})},
    {"name": "research_get_failures", "group": "read",
     "description": "Failure memory: what failed, cause, lesson and avoidance rule — check before planning an experiment.",
     "inputSchema": _obj({"query": Q, "model": {"type": "string", "maxLength": 80}, "dataset": {"type": "string", "maxLength": 80}})},
    {"name": "research_get_context", "group": "read",
     "description": "The compiled, budgeted research context for a question and a role (what PhD-Lab itself injects).",
     "inputSchema": _obj({"query": Q, "role": ROLE, "budget_tokens": {"type": "integer", "minimum": 400, "maximum": 20000},
                          "trace": {"type": "boolean"}}, ["query"])},
    {"name": "research_get_provenance", "group": "read",
     "description": "Where a record came from: experiments, commits, dataset versions, runs, artifacts, and the decisions "
                    "that rely on it.",
     "inputSchema": _obj({"id": {"type": "string", "pattern": r"^(HYPE|EXP|FAIL|CLM|EVID)-\d{3,6}$|^D[0-9a-f]{6}$"}}, ["id"])},
    {"name": "research_record_observation", "group": "write",
     "description": "Propose an observation to the researcher's memory. It becomes a REVIEW CANDIDATE, not memory.",
     "inputSchema": _obj({"text": {"type": "string", "minLength": 3, "maxLength": 4000}, "experiment_id": {"type": "string", "pattern": r"^EXP-\d{3,6}$"},
                          "claim_id": {"type": "string", "pattern": r"^CLM-\d{3,6}$"},
                          "stance": {"type": "string", "enum": ["supports", "refutes", "neutral"]}, "metric": METRIC}, ["text"])},
    {"name": "research_record_decision", "group": "write",
     "description": "Propose a research decision. It becomes a REVIEW CANDIDATE; the researcher approves it.",
     "inputSchema": _obj({"text": {"type": "string", "minLength": 3, "maxLength": 4000},
                          "kind": {"type": "string", "enum": ["direction", "hypothesis", "gap", "constraint", "rejected", "other"]},
                          "evidence_ids": {"type": "array", "items": ID, "maxItems": 20},
                          "supersedes": {"type": "string", "pattern": r"^D[0-9a-f]{6}$"}}, ["text"])},
    {"name": "research_record_experiment_result", "group": "write",
     "description": "Propose the result of an experiment (observation, metric, verdict). Becomes a REVIEW CANDIDATE.",
     "inputSchema": _obj({"experiment_id": {"type": "string", "pattern": r"^EXP-\d{3,6}$"}, "text": {"type": "string", "minLength": 3, "maxLength": 4000},
                          "metric": METRIC, "verdict": {"type": "string", "enum": ["supports", "refutes", "inconclusive"]},
                          "conclusion": {"type": "string", "maxLength": 2000}}, ["experiment_id", "text"])},
]
BY_NAME = {t["name"]: t for t in TOOLS}


class ToolInputError(ValueError):
    pass


def validate(schema: dict, value, path: str = "arguments") -> None:
    """Strict subset of JSON Schema used by the tool schemas above (type, required, additionalProperties, enum, pattern,
    lengths, ranges, items)."""
    t = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "number": (int, float), "integer": int}
    if t and (not isinstance(value, types[t]) or (t in ("number", "integer") and isinstance(value, bool))):
        raise ToolInputError(f"{path} must be {t}")
    if t == "object":
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                raise ToolInputError(f"{path}.{k} is required")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(props)
            if extra:
                raise ToolInputError(f"{path}: unknown field(s) {', '.join(sorted(extra))}")
        for k, v in value.items():
            validate(props[k], v, f"{path}.{k}")
    elif t == "array":
        if len(value) > schema.get("maxItems", 10 ** 6):
            raise ToolInputError(f"{path}: too many items")
        for i, v in enumerate(value):
            validate(schema.get("items", {}), v, f"{path}[{i}]")
    elif t == "string":
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 10 ** 6):
            raise ToolInputError(f"{path}: length out of range")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ToolInputError(f"{path}: invalid format")
    elif t in ("number", "integer"):
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            raise ToolInputError(f"{path}: out of range")
    if "enum" in schema and value not in schema["enum"]:
        raise ToolInputError(f"{path} must be one of {', '.join(map(str, schema['enum']))}")


def listed(mcfg: dict) -> list:
    if not mcfg.get("expose_research", True):
        return []
    return [{k: v for k, v in t.items() if k != "group"} for t in TOOLS if t["group"] == "read" or mcfg.get("allow_writes", True)]


# ------------------------------------------------------------------ implementation
def _policy():
    from ..config import load_config
    from ..memory.engine import index
    from .policy import allowed_classes
    cfg = load_config()
    allowed = allowed_classes(cfg)
    idx, _ = index()
    blocked = {n.id for n in idx.nodes if n.classification not in allowed}
    return cfg, allowed, blocked


def _ok(ids: set, blocked: set) -> bool:
    return not (ids & blocked)


def _clean(obj, cfg):
    """Sanitise every string leaving through MCP (credentials; source code under block_source_code)."""
    from .policy import sanitize
    if isinstance(obj, str):
        return sanitize(obj, cfg)[0]
    if isinstance(obj, list):
        return [_clean(x, cfg) for x in obj]
    if isinstance(obj, dict):
        return {k: _clean(v, cfg) for k, v in obj.items()}
    return obj


def call(name: str, args: dict, client: dict | None = None) -> dict:
    name = name.replace(".", "_") if name and name.startswith("research.") else name
    if name not in BY_NAME:
        raise KeyError(name)
    from ..config import load_config
    mcfg = load_config()["mcp"]
    tool = BY_NAME[name]
    if not mcfg.get("expose_research", True) or (tool["group"] == "write" and not mcfg.get("allow_writes", True)):
        raise PermissionError(f"{name} is disabled in the MCP settings")
    args = args or {}
    validate(tool["inputSchema"], args)
    cfg, allowed, blocked = _policy()
    data, ids = globals()["_" + name](args, blocked, client or {})
    from ..memory import cache
    data = _clean(data, cfg)
    prov = {"source": "phd-research-lab", "project_id": _project(), "context_version": cache.version(),
            "record_ids": sorted(ids)[:200], "sensitivity_allowed": list(allowed), "retrieved_at": round(time.time(), 3)}
    out = {"result": data, "provenance": prov}
    return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, indent=1)[:60000]}], "structuredContent": out}


def _project() -> str:
    from ..config import data_dir
    return data_dir().name


def _research_get_current_state(a, blocked, client):
    from ..memory.state import current, ids
    st = current(blocked)
    return st, ids(st)


def _hits(res, blocked):
    from ..memory.engine import index
    idx, _ = index()
    out = []
    for h in res["hits"]:
        n = idx.by_id.get(h["id"])
        if not n or h["id"] in blocked:
            continue
        out.append({"id": h["id"], "type": h["type"], "score": h["score"], "summary": n.tagline, "detail": n.short,
                    "status": n.status, "refs": {k: v for k, v in n.refs.items() if v}, "why": h["reasons"]})
    return out


def _research_search_memory(a, blocked, client):
    from ..memory import engine
    from .policy import allowed_classes
    ctx = engine.build_context(a["query"], role=a.get("role", ""), filters=a.get("filters"), purged=blocked,
                               allowed=allowed_classes(), k=int(a.get("k") or 12))
    hits = _hits(engine.retrieve(ctx), blocked)
    return {"hits": hits, "query": a["query"], "role": ctx.role}, {h["id"] for h in hits}


def _research_get_hypothesis(a, blocked, client):
    from ..memory import evidence, research
    if a["id"] in blocked:
        raise LookupError(f"{a['id']} not found")
    rs = research.load()
    h = next((x for x in rs["hypotheses"] if x["id"] == a["id"]), None)
    if not h:
        raise LookupError(f"{a['id']} not found")
    exps = [e for e in rs["experiments"] if e.get("hypothesis_id") == h["id"] and e["id"] not in blocked]
    fails = [f for f in rs["failures"] if f.get("hypothesis_id") == h["id"] and f["id"] not in blocked]
    claims = [c for c in evidence.load()["claims"] if c.get("hypothesis_id") == h["id"] and c["id"] not in blocked]
    return ({"hypothesis": h, "experiments": exps, "failures": fails, "claims": claims},
            {h["id"]} | {x["id"] for x in exps + fails + claims})


def _research_get_experiment(a, blocked, client):
    from ..memory import evidence, research, trace
    if a["id"] in blocked:
        raise LookupError(f"{a['id']} not found")
    rs = research.load()
    e = next((x for x in rs["experiments"] if x["id"] == a["id"]), None)
    if not e:
        raise LookupError(f"{a['id']} not found")
    ev = [x for x in evidence.for_experiment(e["id"]) if x["id"] not in blocked]
    fails = [f for f in rs["failures"] if f.get("experiment_id") == e["id"] and f["id"] not in blocked]
    prov = trace.chain(e["id"], depth=2)["answers"]
    return {"experiment": e, "evidence": ev, "failures": fails, "provenance": prov}, {e["id"]} | {x["id"] for x in ev + fails}


def _research_get_evidence(a, blocked, client):
    from ..memory import evidence, engine
    from .policy import allowed_classes
    es = evidence.load()
    if a.get("claim_id"):
        c = evidence.get(a["claim_id"])
        items = c["evidence"]
        claims = [c] if c["id"] not in blocked else []
    elif a.get("experiment_id"):
        items, claims = evidence.for_experiment(a["experiment_id"]), []
    elif a.get("query"):
        ctx = engine.build_context(a["query"], filters={"tiers": ["evidence"]}, purged=blocked, allowed=allowed_classes(), k=15)
        ids = [h["id"] for h in engine.retrieve(ctx)["hits"]]
        items = [x for x in es["evidence"] if x["id"] in ids]
        claims = [x for x in es["claims"] if x["id"] in ids]
    else:
        raise ToolInputError("give query, claim_id or experiment_id")
    if a.get("status"):
        items = [x for x in items if x["status"] == a["status"]]
    items = [x for x in items if x["id"] not in blocked]
    claims = [{k: v for k, v in c.items() if k != "evidence"} for c in claims]
    return {"evidence": items, "claims": claims}, {x["id"] for x in items + claims}


def _research_get_decisions(a, blocked, client):
    from ..memory import load
    ds = [d for d in load()["decisions"] if d["id"] not in blocked and (a.get("include_superseded") or not d.get("superseded_by"))]
    return {"decisions": ds}, {d["id"] for d in ds}


def _research_get_failures(a, blocked, client):
    from ..memory import engine, research
    from .policy import allowed_classes
    fs = [f for f in research.load()["failures"] if f["id"] not in blocked]
    for k in ("model", "dataset"):
        if a.get(k):
            fs = [f for f in fs if a[k].lower() in (f.get(k) or "").lower() or a[k].lower() in f["text"].lower()]
    if a.get("query"):
        ctx = engine.build_context(a["query"], filters={"types": ["failure"]}, purged=blocked, allowed=allowed_classes(), k=20)
        order = [h["id"] for h in engine.retrieve(ctx)["hits"]]
        fs = sorted([f for f in fs if f["id"] in order], key=lambda f: order.index(f["id"]))
    return {"failures": fs[:30]}, {f["id"] for f in fs[:30]}


def _research_get_context(a, blocked, client):
    from ..memory.compiler import compile_context, trace_text
    from .policy import allowed_classes
    c = compile_context("mcp", "", a["query"], int(a.get("budget_tokens") or 4000), blocked, None, role=a.get("role", ""),
                        allowed=allowed_classes())
    out = {"context": c["text"], "tokens": c["tokens"], "role": c["role"], "context_version": c["context_version"]}
    if a.get("trace"):
        out["trace"] = trace_text(c)
    return out, set(c["used"])


def _research_get_provenance(a, blocked, client):
    from ..memory import trace
    if a["id"] in blocked:
        raise LookupError(f"{a['id']} not found")
    ch = trace.chain(a["id"])
    ch["nodes"] = [n for n in ch["nodes"] if n["id"] not in blocked]
    ch["edges"] = [e for e in ch["edges"] if e["from"] not in blocked and e["to"] not in blocked]
    return ch, {n["id"] for n in ch["nodes"]}


def _origin(client: dict) -> dict:
    return {"origin": "provider", "provider": re.sub(r"[^\w.-]", "", str(client.get("name") or "mcp-client"))[:40],
            "session": str(client.get("session") or "")[:80], "request_id": str(client.get("request_id") or "")[:40]}


def _research_record_observation(a, blocked, client):
    from ..memory import lifecycle
    c = lifecycle.propose("observation", dict(a), **_origin(client))
    return {"candidate": c, "note": "Recorded as a review candidate; it becomes memory only when the researcher approves it."}, {c["id"]}


def _research_record_decision(a, blocked, client):
    from ..memory import lifecycle
    p = {k: v for k, v in a.items() if k != "kind"}
    if a.get("kind"):
        p["decision_kind"] = a["kind"]
    c = lifecycle.propose("decision", p, **_origin(client))
    return {"candidate": c, "note": "Recorded as a review candidate; it becomes a decision only when the researcher approves it."}, {c["id"]}


def _research_record_experiment_result(a, blocked, client):
    from ..memory import lifecycle, research
    if not any(e["id"] == a["experiment_id"] for e in research.load()["experiments"]) or a["experiment_id"] in blocked:
        raise LookupError(f"{a['experiment_id']} not found")
    c = lifecycle.propose("experiment_result", dict(a), **_origin(client))
    return {"candidate": c, "note": "Recorded as a review candidate; the experiment is updated only after approval."}, {c["id"]}
