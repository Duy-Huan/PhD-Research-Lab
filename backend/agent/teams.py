"""v6.1 compatibility/v6.2 logical teams over existing Mission tasks and admissions."""
import hashlib
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from backend.agent import capabilities as C,decision_ledger as L
from backend.agent.mission_contracts import MissionSpec,TeamPlan,AgentRole,TaskAssignment,TaskEnvelope,VerificationResult
from backend.knowledge import research_store as S


def enabled():
    from backend.core.config import load_config
    return load_config()["research_os"]["team_enabled"] is True


def validate(spec):
    team=spec.team
    if not team:return
    if not spec.control:raise ValueError("Team execution requires a supervised mission brief")
    agents={a.id:a for a in team.agents};assignments={a.task_id:a for a in team.assignments};tasks={t.id:t for t in spec.tasks}
    if len(agents)!=len(team.agents) or len(agents)>team.max_agents:raise ValueError("Duplicate role or agent cap exceeded")
    if len(assignments)!=len(team.assignments) or set(assignments)!=set(tasks):raise ValueError("Exactly one owner assignment per task is required")
    if team.generation>team.max_replans:raise ValueError("Replan generation exhausted")
    for role in agents.values():
        if not set(role.permissions)<=set(spec.permissions) or not set(role.engines)<=set(spec.control.allowed_engines):raise ValueError("Role cannot expand mission authority")
        if not set(role.capabilities)<=set(C.INPUTS):raise ValueError("Role claims unregistered capabilities")
    for tid,a in assignments.items():
        if a.owner not in agents:raise ValueError("Unknown task owner")
        task=tasks[tid];role=agents[a.owner];meta=C.META.get(task.capability)
        if not meta or task.capability not in role.capabilities or not set(meta[2])<=set(role.permissions) or not {task.preferred_engine,*task.fallback_engines}<=set(role.engines):raise ValueError("Owner lacks task capability, engine or permissions")
        if a.verifier:
            if a.verifier==a.owner or a.verifier not in agents:raise ValueError("Independent verifier must be a different known role")
            if not any(t.capability in ("experiment.verify","artifact.verify") and t.args.get("from_task")==tid and assignments[t.id].owner==a.verifier and tid in t.depends_on for t in tasks.values()):raise ValueError("Verifier requires a real dependent deterministic verification task")
        if task.capability in ("experiment.run","paper.compare") and not a.verifier:raise ValueError("Scientific work needs independent deterministic review assignment")


def propose(spec:MissionSpec,mode="adaptive"):
    if mode not in ("single","fixed","adaptive"):raise ValueError("Unknown team template")
    data=spec.model_dump(mode="json");data["team"]=None
    if not data.get("control"):raise ValueError("Supervised brief required")
    tasks=data["tasks"];reviews={}
    for task in list(tasks):
        if task["capability"] in ("experiment.run","paper.compare"):
            existing=next((t for t in tasks if t["capability"] in ("experiment.verify","artifact.verify") and t["args"].get("from_task")==task["id"]),None)
            vid=existing["id"] if existing else "check_"+task["id"][:32]
            if not existing:tasks.append({"id":vid,"capability":"experiment.verify" if task["capability"]=="experiment.run" else "artifact.verify","args":{"from_task":task["id"]},"depends_on":[task["id"]]})
            reviews[task["id"]]=vid
    verification_ids={t["id"] for t in tasks if t["capability"] in ("experiment.verify","artifact.verify")}
    workers=[t for t in tasks if t["id"] not in verification_ids]
    owners={};assignments=[];role_tasks={}
    for i,task in enumerate(workers):
        # Serial worker: expand only for an actual fixed template or independent compute specialization.
        independent=task["capability"]=="experiment.run" and any(not task.get("depends_on") and t["id"]!=task["id"] and not t.get("depends_on") for t in workers)
        owner="worker"+str(i%2+1) if mode=="fixed" and len(workers)>1 else "compute" if mode=="adaptive" and independent else "worker1"
        owners[task["id"]]=owner;role_tasks.setdefault(owner,[]).append(task)
    for task in tasks:
        if task["id"] in verification_ids:owners[task["id"]]="verifier";role_tasks.setdefault("verifier",[]).append(task)
    roles=[]
    for rid,owned in role_tasks.items():
        caps=sorted({t["capability"] for t in owned});perms=sorted({p for cap in caps for p in C.META[cap][2]});engines=sorted({e for t in owned for e in [t.get("preferred_engine","deterministic"),*t.get("fallback_engines",[])]})
        roles.append(AgentRole(id=rid,purpose="Independent raw-evidence verification" if rid=="verifier" else "Execute assigned registered capabilities",capabilities=caps,permissions=perms,engines=engines,expected_value="Separate measured evidence from interpretations" if rid=="verifier" else "Minimal bounded ownership; productivity advantage is unmeasured"))
    for task in tasks:assignments.append(TaskAssignment(task_id=task["id"],owner=owners[task["id"]],verifier="verifier" if task["id"] in reviews else "",acceptance=["ExecutionResult schema; owned evidence; scientific claims remain pending human review"]))
    data["team"]=TeamPlan(mode=mode,agents=roles,assignments=assignments,max_agents=4).model_dump(mode="json")
    # Reports wait for independent checks too, so the snapshot does not omit the review.
    for t in tasks:
        if t["capability"]=="mission.report":t["depends_on"]=list(dict.fromkeys([*t.get("depends_on",[]),*verification_ids]))
    result=MissionSpec.model_validate(data);validate(result);return result


