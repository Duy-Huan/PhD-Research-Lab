"""Native engines remain independent. Only persisted files are observed by this bridge."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from backend.core.config import data_dir, list_projects
from backend.knowledge import research_store as S

OBSERVABILITY = "Persisted artifacts only; external sessions, private reasoning and unsaved activity are not observable."
IGNORE = {".git", ".venv", "venv", "node_modules", "__pycache__", ".cache", "build", "dist", ".phdlab", ".env", ".aws", ".ssh", ".codex"}
EXTENSIONS = {".md", ".txt", ".csv", ".json", ".jsonl", ".pdf", ".bib", ".tex", ".png", ".svg", ".yaml", ".yml", ".ipynb", ".pt", ".pth", ".ckpt", ".safetensors", ".parquet", ".npy", ".py", ".r", ".jl", ".c", ".cpp", ".h"}
TEXT_EXTENSIONS = {".md", ".txt", ".csv", ".json", ".jsonl", ".bib", ".tex", ".yaml", ".yml", ".py", ".r", ".jl", ".c", ".cpp", ".h"}
_lock = threading.Lock()
_processes: dict = {}
IS_WIN = os.name == "nt"


class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: str = Field(pattern="^(openscience|feynman|opencode)$")
    path: str = Field(default="", max_length=2000)
    sync_interval_minutes: int = Field(default=0, ge=0, le=10080)


def _capabilities(engine: str) -> dict:
    from backend.execution.tools import which
    return {"engine": engine, "binary_available": bool(which(engine)), "artifact_reconciliation": True,
            "external_session_enumeration": engine == "opencode", "external_event_replay": engine == "opencode",
            "native_open": "browser_process" if engine == "openscience" else "http_loopback" if engine == "opencode" else "terminal_window" if IS_WIN else "terminal_command",
            "fidelity": "artifact_observed", "limitations": OBSERVABILITY, "adapter_version": "1.0"}


def _get(c, wid: str) -> dict:
    r = c.execute("SELECT * FROM workspaces WHERE id=?", (wid,)).fetchone()
    if not r:
        raise ValueError("Workspace not found in this project")
    checkpoint = c.execute("SELECT payload FROM checkpoints WHERE workspace_id=?", (wid,)).fetchone()
    count = c.execute("SELECT count(*) FROM artifact_versions a WHERE workspace_id=? AND available=1 AND version=(SELECT max(version) FROM artifact_versions b WHERE b.workspace_id=a.workspace_id AND b.path=a.path)", (wid,)).fetchone()[0]
    return {**dict(r), **json.loads(r["payload"]), "project_id": c.execute("SELECT value FROM meta WHERE key='project_id'").fetchone()[0], "capabilities": _capabilities(r["engine"]), "artifact_count": count,
            "checkpoint": json.loads(checkpoint[0]) if checkpoint else None}


def get(wid: str) -> dict:
    with S.db() as c:
        return _get(c, wid)


def list_workspaces(tid: str) -> list:
    with S.db() as c:
        S.topic(c, tid)
        return [_get(c, r[0]) for r in c.execute("SELECT id FROM workspaces WHERE topic_id=?", (tid,))]


def validate_path(path: Path, tid: str, wid: str = "") -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Use an absolute workspace path without traversal")
    S.safe_child(path)
    p = path.resolve()
    # No native workspace may contain PhD Lab or another project's data, or vice versa.
    root = data_dir().resolve()
    canonical = S.safe_child(root, "topics", tid)
    from backend.core.config import ROOT
    if p == Path(p.anchor) or p == Path.home().resolve() or p == root or p == ROOT.resolve() or p in root.parents or p in ROOT.resolve().parents:
        raise ValueError("Choose a dedicated engine workspace, not a project/application/home root")
    if p.is_relative_to(root) and not p.is_relative_to(canonical):
        raise ValueError("Managed workspaces must belong to the selected topic")
    if p.is_relative_to(ROOT.resolve()) and not p.is_relative_to(root):
        raise ValueError("Cannot link application source as an engine workspace")
    for project in list_projects():
        other = Path(project["data_dir"]).resolve()
        if other != root and ((p.is_relative_to(other) and not (root.is_relative_to(other) and p.is_relative_to(root))) or other.is_relative_to(p)):
            raise ValueError("Workspace overlaps another project")
        index = other / "workspace" / "research" / "research.sqlite3"
        if other != root and index.is_file():
            import sqlite3
            with sqlite3.connect(f"file:{index.as_posix()}?mode=ro", uri=True) as c:
                for row in c.execute("SELECT path FROM workspaces"):
                    linked = Path(row[0]).resolve()
                    if p.is_relative_to(linked) or linked.is_relative_to(p):
                        raise ValueError("Workspace is already owned by another project")
    with S.db() as c:
        S.topic(c, tid)
        for r in c.execute("SELECT id,path FROM workspaces WHERE id!=?", (wid,)):
            other = Path(r["path"]).resolve()
            if p.is_relative_to(other) or other.is_relative_to(p):
                raise ValueError("Workspace overlaps an existing workspace")
    return p


def link(tid: str, body: WorkspaceInput) -> dict:
    S.get_topic(tid)
    path = Path(body.path).expanduser() if body.path else S.safe_child(data_dir(), "topics", tid, body.engine + "_prj")
    # Serialize validation and registration to prevent two concurrent topics acquiring the same folder.
    with _lock:
        path = validate_path(path, tid)
        if body.path and not path.is_dir():
            raise ValueError("Existing workspace folder does not exist")
        path.mkdir(parents=True, exist_ok=True)
        if body.engine == "opencode":
            plugins_dir = S.safe_child(path, ".opencode", "plugins")
            plugins_dir.mkdir(parents=True, exist_ok=True)
            agents_md = S.safe_child(path, "AGENTS.md")
            if not agents_md.exists():
                agents_md.write_text("# PhD Research Lab — OpenCode Scoped Workspace\n\nOperate strictly within this topic workspace. Do not exfiltrate secrets or invoke metered APIs without approval.\n", "utf-8")
        payload = {"created": S.now(), "adapter_version": "1.0", "native_project_id": None,
                   "sync_interval_minutes": body.sync_interval_minutes, "origin": "linked" if body.path else "managed_folder"}
        with S.db() as c:
            wid = S.uid()
            c.execute("INSERT INTO workspaces VALUES(?,?,?,?,?)", (wid, tid, body.engine, str(path), S.dumps(payload)))
            S.event(c, tid, "workspace.linked", {"path": str(path), "engine": body.engine}, wid=wid)
            return _get(c, wid)


def _root(w: dict) -> Path:
    p = Path(w["path"])
    S.safe_child(p)
    if not p.is_dir():
        raise ValueError("Workspace is unavailable; relink the folder before syncing")
    return p


def relink(wid: str, body: WorkspaceInput) -> dict:
    with _lock:
        w = get(wid)
        if body.engine != w["engine"]:
            raise ValueError("A workspace cannot change engine type")
        path = validate_path(Path(body.path or w["path"]).expanduser(), w["topic_id"], wid)
        if not path.is_dir():
            raise ValueError("Relink requires an existing directory; files are never moved or deleted")
        payload = json.loads(w["payload"])
        payload["sync_interval_minutes"] = body.sync_interval_minutes
        payload["reconciliation_needed"] = True
        with S.db() as c:
            c.execute("UPDATE workspaces SET path=?,payload=? WHERE id=?", (str(path), S.dumps(payload), wid))
            S.event(c, w["topic_id"], "workspace.relinked", {"previous_path": w["path"], "path": str(path), "files_moved": False}, wid=wid)
            return _get(c, wid)


def _inventory(root: Path, cancelled=lambda: False) -> tuple[list, dict]:
    """One bounded traversal. Incomplete scans cannot assert deletion. No code is executed."""
    files, skipped, errors, unstable = [], [], [], []
    complete, visited, hashed = True, 0, 0
    stack = [root]
    started = time.monotonic()
    while stack:
        if cancelled():
            raise ValueError("Sync cancelled")
        folder = stack.pop()
        try:
            S.safe_child(root, str(folder.relative_to(root)))
            entries = os.scandir(folder)
            with entries:
                for e in entries:
                    visited += 1
                    if visited > 10000 or len(files) >= 2000 or time.monotonic() - started > 20:
                        complete = False
                        stack.clear()
                        break
                    rel = str(Path(e.path).relative_to(root)).replace("\\", "/")
                    if e.name in IGNORE or e.name.startswith(".") or e.name.endswith((".tmp", ".part", "~")):
                        continue
                    try:
                        path = S.safe_child(root, rel)
                        if e.is_symlink():
                            raise ValueError("Symlink skipped")
                        if e.is_dir(follow_symlinks=False):
                            stack.append(path)
                            continue
                        if not e.is_file(follow_symlinks=False) or path.suffix.lower() not in EXTENSIONS:
                            continue
                        st = path.stat()
                        if time.time() - st.st_mtime < 1:
                            unstable.append(rel)
                            continue
                        sha, excerpt = None, b""
                        if st.st_size <= 32 * 1024 * 1024 and hashed + st.st_size <= 64 * 1024 * 1024:
                            digest = hashlib.sha256()
                            with path.open("rb") as f:
                                # Also compare fstat: a file replaced while opening is deferred.
                                opened = os.fstat(f.fileno())
                                if (opened.st_ino, opened.st_size, opened.st_mtime_ns) != (st.st_ino, st.st_size, st.st_mtime_ns):
                                    unstable.append(rel)
                                    continue
                                for block in iter(lambda: f.read(1024 * 1024), b""):
                                    digest.update(block)
                                    if not excerpt and path.suffix.lower() in TEXT_EXTENSIONS and st.st_size <= 2 * 1024 * 1024:
                                        excerpt = block[:40000]
                                    hashed += len(block)
                                    if hashed > 65 * 1024 * 1024 or cancelled():
                                        raise ValueError("Hash budget exceeded or sync cancelled")
                            sha = digest.hexdigest()
                        else:
                            skipped.append({"path": rel, "reason": "metadata_only: hash/copy budget", "bytes": st.st_size})
                        after = path.stat()
                        if (st.st_ino, st.st_size, st.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                            unstable.append(rel)
                            continue
                        signature = sha or f"metadata:{st.st_size}:{st.st_mtime_ns}"
                        files.append({"path": rel, "sha256": sha, "signature": signature, "bytes": st.st_size,
                                      "original_root": str(root), "text_excerpt": excerpt.decode("utf-8", errors="replace"),
                                      "source_time": __import__('datetime').datetime.fromtimestamp(st.st_mtime, __import__('datetime').timezone.utc).isoformat(),
                                      "mtime_ns": st.st_mtime_ns, "type": path.suffix.lower()[1:], "hash_status": "verified" if sha else "not_computed"})
                    except (OSError, ValueError) as exc:
                        errors.append({"path": rel, "error": str(exc)[:300]})
                        complete = False
        except (OSError, ValueError) as exc:
            errors.append({"path": str(folder.relative_to(root)), "error": str(exc)[:300]})
            complete = False
    return files, {"complete": complete and not unstable, "skipped": skipped[:100], "errors": errors[:100],
                   "unstable": unstable[:100], "visited": visited, "hashed_bytes": hashed,
                   "ignored_directories": sorted(IGNORE), "allowlisted_extensions": sorted(EXTENSIONS),
                   "fidelity": "artifact_observed", "not_observable": OBSERVABILITY}


def sync(wid: str, cancelled=lambda: False) -> dict:
    # Scans don't hold SQLite write locks. Registration is one transaction after a complete inventory.
    with _lock:
        w = get(wid)
        try:
            files, report = _inventory(_root(w), cancelled)
            if cancelled():
                raise ValueError("Sync cancelled")
            changed, deleted = 0, 0
            with S.db() as c:
                previous_checkpoint = c.execute("SELECT payload FROM checkpoints WHERE workspace_id=?", (wid,)).fetchone()
                previous_checkpoint = json.loads(previous_checkpoint[0]) if previous_checkpoint else {}
                current = {r["path"]: dict(r) for r in c.execute("SELECT a.* FROM artifact_versions a WHERE workspace_id=? AND version=(SELECT max(version) FROM artifact_versions b WHERE b.workspace_id=a.workspace_id AND b.path=a.path)", (wid,))}
                seen = set()
                for f in files:
                    f.update(project_id=w["project_id"], topic_id=w["topic_id"], workspace_id=wid, source_engine=w["engine"], session_id=None, run_id=None)
                    seen.add(f["path"])
                    previous = current.get(f["path"])
                    if previous and previous["available"] and previous["signature"] == f["signature"]:
                        continue
                    version = previous["version"] + 1 if previous else 1
                    aid = S.uid()
                    c.execute("INSERT INTO artifact_versions VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (aid, wid, f["path"], f["signature"], version, f["sha256"], f["bytes"], 1, S.now(), S.dumps(f)))
                    c.execute("DELETE FROM artifact_search WHERE artifact_id IN (SELECT id FROM artifact_versions WHERE workspace_id=? AND path=?)", (wid, f["path"]))
                    if f["text_excerpt"]:
                        c.execute("INSERT INTO artifact_search VALUES(?,?)", (aid, f["path"] + "\n" + f["text_excerpt"]))
                    S.event(c, w["topic_id"], "artifact.observed", {"artifact_id": aid, "version": version, **{k:v for k,v in f.items() if k != "text_excerpt"}, "fidelity": "artifact_observed"},
                            key=f"artifact:{aid}", wid=wid)
                    changed += 1
                if report["complete"]:
                    for path, previous in current.items():
                        if path in seen or not previous["available"]:
                            continue
                        # Append a tombstone; never erase history.
                        aid = S.uid()
                        c.execute("INSERT INTO artifact_versions VALUES(?,?,?,?,?,?,?,?,?,?)",
                                  (aid, wid, path, previous["signature"], previous["version"] + 1, previous["sha256"], previous["bytes"], 0, S.now(), previous["payload"]))
                        c.execute("DELETE FROM artifact_search WHERE artifact_id IN (SELECT id FROM artifact_versions WHERE workspace_id=? AND path=?)", (wid, path))
                        S.event(c, w["topic_id"], "artifact.unavailable", {"artifact_id": aid, "path": path, "fidelity": "artifact_observed"}, wid=wid)
                        deleted += 1
                report.update(changed=changed, deleted=deleted, observed=len(files), at=S.now(), status="completed" if report["complete"] else "partial")
                report["last_success"] = report["at"] if report["complete"] else previous_checkpoint.get("last_success")
                c.execute("INSERT INTO checkpoints VALUES(?,?) ON CONFLICT(workspace_id) DO UPDATE SET payload=excluded.payload", (wid, S.dumps(report)))
            return report
        except Exception as exc:
            with S.db() as c:
                previous = c.execute("SELECT payload FROM checkpoints WHERE workspace_id=?", (wid,)).fetchone()
                previous = json.loads(previous[0]) if previous else {}
                report = {"status": "failed", "complete": False, "at": S.now(), "last_success": previous.get("last_success"), "error": str(exc)[:500], "not_observable": OBSERVABILITY}
                c.execute("INSERT INTO checkpoints VALUES(?,?) ON CONFLICT(workspace_id) DO UPDATE SET payload=excluded.payload", (wid, S.dumps(report)))
            raise


def artifacts(tid: str, wid: str = "", history: bool = False) -> list:
    with S.db() as c:
        S.topic(c, tid)
        query = "SELECT a.*,w.engine,w.topic_id FROM artifact_versions a JOIN workspaces w ON w.id=a.workspace_id WHERE w.topic_id=? AND (?='' OR w.id=?)"
        if not history:
            query += " AND a.version=(SELECT max(version) FROM artifact_versions b WHERE b.workspace_id=a.workspace_id AND b.path=a.path)"
        query += " ORDER BY observed DESC LIMIT 500"
        return [{**dict(r), "payload": json.loads(r["payload"]), "fidelity": "artifact_observed"} for r in c.execute(query, (tid, wid, wid))]


def artifact(tid: str, aid: str) -> dict:
    with S.db() as c:
        r = c.execute("SELECT a.*,w.path AS root,w.topic_id,w.engine FROM artifact_versions a JOIN workspaces w ON w.id=a.workspace_id WHERE a.id=? AND w.topic_id=?", (aid, tid)).fetchone()
        if not r:
            raise ValueError("Artifact not found in this topic")
        return dict(r)


def artifact_text(tid: str, aid: str) -> dict:
    r = artifact(tid, aid)
    snapshot = json.loads(r["payload"])
    if snapshot.get("text_excerpt"):
        return {"id": "artifact:" + aid, "title": r["path"], "text": f"Observed text snapshot; artifact version {r['version']}; SHA256 {r['sha256']}; source time {snapshot['source_time']}; artifact_observed (not a verified finding).\n{snapshot['text_excerpt']}", "trust": "untrusted"}
    path = S.safe_child(Path(r["root"]), r["path"])
    if not r["available"] or not r["sha256"] or r["bytes"] > 2 * 1024 * 1024 or not path.is_file():
        text = "Content unavailable; metadata-only observation."
    else:
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != r["sha256"]:
            raise ValueError("Artifact changed since sync; sync again before citing it")
        if path.suffix.lower() == ".pdf":
            from backend.knowledge.library import first_pages_text
            text = first_pages_text(path, 3, 12000)
        elif path.suffix.lower() in (".png", ".pt", ".pth", ".ckpt", ".npy", ".parquet", ".safetensors"):
            text = "Binary artifact; contents not interpreted."
        else:
            text = raw.decode("utf-8", errors="replace")[:12000]
    return {"id": "artifact:" + aid, "title": r["path"], "text": f"Artifact version {r['version']}; SHA256 {r['sha256']}; artifact_observed (not a verified finding).\n{text}", "trust": "untrusted"}


def search(tid: str, query: str, limit: int = 5) -> list:
    import re
    terms = re.findall(r"\w+", query)[:20]
    if not terms:
        return []
    with S.db() as c:
        S.topic(c, tid)
        rows = c.execute("SELECT a.id,a.path,a.version,a.sha256 FROM artifact_search JOIN artifact_versions a ON a.id=artifact_search.artifact_id "
                         "JOIN workspaces w ON w.id=a.workspace_id WHERE w.topic_id=? AND a.available=1 AND artifact_search MATCH ? "
                         "ORDER BY bm25(artifact_search) LIMIT ?", (tid, " OR ".join('"'+t+'"' for t in terms), min(10, limit)))
        return [{"id": "artifact:" + r["id"], "title": r["path"], "version": r["version"], "sha256": r["sha256"],
                 "trust": "untrusted", "status": "artifact_observed"} for r in rows]


def open_workspace(wid: str) -> dict:
    from backend.execution.tools import node_argv, which, NO_WINDOW
    w = get(wid)
    root = _root(w)
    package = "@synsci/openscience/bin/openscience" if w["engine"] == "openscience" else "opencode-ai/bin/opencode" if w["engine"] == "opencode" else "@companion-ai/feynman/bin/feynman.js"
    argv = node_argv(which(w["engine"]), package)
    if not argv:
        return {"status": "unavailable", "detail": "Engine CLI is not installed", "capabilities": w["capabilities"]}
    if os.name == "nt" and Path(argv[0]).suffix.lower() in (".cmd", ".bat", ".ps1"):
        return {"status": "unavailable", "detail": "Cannot safely resolve npm launcher to an executable"}
    if w["engine"] == "feynman" and not IS_WIN:
        args = argv + ["--cwd", str(root)]
        return {"status": "terminal_required", "argv": args, "cwd": str(root),
                "command": ("& " + " ".join("'" + a.replace("'", "''") + "'" for a in args)) if os.name == "nt" else __import__('shlex').join(args),
                "detail": "Run in your terminal for native interactive Feynman. No model task was submitted."}
    key = (str(data_dir()), wid)
    with _lock:
        existing = _processes.get(key)
        if existing and existing.poll() is None:
            return {"status": "already_running", "pid": existing.pid, "cwd": str(root)}
        logs = S.safe_child(S.store_dir(), "launch-" + wid + ".log")
        from backend.providers.cli_space import minimal_env
        env = minimal_env()
        # Do not forward PhD Lab provider keys or runtime tokens. Native engine uses its own auth.
        env["OPENSCIENCE_DISABLE_AUTOUPDATE"] = "1"
        args = argv + (["web", str(root)] if w["engine"] == "openscience" else ["--cwd", str(root)])
        if IS_WIN:
            import base64
            command = "& " + " ".join("'" + a.replace("'", "''") + "'" for a in args)
            encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
            # User-requested independent interactive window; errors remain visible in NoExit.
            p = subprocess.Popen(["powershell.exe", "-NoLogo", "-NoProfile", "-NoExit", "-EncodedCommand", encoded],
                                 cwd=str(root), env=env, shell=False,
                                 creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        else:
            with logs.open("ab") as out:
                p = subprocess.Popen(args, cwd=str(root), env=env, stdin=subprocess.DEVNULL,
                                     stdout=out, stderr=subprocess.STDOUT, shell=False, creationflags=NO_WINDOW,
                                     start_new_session=True)
        _processes[key] = p
        try:
            code = p.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            code = None
        status = "started" if code is None else "exited" if code == 0 else "failed"
        with S.db() as c:
            S.event(c, w["topic_id"], "workspace.launch", {"status": status, "pid": p.pid, "exit_code": code, "fidelity": "native_event_verified", "scope": "local process creation only"}, wid=wid)
        return {"status": status, "pid": p.pid, "exit_code": code, "cwd": str(root), "log": str(logs) if not IS_WIN else "",
                "detail": "Opened an independent engine window on the server computer. Its terminal shows authentication and startup errors. No research prompt was submitted." if IS_WIN else "Process creation does not establish model authentication or full activity capture."}


def open_editor(wid: str) -> dict:
    """Open only a registered, project-scoped engine workspace in a separate editor window."""
    from backend.execution.vscode import vscode_cli
    from backend.execution.tools import run_cli
    root = _root(get(wid))
    cli = vscode_cli()
    if not cli:
        raise ValueError("VS Code not found; configure its path in Settings")
    code, _ = run_cli([cli, "--new-window", str(root)], 30)
    if code:
        raise ValueError("VS Code could not open this workspace")
    return {"status": "started", "cwd": str(root), "detail": "VS Code accepted this workspace in a separate window."}
