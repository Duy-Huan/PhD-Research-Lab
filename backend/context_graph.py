"""Context knowledge graph & Context Decision Agent (v3.0).

The graph is DERIVED from the project's live state (memory tiers, locked decisions, library, runs/metrics, pinned
notes, code files) plus an OVERLAY the researcher controls (memory/context_graph.json):
    📌 pinned  → injected into EVERY agent as must-follow context
    🗑 purged  → excluded from what the agents see (the source data itself is not deleted)
    custom nodes (assumptions, constraints, ideas) and extra edges
The Context Decision Agent turns natural-language commands into graph operations that the researcher approves.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone

from . import memory as M

_lock = threading.Lock()
TYPES = {"project": "Project", "objective": "Objective", "hypothesis": "Hypothesis", "decision": "Decision",
         "literature": "Literature", "assumption": "Code assumption", "code": "Code", "metric": "Metric", "run": "Run",
         "episode": "Episode", "note": "Pinned note", "constraint": "Constraint", "idea": "Idea", "result": "Result",
         "experiment": "Experiment", "failure": "Validated failure"}
HUB_LABELS = {"objective": "Objectives", "hypothesis": "Hypotheses", "decision": "Decisions", "literature": "Literature",
              "assumption": "Code assumptions", "code": "Code files", "metric": "Metrics", "run": "Runs", "episode": "Episodes",
              "note": "Pinned notes", "constraint": "Constraints", "idea": "Ideas", "result": "Results",
              "experiment": "Experiments", "failure": "Failures"}
RESEARCH_ID = re.compile(r"^(HYPE|EXP|FAIL)-\d{3,6}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _overlay_path():
    return M.mem_dir() / "context_graph.json"


def load_overlay() -> dict:
    d = {"nodes": {}, "custom": [], "edges": []}
    f = _overlay_path()
    if f.exists():
        try:
            d.update(json.loads(f.read_text("utf-8")))
        except Exception:
            pass
    return d


def save_overlay(ov: dict):
    with _lock:
        f = _overlay_path()
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(ov, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, f)


def purged_ids(ov: dict | None = None) -> set:
    ov = ov or load_overlay()
    return {k for k, v in ov["nodes"].items() if v.get("purged")}


def purged_lit_keys() -> set:
    return {k.split(":", 1)[1] for k in purged_ids() if k.startswith("lit:")}


def _short(t: str, n: int = 60) -> str:
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def build(include_purged: bool = True) -> dict:
    """Nodes + edges for vis-network. Each node: id, type, label, text, pinned, purged, editable, source."""
    ov = load_overlay()
    st = M.load()
    nodes, edges = [], []

    def add(nid, typ, label, text="", source="", editable=False, default_pinned=False, deletable=False, extra=None):
        o = ov["nodes"].get(nid, {})
        n = {"id": nid, "type": typ, "label": o.get("label") or label, "text": o.get("text") or text, "source": source,
             "pinned": o.get("pinned", default_pinned), "purged": bool(o.get("purged")), "editable": editable, "deletable": deletable,
             "edited": bool(o.get("label") or o.get("text"))}
        if extra:
            n.update(extra)
        nodes.append(n)
        return n

    add("project", "project", "Research project", source="project")
    hubs = {}
    for typ in ("objective", "hypothesis", "decision", "literature", "assumption", "metric", "episode", "note", "code", "result"):
        hubs[typ] = f"hub:{typ}"
    used_types = set()

    t3 = st["tier3"]
    try:
        from .memory import research as RM
        rs = RM.load()
    except Exception:
        rs = {"hypotheses": [], "experiments": [], "failures": []}
    norm = lambda t: re.sub(r"[^\w]+", " ", re.sub(r"^\s*H\d+\s*[:.)-]\s*", "", t or "").lower()).strip()  # noqa: E731
    hype_by_text = {norm(h["text"]): h for h in rs["hypotheses"]}
    alias = {}  # HYPE id → graph node id (plan hypotheses keep their hyp:i node, labelled with the HYPE id)
    for i, g in enumerate(t3.get("goals") or []):
        add(f"goal:{i}", "objective", _short(g), g, "Tier 3 · goals", editable=True); used_types.add("objective")
    for i, h in enumerate(t3.get("hypotheses") or []):
        hy = hype_by_text.get(norm(h))
        if hy:
            alias[hy["id"]] = f"hyp:{i}"
        add(f"hyp:{i}", "hypothesis", (f"{hy['id']} · " if hy else "") + _short(h), h,
            "Tier 3 · hypotheses" + (f" · {hy['id']} ({hy['status']})" if hy else ""), editable=True,
            extra={"hype": hy["id"], "status": hy["status"]} if hy else None)
        used_types.add("hypothesis")
    for h in rs["hypotheses"]:
        if h["id"] not in alias:
            add(h["id"], "hypothesis", f"{h['id']} · {_short(h['text'], 48)}", h["text"], f"Research memory · {h['status']}",
                editable=True, deletable=True, extra={"hype": h["id"], "status": h["status"]})
            alias[h["id"]] = h["id"]
            used_types.add("hypothesis")
    run_nodes = set()
    for e in rs["experiments"]:
        add(e["id"], "experiment", f"{e['id']} · {_short(e['title'], 44)}",
            "\n".join(f"{k}: {e[k]}" for k in ("observation", "interpretation", "decision", "conclusion", "next_action") if e.get(k)),
            f"Research memory · {e.get('verdict') or 'open'}", deletable=True,
            extra={k: e.get(k) for k in ("run_id", "clearml_task_id", "clearml_url", "git_sha", "hypothesis_id", "verdict")})
        used_types.add("experiment")
        if e.get("run_id"):
            run_nodes.add(e["run_id"])
    for f in rs["failures"]:
        add(f["id"], "failure", f"{f['id']} · {_short(f['text'], 44)}", f"{f['text']}\n{f.get('reason', '')}", "Research memory · failure",
            deletable=True)
        used_types.add("failure")
        if f.get("run_id"):
            run_nodes.add(f["run_id"])
    for rid in sorted(run_nodes):
        add(f"run:{rid}", "run", f"run {rid[-11:]}", rid, "Sandbox run")
        used_types.add("run")
    for i, c in enumerate(t3.get("constraints") or []):
        add(f"con:{i}", "constraint", _short(c), c, "Tier 3 · constraints", editable=True); used_types.add("constraint")
    for d in st["decisions"]:
        add(d["id"], "decision", ("🔒 " if d.get("locked") else "") + _short(d["text"]), d["text"], f"Decision · {d['kind']}",
            editable=True, default_pinned=bool(d.get("locked")), deletable=True, extra={"kind": d["kind"], "locked": d.get("locked")})
        used_types.add("decision")
    try:
        from .library import included
        for e in included()[:60]:
            add(f"lit:{e['key']}", "literature", f"{e['key']}", f"{e.get('title', '')} ({e.get('year', '')})\n{(e.get('abstract') or '')[:600]}",
                "Reference library", extra={"title": e.get("title", "")})
            used_types.add("literature")
    except Exception:
        pass
    for k, v in (t3.get("best_metrics") or {}).items():
        add(f"metric:{k}", "metric", f"{k} = {v['value']:.4g}", f"Best {k} = {v['value']} ({v['direction']}) in run {v['run']}", "Runs · best metrics",
            extra={"run": v["run"]})
        used_types.add("metric")
    try:
        from .results import load as load_results
        for it in load_results()[:40]:
            add(f"result:{it['id']}", "result", _short(it["title"], 50),
                ((it.get("notes") or "") + ("\n" + it["findings"] if it.get("findings") else ""))[:1500] or it.get("file", ""),
                f"Result · {it['kind']}" + (f" · {it['file']}" if it.get("file") else ""), extra={"rid": it["id"], "kind": it["kind"]})
            used_types.add("result")
    except Exception:
        pass
    for e in st["tier2"][-25:]:
        add(e["id"], "episode", _short(e["title"], 50), e["summary"], f"Tier 2 · {e.get('source', '')}", editable=True, deletable=True)
        used_types.add("episode")
    try:
        from .context_hub import load_notes
        for n in load_notes()[-30:]:
            add(f"note:{n['id']}", "note", _short(n["text"], 50), n["text"], f"📌 note · {n.get('tool', '')}", deletable=True)
            used_types.add("note")
    except Exception:
        pass
    try:
        from .sandbox import code_dir
        pys = sorted([p for p in code_dir().rglob("*.py") if ".trash" not in p.parts and "__pycache__" not in p.parts],
                     key=lambda p: -p.stat().st_mtime)[:15]
        for p in pys:
            relp = str(p.relative_to(code_dir())).replace("\\", "/")
            doc = re.match(r'\s*(?:#.*\n)*\s*(?:"""|\'\'\')(.+?)(?:"""|\'\'\')', p.read_text("utf-8", errors="replace")[:3000], re.S)
            add(f"code:{relp}", "code", relp, (doc.group(1).strip() if doc else "")[:500], "code workspace")
            used_types.add("code")
    except Exception:
        pass
    for c in ov["custom"]:
        add(c["id"], c["type"], _short(c["label"], 60), c.get("text", ""), "custom", editable=True,
            default_pinned=c.get("pinned", False), deletable=True)
        used_types.add(c["type"] if c["type"] in hubs else "assumption")

    # structure: project → type hubs → items
    for typ in sorted(used_types):
        hid = f"hub:{typ}"
        nodes.append({"id": hid, "type": "hub", "label": HUB_LABELS.get(typ, TYPES.get(typ, typ)),
                      "text": "", "pinned": False, "purged": False, "editable": False, "deletable": False, "hub_for": typ})
        edges.append({"from": "project", "to": hid})
    hub_of = {"constraint": "constraint", "idea": "assumption"}
    for n in nodes:
        if n["type"] in ("project", "hub"):
            continue
        h = f"hub:{hub_of.get(n['type'], n['type'])}"
        if any(x["id"] == h for x in nodes):
            edges.append({"from": h, "to": n["id"]})
    ids = {n["id"] for n in nodes}
    # v3.2 research links: experiment → hypothesis / run, failure → hypothesis / run, episode → entities it mentions
    def link(a, b, label):
        b = alias.get(b, b)
        if a in ids and b in ids and a != b:
            edges.append({"from": a, "to": b, "label": label, "research": True})
    for e in rs["experiments"]:
        if e.get("hypothesis_id"):
            link(e["id"], e["hypothesis_id"], e.get("verdict") or "tests")
        if e.get("run_id"):
            link(e["id"], f"run:{e['run_id']}", "run")
    for f in rs["failures"]:
        if f.get("hypothesis_id"):
            link(f["id"], f["hypothesis_id"], "refutes")
        if f.get("run_id"):
            link(f["id"], f"run:{f['run_id']}", "run")
    for ep in st["tier2"][-25:]:
        for l in ep.get("links") or []:
            link(ep["id"], l, "mentions")
    for a, b, *lab in ov["edges"]:
        if a in ids and b in ids:
            edges.append({"from": a, "to": b, "label": lab[0] if lab else "", "custom": True})
    if not include_purged:
        keep = {n["id"] for n in nodes if not n["purged"]}
        nodes = [n for n in nodes if n["id"] in keep]
        edges = [e for e in edges if e["from"] in keep and e["to"] in keep]
    stats = {"nodes": len([n for n in nodes if n["type"] not in ("hub", "project")]), "pinned": sum(1 for n in nodes if n["pinned"]),
             "purged": sum(1 for n in nodes if n["purged"])}
    return {"nodes": nodes, "edges": edges, "stats": stats}


