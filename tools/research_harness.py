"""Isolated, measured supervised Research OS harness. No paid model or GPU invocation.

python -B tools/research_harness.py --stage 6.0 [--probe-engines]
Literature metadata/engine workspace content is explicitly synthetic. CPU observations are real.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"tests")]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["6.0","6.2","6.3"],default="6.0")
    parser.add_argument("--probe-engines",action="store_true")
    parser.add_argument("--output", type=Path, help="Separate evidence directory (default: artifacts/v<stage>)")
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="phdlab-harness-") as temporary:
        os.environ["PHDLAB_DATA_DIR"]=temporary
        from datetime import datetime,timedelta,timezone
        from backend.core import config
        from backend.agent import missions as M,research_os as O,decision_ledger as L
        from backend.agent.mission_contracts import MissionSpec
        from backend.knowledge import research_store as S,corpus as K,governance as G,verification as V
        from backend.execution import protocols as P
        from backend.execution.protocol_contracts import ExperimentProtocol
        from backend.research_engines import workspaces as W
        config.save_config({"research_os":{"enabled":True,"team_enabled":args.stage!="6.0","multi_team_enabled":args.stage=="6.3"},"clearml":{"auto_record":False},"memory":{"embed_engine":"hashing"}})
        a=S.save_topic(S.TopicInput(title="MRI Denoising (generated acceptance fixture)"))["id"]
        b=S.save_topic(S.TopicInput(title="CT Restoration (workspace fixture)"))["id"]
        ch=O.create_charter(O.ProjectCharter(goal="Medical Image Restoration — offline harness",topics=[O.TopicGoal(topic_id=a,goal="MRI"),O.TopicGoal(topic_id=b,parent_topic_id=a,goal="CT")],permissions=["workspace_write","compute"],max_reasoning_calls=0))
        records=K.ingest(a,[{"title":f"Synthetic literature fixture {i}","source":"harness_fixture","abstract":"Untrusted fixture, never evidence of a real publication."} for i in range(10)])
        common={"success_criteria":["Deterministic evidence available for human review"],"charter_id":ch["id"],"charter_digest":ch["digest"],"end_date":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
        rows=[];mission_ids=[]
        def execute(name,tid,tasks,permissions,mode="single"):
            start=time.perf_counter()
            spec=MissionSpec(topic_id=tid,objective=name,permissions=permissions,control=common,tasks=tasks)
            if args.stage!="6.0":
                from backend.agent import teams
                spec=teams.propose(spec,"adaptive" if args.stage=="6.3" else mode)
                if mode=="multi":
                    from backend.agent import collaboration
                    spec=collaboration.partition(spec)
                tasks=spec.tasks
            m=M.create(spec);O.request_approval(tid,m["id"]);M.approve(tid,m["id"],m["payload"]["plan_digest"],"Harness approval of fixed offline work; not a scientific endorsement")
            for _ in range(len(tasks)+2):asyncio.run(M.tick())
            m=M.get(m["id"]);assert m["status"]=="awaiting_review",m
            extra_reviews=0
            if spec.collaboration:
                from backend.agent import collaboration
                for dispute in collaboration.monitor(tid,m["id"])["disputes"]:
                    if dispute["status"]=="open":
                        collaboration.resolve(tid,m["id"],dispute["id"],dispute["revision"],"Harness simulated PI follow-up: technical evidence retained, no scientific claim approved");extra_reviews+=1
            O.review(tid,m["id"],"Harness simulated oversight; scientific claims remain separate")
            attempts=sum(t["payload"]["attempts"] for t in m["tasks"])
            rows.append({"workflow":name,"mode":mode,"logical_roles":len(spec.team.agents) if spec.team else 1,"workstreams":len(spec.collaboration.workstreams) if spec.collaboration else 1,"wall_seconds":time.perf_counter()-start,"executions":attempts,"verified_completion":True,"quality_indicator":"Bounded technical contract completion, not a scientific quality score","reasoning_calls":m["payload"]["reasoning_calls"],"provider_tokens":None,"currency_cost":None,"gpu_seconds":0,"human_gate_actions":3+extra_reviews,"retries":sum(max(0,t["payload"]["attempts"]-1) for t in m["tasks"]),"mission_id":m["id"]})
            mission_ids.append((tid,m["id"]));return m
        modes=["single"] if args.stage=="6.0" else ["single","multi"] if args.stage=="6.3" else ["single","fixed","adaptive"]
        for mode in modes:execute("Literature inspection",a,[{"id":"inspect","capability":"paper.inspect","args":{"paper_ids":records["paper_ids"][:2]}},{"id":"report","capability":"mission.report","depends_on":["inspect"]}],["workspace_write"],mode)
        workspaces=[]
        for engine in ("openscience","feynman"):
            w=W.link(b,W.WorkspaceInput(engine=engine));path=Path(w["path"])/"fixture.md"
            path.write_text("# Harness fixture\nNot an external engine session.\n","utf-8");os.utime(path,(time.time()-10,time.time()-10));workspaces.append(w)
        for mode in modes:execute("Federated artifact reconciliation",b,[{"id":"science","capability":"workspace.sync","args":{"workspace_id":workspaces[0]["id"]}},{"id":"feynman","capability":"workspace.sync","args":{"workspace_id":workspaces[1]["id"]}},{"id":"report","capability":"mission.report","depends_on":["science","feynman"]}],["workspace_write"],mode)
        protocol=P.create(ExperimentProtocol(topic_id=a,hypothesis="Fixed smoothing reduces noise in generated smooth images"))
        for mode in modes:
            for repeat in range(2):
                protocol=P.approve(a,protocol["id"],protocol["digest"],"Harness fixed CPU approval / independent fresh-process reproduction")
                cpu_tasks=[{"id":"experiment","capability":"experiment.run","args":{"protocol_id":protocol["id"],"protocol_digest":protocol["digest"],"approval_nonce":protocol["approval"]["nonce"]}},{"id":"report","capability":"mission.report","depends_on":["experiment"]}]
                if args.stage=="6.3":cpu_tasks.insert(0,{"id":"inspect","capability":"paper.inspect","args":{"paper_ids":records["paper_ids"][:2]}});cpu_tasks[-1]["depends_on"].append("inspect")
                execute("CPU reproducibility "+str(repeat+1),a,cpu_tasks,["workspace_write","compute"],mode)
        verification=V.verify_run(a,P.runs(a)[0]["id"]);assert verification["status"]=="passed" and verification["reproduction_run_id"]
        fake=G.create(a,G.ClaimInput(text="Invented paper claim",evidence=[G.EvidenceInput(source_id="doi:10.1234/harness-unresolved")]))
        assert G.evaluate(a,fake["id"])["checks"][0]["outcome"]=="unverifiable"
        interrupted=M.create(MissionSpec(topic_id=a,objective="Outage injection",permissions=[],control=common,tasks=[{"id":"inspect","capability":"paper.inspect"}]))
        with S.db() as c:
            c.execute("UPDATE missions SET status='running' WHERE id=?",(interrupted["id"],))
            c.execute("UPDATE mission_tasks SET status='running' WHERE mission_id=?",(interrupted["id"],))
        M.recover();asyncio.run(M.tick());assert M.get(interrupted["id"])["status"]=="interrupted"
        audits=[L.export(tid) for tid in (a,b)];assert all(audit["project_chain_valid"] for audit in audits)
        probes=[]
        if args.probe_engines:
            from backend.execution.tools import which,NO_WINDOW
            from backend.core.telemetry import redact
            env=os.environ.copy();env.update({"OPENSCIENCE_DATA_DIR":str(Path(temporary)/"os-data"),"OPENSCIENCE_CONFIG_DIR":str(Path(temporary)/"os-config"),"OPENSCIENCE_TEST_HOME":temporary,"OPENSCIENCE_DISABLE_AUTOUPDATE":"1"})
            for engine in ("openscience","feynman"):
                binary=which(engine)
                for option in ("--version","--help"):
                    if not binary:probes.append({"engine":engine,"option":option,"status":"unavailable"});continue
                    try:
                        prefix=["cmd","/d","/c",binary] if Path(binary).suffix.lower() in (".cmd",".bat") else [binary]
                        result=subprocess.run([*prefix,option],cwd=temporary,env=env,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=25,creationflags=NO_WINDOW)
                        probes.append({"engine":engine,"option":option,"exit":result.returncode,"output":redact(result.stdout+result.stderr)[:18000]})
                    except (OSError,subprocess.TimeoutExpired) as exc:probes.append({"engine":engine,"option":option,"error":type(exc).__name__})
        def portable(value):
            if isinstance(value,dict):return {k:portable(v) for k,v in value.items()}
            if isinstance(value,list):return [portable(v) for v in value]
            return value.replace(temporary,"<temporary-data>") if isinstance(value,str) else value
        output=args.output or ROOT/"artifacts"/("v"+args.stage.replace(".",""));output.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(output/"measurements.zip","w",compression=zipfile.ZIP_DEFLATED) as archive:
            for run in P.runs(a):
                for trial in run["trials"]:
                    folder=Path(trial["payload"]["artifact"]["path"]).parent
                    for name in ("request.json","observations.json","stdout.log","stderr.log"):archive.write(folder/name,f"{run['id']}/{trial['id']}/{name}")
            for tid,mid in mission_ids:
                for task in M.get(mid,tid)["tasks"]:
                    for index,ref in enumerate(task["payload"].get("result",{}).get("artifacts",[])):
                        path=O.artifact(tid,mid,task["id"],index)
                        archive.write(path,f"missions/{mid}/{task['id']}/{path.name}")
            for tid,audit in zip((a,b),audits):archive.writestr("audit/"+tid+".json",json.dumps(audit,ensure_ascii=False))
        import hashlib
        with zipfile.ZipFile(output/"measurements.zip") as archive:
            assert archive.testzip() is None
            for run in P.runs(a):
                for trial in run["trials"]:
                    assert hashlib.sha256(archive.read(f"{run['id']}/{trial['id']}/observations.json")).hexdigest()==trial["payload"]["artifact"]["sha256"]
            events=sorted([e for audit in audits for e in audit["events"]],key=lambda e:e["seq"]);previous=""
            for event in events:
                item={k:event[k] for k in ("topic_id","entity_id","kind","at","previous_hash","payload")}
                assert item["previous_hash"]==previous and L.digest(item)==event["hash"]
                previous=event["hash"]
        snapshots=[]
        for tid,mid in mission_ids:
            m=M.get(mid,tid);snapshot={"project_id":S.project_id(),"topic_id":tid,"mission":m}
            if m["payload"]["spec"].get("collaboration"):
                from backend.agent import collaboration
                snapshot["collaboration"]={k:v for k,v in collaboration.monitor(tid,mid).items() if k!="mission"}
            snapshots.append(snapshot)
        source_files=sorted([*ROOT.glob("backend/**/*.py"),*ROOT.glob("frontend/assets/*.js"),*ROOT.glob("frontend/assets/*.css"),*ROOT.glob("tools/*.py"),ROOT/"frontend/index.html",ROOT/"start.py",ROOT/"requirements.txt"])
        source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
        identity={"source_tree_sha256":L.digest(source_hashes),"files":source_hashes,"git_parent_commit":None,"git_dirty":None,"note":"Exact source bytes are fingerprinted; parent commit plus dirty flag honestly describes a pre-commit acceptance run"}
        try:
            identity["git_parent_commit"]=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
            identity["git_dirty"]=bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip())
        except (OSError,subprocess.CalledProcessError):pass
        report={"version":config.APP_VERSION,"at":S.now(),"source_identity":identity,"status":"passed","scope":"Real local software and CPU workers; synthetic literature/workspace fixtures; no live inference/GPU or scientific endorsement","rows":rows,"verification":verification,"experiment_runs":P.runs(a),"restart":{"uncertain_status":"interrupted","automatically_repeated":False},"claims":{"unresolved_doi":"unverifiable"},"mission_reports":snapshots,"engine_probes":probes,"limitations":["No real scientific pilot signoff","No live provider billing, quota or native inference qualification","Wall time includes durable SQLite/worker overhead, not model productivity","Portable JSON paths are redacted; original hash-verifiable audits and raw measurements are in measurements.zip"]}
        (output/"harness.json").write_text(json.dumps(portable(report),indent=2,ensure_ascii=False),"utf-8")
        lines=["# Measured local research harness", "Synthetic literature/workspace fixtures; actual local code and CPU workers. These serial samples do not establish a productivity or scientific quality advantage.", "| Workflow | Mode | Domains | Logical roles | Wall seconds | Task executions | Technical completion |", "|---|---|---:|---:|---:|---:|---|"]
        for row in rows:lines.append(f"| {row['workflow']} | {row['mode']} | {row['workstreams']} | {row['logical_roles']} | {row['wall_seconds']:.3f} | {row['executions']} | {row['verified_completion']} |")
        lines.append("\nProvider tokens/currency are unknown; GPU time is zero. Simulated review actions and retries are recorded per row in harness.json. Raw artifact hashes, ZIP integrity and the original merged audit chain were checked after packaging.")
        (output/"benchmark.md").write_text("\n\n".join(lines[:2])+"\n\n"+"\n".join(lines[2:]),"utf-8")
        print(json.dumps({"status":"passed","version":config.APP_VERSION,"workflows":len(rows),"cpu_reproduction":verification["status"],"evidence":str(output)}))


if __name__=="__main__":main()
