"""Module C — Context Intelligence Gateway (v6.4.2).

Constructs deterministic, role-aware, permission-scoped, and evidence-cited
Context Packs (`ContextPackBuilder`) with prompt-injection stripping, secret
redaction, and cross-topic isolation.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.core.telemetry import redact
from backend.intelligence import observability
from backend.knowledge import corpus as K, research_context as RC, research_store as S

ROLE_PROFILES: dict[str, dict] = {
    "literature_reviewer": {
        "focus": "papers_and_citations",
        "include_papers": True,
        "include_code_artifacts": False,
        "include_experiments": False,
        "prohibited_actions": ["edit_code", "run_shell", "publish_external", "write_outside_workspace"],
    },
    "experiment_engineer": {
        "focus": "protocols_code_and_metrics",
        "include_papers": False,
        "include_code_artifacts": True,
        "include_experiments": True,
        "prohibited_actions": ["approve_scientific_claim", "publish_external", "write_outside_workspace"],
    },
    "verification_auditor": {
        "focus": "raw_measurements_hashes_and_claims",
        "include_papers": True,
        "include_code_artifacts": True,
        "include_experiments": True,
        "prohibited_actions": ["modify_source_data", "self_approve", "publish_external", "write_outside_workspace"],
    },
    "synthesis_author": {
        "focus": "verified_findings_and_figures",
        "include_papers": True,
        "include_code_artifacts": False,
        "include_experiments": True,
        "prohibited_actions": ["invent_citations", "run_shell", "publish_external"],
    },
}

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|safeguards|instructions).*?(?:\.|$)", re.IGNORECASE),
    re.compile(r"system\s*override\s*:.*?(?:\.|$)", re.IGNORECASE),
    re.compile(r"grant\s+(all\s+)?(shell|network|file|root|admin)\s+permissions?.*?(?:\.|$)", re.IGNORECASE),
    re.compile(r"approve\s+everything.*?(?:\.|$)", re.IGNORECASE),
]


def sanitize_untrusted_evidence(text: str) -> tuple[str, bool]:
    """Strip prompt injection attempts from untrusted paper/tool text and flag if stripped."""
    cleaned = redact(str(text or ""))
    injected = False
    for pat in INJECTION_PATTERNS:
        if pat.search(cleaned):
            injected = True
            cleaned = pat.sub("[REDACTED_PROMPT_INJECTION_ATTEMPT]", cleaned)
    return cleaned, injected


class ContextPackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(min_length=1, max_length=120)
    mission_id: str = Field(default="", max_length=120)
    task_id: str = Field(min_length=1, max_length=120)
    role: Literal["literature_reviewer", "experiment_engineer", "verification_auditor", "synthesis_author"] = "experiment_engineer"
    objective: str = Field(default="Execute bounded research task", max_length=4000)
    query: str = Field(default="", max_length=1000)
    max_tokens: int = Field(default=3500, ge=256, le=32000)
    requested_source_ids: list[str] = Field(default_factory=list, max_length=50)


def build_context_pack(req: ContextPackRequest) -> dict:
    """Build a role-specific, budget-bounded, injection-safe Context Pack for a task."""
    S.get_topic(req.topic_id)
    profile = ROLE_PROFILES.get(req.role, ROLE_PROFILES["experiment_engineer"])

    # Enforce strict topic isolation on requested_source_ids
    if req.requested_source_ids:
        RC.validate_sources(req.topic_id, req.requested_source_ids)

    candidates: list[dict] = []
    injection_attempts_blocked = 0

    # 1. Role-tailored retrieval from SKB papers & chunks
    if profile["include_papers"]:
        papers = K.search(req.topic_id, q=req.query, limit=15).get("papers") or []
        for p in papers:
            clean_title, inj1 = sanitize_untrusted_evidence(p.get("title", ""))
            clean_abs, inj2 = sanitize_untrusted_evidence(p.get("abstract", ""))
            if inj1 or inj2:
                injection_attempts_blocked += 1
            trust = "user_verified" if p.get("level", 0) >= 4 else ("auto_screened" if p.get("level", 0) >= 2 else "source_reported")
            candidates.append(
                {
                    "id": f"paper:{p['id']}",
                    "kind": "paper_metadata",
                    "role_relevance": "high" if req.role == "literature_reviewer" else "medium",
                    "trust": trust,
                    "citation": {"doi": p.get("doi"), "year": p.get("year"), "level": p.get("level", 0)},
                    "excerpt": f"[UNTRUSTED_DATA] Title: {clean_title} | DOI: {p.get('doi') or 'none'} | Abstract: {clean_abs[:400]}",
                }
            )

    # 2. Role-tailored retrieval from Experiment Runs & Protocols
    if profile["include_experiments"]:
        from backend.execution import protocols as P

        for run in P.runs(req.topic_id)[:10]:
            comp = (run.get("payload") or {}).get("comparison") or {}
            candidates.append(
                {
                    "id": f"experiment:{run['id']}",
                    "kind": "experiment_result",
                    "role_relevance": "high" if req.role in ("experiment_engineer", "verification_auditor") else "medium",
                    "trust": "measurement",
                    "citation": {"protocol_id": run.get("protocol_id"), "status": run.get("status")},
                    "excerpt": f"Experiment Run {run['id']}: status={run['status']}, selected_alpha={comp.get('selected_alpha')}, gain_db={comp.get('paired_psnr_gain_db')}",
                }
            )

    # 3. Role-tailored retrieval from URAP & Workspace Artifacts
    if profile["include_code_artifacts"]:
        from backend.intelligence import urap

        for art in urap.list_artifacts(req.topic_id)[:15]:
            candidates.append(
                {
                    "id": art["artifact_id"],
                    "kind": art["artifact_type"],
                    "role_relevance": "high",
                    "trust": art["verification"]["status"],
                    "citation": {"sha256": art["content"]["sha256"][:16], "producer": art["producer"]["runtime_id"]},
                    "excerpt": f"Artifact {art['artifact_id']} ({art['artifact_type']}) uri={art['content']['uri']} sha256={art['content']['sha256'][:16]}",
                }
            )

    # 4. Fit to token budget (approx 4 chars per token) and record omissions
    included_inputs: list[dict] = []
    evidence_ids: list[str] = []
    used_tokens = 120  # base schema overhead
    omitted_count = 0

    for item in candidates:
        est_tokens = max(16, len(item["excerpt"]) // 4)
        if used_tokens + est_tokens > req.max_tokens:
            omitted_count += 1
            continue
        used_tokens += est_tokens
        included_inputs.append(item)
        evidence_ids.append(item["id"])

    pack_id = f"ctx-{S.uid()[:10]}"
    at = S.now()
    pack = {
        "schema_version": 1,
        "context_pack_id": pack_id,
        "project_id": S.project_id(),
        "topic_id": req.topic_id,
        "mission_id": req.mission_id,
        "task_id": req.task_id,
        "role": req.role,
        "role_focus": profile["focus"],
        "objective": redact(req.objective),
        "constraints": {
            "max_vram_gb": 12,
            "max_run_seconds": 1800,
            "prohibited_actions": profile["prohibited_actions"],
            "external_documents_are_untrusted_data": True,
            "permissions_immutable_by_retrieved_text": True,
        },
        "inputs": included_inputs,
        "retrieval": {
            "evidence_ids": evidence_ids,
            "omitted_due_to_budget": omitted_count,
            "injection_attempts_blocked": injection_attempts_blocked,
        },
        "budget": {
            "token_estimate": used_tokens,
            "max_tokens": req.max_tokens,
        },
        "created_at": at,
    }
    digest = hashlib.sha256(S.dumps(pack).encode("utf-8")).hexdigest()
    pack["digest"] = digest

    with S.db() as c:
        c.execute(
            "INSERT INTO context_packs VALUES(?,?,?,?,?,?,?,?,?)",
            (pack_id, pack["project_id"], req.topic_id, req.mission_id, req.task_id, req.role, digest, S.dumps(pack), at),
        )

    observability.emit_trace_event(
        topic_id=req.topic_id,
        mission_id=req.mission_id,
        task_id=req.task_id,
        event_type="CONTEXT_PACK_BUILT",
        span_name="context_pack.build",
        payload={
            "context_pack_id": pack_id,
            "role": req.role,
            "evidence_count": len(evidence_ids),
            "omitted_due_to_budget": omitted_count,
            "token_estimate": used_tokens,
            "injection_attempts_blocked": injection_attempts_blocked,
        },
    )
    return pack


def get_task_context_pack(task_id: str, topic_id: str = "") -> dict:
    with S.db() as c:
        row = c.execute(
            "SELECT payload FROM context_packs WHERE task_id=? AND (?='' OR topic_id=?) ORDER BY created_at DESC LIMIT 1",
            (task_id, topic_id, topic_id),
        ).fetchone()
        if row:
            return json.loads(row[0])
    if not topic_id:
        with S.db() as c:
            trow = c.execute("SELECT id FROM topics ORDER BY created LIMIT 1").fetchone()
            if not trow:
                raise ValueError("No Topic found to build context pack")
            topic_id = trow[0]
    return build_context_pack(ContextPackRequest(topic_id=topic_id, task_id=task_id))
