"""v3.1 Writing briefs: what the researcher wants each section (and the whole paper) to say and which results to present.

project.json keeps:
    section_notes[sid]   free-text directions (same field as the v2.5 "Instructions for AI", so old projects keep working)
    section_briefs[sid]  structured part: must / avoid / outline / tone / length / cite / results
    paper_brief          paper-wide story, style and terminology, applied to every section

render() turns a brief into a binding block for the Author (3.2), the Editor (3.4) and the section Reviewer (3.3-S).
"""
from __future__ import annotations

import re

TONES = {
    "": "",
    "concise": "Concise and direct: short sentences, no filler, every sentence carries information.",
    "detailed": "Detailed and explanatory: develop each argument fully with motivation, mechanism and evidence.",
    "persuasive": "Persuasive: foreground novelty and significance, while every claim stays factual and supported.",
    "cautious": "Cautious: hedge claims precisely, state assumptions and limitations openly.",
    "tutorial": "Didactic: give the intuition before the formalism, guide the reader step by step.",
    "formal": "Strictly formal journal register (IEEE Transactions style).",
}
LENGTHS = {"": "", "short": "Noticeably shorter than a typical section of this kind (tight, about half).",
           "standard": "Typical length for this section at the target venue.",
           "long": "Longer and more thorough than usual — depth from substance, never padding."}
PRESENT_HELP = {
    "auto": "choose the clearest form (table, figure or prose)",
    "table": "present as a LaTeX table (booktabs) with exactly these values; if it already is a LaTeX table include it verbatim",
    "figure": "include it as a figure with the exact \\includegraphics line given below and reference it with \\ref",
    "text": "report the key numbers inline in the prose (no table/figure)",
    "comparison": "write a comparative analysis of this result against the other selected results / baselines",
    "highlight": "treat it as a headline result: state it prominently (and it may be quoted in the abstract/conclusion)",
}
DEFAULT_BRIEF = {"must": [], "avoid": [], "outline": [], "tone": "", "length": "", "words": 0, "cite": [], "results": [],
                 "results_only": True}
DEFAULT_PAPER_BRIEF = {"story": "", "style": "", "terms": "", "avoid": ""}


def _lst(v, n=40, m=600) -> list:
    return [str(x).strip()[:m] for x in (v or []) if str(x).strip()][:n] if isinstance(v, list) else []


def clean_brief(b: dict) -> dict:
    b = b or {}
    res = []
    for r in (b.get("results") or [])[:30]:
        if isinstance(r, dict) and re.fullmatch(r"(up:[a-f0-9]{10}|run:[\w-]{6,60}|runfig:[\w-]{6,60}/[^/\\]{1,120}|table:\d{1,3}|notes)", str(r.get("ref", ""))):
            res.append({"ref": r["ref"], "as": r.get("as") if r.get("as") in PRESENT_HELP else "auto",
                        "note": str(r.get("note") or "")[:1000], "title": str(r.get("title") or "")[:160]})
    words = b.get("words")
    return {"must": _lst(b.get("must")), "avoid": _lst(b.get("avoid")), "outline": _lst(b.get("outline")),
            "tone": b.get("tone") if b.get("tone") in TONES else "", "length": b.get("length") if b.get("length") in LENGTHS else "",
            "words": int(words) if str(words or "").isdigit() and 0 < int(words) < 20000 else 0,
            "cite": [k for k in _lst(b.get("cite"), 40, 80) if re.fullmatch(r"[\w:.\-]+", k)],
            "results": res, "results_only": bool(b.get("results_only", True))}


def clean_paper_brief(b: dict) -> dict:
    return {k: str((b or {}).get(k) or "")[:6000] for k in DEFAULT_PAPER_BRIEF}


def get_brief(p: dict, sid: str) -> dict:
    b = dict(DEFAULT_BRIEF)
    b.update(clean_brief((p.get("section_briefs") or {}).get(sid) or {}))
    b["directions"] = (p.get("section_notes") or {}).get(sid, "")
    return b