def pinned_block() -> str:
    """MUST-FOLLOW context for every agent: pinned (not purged) nodes."""
    g = build()
    items = [n for n in g["nodes"] if n["pinned"] and not n["purged"] and n["type"] not in ("hub", "project")]
    if not items:
        return ""
    kind_lab = {"direction": "CHOSEN DIRECTION", "hypothesis": "HYPOTHESIS", "gap": "TARGET GAP", "constraint": "CONSTRAINT",
                "rejected": "REJECTED — do not propose again", "other": "DECISION"}

    def lab(n):
        return kind_lab.get(n.get("kind"), "DECISION") if n["type"] == "decision" else TYPES.get(n["type"], n["type"])
    return "\n".join(f"- [{lab(n)}] {(n['text'] or n['label'])[:800]}" for n in items)


# ------------------------------------------------------------------ operations
def apply_ops(ops: list) -> dict:
    ov = load_overlay()
    done, errors = [], []
    for op in ops or []:
        try:
            kind, nid = op.get("op"), op.get("id", "")
            if kind in ("pin", "unpin", "purge", "restore"):
                o = ov["nodes"].setdefault(nid, {})
                if kind in ("pin", "unpin"):
                    o["pinned"] = kind == "pin"
                    if nid.startswith("D"):  # decisions: pin == locked
                        M.edit_decision(nid, {"locked": kind == "pin"})
                else:
                    o["purged"] = kind == "purge"
                    if kind == "purge":
                        o["pinned"] = False
            elif kind == "edit":
                if nid.startswith("goal:") or nid.startswith("hyp:") or nid.startswith("con:"):
                    key = {"goal": "goals", "hyp": "hypotheses", "con": "constraints"}[nid.split(":")[0]]
                    idx = int(nid.split(":")[1])
                    vals = list(M.load()["tier3"].get(key) or [])
                    if idx < len(vals):
                        vals[idx] = op.get("text") or op.get("label") or vals[idx]
                        M.set_tier3({key: vals})
                elif nid.startswith("D"):
                    M.edit_decision(nid, {"text": op.get("text") or op.get("label")})
                elif RESEARCH_ID.match(nid):
                    from .memory import research as RM
                    if nid.startswith("HYPE"):
                        RM.update_hypothesis(nid, {"text": op.get("text") or op.get("label")})
                    elif nid.startswith("EXP") and op.get("label"):
                        RM.update_experiment(nid, {"title": op["label"]})
                elif nid.startswith("E"):
                    patch = {}
                    if op.get("text"):
                        patch["summary"] = op["text"]
                    if op.get("label"):
                        patch["title"] = op["label"]
                    M.edit_episode(nid, patch)
                elif any(c["id"] == nid for c in ov["custom"]):
                    for c in ov["custom"]:
                        if c["id"] == nid:
                            c["label"] = op.get("label", c["label"]); c["text"] = op.get("text", c.get("text", ""))
                else:
                    o = ov["nodes"].setdefault(nid, {})
                    if op.get("label"):
                        o["label"] = op["label"]
                    if op.get("text"):
                        o["text"] = op["text"]
            elif kind == "add":
                typ = op.get("type", "assumption")
                if typ == "decision":
                    d = M.add_decision(op.get("text") or op.get("label", ""), op.get("kind", "direction"), "context agent", op.get("pinned", True))
                    nid = d["id"]
                elif typ in ("objective", "hypothesis", "constraint"):
                    key = {"objective": "goals", "hypothesis": "hypotheses", "constraint": "constraints"}[typ]
                    vals = list(M.load()["tier3"].get(key) or []) + [op.get("text") or op.get("label", "")]
                    M.set_tier3({key: vals})
                    prefix = {"goals": "goal", "hypotheses": "hyp", "constraints": "con"}[key]
                    nid = f"{prefix}:{len(vals) - 1}"
                    if op.get("pinned"):
                        ov["nodes"].setdefault(nid, {})["pinned"] = True
                else:
                    nid = "N" + secrets.token_hex(3)
                    ov["custom"].append({"id": nid, "type": typ if typ in TYPES else "assumption", "label": op.get("label") or _short(op.get("text", ""), 60),
                                         "text": op.get("text", ""), "pinned": bool(op.get("pinned")), "created": _now()})
            elif kind == "link":
                ov["edges"].append([op["from"], op["to"], op.get("label", "")])
            elif kind == "delete":
                if RESEARCH_ID.match(nid):
                    from .memory import research as RM
                    RM.delete(nid)
                elif nid.startswith("D"):
                    M.delete_decision(nid)
                elif nid.startswith("E"):
                    M.delete_episode(nid)
                elif nid.startswith("note:"):
                    from .context_hub import delete_note
                    delete_note(nid.split(":", 1)[1])
                elif any(c["id"] == nid for c in ov["custom"]):
                    ov["custom"] = [c for c in ov["custom"] if c["id"] != nid]
                else:
                    raise ValueError("This node is derived from project data — purge it instead")
                ov["nodes"].pop(nid, None)
            else:
                raise ValueError(f"unknown op {kind}")
            done.append({**op, "id": nid})
        except Exception as e:
            errors.append(f"{op.get('op')} {op.get('id', '')}: {e}")
    save_overlay(ov)
    return {"applied": done, "errors": errors, "graph": build()}


