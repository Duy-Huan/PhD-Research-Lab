"""Bounded logical workstreams, durable receipts and PI decisions under one Mission authority."""
import json
import re
from backend.agent import capabilities as C,decision_ledger as L,teams
from backend.agent.mission_contracts import MissionSpec,Workstream,CollaborationPlan,WorkOrder,EvidenceBundle,ArtifactReference
from backend.knowledge import research_store as S


def enabled():
    from backend.core.config import load_config
    return load_config()["research_os"]["multi_team_enabled"] is True


def membership(spec):
    plan=spec.get("collaboration")
    return {task:w for w in plan["workstreams"] for task in w["task_ids"]} if plan else {}


def validate(spec):
    plan=spec.collaboration
    if not plan:return
    if not spec.team or not spec.control:raise ValueError("Workstreams require the supervised team harness")
    groups={w.id:w for w in plan.workstreams};tasks={t.id:t for t in spec.tasks};owners={t:w.id for w in plan.workstreams for t in w.task_ids}
    if len(groups)!=len(plan.workstreams) or len(groups)>plan.max_teams:raise ValueError("Workstream count/identity exceeds cap")
    if sum(len(w.task_ids) for w in plan.workstreams)!=len(tasks) or set(owners)!=set(tasks):raise ValueError("Each task belongs to exactly one workstream")
    if sum(w.max_reasoning_calls for w in plan.workstreams)>spec.limits.max_reasoning_calls or sum(w.max_active_seconds for w in plan.workstreams)>spec.limits.max_seconds or sum(w.max_artifact_mb for w in plan.workstreams)>spec.limits.max_artifact_mb:raise ValueError("Workstream allocations exceed mission resource budget")
    edges=0
    for w in plan.workstreams:
        if w.topic_id!=spec.topic_id:raise ValueError("Cross-topic team execution/messages require a separately scoped Mission")
        if not set(w.permissions)<=set(spec.permissions) or not set(w.engines)<=set(spec.control.allowed_engines):raise ValueError("Workstream expands mission authority")
        incoming=set();reasoning=0
        for tid in w.task_ids:
            t=tasks[tid];meta=C.META[t.capability]
            if not set(meta[2])<=set(w.permissions) or not {t.preferred_engine,*t.fallback_engines}<=set(w.engines):raise ValueError("Workstream lacks required task permissions/engine")
            reasoning+=int(not meta[1])
            for d in t.depends_on:
                if owners[d]!=w.id:incoming.add(owners[d]);edges+=1
        if reasoning>w.max_reasoning_calls:raise ValueError("Insufficient workstream reasoning allocation")
        if incoming!=set(w.depends_on):raise ValueError("Workstream dependency declarations must match the task DAG")
    if edges>plan.max_handoffs:raise ValueError("Cross-team handoff cap exceeded")
    pending={w.id:set(w.depends_on) for w in plan.workstreams};done=set()
    while pending:
        ready={k for k,v in pending.items() if v<=done}
        if not ready:raise ValueError("Cyclic workstream dependencies")
        done|=ready;pending={k:v for k,v in pending.items() if k not in ready}