def registry():
    with S.db() as c:
        observed=[dict(r) for r in c.execute("SELECT json_extract(payload,'$.spec.capability') AS capability,status,count(*) AS count FROM mission_tasks GROUP BY capability,status")]
    return {"checked_at":S.now(),"capabilities":C.catalog(),"observed":observed,"health":"Native backend health is rechecked at admission; no confidence score is inferred","usage":"Token/currency cost unknown unless reported","logical_roles":True,"max_parallel_tasks":1}


def admit(c,m,task,key):
    team=m["payload"]["spec"].get("team")
    if not team:return
    if not enabled():raise ValueError("Team execution is disabled")
    assignments={a["task_id"]:a for a in team["assignments"]};own=assignments[task.id]["owner"]
    for dep in task.depends_on:
        previous=next(t for t in m["tasks"] if t["id"]==dep)
        if previous["status"]!="completed":raise ValueError("Handoff dependency is not complete")
        result=previous["payload"].get("result",{})
        envelope=TaskEnvelope(mission_id=m["id"],topic_id=m["topic_id"],task_id=task.id,sender=assignments[dep]["owner"],receiver=own,dependency_task_id=dep,input_digest=L.digest(result),artifact_refs=result.get("artifacts",[]))
        payload=envelope.model_dump(mode="json")
        existing=c.execute("SELECT payload FROM task_handoffs WHERE mission_id=? AND task_id=? AND dependency_id=?",(m["id"],task.id,dep)).fetchone()
        if existing and json.loads(existing[0])!=payload:raise ValueError("Dependency output changed after handoff")
        c.execute("INSERT OR IGNORE INTO task_handoffs VALUES(?,?,?,?,?,?)",(S.uid(),m["id"],m["topic_id"],task.id,dep,S.dumps(payload)))
    c.execute("UPDATE mission_attempts SET payload=? WHERE key=?",(S.dumps({"owner":own,"verifier":assignments[task.id]["verifier"],"started_at":S.now(),"queue_seconds":max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(m["created"])).total_seconds())}),key))


def monitor(tid,mid):
    from backend.agent import missions as M
    m=M.get(mid,tid)
    with S.db() as c:
        handoffs=[{**dict(r),"payload":json.loads(r["payload"])} for r in c.execute("SELECT * FROM task_handoffs WHERE mission_id=?",(mid,))]
        attempts=[{**dict(r),"payload":json.loads(r["payload"])} for r in c.execute("SELECT * FROM mission_attempts WHERE mission_id=?",(mid,))]
    return {"mission":m,"handoffs":handoffs,"attempts":attempts,"active_agents":[a["payload"].get("owner") for a in attempts if a["status"]=="admitted"],"cost":None,"remaining_provider_quota":None}


