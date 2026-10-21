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
            "retrieval": "SQLite FTS5/BM25; vector/reranker deferred", "engine_observability": W.OBSERVABILITY}


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


class BulkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ids: list[str] = Field(min_length=1, max_length=100)
    action: str
    target_topic_id: str = ""
    note: str = Field(default="", max_length=8000)


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
                 oa: bool = False, offset: int = 0, limit: int = 25, sort: str = "relevance"):
    return await call(corpus.search, tid, q[:1000], level, state, source, year, oa, offset, limit, sort)


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
async def evidence(tid: str, q: str = ""):
    return {"evidence": await call(corpus.retrieve, tid, q[:2000])}


@router.get("/topics/{tid}/bibliography", response_class=PlainTextResponse)
async def bibliography(tid: str):
    return await call(corpus.bibliography, tid)


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