def partition(spec:MissionSpec,max_teams=4):
    if not 1<=max_teams<=4:raise ValueError("Team cap must be 1–4")
    if not spec.team:spec=teams.propose(spec)
    data=spec.model_dump(mode="json");data["collaboration"]=None
    tasks=data["tasks"];roots=[t for t in tasks if not t["depends_on"] and t["capability"] not in ("mission.report","artifact.verify","experiment.verify")]
    useful=len(roots)>=2 and len({t["capability"] for t in roots})>=2
    if len(roots)>=2 and all(t["capability"]=="workspace.sync" for t in roots):useful=True
    grouped={}
    for t in tasks:
        cap=t["capability"]
        if not useful:key="single"
        elif cap=="workspace.sync":key="workspace_"+t["id"][:25]
        elif cap.startswith("paper."):key="literature"
        elif cap=="experiment.run":key="experiments"
        elif cap.endswith(".verify"):key="verification"
        else:key="reporting"
        grouped.setdefault(key,[]).append(t)
    if len(grouped)>max_teams or len(grouped)>min(spec.limits.max_seconds,spec.limits.max_artifact_mb):grouped={"single":tasks}
    owners={t["id"]:key for key,owned in grouped.items() for t in owned};count=len(grouped);workstreams=[]
    for i,(key,owned) in enumerate(grouped.items()):
        perms=sorted({p for t in owned for p in C.META[t["capability"]][2]});engines=sorted({e for t in owned for e in [t["preferred_engine"],*t["fallback_engines"]]})
        workstreams.append(Workstream(id=key,topic_id=spec.topic_id,objective="Bounded "+key+" work for "+spec.objective[:500],task_ids=[t["id"] for t in owned],depends_on=sorted({owners[d] for t in owned for d in t["depends_on"] if owners[d]!=key}),permissions=perms,engines=engines,max_reasoning_calls=sum(int(not C.META[t["capability"]][1]) for t in owned),max_active_seconds=spec.limits.max_seconds//count+(spec.limits.max_seconds%count if i==0 else 0),max_artifact_mb=spec.limits.max_artifact_mb//count+(spec.limits.max_artifact_mb%count if i==0 else 0),deliverables=["ExecutionResult and owned source/artifact pointers"]))
    data["collaboration"]=CollaborationPlan(workstreams=workstreams,max_teams=max_teams,rationale="Independent runnable branches justify separate bounded domains; execution remains serial" if count>1 else "Single-team fallback: extra workstreams are not justified by independent branches/budget").model_dump(mode="json")
    result=MissionSpec.model_validate(data)
    try:validate(result)
    except ValueError:
        if count==1:raise
        return partition(spec,1)  # Quotient cycles/insufficient allocation never create another scheduler.
    return result


def register(c,mid,spec):
    if spec.collaboration:
        for w in spec.collaboration.workstreams:c.execute("INSERT INTO workstream_usage(mission_id,team_id) VALUES(?,?)",(mid,w.id))


def gate(c,m,task=None):
    plan=m["payload"]["spec"].get("collaboration")
    if not plan:return ""
    if len(plan["workstreams"])>1 and not enabled():return "Multi-team execution is disabled"
    if not task:return ""
    w=membership(m["payload"]["spec"])[task.id];usage=c.execute("SELECT * FROM workstream_usage WHERE mission_id=? AND team_id=?",(m["id"],w["id"])).fetchone()
    if not usage:return "Workstream accounting is unavailable"
    if usage["active_seconds"]>=w["max_active_seconds"] or usage["artifact_bytes"]>=w["max_artifact_mb"]*1024*1024:return "Workstream time/storage budget exhausted"
    if not C.META[task.capability][1] and usage["reasoning_calls"]>=w["max_reasoning_calls"]:return "Workstream reasoning budget exhausted"
    if task.capability=="paper.download":
        from backend.agent.missions import _papers
        profile=S.topic(c,m["topic_id"])
        estimate=min(len(_papers(m,task)),profile["pdf_limit"])*profile["max_pdf_mb"]*1024*1024
        if usage["artifact_bytes"]+estimate>w["max_artifact_mb"]*1024*1024:return "PDF worst-case download size exceeds workstream storage allocation"
    if task.capability=="experiment.run":
        protocol=c.execute("SELECT payload FROM experiment_protocols WHERE id=? AND topic_id=?",(task.args["protocol_id"],m["topic_id"])).fetchone()
        if not protocol:return "Protocol not found in this Topic"
        p=json.loads(protocol[0])["spec"];recipe=p["dataset"]
        estimate=recipe["side"]**2*max(recipe["validation_count"],recipe["test_count"])*len(p["seeds"])*(len(p["alphas"])+3)*3*32+4096
        if usage["artifact_bytes"]+estimate>w["max_artifact_mb"]*1024*1024:return "Trusted experiment observation estimate exceeds workstream storage budget"
    return ""


def remaining(c,m,task):
    mapping=membership(m["payload"]["spec"])
    if not mapping:return 3600
    w=mapping[task.id];row=c.execute("SELECT active_seconds FROM workstream_usage WHERE mission_id=? AND team_id=?",(m["id"],w["id"])).fetchone()
    return max(0.001,w["max_active_seconds"]-row[0])


def charge(c,m,task,*,reasoning=0,seconds=0,artifact_bytes=0):
    mapping=membership(m["payload"]["spec"])
    if mapping:c.execute("UPDATE workstream_usage SET reasoning_calls=reasoning_calls+?,active_seconds=active_seconds+?,artifact_bytes=artifact_bytes+? WHERE mission_id=? AND team_id=?",(reasoning,seconds,artifact_bytes,m["id"],mapping[task.id]["id"]))


def _message(c,m,source_task,target_task):
    from backend.agent import missions as M
    current=M._get(c,m["id"],m["topic_id"]);mapping=membership(current["payload"]["spec"])
    rows={t["id"]:t for t in current["tasks"]}
    if source_task not in rows or target_task not in rows or source_task not in rows[target_task]["payload"]["spec"]["depends_on"]:raise ValueError("Work order must follow a declared dependency")
    if mapping[source_task]["id"]==mapping[target_task]["id"]:return None
    source=rows[source_task]
    if source["status"]!="completed":raise ValueError("Only completed task evidence can be handed off")
    result=source["payload"].get("result",{});out=result.get("output",{});refs=["paper:"+p for p in out.get("paper_ids",[])]
    if out.get("experiment_run_id"):refs.append("experiment:"+out["experiment_run_id"])
    order=WorkOrder(project_id=c.execute("SELECT value FROM meta WHERE key='project_id'").fetchone()[0],mission_id=m["id"],topic_id=m["topic_id"],source_team=mapping[source_task]["id"],target_team=mapping[target_task]["id"],source_task=source_task,target_task=target_task,evidence=EvidenceBundle(result_digest=L.digest(result),source_refs=refs,artifacts=[ArtifactReference.model_validate({k:v for k,v in a.items() if k in ("path","sha256","bytes")}) for a in result.get("artifacts",[])]))
    payload=order.model_dump(mode="json");digest=L.digest(payload)
    existing=c.execute("SELECT id,digest FROM collaboration_messages WHERE mission_id=? AND source_task=? AND target_task=?",(m["id"],source_task,target_task)).fetchone()
    if existing:
        if existing["digest"]!=digest:raise ValueError("Immutable handoff evidence changed")
        return existing["id"]
    count=c.execute("SELECT count(*) FROM collaboration_messages WHERE mission_id=?",(m["id"],)).fetchone()[0]
    if count>=current["payload"]["spec"]["collaboration"]["max_handoffs"]:raise ValueError("Handoff budget exhausted")
    hid=S.uid();c.execute("INSERT INTO collaboration_messages VALUES(?,?,?,?,?,?,?,?,?)",(hid,m["id"],m["topic_id"],source_task,target_task,"published",digest,S.dumps(payload),S.now()))
    L.append(c,m["topic_id"],m["id"],"workstream.handoff_published",{"message_id":hid,"digest":digest,"source":source_task,"target":target_task})
    return hid


def acknowledge(c,m,hid,receiver):
    row=c.execute("SELECT * FROM collaboration_messages WHERE id=? AND mission_id=? AND topic_id=?",(hid,m["id"],m["topic_id"])).fetchone()
    if not row:raise ValueError("Handoff outside Mission/Topic")
    order=WorkOrder.model_validate(json.loads(row["payload"]))
    if order.project_id!=c.execute("SELECT value FROM meta WHERE key='project_id'").fetchone()[0] or order.target_team!=receiver or L.digest(order.model_dump(mode="json"))!=row["digest"]:raise ValueError("Invalid handoff project, receiver or digest")
    from backend.agent import missions as M,research_os as O
    current=M._get(c,m["id"]);source=next(t for t in current["tasks"] if t["id"]==order.source_task)
    if source["status"]!="completed" or L.digest(source["payload"].get("result",{}))!=order.evidence.result_digest:raise ValueError("Handoff source evidence changed")
    # File ownership and checksums are independently checked at execution/export; never trust a receiving model's assertion.
    import hashlib
    from pathlib import Path
    for ref in order.evidence.artifacts:
        path=Path(ref.path)
        if not path.is_relative_to(S.store_dir()):raise ValueError("Handoff artifact outside research store")
        path=S.safe_child(S.store_dir(),*path.relative_to(S.store_dir()).parts)
        if not path.is_file() or path.stat().st_size!=ref.bytes or hashlib.sha256(path.read_bytes()).hexdigest()!=ref.sha256:raise ValueError("Handoff artifact integrity failed")
    receipt={"message_digest":row["digest"],"source_result_digest":order.evidence.result_digest,"validation":"schema/source/hash checked; scientific validity still unverified"}
    existing=c.execute("SELECT receiver_team,payload FROM handoff_receipts WHERE message_id=?",(hid,)).fetchone()
    if existing:
        if existing[0]!=receiver or json.loads(existing[1])!=receipt:raise ValueError("Receipt conflict")
    else:
        c.execute("INSERT INTO handoff_receipts VALUES(?,?,?,?)",(hid,receiver,S.dumps(receipt),S.now()))
        c.execute("UPDATE collaboration_messages SET status='acknowledged' WHERE id=?",(hid,))
        L.append(c,m["topic_id"],m["id"],"workstream.handoff_acknowledged",{"message_id":hid,"receiver_team":receiver,**receipt})


def admit(c,m,task):
    mapping=membership(m["payload"]["spec"])
    if not mapping:return
    blocked=gate(c,m,task)
    if blocked:raise ValueError(blocked)
    for dep in task.depends_on:
        if mapping[dep]["id"]!=mapping[task.id]["id"]:
            hid=_message(c,m,dep,task.id);acknowledge(c,m,hid,mapping[task.id]["id"])
    charge(c,m,task,reasoning=int(not C.META[task.capability][1]))
    if task.capability=="paper.download":
        before=_topic_pdf_bytes(c,m["topic_id"])
        c.execute("UPDATE mission_attempts SET payload=json_set(payload,'$.pdf_bytes_before',?) WHERE key=(SELECT key FROM mission_attempts WHERE mission_id=? AND task_id=? ORDER BY rowid DESC LIMIT 1)",(before,m["id"],task.id))


def _topic_pdf_bytes(c,tid):
    return c.execute("SELECT coalesce(sum(bytes),0) FROM documents WHERE sha256 IN (SELECT vd.sha256 FROM version_documents vd JOIN versions v ON v.id=vd.version_id JOIN paper_topics pt ON pt.paper_id=v.paper_id WHERE pt.topic_id=?)",(tid,)).fetchone()[0]


def output_bytes(c,result,m=None,task=None):
    total=sum(a.get("bytes",0) for a in result.get("artifacts",[]))
    rid=result.get("output",{}).get("experiment_run_id")
    if rid:total+=c.execute("SELECT coalesce(sum(json_extract(payload,'$.artifact.bytes')),0) FROM experiment_trials WHERE run_id=?",(rid,)).fetchone()[0]
    if m and task and task.capability=="paper.download":
        before=c.execute("SELECT json_extract(payload,'$.pdf_bytes_before') FROM mission_attempts WHERE mission_id=? AND task_id=? ORDER BY rowid DESC LIMIT 1",(m["id"],task.id)).fetchone()
        if before and before[0] is not None:total+=max(0,_topic_pdf_bytes(c,m["topic_id"])-before[0])
    return total


def check_output(c,m,task,result,outcome):
    mapping=membership(m["payload"]["spec"])
    if not mapping:return outcome
    w=mapping[task.id];used=c.execute("SELECT artifact_bytes FROM workstream_usage WHERE mission_id=? AND team_id=?",(m["id"],w["id"])).fetchone()[0]
    if used+output_bytes(c,result,m,task)>w["max_artifact_mb"]*1024*1024:
        result["resource_error"]="Workstream output storage budget exceeded; artifacts retained, no automatic retry";return "failed"
    return outcome


def settle(c,m,task,result,outcome,seconds):
    mapping=membership(m["payload"]["spec"])
    if not mapping:return
    charge(c,m,task,seconds=seconds,artifact_bytes=output_bytes(c,result,m,task))
    if outcome=="completed":
        for target in m["payload"]["spec"]["tasks"]:
            if task.id in target["depends_on"] and mapping[task.id]["id"]!=mapping[target["id"]]["id"]:_message(c,m,task.id,target["id"])
        if task.capability.endswith(".verify") and result.get("output",{}).get("status") in ("unverified","failed"):
            _dispute(c,m,mapping[task.id]["id"],"Independent review: "+result["output"]["status"],{"task_id":task.id,"verification":result["output"]})


def _dispute(c,m,team_id,reason,evidence):
    did=S.uid();payload={"source_team":team_id,"reason":reason[:4000],"evidence":evidence,"created":S.now(),"scientific_claims_not_promoted":True}
    c.execute("INSERT INTO collaboration_disputes VALUES(?,?,?,?,?,?)",(did,m["id"],m["topic_id"],"open",1,S.dumps(payload)))
    L.append(c,m["topic_id"],m["id"],"workstream.dispute_opened",{"dispute_id":did,**payload});return did


def dispute(tid,mid,team_id,reason,claim_ids):
    from backend.agent import missions as M
    from backend.knowledge import governance as G
    m=M.get(mid,tid)
    if not reason.strip() or team_id not in {w["id"] for w in (m["payload"]["spec"].get("collaboration") or {}).get("workstreams",[])}:raise ValueError("Scoped team and reason required")
    for cid in claim_ids:G.get(tid,cid)
    with S.db() as c:return {"id":_dispute(c,m,team_id,reason,{"claim_ids":claim_ids})}


def resolve(tid,mid,did,revision,note):
    from backend.agent import missions as M
    M.get(mid,tid)
    if not note.strip():raise ValueError("Human resolution note required")
    with S.db() as c:
        row=c.execute("SELECT * FROM collaboration_disputes WHERE id=? AND mission_id=? AND topic_id=?",(did,mid,tid)).fetchone()
        if not row or row["revision"]!=revision or row["status"]!="open":raise ValueError("Dispute version/state conflict")
        payload=json.loads(row["payload"]);payload["resolution"]={"by":"researcher","note":note[:4000],"at":S.now(),"does_not_approve_claims":True}
        c.execute("UPDATE collaboration_disputes SET status='resolved',revision=revision+1,payload=? WHERE id=? AND revision=?",(S.dumps(payload),did,revision))
        L.append(c,tid,mid,"workstream.dispute_resolved",{"dispute_id":did,"revision":revision+1,**payload["resolution"]})
    return {"id":did,"status":"resolved","revision":revision+1}


def review_blocker(c,m):
    if not m["payload"]["spec"].get("collaboration"):return ""
    if c.execute("SELECT 1 FROM collaboration_disputes WHERE mission_id=? AND status='open'",(m["id"],)).fetchone():return "Resolve open workstream disputes before final Mission review"
    if c.execute("SELECT 1 FROM collaboration_messages WHERE mission_id=? AND status!='acknowledged'",(m["id"],)).fetchone():return "Unacknowledged workstream handoffs remain"
    return ""


def canonical(tid,mid,team_id,key,source_task,index,expected_revision,note):
    from backend.agent import missions as M,research_os as O
    m=M.get(mid,tid);mapping=membership(m["payload"]["spec"])
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}",key) or expected_revision<0 or not note.strip():raise ValueError("Canonical key, version and human note required")
    if source_task not in mapping or mapping[source_task]["id"]!=team_id:raise ValueError("Canonical output must be owned by the submitting team")
    O.artifact(tid,mid,source_task,index)
    task=next(t for t in m["tasks"] if t["id"]==source_task);ref=task["payload"]["result"]["artifacts"][index]
    payload={"mission_id":mid,"owner_team":team_id,"source_task":source_task,"artifact":ref,"scientific_review":"pending","by":"researcher","note":note[:4000]}
    conflict=False
    with S.db() as c:
        row=c.execute("SELECT revision FROM canonical_outputs WHERE topic_id=? AND output_key=?",(tid,key)).fetchone();actual=row[0] if row else 0
        if actual!=expected_revision:
            conflict=True;L.append(c,tid,mid,"workstream.canonical_conflict",{"key":key,"expected_revision":expected_revision,"actual_revision":actual,"team_id":team_id})
        else:
            revision=actual+1
            c.execute("INSERT INTO canonical_outputs VALUES(?,?,?,?) ON CONFLICT(topic_id,output_key) DO UPDATE SET revision=excluded.revision,payload=excluded.payload",(tid,key,revision,S.dumps(payload)))
            c.execute("INSERT INTO canonical_revisions VALUES(?,?,?,?,?)",(S.uid(),tid,key,revision,S.dumps(payload)))
            L.append(c,tid,mid,"workstream.canonical_registered",{"key":key,"revision":revision,**payload})
    if conflict:raise ValueError("Canonical output version conflict; prior output retained")
    return {"key":key,"revision":revision,"payload":payload}


def monitor(tid,mid):
    from backend.agent import missions as M
    m=M.get(mid,tid)
    with S.db() as c:
        messages=[{**dict(r),"payload":json.loads(r["payload"])} for r in c.execute("SELECT * FROM collaboration_messages WHERE mission_id=?",(mid,))]
        receipts=[{**dict(r),"payload":json.loads(r["payload"])} for r in c.execute("SELECT r.* FROM handoff_receipts r JOIN collaboration_messages m ON m.id=r.message_id WHERE m.mission_id=?",(mid,))]
        disputes=[{**dict(r),"payload":json.loads(r["payload"])} for r in c.execute("SELECT * FROM collaboration_disputes WHERE mission_id=?",(mid,))]
        usage=[dict(r) for r in c.execute("SELECT * FROM workstream_usage WHERE mission_id=?",(mid,))]
        outputs=[{**dict(r),"payload":json.loads(r["payload"])} for r in c.execute("SELECT * FROM canonical_outputs WHERE topic_id=?",(tid,))]
    return {"mission":m,"messages":messages,"receipts":receipts,"disputes":disputes,"usage":usage,"canonical_outputs":outputs,"external_agent_authentication":"Not provided; existing local trusted-researcher authority only","concurrency":1}


def publish(tid,mid,source_task,target_task):
    from backend.agent import missions as M
    m=M.get(mid,tid)
    if not m["payload"]["spec"].get("collaboration"):raise ValueError("Mission has no workstream contract")
    with S.db() as c:return {"message_id":_message(c,m,source_task,target_task)}


def receive(tid,mid,hid,receiver):
    from backend.agent import missions as M
    m=M.get(mid,tid)
    with S.db() as c:acknowledge(c,m,hid,receiver)
    return {"message_id":hid,"status":"acknowledged"}


def finding(tid,mid,team_id,body):
    from backend.agent import missions as M
    from backend.knowledge import governance as G
    m=M.get(mid,tid)
    if team_id not in {w["id"] for w in (m["payload"]["spec"].get("collaboration") or {}).get("workstreams",[])}:raise ValueError("Finding must name a scoped workstream")
    claim=G.create(tid,body)
    with S.db() as c:L.append(c,tid,mid,"workstream.finding_proposed",{"claim_id":claim["id"],"team_id":team_id,"status":claim["status"],"memory_promoted":False})
    return claim
