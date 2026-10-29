"""Evidence the section writer is given (v6.6.4, agent/PLAN_6.6.4_L3.md A6).

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): full orchestration wrote every section from the
objective alone (`write_section(..., "", ...)`), so the draft had no citations and measured numbers reached it only
when a person pasted them. The writer now receives the topic library with the exact cite keys of the bibliography and
the topic's measured experiment runs with their independent verification status, and nothing else counts as evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_PAPERS = 40
MAX_RUNS = 10
MAX_CHARS = 14000

AGENT_TEXT = re.compile(
    r"phdlab-action|```phdlab|(?<!\w)/(?:accept|reject)\b|Chờ bạn duyệt|Awaiting your approval|approval plan|"
    r"kế hoạch (?:phê duyệt|thực hiện)|I (?:will|would) need (?:your )?approval|please approve|vui lòng (?:duyệt|phê duyệt)",
    re.I)
PREAMBLE = re.compile(
    r"^\s*(?:sure|certainly|of course|okay|ok|here(?:'s| is| are)|below (?:is|are)|as requested|i(?:'ll| will| have)|"
    r"dưới đây|đây là|tôi (?:sẽ|đã)|vâng|được rồi)\b.*$", re.I)
OUTRO = re.compile(r"^\s*(?:let me know|i hope|feel free|would you like|do you want|hãy cho tôi biết|bạn có muốn)\b.*$", re.I)
FENCE = re.compile(r"```(?:latex|tex)?\s*\n(.*?)```", re.S | re.I)


@dataclass
class Evidence:
    text: str = ""
    keys: list[str] = field(default_factory=list)
    runs: list[str] = field(default_factory=list)


def _library(tid: str) -> list[dict]:
    from backend.knowledge import corpus
    papers = [p for p in corpus.all_papers(tid) if p.get("state") != "dismissed"]
    papers.sort(key=lambda p: (p.get("state") != "accepted", p.get("id")))
    return [{"key": corpus.cite_key(p["id"]), "title": p.get("title") or p["id"], "year": p.get("year") or "",
             "venue": p.get("venue") or "", "abstract": (p.get("abstract") or "")[:500], "accepted": p.get("state") == "accepted"}
            for p in papers[:MAX_PAPERS]]


def _measure(run: dict) -> str:
    c = run["payload"].get("comparison") or {}
    if run["payload"].get("kind") == "agent_code_v1":
        effects = "; ".join(
            f"{name} vs {c.get('baseline')}: paired {c.get('direction')} improvement of {c.get('primary_metric')} = "
            f"{e['paired_improvement']:.6g}" + (f" (95% CI {e['normal_approx_ci95'][0]:.6g} to {e['normal_approx_ci95'][1]:.6g})"
                                                 if e.get("normal_approx_ci95") else "") + f", {e['recommendation']}"
            for name, e in (c.get("effects") or {}).items())
        means = "; ".join(f"{name}: " + ", ".join(f"{m}={v:.6g}" for m, v in d["mean"].items())
                          for name, d in (c.get("per_condition") or {}).items())
        return f"means over {c.get('repeat_count')} seeds: {means}. {effects}"
    ci = c.get("normal_approx_ci95")
    return (f"selected smoothing alpha {c.get('selected_alpha')} on the validation split; paired PSNR gain "
            f"{c.get('paired_psnr_gain_db', 0):.6g} dB" + (f" (95% CI {ci[0]:.6g} to {ci[1]:.6g})" if ci else "") +
            f" over {c.get('repeat_count')} seeds, {c.get('recommendation')}; held-out test mean PSNR " +
            ", ".join(f"{t.get('mean_psnr_db', 0):.6g} dB" for t in run["payload"].get("test_evaluations") or []))


def _experiments(tid: str) -> list[tuple[str, str]]:
    from backend.execution import protocols
    from backend.knowledge.verification import verify_run
    out = []
    for run in [r for r in protocols.runs(tid) if r["status"] == "completed"][:MAX_RUNS]:
        try:
            report = verify_run(tid, run["id"])
            status = "verified and reproduced" if report["status"] == "passed" and report["reproduction_run_id"] else \
                "verified, not reproduced" if report["status"] == "passed" else "FAILED independent verification"
            hypothesis = protocols.get(tid, run["protocol_id"])["payload"]["spec"]["hypothesis"]
            out.append((run["id"], f"- experiment:{run['id']} [{status}] hypothesis: {hypothesis[:300]}. {_measure(run)}"))
        except (KeyError, ValueError, TypeError, OSError):
            continue
    return out


def gather(tid: str) -> Evidence:
    """The library and measured experiments of a topic as writer context, bounded in size. An unknown topic has none."""
    try:
        papers, runs = _library(tid), _experiments(tid)
    except (KeyError, ValueError):
        papers, runs = [], []
    parts = []
    if papers:
        parts.append("Topic library. Cite ONLY these keys, with \\cite{key}, and only for what the title/abstract supports:\n" +
                     "\n".join(f"- {p['key']}{'' if p['accepted'] else ' [not yet accepted into the bibliography]'}: "
                               f"{p['title']} ({p['year']}{', ' + p['venue'] if p['venue'] else ''}). {p['abstract']}"
                               for p in papers))
    else:
        parts.append("Topic library: empty. Do not write any \\cite command.")
    if runs:
        parts.append("Measured experiments (the ONLY numbers you may report; keep the verification status in the text):\n" +
                     "\n".join(line for _, line in runs))
    else:
        parts.append("Measured experiments: none. Do not report any experimental number or result.")
    text = "\n\n".join(parts)
    return Evidence(text=text[:MAX_CHARS], keys=[p["key"] for p in papers], runs=[rid for rid, _ in runs])


def manuscript_only(raw: str) -> str:
    """The LaTeX of a model answer without chat around it. Raises ValueError when the answer is not a manuscript."""
    if AGENT_TEXT.search(raw or ""):
        raise ValueError("The writer returned agent text (approval plan or commands), not a manuscript section")
    fenced = FENCE.findall(raw or "")
    text = "\n\n".join(fenced) if fenced else (raw or "").replace("```", "")
    lines = text.strip().splitlines()
    while lines and (not lines[0].strip() or PREAMBLE.match(lines[0])):
        lines.pop(0)
    while lines and (not lines[-1].strip() or OUTRO.match(lines[-1])):
        lines.pop()
    text = "\n".join(lines).strip()
    if len(re.findall(r"\w+", re.sub(r"\\[a-zA-Z]+\*?(\{[^}]*\})?", " ", text))) < 20:
        raise ValueError("The writer returned no usable section text")
    return text