AGENT_SYS = """You are the Context Decision Agent of a PhD research IDE. You manage the project's context knowledge graph:
what every AI agent (planning, coding, writing, reviewing) is allowed or required to take into account.
Node types: objective, hypothesis, decision, constraint, literature, assumption, code, metric, episode, note, idea.
📌 pinned = must-follow for every agent. 🗑 purged = hidden from all agents (data is kept).
Given the researcher's command and the current graph, decide the operations. Be conservative: never purge pinned or locked
items unless explicitly asked; prefer pinning a new constraint/decision that states the new focus.
Return ONLY a JSON object:
{"reply": "short explanation of what you propose and why (in the researcher's language)",
 "ops": [
   {"op": "pin"|"unpin"|"purge"|"restore", "id": "<node id>"},
   {"op": "edit", "id": "<node id>", "label": "...", "text": "..."},
   {"op": "add", "type": "decision"|"constraint"|"assumption"|"objective"|"hypothesis"|"idea", "label": "...", "text": "...", "kind": "direction|constraint|rejected|hypothesis|gap", "pinned": true},
   {"op": "link", "from": "<id>", "to": "<id>", "label": "..."},
   {"op": "delete", "id": "<custom/decision/episode/note id>"}
 ]}
Use only ids that exist in the graph (except for add)."""


