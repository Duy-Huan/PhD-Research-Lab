"""Provenance chain (v3.3 §10): walk the typed research graph from any record and answer where a conclusion came from.

    Paper ─stated_in─ Claim ─informs─▶ Hypothesis ◀─tests─ Experiment ─executed_as─▶ Run ─▶ artifacts (sealed files)
                        ▲                                  │  └─ code: git commit · dataset version · environment · ClearML task
                        └──supports/refutes── Evidence ─produced_by─┘
    Decision ─informed_by─▶ Evidence / Experiment / Claim        Failure ─observed_in─▶ Experiment / Run / Hypothesis

chain(id)            nodes + typed edges reachable from the record (bounded depth), plus direct answers:
                     where_from (sources at the end of the chain), commits, datasets, environments, clearml tasks, runs,
                     artifacts, and the decisions that rely on anything in the chain.
decisions_based_on() reverse lookup: which decisions cite this record (directly or through evidence of an experiment).
Read-only; built from the stores on every call (no copy that could drift).
"""
from __future__ import annotations

import json
import re

RUN_RE = re.compile(r"^[\w-]{6,60}$")


def _load():
    from . import evidence, load, research
    from .knowledge import papers
    st, rs, es = load(), research.load(), evidence.load()
    recs: dict = {}
    for h in rs["hypotheses"]:
        recs[h["id"]] = ("hypothesis", h)
    for e in rs["experiments"]:
        recs[e["id"]] = ("experiment", e)
    for f in rs["failures"]:
        recs[f["id"]] = ("failure", f)
    for d in st["decisions"]:
        recs[d["id"]] = ("decision", d)
    for c in es["claims"]:
        recs[c["id"]] = ("claim", c)
    for v in es["evidence"]:
        recs[v["id"]] = ("evidence", v)
    for p in papers():
        if p["key"]:
            recs[f"lit:{p['key']}"] = ("paper", p)
    return recs, es


def _edges(rid: str, typ: str, r: dict, es: dict) -> list:
    """Outgoing typed edges of one record."""
    out = []
    if typ == "experiment":
        if r.get("hypothesis_id"):
            out.append((r["hypothesis_id"], "tests"))
        if r.get("run_id"):
            out.append((f"run:{r['run_id']}", "executed_as"))
        out += [(v["id"], "produced") for v in es["evidence"] if v.get("experiment_id") == rid]
    elif typ == "evidence":
        if r.get("claim_id"):
            out.append((r["claim_id"], r.get("stance") or "supports"))
        if r.get("experiment_id"):
            out.append((r["experiment_id"], "produced_by"))
        if r.get("paper_key"):
            out.append((f"lit:{r['paper_key']}", "from_source"))
        if r.get("run_id"):
            out.append((f"run:{r['run_id']}", "measured_in"))
    elif typ == "claim":
        if r.get("hypothesis_id"):
            out.append((r["hypothesis_id"], "informs"))
        out += [(s, "stated_in") for s in r.get("source_refs") or []]
        out += [(v["id"], "evidenced_by") for v in es["evidence"] if v.get("claim_id") == rid]
    elif typ == "decision":
        out += [(x, "informed_by") for x in r.get("evidence_ids") or []]
        if r.get("supersedes"):
            out.append((r["supersedes"], "supersedes"))
    elif typ == "failure":
        for k, rel in (("experiment_id", "observed_in"), ("hypothesis_id", "about")):
            if r.get(k):
                out.append((r[k], rel))
        if r.get("run_id"):
            out.append((f"run:{r['run_id']}", "observed_in"))
    return out


def _run_info(run_id: str) -> dict:
    if not RUN_RE.match(run_id or ""):
        return {}
    try:
        from ..sandbox import get_run, runs_dir
        r = get_run(run_id)
    except Exception:
        return {"id": run_id, "missing": True}
    git = r.get("git") or {}
    info = {"id": run_id, "status": r.get("status"), "git_sha": git.get("sha", ""), "git_dirty": bool(git.get("dirty")),
            "clearml_task_id": (r.get("clearml") or {}).get("task_id", ""), "environment": r.get("environment") or r.get("mode", ""),
            "metrics": {k: v for k, v in (r.get("metrics") or {}).items() if isinstance(v, (int, float))}}
    try:
        man = json.loads((runs_dir() / run_id / "provenance.json").read_text("utf-8"))
        info["artifacts"] = [{"file": f, "sha256": h} for f, h in sorted((man.get("files") or {}).items())]
    except (OSError, ValueError):
        info["artifacts"] = []
    return info


def decisions_based_on(item_id: str, recs: dict | None = None, es: dict | None = None) -> list:
    if recs is None:
        recs, es = _load()
    targets = {item_id}
    typ = recs.get(item_id, ("", {}))[0]
    if typ == "experiment":
        targets |= {v["id"] for v in es["evidence"] if v.get("experiment_id") == item_id}
    if typ == "claim":
        targets |= {v["id"] for v in es["evidence"] if v.get("claim_id") == item_id}
    return sorted(d["id"] for t, d in recs.values() if t == "decision" and targets & set(d.get("evidence_ids") or []))


def chain(item_id: str, depth: int = 4) -> dict:
    recs, es = _load()
    if item_id not in recs and not item_id.startswith("run:"):
        raise KeyError(f"{item_id} not found")
    nodes, edges, seen = {}, [], set()
    frontier = [item_id]
    for _ in range(depth + 1):
        nxt = []
        for nid in frontier:
            if nid in seen:
                continue
            seen.add(nid)
            if nid.startswith("run:"):
                info = _run_info(nid[4:])
                nodes[nid] = {"id": nid, "type": "run", **info}
                continue
            if nid not in recs:
                nodes[nid] = {"id": nid, "type": "unknown"}
                continue
            typ, r = recs[nid]
            label = r.get("text") or r.get("title") or r.get("name") or ""
            nodes[nid] = {"id": nid, "type": typ, "label": str(label)[:200], "status": r.get("status") or r.get("verdict", "")}
            for dst, rel in _edges(nid, typ, r, es):
                edges.append({"from": nid, "to": dst, "rel": rel})
                nxt.append(dst)
        frontier = nxt
    exps = [recs[n][1] for n in nodes if n in recs and recs[n][0] == "experiment"]
    evs = [recs[n][1] for n in nodes if n in recs and recs[n][0] == "evidence"]
    runs = [nodes[n] for n in nodes if n.startswith("run:")]

    def uniq(vals):
        return sorted({v for v in vals if v})
    answers = {
        "where_from": sorted(n for n, v in nodes.items() if v["type"] in ("paper", "experiment", "run")),
        "commits": uniq([e.get("git_sha") for e in exps] + [v.get("git_sha") for v in evs] + [r.get("git_sha") for r in runs]),
        "datasets": uniq([e.get("dataset_version") for e in exps] + [v.get("dataset_version") for v in evs]),
        "environments": uniq([e.get("environment") for e in exps] + [str(r.get("environment") or "") for r in runs]),
        "clearml_tasks": uniq([e.get("clearml_task_id") for e in exps] + [v.get("clearml_task_id") for v in evs]
                              + [r.get("clearml_task_id") for r in runs]),
        "runs": sorted(n for n in nodes if n.startswith("run:")),
        "artifacts": [a for r in runs for a in r.get("artifacts", [])],
        "metrics": [{"evidence": v["id"], **v["metric"]} for v in evs if v.get("metric")],
        "decisions": sorted(set().union(*[set(decisions_based_on(n, recs, es)) for n in nodes if n in recs]) if nodes else set()),
    }
    return {"root": item_id, "nodes": list(nodes.values()), "edges": edges, "answers": answers}
