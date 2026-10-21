"""Immutable protocol snapshots and bounded trusted experiments, run only by approved missions."""
import asyncio
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

from backend.agent import decision_ledger as L
from backend.execution.protocol_contracts import ExperimentProtocol
from backend.knowledge import research_store as S

WORKER=Path(__file__).with_name("denoising_worker.py")


def worker_hash():return hashlib.sha256(WORKER.read_bytes()).hexdigest()


def _get(c,pid,tid):
    r=c.execute("SELECT * FROM experiment_protocols WHERE id=? AND topic_id=?",(pid,tid)).fetchone()
    if not r:raise ValueError("Protocol not found in this Topic/project")
    return {**dict(r),"payload":json.loads(r["payload"]),"approval":json.loads(r["approval"]) if r["approval"] else None}


def get(tid,pid):
    with S.db() as c:return _get(c,pid,tid)


def listing(tid):
    with S.db() as c:
        S.topic(c,tid)
        return [_get(c,r[0],tid) for r in c.execute("SELECT id FROM experiment_protocols WHERE topic_id=? ORDER BY rowid DESC",(tid,))]


def create(spec:ExperimentProtocol,parent_id=""):
    data=spec.model_dump();recipe=data["dataset"]
    splits={k:[k+":"+str(i) for i in range(recipe[k+"_count"])] for k in ("train","validation","test")}
    fingerprint=L.digest({"recipe":recipe,"splits":splits,"generator_sha256":worker_hash()})
    with S.db() as c:
        S.topic(c,spec.topic_id)
        revision=_get(c,parent_id,spec.topic_id)["revision"]+1 if parent_id else 1
        did=S.uid()
        c.execute("INSERT OR IGNORE INTO dataset_versions VALUES(?,?,?,?)",(did,spec.topic_id,fingerprint,S.dumps({"recipe":recipe,"splits":splits,"generator_sha256":worker_hash(),"license":recipe["license"]})))
        did=c.execute("SELECT id FROM dataset_versions WHERE topic_id=? AND fingerprint=?",(spec.topic_id,fingerprint)).fetchone()[0]
        snapshot={"spec":data,"dataset_id":did,"dataset_fingerprint":fingerprint,"splits":splits,"worker_sha256":worker_hash(),"baseline_locked":"noisy_input","training":"No learning; train split unused by non-parametric fixed filters"}
        pid=S.uid();digest=L.digest(snapshot)
        c.execute("INSERT INTO experiment_protocols VALUES(?,?,?,?,?,?,?)",(pid,spec.topic_id,parent_id or None,revision,digest,S.dumps(snapshot),None))
        L.append(c,spec.topic_id,pid,"protocol.created",{"digest":digest,"revision":revision,"parent_id":parent_id})
        return _get(c,pid,spec.topic_id)


def approve(tid,pid,digest,note):
    if not note.strip():raise ValueError("Human protocol review note required")
    with S.db() as c:
        p=_get(c,pid,tid)
        if p["digest"]!=digest or L.digest(p["payload"])!=digest:raise ValueError("Protocol digest mismatch")
        if c.execute("SELECT 1 FROM experiment_runs WHERE protocol_id=? AND status='running'",(pid,)).fetchone():raise ValueError("Protocol has an active run")
        approval={"by":"researcher","at":S.now(),"note":note[:4000],"digest":digest,"nonce":S.uid(),"resources":{"cpu_threads":1,"gpu":False,"memory_limit_enforced":p["payload"]["spec"]["engine"]=="docker","local_process_not_os_sandbox":True}}
        c.execute("UPDATE experiment_protocols SET approval=? WHERE id=?",(S.dumps(approval),pid))
        L.append(c,tid,pid,"protocol.approved",approval)
        return _get(c,pid,tid)


def mission_draft(tid,pid):
    from backend.agent import missions
    from backend.agent.mission_contracts import MissionSpec
    p=get(tid,pid)
    if not p["approval"]:raise ValueError("Approve the fixed protocol first")
    return missions.create(MissionSpec.model_validate({"topic_id":tid,"objective":p["payload"]["spec"]["hypothesis"],"permissions":["compute","workspace_write"],
        "limits":{"max_seconds":p["payload"]["spec"]["max_seconds"]+15},"tasks":[{"id":"experiment","capability":"experiment.run","args":{"protocol_id":pid,"protocol_digest":p["digest"],"approval_nonce":p["approval"]["nonce"]}},{"id":"report","capability":"mission.report","depends_on":["experiment"]}]}))


def runs(tid):
    with S.db() as c:
        S.topic(c,tid)
        return [{**dict(r),"payload":json.loads(r["payload"]),"trials":[{**dict(t),"payload":json.loads(t["payload"])} for t in c.execute("SELECT * FROM experiment_trials WHERE run_id=? ORDER BY rowid",(r["id"],))]} for r in c.execute("SELECT * FROM experiment_runs WHERE topic_id=? ORDER BY rowid DESC",(tid,))]


