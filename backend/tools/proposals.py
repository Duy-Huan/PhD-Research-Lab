"""Agent-proposed tools: propose -> implement in a sandbox area -> validate -> promote -> (rollback).

  propose(manifest, files)   an agent writes a candidate tool (manifest + source files) into
                             <project data>/tools/_proposals/<id>/<version>/ -- never into the active registry
  validate(id, version)      schema/static checks, then the manifest's own `examples` executed through the normal
                             runtime under a validation-only grant. Agent-written Python runs inside a container
                             (no network, read-only code mount); when no container is available validation is
                             BLOCKED unless the owner set tools.allow_host_validation. The report is bound to the
                             exact proposal digest.
  promote(id, version, by)   requires a PASS report for the unchanged digest and a named approver; copies the
                             immutable version into tools/<id>/<version>/ and activates it. Existing versions are
                             never overwritten.
  rollback(id, to, by)       re-points the active version to an existing earlier version (history retained).

A promoted tool gains NO authority: every later call still needs a Grant. Proposals cannot be kind=native, cannot reuse
builtin ids and cannot touch application source, tests or CI gates (they live only in project data).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from backend.tools.registry import REGISTRY, Registry, active_version, builtin_specs, load_manifest, tools_root
from backend.tools.runtime import Grant, Runtime
from backend.tools.spec import ToolError, ToolSpec, parse_version

FILE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,80}(?:/[A-Za-z0-9_][A-Za-z0-9_.-]{0,80}){0,3}$")
MAX_FILES, MAX_BYTES = 20, 512_000
VALIDATION_IMAGE = "python:3.12-slim"


def _dir(tool_id: str, version: str) -> Path:
    parse_version(version)
    if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){0,3}", tool_id or ""):
        raise ToolError("invalid_input", "Invalid tool id")
    return tools_root() / "_proposals" / tool_id / version


def digest(folder: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(x for x in folder.rglob("*") if x.is_file() and x.name != "validation.json"):
        h.update(p.relative_to(folder).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def propose(manifest: dict, files: dict | None = None, *, proposer: str = "agent") -> dict:
    files = dict(files or {})
    if not isinstance(manifest, dict) or manifest.get("kind") == "native":
        raise ToolError("invalid_spec", "A proposal must be a manifest object and cannot be a native tool")
    if manifest.get("id") in {s.id for s in builtin_specs()}:
        raise ToolError("invalid_spec", f"{manifest.get('id')} is a reserved builtin tool id")
    if len(files) > MAX_FILES or sum(len(str(v).encode()) for v in files.values()) > MAX_BYTES:
        raise ToolError("budget_exceeded", f"At most {MAX_FILES} files / {MAX_BYTES} bytes per proposal")
    folder = _dir(str(manifest.get("id", "")), str(manifest.get("version", "1.0.0")))
    if folder.exists():
        raise ToolError("invalid_input", "This proposal version already exists; propose a new version")
    if (tools_root() / manifest["id"] / manifest.get("version", "1.0.0")).exists():
        raise ToolError("invalid_input", "That version is already promoted; versions are immutable")
    for name in files:
        if not FILE.match(name) or name == "tool.json" or ".." in name:
            raise ToolError("invalid_input", f"Illegal proposal file name {name!r}")
    folder.mkdir(parents=True)
    (folder / "tool.json").write_text(json.dumps({**manifest, "source": f"proposal:{proposer}"}, indent=1), "utf-8")
    for name, text in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(str(text), "utf-8")
    try:
        spec = load_manifest(folder / "tool.json", source=f"proposal:{proposer}")
    except ToolError:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return {"id": spec.id, "version": spec.version, "status": "proposed", "digest": digest(folder),
            "path": str(folder.relative_to(tools_root()))}


def _validation_spec(spec: ToolSpec, folder: Path, host_ok: bool) -> ToolSpec:
    """Agent-written python executes in a container unless the owner explicitly allowed host validation."""
    if spec.kind != "python":
        return spec
    from backend.tools.adapters import Container
    image = _image()
    container = spec.model_copy(update={"kind": "container", "execution": {
        "image": image, "command": ["python", "-I", "/tool/" + spec.execution["entry"]], "home": str(folder.resolve())}})
    if Container.probe(container)["available"]:
        return container
    if host_ok:
        return spec
    raise ToolError("unavailable", f"No container ({image}) available to validate agent-written code",
                    hint="Start Docker with the image present, or the owner may set tools.allow_host_validation")


def _image() -> str:
    from backend.core.config import load_config
    return (load_config().get("tools") or {}).get("validation_image") or VALIDATION_IMAGE


def _subset(expected, actual) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _subset(v, actual[k]) for k, v in expected.items())
    return expected == actual


def validate(tool_id: str, version: str, *, runtime: Runtime | None = None, allowed_permissions: list | None = None) -> dict:
    """`allowed_permissions` bounds a self-validation requested by an agent: its own grant's permissions. A proposal
    that needs more than its proposer holds is not executed (no authority escalation through validation)."""
    from backend.core.config import load_config
    folder = _dir(tool_id, version)
    if not (folder / "tool.json").is_file():
        raise ToolError("not_found", f"No proposal {tool_id}@{version}")
    report = {"id": tool_id, "version": version, "digest": digest(folder), "checks": [], "examples": [],
              "validated_at": time.time()}
    try:
        spec = load_manifest(folder / "tool.json", source="proposal")
        report["checks"].append({"check": "manifest", "status": "PASS"})
        if spec.kind == "python":
            entry = folder / spec.execution.get("entry", "")
            compile(entry.read_text("utf-8"), str(entry), "exec")
            report["checks"].append({"check": "python_compiles", "status": "PASS"})
        if not spec.examples:
            raise ToolError("invalid_spec", "A proposal must declare at least one example {args, expect} to validate")
        if allowed_permissions is not None and not set(spec.permissions) <= set(allowed_permissions):
            raise ToolError("permission_denied", f"Proposal needs {sorted(set(spec.permissions) - set(allowed_permissions))} "
                                                 "which its proposer does not hold; the owner must validate it")
        host_ok = bool((load_config().get("tools") or {}).get("allow_host_validation"))
        run_spec = _validation_spec(spec, folder, host_ok)
        report["executed_as"] = run_spec.kind
        sandbox_registry = Registry(extra_sources=[lambda: [run_spec]])
        rt = runtime or Runtime(sandbox_registry, workers=1)
        rt.registry = sandbox_registry
        grant = Grant(principal=f"validation:{spec.ref}", tools=[spec.id], permissions=list(spec.permissions),
                      allow_mutation=spec.mutates, max_calls=len(spec.examples), max_wall_s=600)
        for i, example in enumerate(spec.examples):
            job = rt.run(spec.id, example.get("args") or {}, grant, version=spec.version)
            ok = job["status"] == "succeeded" and _subset(example.get("expect") or {}, job["result"])
            report["examples"].append({"example": i, "job": job["id"], "status": job["status"],
                                       "matched": ok, "error": job["error"]})
        passed = all(e["matched"] for e in report["examples"])
        report["status"] = "PASS" if passed else "FAIL"
    except ToolError as e:
        report["status"] = "BLOCKED" if e.code in ("unavailable", "permission_denied") else "FAIL"
        report["error"] = e.as_dict()
    except (SyntaxError, OSError, UnicodeDecodeError) as e:
        report["status"], report["error"] = "FAIL", {"code": "invalid_spec", "message": f"{type(e).__name__}: {e}"[:500]}
    (folder / "validation.json").write_text(json.dumps(report, indent=1, default=str), "utf-8")
    return report


def _history(tool_dir: Path, version: str, by: str, action: str) -> None:
    try:
        data = json.loads((tool_dir / "active.json").read_text("utf-8"))
    except (OSError, ValueError):
        data = {"history": []}
    data["history"] = (data.get("history") or []) + [{"version": version, "by": by, "action": action, "at": time.time()}]
    data["version"] = version
    (tool_dir / "active.json").write_text(json.dumps(data, indent=1), "utf-8")


def promote(tool_id: str, version: str, approved_by: str) -> dict:
    if not (approved_by or "").strip() or approved_by.startswith(("agent", "model", "validation:")):
        raise ToolError("permission_denied", "Promotion needs a named human/owner approver, not the proposing agent")
    folder = _dir(tool_id, version)
    try:
        report = json.loads((folder / "validation.json").read_text("utf-8"))
    except (OSError, ValueError) as e:
        raise ToolError("invalid_input", "Validate the proposal before promotion") from e
    if report.get("status") != "PASS" or report.get("digest") != digest(folder):
        raise ToolError("invalid_input", "Promotion requires a PASS validation of the unchanged proposal")
    target = tools_root() / tool_id / version
    if target.exists():
        raise ToolError("invalid_input", "Version already promoted; versions are immutable")
    shutil.copytree(folder, target)
    _history(target.parent, version, approved_by, "promote")
    REGISTRY.resolve(tool_id, version)  # confirms the promoted manifest loads in the live registry
    return {"id": tool_id, "version": version, "status": "active", "approved_by": approved_by}


def rollback(tool_id: str, to_version: str, approved_by: str) -> dict:
    if not (approved_by or "").strip():
        raise ToolError("permission_denied", "Rollback needs a named approver")
    tool_dir = tools_root() / tool_id
    if not (tool_dir / to_version / "tool.json").is_file():
        raise ToolError("not_found", f"{tool_id}@{to_version} was never promoted")
    previous = active_version(tool_dir)
    _history(tool_dir, to_version, approved_by, "rollback")
    return {"id": tool_id, "active": to_version, "previous": previous}


def listing() -> list:
    root = tools_root() / "_proposals"
    out = []
    for manifest in sorted(root.glob("*/*/tool.json")) if root.is_dir() else []:
        try:
            v = json.loads((manifest.parent / "validation.json").read_text("utf-8")).get("status")
        except (OSError, ValueError):
            v = "NOT_VALIDATED"
        out.append({"id": manifest.parent.parent.name, "version": manifest.parent.name, "validation": v})
    return out
