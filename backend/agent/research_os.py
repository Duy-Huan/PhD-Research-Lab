"""Opt-in supervised lifecycle on the existing Mission worker. No second orchestrator."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import Field, model_validator
from backend.agent.mission_contracts import Contract, MissionSpec
from backend.agent import decision_ledger as L
from backend.knowledge import research_store as S


class TopicGoal(Contract):
    topic_id:str
    parent_topic_id:str=""
    goal:str=Field(min_length=1,max_length=4000)
    priority:int=Field(default=0,ge=0,le=10)
    depends_on:list[str]=Field(default_factory=list,max_length=30)


class RetrievalGrant(Contract):
    requester_topic:str
    source_topic:str


class ProjectCharter(Contract):
    goal:str=Field(min_length=1,max_length=8000)
    exclusions:list[str]=Field(default_factory=list,max_length=20)
    topics:list[TopicGoal]=Field(min_length=1,max_length=30)
    retrieval:list[RetrievalGrant]=Field(default_factory=list,max_length=60)
    permissions:list[Literal["network","workspace_write","reasoning","compute"]]=Field(default_factory=lambda:["workspace_write"])
    max_reasoning_calls:int=Field(default=3,ge=0,le=30)
    max_active_seconds:int=Field(default=3600,ge=1,le=86400)
    predecessor_id:str=""

    @model_validator(mode="after")
    def hierarchy(self):
        ids={t.topic_id for t in self.topics}
        if len(ids)!=len(self.topics):raise ValueError("Duplicate charter Topic")
        for attribute in ("parent_topic_id","depends_on"):
            pending={t.topic_id:set(filter(None,[t.parent_topic_id])) if attribute=="parent_topic_id" else set(t.depends_on) for t in self.topics};done=set()
            if any(not deps<=ids for deps in pending.values()):raise ValueError("Charter references unknown Topic")
            while pending:
                ready={k for k,v in pending.items() if v<=done}
                if not ready:raise ValueError("Cyclic Topic hierarchy/dependencies")
                done|=ready;pending={k:v for k,v in pending.items() if k not in ready}
        if any(g.requester_topic not in ids or g.source_topic not in ids for g in self.retrieval):raise ValueError("Retrieval grant outside charter")
        return self


def enabled():
    from backend.core.config import load_config
    return load_config()["research_os"]["enabled"] is True


def charters():
    with S.db() as c:return [{**dict(r),"payload":json.loads(r["payload"])} for r in c.execute("SELECT * FROM project_charters ORDER BY rowid DESC")]


def charter(cid):
    result=next((r for r in charters() if r["id"]==cid),None)
    if not result:raise ValueError("Charter not found in current project")
    return result


def create_charter(body:ProjectCharter):
    for t in body.topics:S.get_topic(t.topic_id)
    if body.predecessor_id:charter(body.predecessor_id)
    payload=body.model_dump(mode="json");cid=S.uid();digest=L.digest(payload)
    with S.db() as c:
        c.execute("INSERT INTO project_charters VALUES(?,?,?,?)",(cid,digest,S.dumps(payload),S.now()))
        c.execute("INSERT INTO charter_usage(charter_id) VALUES(?)",(cid,))
        for t in body.topics:L.append(c,t.topic_id,cid,"charter.created",{"digest":digest,"goal":body.goal})
    return charter(cid)


def validate(spec:MissionSpec):
    from backend.agent import teams
    teams.validate(spec)
    from backend.agent import collaboration
    collaboration.validate(spec)
    control=spec.control
    if not control:return
    from backend.core.config import PROVIDERS
    if control.end_date<=datetime.now(timezone.utc):raise ValueError("Mission end date has passed")
    for task in spec.tasks:
        if not {task.preferred_engine,*task.fallback_engines}<=set(control.allowed_engines):raise ValueError("Engine outside approved allowlist")
        if "app" in [task.preferred_engine,*task.fallback_engines]:
            if not control.app_model:raise ValueError("Supervised app reasoning requires an explicit model")
            if control.app_backend not in {"local","ollama",*PROVIDERS}:raise ValueError("Unknown fixed application backend")
            if control.app_backend not in ("local","ollama") and not control.allow_api_billing:raise ValueError("API billing is disabled in this mission")
    if control.charter_id:
        ch=charter(control.charter_id)
        if ch["digest"]!=control.charter_digest or ch["digest"]!=L.digest(ch["payload"]):raise ValueError("Charter digest mismatch")
        if spec.topic_id not in {t["topic_id"] for t in ch["payload"]["topics"]}:raise ValueError("Mission Topic outside charter")
        if not set(spec.permissions)<=set(ch["payload"]["permissions"]):raise ValueError("Mission expands charter permissions")
    elif control.charter_digest:raise ValueError("Charter ID required")
    if control.predecessor_id:
        from backend.agent.missions import get
        previous=get(control.predecessor_id,spec.topic_id)
        if previous["status"] not in ("draft","awaiting_approval","paused","cancelled","failed","completed"):
            raise ValueError("Pause the prior mission before proposing a revision")


def request_approval(tid,mid):
    from backend.agent import missions as M
    with S.db() as c:
        m=M._get(c,mid,tid)
        if not m["payload"]["spec"].get("control") or m["status"]!="draft":raise ValueError("Only a supervised draft can request approval")
        c.execute("UPDATE missions SET status='awaiting_approval',updated=? WHERE id=?",(S.now(),mid))
        L.append(c,tid,mid,"mission.approval_requested",{})
    return M.get(mid,tid)


def pause(tid,mid,note):
    from backend.agent import missions as M
    if not note.strip():raise ValueError("Pause note required")
    with S.db() as c:
        m=M._get(c,mid,tid)
        if m["status"] in ("cancelled","completed","failed","interrupted"):raise ValueError("Cannot pause this terminal/uncertain mission")
        p=m["payload"];p["blocking_reason"]="Researcher pause: "+note[:500]
        c.execute("UPDATE missions SET status='paused',payload=? WHERE id=?",(S.dumps(p),mid))
        L.append(c,tid,mid,"mission.paused",{"by":"researcher","note":note})
    return M.get(mid,tid)


def review(tid,mid,note):
    from backend.agent import missions as M
    if not note.strip():raise ValueError("Human review note required")
    with S.db() as c:
        m=M._get(c,mid,tid)
        if m["status"]!="awaiting_review":raise ValueError("Mission is not awaiting review")
        from backend.agent.collaboration import review_blocker
        blocked=review_blocker(c,m)
        if blocked:raise ValueError(blocked)
        c.execute("UPDATE missions SET status='completed',updated=? WHERE id=?",(S.now(),mid))
        L.append(c,tid,mid,"mission.reviewed",{"by":"researcher","note":note,"scientific_claims_not_implicitly_approved":True})
    return M.get(mid,tid)


def breaker_key(m,task):
    control=m["payload"]["spec"].get("control") or {}
    return "app:"+control.get("app_backend","configured") if task.preferred_engine=="app" else task.preferred_engine


def trip(c,m,key,reason):
    from backend.core.telemetry import redact
    until=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()
    data={"reason":redact(reason)[:500],"remaining_quota":None,"by":"observed_provider_failure"}
    c.execute("INSERT INTO provider_breakers VALUES(?,?,?) ON CONFLICT(provider) DO UPDATE SET until_at=excluded.until_at,payload=excluded.payload",(key,until,S.dumps(data)))
    L.append(c,m["topic_id"],m["id"],"provider.cooldown",{"provider":key,"until":until,**data})


def gate(c,m,task=None):
    """Return a persistent blocking reason. Called again in the admission transaction."""
    p=m.get("payload") or {}
    spec=p.get("spec") or {}
    control=spec.get("control")
    if not control:return ""
    now=datetime.now(timezone.utc)
    if not enabled():return "Research OS is disabled"
    if spec.get("team"):
        from backend.agent import teams
        if not teams.enabled():return "Team execution is disabled"
    from backend.agent import collaboration
    blocked=collaboration.gate(c,m,task)
    if blocked:return blocked
    if now>=datetime.fromisoformat(control["end_date"]):return "Mission end date reached"
    if control.get("not_before") and now<datetime.fromisoformat(control["not_before"]):return "Scheduled for "+control["not_before"]
    if p.get("started_at") and (now-datetime.fromisoformat(p["started_at"])).total_seconds()>=control["max_wall_seconds"]:return "Mission wall-time budget exhausted"
    if control.get("charter_id"):
        row=c.execute("SELECT ch.payload,u.reasoning_calls,u.active_seconds FROM project_charters ch JOIN charter_usage u ON u.charter_id=ch.id WHERE ch.id=?",(control["charter_id"],)).fetchone()
        if not row:return "Charter unavailable"
        charter_spec=json.loads(row["payload"])
        topic_goal=next(t for t in charter_spec["topics"] if t["topic_id"]==m["topic_id"])
        for dependency in topic_goal["depends_on"]:
            completed=c.execute("SELECT 1 FROM missions WHERE topic_id=? AND status='completed' AND json_extract(payload,'$.spec.control.charter_id')=? LIMIT 1",(dependency,control["charter_id"])).fetchone()
            if not completed:return "Charter Topic dependency awaiting completed human review: "+dependency
        if row["active_seconds"]>=charter_spec["max_active_seconds"]:return "Aggregate charter time budget exhausted"
        if task and task.capability=="paper.compare" and row["reasoning_calls"]>=charter_spec["max_reasoning_calls"]:return "Aggregate charter reasoning budget exhausted"
    if task and task.capability=="paper.compare":
        key=breaker_key(m,task);row=c.execute("SELECT until_at FROM provider_breakers WHERE provider=?",(key,)).fetchone()
        if row and now<datetime.fromisoformat(row[0]):return "Provider cooldown until "+row[0]
    return ""


def charge(c,m,*,reasoning=0,seconds=0):
    control=m["payload"]["spec"].get("control") or {}
    if control.get("charter_id"):c.execute("UPDATE charter_usage SET reasoning_calls=reasoning_calls+?,active_seconds=active_seconds+? WHERE charter_id=?",(reasoning,seconds,control["charter_id"]))


def time_remaining(c,m):
    control=m["payload"]["spec"].get("control") or {};remaining=m["payload"]["spec"]["limits"]["max_seconds"]-m["payload"]["active_seconds"]
    if control:
        remaining=min(remaining,(datetime.fromisoformat(control["end_date"])-datetime.now(timezone.utc)).total_seconds())
        if m["payload"].get("started_at"):remaining=min(remaining,control["max_wall_seconds"]-(datetime.now(timezone.utc)-datetime.fromisoformat(m["payload"]["started_at"])).total_seconds())
        if control.get("charter_id"):
            row=c.execute("SELECT ch.payload,u.active_seconds FROM project_charters ch JOIN charter_usage u ON u.charter_id=ch.id WHERE ch.id=?",(control["charter_id"],)).fetchone()
            remaining=min(remaining,json.loads(row[0])["max_active_seconds"]-row[1])
    return max(0.001,remaining)


async def fixed_reasoning(m,system,user):
    from backend.core.config import load_config
    from backend.providers import models
    control=m["payload"]["spec"]["control"];backend=control["app_backend"];cfg=load_config()
    output_tokens=(m["payload"]["spec"].get("autonomy") or {}).get("max_output_tokens",3000)
    if backend in ("local","ollama"):
        token = models.REASONING.set("off") if m["payload"]["spec"].get("autonomy") else None
        try:
            text=await models.local_chat(cfg,system,[{"role":"user","content":user}],output_tokens,0,backend,control["app_model"],"interactive")
        finally:
            if token is not None:
                models.REASONING.reset(token)
    elif control["allow_api_billing"]:
        text=await models.cloud_chat(cfg,backend,system,[{"role":"user","content":user}],output_tokens,0,control["app_model"])
    else:raise ValueError("Hidden API billing refused")
    return {"text":text,"engine":backend,"model":control["app_model"],"usage":None,"fallback":False}


def report(tid,mid):
    from backend.agent import missions as M
    from backend.knowledge import corpus, governance
    from backend.execution import protocols
    from backend.research_engines import workspaces
    m=M.get(mid,tid);control=m["payload"]["spec"].get("control") or {};related=[]
    if control.get("charter_id"):
        ch=charter(control["charter_id"])
        allowed={g["source_topic"] for g in ch["payload"]["retrieval"] if g["requester_topic"]==tid}
        related=[{"topic_id":t,"title":S.get_topic(t)["title"],"papers":corpus.all_papers(t)} for t in sorted(allowed)]
    bundle={"project_id":S.project_id(),"topic_id":tid,"mission":m,"related_topics":related,"papers":corpus.all_papers(tid),"experiments":protocols.runs(tid),"claims":governance.export_markdown(tid),"bibliography":corpus.bibliography(tid),"workspaces":workspaces.list_workspaces(tid),"audit":L.export(tid),"limitations":["Scientific review is independent of mission completion","Private native session visibility is partial; sync uses exposed files","Token/currency cost and remaining subscription quota are unknown unless the provider reports them","No paper draft or external dissemination is generated"]}
    return bundle


def artifact(tid,mid,task_id,index):
    from backend.agent import missions as M
    return checked_artifact(M.get(mid,tid),task_id,index)


def checked_artifact(m,task_id,index):
    """Check an already-scoped mission snapshot without opening a nested transaction."""
    task=next((t for t in m["tasks"] if t["id"]==task_id),None)
    if not task or task["status"]!="completed":raise ValueError("Completed task artifact required")
    refs=task["payload"].get("result",{}).get("artifacts",[])
    if not 0<=index<len(refs):raise ValueError("Artifact not found")
    ref=refs[index];from pathlib import Path
    path=Path(ref["path"])
    if not path.is_relative_to(S.store_dir()):raise ValueError("Artifact outside research store")
    path=S.safe_child(S.store_dir(),*path.relative_to(S.store_dir()).parts)
    if path.stat().st_size!=ref["bytes"] or ref["bytes"]>m["payload"]["spec"]["limits"]["max_artifact_mb"]*1024*1024:raise ValueError("Artifact size/budget mismatch")
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ref["sha256"]:raise ValueError("Artifact checksum mismatch")
    return path
