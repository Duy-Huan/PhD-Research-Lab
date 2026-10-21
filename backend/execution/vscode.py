"""VS Code is the experiment editor: PhD Lab opens the active code project in it (its interpreter is the project's venv,
see code_projects.sync_vscode) and brings the results back (execution/sync.py). It never re-implements an editor.

Security: actions take a TARGET NAME ("code" = the active code project, "project" = the research project folder),
never an arbitrary path from the browser; every resolved path is checked against that allow-list.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from backend.core.config import data_dir, load_config
from backend.execution.tools import IntegrationError, run_cli, which

IS_WIN = sys.platform.startswith("win")


def targets() -> dict:
    """"code" is the ACTIVE code project and only exists while one is open (code_projects.py)."""
    from backend.execution.code_projects import active_dir_or_none
    code = active_dir_or_none()
    return {**({"code": code.resolve()} if code else {}), "project": data_dir().resolve()}


def resolve_target(name: str) -> Path:
    t = targets()
    if name == "code" and name not in t:
        from backend.execution.code_projects import NoCodeProject
        raise NoCodeProject()
    if name not in t:
        raise IntegrationError(f"Unknown workspace target '{name}' (allowed: {', '.join(t)})")
    p = t[name]
    if not p.is_dir():
        raise IntegrationError(f"{p} does not exist")
    return p


def vscode_cli() -> str | None:
    custom = (load_config()["workspace"].get("vscode_path") or "").strip()
    if custom and Path(custom).is_file():
        return custom
    p = which("code", "code-insiders", "codium")
    if p:
        return p
    if IS_WIN:
        for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
            for sub in ("Programs\\Microsoft VS Code\\bin\\code.cmd", "Microsoft VS Code\\bin\\code.cmd"):
                c = Path(base) / sub
                if base and c.is_file():
                    return str(c)
    return None


def open_folder(target: str = "code") -> dict:
    cli = vscode_cli()
    if not cli:
        raise IntegrationError("VS Code not found — install VS Code or set its path in Settings → Experiments & hardware")
    p = resolve_target(target)
    code, out = run_cli([cli, str(p)], 30)
    if code != 0:
        raise IntegrationError(f"`code` exited with {code}: {out.strip()[-300:]}")
    return {"launched": True, "path": str(p), "note": "VS Code accepted the request (the window opens on this computer)."}
