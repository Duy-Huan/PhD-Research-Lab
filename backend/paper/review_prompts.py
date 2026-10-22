"""Prompts and venue standards for the external Paper Review flow (v2.5).

The venue bar is described qualitatively. Rank proportions and acceptance rates are TYPICAL figures used only
to calibrate the reviewer's strictness; they are not claims about any specific venue.
"""
from __future__ import annotations

ICORE = {
    "A*": ("Flagship conference: a leading venue of the discipline (roughly the top ~7% of CORE-ranked conferences; "
           "typical acceptance rates ~15-25%). Expect a clear, significant advance over the state of the art, a compelling "
           "and well-motivated problem, comprehensive experiments against the strongest recent baselines, thorough ablations, "
           "statistical rigour, reproducibility details and excellent writing. Solid-but-incremental work is rejected."),
    "A": ("Excellent conference, highly respected in the discipline (roughly the next ~17% of CORE-ranked conferences; "
          "typical acceptance ~20-30%). Expect clear novelty, convincing evaluation on standard benchmarks with recent SOTA "
          "comparisons and ablations; incremental ideas need strong, well-analysed empirical gains."),
    "B": ("Good, well-regarded conference (roughly the next ~27% of CORE-ranked conferences; typical acceptance ~30-45%). "
          "Expect a sound contribution with reasonable novelty and adequate evaluation; limitations are acceptable when "
          "acknowledged and the claims match the evidence."),
    "C": ("Ranked conference meeting the minimum standards of the field (typical acceptance ~40-60%). Expect technically "
          "correct, relevant and clearly written work with a modest contribution and at least basic validation."),
}
ICORE_EQUIV = {"100+": "A*", "50-99": "A", "25-49": "B", "10-24": "C", "<10": "C"}
H5 = {
    "100+": "h5-index ≥ 100 (Google Scholar Metrics): the very top venues of the field — apply a flagship (A*-level) bar.",
    "50-99": "h5-index 50-99: highly cited, highly selective venue — apply an A-level bar.",
    "25-49": "h5-index 25-49: well-cited, selective venue — apply a B-to-A level bar.",
    "10-24": "h5-index 10-24: established venue with moderate selectivity — apply a B/C-level bar.",
    "<10": "h5-index < 10: smaller / emerging venue or workshop-like — apply a C-level bar focused on soundness and clarity.",
}
QUARTILE = {
    "Q1": ("Q1 journal: top 25% of its subject category (SJR / JCR). Expect a significant, well-validated contribution, a "
           "thorough and current literature review, comprehensive experiments with statistical analysis, reproducibility "
           "(code/data availability), journal-length depth and polished writing. An extended conference paper must add "
           "substantial new material. Most first submissions receive Major Revision or Reject."),
    "Q2": ("Q2 journal: 25-50% of its category. Expect a solid contribution, rigorous methodology, good validation against "
           "relevant baselines and clear writing; moderate novelty is acceptable when the evaluation is convincing."),
    "Q3": ("Q3 journal: 50-75% of its category. Expect technically sound work with a clear (possibly applied or "
           "incremental) contribution, correct methodology, adequate validation and clear presentation."),
    "Q4": ("Q4 journal: bottom 25% of its category. Expect basic soundness, relevance to the journal's scope and clear "
           "presentation; limited novelty is acceptable but technical errors are not."),
}

CONF_DECISIONS = "Strong Accept | Accept | Weak Accept | Borderline | Weak Reject | Reject | Strong Reject"
JOURNAL_DECISIONS = "Accept | Minor Revision | Major Revision | Reject and Resubmit | Reject"


def venue_label(v: dict) -> str:
    name = (v.get("name") or "").strip()
    if v.get("type") == "journal":
        base = f"Journal · {v.get('quartile', 'Q1')}"
    elif v.get("scale") == "h5":
        base = f"Conference · h5 {v.get('h5', '50-99')}"
    else:
        base = f"Conference · ICORE {v.get('rank', 'A')}"
    return f"{base}{' · ' + name if name else ''}"


