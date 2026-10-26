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
            studio = re.fullmatch(r'([A-Za-z0-9_-]+)_v([0-9]{4,})\.pdf', n)
            if studio:
                from backend.figures import store
                from backend.knowledge import research_store as S
                with S.db() as connection:
                    row = connection.execute('SELECT topic_id FROM figures WHERE id=?', (studio.group(1),)).fetchone()
                if row is None: raise ValueError('Referenced scientific figure is missing in this project')
                tid, fid, version = row[0], studio.group(1), int(studio.group(2))
                figure = store.get_figure(tid, fid, version)
                check = store.validate_figure_version(tid, fid, version)
                if check['overall_status'] == 'failed' or (figure['spec'].get('require_approval_before_paper_use') and not figure.get('approval')):
                    raise ValueError('Referenced scientific figure requires current integrity checks and exact-version approval')
                src = store.export_file_path(tid, fid, 'pdf', version)
            elif src:
                from backend.knowledge.research_store import safe_child
                src = safe_child(runs_dir(), m.group(1), 'figures', m.group(2))
            if src and Path(src.name).suffix.lower() in LATEX_FIGURE_OK and src.is_file():
                out.append((src, f"figures/{n}"))
    return list(dict.fromkeys(out))


def copy_figures(tex_sources: list, dest: Path) -> list:
    copied = []
    for src, rel in figure_files(tex_sources):
        t = dest / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        import hashlib
        if not t.exists() or hashlib.sha256(t.read_bytes()).digest() != hashlib.sha256(src.read_bytes()).digest():
            shutil.copy2(src, t)
        copied.append(rel)
    return copied
