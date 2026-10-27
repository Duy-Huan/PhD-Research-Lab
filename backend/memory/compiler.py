"""Context Compiler (CONTEXT_MEMORY.md §3.3; v3.3 §6-7, §18): retrieval results → one deterministic Markdown block.

    [CONTEXT SYSTEM INJECTION]
    ### RESEARCH STATE                                   objective, active hypothesis, current experiment, constraints,
                                                         locked decisions, known failures, best results (always first)
    ### CURRENT WORKING STATE
    ### RELATED EXPERIMENT EVIDENCE (ClearML Pointer)    research tier
    ### EVIDENCE & CLAIMS                                evidence tier (v3.3)
    ### FOUNDATIONAL SCIENTIFIC KNOWLEDGE
    ↳ Focus — …

Rules
- Role-aware: the section budgets and scoring weights come from the role's policy (policy.py); the role is given by the
  caller or derived from the tool (agent_block keeps its v3.2 signature).
- Explicit budget (policy.Budget): max / reserved / system / task tokens and a safety margin → memory budget → sections.
  The research state gets a floor before anything else; unused budget flows to the next section.
- Never blind truncation. Per section, in priority order (protected state records, then score):
      1. duplicates and near-duplicates are dropped (token Jaccard ≥ 0.8)            reason "duplicate of X"
      2. low-value hits are dropped (score < 35 % of the best hit, unprotected)      reason "low relevance"
      3. an item that does not fit is compressed LOD 6 → 5 → 4                       "compressed to LOD n"
      4. only then dropped                                                           reason "budget"
- Deterministic: same memory + query + role → same text (stable sorts; no timestamps of the call).
- Lost-in-the-middle: the research state opens the block, a one-line focus reminder closes it.
- Read-only: compiling never writes long-term memory (write isolation).
- Sensitivity (v3.4): with `allowed` set, records whose classification is not allowed never reach the text.
"""
from __future__ import annotations

from backend.memory import lod as LOD
from backend.memory import policy as P
from backend.memory.embeddings import tokenize

HEADER = "[CONTEXT SYSTEM INJECTION]"
SECTIONS = (("state", "RESEARCH STATE"),
            ("working", "CURRENT WORKING STATE"),
            ("research", "RELATED EXPERIMENT EVIDENCE (ClearML Pointer)"),
            ("evidence", "EVIDENCE & CLAIMS"),
            ("knowledge", "FOUNDATIONAL SCIENTIFIC KNOWLEDGE"))
SECTION_TIERS = tuple((t, k, 0.0) for k, t in SECTIONS if k in ("working", "research", "knowledge"))  # v3.2 name kept
DUP_JACCARD = 0.8
STATE_COMPLETE = ("decision", "hypothesis", "failure")  # their RESEARCH STATE line already carries the full record
                                                        # (failures: text + lesson); experiments add refs/observations
LOW_VALUE = 0.35


def _tok(s: str) -> int:
    return (len(s) + 3) // 4


def _clearml_ptr(n: LOD.MemoryNode) -> str:
    tid = n.refs.get("clearml_task")
    return f" → ClearML task `{tid}`" if tid else ""


def _render(n: LOD.MemoryNode, lvl: int) -> str:
    return "- " + LOD.render(n, lvl) + (_clearml_ptr(n) if n.tier in ("research", "evidence") and lvl >= 5 else "")


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def compile_context(tool: str = "", session_id: str = "", query: str = "", budget_tokens: int = 3500,
                    purged: set | None = None, cfg: dict | None = None, role: str = "", allowed=(), filters: dict | None = None,
                    budget: P.Budget | None = None, request_id: str = "") -> dict:
    from backend.core.config import data_dir, project_scope

    # Resolve once per compilation. Concurrent project selection cannot mix research
    # inputs, and each memory path need not reload global config/project metadata.
    with project_scope(data_dir()):
        return _compile_context(tool, session_id, query, budget_tokens, purged, cfg, role, allowed,
                                filters, budget, request_id)