def graph_digest(g: dict, max_nodes: int = 160) -> str:
    rows = []
    for n in g["nodes"]:
        if n["type"] in ("hub", "project"):
            continue
        flags = ("📌" if n["pinned"] else "") + ("🗑" if n["purged"] else "")
        rows.append(f"{n['id']} | {n['type']} | {flags} | {_short(n['label'], 70)} | {_short(n.get('text', ''), 160)}")
        if len(rows) >= max_nodes:
            break
    return "id | type | flags | label | text\n" + "\n".join(rows)


async def agent(message: str, history: list) -> dict:
    from .llm import call_agent, extract_json
    g = build()
    msgs = [{"role": m["role"], "content": m["content"]} for m in (history or [])[-8:] if m.get("role") in ("user", "assistant")]
    msgs.append({"role": "user", "content": f"CURRENT CONTEXT GRAPH:\n{graph_digest(g)}\n\nRESEARCHER COMMAND:\n{message}"})
    r = await call_agent("context_agent", AGENT_SYS, messages=msgs, max_tokens=1800, temperature=0.1)
    try:
        d = extract_json(r["text"])
    except Exception:
        d = {"reply": r["text"], "ops": []}
    ids = {n["id"] for n in g["nodes"]}
    ops = [o for o in (d.get("ops") or []) if isinstance(o, dict) and (o.get("op") in ("add", "link") or o.get("id") in ids)]
    return {"reply": str(d.get("reply") or ""), "ops": ops, "engine": r["engine"], "note": r.get("note", "")}


# chat history of the Context tab
def chat_path():
    return M.mem_dir() / "context_chat.json"


def load_chat() -> list:
    try:
        return json.loads(chat_path().read_text("utf-8"))
    except Exception:
        return []


def save_chat(msgs: list):
    chat_path().write_text(json.dumps(msgs[-200:], ensure_ascii=False, indent=1), "utf-8")
