"""Folder picking for the local app.

1. Native dialog: a short-lived Python/Tk subprocess shows the operating system's
   "Select folder" dialog (works on Windows, macOS and Linux desktops). A subprocess keeps
   Tk away from the server's threads.
2. Fallback: a server-side directory listing used by the in-app folder browser
   (when Tk is missing, blocked, or there is no desktop session).
"""
from __future__ import annotations

import json
import os
import string
import subprocess
import sys
from pathlib import Path

TK_SCRIPT = r"""
import json, sys
try:
    import tkinter as tk
    from tkinter import filedialog
except Exception as e:
    print(json.dumps({"error": "tkinter unavailable: %s" % e})); sys.exit(0)
try:
    root = tk.Tk(); root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    root.update()
    path = filedialog.askdirectory(initialdir=sys.argv[1] or None, title=sys.argv[2], mustexist=False, parent=root)
    root.destroy()
    print(json.dumps({"path": path or ""}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""


def pick_folder_native(initial: str = "", title: str = "Select folder") -> dict:
    """Returns {"native": True, "path": str|"" (""=cancelled)} or {"native": False, "error": ...}."""
    init = initial if initial and Path(initial).exists() else str(Path.home())
    try:
        r = subprocess.run([sys.executable, "-c", TK_SCRIPT, init, title], capture_output=True, text=True, timeout=600)
        out = json.loads((r.stdout or "").strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr[-300:] or "no output"}
    except Exception as e:  # timeout, blocked executable, no display…
        return {"native": False, "error": str(e)}
    if "error" in out:
        return {"native": False, "error": out["error"]}
    path = out.get("path") or ""
    return {"native": True, "path": str(Path(path).resolve()) if path else "", "cancelled": not path}


def _drives() -> list:
    if os.name != "nt":
        return [{"name": "/", "path": "/"}]
    return [{"name": f"{d}:", "path": f"{d}:\\"} for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


def list_dir(path: str = "") -> dict:
    p = Path(path).expanduser() if path else Path.home()
    try:
        p = p.resolve()
    except OSError:
        p = Path.home()
    while not p.exists() and p != p.parent:  # walk up to the nearest existing folder
        p = p.parent
    dirs, pdfs, error = [], 0, ""
    try:
        with os.scandir(p) as it:
            for e in it:
                try:
                    if e.is_dir() and not e.name.startswith((".", "$")) and e.name not in ("System Volume Information",):
                        dirs.append({"name": e.name, "path": str(Path(e.path))})
                    elif e.is_file() and e.name.lower().endswith(".pdf"):
                        pdfs += 1
                except OSError:
                    continue
    except PermissionError:
        error = "Access denied"
    except OSError as e:
        error = str(e)
    dirs.sort(key=lambda d: d["name"].lower())
    parent = str(p.parent) if p.parent != p else ""
    project = (p / "project_meta.json").exists()
    return {"path": str(p), "parent": parent, "dirs": dirs[:2000], "pdfs": pdfs, "is_project": project,
            "drives": _drives(), "home": str(Path.home()), "sep": os.sep, "error": error}


def make_dir(parent: str, name: str) -> dict:
    name = (name or "").strip()
    if not name or any(c in name for c in '\\/:*?"<>|') or name in (".", ".."):
        raise ValueError("Invalid folder name")
    d = Path(parent).expanduser().resolve() / name
    d.mkdir(parents=False, exist_ok=True)
    return list_dir(str(d))
