"""Agent-written experiments under the same governance as the built-in protocol (v6.6.4, agent/PLAN_6.6.4_L3.md A2).

create   snapshots the active code project (content-addressed copy + per-file sha256) and pins the environment
         (interpreter, version and installed packages, or a Docker image digest). The snapshot digest is what the
         researcher approves; a later edit of the project never changes an approved protocol.
execute  runs every registered condition x seed once, each in a fresh process on a fresh copy of the frozen code, after
         re-checking the code and the environment. The code writes `$PHDLAB_OUT/metrics.json` = {"metrics": {...}}.
verify   independently re-reads the raw metric files, recomputes the aggregation and the paired comparison, and looks
         for a reproduction: another approved run of the same digest with matching metrics.

The runner records measurements only. It never installs packages, edits code or retries, and the result always
needs scientific review.
"""
import asyncio
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import time
from pathlib import Path, PurePosixPath

from backend.agent import decision_ledger as L
from backend.execution.protocol_contracts import AgentCodeProtocol
from backend.knowledge import research_store as S

KIND = "agent_code_v1"
SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", ".ipynb_checkpoints", ".mypy_cache",
             ".pytest_cache", ".vscode", ".idea", "outputs", "runs", "wandb"}
MAX_FILES = 500
MAX_BYTES = 20 * 1024 * 1024
PROBE = ("import json,platform,sys\nfrom importlib import metadata\n"
         "print(json.dumps({'version':sys.version,'implementation':platform.python_implementation(),"
         "'packages':sorted({(d.metadata['Name'] or '?').lower()+'=='+d.version for d in metadata.distributions()})}))")


def _code_store(digest: str) -> Path:
    return S.safe_child(S.store_dir(), "protocol-code", digest)


def _collect(root: Path, include: list) -> list[tuple[str, Path]]:
    picked: dict[str, Path] = {}

    def add(path: Path):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"Symbolic links are not frozen: {rel}")
        picked[rel] = path

    def walk(folder: Path):
        for item in sorted(folder.iterdir()):
            if item.is_dir() and not item.is_symlink():
                if item.name not in SKIP_DIRS and not item.name.startswith("."):
                    walk(item)
            elif item.is_file() or item.is_symlink():
                add(item)
            if len(picked) > MAX_FILES:
                raise ValueError(f"More than {MAX_FILES} files; list the needed files or folders in `include`")

    for rel in include or ["."]:
        target = S.safe_child(root, *PurePosixPath(rel.replace("\\", "/")).parts) if rel != "." else root
        if target.is_dir():
            walk(target)
        elif target.is_file():
            add(target)
        else:
            raise ValueError(f"Not found in the code project: {rel}")
    return sorted(picked.items())


