"""Deterministic Topic/SKB/workspace actions, isolated from agent execution."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.api.common import call
from backend.knowledge import corpus, research_context as C, research_jobs as J, research_store as S
from backend.research_engines import workspaces as W
from backend.core.config import data_dir, project_scope


async def bind_project():
    # A project switch in another request cannot redirect an in-flight research mutation.
    with project_scope(data_dir()):
        yield


router = APIRouter(prefix="/api/research", tags=["research-workspace"], dependencies=[Depends(bind_project)])

from backend.agent import missions
from backend.agent.mission_contracts import MissionSpec
from backend.execution import protocols
from backend.execution.protocol_contracts import ExperimentProtocol
from backend.knowledge import governance as G
from backend.agent import research_os as OS


class OSSettings(G.Contract):
    enabled:bool
    team_enabled:bool|None=None
    multi_team_enabled:bool|None=None


class ReviewNote(G.Contract):
    note:str=Field(min_length=1,max_length=4000)


@router.get("/os-settings")
async def os_settings():
    from backend.agent import teams,collaboration
    return {"enabled":OS.enabled(),"team_enabled":teams.enabled(),"multi_team_enabled":collaboration.enabled(),"experimental":True,"max_parallel_tasks":1}


@router.put("/os-settings")
async def os_settings_update(body:OSSettings):
    from backend.core.config import save_config
    await call(save_config,{"research_os":{k:v for k,v in body.model_dump(exclude_unset=True).items() if k!="schema_version" and v is not None}})
    return await os_settings()


@router.get("/charters")
async def charter_list():return {"charters":await call(OS.charters)}


@router.post("/charters")
async def charter_create(body:OS.ProjectCharter):return await call(OS.create_charter,body)


@router.post("/topics/{tid}/missions/{mid}/request-approval")
async def mission_request(tid:str,mid:str):return await call(OS.request_approval,tid,mid)


@router.post("/topics/{tid}/missions/{mid}/pause")
async def mission_pause(tid:str,mid:str,body:ReviewNote):return await call(OS.pause,tid,mid,body.note)


@router.post("/topics/{tid}/missions/{mid}/review")
async def mission_review(tid:str,mid:str,body:ReviewNote):return await call(OS.review,tid,mid,body.note)


@router.get("/topics/{tid}/missions/{mid}/report")
async def mission_bundle(tid:str,mid:str):return await call(OS.report,tid,mid)


@router.get("/topics/{tid}/missions/{mid}/artifacts/{task_id}/{index}")
async def mission_artifact(tid:str,mid:str,task_id:str,index:int):
    return FileResponse(await call(OS.artifact,tid,mid,task_id,index),media_type="application/octet-stream")


@router.get("/team-capabilities")
async def team_capabilities():
    from backend.agent.teams import registry
    return await call(registry)


@router.post("/teams/propose")
async def team_propose(body:MissionSpec,mode:str="adaptive"):
    from backend.agent.teams import propose
    proposal=await call(propose,body,mode)
    await call(OS.validate,proposal)
    return {"spec":proposal.model_dump(mode="json"),"execution_started":False}


@router.get("/topics/{tid}/missions/{mid}/team")
async def team_monitor(tid:str,mid:str):
    from backend.agent.teams import monitor
    return await call(monitor,tid,mid)


class Reassignment(ReviewNote):
    task_id:str
    engine:str


@router.post("/topics/{tid}/missions/{mid}/replan")
async def team_replan(tid:str,mid:str,body:Reassignment):
    from backend.agent.teams import replan
    return await call(replan,tid,mid,body.task_id,body.engine,body.note)


@router.post("/workstreams/propose")
async def workstream_propose(body:MissionSpec,max_teams:int=4):
    from backend.agent import collaboration as CO
    proposal=await call(CO.partition,body,max_teams)
    await call(OS.validate,proposal)
    return {"spec":proposal.model_dump(mode="json"),"execution_started":False}


@router.get("/topics/{tid}/missions/{mid}/workstreams")
async def workstream_monitor(tid:str,mid:str):
    from backend.agent import collaboration as CO
    return await call(CO.monitor,tid,mid)


class HandoffRequest(G.Contract):
    source_task:str
    target_task:str


class ReceiptRequest(G.Contract):
    receiver_team:str


@router.post("/topics/{tid}/missions/{mid}/handoffs")
async def workstream_publish(tid:str,mid:str,body:HandoffRequest):
    from backend.agent import collaboration as CO
    return await call(CO.publish,tid,mid,body.source_task,body.target_task)


@router.post("/topics/{tid}/missions/{mid}/handoffs/{hid}/ack")
async def workstream_receive(tid:str,mid:str,hid:str,body:ReceiptRequest):
    from backend.agent import collaboration as CO
    return await call(CO.receive,tid,mid,hid,body.receiver_team)


class CanonicalRequest(ReviewNote):
    team_id:str
    key:str=Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    source_task:str
    artifact_index:int=Field(default=0,ge=0)
    expected_revision:int=Field(ge=0)


@router.post("/topics/{tid}/missions/{mid}/outputs")
async def workstream_output(tid:str,mid:str,body:CanonicalRequest):
    from backend.agent import collaboration as CO
    return await call(CO.canonical,tid,mid,body.team_id,body.key,body.source_task,body.artifact_index,body.expected_revision,body.note)


class DisputeRequest(ReviewNote):
    team_id:str
    claim_ids:list[str]=Field(default_factory=list,max_length=10)


@router.post("/topics/{tid}/missions/{mid}/disputes")
async def workstream_dispute(tid:str,mid:str,body:DisputeRequest):
    from backend.agent import collaboration as CO
    return await call(CO.dispute,tid,mid,body.team_id,body.note,body.claim_ids)


class DisputeResolution(ReviewNote):
    expected_revision:int=Field(ge=1)


@router.post("/topics/{tid}/missions/{mid}/disputes/{did}/resolve")
async def workstream_resolve(tid:str,mid:str,did:str,body:DisputeResolution):
    from backend.agent import collaboration as CO
    return await call(CO.resolve,tid,mid,did,body.expected_revision,body.note)


class FindingRequest(G.ClaimInput):
    team_id:str


@router.post("/topics/{tid}/missions/{mid}/findings")
async def workstream_finding(tid:str,mid:str,body:FindingRequest):
    from backend.agent import collaboration as CO
    return await call(CO.finding,tid,mid,body.team_id,G.ClaimInput.model_validate(body.model_dump(exclude={"team_id"})))


@router.get("/topics/{tid}/claims")
async def claims(tid:str):return {"claims":await call(G.listing,tid)}


@router.post("/topics/{tid}/claims")
async def claim_create(tid:str,body:G.ClaimInput,parent_id:str=""):
    return await call(G.create,tid,body,parent_id)


@router.post("/topics/{tid}/claims/{cid}/check")
async def claim_check(tid:str,cid:str):return await call(G.evaluate,tid,cid)


class ClaimDecision(G.Contract):
    action:str
    note:str=Field(min_length=1,max_length=8000)


@router.post("/topics/{tid}/claims/{cid}/decision")
async def claim_decide(tid:str,cid:str,body:ClaimDecision):return await call(G.decide,tid,cid,body.action,body.note)


@router.post("/topics/{tid}/citations/resolve")
async def citation_resolve(tid:str,body:dict=Body(...)):
    if body.get("allow_network") is not True:raise HTTPException(400,"Explicit network authorization required")
    try:return await G.resolve_citation(tid,str(body.get("doi") or ""))
    except Exception as exc:raise HTTPException(400,"Citation unresolved: "+type(exc).__name__)


@router.get("/topics/{tid}/audit")
async def audit(tid:str):
    from backend.agent.decision_ledger import export
    return await call(export,tid)


@router.get("/topics/{tid}/claims/export",response_class=PlainTextResponse)
async def claim_export(tid:str):return await call(G.export_markdown,tid)


@router.get("/topics/{tid}/prior-art")
async def prior_art(tid:str,q:str=""):return await call(G.prior_art,tid,q[:2000])


@router.get("/topics/{tid}/experiments/{rid}/verification")
async def experiment_verification(tid:str,rid:str):
    from backend.knowledge.verification import verify_run
    return await call(verify_run,tid,rid)


@router.get("/topics/{tid}/protocols")
async def protocol_list(tid:str):return {"protocols":await call(protocols.listing,tid),"runs":await call(protocols.runs,tid)}


@router.post("/topics/{tid}/protocols")
async def protocol_create(tid:str,body:ExperimentProtocol,parent_id:str=""):
    if tid!=body.topic_id:raise HTTPException(400,"Topic mismatch")
    return await call(protocols.create,body,parent_id)


@router.post("/topics/{tid}/protocols/{pid}/approve")
async def protocol_approve(tid:str,pid:str,body:dict=Body(...)):
    return await call(protocols.approve,tid,pid,str(body.get("digest") or ""),str(body.get("note") or ""))


@router.post("/topics/{tid}/protocols/{pid}/mission")
async def protocol_mission(tid:str,pid:str):return await call(protocols.mission_draft,tid,pid)


@router.get("/mission-capabilities")
async def mission_capabilities():
    from backend.agent.capabilities import catalog
    return {"capabilities":catalog(),"max_concurrency":1,"automatic_delegation":False}


@router.get("/topics/{tid}/missions")
async def mission_list(tid: str):
    return {"missions":await call(missions.listing,tid)}


@router.post("/topics/{tid}/missions")
async def mission_create(tid: str, body: MissionSpec):
    if tid!=body.topic_id:raise HTTPException(400,"Topic mismatch")
    return await call(missions.create,body)


@router.post("/topics/{tid}/missions/plan")
async def mission_plan(tid: str, body: dict = Body(...)):
    await call(S.get_topic,tid)
    if body.get("allow_reasoning") is not True:raise HTTPException(400,"AI planning requires explicit reasoning/network permission")
    from backend.providers.models import call_agent, extract_json
    from backend.agent.capabilities import catalog
    import json
    objective=str(body.get("objective") or "").strip()[:8000]
    if not objective:raise HTTPException(400,"Objective required")
    answer=await call_agent("research","Return a JSON MissionSpec draft only. Never claim approval. Do not invent paper IDs. Schema: "+json.dumps(MissionSpec.model_json_schema())+" Capabilities: "+json.dumps(catalog()),objective,max_tokens=4000,temperature=0)
    try:
        plan=extract_json(answer["text"]);plan["topic_id"]=tid;plan["parent_mission_id"]=""
        return await call(missions.create,MissionSpec.model_validate(plan))
    except ValueError as exc:raise HTTPException(400,"Planner draft rejected: "+str(exc)[:500])


@router.post("/topics/{tid}/missions/{mid}/approve")
async def mission_approve(tid: str, mid: str, body: dict = Body(...)):
    return await call(missions.approve,tid,mid,str(body.get("plan_digest") or ""),str(body.get("note") or ""),int(body.get("expires_minutes",60)))


@router.post("/topics/{tid}/missions/{mid}/cancel")
async def mission_cancel(tid: str, mid: str):
    return await call(missions.cancel,tid,mid)


@router.post("/topics/{tid}/missions/{mid}/retry")
async def mission_retry(tid: str, mid: str, body: dict = Body(...)):
    return await call(missions.retry,tid,mid,str(body.get("task_id") or ""),str(body.get("reconcile_note") or ""))


@router.get("/capabilities")
async def capabilities():
    from backend.plugins.local_research import capabilities
    from backend.agent.ui_actions import catalog
    return {"plugins": await call(capabilities), "actions": catalog(), "core_requires_paid_llm": False,
            "retrieval": "SQLite FTS5/BM25 + configured local vectors, reciprocal-rank fusion; hashing fallback is lexical, not neural; no external reranker", "engine_observability": W.OBSERVABILITY}


@router.get("/sources")
async def source_catalog():
    from backend.knowledge.sources import PROVIDER_IDS
    from backend.knowledge.source_packs import catalog
    return {"providers": list(PROVIDER_IDS), "packs": catalog(),
            "priority": "Topic sources are ordered and explicitly enabled; four core providers remain the default"}


@router.post("/topics/{tid}/zotero/import")
async def zotero_import(tid: str, file: UploadFile = File(...)):
    import json
    from backend.plugins.local_research import import_zotero
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "Zotero JSON exceeds 5 MB")
    try:
        records = json.loads(raw)
        if isinstance(records, dict):
            records = records.get("items")
    except ValueError:
        raise HTTPException(400, "Invalid Zotero/CSL JSON")
    return await call(import_zotero, tid, records)


class ZoteroSyncInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_network: bool = False
    start: int = Field(default=0, ge=0, le=1000000)
    max_items: int = Field(default=100, ge=1, le=1000)


@router.post("/topics/{tid}/zotero/sync")
async def zotero_sync(tid: str, body: ZoteroSyncInput):
    from backend.plugins.local_research import sync_zotero
    try:
        return await sync_zotero(tid, **body.model_dump())
    except Exception as exc:
        import httpx
        if isinstance(exc, httpx.HTTPError):
            raise HTTPException(400, "Local Zotero API is not reachable; open Zotero and enable permitted local API access")
        if isinstance(exc, ValueError):
            raise HTTPException(400, str(exc))
        raise


class BulkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ids: list[str] = Field(min_length=1, max_length=100)
    action: str
    target_topic_id: str = ""
    note: str = Field(default="", max_length=8000)
    tags: list[str] = Field(default_factory=list, max_length=30)


@router.get("/topics")
async def topics():
    profiles = await call(S.topics)
    return {"project_id": await call(S.project_id), "topics": profiles,
            "schedules": {t["id"]: await call(J.schedule_status, t) for t in profiles}}


@router.post("/topics")
async def create_topic(body: S.TopicInput):
    return await call(S.save_topic, body)


@router.get("/topics/{tid}")
async def topic(tid: str):
    return await call(S.get_topic, tid)


@router.put("/topics/{tid}")
async def update_topic(tid: str, body: S.TopicInput):
    return await call(S.save_topic, body, tid)


@router.get("/topics/{tid}/papers")
async def papers(tid: str, q: str = "", level: int = -1, state: str = "", source: str = "", year: int = 0,
                 oa: bool = False, offset: int = 0, limit: int = 25, sort: str = "relevance",
                 max_year: int = 0, venue: str = "", publication_type: str = "", tag: str = "", pdf: bool | None = None, flag: str = ""):
    return await call(corpus.search, tid, q[:1000], level, state, source, year, oa, offset, limit, sort,
                      max_year=max_year, venue=venue[:500], publication_type=publication_type[:100], tag=tag[:80], pdf=pdf, flag=flag[:120])


@router.post("/topics/{tid}/papers/import")
async def import_papers(tid: str, body: dict = Body(...)):
    records = body.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= 1000 or any(not isinstance(r, dict) for r in records):
        raise HTTPException(400, "Provide 1–1000 metadata records")
    return await call(corpus.ingest, tid, records)


@router.post("/topics/{tid}/papers/import-library")
async def import_library(tid: str):
    return await call(corpus.import_legacy, tid)


@router.post("/topics/{tid}/papers/bulk")
async def bulk(tid: str, body: BulkInput):
    if body.action in ("tag", "untag"):
        return await call(corpus.tag_papers, tid, body.paper_ids, body.tags, body.action == "untag")
    if body.action == "associate":
        return await call(corpus.associate, tid, body.target_topic_id, body.paper_ids)
    if body.action in ("download", "index"):
        return await call(J.enqueue, tid, body.action, {"paper_ids": body.paper_ids})
    return await call(corpus.curate, tid, body.paper_ids, body.action, body.note)


@router.get("/topics/{tid}/papers/{pid}")
async def paper(tid: str, pid: str):
    return await call(corpus.paper, tid, pid)


@router.get("/topics/{tid}/papers/{pid}/pdf/{vid}")
async def pdf(tid: str, pid: str, vid: str):
    p = await call(corpus.paper, tid, pid)
    v = next((v for v in p["versions"] if v["id"] == vid), None)
    if not v or not v["document"]:
        raise HTTPException(404, "PDF unavailable for this version")
    path = corpus.object_path(v["document"]["sha256"])
    if not path.is_file():
        raise HTTPException(404, "Stored PDF is unavailable; retry download")
    return FileResponse(path, media_type="application/pdf", content_disposition_type="inline")


@router.get("/topics/{tid}/evidence")
async def evidence(tid: str, q: str = "", paper_id: str = "", limit: int = 10):
    return {"evidence": await call(corpus.retrieve, tid, q[:2000], limit, paper_id)}


@router.get("/topics/{tid}/bibliography", response_class=PlainTextResponse)
async def bibliography(tid: str):
    return await call(corpus.bibliography, tid)


@router.get("/topics/{tid}/citation-graph")
async def citation_graph(tid: str):
    return await call(corpus.citation_graph, tid)


@router.post("/topics/{tid}/discover")
async def discover(tid: str, body: dict = Body(default={})):
    return await call(J.enqueue, tid, "discover", {"dry_run": bool(body.get("dry_run", False))})


@router.get("/jobs")
async def jobs(topic_id: str = ""):
    return {"jobs": await call(J.list_jobs, topic_id)}


@router.post("/jobs/{jid}/cancel")
async def cancel(jid: str):
    return await call(J.cancel, jid)


@router.post("/jobs/{jid}/retry")
async def retry(jid: str):
    return await call(J.retry, jid)


@router.get("/topics/{tid}/workspaces")
async def workspaces(tid: str):
    return {"workspaces": await call(W.list_workspaces, tid)}


@router.post("/topics/{tid}/workspaces")
async def link_workspace(tid: str, body: W.WorkspaceInput):
    return await call(W.link, tid, body)


@router.post("/workspaces/{wid}/open")
async def open_workspace(wid: str):
    return await call(W.open_workspace, wid)


@router.put("/workspaces/{wid}")
async def relink_workspace(wid: str, body: W.WorkspaceInput):
    return await call(W.relink, wid, body)


@router.post("/workspaces/{wid}/sync")
async def sync_workspace(wid: str):
    w = await call(W.get, wid)
    return await call(J.enqueue, w["topic_id"], "sync", {"workspace_id": wid})


@router.get("/workspaces/{wid}/sync-status")
async def sync_status(wid: str):
    return await call(W.get, wid)


@router.get("/topics/{tid}/artifacts")
async def artifacts(tid: str, workspace_id: str = "", history: bool = False):
    return {"artifacts": await call(W.artifacts, tid, workspace_id, history)}


@router.get("/topics/{tid}/artifacts/{aid}")
async def artifact_detail(tid: str, aid: str):
    return await call(W.artifact_text, tid, aid)


@router.get("/topics/{tid}/provenance")
async def provenance(tid: str, workspace_id: str = "", kind: str = "", limit: int = 100):
    return {"events": await call(S.timeline, tid, limit, workspace_id, kind)}


@router.get("/topics/{tid}/findings")
async def findings(tid: str):
    return {"findings": await call(C.findings, tid)}


@router.post("/topics/{tid}/findings")
async def propose_finding(tid: str, body: dict = Body(...)):
    return await call(C.finding, tid, str(body.get("text") or ""), body.get("source_evidence_ids") or [])


@router.post("/topics/{tid}/findings/{fid}/review")
async def review_finding(tid: str, fid: str, body: dict = Body(...)):
    if not isinstance(body.get("approve"), bool):
        raise HTTPException(400, "approve must be an explicit boolean")
    return await call(C.review_finding, tid, fid, body["approve"], str(body.get("note") or ""))


@router.get("/topics/{tid}/research-state")
async def state(tid: str):
    return {"topic": await call(S.get_topic, tid), "papers": (await call(corpus.search, tid))["total"],
            "workspaces": await call(W.list_workspaces, tid), "jobs": await call(J.list_jobs, tid),
            "findings": await call(C.findings, tid), "observability": W.OBSERVABILITY}
