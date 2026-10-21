"""Figures a paper references: run figures (`figures/run-<job>--<file>` in \\includegraphics) are copied into the LaTeX
build folder and the export zip — only files that exist, never a placeholder."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

LATEX_FIGURE_OK = {".png", ".jpg", ".jpeg", ".pdf", ".eps"}      # formats \includegraphics accepts with pdfLaTeX


def figure_files(tex_sources: list) -> list:
    """(source path, 'figures/<name>') for every run figure referenced by \\includegraphics in the paper."""
    from backend.execution.sandbox import runs_dir
    out = []
    for t in tex_sources:
        for n in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{figures/([^}]+)\}", t or ""):
            m = re.fullmatch(r"run-([\w-]+?)--(\w[\w.-]*)", n)
            src = runs_dir() / m.group(1) / "figures" / m.group(2) if m else None
            if src and Path(src.name).suffix.lower() in LATEX_FIGURE_OK and src.is_file():
                out.append((src, f"figures/{n}"))
    return list(dict.fromkeys(out))


def copy_figures(tex_sources: list, dest: Path) -> list:
    copied = []
    for src, rel in figure_files(tex_sources):
        t = dest / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        if not t.exists() or t.stat().st_size != src.stat().st_size:
            shutil.copy2(src, t)
        copied.append(rel)
    return copied