def _compile_context(tool: str, session_id: str, query: str, budget_tokens: int,
                     purged: set | None, cfg: dict | None, role: str, allowed, filters: dict | None,
                     budget: P.Budget | None, request_id: str) -> dict:
    from backend.core.config import load_config
    from backend.core.telemetry import span
    from backend.memory import cache, working
    from backend.memory.engine import build_context, retrieve
    from backend.memory.state import current, lines as state_lines_of
    cfg = cfg or load_config()
    task = (working.get().get("current_task") or {}).get("text", "")
    q = (query or task or tool or "research project").strip()
    rname = P.resolve_role(role, tool)
    pol = P.POLICIES[rname]
    budget = budget or P.Budget(max_tokens=max(400, int(budget_tokens)))
    shares = budget.split(pol)
    with span("memory.compile", request_id=request_id or None, session_id=session_id or None, role=rname) as sp:
        ctx = build_context(q, role=rname, session_id=session_id, filters=filters, purged=purged, allowed=allowed, k=80)
        res = retrieve(ctx, cfg)
        idx_nodes = _nodes(ctx)
        blocked = set(res.get("blocked") or [])
        hidden = set(purged or ()) | blocked
        stt = current(hidden) if blocked else ctx.state
        by_id = {n.id: n for n in idx_nodes if n.id not in hidden}
        score = {h["id"]: h["score"] for h in res["hits"]}
        why = {h["id"]: h["reasons"] for h in res["hits"]}
        # "direct match": a top-3 keyword/vector hit is never dropped as low value, whatever the other sections score
        direct = {h["id"] for h in res["hits"] if any((h["ranks"].get(s) or 99) <= 3 for s in ("keyword", "vector"))}
        best_tier: dict = {}
        for h in res["hits"]:
            best_tier[h["tier"]] = max(best_tier.get(h["tier"], 0.0), h["score"])
        from backend.memory.state import ids as state_ids_of
        protected = state_ids_of(stt) & set(by_id)
        always = {n.id for n in by_id.values() if n.pinned or (session_id and n.type == "episode"
                                                                 and session_id in " ".join(n.links + [n.status]))}
        selected, dropped, seen_tok = [], [], []
        sec_out: dict = {}
        carry = 0
        for key in P.SECTION_ORDER:
            title = dict(SECTIONS)[key]
            b = shares.get(key, 0) + carry
            lines = [f"### {title}"]
            used = _tok(lines[0])
            if key == "state":
                for l in state_lines_of(stt):
                    if used + _tok(l) > b:
                        dropped.append({"id": "state-line", "reason": "budget", "section": key})
                        continue
                    lines.append(l)
                    used += _tok(l)
            elif key == "working":
                for l in working.state_lines(tool):
                    if used + _tok(l) > b:
                        break
                    lines.append(l)
                    used += _tok(l)
            if key != "state":
                tier = key
                cands = [i for i in dict.fromkeys([h["id"] for h in res["hits"]] + sorted(always))
                         if i in by_id and by_id[i].tier == tier]
                cands.sort(key=lambda i: (-(score.get(i, 0.0) + (1.0 if i in always else 0.0)), i))
                expanded = 0
                for i in cands:
                    n = by_id[i]
                    s = score.get(i, 0.0)
                    if i in protected and (i not in score or n.type in STATE_COMPLETE):
                        dropped.append({"id": i, "reason": "already in RESEARCH STATE", "score": s, "section": key})
                        continue
                    best = best_tier.get(tier, 0.0)  # low value is judged within the section, not against other tiers
                    if i not in always and best and s < LOW_VALUE * best and i not in protected and i not in direct:
                        dropped.append({"id": i, "reason": "low relevance", "score": s, "section": key})
                        continue
                    toks = set(tokenize(LOD.render(n, 5)))
                    dup = next((sid for sid, st_ in seen_tok if _jaccard(toks, st_) >= DUP_JACCARD), None)
                    if dup:
                        dropped.append({"id": i, "reason": f"duplicate of {dup}", "score": s, "section": key})
                        continue
                    lvl = 6 if expanded < 2 and n.commentary and s > 0 else 5
                    text = _render(n, lvl)
                    while used + _tok(text) > b and lvl > 4:
                        lvl -= 1
                        text = _render(n, lvl)
                    if used + _tok(text) > b:
                        dropped.append({"id": i, "reason": "budget", "score": s, "section": key})
                        continue
                    lines.append(text)
                    used += _tok(text)
                    seen_tok.append((i, toks))
                    full = _tok(_render(n, 6))
                    selected.append({"id": i, "section": key, "lod": lvl, "tokens": _tok(text), "full_tokens": full,
                                     "score": s, "protected": i in protected, "reasons": why.get(i, ["pinned / this session"])
                                     + ([f"compressed to LOD {lvl}"] if lvl < 5 else [])})
                    expanded += lvl == 6
            if len(lines) == 1:
                lines.append("- (nothing recorded yet)")
                used += 6
            carry = max(0, b - used)
            sec_out[key] = {"lines": lines, "tokens": used, "budget": b}
        out = [HEADER]
        for key, _ in SECTIONS:
            out.extend(sec_out[key]["lines"])
        hyp = (stt.get("active_hypotheses") or [None])[0]
        focus = []
        if task:
            focus.append("task: " + " ".join(task.split())[:160])
        if hyp:
            focus.append(f"hypothesis {hyp['id']}: {' '.join(hyp['text'].split())[:120]}")
        if focus:
            out.append("↳ Focus — " + " · ".join(focus))
        text = "\n".join(out)
        if blocked:  # a blocked record must not even be named through another record that mentions it
            import re
            rx = re.compile(r"(?<![\w:-])(" + "|".join(re.escape(b) for b in sorted(blocked, key=len, reverse=True)) + r")(?![\w-])")
            text = rx.sub("[withheld]", text)
        tokens = _tok(text)
        full = sum(x["full_tokens"] for x in selected) + sum(
            _tok(_render(by_id[d["id"]], 6)) for d in dropped if d["id"] in by_id)
        trace = {"task": q[:200], "role": rname, "policy": pol.label, "budget": budget.to_dict(),
                 "research_state": {"active_hypotheses": [h["id"] for h in stt["active_hypotheses"]],
                                    "current_experiment": (stt.get("current_experiment") or {}).get("id", ""),
                                    "context_version": stt.get("context_version", "")},
                 "selected": selected, "dropped": dropped, "blocked": sorted(blocked),
                 "sections": {k: {"tokens": v["tokens"], "budget": v["budget"], "items": len(v["lines"]) - 1} for k, v in sec_out.items()},
                 "total_tokens": tokens, "compression_ratio": round(full / max(1, sum(x["tokens"] for x in selected)), 2) if selected else 1.0,
                 "retrieval": res["diagnostics"]}
        sp.update(context_tokens=tokens, memory_tokens=tokens, selected_count=len(selected), dropped_count=len(dropped),
                  blocked_count=len(blocked), candidate_count=res["diagnostics"].get("candidates", 0),
                  cache_hit=bool(res["diagnostics"].get("cache_hit")), tokens_budget=budget.memory_budget,
                  context_version=stt.get("context_version", ""))
    return {"text": text, "tokens": tokens, "query": q, "role": rname, "used": [x["id"] for x in selected],
            "sections": {k: {"lines": len(v["lines"]) - 1, "tokens": v["tokens"], "budget": v["budget"]} for k, v in sec_out.items()},
            "skeleton": LOD.skeleton([n for n in idx_nodes if n.id not in hidden]), "trace": trace,
            "blocked": sorted(blocked), "context_version": cache.version(),
            "diagnostics": {**res["diagnostics"], "query_terms": len(tokenize(q))}}


