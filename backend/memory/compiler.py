"""Context Compiler (CONTEXT_MEMORY.md §3.3): retrieval results → one deterministic Markdown block per agent call.

    [CONTEXT SYSTEM INJECTION]
    ### CURRENT WORKING STATE
    ### RELATED EXPERIMENT EVIDENCE (ClearML Pointer)
    ### FOUNDATIONAL SCIENTIFIC KNOWLEDGE

Rules
- Deterministic: the same memory + query always gives the same text (stable sort by score, then id; no timestamps of
  the call itself), so prompts are reproducible and cache-friendly.
- Budgeted: a token budget split over the three sections (unused budget flows to the next section). Every node is
  serialised at LOD 5; the best hits of each section are expanded to LOD 6 while budget remains (TREEFRAG: low LOD for
  the map, high LOD only where it matters). Raw pages (LOD 7) are referenced by id, never inlined.
- Lost-in-the-middle: the current task opens the block and a one-line focus reminder closes it.
- Read-only: compiling never writes long-term memory (write isolation).
"""
from __future__ import annotations

from . import lod as LOD
from .embeddings import tokenize

HEADER = "[CONTEXT SYSTEM INJECTION]"
SECTION_TIERS = (("CURRENT WORKING STATE", "working", 0.35),
                 ("RELATED EXPERIMENT EVIDENCE (ClearML Pointer)", "research", 0.40),
                 ("FOUNDATIONAL SCIENTIFIC KNOWLEDGE", "knowledge", 0.25))


def _tok(s: str) -> int:
    return (len(s) + 3) // 4


def _clearml_ptr(n: LOD.MemoryNode) -> str:
    tid = n.refs.get("clearml_task")
    return f" → ClearML task `{tid}`" if tid else ""


def compile_context(tool: str = "", session_id: str = "", query: str = "", budget_tokens: int = 3500,
                    purged: set | None = None, cfg: dict | None = None) -> dict:
    from ..config import load_config
    from . import working
    from .retrieval import search
    cfg = cfg or load_config()
    nodes = LOD.collect(purged)
    by_id = {n.id: n for n in nodes}
    state = working.state_lines(tool)
    task = (working.get().get("current_task") or {}).get("text", "")
    q = (query or task or tool or "research project").strip()
    res = search(q, nodes, cfg, k=60)
    order = [h["id"] for h in res["hits"]]
    score = {h["id"]: h["score"] for h in res["hits"]}
    # nodes that matter regardless of the query: pinned, open hypotheses, this session's episodes
    always = sorted([n.id for n in nodes if n.pinned or (n.type == "hypothesis" and n.status in ("testing", "proposed"))
                     or (session_id and n.type == "episode" and session_id in " ".join(n.links + [n.status]))],
                    key=lambda i: (-score.get(i, 0.0), i))
    budget_total = max(400, int(budget_tokens))
    out = [HEADER]
    carry = 0
    used_ids: list = []
    sections = {}
    for title, tier, share in SECTION_TIERS:
        budget = int(budget_total * share) + carry
        lines = [f"### {title}"]
        used = _tok(lines[0])
        if tier == "working":
            for l in state:
                if used + _tok(l) > budget:
                    break
                lines.append(l)
                used += _tok(l)
        picks = [i for i in dict.fromkeys(always + order) if i in by_id and by_id[i].tier == tier]
        picks.sort(key=lambda i: (-(score.get(i, 0.0) + (1.0 if i in always else 0.0)), i))
        expanded = 0
        for i in picks:
            n = by_id[i]
            lvl = 6 if expanded < 2 and n.commentary and score.get(i, 0) > 0 else 5
            text = "- " + LOD.render(n, lvl) + (_clearml_ptr(n) if tier == "research" else "")
            if used + _tok(text) > budget and lvl == 6:
                lvl, text = 5, "- " + LOD.render(n, 5) + (_clearml_ptr(n) if tier == "research" else "")
            if used + _tok(text) > budget:
                continue
            lines.append(text)
            used += _tok(text)
            used_ids.append(i)
            expanded += lvl == 6
        if len(lines) == 1:
            lines.append("- (nothing recorded yet)")
            used += 6
        carry = max(0, budget - used)
        sections[tier] = {"lines": len(lines) - 1, "tokens": used, "budget": budget}
        out.extend(lines)
    hyp = next((by_id[i] for i in order if i in by_id and by_id[i].type == "hypothesis"), None) \
        or next((n for n in nodes if n.type == "hypothesis" and n.status == "testing"), None)
    focus = []
    if task:
        focus.append("task: " + " ".join(task.split())[:160])
    if hyp:
        focus.append(f"hypothesis {hyp.id}: {hyp.tagline[:120]}")
    if focus:
        out.append("↳ Focus — " + " · ".join(focus))
    text = "\n".join(out)
    return {"text": text, "tokens": _tok(text), "query": q, "used": used_ids, "sections": sections,
            "skeleton": LOD.skeleton(nodes), "diagnostics": {**res["diagnostics"], "query_terms": len(tokenize(q))}}


def agent_block(tool: str, sid: str = "", query: str = "", purged: set | None = None) -> str:
    """What every agent gets appended to its system prompt: the compiled context (v2 pipeline) or, if that is switched off
    or fails, the legacy Tier 3 + Tier 2 block. Also records the request as the current task (Working Memory)."""
    from ..config import load_config
    from . import memory_block
    cfg = load_config()
    if cfg["memory"].get("v2_pipeline", True):
        try:
            from .working import note_task
            if query:
                note_task(tool, query, sid)
            block = compile_context(tool, sid, query, cfg["memory"]["context_budget_tokens"], purged, cfg)["text"]
            return "\n\n# PROJECT MEMORY (compiled: working state, experiment evidence, scientific knowledge)\n" + block
        except Exception as e:
            print(f"[memory] compiler failed, using the legacy memory block: {type(e).__name__}: {e}")
    mem = memory_block(tool, sid, budget=7000, purged=purged)
    return "\n\n# PROJECT MEMORY (hierarchical: long-term facts + summaries of earlier work)\n" + mem if mem else ""
