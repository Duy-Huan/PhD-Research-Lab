"""LaTeX → PDF compilation for the Paper Writer preview (v2.7).

Uses a TeX distribution installed on this computer (searched on PATH and in the usual install folders):
    tectonic            single binary, downloads missing packages automatically (easiest)
    latexmk / pdflatex  TeX Live, MiKTeX or MacTeX (pdflatex → bibtex → pdflatex ×2)
Optional, opt-in only: online compilation through the public LaTeX-on-HTTP service (sends main.tex + references.bib).

Build files live in <workspace>/build/ (main.tex, references.bib, main.pdf, main.log).
"Quick layout" swaps IEEEtran / acmart for the standard article class so a preview always compiles,
even when the conference class is not installed.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from .config import load_config, workspace
from .paper import SECTION_TITLES, assemble

TIMEOUT = 240
ONLINE_URL = os.environ.get("PHDLAB_LATEX_ONLINE", "https://latex.ytotech.com/builds/sync")
_lock = threading.Lock()
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ------------------------------------------------------------------ engine discovery
def _extra_dirs() -> list:
    dirs = []
    if sys.platform.startswith("win"):
        for pat in (r"C:\Program Files\MiKTeX*\miktex\bin\x64", os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64"),
                    r"C:\texlive\*\bin\windows", r"C:\texlive\*\bin\win64", r"C:\texlive\*\bin\win32",
                    os.path.expandvars(r"%USERPROFILE%\.cargo\bin"), os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links")):
            dirs += sorted(glob.glob(pat), reverse=True)
    else:
        dirs += ["/Library/TeX/texbin", "/usr/local/texlive/bin", os.path.expanduser("~/.cargo/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
        dirs += sorted(glob.glob("/usr/local/texlive/*/bin/*"), reverse=True)
        dirs += sorted(glob.glob(os.path.expanduser("~/texlive/*/bin/*")), reverse=True)
    return [d for d in dirs if os.path.isdir(d)]


def which(name: str) -> str | None:
    p = shutil.which(name)
    if p:
        return p
    for d in _extra_dirs():
        p = shutil.which(name, path=d)
        if p:
            return p
    return None


def engines() -> dict:
    found = {n: which(n) for n in ("tectonic", "latexmk", "pdflatex", "xelatex", "bibtex", "kpsewhich")}
    avail = []
    if found["pdflatex"]:
        avail.append("pdflatex")
    if found["latexmk"] and found["pdflatex"]:
        avail.append("latexmk")
    if found["xelatex"]:
        avail.append("xelatex")
    if found["tectonic"]:
        avail.append("tectonic")
    online = bool(load_config().get("latex_online"))
    return {"available": avail, "paths": {k: v for k, v in found.items() if v}, "online": online,
            "default": avail[0] if avail else ("online" if online else ""), "platform": sys.platform}


def class_available(cls: str) -> bool | None:
    """True/False when kpsewhich can tell, None when unknown (e.g. tectonic only / MiKTeX on-the-fly install)."""
    k = which("kpsewhich")
    if not k:
        return None
    try:
        r = subprocess.run([k, f"{cls}.cls"], capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
        return bool(r.stdout.strip())
    except Exception:
        return None


# ------------------------------------------------------------------ quick layout
SHIM = r"""\documentclass[10pt,twocolumn]{article}
\usepackage[margin=0.7in,columnsep=0.25in]{geometry}
% --- quick-preview shims for IEEEtran / acmart commands (PhD Research Lab) ---
\providecommand{\IEEEoverridecommandlockouts}{}
\newenvironment{IEEEkeywords}{\par\noindent\textit{Index Terms}---}{\par}
\providecommand{\IEEEauthorblockN}[1]{#1\\}
\providecommand{\IEEEauthorblockA}[1]{\small #1}
\providecommand{\IEEEPARstart}[2]{#1#2}
\providecommand{\IEEEbibitemsep}{}
\providecommand{\settopmatter}[1]{}
\providecommand{\setcopyright}[1]{}
\providecommand{\keywords}[1]{\gdef\phdlabkeywords{#1}}
\providecommand{\affiliation}[1]{}
\providecommand{\institution}[1]{#1}
\providecommand{\country}[1]{#1}
\providecommand{\email}[1]{\texttt{#1}}
\providecommand{\acmConference}[4][]{}
\providecommand{\acmYear}[1]{}
\providecommand{\acmDOI}[1]{}
\providecommand{\acmISBN}[1]{}
"""


def quick_layout(main: str) -> str:
    out = re.sub(r"\\documentclass(\[[^\]]*\])?\{[^}]*\}", lambda m: SHIM, main, count=1)
    out = re.sub(r"\\bibliographystyle\{[^}]*\}", r"\\bibliographystyle{plain}", out)
    out = out.replace("\\usepackage{amsmath,amssymb,amsfonts}", "\\usepackage{amsmath,amssymb,amsfonts}")
    if "\\usepackage{xcolor}" not in out:
        out = out.replace("\\begin{document}", "\\usepackage{xcolor}\n\\usepackage{booktabs}\n\\usepackage{graphicx}\n\\begin{document}", 1)
    return out


# ------------------------------------------------------------------ log parsing
def _section_lines(main: str) -> list:
    """[(start_line, section_id)] from the '% ===== id =====' markers written by assemble()."""
    out = []
    for i, line in enumerate(main.splitlines(), 1):
        m = re.match(r"% ===== (\w+) =====", line)
        if m:
            out.append((i, m.group(1)))
        elif "\\begin{abstract}" in line:
            out.append((i, "abstract"))
        elif line.startswith("\\bibliographystyle") or line.startswith("\\end{abstract}"):
            out.append((i, ""))
    return out


def _section_of(line: int | None, marks: list) -> str:
    if not line:
        return ""
    cur = ""
    for start, sid in marks:
        if start <= line:
            cur = sid
    return cur


def parse_log(log: str, main: str) -> dict:
    marks = _section_lines(main)
    errors = []
    lines = log.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("! "):
            msg = ln[2:].strip()
            lno, ctx = None, ""
            for nxt in lines[i + 1:i + 12]:
                m = re.match(r"l\.(\d+)\s?(.*)", nxt)
                if m:
                    lno, ctx = int(m.group(1)), m.group(2).strip()
                    break
            sid = _section_of(lno, marks)
            errors.append({"message": msg[:300], "line": lno, "context": ctx[-160:], "section": sid,
                           "section_title": SECTION_TITLES.get(sid, "")})
    # tectonic style: "error: main.tex:12: Undefined control sequence"
    for m in re.finditer(r"^error: [^:\n]*\.tex:(\d+): (.+)$", log, re.M):
        lno = int(m.group(1))
        sid = _section_of(lno, marks)
        errors.append({"message": m.group(2)[:300], "line": lno, "context": "", "section": sid, "section_title": SECTION_TITLES.get(sid, "")})
    uniq, seen = [], set()
    for e in errors:
        k = (e["message"], e["line"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    pages = re.search(r"Output written on \S+ \((\d+) pages?", log)
    missing = sorted(set(re.findall(r"File `([^']+\.(?:cls|sty))' not found", log)))
    return {"errors": uniq[:30],
            "undefined_citations": sorted(set(re.findall(r"Citation `([^']+)'[^\n]*undefined", log)))[:30],
            "undefined_refs": sorted(set(re.findall(r"Reference `([^']+)'[^\n]*undefined", log)))[:30],
            "overfull": len(re.findall(r"^Overfull \\hbox", log, re.M)),
            "pages": int(pages.group(1)) if pages else None,
            "missing_files": missing}


# ------------------------------------------------------------------ compilation
def _run(cmd: list, cwd: Path, timeout: int) -> tuple[int, str]:
    env = dict(os.environ, max_print_line="1000", error_line="254", half_error_line="238")
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, errors="replace", timeout=timeout,
                       creationflags=NO_WINDOW, env=env, stdin=subprocess.DEVNULL)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _compile_local(engine: str, build: Path) -> str:
    """Run the engine; returns the combined console/log text."""
    deadline = time.time() + TIMEOUT
    left = lambda: max(10, int(deadline - time.time()))
    out = []
    if engine == "tectonic":
        _, o = _run([which("tectonic"), "--keep-logs", "--keep-intermediates", "main.tex"], build, left())
        out.append(o)
    elif engine == "latexmk":
        _, o = _run([which("latexmk"), "-pdf", "-f", "-interaction=nonstopmode", "-file-line-error-", "main.tex"], build, left())
        out.append(o)
    else:
        tex = which(engine)
        cmd = [tex, "-interaction=nonstopmode", "main.tex"]
        _, o = _run(cmd, build, left())
        out.append(o)
        if which("bibtex") and (build / "main.aux").exists() and "\\bibdata" in (build / "main.aux").read_text("utf-8", "replace"):
            _, o = _run([which("bibtex"), "main"], build, left())
            out.append(o)
        for _ in range(2):
            _, o = _run(cmd, build, left())
            out.append(o)
    log = build / "main.log"
    return log.read_text("utf-8", "replace") if log.exists() else "\n".join(out)


def _compile_online(main: str, bib: str, build: Path) -> str:
    body = {"compiler": "pdflatex", "resources": [{"main": True, "content": main}, {"path": "references.bib", "content": bib}]}
    try:
        r = httpx.post(ONLINE_URL, json=body, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise RuntimeError(f"Online LaTeX service unreachable: {e}")
    if r.status_code < 300 and r.content[:4] == b"%PDF":
        (build / "main.pdf").write_bytes(r.content)
        return "(compiled online by LaTeX-on-HTTP)"
    try:
        d = r.json()
        return str(d.get("logs") or d.get("error") or d)
    except Exception:
        return f"Online service returned HTTP {r.status_code}"


def build_dir() -> Path:
    d = workspace() / "build"
    d.mkdir(parents=True, exist_ok=True)
    return d


def compile_pdf(engine: str = "", layout: str = "template") -> dict:
    """Assemble main.tex and compile it. layout: template | simple. Returns a report for the UI."""
    with _lock:
        info = engines()
        engine = engine or info["default"]
        if engine == "online" and not info["online"]:
            raise RuntimeError("Online compilation is off — enable it in the PDF preview options first.")
        if not engine:
            raise NoEngine()
        if engine != "online" and engine not in info["available"]:
            raise RuntimeError(f"{engine} is not installed on this computer.")
        return _compile(engine, layout, [], time.time(), retry=True)


def _compile(engine: str, layout: str, notes: list, t0: float, retry: bool) -> dict:
    main, bib, report = assemble()
    m = re.search(r"\\documentclass(?:\[[^\]]*\])?\{([^}]*)\}", main)
    cls = m.group(1) if m else ""
    fix = "sudo apt install texlive-publishers" if sys.platform.startswith("linux") else \
          "MiKTeX Console → Packages" if sys.platform.startswith("win") else "tlmgr install " + cls.lower()
    if layout != "simple" and engine not in ("tectonic", "online") and cls in ("IEEEtran", "acmart") and class_available(cls) is False:
        layout = "simple"
        notes.append(f"{cls}.cls is not installed — compiled with the quick layout instead (to get the real template: {fix}).")
    tex = quick_layout(main) if layout == "simple" else main
    build = build_dir()
    for f in build.glob("main.*"):
        try:
            f.unlink()
        except OSError:
            pass
    (build / "main.tex").write_text(tex, "utf-8")
    (build / "references.bib").write_text(bib, "utf-8")
    try:
        from .results import copy_figures
        copy_figures([tex], build)          # v3.1: figures chosen in the section briefs
    except Exception:
        pass
    try:
        log = _compile_online(tex, bib, build) if engine == "online" else _compile_local(engine, build)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"LaTeX did not finish within {TIMEOUT} s (a package download or an endless loop?).")
    (build / "build.log").write_text(log, "utf-8")
    parsed = parse_log(log, tex)
    pdf = build / "main.pdf"
    ok = pdf.exists() and pdf.stat().st_size > 0
    if not ok and retry and layout != "simple" and any(f.endswith(".cls") for f in parsed["missing_files"]):
        notes.append(f"Missing {', '.join(parsed['missing_files'])} — compiled with the quick layout instead (to get the real template: {fix}).")
        return _compile(engine, "simple", notes, t0, retry=False)
    return {"ok": ok, "engine": engine, "layout": layout, "seconds": round(time.time() - t0, 1),
            "pdf_mtime": int(pdf.stat().st_mtime) if ok else None, "report": report, "notes": notes, **parsed}


class NoEngine(RuntimeError):
    def __init__(self):
        super().__init__("No LaTeX engine found on this computer.")


INSTALL_HELP = {
    "win32": ["Easiest: install Tectonic — open PowerShell and run:  winget install TectonicTypesetting.Tectonic",
              "Full distribution: MiKTeX (https://miktex.org/download) — tick 'install missing packages on-the-fly'.",
              "Or TeX Live for Windows (https://tug.org/texlive/). Restart the app afterwards."],
    "darwin": ["Easiest: brew install tectonic", "Full distribution: MacTeX (https://tug.org/mactex/)."],
    "linux": ["Ubuntu/Debian: sudo apt install texlive-latex-extra texlive-publishers texlive-bibtex-extra latexmk",
              "(texlive-publishers contains IEEEtran and acmart) — or a single binary: Tectonic (https://tectonic-typesetting.github.io)."],
}


def install_help() -> list:
    key = "win32" if sys.platform.startswith("win") else "darwin" if sys.platform == "darwin" else "linux"
    return INSTALL_HELP[key]
