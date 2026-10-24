"""Code projects (v4.2): `<research project>/code/` is the ROOT of the researcher's code projects.

    code/
      .phdlab-code.json        registry: {"version", "active", "projects": {name: record}, "migrated"}
      experiment1/             one code project = one VS Code folder, one git repository,
      experiment2/             one Python environment, one Docker container (mounted at /workspace)
      .trash/<ts>-<name>/      deleted projects (recoverable by hand)

Every editor / environment action needs an ACTIVE code project: VS Code, Dev Container, Jupyter, git, the sandbox and
the IDE file API resolve their folder through `active_dir()`, which raises NoCodeProject ("NO_CODE_PROJECT: …", HTTP
409) when the researcher has not created or opened one yet — the UI and the CLI then ask to create or open a project.

Per project (record `id` is stable across renames):
    sandbox settings + venv   <project>/sandbox/projects/<id>/   (the v3–v4.1 single workspace keeps <project>/sandbox/)
    Docker container          phdlab-<research hash>-<id>
    VS Code                   .vscode/settings.json → python.defaultInterpreterPath of the project's environment

Migration (additive, reversible): a v4.1 flat `code/` (files directly in it, no registry) is moved — rename only, same
disk — into `code/main/` and registered as the active project with `sandbox: "legacy"`, so its settings, venv and git
history stay in use. Undo: move the contents of code/main/ back to code/ and delete .phdlab-code.json.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

from backend.core.config import data_dir

REGISTRY = ".phdlab-code.json"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
RESERVED = {"con", "prn", "aux", "nul", "trash"}  # Windows device names + the trash folder name
MANAGED_KEYS = ("python.defaultInterpreterPath", "python.terminal.activateEnvironment")
_lock = threading.RLock()
_CACHE: dict = {}  # registry path → (mtime_ns, size, registry): code_dir() is called very often


class CodeProjectError(ValueError):
    pass


class NoCodeProject(Exception):
    """Not a ValueError on purpose: route helpers that map ValueError to 400 let it through to the app handler
    (409 + {"code": "NO_CODE_PROJECT"}), so the UI and the CLI can offer create / open."""

    def __init__(self, msg: str = "Create or open a code project first (Workspace → Code projects, or `phdlab code new <name>`)"):
        super().__init__(f"NO_CODE_PROJECT: {msg}")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def root() -> Path:
    d = data_dir() / "code"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _reg_path() -> Path:
    return root() / REGISTRY


def _write(reg: dict) -> None:
    p = _reg_path()
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=1)
    from backend.memory.store import replace_retry
    replace_retry(tmp, p)
    st = os.stat(p)
    _CACHE[str(p)] = (st.st_mtime_ns, st.st_size, json.loads(json.dumps(reg)))


def valid_name(name: str) -> str:
    name = str(name or "").strip()
    if not NAME_RE.match(name) or name.lower() in RESERVED or name.endswith("."):
        raise CodeProjectError("Project name: letters, digits, '-', '_' or '.', starting with a letter or digit (max 64)")
    return name


def _record(name: str, **extra) -> dict:
    return {"name": name, "id": "cp" + secrets.token_hex(3), "created": _now(), "description": "", "sandbox": "", **extra}


def _migrate(r: Path) -> dict:
    """v4.1 flat layout → code/main/ (rename only)."""
    entries = [p for p in r.iterdir() if p.name not in (REGISTRY, REGISTRY.replace(".json", ".tmp"))]
    reg = {"version": 1, "active": None, "projects": {}, "migrated": None}
    if not entries:
        return reg
    name = "main" if not (r / "main").exists() else "legacy-" + time.strftime("%Y%m%d")
    stage = r / (".migrating-" + secrets.token_hex(3))
    stage.mkdir()
    for p in entries:
        os.replace(p, stage / p.name)
    os.replace(stage, r / name)
    reg["projects"][name] = _record(name, sandbox="legacy", description="Code workspace of v4.1 and earlier (migrated)")
    reg["active"] = name
    reg["migrated"] = {"at": _now(), "into": name, "entries": sorted(p.name for p in entries)}
    return reg


def _load() -> dict:
    with _lock:
        p = _reg_path()
        if p.exists():
            st, hit = os.stat(p), _CACHE.get(str(p))
            if hit and hit[:2] == (st.st_mtime_ns, st.st_size):
                return json.loads(json.dumps(hit[2]))
            try:
                with open(p, encoding="utf-8") as fh:
                    reg = json.load(fh)
                if isinstance(reg.get("projects"), dict):
                    _CACHE[str(p)] = (st.st_mtime_ns, st.st_size, json.loads(json.dumps(reg)))
                    return reg
            except ValueError:
                pass
            os.replace(p, p.with_name(f"{REGISTRY}.corrupt-{int(time.time())}"))
            reg = {"version": 1, "active": None, "projects": {}, "migrated": None}
        else:
            reg = _migrate(root())
        _write(reg)
        return reg


def _folder(name: str) -> Path:
    return root() / name


def sandbox_dir(rec: dict) -> Path:
    base = data_dir() / "sandbox"
    d = base if rec.get("sandbox") == "legacy" else base / "projects" / rec["id"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def active() -> dict | None:
    reg = _load()
    name = reg.get("active")
    rec = reg["projects"].get(name) if name else None
    if rec and _folder(name).is_dir():
        return rec
    return None


def active_dir() -> Path:
    rec = active()
    if not rec:
        raise NoCodeProject()
    return _folder(rec["name"])


def active_dir_or_none() -> Path | None:
    rec = active()
    return _folder(rec["name"]) if rec else None


def active_sandbox_dir() -> Path:
    rec = active()
    if not rec:
        raise NoCodeProject()
    return sandbox_dir(rec)


def _summary(rec: dict, act: str | None) -> dict:
    f = _folder(rec["name"])
    sb = data_dir() / "sandbox" / ("" if rec.get("sandbox") == "legacy" else f"projects/{rec['id']}")
    return {**rec, "path": str(f), "exists": f.is_dir(), "active": rec["name"] == act, "registered": True,
            "git": (f / ".git").exists(), "devcontainer": (f / ".devcontainer" / "devcontainer.json").exists(),
            "vscode_settings": (f / ".vscode" / "settings.json").exists(), "venv": any(sb.glob("venv*/pyvenv.cfg")),
            "container": container_for(rec)}


def container_for(rec: dict) -> str:
    import hashlib
    # Preserve legacy resource names; this digest is not an authorization token.
    return f"phdlab-{hashlib.sha1(str(data_dir().resolve()).encode(), usedforsecurity=False).hexdigest()[:10]}-{rec['id']}"


def list_projects() -> dict:
    reg = _load()
    act = reg.get("active") if reg.get("active") in reg["projects"] else None
    items = [_summary(r, act) for r in reg["projects"].values()]
    known = set(reg["projects"])
    found = [{"name": p.name, "path": str(p), "registered": False, "active": False, "git": (p / ".git").exists()}
             for p in sorted(root().iterdir()) if p.is_dir() and p.name not in known and NAME_RE.match(p.name)]
    return {"root": str(root()), "active": act, "projects": sorted(items, key=lambda x: x["name"].lower()),
            "unregistered": found, "migrated": reg.get("migrated")}


def _activate(reg: dict, name: str | None) -> None:
    reg["active"] = name
    _write(reg)


def create(name: str, description: str = "", git: bool = True, vscode: bool = True, settings: dict | None = None,
           seed: bool = True) -> dict:
    name = valid_name(name)
    with _lock:
        reg = _load()
        f = _folder(name)
        if name in reg["projects"] or f.exists():
            raise CodeProjectError(f"A code project or folder named '{name}' already exists — open it instead")
        f.mkdir(parents=True)
        rec = _record(name, description=str(description or "")[:300])
        reg["projects"][name] = rec
        _activate(reg, name)
    notes = []
    if settings:
        from backend.execution.sandbox import save_settings
        save_settings(settings)
    if seed:
        (f / "README.md").write_text(f"# {name}\n\n{rec['description'] or 'Code project of PhD Research Lab.'}\n\n"
                                     "Run it from Workspace & Runs (sandbox) or `phdlab run \"python main.py\"`.\n"
                                     "Final metrics: write `$RUN_DIR/metrics.json`.\n", "utf-8")
        (f / "requirements.txt").write_text("", "utf-8")
    if git:
        notes.append(_git_init())
    if vscode:
        notes.append(sync_vscode()["note"])
    return {**info(name), "notes": [n for n in notes if n]}


def _git_init() -> str:
    from backend.execution import gitops
    if not gitops.git_exe():
        return "Git is not installed — the project has no repository yet (Source Control → Initialise later)"
    try:
        gitops.init()
        return "git repository initialised (branch main)"
    except gitops.GitError as e:
        return f"git init failed: {e}"


def info(name: str) -> dict:
    reg = _load()
    if name not in reg["projects"]:
        raise CodeProjectError(f"Unknown code project '{name}'")
    return _summary(reg["projects"][name], reg.get("active"))


def open_project(name: str) -> dict:
    """Activate a registered project, or register + activate a folder that already exists in code/."""
    name = valid_name(name)
    with _lock:
        reg = _load()
        if name not in reg["projects"]:
            if not _folder(name).is_dir():
                raise CodeProjectError(f"No code project or folder '{name}' in {root()}")
            reg["projects"][name] = _record(name, description="Registered from an existing folder")
        elif not _folder(name).is_dir():
            raise CodeProjectError(f"The folder of '{name}' is missing ({_folder(name)})")
        _activate(reg, name)
    return info(name)


def close() -> dict:
    with _lock:
        reg = _load()
        _activate(reg, None)
    return list_projects()


def rename(name: str, new_name: str) -> dict:
    name, new_name = valid_name(name), valid_name(new_name)
    with _lock:
        reg = _load()
        if name not in reg["projects"]:
            raise CodeProjectError(f"Unknown code project '{name}'")
        if new_name in reg["projects"] or _folder(new_name).exists():
            raise CodeProjectError(f"'{new_name}' already exists")
        try:
            os.replace(_folder(name), _folder(new_name))
        except OSError as e:
            raise CodeProjectError(f"Could not rename the folder (is it open in VS Code or a terminal?): {e}")
        rec = reg["projects"].pop(name)
        rec["name"] = new_name
        reg["projects"][new_name] = rec
        if reg.get("active") == name:
            reg["active"] = new_name
        _write(reg)
    return info(new_name)


def delete(name: str, confirm: str, remove_container: bool = False) -> dict:
    """Moves the folder to code/.trash/ (never a hard delete). `confirm` must repeat the project name."""
    name = valid_name(name)
    if confirm != name:
        raise CodeProjectError("Type the project name to confirm the deletion")
    with _lock:
        reg = _load()
        if name not in reg["projects"]:
            raise CodeProjectError(f"Unknown code project '{name}'")
        rec = reg["projects"].pop(name)
        dst = None
        if _folder(name).exists():
            dst = root() / ".trash" / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(_folder(name)), str(dst))
        if reg.get("active") == name:
            reg["active"] = None
        _write(reg)
    out = {"deleted": name, "trash": str(dst) if dst else "", "container_removed": False}
    if remove_container:
        from backend.execution.sandbox import docker
        code, _ = docker(["rm", "-f", container_for(rec)], 60)
        out["container_removed"] = code == 0
    return out


def sync_vscode() -> dict:
    """Point VS Code at the project's Python environment (.vscode/settings.json; other keys are kept)."""
    from backend.execution.sandbox import local_python_info
    f = active_dir() / ".vscode" / "settings.json"
    cur = {}
    if f.exists():
        try:
            cur = json.loads(f.read_text("utf-8") or "{}")
        except ValueError:
            return {"written": False, "path": str(f), "note": ".vscode/settings.json has comments or is not plain JSON — "
                                                              "left unchanged (set the interpreter in VS Code)"}
    py = local_python_info()["python"]
    want = {MANAGED_KEYS[0]: py, MANAGED_KEYS[1]: True}
    if all(cur.get(k) == v for k, v in want.items()):
        return {"written": False, "path": str(f), "python": py, "note": "VS Code already uses the project environment"}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({**cur, **want}, indent=2), "utf-8")
    return {"written": True, "path": str(f), "python": py, "note": f"VS Code interpreter → {py}"}


def environment() -> dict:
    """Git, Python environment, Docker container and VS Code state of the active project (what the UI/CLI show)."""
    rec = active()
    if not rec:
        raise NoCodeProject()
    from backend.execution import gitops
    from backend.execution.sandbox import container_name, effective_image, effective_mode, load_settings, local_python_info
    s = load_settings()
    return {"project": info(rec["name"]), "git": gitops.head_info(), "python": local_python_info(),
            "sandbox": {"mode": s["mode"], "effective_mode": effective_mode(s), "image": effective_image(s), "gpu": s["gpu"]},
            "container": container_name()}