def verify(m,task):
    from backend.agent import missions as M
    if task.capability=="experiment.verify":
        from backend.knowledge.verification import verify_run
        rid=task.args.get("run_id")
        if not rid:
            previous=next((t for t in m["tasks"] if t["id"]==task.args.get("from_task")),None)
            if not previous:raise ValueError("Verification dependency required")
            rid=previous["payload"].get("result",{}).get("output",{}).get("experiment_run_id")
        if not rid:raise ValueError("No measured run reference")
        report=verify_run(m["topic_id"],rid)
        status="failed" if report["status"]=="failed" else "verified" if report["reproduction_run_id"] else "unverified"
        return VerificationResult(status=status,method=report["verifier"],evidence_refs=["experiment:"+rid],checks=report["checks"],limitations=report["limitations"]+report["warnings"]).model_dump()
    previous=next((t for t in m["tasks"] if t["id"]==task.args.get("from_task")),None)
    if not previous:raise ValueError("Artifact verification needs a scoped completed dependency")
    refs=previous["payload"].get("result",{}).get("artifacts",[]);checks=[]
    from backend.agent.research_os import artifact
    for index,ref in enumerate(refs):
        try:artifact(m["topic_id"],m["id"],previous["id"],index);ok=True
        except (ValueError,OSError):ok=False
        checks.append({"sha256":ref["sha256"],"status":"passed" if ok else "failed"})
    return VerificationResult(status="failed" if any(c["status"]=="failed" for c in checks) else "unverified",method="artifact-sha256-v1",checks=checks,limitations=["Artifact integrity never proves a scientific interpretation","No original numerical evidence means the performance claim stays unverified"]).model_dump()


def replan(tid,mid,task_id,engine,note):
    from backend.agent import missions as M
    if not note.strip():raise ValueError("Replan review note required")
    m=M.get(mid,tid);data=m["payload"]["spec"];team=data.get("team")
    if not team or m["status"] not in ("failed","paused"):raise ValueError("Replan only a failed/paused team mission")
    target=next((t for t in m["tasks"] if t["id"]==task_id),None)
    if not target or target["status"] not in ("failed","pending") or target["payload"]["spec"]["capability"]!="paper.compare":raise ValueError("Only a known failed/unadmitted reasoning task can be reassigned; reconcile uncertain admissions first")
    if engine not in data["control"]["allowed_engines"]:raise ValueError("Replan cannot enlarge engine policy")
    generation=team["generation"]+1
    if generation>team["max_replans"]:raise ValueError("Replan cap exhausted")
    completed={t["id"]:t for t in m["tasks"] if t["status"]=="completed"};remaining=[]
    for row in m["tasks"]:
        if row["id"] in completed:continue
        if row["status"] in ("running","interrupted"):raise ValueError("Reconcile uncertain work before replanning")
        t=json.loads(S.dumps(row["payload"]["spec"]));t["depends_on"]=[d for d in t["depends_on"] if d not in completed]
        dep=t["args"].get("from_task")
        if dep in completed:
            if not t["capability"].startswith("paper."):raise ValueError("This completed handoff requires manual versioning")
            t["args"].pop("from_task");t["args"]["paper_ids"]=completed[dep]["payload"].get("result",{}).get("output",{}).get("paper_ids",[])
        if t["id"]==task_id:t["preferred_engine"]=engine;t["fallback_engines"]=[]
        remaining.append(t)
    data=json.loads(S.dumps(data));data["tasks"]=remaining;data["team"]=None;data["control"]["predecessor_id"]=mid
    data["limits"]["max_reasoning_calls"]-=m["payload"]["reasoning_calls"]
    data["limits"]["max_seconds"]-=math.ceil(m["payload"]["active_seconds"])
    data["limits"]["max_attempts"]-=target["payload"]["attempts"]
    if data["limits"]["max_reasoning_calls"]<1 or data["limits"]["max_seconds"]<1 or data["limits"]["max_attempts"]<1:raise ValueError("Remaining resource budget exhausted; request a new human-approved direction/budget")
    draft=propose(MissionSpec.model_validate(data),team["mode"]);draft.team.generation=generation;draft.team.max_replans=team["max_replans"]
    draft.team.max_agents=team["max_agents"]
    new=M.create(draft)
    with S.db() as c:L.append(c,tid,new["id"],"team.replan_proposed",{"predecessor":mid,"task":task_id,"engine":engine,"note":note,"generation":generation,"fresh_approval_required":True})
    return new
