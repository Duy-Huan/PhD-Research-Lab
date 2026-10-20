"""Memory tree with Levels Of Detail — adapted from TREEFRAG (Stingy Context, arXiv:2601.19929).

TREEFRAG turns flat material into a tree whose nodes carry metadata at 7 escalating levels of detail and serialises only
the low levels, so the "middle" of a prompt shrinks by an order of magnitude. The same idea for research memory:

    LOD 1 name        e.g. "HYPE-004"
    LOD 2 tier        working | research | knowledge         (category)
    LOD 3 type        hypothesis | experiment | episode | paper | …
    LOD 4 tag line    one line
    LOD 5 short       one or two sentences / key numbers
    LOD 6 commentary  the full memo (episode summary, interpretation, abstract)
    LOD 7 raw         page-store pages (never serialised unless explicitly expanded)

`collect()` builds every node from the live stores (nothing is copied); `skeleton()` prints the low-LOD tree that gives
an agent the whole map in a few hundred tokens; `render()` prints one node at a chosen LOD.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TIERS = ("working", "research", "evidence", "knowledge")
SENSITIVITY = ("PUBLIC", "INTERNAL", "SENSITIVE", "RESTRICTED")
# default classification by node type (v3.4 §11); the researcher overrides it per node (context-graph overlay)
DEFAULT_SENSITIVITY = {"paper": "PUBLIC", "concept": "PUBLIC"}


@dataclass
class MemoryNode:
    id: str
    tier: str
    type: str
    name: str
    tagline: str = ""
    short: str = ""
    commentary: str = ""
    pages: list = field(default_factory=list)
    links: list = field(default_factory=list)
    ts: str = ""
    pinned: bool = False
    status: str = ""
    refs: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)   # v3.3 filterable metadata: dataset, model, source_type, evidence_status, origin
    sensitivity: str = ""                      # v3.4: PUBLIC | INTERNAL | SENSITIVE | RESTRICTED ("" = type default)

    @property
    def classification(self) -> str:
        return self.sensitivity or DEFAULT_SENSITIVITY.get(self.type, "INTERNAL")

    def text(self) -> str:
        """Everything searchable about the node (LOD 1-6 + external reference ids)."""
        return " ".join([self.name, self.type, self.tagline, self.short, self.commentary, self.status,
                         " ".join(str(v) for v in self.refs.values() if v), " ".join(str(v) for v in self.meta.values() if v)])


def _one_line(t: str, n: int = 140) -> str:
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def render(n: MemoryNode, lod: int = 5) -> str:
    """One node as Markdown at the given level of detail (1-6; LOD 7 = pages are only referenced, never inlined)."""
    if lod <= 1:
        return n.name
    head = f"[{n.id}]" + (f" ({n.status})" if n.status else "") + f" {n.tagline or n.name}"
    if lod <= 4:
        return head
    out = head
    if n.short and _norm(n.short) not in _norm(n.tagline or n.name):  # never print the same sentence twice
        out += f" — {n.short}"
    refs = ", ".join(f"{k}={v}" for k, v in n.refs.items() if v)
    if refs:
        out += f" · {refs}"
    if lod >= 6 and n.commentary and _norm(n.commentary) not in _norm(f"{n.tagline} {n.short}"):
        out += "\n  " + n.commentary.strip().replace("\n", "\n  ")
    if n.pages:
        out += f" · raw pages: {', '.join(n.pages[:6])}"
    return out


def _norm(t: str) -> str:
    return re.sub(r"[^\w]+", " ", (t or "").lower()).strip()


def collect(purged: set | None = None) -> list:
    """All memory nodes of the active project (purged ones excluded)."""
    from . import load as load_legacy
    from . import knowledge, research
    purged = purged or set()
    st = load_legacy()
    rs = research.load()
    t3 = st["tier3"]
    nodes: list = []

    def add(n: MemoryNode):
        if n.id not in purged:
            nodes.append(n)

    # ---- research tier: hypotheses (stable HYPE ids), plan hypotheses without an id, decisions, experiments, failures
    purged_hyp_text = {_norm(h) for i, h in enumerate(t3.get("hypotheses") or []) if f"hyp:{i}" in purged}
    known = set()
    for h in rs["hypotheses"]:
        known.add(_norm(h["text"]))
        if _norm(h["text"]) in purged_hyp_text:
            continue
        add(MemoryNode(h["id"], "research", "hypothesis", h["id"], _one_line(h["text"]), h["text"][:400], ts=h["updated"],
                       status=h["status"], refs={"plan": h.get("plan_key", "")}))
    for i, h in enumerate(t3.get("hypotheses") or []):
        if _norm(re.sub(r"^\s*H\d+\s*[:.)-]\s*", "", h)) not in known and _norm(h) not in known:
            add(MemoryNode(f"hyp:{i}", "research", "hypothesis", f"hyp:{i}", _one_line(h), h[:400]))
    for d in st["decisions"]:
        add(MemoryNode(d["id"], "research", "decision", d["id"], _one_line(d["text"]), d["text"][:600], ts=d.get("created", ""),
                       pinned=bool(d.get("locked")),
                       status="superseded" if d.get("superseded_by") else ("locked " if d.get("locked") else "") + d.get("kind", ""),
                       links=list(d.get("evidence_ids") or []) + ([d["supersedes"]] if d.get("supersedes") else []),
                       meta={"origin": d.get("origin", "human"), "provider": d.get("provider", ""), "source_type": "decision"}))
    for e in rs["experiments"]:
        parts = [f"{k}: {e[k]}" for k in ("observation", "interpretation", "decision", "conclusion", "next_action") if e.get(k)]
        ms = ", ".join(f"{k}={v:.4g}" for k, v in list((e.get("metrics") or {}).items())[:8] if isinstance(v, (int, float)))
        add(MemoryNode(e["id"], "research", "experiment", e["id"], _one_line(e["title"]),
                       (f"metrics {ms}. " if ms else "") + _one_line(e.get("conclusion") or e.get("interpretation") or "", 300),
                       "\n".join(parts), ts=e["updated"], status=e.get("verdict") or "open",
                       links=[x for x in (e.get("hypothesis_id"), e.get("run_id") and f"run:{e['run_id']}") if x],
                       refs={"run": e.get("run_id", ""), "clearml_task": e.get("clearml_task_id", ""), "git": (e.get("git_sha") or "")[:10],
                             "dataset": e.get("dataset_version", ""), "env": (e.get("environment") or "")[:120]},
                       meta={"dataset": e.get("dataset_version", ""), "model": e.get("model_id", ""), "source_type": "experiment",
                             "environment": e.get("environment", "")}))
    for f in rs["failures"]:
        detail = [f"{k.replace('_', ' ')}: {f[k]}" for k in ("model", "dataset", "environment", "configuration", "error", "cause",
                                                             "observation", "lesson", "avoidance_rule") if f.get(k)]
        short = f.get("lesson") or f.get("avoidance_rule") or f.get("reason") or f.get("cause", "")
        add(MemoryNode(f["id"], "research", "failure", f["id"], _one_line(f["text"]), _one_line(short, 400),
                       "\n".join(detail), ts=f["created"], status="validated failure",
                       links=[x for x in (f.get("hypothesis_id"), f.get("experiment_id"), f.get("run_id") and f"run:{f['run_id']}") if x],
                       refs={"run": f.get("run_id", "")},
                       meta={"dataset": f.get("dataset", ""), "model": f.get("model", ""), "source_type": "failure",
                             "origin": f.get("origin", "")}))
    for k, v in (t3.get("best_metrics") or {}).items():
        add(MemoryNode(f"metric:{k}", "research", "metric", k, f"best {k} = {v['value']:.4g} ({v['direction']})",
                       f"measured in run {v['run']}", links=[f"run:{v['run']}"], refs={"run": v["run"]}))
    for i, c in enumerate(t3.get("constraints") or []):
        add(MemoryNode(f"con:{i}", "research", "constraint", f"con:{i}", _one_line(c), c[:400]))

    # ---- evidence tier (v3.3): claims and evidence with provenance pointers
    try:
        from . import evidence as EV
        es = EV.load()
        for c in es["claims"]:
            add(MemoryNode(c["id"], "evidence", "claim", c["id"], _one_line(c["text"]), c["text"][:600], ts=c["updated"],
                           status=c["status"], links=[x for x in [c.get("hypothesis_id")] + list(c.get("source_refs") or []) if x],
                           meta={"source_type": "claim", "origin": c.get("origin", "")}))
        for e in es["evidence"]:
            m = e.get("metric") or {}
            ms = f"{m['name']}={m['value']:.4g}{m.get('unit') or ''}" if m.get("name") and isinstance(m.get("value"), (int, float)) else ""
            tag = f"{e['stance']} {e.get('claim_id') or 'claim?'}" + (f" — {ms}" if ms else "") + \
                (f" ({e['experiment_id']})" if e.get("experiment_id") else "")
            add(MemoryNode(e["id"], "evidence", "evidence", e["id"], _one_line(tag), _one_line(e.get("text") or tag, 400), ts=e["updated"],
                           status=e["status"], links=[x for x in (e.get("claim_id"), e.get("experiment_id"),
                                                                  e.get("paper_key") and f"lit:{e['paper_key']}") if x],
                           refs={"git": (e.get("git_sha") or "")[:10], "clearml_task": e.get("clearml_task_id", ""),
                                 "run": e.get("run_id", ""), "dataset": e.get("dataset_version", "")},
                           meta={"source_type": e["source_type"], "evidence_status": e["status"],
                                 "dataset": e.get("dataset_version", ""), "origin": e.get("origin", "")}))
    except Exception:
        pass

    # ---- working tier: goals, episodic memory (compressed short-term memory), pinned notes
    for i, g in enumerate(t3.get("goals") or []):
        add(MemoryNode(f"goal:{i}", "working", "objective", f"goal:{i}", _one_line(g), g[:600]))
    for e in st["tier2"]:
        add(MemoryNode(e["id"], "working", "episode", e["id"], _one_line(e["title"]), _one_line(e.get("summary", ""), 300),
                       e.get("summary", ""), pages=list(e.get("pages") or []), links=list(e.get("links") or []),
                       ts=e.get("created", ""), pinned=bool(e.get("pinned")), status=e.get("source", "")))
    try:
        from ..context_hub import load_notes
        for n in load_notes()[-60:]:
            add(MemoryNode(f"note:{n['id']}", "working", "note", f"note:{n['id']}", _one_line(n["text"]), n["text"][:800], ts=n.get("ts", "")))
    except Exception:
        pass

    # ---- knowledge tier: papers (live from the library), concepts, methods
    for p in knowledge.papers():
        if not p["key"]:
            continue
        add(MemoryNode(f"lit:{p['key']}", "knowledge", "paper", p["key"], _one_line(f"{p['title']} ({p['year']})"),
                       _one_line(p["abstract"], 400), p["abstract"], refs={"bib": p["key"], "venue": p.get("venue", "")},
                       meta={"source_type": "paper"}))
    kn = knowledge.load()
    for c in kn["concepts"]:
        add(MemoryNode(c["id"], "knowledge", "concept", c["name"], _one_line(c["name"] + ": " + c["text"]), c["text"][:600],
                       links=[f"lit:{r}" for r in c.get("refs", [])], ts=c["created"]))
    for m in kn["methods"]:
        add(MemoryNode(m["id"], "knowledge", "method", m["name"], _one_line(m["name"] + ": " + m["text"]), m["text"][:600],
                       links=[f"lit:{r}" for r in m.get("refs", [])], ts=m["created"], refs={"code": m.get("code_ref", "")},
                       meta={"source_type": "method", "has_code": "yes" if m.get("code_ref") else ""}))

    # ---- researcher-controlled overlay of the context graph: pins, custom nodes, extra edges
    try:
        from ..context_graph import load_overlay
        ov = load_overlay()
        by_id = {n.id: n for n in nodes}
        for nid, o in ov["nodes"].items():
            if nid in by_id and o.get("pinned"):
                by_id[nid].pinned = True
            if nid in by_id and o.get("sensitivity") in SENSITIVITY:
                by_id[nid].sensitivity = o["sensitivity"]
        for c in ov["custom"]:
            add(MemoryNode(c["id"], "research", c.get("type", "assumption"), c["id"], _one_line(c.get("label", "")), c.get("text", "")[:600],
                           pinned=bool(c.get("pinned")), ts=c.get("created", "")))
        for a, b, *_ in ov["edges"]:
            if a in by_id:
                by_id[a].links.append(b)
    except Exception:
        pass
    return nodes


def skeleton(nodes: list, max_per_type: int = 6) -> str:
    """LOD-1/4 map of the whole memory: tier → type → most recent items (a few hundred tokens)."""
    lines = ["Project memory"]
    for tier in TIERS:
        tn = [n for n in nodes if n.tier == tier]
        if not tn:
            continue
        lines.append(f"├── {tier} ({len(tn)})")
        types = sorted({n.type for n in tn})
        for ti, typ in enumerate(types):
            items = sorted([n for n in tn if n.type == typ], key=lambda n: (n.ts or "", n.id), reverse=True)
            last = ti == len(types) - 1
            names = ", ".join(n.name for n in items[:max_per_type]) + (f", +{len(items) - max_per_type}" if len(items) > max_per_type else "")
            lines.append(f"│   {'└──' if last else '├──'} {typ} ({len(items)}): {names}")
    return "\n".join(lines)
