"""IDE workspace files (v3.0): tree, read, write, create, rename, delete (to .trash), upload, search, blueprint seeding.

Every path is resolved inside the project's code/ folder — the UI and the AI can never touch files outside it.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from .sandbox import code_dir

IGNORE_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", ".trash", "node_modules", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
TEXT_EXT = {".py", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".tex", ".bib", ".sh", ".bat", ".csv",
            ".tsv", ".m", ".r", ".jl", ".c", ".h", ".cpp", ".hpp", ".cu", ".js", ".ts", ".html", ".css", ".sty", ".cls",
            ".ipynb", ".gitignore", ".dockerfile", ".env", ".log", ".sql", ".xml", ".v", ".sv", ".vhd", ""}
MAX_READ = 2 * 1024 * 1024


class FsError(Exception):
    pass


def safe(rel: str) -> Path:
    root = code_dir().resolve()
    rel = (rel or "").replace("\\", "/").lstrip("/")
    p = (root / rel).resolve()
    if p != root and root not in p.parents:
        raise FsError("Path outside the workspace")
    return p


def rel(p: Path) -> str:
    return str(p.resolve().relative_to(code_dir().resolve())).replace("\\", "/")


def tree(max_entries: int = 4000) -> dict:
    root = code_dir()
    count = 0

    def walk(d: Path) -> list:
        nonlocal count
        items = []
        try:
            entries = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except OSError:
            return items
        for e in entries:
            if count > max_entries:
                break
            if e.name in IGNORE_DIRS:
                continue
            count += 1
            if e.is_dir():
                items.append({"name": e.name, "path": rel(e), "dir": True, "children": walk(e)})
            else:
                try:
                    size = e.stat().st_size
                except OSError:
                    size = 0
                items.append({"name": e.name, "path": rel(e), "dir": False, "size": size})
        return items

    return {"root": str(root), "children": walk(root), "truncated": count > max_entries}


def is_text(p: Path) -> bool:
    if p.suffix.lower() in TEXT_EXT or p.name in ("Dockerfile", "Makefile", "LICENSE", "requirements.txt"):
        try:
            with open(p, "rb") as f:
                return b"\x00" not in f.read(4096)
        except OSError:
            return False
    return False


def read(path: str) -> dict:
    p = safe(path)
    if not p.is_file():
        raise FsError("File not found")
    st = p.stat()
    if not is_text(p):
        return {"path": rel(p), "binary": True, "size": st.st_size, "mtime": st.st_mtime}
    if st.st_size > MAX_READ:
        raise FsError("File too large for the editor (> 2 MB)")
    return {"path": rel(p), "content": p.read_text("utf-8", errors="replace"), "size": st.st_size, "mtime": st.st_mtime}


def write(path: str, content: str, expected_mtime: float | None = None) -> dict:
    p = safe(path)
    if p.is_dir():
        raise FsError("Is a folder")
    if expected_mtime and p.exists() and abs(p.stat().st_mtime - expected_mtime) > 0.01:
        raise FsError("CONFLICT: the file changed on disk (another tab, the AI or a run) — reload it first")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp~")
    tmp.write_text(content, "utf-8", newline="")
    os.replace(tmp, p)
    return {"path": rel(p), "size": p.stat().st_size, "mtime": p.stat().st_mtime}


def create(path: str, folder: bool = False) -> dict:
    p = safe(path)
    if p.exists():
        raise FsError("Already exists")
    if folder:
        p.mkdir(parents=True)
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", "utf-8")
    return {"path": rel(p)}


def rename(src: str, dst: str) -> dict:
    a, b = safe(src), safe(dst)
    if not a.exists():
        raise FsError("Source not found")
    if b.exists():
        raise FsError("Target already exists")
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(a), str(b))
    return {"path": rel(b)}


def delete(path: str) -> dict:
    """Move to code/.trash/<timestamp>/ (recoverable, ignored by git)."""
    p = safe(path)
    if p == code_dir().resolve():
        raise FsError("Cannot delete the workspace root")
    if not p.exists():
        raise FsError("Not found")
    dst = code_dir() / ".trash" / time.strftime("%Y%m%d-%H%M%S") / rel(p)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(dst))
    return {"trashed": rel(p)}


def upload(path: str, data: bytes) -> dict:
    p = safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return {"path": rel(p), "size": len(data)}


def search(query: str, max_hits: int = 300) -> list:
    if not query:
        return []
    rx = re.compile(re.escape(query), re.I)
    hits = []
    for p in code_dir().rglob("*"):
        if any(part in IGNORE_DIRS for part in p.parts) or not p.is_file() or not is_text(p) or p.stat().st_size > MAX_READ:
            continue
        try:
            for i, line in enumerate(p.read_text("utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append({"path": rel(p), "line": i, "text": line.strip()[:200]})
                    if len(hits) >= max_hits:
                        return hits
        except OSError:
            continue
    return hits


def snapshot(max_files: int = 40, max_chars: int = 60000, focus: list | None = None) -> str:
    """Compact view of the workspace for the coder agent: file list + contents of the most relevant text files."""
    files = [p for p in code_dir().rglob("*") if p.is_file() and not any(part in IGNORE_DIRS for part in p.parts)]
    listing = "\n".join(f"{rel(p)}  ({p.stat().st_size} B)" for p in sorted(files)[:300])
    focus = [f for f in (focus or []) if f]
    order = sorted(files, key=lambda p: (rel(p) not in focus, p.suffix != ".py", -p.stat().st_mtime))
    parts, used = [], 0
    for p in order[:max_files]:
        if not is_text(p) or p.stat().st_size > 120_000 or p.suffix in (".csv", ".log", ".tsv"):
            continue
        txt = p.read_text("utf-8", errors="replace")
        if used + len(txt) > max_chars:
            continue
        used += len(txt)
        parts.append(f"=== FILE: {rel(p)} ===\n{txt}")
    return f"WORKSPACE FILES:\n{listing or '(empty workspace)'}\n\n" + "\n\n".join(parts)


GITIGNORE = """# PhD Research Lab — code workspace
__pycache__/
*.pyc
.trash/
.ipynb_checkpoints/
*.pt
*.pth
*.ckpt
*.h5
data/raw/
outputs/
wandb/
.env
"""


def seed(design_md: str = "", skeleton: str = "") -> list:
    """Create a starter project from the Tool 2 blueprint (never overwrites existing files)."""
    created = []
    root = code_dir()

    def put(name: str, content: str):
        p = root / name
        if not p.exists() and content:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, "utf-8")
            created.append(name)

    put(".gitignore", GITIGNORE)
    if skeleton:
        put("experiment_skeleton.py", skeleton)
    if design_md:
        put("docs/experiment_design.md", design_md)
    put("README.md", "# Research code\n\nCreated by PhD Research Lab. Run experiments from the 💻 Code IDE (Docker sandbox).\n\n"
                     "Conventions picked up automatically after each run:\n"
                     "- write final metrics to `$RUN_DIR/metrics.json` (a flat JSON object of numbers)\n"
                     "- log progress lines like `epoch 3 loss=0.12 psnr=28.4` (plotted live)\n"
                     "- save figures to `$RUN_DIR/` or `outputs/` (PNG/SVG/PDF)\n")
    put("requirements.txt", "numpy\nmatplotlib\n")
    return created