def run(tid,rid):
    r=next((r for r in runs(tid) if r["id"]==rid),None)
    if not r:raise ValueError("Experiment run not found in this Topic/project")
    return r


def recover():
    with S.db() as c:
        for r in list(c.execute("SELECT id,topic_id FROM experiment_runs WHERE status='running'")):
            c.execute("UPDATE experiment_runs SET status='interrupted' WHERE id=?",(r["id"],))
            c.execute("UPDATE experiment_trials SET status='interrupted' WHERE run_id=? AND status='running'",(r["id"],))
            L.append(c,r["topic_id"],r["id"],"experiment.interrupted",{"automatic_rerun":False})


def _summary(observations):
    out={}
    for seed in sorted({o["seed"] for o in observations}):
        values=[o for o in observations if o["seed"]==seed]
        out[str(seed)]={k:statistics.mean(o[k] for o in values) for k in ("mse","psnr_db")}
    return {"per_seed":out,"mean_psnr_db":statistics.mean(v["psnr_db"] for v in out.values()),"repeat_count":len(out)}


async def _trial(tid,rid,protocol,alpha,split,remaining,cancelled):
    from backend.execution.tools import NO_WINDOW
    from backend.providers.cli_space import minimal_env
    from backend.providers.cli import kill_tree
    spec=protocol["payload"]["spec"]
    trial_id=S.uid();key=split+":"+str(alpha)
    folder=S.safe_child(S.store_dir(),"experiments",rid,trial_id);folder.mkdir(parents=True,exist_ok=True)
    request={"recipe":spec["dataset"],"seeds":spec["seeds"],"alpha":alpha,"split":split}
    input_path=S.safe_child(folder,"request.json");output=S.safe_child(folder,"observations.json")
    input_path.write_text(S.dumps(request),"utf-8")
    payload={"request":request,"protocol_digest":protocol["digest"],"dataset_fingerprint":protocol["payload"]["dataset_fingerprint"],"worker_sha256":worker_hash(),"started":S.now(),"folder":str(folder)}
    with S.db() as c:c.execute("INSERT INTO experiment_trials VALUES(?,?,?,?,?)",(trial_id,rid,key,"running",S.dumps(payload)))
    name="phdlab-protocol-"+trial_id[:8]
    proc=None;started=time.monotonic()
    try:
        if spec["engine"]=="docker":
            from backend.execution import sandbox
            if not sandbox.docker_running() or not sandbox.image_present(spec["docker_image"]):raise ValueError("Pinned Docker image/daemon unavailable; no pull or fallback performed")
            argv=[sandbox.docker_exe(),"run","--rm","--name",name,"--network","none","--read-only","--memory","512m","--cpus","1","--pids-limit","64","--cap-drop","ALL","--security-opt","no-new-privileges","--tmpfs","/tmp","-v",str(folder)+":/out","-v",str(WORKER)+":/runner.py:ro",spec["docker_image"],"python","-I","-B","/runner.py","/out/request.json","/out/observations.json"]
        else:argv=[sys.executable,"-I","-B",str(WORKER),str(input_path),str(output)]
        with S.safe_child(folder,"stdout.log").open("wb") as stdout,S.safe_child(folder,"stderr.log").open("wb") as stderr:
            proc=subprocess.Popen(argv,cwd=str(folder),env=minimal_env(),stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,shell=False,creationflags=NO_WINDOW,start_new_session=__import__('os').name!='nt')
            while proc.poll() is None:
                if cancelled() or time.monotonic()-started>min(45,remaining):raise ValueError("Trial cancelled or time budget exceeded")
                await asyncio.sleep(0.05)
        if proc.returncode:raise ValueError("Native worker failed; inspect retained stderr")
        if not output.is_file() or output.stat().st_size>spec["max_artifact_mb"]*1024*1024:raise ValueError("Missing/oversized observation artifact")
        data=json.loads(output.read_text("utf-8"))
        if len(data["observations"])!=len(spec["seeds"])*spec["dataset"][split+"_count"]:raise ValueError("Unexpected sample count")
        payload.update(summary=_summary(data["observations"]),artifact={"path":str(output),"sha256":hashlib.sha256(output.read_bytes()).hexdigest(),"bytes":output.stat().st_size},ended=S.now(),elapsed_s=time.monotonic()-started,measurement=True)
        with S.db() as c:
            c.execute("UPDATE experiment_trials SET status='completed',payload=? WHERE id=?",(S.dumps(payload),trial_id))
            L.append(c,tid,rid,"trial.completed",{"trial_id":trial_id,**payload})
        return payload
    except BaseException as exc:
        payload.update(error=str(exc)[:500],ended=S.now())
        with S.db() as c:c.execute("UPDATE experiment_trials SET status='failed',payload=? WHERE id=?",(S.dumps(payload),trial_id))
        raise
    finally:
        if proc and proc.poll() is None:
            if spec["engine"]=="docker":
                from backend.execution import sandbox
                await asyncio.to_thread(sandbox.docker,["stop","-t","1",name],10)
            kill_tree(proc)
            await asyncio.to_thread(proc.wait,5)