def snapshot_code(root: Path, include: list, entrypoint: str) -> tuple[str, list]:
    """Copy the selected files into a content-addressed store; return (code digest, manifest)."""
    files = _collect(root, include)
    manifest, blobs, total = [], {}, 0
    for rel, path in files:
        raw = path.read_bytes()
        total += len(raw)
        if total > MAX_BYTES:
            raise ValueError(f"Code snapshot over {MAX_BYTES // (1024 * 1024)} MB; keep data and outputs out of it")
        manifest.append({"path": rel, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        blobs[rel] = raw
    entry = PurePosixPath(entrypoint.replace("\\", "/")).as_posix()
    if entry not in blobs:
        raise ValueError(f"The entrypoint {entrypoint} is not in the frozen files")
    digest = L.digest(manifest)
    store = _code_store(digest)
    if not store.is_dir():
        tmp = store.with_name(store.name + ".tmp-" + S.uid()[:8])
        for rel, raw in blobs.items():
            out = S.safe_child(tmp, *rel.split("/"))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(raw)
        try:
            tmp.rename(store)
        except OSError:  # another snapshot of the same content won the race
            shutil.rmtree(tmp, ignore_errors=True)
    return digest, manifest


def check_code(digest: str, manifest: list) -> list[str]:
    """Paths whose frozen copy is missing or changed (empty when intact)."""
    store, bad = _code_store(digest), []
    if L.digest(manifest) != digest:
        return ["<manifest>"]
    for f in manifest:
        try:
            raw = S.safe_child(store, *f["path"].split("/")).read_bytes()
            if hashlib.sha256(raw).hexdigest() != f["sha256"] or len(raw) != f["bytes"]:
                bad.append(f["path"])
        except (OSError, ValueError):
            bad.append(f["path"])
    return bad


def _python() -> str:
    from backend.execution import sandbox
    return sandbox._local_python()


def environment(spec: dict) -> dict:
    """The pinned environment of a protocol, with the digest that execute re-checks."""
    if spec["engine"] == "docker":
        env = {"engine": "docker", "image": spec["docker_image"]}
    else:
        from backend.execution.tools import NO_WINDOW
        from backend.providers.cli_space import minimal_env
        py = _python()
        r = subprocess.run([py, "-I", "-c", PROBE], capture_output=True, text=True, timeout=120, env=minimal_env(),
                           stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        if r.returncode:
            raise ValueError("The code project's Python environment could not be inspected: " + (r.stderr or "")[-300:])
        env = {"engine": "python", "python": py, **json.loads(r.stdout.strip().splitlines()[-1])}
    return {**env, "digest": L.digest(env)}


def create(spec: AgentCodeProtocol, parent_id: str = ""):
    from backend.execution import code_projects
    from backend.execution.protocols import _get
    data = spec.model_dump()
    project = code_projects.active()
    if not project:
        raise code_projects.NoCodeProject()
    code_digest, manifest = snapshot_code(code_projects.active_dir(), spec.include, spec.entrypoint)
    env = environment(data)
    snapshot = {"kind": KIND, "spec": data, "code_project": {"id": project.get("id"), "name": project.get("name")},
                "code_digest": code_digest, "code_manifest": manifest, "environment": env,
                "dataset_fingerprint": None, "worker_sha256": None,
                "trials": [{"condition": c, "seed": s} for c in spec.conditions for s in spec.seeds]}
    with S.db() as c:
        S.topic(c, spec.topic_id)
        revision = _get(c, parent_id, spec.topic_id)["revision"] + 1 if parent_id else 1
        pid = S.uid()
        digest = L.digest(snapshot)
        c.execute("INSERT INTO experiment_protocols VALUES(?,?,?,?,?,?,?)",
                  (pid, spec.topic_id, parent_id or None, revision, digest, S.dumps(snapshot), None))
        L.append(c, spec.topic_id, pid, "protocol.created",
                 {"digest": digest, "revision": revision, "parent_id": parent_id, "kind": KIND, "code_digest": code_digest})
        return _get(c, pid, spec.topic_id)


def _metrics(path: Path, declared: list, limit: int) -> dict:
    if not path.is_file():
        raise ValueError("The code did not write $PHDLAB_OUT/metrics.json")
    if path.stat().st_size > limit:
        raise ValueError("metrics.json exceeds the artifact budget")
    data = json.loads(path.read_text("utf-8"))
    values = data.get("metrics") if isinstance(data, dict) else None
    if not isinstance(values, dict):
        raise ValueError('metrics.json must be {"metrics": {name: number}}')
    out = {}
    for name in declared:
        v = values.get(name)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"Registered metric {name} is missing or not a finite number")
        out[name] = float(v)
    return out


async def _trial(tid, rid, p, condition, seed, remaining, cancelled):
    from backend.execution.tools import NO_WINDOW
    from backend.providers.cli import kill_tree
    from backend.providers.cli_space import minimal_env
    snap, spec = p["payload"], p["payload"]["spec"]
    trial_id = S.uid()
    folder = S.safe_child(S.store_dir(), "experiments", rid, trial_id)
    work, out = S.safe_child(folder, "code"), S.safe_child(folder, "out")
    shutil.copytree(_code_store(snap["code_digest"]), work)
    out.mkdir(parents=True)
    request = {"condition": condition, "seed": seed}
    S.safe_child(folder, "request.json").write_text(S.dumps(request), "utf-8")
    payload = {"request": request, "protocol_digest": p["digest"], "code_digest": snap["code_digest"],
               "environment_digest": snap["environment"]["digest"], "started": S.now(), "folder": str(folder)}
    with S.db() as c:
        c.execute("INSERT INTO experiment_trials VALUES(?,?,?,?,?)", (trial_id, rid, f"{condition}:{seed}", "running", S.dumps(payload)))
    variables = {"PHDLAB_CONDITION": condition, "PHDLAB_SEED": str(seed), "PYTHONHASHSEED": str(seed),
                 "PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8"}
    name = "phdlab-protocol-" + trial_id[:8]
    entry = PurePosixPath(spec["entrypoint"].replace("\\", "/")).as_posix()
    proc, started = None, time.monotonic()
    try:
        if spec["engine"] == "docker":
            from backend.execution import sandbox
            if not sandbox.docker_running() or not sandbox.image_present(spec["docker_image"]):
                raise ValueError("Pinned Docker image/daemon unavailable; no pull or fallback performed")
            argv = [sandbox.docker_exe(), "run", "--rm", "--name", name, "--network", "none", "--read-only", "--memory", "512m",
                    "--cpus", "1", "--pids-limit", "64", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                    "--tmpfs", "/tmp", "-v", f"{work}:/work:ro", "-v", f"{out}:/out", "-w", "/work",
                    *sum((["-e", f"{k}={v}"] for k, v in {**variables, "PHDLAB_OUT": "/out", "PHDLAB_REQUEST": "/out/request.json"}.items()), []),
                    spec["docker_image"], "python", "-B", "/work/" + entry]
            shutil.copy2(S.safe_child(folder, "request.json"), S.safe_child(out, "request.json"))
            env = minimal_env()
        else:
            argv = [snap["environment"]["python"], "-B", str(S.safe_child(work, *entry.split("/")))]
            env = {**minimal_env(), **variables, "PHDLAB_OUT": str(out), "PHDLAB_REQUEST": str(S.safe_child(folder, "request.json"))}
        limit = min(spec["trial_seconds"], remaining)
        with S.safe_child(folder, "stdout.log").open("wb") as stdout, S.safe_child(folder, "stderr.log").open("wb") as stderr:
            proc = subprocess.Popen(argv, cwd=str(work), env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                    shell=False, creationflags=NO_WINDOW, start_new_session=os.name != "nt")
            while proc.poll() is None:
                if cancelled():
                    raise ValueError("Trial cancelled")
                if time.monotonic() - started > limit:
                    raise ValueError(f"Trial exceeded its {limit:.0f} s budget")
                await asyncio.sleep(0.05)
        if proc.returncode:
            raise ValueError(f"The code exited with {proc.returncode}; inspect the retained stderr.log")
        path = S.safe_child(out, "metrics.json")
        metrics = _metrics(path, spec["metrics"], spec["max_artifact_mb"] * 1024 * 1024)
        raw = path.read_bytes()
        payload.update(metrics=metrics, artifact={"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
                       ended=S.now(), elapsed_s=time.monotonic() - started, measurement=True)
        with S.db() as c:
            c.execute("UPDATE experiment_trials SET status='completed',payload=? WHERE id=?", (S.dumps(payload), trial_id))
            L.append(c, tid, rid, "trial.completed", {"trial_id": trial_id, **payload})
        return payload
    except BaseException as exc:
        payload.update(error=str(exc)[:500], ended=S.now())
        with S.db() as c:
            c.execute("UPDATE experiment_trials SET status='failed',payload=? WHERE id=?", (S.dumps(payload), trial_id))
        raise
    finally:
        if proc and proc.poll() is None:
            if spec["engine"] == "docker":
                from backend.execution import sandbox
                await asyncio.to_thread(sandbox.docker, ["stop", "-t", "1", name], 10)
            kill_tree(proc)
            await asyncio.to_thread(proc.wait, 5)


def compare(spec: dict, metrics: dict) -> dict:
    """Paired comparison of every condition with the baseline on the primary metric (metrics[(condition, seed)])."""
    sign = 1 if spec["direction"] == "maximize" else -1
    seeds, primary, base = spec["seeds"], spec["primary_metric"], spec["baseline"]
    per_condition = {c: {"per_seed": {str(s): metrics[(c, s)] for s in seeds},
                         "mean": {m: statistics.mean(metrics[(c, s)][m] for s in seeds) for m in spec["metrics"]}}
                     for c in spec["conditions"]}
    effects = {}
    for c in spec["conditions"]:
        if c == base:
            continue
        deltas = [sign * (metrics[(c, s)][primary] - metrics[(base, s)][primary]) for s in seeds]
        gain = statistics.mean(deltas)
        ci = 1.96 * statistics.stdev(deltas) / math.sqrt(len(deltas)) if len(deltas) > 1 else None
        eligible = len(deltas) >= 3 and all(d > 0 for d in deltas) and gain >= spec["min_effect"]
        effects[c] = {"paired_improvement": gain, "normal_approx_ci95": [gain - ci, gain + ci] if ci is not None else None,
                      "recommendation": "candidate_improvement" if eligible else "no_supported_improvement"}
    selected = max(effects, key=lambda c: effects[c]["paired_improvement"])
    return {"baseline": base, "primary_metric": primary, "direction": spec["direction"], "per_condition": per_condition,
            "effects": effects, "selected_condition": selected, "repeat_count": len(seeds),
            "selection_on_same_runs": True, "requires_human_review": True}


async def execute(tid, p, mission_id, nonce, holder):
    from backend.agent import missions
    from backend.execution import guard
    snap, spec = p["payload"], p["payload"]["spec"]
    AgentCodeProtocol.model_validate(spec)
    bad = check_code(snap["code_digest"], snap["code_manifest"])
    if bad:
        raise ValueError("Frozen code changed or missing (" + ", ".join(bad[:5]) + "); create a new protocol version")
    if await asyncio.to_thread(environment, spec) != snap["environment"]:
        raise ValueError("The pinned environment changed since approval; create a new protocol version")
    guard.try_acquire("cpu", holder)
    rid = S.uid()
    status = "failed"
    payload = {"kind": KIND, "protocol_digest": p["digest"], "code_digest": snap["code_digest"],
               "environment_digest": snap["environment"]["digest"], "dataset_fingerprint": None, "worker_sha256": None,
               "seeds": spec["seeds"], "conditions": spec["conditions"],
               "hardware": {"platform": platform.platform(), "machine": platform.machine()}, "engine": spec["engine"],
               "started": S.now(), "scientific_review": "pending", "raw_measurements_only": True}
    admitted, started = False, time.monotonic()
    try:
        with S.db() as c:
            if c.execute("SELECT 1 FROM experiment_runs WHERE approval_nonce=?", (nonce,)).fetchone():
                raise ValueError("Protocol approval already consumed; explicit new approval required")
            c.execute("INSERT INTO experiment_runs VALUES(?,?,?,?,?,?,?)", (rid, tid, p["id"], mission_id, nonce, "running", S.dumps(payload)))
            admitted = True
            L.append(c, tid, rid, "experiment.admitted", {"protocol_id": p["id"], **payload})
        cancelled = lambda: missions.is_stopped(mission_id)  # noqa: E731
        measured = {}
        for t in snap["trials"]:
            remaining = spec["max_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError("Experiment time budget exceeded")
            trial = await _trial(tid, rid, p, t["condition"], t["seed"], remaining, cancelled)
            measured[(t["condition"], t["seed"])] = trial["metrics"]
            run_dir = S.safe_child(S.store_dir(), "experiments", rid)  # outputs and logs; the frozen code copies are not counted
            size = sum(f.stat().st_size for f in run_dir.rglob("*") if f.is_file() and f.relative_to(run_dir).parts[1] != "code")
            if size > spec["max_artifact_mb"] * 1024 * 1024:
                raise ValueError("Experiment artifact budget exceeded")
        payload.update(comparison=compare(spec, measured), elapsed_s=time.monotonic() - started, ended=S.now())
        status = "completed"
    except asyncio.CancelledError:
        status = "interrupted"
        payload["error"] = "Controller stopped; no automatic rerun"
        raise
    except Exception as exc:
        payload["error"] = str(exc)[:800]
        raise
    finally:
        guard.release("cpu", holder)
        if admitted:
            with S.db() as c:
                c.execute("UPDATE experiment_runs SET status=?,payload=? WHERE id=?", (status, S.dumps(payload), rid))
                L.append(c, tid, rid, "experiment." + status, payload)
    return {"experiment_run_id": rid, "status": status, **payload}


def _raw_metrics(rid, trial, spec):
    folder = S.safe_child(S.store_dir(), "experiments", rid, trial["id"])
    path = S.safe_child(folder, "out", "metrics.json")
    if str(path) != trial["payload"]["artifact"]["path"]:
        raise ValueError("Artifact pointer outside trial")
    raw = path.read_bytes()
    art = trial["payload"]["artifact"]
    return folder, raw, hashlib.sha256(raw).hexdigest() == art["sha256"] and len(raw) == art["bytes"], \
        _metrics(path, spec["metrics"], spec["max_artifact_mb"] * 1024 * 1024)


def verify(tid, run, p, *, find_reproduction=True):
    """Independent check of an agent-code run from its raw files. Aggregation is re-implemented here with fsum on
    purpose, so a wrong stored summary is caught even though the runner's compare() produced it."""
    from backend.execution import protocols as P
    snap, spec, rid, checks = p["payload"], p["payload"]["spec"], run["id"], []

    def check(name, ok, detail=""):
        checks.append({"check": name, "status": "passed" if ok else "failed", "detail": detail})

    check("run_completed", run["status"] == "completed")
    check("immutable_protocol", p["digest"] == L.digest(snap) == run["payload"]["protocol_digest"])
    bad = check_code(snap["code_digest"], snap["code_manifest"])
    check("code_snapshot_intact", not bad and run["payload"].get("code_digest") == snap["code_digest"], ", ".join(bad[:5]))
    check("environment_pinned", run["payload"].get("environment_digest") == snap["environment"]["digest"]
          == L.digest({k: v for k, v in snap["environment"].items() if k != "digest"}))
    raw_metrics, artifacts = {}, []
    for trial in run["trials"]:
        key, t = trial["trial_key"], trial["payload"]
        if trial["status"] != "completed":
            check(key + ":completed", False)
            continue
        try:
            folder, _, same, values = _raw_metrics(rid, trial, spec)
            check(key + ":sha256", same)
            check(key + ":logs", S.safe_child(folder, "stdout.log").is_file() and S.safe_child(folder, "stderr.log").is_file())
            req = t["request"]
            check(key + ":manifest", t["protocol_digest"] == p["digest"] and t["code_digest"] == snap["code_digest"]
                  and key == f"{req['condition']}:{req['seed']}" and req["condition"] in spec["conditions"] and req["seed"] in spec["seeds"])
            check(key + ":metrics_match_raw", all(math.isclose(values[m], t["metrics"][m], rel_tol=0, abs_tol=0) for m in spec["metrics"]))
            raw_metrics[(req["condition"], req["seed"])] = values
            artifacts.append({"trial_key": key, "sha256": t["artifact"]["sha256"]})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            check(key + ":artifact_readable", False, str(exc)[:500])
    registered = {(c, s) for c in spec["conditions"] for s in spec["seeds"]}
    check("registered_trials", set(raw_metrics) == registered and len(run["trials"]) == len(registered))
    comparison = run["payload"].get("comparison") or {}
    if set(raw_metrics) == registered:
        sign = 1 if spec["direction"] == "maximize" else -1
        primary, base, n = spec["primary_metric"], spec["baseline"], len(spec["seeds"])
        ok = comparison.get("repeat_count") == n and comparison.get("baseline") == base and comparison.get("primary_metric") == primary
        for c in spec["conditions"]:
            for m in spec["metrics"]:
                mean = math.fsum(raw_metrics[(c, s)][m] for s in spec["seeds"]) / n
                ok &= math.isclose(mean, comparison.get("per_condition", {}).get(c, {}).get("mean", {}).get(m, float("nan")), rel_tol=1e-9, abs_tol=1e-12)
        check("summary_matches_measurements", ok)
        ok, best = True, None
        for c in spec["conditions"]:
            if c == base:
                continue
            deltas = [sign * (raw_metrics[(c, s)][primary] - raw_metrics[(base, s)][primary]) for s in spec["seeds"]]
            gain = math.fsum(deltas) / n
            reported = comparison.get("effects", {}).get(c, {})
            ok &= math.isclose(gain, reported.get("paired_improvement", float("nan")), rel_tol=1e-9, abs_tol=1e-12)
            if n > 1:
                half = 1.96 * statistics.stdev(deltas) / math.sqrt(n)
                ci = reported.get("normal_approx_ci95") or [float("nan")] * 2
                ok &= all(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12) for a, b in zip(ci, [gain - half, gain + half]))
            else:
                ok &= reported.get("normal_approx_ci95") is None
            expected = "candidate_improvement" if n >= 3 and all(d > 0 for d in deltas) and gain >= spec["min_effect"] else "no_supported_improvement"
            ok &= reported.get("recommendation") == expected
            if best is None or gain > best[1]:
                best = (c, gain)
        check("comparison_recomputed", ok and comparison.get("selected_condition") == best[0])
    else:
        check("comparison_recomputed", False, "Not every registered trial has a measurement")
    reproduction = None
    if find_reproduction:
        tol = spec["reproduction_rel_tol"]
        for other in P.runs(tid):
            if other["id"] == rid or other["status"] != "completed" or other["approval_nonce"] == run["approval_nonce"] \
                    or other["payload"].get("protocol_digest") != run["payload"]["protocol_digest"]:
                continue
            theirs = {t["trial_key"]: t["payload"].get("metrics") or {} for t in other["trials"] if t["status"] == "completed"}
            mine = {f"{c}:{s}": v for (c, s), v in raw_metrics.items()}
            if set(theirs) == set(mine) and all(math.isclose(mine[k][m], theirs[k].get(m, float("nan")), rel_tol=tol, abs_tol=1e-12)
                                                 for k in mine for m in spec["metrics"]) \
                    and verify(tid, other, p, find_reproduction=False)["status"] == "passed":
                reproduction = other["id"]
                break
    passed = all(c["status"] == "passed" for c in checks)
    return {"verifier": "agent-code-recompute-v1", "status": "passed" if passed else "failed", "checks": checks,
            "artifact_refs": artifacts, "reproduction_run_id": reproduction,
            "warnings": [] if reproduction else ["Independent fresh-process reproduction is not recorded"],
            "limitations": ["Metrics are computed by the agent's own code; the verifier checks integrity, registration and "
                            "aggregation, not the metric implementation", "The best condition is selected on the same runs; "
                            "no held-out split is enforced by the runner", "Small-n intervals are approximate"],
            "experiment_run_id": rid, "protocol_digest": p["digest"]}
