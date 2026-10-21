"""ClearML worker — the ONLY place where the `clearml` SDK is imported. Always runs as a separate Python process:

    python clearml_worker.py   < {"cmd": ..., "args": {...}}   (JSON on stdin)
    → last stdout line:  @@RESULT@@{json}   or   @@ERROR@@{json}

Why a subprocess: Task.init (needed for ClearML's offline mode) hooks the calling process (stdout, argparse,
frameworks), and the SDK pulls native packages (numpy, psutil, Pillow) that Windows Smart App Control may block —
neither may affect the web server. The offline cache directory arrives as CLEARML_CACHE_DIR (one per research project).
This file must not import the app (it runs standalone).

Commands
    probe           SDK importable? → {version}
    record_run      one finished run → a ClearML offline session (zip)
"""
import json
import os
import sys
import traceback

RESULT, ERROR = "@@RESULT@@", "@@ERROR@@"


def record_run(Task, a: dict) -> dict:
    """a: {project, run: {id, title, cmd, status, git, environment, metrics, series, stdout_tail, files: [abs paths]}}"""
    r = a["run"]
    git = r.get("git") or {}
    # Task.init would describe THIS worker script. ClearML's official VCS variables describe the research code instead
    # (and skip scanning the worker's own repository).
    if git.get("remote"):
        os.environ.update(CLEARML_VCS_REPO_URL=git["remote"], CLEARML_VCS_COMMIT_ID=git.get("sha", ""),
                          CLEARML_VCS_BRANCH=git.get("branch", ""), CLEARML_VCS_DIFF="")
    os.environ["CLEARML_VCS_ENTRY_POINT"] = (r.get("cmd") or "")[:500]
    Task.set_offline(True)
    t = Task.init(project_name=a.get("project") or "PhD Research Lab", task_name=f"{(r.get('title') or r.get('cmd') or r['id'])[:120]} [{r['id']}]",
                  task_type=Task.TaskTypes.training, reuse_last_task_id=False, continue_last_task=False, auto_connect_frameworks=False,
                  auto_connect_arg_parser=False, auto_connect_streams=False, auto_resource_monitoring=False)
    notes = []
    try:  # repository detection runs in a background thread; finish it before overriding the script section
        t._wait_for_repo_detection(timeout=60)
    except Exception:
        pass
    try:
        if t.data.script is not None:
            t.set_script(repository=git.get("remote", "") or "", branch=git.get("branch", "") or "", commit=git.get("sha", "") or "",
                         diff="", working_dir=".", entry_point=(r.get("cmd") or "")[:500])
        else:
            notes.append("script section not available — code identity kept in parameters (git_sha, cmd)")
    except Exception as e:
        notes.append(f"set_script skipped: {type(e).__name__}")
    t.set_parameters({"General/cmd": r.get("cmd", ""), "General/run_id": r["id"], "General/git_sha": git.get("sha", ""),
                      "General/git_dirty": str(bool(git.get("dirty"))), "General/environment": json.dumps(r.get("environment") or {}),
                      "General/status": r.get("status", "")})
    t.add_tags(["phd-research-lab", f"run:{r['id']}", r.get("status") or "unknown"] + ([f"git:{git['sha'][:10]}"] if git.get("sha") else []))
    log = t.get_logger()
    for name, points in (r.get("series") or {}).items():
        for step, val in points:
            log.report_scalar(title=name, series=name, value=float(val), iteration=int(step))
    for name, val in (r.get("metrics") or {}).items():
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            log.report_single_value(name=name, value=float(val))
    if r.get("stdout_tail"):
        log.report_text(r["stdout_tail"][-20000:])
    for f in (r.get("files") or [])[:30]:
        if os.path.isfile(f):
            t.upload_artifact(name=os.path.basename(f), artifact_object=f, wait_on_upload=True)
    out = {"task_id": t.id, "offline": True, "notes": notes, "session_dir": str(t.get_offline_mode_folder())}
    t.close()
    z = out["session_dir"].rstrip("\\/") + ".zip"
    out["session_zip"] = z if os.path.isfile(z) else ""
    return out


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
        cmd, args = req.get("cmd"), req.get("args") or {}
        import clearml
        from clearml import Task
        if cmd == "probe":
            out = {"version": clearml.__version__}
        elif cmd == "record_run":
            out = record_run(Task, args)
        elif cmd == "remote_snapshot":
            if req.get("offline", True):
                raise ValueError("Remote task requires online mode")
            from pathlib import Path
            import hashlib
            import shutil
            Task.set_offline(False)
            task = Task.get_task(task_id=args["task_id"])
            if task.get_parameters().get("General/run_id") != args["run_id"]:
                raise ValueError("ClearML task run_id does not match the approved run")
            out = {"task_id": task.id, "project_id": task.project, "status": str(task.get_status()),
                   "metrics": task.get_last_scalar_metrics(), "artifacts": []}
            if args.get("collect"):
                dest = Path(args["destination"]).resolve()
                dest.mkdir(parents=True, exist_ok=True)
                for name in args["required_artifacts"]:
                    if name not in task.artifacts:
                        raise ValueError("Required artifact missing: " + name)
                    art = task.artifacts[name]
                    # Never art.get(): it can deserialize pickle from untrusted remote code.
                    source = Path(art.get_local_copy(extract_archive=False)).resolve()
                    if not source.is_file():
                        raise ValueError("Artifact must be a regular file: " + name)
                    target = dest / name
                    tmp = target.with_suffix(target.suffix + ".partial")
                    try:
                        shutil.copyfile(source, tmp)
                        with tmp.open("rb") as f:
                            sha = hashlib.file_digest(f, "sha256").hexdigest()
                        expected = getattr(art, "hash", "") or ""
                        if expected and len(expected) == 64 and sha != expected:
                            raise ValueError("Artifact checksum mismatch: " + name)
                        if expected and len(expected) == 32:
                            with tmp.open("rb") as f:
                                if hashlib.file_digest(f, "md5").hexdigest() != expected:
                                    raise ValueError("Artifact checksum mismatch: " + name)
                        os.replace(tmp, target)
                    finally:
                        tmp.unlink(missing_ok=True)
                    out["artifacts"].append({"name": name, "sha256": sha, "size": target.stat().st_size})
        else:
            raise ValueError(f"unknown command {cmd}")
    except Exception as e:  # message only — never the environment
        sys.stdout.write("\n" + ERROR + json.dumps({"error": f"{type(e).__name__}: {e}"[:800],
                                                     "trace": traceback.format_exc(limit=3)[-1500:]}) + "\n")
        return 1
    sys.stdout.write("\n" + RESULT + json.dumps(out, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