def venue_brief(v: dict) -> str:
    """Natural-language description of the bar the reviewers must apply."""
    if v.get("type") == "journal":
        q = v.get("quartile") if v.get("quartile") in QUARTILE else "Q1"
        text = (f"VENUE TYPE: international journal ({q}).\n{QUARTILE[q]}\n"
                f"DECISION SCALE (journal): {JOURNAL_DECISIONS}.\n"
                "Journal reviewing style: detailed comments to the authors, numbered so they can respond point by point, "
                "plus short confidential comments to the editor.")
    else:
        if v.get("scale") == "h5":
            band = v.get("h5") if v.get("h5") in H5 else "50-99"
            bar = f"{H5[band]}\nEquivalent ICORE bar: {ICORE[ICORE_EQUIV[band]]}"
            what = f"conference ranked by h5-index ({band})"
        else:
            rank = v.get("rank") if v.get("rank") in ICORE else "A"
            bar, what = ICORE[rank], f"conference ranked ICORE/CORE {rank}"
        text = (f"VENUE TYPE: {what}.\n{bar}\nDECISION SCALE (conference): {CONF_DECISIONS}.\n"
                "Conference reviewing style: one review round (no major revision), so judge the paper as submitted; "
                "the rebuttal can only clarify, not add new experiments.")
    if (v.get("name") or "").strip():
        text += f"\nNAMED VENUE: {v['name'].strip()} — apply its known scope and standards when you are confident about them."
    if (v.get("field") or "").strip():
        text += f"\nFIELD / TRACK: {v['field'].strip()}"
    text += ("\nREVIEW MODE: double-blind — also flag anything that reveals the authors' identity."
             if v.get("blind", True) else "\nREVIEW MODE: single-blind (author names are visible).")
    return text


PERSONAS = {
    1: [("R1", "Comprehensive reviewer",
         "Cover everything: novelty and significance, positioning versus the state of the art, technical soundness, "
         "experimental evaluation and statistics, reproducibility, clarity, presentation and formatting.")],
    2: [("R1", "Domain expert — novelty, significance & related work",
         "Focus on the novelty claim, significance, positioning against the state of the art and missing related work; "
         "also judge whether the conclusions follow."),
        ("R2", "Methodology & experiments expert (the demanding Reviewer 2)",
         "Focus on technical correctness (equations, assumptions, proofs), experimental design, baselines, datasets, "
         "metrics, ablations, statistical significance and reproducibility; also clarity and presentation.")],
    3: [("R1", "Domain expert — novelty, significance & related work",
         "Focus on the novelty claim, significance, positioning against the state of the art and missing related work; "
         "also judge whether the conclusions follow."),
        ("R2", "Methodology & experiments expert (the demanding Reviewer 2)",
         "Focus on technical correctness (equations, assumptions, proofs), experimental design, baselines, datasets, "
         "metrics, ablations, statistical significance and reproducibility."),
        ("R3", "Clarity, presentation & venue-fit reviewer",
         "Focus on structure, argument flow, writing quality, notation consistency, figures/tables, formatting, "
         "limitations and ethics statements, anonymity and fit to the venue's scope and audience.")],
}

_GROUNDING = """Integrity rules (strict):
- Ground every comment in the manuscript: give the location as (p. N) using the [[Page N]] markers and/or the section, and quote short exact phrases.
- Never invent content that is not in the manuscript, and never invent references, numbers or venue facts. When you think related work is missing, describe the line of work; name a specific paper only if you are certain it exists and mark it "(verify)".
- If the manuscript text is truncated or garbled (PDF extraction), say so instead of guessing; do not penalise extraction artefacts such as broken ligatures or hyphenation."""


def reviewer_system(v: dict, persona: tuple) -> str:
    rid, title, focus = persona
    journal = v.get("type") == "journal"
    decisions = JOURNAL_DECISIONS if journal else CONF_DECISIONS
    return f"""You are {rid}, an experienced, fair but rigorous peer reviewer serving on the programme committee / editorial board of the venue below. Your role: {title}.
{focus}
Write the review a real {'journal reviewer' if journal else 'conference PC member'} at this level would write, calibrated EXACTLY to the venue bar: a paper that would be accepted at a lower-ranked venue may deserve rejection here, and vice versa.

{venue_brief(v)}

{_GROUNDING}

Output Markdown in exactly this structure:
# {rid} — {title}
**Recommendation:** <one of: {decisions}>
**Overall score:** <1-10>/10 · **Confidence:** <1-5>/5
## Summary of the submission
3-5 sentences in your own words: problem, approach, claimed contributions, main results.
## Strengths
Numbered.
## Weaknesses
Numbered, most serious first.
## Detailed comments
Numbered; each starts with a severity tag [Critical], [Major], [Minor] or [Typo], then **Location** (p. N / section), the problem and a concrete suggestion.
## Questions for the authors
Questions whose answers could change your assessment.
## Scores
| Criterion | Score (1-5) | Comment |
with rows: Novelty / originality, Technical soundness, Experimental evaluation, Clarity & presentation, Significance / impact, Reproducibility, Relevance to the venue.
## Assessment against the venue bar
Why the paper does or does not meet this venue's bar, and what would make it acceptable.
{'## Confidential comments to the editor' + chr(10) + 'Two or three sentences.' if journal else '## Comments to the area chair' + chr(10) + 'One or two sentences (not shown to authors).'}"""