async def execute(tid,pid,mission_id,expected_digest,expected_nonce):
    from backend.agent import missions
    from backend.execution import guard
    m=missions.get(mission_id,tid);p=get(tid,pid)
    if m["status"]!='running' or not m["payload"].get("approval"):raise ValueError("An approved running mission is required")
    if p["digest"]!=expected_digest or L.digest(p["payload"])!=expected_digest or not p["approval"] or p["approval"]["nonce"]!=expected_nonce:raise ValueError("Protocol/approval drift; create a new version or reapprove exact plan")
    if p["payload"]["worker_sha256"]!=worker_hash():raise ValueError("Runner revision changed; protocol reapproval requires a new snapshot")
    spec=ExperimentProtocol.model_validate(p["payload"]["spec"])
    sets=[set(v) for v in p["payload"]["splits"].values()]
    if any(a&b for i,a in enumerate(sets) for b in sets[i+1:]):raise ValueError("Dataset split leakage detected")
    holder="protocol:"+mission_id
    guard.try_acquire("cpu",holder)
    rid=S.uid();status="failed";payload={"protocol_digest":p["digest"],"dataset_fingerprint":p["payload"]["dataset_fingerprint"],"worker_sha256":worker_hash(),"seeds":spec.seeds,"hardware":{"platform":platform.platform(),"machine":platform.machine()},"python":sys.version,"engine":spec.engine,"started":S.now(),"scientific_review":"pending","raw_measurements_only":True}
    admitted=False;started=time.monotonic()
    try:
        with S.db() as c:
            if c.execute("SELECT 1 FROM experiment_runs WHERE approval_nonce=?",(expected_nonce,)).fetchone():raise ValueError("Protocol approval already consumed; explicit new approval required")
            c.execute("INSERT INTO experiment_runs VALUES(?,?,?,?,?,?,?)",(rid,tid,pid,mission_id,expected_nonce,"running",S.dumps(payload)));admitted=True
            L.append(c,tid,rid,"experiment.admitted",{"protocol_id":pid,**payload})
        cancelled=lambda:missions.get(mission_id,tid)["status"]=="cancelled"
        results=[]
        for alpha in [0.0,*spec.alphas]:
            remaining=spec.max_seconds-(time.monotonic()-started)
            if remaining<=0 or len(results)>=spec.max_trials:raise ValueError("Experiment budget exceeded")
            trial=await _trial(tid,rid,p,alpha,"validation",remaining,cancelled);results.append(trial)
            size=sum(f.stat().st_size for f in S.safe_child(S.store_dir(),"experiments",rid).rglob("*") if f.is_file())
            if size>spec.max_artifact_mb*1024*1024:raise ValueError("Experiment artifact budget exceeded")
            if spec.stop_on_target and len(results)>1 and trial["summary"]["mean_psnr_db"]-results[0]["summary"]["mean_psnr_db"]>=spec.min_psnr_gain_db:break
        baseline=results[0];best=max(results,key=lambda t:t["summary"]["mean_psnr_db"])
        deltas=[best["summary"]["per_seed"][str(seed)]["psnr_db"]-baseline["summary"]["per_seed"][str(seed)]["psnr_db"] for seed in spec.seeds]
        gain=statistics.mean(deltas);ci=1.96*statistics.stdev(deltas)/math.sqrt(len(deltas)) if len(deltas)>1 else None
        eligible=len(spec.seeds)>=3 and all(d>0 for d in deltas) and gain>=spec.min_psnr_gain_db
        test=[]
        for alpha in dict.fromkeys([0.0,best["request"]["alpha"]]):
            remaining=spec.max_seconds-(time.monotonic()-started)
            if remaining<=0 or len(results)+len(test)>=spec.max_trials:raise ValueError("Held-out evaluation budget exceeded")
            test.append(await _trial(tid,rid,p,alpha,"test",remaining,cancelled))
        payload.update(comparison={"selection_split":"validation","held_out_used_for_selection":False,"baseline_alpha":0,"selected_alpha":best["request"]["alpha"],"paired_psnr_gain_db":gain,"normal_approx_ci95":[gain-ci,gain+ci] if ci is not None else None,"repeat_count":len(spec.seeds),"recommendation":"candidate_improvement" if eligible else "no_supported_improvement","requires_human_review":True},test_evaluations=[r["summary"] for r in test],elapsed_s=time.monotonic()-started,ended=S.now())
        status="completed"
    except asyncio.CancelledError:
        status="interrupted";payload["error"]="Controller stopped; no automatic rerun";raise
    except Exception as exc:
        payload["error"]=str(exc)[:800];raise
    finally:
        guard.release("cpu",holder)
        if admitted:
            with S.db() as c:
                c.execute("UPDATE experiment_runs SET status=?,payload=? WHERE id=?",(status,S.dumps(payload),rid))
                L.append(c,tid,rid,"experiment."+status,payload)
    return {"experiment_run_id":rid,"status":status,**payload}