def is_empty(b: dict) -> bool:
    return not (b.get("directions", "").strip() or b["must"] or b["avoid"] or b["outline"] or b["tone"] or b["length"]
                or b["words"] or b["cite"] or b["results"])


def paper_block(p: dict) -> str:
    pb = clean_paper_brief(p.get("paper_brief") or {})
    parts = []
    if pb["story"].strip():
        parts.append(f"Overall story / key claims the whole paper must support:\n{pb['story'].strip()}")
    if pb["style"].strip():
        parts.append(f"Writing style preferences:\n{pb['style'].strip()}")
    if pb["terms"].strip():
        parts.append(f"Terminology & notation to use consistently:\n{pb['terms'].strip()}")
    if pb["avoid"].strip():
        parts.append(f"Never do / never claim (whole paper):\n{pb['avoid'].strip()}")
    return "\n".join(parts)


def render(p: dict, sid: str, role: str = "author", valid_keys: list | None = None, budget: int = 16000) -> str:
    """Binding brief block for one section. role: author | editor | reviewer."""
    from . import results as RS
    b = get_brief(p, sid)
    paper = paper_block(p)
    if is_empty(b) and not paper:
        return ""
    out = []
    if paper:
        out.append("PAPER-WIDE BRIEF:\n" + paper)
    if b["directions"].strip():
        out.append("Directions / what the author wants from this section:\n" + b["directions"].strip())
    if b["outline"]:
        out.append("Required structure — follow this order (one paragraph or \\subsection per item):\n"
                   + "\n".join(f"{i}. {x}" for i, x in enumerate(b["outline"], 1)))
    if b["must"]:
        out.append("Must include:\n" + "\n".join(f"- {x}" for x in b["must"]))
    if b["avoid"]:
        out.append("Must avoid:\n" + "\n".join(f"- {x}" for x in b["avoid"]))
    if b["tone"]:
        out.append("Tone: " + TONES[b["tone"]])
    if b["words"]:
        out.append(f"Target length: about {b['words']} words.")
    elif b["length"]:
        out.append("Target length: " + LENGTHS[b["length"]])
    if b["cite"]:
        keys = [k for k in b["cite"] if valid_keys is None or k in valid_keys]
        if keys:
            out.append("Give prominence to these references (cite them where relevant): " + ", ".join(keys))
    if b["results"]:
        room = max(1500, budget // max(1, len(b["results"])))
        lines = ["RESULTS TO PRESENT IN THIS SECTION (in this order). Use ONLY the numbers contained here, copied exactly; "
                 "never add values that are not in these results."]
        if b["results_only"]:
            lines.append("Present ONLY these results in this section; other results may be mentioned only if strictly needed for context.")
        for i, r in enumerate(b["results"], 1):
            c = RS.resolve(r["ref"], room)
            if not c:
                lines.append(f"[R{i}] {r.get('title') or r['ref']} — (no longer available; skip it)")
                continue
            how = r["as"]
            if how == "figure" and not c.get("figure"):
                how = "auto"
            lines.append(f"[R{i}] {c['title']} (type: {c['kind']}) — present as: {how} → {PRESENT_HELP[how]}.")
            if r.get("note", "").strip():
                lines.append(f"     Author's note for R{i}: {r['note'].strip()}")
            if c.get("figure") and how in ("figure", "auto"):
                lines.append(f"     Figure LaTeX: \\begin{{figure}}[t]\\centering\\includegraphics[width=\\linewidth]{{{c['figure']['path']}}}"
                             f"\\caption{{<caption grounded in the description/analysis below>}}\\label{{{c['figure']['label']}}}\\end{{figure}}")
            body = c["body"].strip()
            lines.append("     " + body.replace("\n", "\n     "))
        out.append("\n".join(lines))
    head = {"author": "AUTHOR'S BRIEF FOR THIS SECTION — binding; it overrides the generic section guidance:",
            "editor": "AUTHOR'S BRIEF (binding; takes precedence over reviewer suggestions — keep the revised section compliant):",
            "reviewer": "AUTHOR'S BRIEF that this section must satisfy (report every deviation as a Major issue under '## Issues'):"}[role]
    return head + "\n" + "\n\n".join(out)