def reviewer_user(paper: str, prescreen: str, title: str) -> str:
    return f"MANUSCRIPT TITLE (detected): {title or '(unknown)'}\n\nAUTOMATIC DESK CHECK (facts computed by software):\n{prescreen}\n\nMANUSCRIPT TEXT (extracted; [[Page N]] marks page starts):\n{paper}"


def meta_system(v: dict) -> str:
    journal = v.get("type") == "journal"
    role = "Associate Editor (handling editor)" if journal else "Area Chair / senior PC member"
    decisions = JOURNAL_DECISIONS if journal else "Accept | Accept (poster) | Borderline | Reject"
    return f"""You are the {role} of the venue below. You have the manuscript and the independent reviewer reports.
Write the meta-review and a practical revision roadmap for the authors. Weigh the reviews (do not just average them), resolve disagreements by checking the manuscript yourself, and discard reviewer points that the manuscript clearly answers.

{venue_brief(v)}

{_GROUNDING}

Output Markdown in exactly this structure:
# Meta-review
**Decision:** <one of: {decisions}>
**Consensus score:** <1-10>/10
## Summary of the reviews
Where the reviewers agree and disagree, and your resolution.
## Decisive strengths
## Decisive weaknesses
What blocks acceptance at THIS venue level, most serious first.
## Required changes
Numbered must-fix items for acceptance{' in the revised manuscript' if journal else ' (or for a resubmission)'}.
## Revision roadmap
Ordered phases — Phase 1: Critical fixes, Phase 2: Major, Phase 3: Minor, Phase 4: Language & formatting polish. For each step: the concrete task, which reviewer comments it answers (e.g. R2.3), whether it needs new experiments/analysis or only text changes, and an effort estimate (hours or days).
## Venue fit
Is this the right venue level? If the bar is clearly out of reach, suggest a more suitable level (e.g. ICORE B, or Q2 journals) — do not invent venue names.
## Outlook after revision
Realistic acceptance chances if the roadmap is completed."""


ISSUES_SYS = """You convert peer-review reports into a structured, de-duplicated list of revision issues for the authors.
Read the manuscript, the reviewer reports and the meta-review. Merge duplicates (record every reviewer who raised it). Also scan the manuscript yourself for clear language errors and typos (at most 15 such items).
Return ONLY a JSON object, no prose, no code fences:
{"issues": [
  {"id": "I1",
   "severity": "critical" | "major" | "minor" | "typo",
   "category": "novelty" | "soundness" | "experiments" | "related_work" | "clarity" | "presentation" | "formatting" | "reproducibility" | "ethics" | "anonymity" | "language",
   "title": "short headline (max 12 words)",
   "location": "section and/or page, e.g. 'Sec. 3.2, p. 4'",
   "quote": "an EXACT verbatim excerpt (10-300 characters) copied from the manuscript text where the problem is, or \\"\\" when the issue is not tied to one passage",
   "problem": "what is wrong and why it matters at this venue",
   "fix": "the concrete recommended change",
   "fix_type": "text" | "experiment" | "analysis" | "figure" | "structure",
   "effort": "minutes" | "hours" | "days",
   "raised_by": ["R1", "R2", "AC", "auto"]}
]}
Severity: critical = would by itself cause rejection at this venue; major = must be fixed for acceptance; minor = should be fixed; typo = spelling/grammar/formatting slip.
Order by severity (critical first), then by position in the paper. At most 60 issues. Copy quotes character-for-character from the manuscript text (they are verified automatically)."""


def issues_user(paper: str, reviews: str, meta: str, venue: str) -> str:
    return f"VENUE: {venue}\n\nMETA-REVIEW:\n{meta}\n\nREVIEWER REPORTS:\n{reviews}\n\nMANUSCRIPT TEXT:\n{paper}"


FIX_SYS = """You are a senior academic editor and co-author. Fix ONE review issue in the manuscript with the smallest change that fully resolves it, written to the standard of the target venue.
Integrity rules: never invent results, numbers, datasets or citations. Where new evidence is needed write a red placeholder — LaTeX: \\textcolor{red}{[TBD: what is needed]} or \\textcolor{red}{[CITATION NEEDED]}; plain text: [TBD: ...] / [CITATION NEEDED].
Keep the format of the excerpt: if the excerpt is LaTeX, the revision must be valid LaTeX (keep \\label, \\ref, \\cite keys unchanged); otherwise plain text.

Answer with these blocks, each on its own lines, in this order:
<<<ORIGINAL
the exact passage to replace, copied character-for-character from the EXCERPT (whole sentences or a whole paragraph); leave it empty if the fix only inserts new text
>>>
<<<REVISED
the replacement text (or the new text to insert)
>>>
<<<NOTE
1-3 sentences: what changed and why; where to insert new text when ORIGINAL is empty; anything the author must still supply
>>>
<<<PLAN
only when text editing alone cannot resolve the issue (new experiment, figure, analysis): numbered concrete steps for the author; otherwise leave empty
>>>"""


