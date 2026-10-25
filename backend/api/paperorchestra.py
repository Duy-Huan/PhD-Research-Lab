"""PaperOrchestra API Endpoints for PhD Research Lab (v6.4.3).

Exposes:
- Engine health and isolated CLI / harness status.
- Versioned writing artifact inspection and comparison.
- On-demand verification quality gates (citations, figures, experimental provenance, LaTeX).
- Independent peer-review scoring and critique.
- L2-L4 workflow planning and dispatch.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from backend.api.common import call
from backend.core.config import data_dir, project_scope
from backend.research_engines import registry
from backend.research_engines.paperorchestra.artifact_store import (
    get_artifact,
    list_artifacts,
)
from backend.research_engines.paperorchestra.contracts import (
    IndependentReviewReport,
    PaperOrchestraConfig,
    VerificationQualityReport,
    WritingArtifact,
)
from backend.research_engines.paperorchestra.modes import (
    create_l2_paper_mission,
    create_l3_team_mission,
    create_l4_research_to_paper_mission,
)
from backend.research_engines.paperorchestra.quality_gates import (
    compile_and_preview_latex,
    evaluate_quality_gates,
    run_independent_review,
    verify_citations,
    verify_experiment_provenance,
    verify_figure_sources,
)


async def bind_project():
    with project_scope(data_dir()):
        yield


router = APIRouter(prefix="/api/paperorchestra", tags=["paperorchestra"], dependencies=[Depends(bind_project)])


class VerifyCitationsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(default="", max_length=120)
    text: str = Field(min_length=1, max_length=500000)


class VerifyFiguresBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(default="", max_length=120)
    text: str = Field(min_length=1, max_length=500000)


class VerifyProvenanceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(default="", max_length=120)
    text: str = Field(min_length=1, max_length=500000)


class QualityGatesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(default="", max_length=120)
    sections: dict[str, str] = Field(default_factory=dict)


class IndependentReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(default="", max_length=120)
    text: str = Field(min_length=1, max_length=500000)
    target_venue: str = Field(default="IEEE / ACM", max_length=100)


class PlanMissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(min_length=1, max_length=120)
    level: Literal["L2", "L3", "L4"] = "L2"
    objective: str = Field(min_length=1, max_length=8000)
    capability: str = Field(default="paperorchestra.outline", max_length=80)
    section: str = Field(default="abstract", max_length=80)
    paper_ids: list[str] = Field(default_factory=list, max_length=50)
    protocol_id: str = ""
    protocol_digest: str = ""
    approval_nonce: str = ""
    style: str = "IEEE"
    target_venue: str = ""


@router.get("/health")
async def health():
    engine = registry.get("paperorchestra")
    return await run_in_threadpool(engine.health)


@router.get("/artifacts/{topic_id}")
async def get_artifacts(topic_id: str, workflow_id: str = ""):
    arts = await run_in_threadpool(list_artifacts, topic_id, workflow_id)
    return {"artifacts": [a.model_dump(mode="json") for a in arts]}


@router.get("/artifacts/{topic_id}/{artifact_id}")
async def get_single_artifact(topic_id: str, artifact_id: str):
    art = await run_in_threadpool(get_artifact, artifact_id)
    if not art:
        raise HTTPException(status_code=404, detail="Writing artifact not found")
    return art.model_dump(mode="json")


@router.post("/verify-citations")
async def api_verify_citations(body: VerifyCitationsBody):
    res = await run_in_threadpool(verify_citations, body.topic_id, body.text)
    return res.model_dump(mode="json")


@router.post("/verify-figures")
async def api_verify_figures(body: VerifyFiguresBody):
    res = await run_in_threadpool(verify_figure_sources, body.topic_id, body.text)
    return res.model_dump(mode="json")


@router.post("/verify-provenance")
async def api_verify_provenance(body: VerifyProvenanceBody):
    res = await run_in_threadpool(verify_experiment_provenance, body.topic_id, body.text)
    return res.model_dump(mode="json")


@router.post("/quality-gates")
async def api_quality_gates(body: QualityGatesBody):
    sections = body.sections
    if not sections:
        from backend.paper.writer import load_project
        p = load_project()
        sections = p.get("sections", {})
    res = await run_in_threadpool(evaluate_quality_gates, body.topic_id, sections)
    return res.model_dump(mode="json")


@router.post("/independent-review")
async def api_independent_review(body: IndependentReviewBody):
    res = await run_in_threadpool(run_independent_review, body.topic_id, body.text, body.target_venue)
    return res.model_dump(mode="json")


@router.post("/plan-mission")
async def api_plan_mission(body: PlanMissionBody):
    if body.level == "L2":
        spec = create_l2_paper_mission(
            topic_id=body.topic_id,
            objective=body.objective,
            capability=body.capability,
            args={"section": body.section},
            paper_ids=body.paper_ids,
        )
    elif body.level == "L3":
        spec = create_l3_team_mission(
            topic_id=body.topic_id,
            objective=body.objective,
            paper_ids=body.paper_ids,
            style=body.style,
            target_venue=body.target_venue,
        )
    elif body.level == "L4":
        spec = create_l4_research_to_paper_mission(
            topic_id=body.topic_id,
            objective=body.objective,
            paper_ids=body.paper_ids,
            protocol_id=body.protocol_id,
            protocol_digest=body.protocol_digest,
            approval_nonce=body.approval_nonce,
            style=body.style,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported level: {body.level}")

    return {"spec": spec.model_dump(mode="json")}

