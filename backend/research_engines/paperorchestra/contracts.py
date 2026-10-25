"""PaperOrchestra Contracts & Typed Artifact Boundaries (v6.4.3).

Defines versioned writing artifact contracts, execution specs, quality gate
reports, and configuration models conforming to PhD Lab's L2-L4 architecture.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class WritingArtifact(Contract):
    """Shared, versioned, traceable artifact contract (§4).

    PaperOrchestra must not maintain an independent source of truth for
    research state; every writing task consumes and produces these records.
    """
    artifact_id: str = Field(default_factory=lambda: "art-" + secrets.token_hex(8))
    task_id: str = Field(min_length=1, max_length=120)
    parent_workflow_id: str = Field(min_length=1, max_length=120)  # mission_id or run_id
    topic_id: str = Field(default="", max_length=120)
    section_id: str = Field(default="", max_length=80)
    title: str = Field(default="", max_length=300)
    input_artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    output_artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence_refs: list[str] = Field(default_factory=list, max_length=200)
    agent_id: str = Field(default="writer", max_length=80)
    provider_id: str = Field(default="paperorchestra", max_length=80)
    execution_status: Literal["draft", "running", "completed", "failed", "verified", "rejected"] = "draft"
    checkpoint_id: str = Field(default="", max_length=120)
    version: int = Field(default=1, ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_status: Literal["draft", "pending_review", "verified", "rejected"] = "draft"
    execution_metrics: dict[str, Any] = Field(default_factory=dict)
    storage_path: str = Field(default="", max_length=1000)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    content: str = ""

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        parent_workflow_id: str,
        content: str,
        section_id: str = "",
        title: str = "",
        topic_id: str = "",
        input_artifact_ids: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        agent_id: str = "writer",
        provider_id: str = "paperorchestra",
        checkpoint_id: str = "",
        version: int = 1,
        review_status: Literal["draft", "pending_review", "verified", "rejected"] = "draft",
        execution_metrics: dict[str, Any] | None = None,
        storage_path: str = "",
    ) -> WritingArtifact:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        metrics = execution_metrics or {}
        metrics.setdefault("char_count", len(content))
        metrics.setdefault("word_count", len(content.split()))
        return cls(
            task_id=task_id,
            parent_workflow_id=parent_workflow_id,
            topic_id=topic_id,
            section_id=section_id,
            title=title or (f"Section: {section_id}" if section_id else "Manuscript Artifact"),
            input_artifact_ids=input_artifact_ids or [],
            evidence_refs=evidence_refs or [],
            agent_id=agent_id,
            provider_id=provider_id,
            execution_status="completed",
            checkpoint_id=checkpoint_id or f"chk-{secrets.token_hex(6)}",
            version=version,
            content_hash=content_hash,
            review_status=review_status,
            execution_metrics=metrics,
            storage_path=storage_path,
            content=content,
        )


class SectionOutline(Contract):
    section_id: str
    title: str
    target_words: int = Field(default=500, ge=50, le=5000)
    bullet_points: list[str] = Field(default_factory=list, max_length=20)
    citation_hints: list[str] = Field(default_factory=list, max_length=30)
    figure_refs: list[str] = Field(default_factory=list, max_length=10)
    experiment_refs: list[str] = Field(default_factory=list, max_length=10)


class PaperOutline(Contract):
    paper_title: str
    abstract_summary: str
    sections: list[SectionOutline] = Field(min_length=1, max_length=15)
    style: str = "IEEE"
    target_venue: str = ""


class CitationVerificationItem(Contract):
    key: str
    status: Literal["valid", "missing", "substituted", "invalid_syntax"]
    matched_title: str = ""
    evidence_id: str = ""
    detail: str = ""


class CitationReport(Contract):
    total_citations: int = 0
    valid_count: int = 0
    missing_count: int = 0
    substituted_count: int = 0
    items: list[CitationVerificationItem] = Field(default_factory=list)
    passed: bool = True


class ExperimentProvenanceItem(Contract):
    claim_text: str
    experiment_id: str = ""
    trial_key: str = ""
    reported_value: str = ""
    measured_value: str = ""
    tolerance_passed: bool = True
    provenance_hash: str = ""


class ExperimentProvenanceReport(Contract):
    total_claims: int = 0
    verified_claims: int = 0
    unverified_claims: int = 0
    items: list[ExperimentProvenanceItem] = Field(default_factory=list)
    passed: bool = True


class FigureValidationItem(Contract):
    figure_ref: str
    figure_id: str = ""
    format: str = ""
    sha256: str = ""
    file_exists: bool = True
    source_data_hash_matches: bool = True
    detail: str = ""


class FigureValidationReport(Contract):
    total_figures: int = 0
    valid_figures: int = 0
    items: list[FigureValidationItem] = Field(default_factory=list)
    passed: bool = True


class LaTeXCompilationReport(Contract):
    engine_used: str = ""
    compilation_passed: bool = False
    pdf_path: str = ""
    pdf_bytes: int = 0
    page_count: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScientificConsistencyReport(Contract):
    abstract_claims_checked: int = 0
    introduction_alignment: bool = True
    conclusion_alignment: bool = True
    limitations_explicitly_stated: bool = True
    inconsistencies: list[str] = Field(default_factory=list)
    passed: bool = True


class IndependentReviewScore(Contract):
    criterion: str  # e.g., "Originality", "Technical Soundness", "Empirical Evaluation", "Clarity"
    score: int = Field(ge=1, le=10)
    comment: str


class IndependentReviewReport(Contract):
    overall_score: float = Field(ge=1.0, le=10.0)
    recommendation: Literal["accept", "weak_accept", "borderline", "weak_reject", "reject"] = "borderline"
    scores: list[IndependentReviewScore] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    actionable_revisions: list[str] = Field(default_factory=list)


class VerificationQualityReport(Contract):
    """Unified evidence and quality gates verification report (§5)."""
    citations: CitationReport = Field(default_factory=CitationReport)
    provenance: ExperimentProvenanceReport = Field(default_factory=ExperimentProvenanceReport)
    figures: FigureValidationReport = Field(default_factory=FigureValidationReport)
    compilation: LaTeXCompilationReport = Field(default_factory=LaTeXCompilationReport)
    consistency: ScientificConsistencyReport = Field(default_factory=ScientificConsistencyReport)
    review: IndependentReviewReport = Field(default_factory=lambda: IndependentReviewReport(overall_score=7.0))
    overall_readiness: bool = False
    human_submission_approved: bool = False
    approval_note: str = ""
    evaluated_at: str = Field(default_factory=_now)


class PaperWritingTaskSpec(Contract):
    """Specification for individual capability execution."""
    operation_id: str = Field(pattern=r"^PO-[0-9a-f]{8}:S[0-9]+$")
    mission_id: str
    topic_id: str
    task_id: str
    capability: Literal[
        "paperorchestra.outline",
        "paperorchestra.section_write",
        "paperorchestra.refine",
        "paperorchestra.cite_verify",
        "paperorchestra.figure_integrate",
        "paperorchestra.full_orchestration",
    ]
    section_id: str = ""
    objective: str = Field(min_length=1, max_length=20000)
    context: str = Field(default="", max_length=200000)
    paper_ids: list[str] = Field(default_factory=list, max_length=50)
    figure_id: str = ""
    style: str = "IEEE"
    target_venue: str = ""
    time_limit_s: int = Field(default=600, ge=10, le=7200)
    backend_mode: Literal["auto", "cli", "harness_skills"] = "auto"


class PaperOrchestraConfig(Contract):
    """Engine configuration settings."""
    enabled: bool = True
    default_backend: Literal["auto", "cli", "harness_skills"] = "auto"
    cli_binary: str = "paper-orchestra"
    cli_timeout_s: int = Field(default=600, ge=10, le=7200)
    isolated_workspace_root: str = ""
    allow_api_billing: bool = False
    max_revisions: int = Field(default=3, ge=1, le=5)
    default_style: str = "IEEE"