def _nodes(ctx) -> list:
    from backend.memory.engine import index
    return index(ctx.purged)[0].nodes


def trace_text(c: dict) -> str:
    """The CONTEXT TRACE debug view (v3.3 §18) of one compile_context() result."""
    t = c["trace"]
    rs = t["research_state"]
    out = ["CONTEXT TRACE", "", "Task:", f"  {t['task']}", "", f"Role: {t['policy']} ({t['role']})", "",
           "Research state:", f"  hypotheses {', '.join(rs['active_hypotheses']) or '–'} · experiment {rs['current_experiment'] or '–'}"
           f" · version {rs['context_version']}", "", "Retrieved:"]
    for s in sorted(t["selected"], key=lambda x: -x["score"])[:20]:
        out.append(f"  {s['id']:<22} score {s['score']:.2f}  [{s['section']}, LOD {s['lod']}, {s['tokens']} tok]  {s['reasons'][0] if s['reasons'] else ''}")
    out += ["", "Dropped:"]
    for d in t["dropped"][:20]:
        out.append(f"  {d['id']:<22} {d['reason']}")
    if t["blocked"]:
        out += ["", "Blocked (sensitivity):", "  " + ", ".join(t["blocked"][:20])]
    out += ["", "Compiled:"]
    for k, v in t["sections"].items():
        out.append(f"  {k:<10} {v['tokens']:>6} / {v['budget']} tokens  ({v['items']} items)")
    out += ["", f"Total: {t['total_tokens']} tokens (memory budget {t['budget']['memory_budget']}) · compression ×{t['compression_ratio']}"]
    return "\n".join(out)
