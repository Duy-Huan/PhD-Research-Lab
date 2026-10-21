"""ClearML worker — the ONLY place where the `clearml` SDK is imported. Always runs as a separate Python process:

    python clearml_worker.py   < {"cmd": ..., "offline": bool, "args": {...}}   (JSON on stdin)
    → last stdout line:  @@RESULT@@{json}   or   @@ERROR@@{json}

Why a subprocess: Task.init (needed for ClearML's offline mode) hooks the calling process (stdout, argparse,
frameworks), and the SDK pulls native packages (numpy, psutil, Pillow) that Windows Smart App Control may block —
neither may affect the web server. Credentials arrive as CLEARML_* environment variables; the offline cache directory
as CLEARML_CACHE_DIR (one per research project). This file must not import the app (it runs standalone).

Commands
    probe           SDK importable? → {version}
    record_run      one finished sandbox run → a ClearML task (offline session zip, or a task on the server)
    import_offline  offline session zip → task on the configured server
    get_task        task summary from the server
    submit_remote   enqueue a script of the code workspace for a ClearML Agent
    op              fine-grained ExperimentBackend operations on the server (create, log_metric, …)
"""
import json
import os
import sys
import traceback

RESULT, ERROR = "@@RESULT@@", "@@ERROR@@"


def _task_summary(Task, t) -> dict:
    last = {}
    try:
        for title, series in (t.get_last_scalar_metrics() or {}).items():
            for s, v in series.items():
                last[title if s == title else f"{title}/{s}"] = v.get("last")
    except Exception:
        pass
    script = {}
    try:
        sc = t.data.script
        script = {k: getattr(sc, a, "") for k, a in (("repository", "repository"), ("branch", "branch"), ("commit", "version_num"),
                                                       ("entry_point", "entry_point"), ("working_dir", "working_dir"))}
    except Exception:
        pass
    return {"id": t.id, "name": t.name, "status": t.get_status(), "project": t.get_project_name(), "url": t.get_output_log_web_page(),
            "parameters": t.get_parameters() or {}, "metrics": last, "artifacts": sorted((t.artifacts or {}).keys()), "script": script}


def record_run(Task, a: dict, offline: bool) -> dict:
    """a: {project, run: {id, title, cmd, status, git, environment, metrics, series, stdout_tail, files: [abs paths]}}"""
    r = a["run"]
    git = r.get("git") or {}
    # Task.init would describe THIS worker script. ClearML's official VCS variables describe the research code instead
    # (and skip scanning the worker's own repository).
    if git.get("remote"):
        os.environ.update(CLEARML_VCS_REPO_URL=git["remote"], CLEARML_VCS_COMMIT_ID=git.get("sha", ""),
                          CLEARML_VCS_BRANCH=git.get("branch", ""), CLEARML_VCS_DIFF="")
    os.environ["CLEARML_VCS_ENTRY_POINT"] = (r.get("cmd") or "")[:500]
    if offline:
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
    out = {"task_id": t.id, "offline": bool(offline), "notes": notes}
    if offline:
        out["session_dir"] = str(t.get_offline_mode_folder())
    else:
        out["url"] = t.get_output_log_web_page()
        if r.get("status") == "failed":
            t.mark_failed(status_reason="sandbox run failed", force=True)
    t.close()
    if offline:
        z = out["session_dir"].rstrip("\\/") + ".zip"
        out["session_zip"] = z if os.path.isfile(z) else ""
    return out


def op(Task, a: dict) -> dict:
    name = a["op"]
    if name == "create":
        t = Task.create(project_name=a.get("project") or "PhD Research Lab", task_name=a["name"][:200], task_type=Task.TaskTypes.training)
        if a.get("params"):
            t.set_parameters({f"General/{k}": v for k, v in a["params"].items()})
        if a.get("tags"):
            t.add_tags([str(x)[:60] for x in a["tags"]])
        return {"id": t.id, "url": t.get_output_log_web_page()}
    if name == "list":
        return {"tasks": [{"id": t.id, "name": t.name, "status": t.get_status()}
                          for t in (Task.get_tasks(project_name=a.get("project") or None) or [])[: int(a.get("limit") or 50)]]}
    t = Task.get_task(task_id=a["id"])
    if t is None:
        raise ValueError(f"ClearML task {a['id']} not found")
    if name == "start":
        t.mark_started(force=True)
    elif name == "log_metric":
        t.get_logger().report_scalar(title=a["name"], series=a["name"], value=float(a["value"]), iteration=int(a.get("step") or 0))
        t.flush(wait_for_uploads=True)
    elif name == "log_parameter":
        t.set_parameters({f"General/{a['name']}": a["value"]})
    elif name == "log_artifact":
        t.upload_artifact(name=a["name"], artifact_object=a["path"], wait_on_upload=True)
    elif name == "log_model":
        from clearml import OutputModel
        m = OutputModel(task=t, name=a["name"])
        m.update_weights(weights_filename=a["path"])
        return {"model_id": m.id}
    elif name == "finish":
        t.flush(wait_for_uploads=True)
        (t.mark_failed if a.get("status") == "failed" else t.mark_completed)(status_message="set by PhD Research Lab")
    else:
        raise ValueError(f"unknown op {name}")
    return {"id": t.id, "status": t.get_status()}


def submit_remote(Task, a: dict) -> dict:
    kw = {"project_name": a.get("project") or "PhD Research Lab", "task_name": f"remote: {a['script']}", "task_type": Task.TaskTypes.training,
          "script": a["script"], "working_directory": ".", "argparse_args": [tuple(x) for x in a.get("argparse_args") or []] or None}
    for k in ("repo", "branch", "commit", "requirements_file"):
        if a.get(k):
            kw[k] = a[k]
    t = Task.create(**kw)
    Task.enqueue(t, queue_name=a.get("queue") or "default")
    return {"task_id": t.id, "url": t.get_output_log_web_page(), "queue": a.get("queue") or "default"}


def main() -> int:
    req = json.loads(sys.stdin.read() or "{}")
    cmd, args = req.get("cmd"), req.get("args") or {}
    try:
        import clearml
        from clearml import Task
        if cmd == "probe":
            out = {"version": clearml.__version__}
        elif cmd == "record_run":
            out = record_run(Task, args, bool(req.get("offline")))
        elif cmd == "import_offline":
            tid = Task.import_offline_session(session_folder_zip=args["zip"])
            out = {"task_id": tid, "url": Task.get_task(task_id=tid).get_output_log_web_page() if tid else ""}
        elif cmd == "get_task":
            t = Task.get_task(task_id=args["id"])
            if t is None:
                raise ValueError(f"ClearML task {args['id']} not found")
            out = _task_summary(Task, t)
        elif cmd == "submit_remote":
            out = submit_remote(Task, args)
        elif cmd == "op":
            out = op(Task, args)
        else:
            raise ValueError(f"unknown command {cmd}")
    except Exception as e:  # message only — never the environment (credentials live there)
        sys.stdout.write("\n" + ERROR + json.dumps({"error": f"{type(e).__name__}: {e}"[:800],
                                                     "trace": traceback.format_exc(limit=3)[-1500:]}) + "\n")
        return 1
    sys.stdout.write("\n" + RESULT + json.dumps(out, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
