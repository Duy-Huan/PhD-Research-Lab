"""Independent deterministic artifact checks. Never convert an agent's prose into measured data."""
import hashlib
import json
import math
import statistics
from pathlib import Path
from backend.knowledge import research_store as S
from backend.agent import decision_ledger as L
from backend.execution import protocols as P


def verify_run(tid,rid,*,_find_reproduction=True):
    P.run(tid,rid)  # A wrong Topic/ID remains a scoped lookup error.
    try:return _verify_run(tid,rid,_find_reproduction=_find_reproduction)
    except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError,OverflowError) as exc:
        return {"verifier":"deterministic-independent-recompute-v1","status":"failed","experiment_run_id":rid,"reproduction_run_id":None,"artifact_refs":[],"checks":[{"check":"persisted_record_integrity","status":"failed","detail":str(exc)[:500]}],"warnings":["Malformed or unavailable persisted evidence"],"limitations":["Evidence could not be fully checked"]}


def _verify_run(tid,rid,*,_find_reproduction=True):
    run=P.run(tid,rid);checks=[]
    def check(name,ok,detail=""):
        checks.append({"check":name,"status":"passed" if ok else "failed","detail":detail})
    p=P.get(tid,run["protocol_id"]);snapshot=p["payload"];spec=snapshot["spec"]
    if snapshot.get("kind")=="agent_code_v1":
        from backend.execution import agent_protocols
        return agent_protocols.verify(tid,run,p,find_reproduction=_find_reproduction)
    check("run_completed",run["status"]=="completed")
    check("immutable_protocol",p["digest"]==L.digest(snapshot)==run["payload"]["protocol_digest"])
    check("worker_revision",P.worker_hash()==snapshot["worker_sha256"]==run["payload"]["worker_sha256"])
    recipe=spec["dataset"];splits=snapshot["splits"]
    check("dataset_license",recipe.get("license")=="CC0-generated-fixture")
    expected_splits={k:[k+":"+str(i) for i in range(recipe[k+"_count"])] for k in ("train","validation","test")}
    check("split_integrity_and_leakage",splits==expected_splits and len(set(sum(splits.values(),[])))==sum(map(len,splits.values())))
    check("dataset_fingerprint",L.digest({"recipe":recipe,"splits":splits,"generator_sha256":snapshot["worker_sha256"]})==snapshot["dataset_fingerprint"]==run["payload"]["dataset_fingerprint"])
    recomputed=[];artifacts=[]
    for trial in run["trials"]:
        t=trial["payload"];prefix=trial["trial_key"]
        if trial["status"]!="completed":check(prefix+":completed",False);continue
        try:
            folder=S.safe_child(S.store_dir(),"experiments",rid,trial["id"])
            artifact=t["artifact"];path=S.safe_child(folder,"observations.json")
            if str(path)!=artifact["path"]:raise ValueError("Artifact pointer outside trial")
            raw=path.read_bytes()
            if len(raw)>spec["max_artifact_mb"]*1024*1024:raise ValueError("Artifact exceeds budget")
            check(prefix+":sha256",hashlib.sha256(raw).hexdigest()==artifact["sha256"] and len(raw)==artifact["bytes"])
            check(prefix+":logs",S.safe_child(folder,"stdout.log").is_file() and S.safe_child(folder,"stderr.log").is_file())
            data=json.loads(raw);request=t["request"]
            check(prefix+":manifest",t["protocol_digest"]==p["digest"] and t["dataset_fingerprint"]==snapshot["dataset_fingerprint"] and t["worker_sha256"]==snapshot["worker_sha256"] and request["seeds"]==spec["seeds"] and request["recipe"]==recipe and data["alpha"]==request["alpha"] and data["split"]==request["split"])
            if request["split"] not in ("validation","test") or request["alpha"] not in [0,*spec["alphas"]]:raise ValueError("Unregistered method or evaluation split")
            expected={(seed,sample) for seed in spec["seeds"] for sample in splits[request["split"]]}
            observed={(o["seed"],o["sample_id"]) for o in data["observations"]}
            check(prefix+":samples",expected==observed and len(data["observations"])==len(expected))
            recalculated=[];numeric_ok=True;conformity=True
            from backend.execution.denoising_worker import image
            for o in data["observations"]:
                clean,noisy,pred=o["clean"],o["noisy"],o["predicted"]
                if not len(clean)==len(noisy)==len(pred)==recipe["side"]**2:raise ValueError("Tensor shape mismatch")
                if any(not isinstance(v,(int,float)) or not math.isfinite(v) for values in (clean,noisy,pred) for v in values):raise ValueError("Non-finite observations")
                generated_clean,generated_noisy=image(o["seed"],o["sample_id"],recipe["side"],recipe["noise_std"])
                conformity &= clean==generated_clean and noisy==generated_noisy
                # Independent metric implementation, not the reporting worker's metrics().
                mse=math.fsum((float(a)-float(b))**2 for a,b in zip(clean,pred))/len(clean)
                if mse<=0:raise ValueError("Invalid zero MSE in noisy fixture")
                psnr=-10*math.log10(mse)
                numeric_ok &= math.isclose(mse,o["mse"],rel_tol=1e-10,abs_tol=1e-12) and math.isclose(psnr,o["psnr_db"],rel_tol=1e-10,abs_tol=1e-10)
                side=recipe["side"];alpha=request["alpha"]
                for index,value in enumerate(pred):
                    y,x=divmod(index,side)
                    neighbors=[noisy[yy*side+xx] for yy in range(max(0,y-1),min(side,y+2)) for xx in range(max(0,x-1),min(side,x+2))]
                    expected_value=(1-alpha)*noisy[index]+alpha*math.fsum(neighbors)/len(neighbors)
                    conformity &= math.isclose(value,expected_value,rel_tol=1e-10,abs_tol=1e-12)
                recalculated.append({"seed":o["seed"],"mse":mse,"psnr_db":psnr})
            check(prefix+":metrics_recomputed",numeric_ok)
            check(prefix+":data_method_conformity",conformity)
            summary={str(seed):{k:statistics.mean(o[k] for o in recalculated if o["seed"]==seed) for k in ("mse","psnr_db")} for seed in spec["seeds"]}
            for seed,values in summary.items():
                numeric_ok &= all(math.isclose(values[k],t["summary"]["per_seed"][seed][k],rel_tol=1e-9,abs_tol=1e-10) for k in values)
            mean=statistics.mean(v["psnr_db"] for v in summary.values())
            numeric_ok &= math.isclose(mean,t["summary"]["mean_psnr_db"],rel_tol=1e-9,abs_tol=1e-10) and t["summary"]["repeat_count"]==len(spec["seeds"])
            check(prefix+":summary_matches_measurements",numeric_ok)
            recomputed.append({"split":request["split"],"alpha":request["alpha"],"per_seed":summary,"mean":mean})
            artifacts.append({"trial_key":prefix,"sha256":artifact["sha256"]})
        except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError,OverflowError) as exc:check(prefix+":artifact_readable",False,str(exc)[:500])
    validation=[r for r in recomputed if r["split"]=="validation"]
    evaluated=[r["alpha"] for r in validation]
    registered=[0,*spec["alphas"]]
    expected=registered
    if spec["stop_on_target"] and validation:
        for i,r in enumerate(validation[1:],1):
            if r["mean"]-validation[0]["mean"]>=spec["min_psnr_gain_db"]:
                expected=registered[:i+1];break
    check("registered_validation_trials",evaluated==expected)
    if validation:
        baseline=next((r for r in validation if r["alpha"]==0),None)
        selected=max(validation,key=lambda r:r["mean"])
        comparison=run["payload"].get("comparison",{})
        check("fair_baseline",baseline is not None and all(set(r["per_seed"])==set(baseline["per_seed"]) for r in validation))
        check("validation_selection",comparison.get("selected_alpha")==selected["alpha"] and comparison.get("selection_split")=="validation" and comparison.get("held_out_used_for_selection") is False)
        if baseline:
            delta=selected["mean"]-baseline["mean"]
            check("reported_gain_matches_raw",math.isclose(delta,comparison.get("paired_psnr_gain_db",float('nan')),rel_tol=1e-9,abs_tol=1e-9))
            deltas=[selected["per_seed"][str(seed)]["psnr_db"]-baseline["per_seed"][str(seed)]["psnr_db"] for seed in spec["seeds"]]
            ci=1.96*statistics.stdev(deltas)/math.sqrt(len(deltas)) if len(deltas)>1 else None
            reported_ci=comparison.get("normal_approx_ci95")
            check("uncertainty_recomputed",reported_ci is None if ci is None else isinstance(reported_ci,list) and len(reported_ci)==2 and all(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9) for a,b in zip(reported_ci,[statistics.mean(deltas)-ci,statistics.mean(deltas)+ci])))
            expected_recommendation="candidate_improvement" if len(deltas)>=3 and all(d>0 for d in deltas) and statistics.mean(deltas)>=spec["min_psnr_gain_db"] else "no_supported_improvement"
            check("recommendation_and_repeat_count",comparison.get("recommendation")==expected_recommendation and comparison.get("repeat_count")==len(deltas))
        check("held_out_evaluation",{r["alpha"] for r in recomputed if r["split"]=="test"}=={0,selected["alpha"]})
        measured_test=[r for r in recomputed if r["split"]=="test"]
        reported_test=run["payload"].get("test_evaluations",[])
        same=len(measured_test)==len(reported_test)
        for measured,reported in zip(measured_test,reported_test):
            same &= reported.get("repeat_count")==len(spec["seeds"]) and math.isclose(reported.get("mean_psnr_db",float('nan')),measured["mean"],rel_tol=1e-9,abs_tol=1e-9)
            same &= set(reported.get("per_seed",{}))==set(measured["per_seed"])
            for seed,values in measured["per_seed"].items():
                same &= all(math.isclose(reported.get("per_seed",{}).get(seed,{}).get(k,float('nan')),v,rel_tol=1e-9,abs_tol=1e-9) for k,v in values.items())
        check("reported_test_metrics",same)
    else:check("validation_measurements",False)
    check("trial_budget",len(run["trials"])<=spec["max_trials"])
    others=[r for r in P.runs(tid) if r["id"]!=rid and r["status"]=="completed" and r["payload"]["protocol_digest"]==run["payload"]["protocol_digest"] and r["approval_nonce"]!=run["approval_nonce"]]
    reproduction=None
    if _find_reproduction:
        for r in others:
            if sorted((t["trial_key"],t["payload"].get("artifact",{}).get("sha256")) for t in r["trials"])==sorted((t["trial_key"],t["payload"].get("artifact",{}).get("sha256")) for t in run["trials"]) and verify_run(tid,r["id"],_find_reproduction=False)["status"]=="passed":
                reproduction=r["id"];break
    passed=all(c["status"]=="passed" for c in checks)
    return {"verifier":"deterministic-independent-recompute-v1","status":"passed" if passed else "failed","checks":checks,"artifact_refs":artifacts,
            "reproduction_run_id":reproduction,"warnings":[] if reproduction else ["Independent fresh-process reproduction is not recorded"],
            "limitations":["Generated CPU fixture only; external methodology/novelty is not certified","Small-n intervals are approximate"],"experiment_run_id":rid,"protocol_digest":p["digest"]}
