"""Independently verify current stages and exact historical v6 harness bundles.

No model, live scholarly API, GPU workload or user project is used. Historical code is
exported from Git into a validated temporary directory; the active checkout is untouched.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
import os
import platform
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASES = {"6.0": ("312e9b0", "6.0.0-preview.1"), "6.2": ("40e1173", "6.2.0-preview.1"), "6.3": ("459fc13", "6.3.0-preview.1")}
MODES = {"6.0": ["single"], "6.2": ["single", "fixed", "adaptive"], "6.3": ["single", "multi"]}
WORKFLOWS = ["Literature inspection", "Federated artifact reconciliation", "CPU reproducibility 1", "CPU reproducibility 2"]


class VerificationError(ValueError):
    pass


def require(condition, message):
    # Unlike assert, release verification remains active under python -O.
    if not condition:
        raise VerificationError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def verify_bundle(folder, stage, *, version=None, source_root=None, require_raw=False):
    folder = Path(folder)
    report = json.loads((folder / "harness.json").read_text("utf-8"))
    require(stage in MODES, "Unsupported stage; v6.1 has no independent release")
    require(report["status"] == "passed", "Harness did not pass")
    require(report.get("stage", stage) == stage, "Reported stage mismatch")
    if "enabled_features" in report:
        flags = report["enabled_features"]
        require(flags["enabled"] is True and flags["team_enabled"] == (stage != "6.0") and flags["multi_team_enabled"] == (stage == "6.3"), "Stage feature flags mismatch")
    if version:
        require(report["version"] == version, "Application version mismatch")
    rows = report["rows"]
    require(Counter((r["mode"], r["workflow"]) for r in rows) == Counter((m, w) for m in MODES[stage] for w in WORKFLOWS), "Missing/duplicated stage workflow or mode")
    require(len({r["mission_id"] for r in rows}) == len(rows), "Duplicate mission identity")
    for r in rows:
        require(r["verified_completion"] is True and r["reasoning_calls"] == 0 and r["gpu_seconds"] == 0, "Unexpected completion/inference/GPU activity")
        require(math.isfinite(r["wall_seconds"]) and r["wall_seconds"] >= 0 and r["executions"] > 0, "Invalid measured execution counters")
    require(report["restart"] == {"uncertain_status": "interrupted", "automatically_repeated": False}, "Uncertain restart repeated work")
    require(report["claims"]["unresolved_doi"] == "unverifiable", "Unsupported citation promoted")
    require(report["verification"]["status"] == "passed" and report["verification"]["reproduction_run_id"], "Independent reproduction missing")
    limitations = []
    identity = report.get("source_identity")
    legacy_format = not identity and stage in ("6.0", "6.2")
    if identity:
        require(identity.get("source_tree_sha256") == digest(identity.get("files", {})), "Source manifest digest mismatch")
    else:
        require(legacy_format and not require_raw, "Source identity missing")
        limitations.append("Original release bundle has no embedded source manifest; identity is supplied by the exact Git export")
    if source_root and identity:
        source_root = Path(source_root).resolve()
        for name, expected in identity["files"].items():
            path = (source_root / name).resolve()
            require(path.is_relative_to(source_root) and path.is_file(), "Source path missing/outside root")
            require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, "Source bytes changed: " + name)
    counts = {"missions": len(rows), "task_artifacts": 0, "experiment_trials": 0, "raw_samples": 0,
              "audit_events": 0, "role_handoffs": 0, "handoffs": 0, "receipts": 0, "raw_control_plane": False,
              "source_manifest_verified": bool(identity)}
    with zipfile.ZipFile(folder / "measurements.zip") as archive:
        require(archive.testzip() is None, "ZIP integrity failed")
        require(len(archive.namelist()) == len(set(archive.namelist())), "Duplicate ZIP entry")
        has_raw = "control-plane.json" in archive.namelist()
        require(not require_raw or has_raw, "Exact original control-plane snapshots missing")
        counts["raw_control_plane"] = has_raw
        snapshots = json.loads(archive.read("control-plane.json")) if has_raw else report["mission_reports"]
        if not has_raw:
            limitations.append("Bundle format lacks raw control-plane snapshots; portable handoff payloads cannot be independently rehashed after path redaction")
        if legacy_format:
            limitations.append("Original release ZIP does not include Mission report files; only experiment arrays, requests, logs and audit chains can be independently checked")
        require({s["mission"]["id"] for s in snapshots} == {r["mission_id"] for r in rows}, "Mission snapshots differ from benchmark rows")
        row_by_id = {r["mission_id"]: r for r in rows}
        topic_ids = set()
        for snapshot in snapshots:
            m = snapshot["mission"]; topic_ids.add(m["topic_id"])
            require(m["status"] == "completed" and snapshot["topic_id"] == m["topic_id"], "Mission completion/Topic scope mismatch")
            spec = m["payload"]["spec"]
            require(m["payload"]["reasoning_calls"] == 0 and sum(t["payload"]["attempts"] for t in m["tasks"]) == row_by_id[m["id"]]["executions"], "Execution counters differ from Mission trace")
            require(bool(spec.get("team")) == (stage != "6.0"), "Stage team feature mismatch")
            require(bool(spec.get("collaboration")) == (stage == "6.3" and row_by_id[m["id"]]["mode"] == "multi"), "Stage workstream feature mismatch")
            if has_raw and spec.get("team"):
                require("team" in snapshot, "Task envelope snapshot missing")
                tasks = {t["id"]: t for t in m["tasks"]}
                assignments = {a["task_id"]: a for a in spec["team"]["assignments"]}
                envelopes = snapshot["team"]["handoffs"]
                expected = {(t["id"], d) for t in spec["tasks"] for d in t["depends_on"]}
                actual = [(e["task_id"], e["dependency_id"]) for e in envelopes]
                require(len(actual) == len(set(actual)) and set(actual) == expected, "Missing/duplicate task envelope")
                for envelope in envelopes:
                    e = envelope["payload"]
                    require(e["mission_id"] == m["id"] and e["topic_id"] == m["topic_id"] and e["trust"] == "untrusted", "Task envelope scope/trust mismatch")
                    require(e["sender"] == assignments[e["dependency_task_id"]]["owner"] and e["receiver"] == assignments[e["task_id"]]["owner"], "Task envelope owner mismatch")
                    require(e["input_digest"] == digest(tasks[e["dependency_task_id"]]["payload"]["result"]), "Task envelope source digest mismatch")
                counts["role_handoffs"] += len(envelopes)
            for task in m["tasks"]:
                require(task["status"] == "completed" and task["payload"]["attempts"] == 1, "Task failed or unexpectedly repeated")
                for ref in task["payload"].get("result", {}).get("artifacts", []):
                    if legacy_format:
                        continue
                    name = ref["path"].replace("\\", "/").rsplit("/", 1)[-1]
                    raw = archive.read(f"missions/{m['id']}/{task['id']}/{name}")
                    require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"], "Mission artifact checksum/size mismatch")
                    counts["task_artifacts"] += 1
            collaboration = snapshot.get("collaboration")
            if collaboration:
                messages, receipts = collaboration["messages"], collaboration["receipts"]
                require(len({r["message_id"] for r in receipts}) == len(receipts), "Duplicate handoff receipt")
                receipt_map = {r["message_id"]: r for r in receipts}
                tasks = {t["id"]: t for t in m["tasks"]}
                for message in messages:
                    order = message["payload"]; receipt = receipt_map.get(message["id"])
                    require(message["status"] == "acknowledged" and receipt is not None, "Handoff missing acknowledgment")
                    require(order["topic_id"] == m["topic_id"] and order["mission_id"] == m["id"] and order["project_id"] == snapshot["project_id"], "Cross-scope handoff")
                    require(receipt["receiver_team"] == order["target_team"] and receipt["payload"]["message_digest"] == message["digest"], "Receipt identity/digest mismatch")
                    if has_raw:
                        require(digest(order) == message["digest"], "Handoff payload digest mismatch")
                        source = tasks[order["source_task"]]["payload"]["result"]
                        require(digest(source) == order["evidence"]["result_digest"] == receipt["payload"]["source_result_digest"], "Handoff result digest mismatch")
                require(set(receipt_map) == {x["id"] for x in messages}, "Orphan handoff receipt")
                require(all(d["status"] != "open" for d in collaboration["disputes"]), "Open dispute hidden by completion")
                counts["handoffs"] += len(messages); counts["receipts"] += len(receipts)
        require(len(topic_ids) == 2, "Two-Topic benchmark isolation not exercised")
        runs = report.get("experiment_runs")
        if runs is None and legacy_format:
            runs = list({r["id"]: r for snapshot in snapshots for r in snapshot.get("experiments", [])}.values())
        require(runs is not None, "Experiment run records missing")
        require(len(runs) == 2 * len(MODES[stage]), "Missing independent CPU runs")
        require(len({r["approval_nonce"] for r in runs}) == len(runs), "Experiment approval nonce reused")
        repetitions = {}
        for run in runs:
            require(run["status"] == "completed" and run["topic_id"] in topic_ids, "Experiment failed/out of scope")
            signatures, summaries, datasets = {}, {}, {}
            if source_root:
                worker = Path(source_root) / "backend/execution/denoising_worker.py"
                require(hashlib.sha256(worker.read_bytes()).hexdigest() == run["payload"]["worker_sha256"], "Executed worker revision mismatch")
            for trial in run["trials"]:
                require(trial["status"] == "completed", "Incomplete experiment trial")
                prefix = f"{run['id']}/{trial['id']}/"
                raw = archive.read(prefix + "observations.json")
                ref = trial["payload"]["artifact"]
                require(hashlib.sha256(raw).hexdigest() == ref["sha256"] and len(raw) == ref["bytes"], "Trial artifact checksum/size mismatch")
                request = json.loads(archive.read(prefix + "request.json"))
                require(request == trial["payload"]["request"], "Trial request differs from manifest")
                for log in ("stdout.log", "stderr.log"):
                    archive.read(prefix + log)
                data = json.loads(raw); groups = {}
                require(data["split"] == request["split"] and data["alpha"] == request["alpha"], "Trial split/alpha drift")
                seen = set()
                for observation in data["observations"]:
                    clean, predicted, noisy = observation["clean"], observation["predicted"], observation["noisy"]
                    require(len(clean) == len(predicted) == len(noisy) == request["recipe"]["side"] ** 2, "Array shape drift")
                    require(all(math.isfinite(v) for v in clean + predicted + noisy), "Nonfinite raw data")
                    dataset_key = (request["split"], observation["seed"], observation["sample_id"])
                    require(dataset_key not in datasets or datasets[dataset_key] == (clean, noisy), "Unfair baseline/variant data")
                    datasets[dataset_key] = (clean, noisy)
                    mse = sum((x-y)**2 for x,y in zip(clean, predicted)) / len(clean)
                    require(mse > 0 and math.isclose(mse, observation["mse"], rel_tol=1e-12), "Raw MSE does not match claimed metric")
                    require(math.isclose(10*math.log10(1/mse), observation["psnr_db"], rel_tol=1e-12), "Raw PSNR does not match claimed metric")
                    sample = (observation["seed"], observation["sample_id"])
                    require(sample not in seen and observation["sample_id"].startswith(request["split"] + ":"), "Duplicate sample or split leakage")
                    seen.add(sample); groups.setdefault(str(observation["seed"]), []).append(observation)
                    if request["alpha"] == 0:
                        require(predicted == observation["noisy"], "Baseline changed")
                    counts["raw_samples"] += 1
                require(set(groups) == {str(s) for s in request["seeds"]}, "Missing/wrong seed")
                require(len(seen) == len(request["seeds"]) * request["recipe"][request["split"] + "_count"], "Wrong sample count")
                summary = trial["payload"]["summary"]
                require(summary["repeat_count"] == len(groups), "Reported repeat count mismatch")
                for seed, observations in groups.items():
                    for metric in ("mse", "psnr_db"):
                        mean = statistics.mean(o[metric] for o in observations)
                        require(math.isclose(mean, summary["per_seed"][seed][metric], rel_tol=1e-12), "Summary differs from raw observations")
                require(math.isclose(summary["mean_psnr_db"], statistics.mean(x["psnr_db"] for x in summary["per_seed"].values()), rel_tol=1e-12), "Aggregate PSNR mismatch")
                signatures[trial["trial_key"]] = hashlib.sha256(raw).hexdigest()
                summaries[(request["split"], request["alpha"])] = summary
                counts["experiment_trials"] += 1
            key = run["payload"]["protocol_digest"]
            if key in repetitions:
                require(signatures == repetitions[key], "Independent CPU reproduction differs")
            repetitions[key] = signatures
            require(run["payload"]["comparison"]["selection_split"] == "validation" and run["payload"]["comparison"]["held_out_used_for_selection"] is False, "Test set used for selection")
            comparison = run["payload"]["comparison"]
            candidates = {alpha: s for (split, alpha), s in summaries.items() if split == "validation" and alpha != 0}
            selected = max(candidates, key=lambda alpha:candidates[alpha]["mean_psnr_db"])
            require(comparison["selected_alpha"] == selected, "Candidate selection differs from measured validation")
            baseline = summaries[("validation", 0)]
            gains = [candidates[selected]["per_seed"][seed]["psnr_db"]-value["psnr_db"] for seed,value in baseline["per_seed"].items()]
            mean = statistics.mean(gains)
            require(math.isclose(mean, comparison["paired_psnr_gain_db"], rel_tol=1e-12), "Reported improvement differs from raw measurements")
            ci = [mean-1.96*statistics.stdev(gains)/math.sqrt(len(gains)), mean+1.96*statistics.stdev(gains)/math.sqrt(len(gains))]
            require(all(math.isclose(a,b,rel_tol=1e-12) for a,b in zip(ci,comparison["normal_approx_ci95"])) and len(comparison["normal_approx_ci95"]) == 2, "Confidence interval differs from raw paired observations")
            require(run["payload"]["test_evaluations"] == [summaries[("test", 0)], summaries[("test", selected)]], "Held-out metrics differ from raw trials")
        events = []
        for name in archive.namelist():
            if name.startswith("audit/") and name.endswith(".json"):
                audit = json.loads(archive.read(name)); require(audit["project_chain_valid"] is True, "Ledger exporter reports invalid chain")
                events.extend(audit["events"])
        previous = ""
        require(bool(events) and len({e["seq"] for e in events}) == len(events), "Missing/duplicated audit sequence")
        for event in sorted(events, key=lambda e:e["seq"]):
            item = {k:event[k] for k in ("topic_id", "entity_id", "kind", "at", "previous_hash", "payload")}
            require(item["previous_hash"] == previous and digest(item) == event["hash"], "Audit hash chain broken")
            previous = event["hash"]; counts["audit_events"] += 1
    return {"stage": stage, "application_version": report["version"], "passed": True, "checks": counts, "limitations": limitations}


def run_command(command, cwd, log):
    env = os.environ.copy()
    for name in ("PHDLAB_DATA_DIR", "PYTHONOPTIMIZE", "PYTHONPATH"):
        env.pop(name, None)
    env["PYTHONIOENCODING"] = "utf-8"
    with Path(log).open("wb") as stream:
        result = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    require(result.returncode == 0, f"Command failed ({result.returncode}); see {log}")


def historical_tree(commit, target):
    paths = ["backend", "frontend", "tools", "tests", "requirements.txt", "requirements-dev.txt", "start.py", "mcp_stdio_bridge.py", ".coveragerc"]
    data = subprocess.check_output(["git", "archive", "--format=tar", commit, *paths], cwd=ROOT)
    target = Path(target).resolve()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            path = (target / member.name).resolve()
            require(path.is_relative_to(target) and (member.isdir() or member.isfile()), "Unsafe Git archive entry")
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())


def run_contracts(output):
    """Use the established isolated test runner and retain each actual test outcome."""
    script = '''import json,time,unittest
from pathlib import Path
from tools import run_tests
class RecordingResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.cases=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.cases.append({"test":test.id(),"status":"passed",**({"evidence":test.evidence} if hasattr(test,"evidence") else {})})
    def addSkip(self,test,reason):
        super().addSkip(test,reason);self.cases.append({"test":test.id(),"status":"skipped","reason":reason})
    def addFailure(self,test,error):
        super().addFailure(test,error);self.cases.append({"test":test.id(),"status":"failed"})
    def addError(self,test,error):
        super().addError(test,error);self.cases.append({"test":test.id(),"status":"error"})
class RecordingRunner(unittest.TextTestRunner):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs,resultclass=RecordingResult)
    def run(self,suite):
        start=time.perf_counter();result=super().run(suite)
        Path(__import__("sys").argv[1]).write_text(json.dumps({"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"cases":result.cases,"seconds":time.perf_counter()-start,"passed":result.wasSuccessful()},indent=2)+"\\n",encoding="utf-8")
        return result
unittest.TextTestRunner=RecordingRunner
raise SystemExit(run_tests.main(["test_research_os","test_teams","test_workstreams","test_missions","test_protocols","test_governance","test_guard","test_harness_verification"]))
'''
    run_command([sys.executable, "-B", "-c", script, str(output / "contracts.json")], ROOT, output / "contracts.log")
    return json.loads((output / "contracts.json").read_text("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/harness-verification")
    parser.add_argument("--verify-only", type=Path)
    parser.add_argument("--stage", choices=MODES)
    parser.add_argument("--historical", action="store_true", help="Also execute exact original release commits")
    args = parser.parse_args()
    if args.verify_only:
        require(args.stage is not None, "--verify-only requires --stage")
        print(json.dumps(verify_bundle(args.verify_only, args.stage))); return
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    results = []; start = time.perf_counter()
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps({"passed": False, "status": "running", "results": []}) + "\n", "utf-8")
    print("Running v6 governance, recovery, resources and adversarial verifier contracts", flush=True)
    contracts = run_contracts(output)
    # Separate processes and data for every stage. Explicitly record failures; never reuse old success.
    jobs = [("current", stage, None) for stage in MODES]
    if args.historical:
        jobs += [("historical", stage, commit) for stage, (commit, _) in RELEASES.items()]
    for scope, stage, commit in jobs:
        folder = output / scope / ("v" + stage.replace(".", "")); folder.mkdir(parents=True, exist_ok=True)
        print(f"Running {scope} stage {stage}", flush=True)
        try:
            if commit:
                full_commit = subprocess.check_output(["git", "rev-parse", commit], cwd=ROOT, text=True).strip()
                with tempfile.TemporaryDirectory(prefix="phdlab-v6-history-") as temporary:
                    tree = Path(temporary).resolve()
                    require(tree.parent == Path(tempfile.gettempdir()).resolve() and tree.name.startswith("phdlab-v6-history-"), "Unexpected historical temporary path")
                    historical_tree(commit, tree)
                    run_command([sys.executable, "-B", str(tree / "tools/research_harness.py"), "--stage", stage], tree, folder / "execution.log")
                    generated = tree / "artifacts" / ("v" + stage.replace(".", ""))
                    for name in ("harness.json", "measurements.zip"):
                        shutil.copyfile(generated / name, folder / name)
                    if (generated / "benchmark.md").is_file():
                        shutil.copyfile(generated / "benchmark.md", folder / "benchmark.md")
                    verified = verify_bundle(folder, stage, version=RELEASES[stage][1], source_root=tree)
                    verified["historical_commit"] = full_commit
            else:
                run_command([sys.executable, "-B", str(ROOT / "tools/research_harness.py"), "--stage", stage, "--output", str(folder)], ROOT, folder / "execution.log")
                verified = verify_bundle(folder, stage, source_root=ROOT, require_raw=True)
            results.append({"scope": scope, **verified})
        except Exception as exc:
            results.append({"scope": scope, "stage": stage, "passed": False, "error": str(exc)})
        summary_path.write_text(json.dumps({"passed": len(results) == len(jobs) and contracts["passed"] and all(r["passed"] for r in results), "status": "complete" if len(results) == len(jobs) else "running", "results": results, "contracts": contracts, "seconds": time.perf_counter()-start,
            "environment": {"python": sys.version, "platform": platform.platform(), "dependency_environment": sys.prefix.replace(str(ROOT), "<workspace>"), "historical_dependency_lock_recreated": False},
            "v6.1": "Compatibility layer verified via test_teams; no separate v6.1 spec, release commit or benchmark stage", "scientific_release_qualified": False}, indent=2) + "\n", "utf-8")
        print(f"{scope} {stage}: {'PASS' if results[-1]['passed'] else results[-1]['error']}", flush=True)
    lines = ["# v6 harness verification", "", "Current stages and exact historical release code, run in isolated processes with the currently installed Python/dependencies. This does not recreate historical dependency locks or certify real scientific autonomy.", "", "| Code | Stage | Application version | Missions | CPU trials | Raw samples recomputed | Role envelopes | Cross-team receipts | Result |", "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for result in results:
        c = result.get("checks", {})
        verdict = "PASS with export limits" if result.get("limitations") else "PASS"
        if not result["passed"]: verdict = "FAIL: " + result["error"]
        lines.append("| " + " | ".join(map(str, [result["scope"] + (" · " + result["historical_commit"][:7] if "historical_commit" in result else ""), result["stage"], result.get("application_version", "unknown"), c.get("missions", 0), c.get("experiment_trials", 0), c.get("raw_samples", 0), c.get("role_handoffs", 0), c.get("receipts", 0), verdict])) + " |")
    lines += ["", f"Governance/resource/recovery/verifier contracts: {contracts['tests']} tests; failures {contracts['failures']}, errors {contracts['errors']}. Exact case outcomes, real process-exit evidence and each original-format limitation are in [summary.json](summary.json).", "", "v6.1 is a tested compatibility layer, not a separately released version. GPU/Docker containment, live inference/billing and a real scientific pilot remain outside this offline qualification."]
    (output / "verification.md").write_text("\n".join(lines) + "\n", "utf-8")
    require(all(r["passed"] for r in results), "One or more v6 harness checks failed; see summary.json")


if __name__ == "__main__":
    main()
