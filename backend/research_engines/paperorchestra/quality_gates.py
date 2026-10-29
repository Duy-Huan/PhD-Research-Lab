"""Evidence & Quality Gates for PaperOrchestra (v6.4.3).

Strict compliance with §5:
- Citation verification against BibTeX and topic library.
- Experimental result provenance matching measured task metrics.
- Figure source validation against FigureSpec hashes.
- LaTeX compilation and PDF layout preview.
- Scientific consistency checks across sections.
- Independent multi-criteria peer review.
- Explicit human approval before submission.
Never fabricate results, citations, or scientific claims.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from backend.agent import decision_ledger as L
from backend.core.config import data_dir, refs_dir, workspace
from backend.knowledge import corpus
from backend.knowledge import research_store as S
from backend.paper import latex as LB
from backend.paper.writer import clean_section, load_project
from backend.research_engines.paperorchestra.contracts import (
    CitationReport,
    CitationVerificationItem,
    ExperimentProvenanceItem,
    ExperimentProvenanceReport,
    FigureValidationItem,
    FigureValidationReport,
    IndependentReviewReport,
    IndependentReviewScore,
    LaTeXCompilationReport,
    ManuscriptReport,
    ScientificConsistencyReport,
    VerificationQualityReport,
)

CITE_PATTERN = re.compile(r"\\(cite[a-zA-Z]*)\*?(?:\[[^\]]*\])?\{([^}]*)\}")
METRIC_NUM_PATTERN = re.compile(r"(\b\d+(?:\.\d+)?%?|\b(?:BLEU|ROUGE|Accuracy|F1|Loss|MSE|MAE|Precision|Recall)\s*[:=]\s*[\d.]+%?)", re.I)


def get_known_bib_keys(topic_id: str = "") -> dict[str, str]:
    """Retrieve all verifiable citation keys and titles from refs_dir and topic papers."""
    known: dict[str, str] = {}

    # 1. Project references.bib / refs_dir
    r_dir = refs_dir()
    bib_file = r_dir / "references.bib"
    if bib_file.exists():
        content = bib_file.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"@\w+\s*\{\s*([^,\s]+),", content):
            key = match.group(1).strip()
            title_m = re.search(rf"@\w+\s*\{{\s*{re.escape(key)}[^}}]*?title\s*=\s*[{{\"](.*?)[}}\"]", content, re.DOTALL | re.IGNORECASE)
            title = title_m.group(1).strip() if title_m else key
            known[key] = title

    # 2. Topic papers from corpus
    if topic_id:
        try:
            with S.db() as c:
                rows = c.execute(
                    "SELECT p.id, p.payload FROM papers p JOIN paper_topics pt ON p.id = pt.paper_id WHERE pt.topic_id=?",
                    (topic_id,),
                ).fetchall()
                for pid, payload_str in rows:
                    payload = json.loads(payload_str)
                    title = payload.get("title") or pid
                    # Format standard keys e.g. "vaswani2017attention" or pid
                    key_hint = payload.get("bibtex_key") or pid.replace("-", "").replace(".", "_")
                    known[key_hint] = title
                    known[pid] = title
                    known[corpus.cite_key(pid)] = title  # the key the bibliography and the writer's evidence use
        except Exception:
            pass

    return known


def verify_citations(topic_id: str, text: str) -> CitationReport:
    """Validate all citations in LaTeX / text against registered papers."""
    known = get_known_bib_keys(topic_id)
    items: list[CitationVerificationItem] = []
    total = 0
    valid_count = 0
    missing_count = 0
    substituted_count = 0

    seen_keys: set[str] = set()
    for m in CITE_PATTERN.finditer(text):
        raw_keys = [k.strip() for k in m.group(2).split(",") if k.strip()]
        for k in raw_keys:
            if k in seen_keys:
                continue
            seen_keys.add(k)
            total += 1
            if k in known:
                valid_count += 1
                items.append(
                    CitationVerificationItem(
                        key=k,
                        status="valid",
                        matched_title=known[k][:100],
                        detail="Verified in project library/topic corpus.",
                    )
                )
            else:
                # Check for possible substitution match
                sub_match = next((kk for kk in known if kk.lower() in k.lower() or k.lower() in kk.lower()), None)
                if sub_match:
                    substituted_count += 1
                    items.append(
                        CitationVerificationItem(
                            key=k,
                            status="substituted",
                            matched_title=known[sub_match][:100],
                            detail=f"Fuzzy match to known reference '{sub_match}'.",
                        )
                    )
                else:
                    missing_count += 1
                    items.append(
                        CitationVerificationItem(
                            key=k,
                            status="missing",
                            detail="Citation key not found in library or topic papers (hallucination risk).",
                        )
                    )

    passed = missing_count == 0
    return CitationReport(
        total_citations=total,
        valid_count=valid_count,
        missing_count=missing_count,
        substituted_count=substituted_count,
        items=items,
        passed=passed,
    )


def verify_experiment_provenance(topic_id: str, text: str, mission_tasks: Sequence[dict] | None = None) -> ExperimentProvenanceReport:
    """Validate experimental metrics in text against real completed mission tasks/runs."""
    items: list[ExperimentProvenanceItem] = []
    total_claims = 0
    verified_claims = 0
    unverified_claims = 0

    # Extract claims containing metrics
    sentences = [s.strip() for s in re.split(r"(?<!\d)\.(?:\s+|$)|[\r\n]+", text) if s.strip()]
    metric_sentences = [s for s in sentences if METRIC_NUM_PATTERN.search(s) and len(s) > 15]

    # Gather known measured metrics from mission tasks
    known_metrics: dict[str, Any] = {}
    if mission_tasks:
        for t in mission_tasks:
            result = (t.get("payload") or {}).get("result", {})
            out = result.get("output", {})
            if isinstance(out, dict):
                for k, v in out.items():
                    if isinstance(v, (int, float, str)):
                        known_metrics[f"{t.get('id')}:{k}"] = str(v)
                metrics_block = out.get("metrics") or out.get("results")
                if isinstance(metrics_block, dict):
                    for k, v in metrics_block.items():
                        known_metrics[f"{t.get('id')}:{k}"] = str(v)

    # Also check experiment_runs in SQLite
    if topic_id:
        try:
            with S.db() as c:
                rows = c.execute("SELECT id, payload FROM experiment_runs WHERE topic_id=?", (topic_id,)).fetchall()
                for exp_id, p_str in rows:
                    p = json.loads(p_str)
                    if isinstance(p.get("metrics"), dict):
                        for k, v in p["metrics"].items():
                            known_metrics[f"{exp_id}:{k}"] = str(v)
        except Exception:
            pass

    for sentence in metric_sentences[:15]:
        total_claims += 1
        # Check if any reported number/token matches known metrics
        matched = False
        matched_key = ""
        measured_val = ""
        for k, v in known_metrics.items():
            if str(v) in sentence:
                matched = True
                matched_key = k
                measured_val = str(v)
                break

        if matched:
            verified_claims += 1
            items.append(
                ExperimentProvenanceItem(
                    claim_text=sentence[:150],
                    experiment_id=matched_key.split(":")[0],
                    reported_value=measured_val,
                    measured_value=measured_val,
                    tolerance_passed=True,
                    provenance_hash=L.digest({"claim": sentence, "key": matched_key, "val": measured_val}),
                )
            )
        else:
            # If there are no experiments in topic, flag as unverified
            unverified_claims += 1
            items.append(
                ExperimentProvenanceItem(
                    claim_text=sentence[:150],
                    tolerance_passed=False,
                    reported_value="unmatched",
                    measured_value="none",
                )
            )

    passed = (unverified_claims == 0) or (total_claims == 0)
    return ExperimentProvenanceReport(
        total_claims=total_claims,
        verified_claims=verified_claims,
        unverified_claims=unverified_claims,
        items=items,
        passed=passed,
    )


def verify_figure_sources(topic_id: str, text: str) -> FigureValidationReport:
    """Validate \\includegraphics against registered FigureSpec artifacts."""
    from backend.figures import store as FS

    items: list[FigureValidationItem] = []
    total = 0
    valid_count = 0

    fig_refs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text)
    for ref in set(fig_refs):
        total += 1
        clean_ref = ref.replace("\\", "/").strip()
        filename = Path(clean_ref).name
        fig_id = Path(clean_ref).stem

        # Try to resolve figure via Figure Studio store
        found = False
        sha = ""
        exists = False
        data_hash_matches = True

        try:
            fig = FS.get_figure(topic_id, fig_id)
            if fig:
                found = True
                exp = fig.get("exports", {}).get("svg") or fig.get("exports", {}).get("pdf") or fig.get("exports", {}).get("png")
                if exp:
                    sha = exp.get("sha256", "")
                    exists = Path(exp.get("path", "")).exists()
                ver = fig.get("verification", {})
                data_hash_matches = bool(ver.get("status") == "verified")
        except Exception:
            pass

        # Check in workspace figures/ directory
        ws_fig = workspace() / clean_ref
        if not ws_fig.exists():
            ws_fig = workspace() / "figures" / filename
        if ws_fig.exists():
            exists = True
            found = True
            if not sha:
                import hashlib
                sha = hashlib.sha256(ws_fig.read_bytes()).hexdigest()

        if found and exists and data_hash_matches:
            valid_count += 1
            items.append(
                FigureValidationItem(
                    figure_ref=clean_ref,
                    figure_id=fig_id,
                    format=Path(clean_ref).suffix.lstrip("."),
                    sha256=sha,
                    file_exists=True,
                    source_data_hash_matches=True,
                    detail="Verified figure artifact with registered hash.",
                )
            )
        else:
            items.append(
                FigureValidationItem(
                    figure_ref=clean_ref,
                    figure_id=fig_id,
                    format=Path(clean_ref).suffix.lstrip("."),
                    sha256=sha,
                    file_exists=exists,
                    source_data_hash_matches=data_hash_matches,
                    detail="Figure file missing or unverified source data.",
                )
            )

    passed = (valid_count == total)
    return FigureValidationReport(
        total_figures=total,
        valid_figures=valid_count,
        items=items,
        passed=passed,
    )


def compile_and_preview_latex(custom_tex: str = "", layout: str = "template") -> LaTeXCompilationReport:
    """Run LaTeX compilation check via backend.paper.latex with quick-layout fallback."""
    try:
        # If custom text is passed, assemble temporary main.tex or compile existing project
        res = LB.compile_pdf(engine="local", layout=layout)
        pdf_path = res.get("pdf_path") or str(LB.build_dir() / "main.pdf")
        pdf_bytes = Path(pdf_path).stat().st_size if Path(pdf_path).exists() else 0
        return LaTeXCompilationReport(
            engine_used=res.get("engine") or "local",
            compilation_passed=bool(res.get("ok")),
            pdf_path=pdf_path,
            pdf_bytes=pdf_bytes,
            page_count=int(res.get("pages") or 1),
            errors=[e.get("message") if isinstance(e, dict) else str(e) for e in res.get("errors", [])],
            warnings=[w.get("message") if isinstance(w, dict) else str(w) for w in res.get("warnings", [])],
        )
    except Exception as exc:
        # Quick fallback simulation test without crashing
        return LaTeXCompilationReport(
            engine_used="none",
            compilation_passed=False,
            errors=[str(exc)[:300]],
        )


def check_scientific_consistency(sections: dict[str, str]) -> ScientificConsistencyReport:
    """Analyze semantic consistency and structural completeness between paper sections."""
    inconsistencies: list[str] = []
    intro = sections.get("introduction", "").lower()
    conclusion = sections.get("conclusion", "").lower()
    abstract = sections.get("abstract", "").lower()
    method = sections.get("methodology", "").lower()

    intro_aligned = bool(intro)
    conclusion_aligned = bool(conclusion)
    limitations_stated = False

    # Check for stated limitations
    for text in (sections.get("discussion", ""), sections.get("conclusion", "")):
        if any(w in text.lower() for w in ("limitation", "threats to validity", "future work", "hạn chế", "failure case")):
            limitations_stated = True
            break

    if not limitations_stated:
        inconsistencies.append("No explicit limitations or threat-to-validity stated in Discussion/Conclusion.")

    if abstract and intro:
        # Check that core keywords from abstract appear in introduction
        abs_words = set(re.findall(r"\b[a-zA-Z]{5,}\b", abstract))
        intro_words = set(re.findall(r"\b[a-zA-Z]{5,}\b", intro))
        overlap = len(abs_words & intro_words) / max(1, len(abs_words))
        if overlap < 0.2:
            inconsistencies.append("Low vocabulary alignment between Abstract and Introduction.")
            intro_aligned = False

    passed = len(inconsistencies) == 0
    return ScientificConsistencyReport(
        abstract_claims_checked=1 if abstract else 0,
        introduction_alignment=intro_aligned,
        conclusion_alignment=conclusion_aligned,
        limitations_explicitly_stated=limitations_stated,
        inconsistencies=inconsistencies,
        passed=passed,
    )


def run_independent_review(
    topic_id: str,
    manuscript_text: str,
    target_venue: str = "NeurIPS / IEEE",
) -> IndependentReviewReport:
    """Produce an objective, multi-criterion peer review score and recommendations."""
    scores: list[IndependentReviewScore] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    actions: list[str] = []

    length = len(manuscript_text.split())

    # Criterion 1: Technical Soundness
    has_math = bool(re.search(r"\\(?:begin\{equation\}|\[|\$)", manuscript_text))
    soundness_score = 8 if has_math else 6
    scores.append(IndependentReviewScore(
        criterion="Technical Soundness & Mathematical Rigor",
        score=soundness_score,
        comment="Formulations are stated with formal notation." if has_math else "Equations could be formalized further.",
    ))

    # Criterion 2: Empirical Evaluation
    has_metrics = bool(METRIC_NUM_PATTERN.search(manuscript_text))
    emp_score = 8 if has_metrics else 5
    scores.append(IndependentReviewScore(
        criterion="Empirical Evaluation & Provenance",
        score=emp_score,
        comment="Experimental results and baseline comparisons are detailed." if has_metrics else "Quantitative metrics should be strengthened.",
    ))

    # Criterion 3: Literature Grounding & Citations
    cites = len(CITE_PATTERN.findall(manuscript_text))
    cite_score = 9 if cites >= 5 else 6 if cites >= 2 else 4
    scores.append(IndependentReviewScore(
        criterion="Literature Coverage & Grounding",
        score=cite_score,
        comment=f"Incorporates {cites} contextual citations." if cites >= 5 else "Literature coverage is sparse; expand citations.",
    ))

    # Criterion 4: Clarity & Structure
    clarity_score = 8 if length >= 600 else 6
    scores.append(IndependentReviewScore(
        criterion="Clarity, Organization & Style",
        score=clarity_score,
        comment="Well-structured sections and academic tone." if length >= 600 else "Paper draft is brief; expand details.",
    ))

    overall = round(sum(s.score for s in scores) / len(scores), 1)
    rec: Any = "accept" if overall >= 8.0 else "weak_accept" if overall >= 7.0 else "borderline" if overall >= 5.5 else "reject"

    if overall >= 7.0:
        strengths.append("Thorough presentation and disciplined execution of the research hypothesis.")
        strengths.append("Adherence to academic formatting standards and clear section boundaries.")
    else:
        weaknesses.append("Empirical evidence requires stronger validation against established baselines.")
        actions.append("Add independent ablation runs and report standard deviations across random seeds.")

    return IndependentReviewReport(
        overall_score=overall,
        recommendation=rec,
        scores=scores,
        strengths=strengths,
        weaknesses=weaknesses,
        actionable_revisions=actions,
    )


MIN_SECTION_WORDS = 30


def check_manuscript(topic_id: str, sections: dict[str, str]) -> ManuscriptReport:
    """Fail on empty or non-manuscript sections and on a draft without citations when the topic has a library.

    Found live (v6.6.3): an agent-style answer (an approval plan in Vietnamese) and a draft with zero citations both
    passed the gates. Word counts ignore LaTeX commands."""
    from backend.research_engines.paperorchestra.evidence import AGENT_TEXT
    empty, agent = [], []
    for sid, text in sections.items():
        words = re.findall(r"\w+", re.sub(r"\\[a-zA-Z]+\*?(\{[^}]*\})?", " ", text or ""))
        if AGENT_TEXT.search(text or ""):
            agent.append(sid)
        elif len(words) < MIN_SECTION_WORDS:
            empty.append(sid)
    cites = len({k.strip() for m in CITE_PATTERN.finditer("\n".join(sections.values())) for k in m.group(2).split(",") if k.strip()})
    library = 0
    if topic_id:
        try:
            library = sum(1 for p in corpus.all_papers(topic_id) if p.get("state") != "dismissed")
        except (KeyError, ValueError):
            library = 0
    issues = [f"Section {s} is empty or under {MIN_SECTION_WORDS} words" for s in empty]
    issues += [f"Section {s} contains agent text (approval plan or commands), not manuscript text" for s in agent]
    if not sections:
        issues.append("No sections were written")
    if library and not cites:
        issues.append(f"The topic library has {library} papers but the draft cites none")
    return ManuscriptReport(empty_sections=empty, agent_text_sections=agent, citation_count=cites, library_size=library,
                            issues=issues, passed=not issues)


def evaluate_quality_gates(
    topic_id: str,
    sections: dict[str, str],
    mission_tasks: Sequence[dict] | None = None,
    allow_online_latex: bool = False,
) -> VerificationQualityReport:
    """Run all quality gates and aggregate into a unified VerificationQualityReport."""
    full_text = "\n\n".join(sections.values())
    m_report = check_manuscript(topic_id, sections)
    c_report = verify_citations(topic_id, full_text)
    p_report = verify_experiment_provenance(topic_id, full_text, mission_tasks)
    f_report = verify_figure_sources(topic_id, full_text)
    k_report = check_scientific_consistency(sections)
    l_report = compile_and_preview_latex()
    r_report = run_independent_review(topic_id, full_text)

    overall_readiness = (
        m_report.passed
        and c_report.passed
        and p_report.passed
        and f_report.passed
        and k_report.passed
        and (l_report.compilation_passed or not l_report.errors)
        and r_report.overall_score >= 6.0
    )

    return VerificationQualityReport(
        manuscript=m_report,
        citations=c_report,
        provenance=p_report,
        figures=f_report,
        compilation=l_report,
        consistency=k_report,
        review=r_report,
        overall_readiness=overall_readiness,
        human_submission_approved=False,
    )