def fix_user(venue: str, issue: dict, excerpt: str, fmt: str, instructions: str = "") -> str:
    fields = {k: issue.get(k) for k in ("id", "severity", "category", "title", "location", "quote", "problem", "fix", "fix_type")}
    extra = f"\nAUTHOR'S INSTRUCTIONS (take precedence):\n{instructions.strip()}\n" if instructions.strip() else ""
    return f"VENUE: {venue}\nEXCERPT FORMAT: {fmt}\n\nISSUE:\n{fields}\n{extra}\nEXCERPT OF THE MANUSCRIPT:\n{excerpt}"


RESPONSE_SYS = """You draft the authors' response letter to the reviewers ("response to reviewers" / rebuttal) for the venue below.
Rules:
- Polite, precise, non-defensive; thank the reviewers once, not in every answer.
- Structure: short letter to the editor / programme chairs → summary of the main changes → for each reviewer (R1, R2, R3, AC/editor) a numbered point-by-point section: **Comment R2.3** (quote or paraphrase) → **Response** → **Changes in the manuscript** (location).
- Use the issue list and its status. NEVER claim a change that is not marked as done/fixed. For open issues write a placeholder: [AUTHOR: describe the change or justify why not]. For conference rebuttals keep it concise and do not promise new experiments the venue does not allow.
- Never invent numbers or results; use [TBD: ...] where values are needed.
Output Markdown."""


def response_user(venue: str, meta: str, reviews: str, issues_digest: str) -> str:
    return f"VENUE: {venue}\n\nMETA-REVIEW:\n{meta}\n\nREVIEWER REPORTS:\n{reviews}\n\nISSUES AND STATUS:\n{issues_digest}"


GUIDE_SYS = """You are a senior academic mentor who has served as reviewer and area chair for the target venue. Write a REVISION GUIDE that tells the authors exactly how to fix their manuscript, issue by issue, so that a second-round reviewer would be satisfied.
Rules:
- Work only from the reviewer reports, the meta-review, the issue list and the proposed fixes given below. Never invent results, numbers, datasets or citations: where new evidence is needed say precisely what experiment / analysis / citation the authors must produce and mark it [TBD].
- Order: CRITICAL → MAJOR → MINOR → TYPO; inside one severity, the issues that most change the decision first.
- Markdown only, in the language requested. Structure:
  # Revision guide — <title>
  ## 1. Verdict and what must change (5–8 bullets: the decision risk, the 3 most important changes, estimated total effort)
  ## 2. Revision plan (a table: # | Issue | Severity | Where | Effort (h) | Depends on)
  ## 3. Issue-by-issue instructions — for EVERY issue a subsection "### <id> · <severity> — <title>" with:
     **Where:** section / page / figure / table · **Why reviewers care:** one or two sentences tied to the venue standard ·
     **How to fix — step by step:** numbered concrete actions (what to write, run, measure, cite, move or delete) ·
     **Example revision:** a short before → after passage when the issue is textual (use the proposed fix when given) ·
     **Done when:** a checklist of verifiable acceptance criteria · **Response-letter sentence:** one sentence the authors can adapt.
  ## 4. New experiments / analyses to run (consolidated, with the metric and the baseline each one needs)
  ## 5. Writing and presentation checklist (figures, tables, notation, related work, limitations, reproducibility, ethics, page limit)
  ## 6. Final pre-submission checklist (- [ ] items)
- Be specific to THIS manuscript; no generic advice that would fit any paper."""


def guide_user(venue: str, title: str, meta: str, reviews: str, issues: str, fixes: str, language: str) -> str:
    lang = "Vietnamese (keep technical terms in English)" if language == "vi" else "English"
    return (f"LANGUAGE OF THE GUIDE: {lang}\nVENUE: {venue}\nTITLE: {title}\n\nMETA-REVIEW:\n{meta}\n\nREVIEWER REPORTS:\n{reviews}"
            f"\n\nISSUES AND STATUS:\n{issues}\n\nPROPOSED FIXES (accepted or proposed):\n{fixes}")
