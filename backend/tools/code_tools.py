"""Code projects and versioned edits as registry tools (v6.6.4, agent/PLAN_6.6.4_L3.md A3).

Found live (docs/qa/evidence/cli-agent-registry-662/live-codex.md): the agent could not create or open a code project,
and a native coding run could only write a new experiments/<run>/ folder, so a one-line fix became a one-line file.
Now an agent with workspace_write lists, creates and opens code projects, and edits an existing file with exact
replacements bound to the file's current sha256. Every patch is journalled outside the code folder (old/new sha256 and
the edits) and, when the project is a git repository, committed on its own with only that file. Nothing is deleted,
renamed or executed here; running stays with the sandbox and the governed protocol.
"""
from __future__ import annotations

import hashlib
import json
import time

from backend.tools.spec import ToolError, ToolSpec

MAX_FILE = 1024 * 1024
MAX_EDITS = 50


def _spec(id_, description, schema, fn, mutates):
    return ToolSpec(id=id_, version="1.0.0", kind="native", source="builtin", description=description,
                    capabilities=["code", "project", *(["edit"] if "patch" in id_ else [])],
                    permissions=["workspace_write"] if mutates else [], mutates=mutates, idempotent=not mutates,
                    input_schema=schema, execution={"callable": f"backend.tools.code_tools:{fn}"})


def specs() -> list[ToolSpec]:
    name = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"}
    return [
        _spec("code.projects", "Code projects of the research project and which one is open", {"type": "object", "properties": {}},
              "projects", False),
        _spec("code.create_project", "Create a code project (own folder, git repository, Python environment) and open it",
              {"type": "object", "required": ["name"], "properties": {"name": name, "description": {"type": "string", "maxLength": 300}}},
              "create_project", True),
        _spec("code.open_project", "Open an existing code project so the sandbox, files and protocols use it",
              {"type": "object", "required": ["name"], "properties": {"name": name}}, "open_project", True),
        _spec("code.apply_patch",
              "Edit an existing text file of the open code project in place. Give the file's current sha256 (from a read or "
              "a previous patch) and exact replacements; each `old` must occur exactly once. The patch is journalled and, in "
              "a git repository, committed with only this file. Use it to iterate on your code instead of writing a new folder.",
              {"type": "object", "required": ["path", "sha256", "edits", "message"], "properties": {
                  "path": {"type": "string", "maxLength": 300},
                  "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                  "edits": {"type": "array", "minItems": 1, "maxItems": MAX_EDITS, "items": {
                      "type": "object", "required": ["old", "new"],
                      "properties": {"old": {"type": "string", "minLength": 1}, "new": {"type": "string"}}}},
                  "message": {"type": "string", "minLength": 1, "maxLength": 200}}},
              "apply_patch", True),
        _spec("code.file_version", "sha256, size and last patches of a file in the open code project (no content)",
              {"type": "object", "required": ["path"], "properties": {"path": {"type": "string", "maxLength": 300}}},
              "file_version", False),
    ]


def _errors(fn):
    def wrapped(args, ctx):
        from backend.execution import code_projects, files
        try:
            return fn(args, ctx)
        except code_projects.NoCodeProject as e:
            raise ToolError("unavailable", str(e), hint="Create or open a code project with code.create_project / code.open_project") from e
        except (code_projects.CodeProjectError, files.FsError) as e:
            raise ToolError("invalid_input", str(e)[:500]) from e
    wrapped.__name__ = fn.__name__
    return wrapped


@_errors
def projects(args, ctx) -> dict:
    from backend.execution import code_projects
    listed = code_projects.list_projects()
    return {"active": listed["active"], "projects": [{k: p.get(k) for k in ("name", "description", "git", "active")} for p in listed["projects"]],
            "unregistered": [p["name"] for p in listed["unregistered"]]}


@_errors
def create_project(args, ctx) -> dict:
    from backend.execution import code_projects
    made = code_projects.create(str(args["name"]), str(args.get("description") or ""), git=True, vscode=False)
    return {"name": made["name"], "active": True, "notes": made.get("notes", [])}


@_errors
def open_project(args, ctx) -> dict:
    from backend.execution import code_projects
    return {"name": code_projects.open_project(str(args["name"]))["name"], "active": True}


def _journal():
    from backend.execution import code_projects
    return code_projects.sandbox_dir(code_projects.active()) / "patches.jsonl"


def _target(path: str):
    from backend.execution import code_projects, files
    root = code_projects.active_dir().resolve()
    p = files.safe(path)
    rel = p.relative_to(root).as_posix()
    if not rel or rel == "." or rel.split("/")[0] == ".git":
        raise ToolError("invalid_input", "Choose a file inside the code project (not .git)")
    if not p.is_file():
        raise ToolError("not_found", f"No file {rel} in the open code project", hint="Create new files with sandbox_manage_files write")
    if p.stat().st_size > MAX_FILE:
        raise ToolError("invalid_input", "Files over 1 MB are not patched")
    return p, rel


def _history(rel: str, limit: int = 5) -> list:
    try:
        lines = _journal().read_text("utf-8").splitlines()
    except OSError:
        return []
    out = [json.loads(line) for line in lines if line.strip()]
    return [{k: e[k] for k in ("at", "new_sha256", "message", "commit", "by")} for e in out if e["path"] == rel][-limit:]


@_errors
def file_version(args, ctx) -> dict:
    p, rel = _target(str(args["path"]))
    raw = p.read_bytes()
    return {"path": rel, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "patches": _history(rel)}


@_errors
def apply_patch(args, ctx) -> dict:
    from backend.execution import gitops
    p, rel = _target(str(args["path"]))
    raw = p.read_bytes()
    old_sha = hashlib.sha256(raw).hexdigest()
    if old_sha != args["sha256"]:
        raise ToolError("invalid_input", f"{rel} changed since you read it (now {old_sha})", hint="Read the file again, then patch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ToolError("invalid_input", "Only UTF-8 text files are patched") from e
    newline = "\r\n" if "\r\n" in text else "\n"
    for i, edit in enumerate(args["edits"]):
        old, new = edit["old"], edit["new"]
        if newline == "\r\n":  # agents write LF; keep the file's own line endings
            old, new = old.replace("\r\n", "\n").replace("\n", "\r\n"), new.replace("\r\n", "\n").replace("\n", "\r\n")
        count = text.count(old)
        if count != 1:
            raise ToolError("invalid_input", f"Edit {i + 1}: `old` occurs {count} times in {rel}; it must occur exactly once",
                            hint="Include more surrounding lines so the text is unique")
        text = text.replace(old, new, 1)
    data = text.encode("utf-8")
    if data == raw:
        raise ToolError("invalid_input", "The edits do not change the file")
    tmp = p.with_name(p.name + ".phdlab-tmp")
    tmp.write_bytes(data)
    tmp.replace(p)
    new_sha = hashlib.sha256(data).hexdigest()
    by = getattr(ctx, "principal", "") or "agent"
    message = f"{str(args['message']).strip()[:200]} (agent patch by {by[:60]})"
    commit = None
    if gitops.is_repo():
        name, email = gitops._identity()
        gitops.G(["add", "--", rel])
        gitops.G(["-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-m", message, "--", rel])
        commit = gitops.G(["rev-parse", "HEAD"]).strip()
    entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "path": rel, "old_sha256": old_sha, "new_sha256": new_sha,
             "edits": args["edits"], "message": message, "commit": commit, "by": by[:100]}
    journal = _journal()
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"path": rel, "old_sha256": old_sha, "sha256": new_sha, "bytes": len(data), "commit": commit,
            "versioned": "git" if commit else "journal"}
