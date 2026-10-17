"""Paper project state, LaTeX assembly, citation validation and latex.zip export."""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import date

from .config import refs_dir, workspace
from .library import build_bibtex, included


SECTIONS = [
    ("abstract", "Abstract"),
    ("introduction", "Introduction"),
    ("related_work", "Related Work"),
    ("methodology", "Methodology"),
    ("experiments", "Experiments and Results"),
    ("discussion", "Discussion"),
    ("conclusion", "Conclusion"),
]
SECTION_TITLES = dict(SECTIONS)

DEFAULT_PROJECT = {
    "title": "", "authors": "", "style": "IEEE", "keywords": "",
    "contribution": "", "method_notes": "", "results_notes": "",
    "tables": [], "sections": {}, "review": "",
    # v2.5 section workshop
    "venue": "",              # target venue (calibrates the section reviewer)
    "section_reviews": {},    # {section_id: markdown review of that section}
    "section_scores": {},     # {section_id: 1-10 from the section reviewer}
    "section_notes": {},      # {section_id: author's instructions for the AI}
    "section_state": {},      # {section_id: drafted | reviewed | revised | accepted | edited}
}


# ---------------------------------------------------------------- state
def load_project() -> dict:
    p = json.loads(json.dumps(DEFAULT_PROJECT))  # deep copy: nested dicts must not be shared
    pp = workspace() / "project.json"
    if pp.exists():
        try:
            p.update(json.loads(pp.read_text("utf-8")))
        except Exception:
            pass
    return p


def save_project(p: dict) -> dict:
    (workspace() / "project.json").write_text(json.dumps(p, indent=2, ensure_ascii=False), "utf-8")
    return p


def write_ws(name: str, text: str) -> None:
    (workspace() / name).write_text(text, "utf-8")


def read_ws(name: str) -> str:
    f = workspace() / name
    return f.read_text("utf-8") if f.exists() else ""


# ---------------------------------------------------------------- cleaning
CITE_RE = re.compile(r"\\(cite[a-zA-Z]*)\*?(\[[^\]]*\])?\{([^}]*)\}")


def clean_section(section_id: str, tex: str) -> str:
    tex = tex.strip()
    tex = re.sub(r"\\documentclass.*?\n|\\usepackage.*?\n|\\begin\{document\}|\\end\{document\}|\\maketitle", "", tex)
    tex = re.sub(r"\\bibliography(style)?\{[^}]*\}", "", tex)
    if section_id == "abstract":
        tex = re.sub(r"\\begin\{abstract\}|\\end\{abstract\}", "", tex)
        tex = re.sub(r"\\section\*?\{[^}]*\}", "", tex)
        return tex.strip()
    if not re.match(r"\s*\\section\*?\{", tex):
        tex = f"\\section{{{SECTION_TITLES.get(section_id, section_id.title())}}}\n" + tex
    return tex.strip()


def fix_citations(tex: str, valid: set) -> tuple[str, list]:
    """Drop cite keys not present in references.bib; mark claims left without support."""
    unknown = []

    def repl(m):
        keys = [k.strip() for k in m.group(3).split(",") if k.strip()]
        good = [k for k in keys if k in valid]
        unknown.extend(k for k in keys if k not in valid)
        if good:
            return f"\\cite{m.group(2) or ''}{{{','.join(good)}}}"
        return "\\textcolor{red}{[CITATION NEEDED]}"

    return CITE_RE.sub(repl, tex), sorted(set(unknown))


def used_keys(tex: str) -> set:
    out = set()
    for m in CITE_RE.finditer(tex):
        out.update(k.strip() for k in m.group(3).split(",") if k.strip())
    return out


# ---------------------------------------------------------------- templates
IEEE_TEMPLATE = r"""\documentclass[conference]{IEEEtran}
\IEEEoverridecommandlockouts
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{url}

\begin{document}

\title{<<TITLE>>}

\author{<<AUTHORS>>}

\maketitle

\begin{abstract}
<<ABSTRACT>>
\end{abstract}

\begin{IEEEkeywords}
<<KEYWORDS>>
\end{IEEEkeywords}

<<BODY>>

\bibliographystyle{IEEEtran}
\bibliography{references}

\end{document}
"""

ACM_TEMPLATE = r"""\documentclass[sigconf]{acmart}
\usepackage{multirow}
\settopmatter{printacmref=false}
\setcopyright{none}

\begin{document}

\title{<<TITLE>>}

<<AUTHORS>>

\begin{abstract}
<<ABSTRACT>>
\end{abstract}

\keywords{<<KEYWORDS>>}

\maketitle

<<BODY>>

\bibliographystyle{ACM-Reference-Format}
\bibliography{references}

\end{document}
"""


def _authors_latex(raw: str, style: str) -> str:
    rows = [r for r in (raw or "").splitlines() if r.strip()] or ["Author Name | Affiliation | email@example.com"]
    parsed = []
    for r in rows:
        parts = [x.strip() for x in r.split("|")] + ["", "", "", ""]
        parsed.append(parts[:4])  # name, affiliation, email, country
    if style == "ACM":
        out = []
        for name, aff, email, country in parsed:
            s = f"\\author{{{name}}}\n\\affiliation{{\\institution{{{aff or 'Institution'}}}\\country{{{country or 'Country'}}}}}"
            if email:
                s += f"\n\\email{{{email}}}"
            out.append(s)
        return "\n".join(out)
    blocks = []
    for name, aff, email, country in parsed:
        a = "\\\\ ".join(x for x in (f"\\textit{{{aff}}}" if aff else "", country, email) if x)
        blocks.append(f"\\IEEEauthorblockN{{{name}}}\n\\IEEEauthorblockA{{{a}}}")
    return "\n\\and\n".join(blocks)


def assemble(p: dict | None = None) -> tuple[str, str, dict]:
    """Build main.tex + references.bib from the project; returns (tex, bib, report)."""
    p = p or load_project()
    entries = included()
    valid = {e["key"] for e in entries}
    secs = p.get("sections") or {}
    unknown_all = []
    body_parts = []
    abstract = ""
    for sid, _ in SECTIONS:
        tex = secs.get(sid, "")
        if not tex:
            continue
        tex, unknown = fix_citations(tex, valid)
        unknown_all += unknown
        if sid == "abstract":
            abstract = tex
        else:
            body_parts.append(f"% ===== {sid} =====\n{tex}")
    style = p.get("style", "IEEE")
    tpl = ACM_TEMPLATE if style == "ACM" else IEEE_TEMPLATE
    main = (tpl.replace("<<TITLE>>", p.get("title") or "Untitled Manuscript")
               .replace("<<AUTHORS>>", _authors_latex(p.get("authors", ""), style))
               .replace("<<ABSTRACT>>", abstract or "\\textcolor{red}{[TBD: abstract]}")
               .replace("<<KEYWORDS>>", p.get("keywords") or "keyword1, keyword2")
               .replace("<<BODY>>", "\n\n".join(body_parts) or "\\section{Introduction}\n\\textcolor{red}{[TBD]}"))
    if "\\cite" not in main:
        main = main.replace("\\bibliography{references}", "\\nocite{*}\n\\bibliography{references}")
    bib = build_bibtex(entries)
    used = used_keys(main)
    report = {
        "unknown": sorted(set(unknown_all)),
        "used": sorted(used),
        "unused": sorted(valid - used),
        "n_references": len(valid),
        "missing_sections": [sid for sid, _ in SECTIONS if not secs.get(sid)],
        "placeholders": len(re.findall(r"\[TBD|\[CITATION NEEDED\]", main)),
    }
    write_ws("main.tex", main)
    write_ws("references.bib", bib)
    return main, bib, report


README_TEMPLATE = """# LaTeX package — <<TITLE>>

Generated by **PhD Interactive Autonomous Research Lab** on <<DATE>>.

## Contents
| File | Purpose |
|---|---|
| `main.tex` | Manuscript (<<STYLE>> template) using `\\bibliography{references}` |
| `references.bib` | Standalone BibTeX database (<<NREF>> entries) built from the local PDF pool |
| `references/` | Full-text PDFs of the cited/collected papers (for your records — not needed to compile; **do not redistribute** publisher PDFs) |

## Compile on Overleaf
1. Overleaf → **New Project → Upload Project** → select `latex.zip`.
2. Menu → Settings: Compiler = **pdfLaTeX**, Main document = `main.tex`.
3. Click **Recompile**. (Overleaf already ships `IEEEtran.cls` and `acmart.cls`.)
4. Optional: delete the `references/` folder on Overleaf to stay within storage limits.

## Compile locally (TeX Live / MiKTeX on Windows 11)
```bash
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```
or simply `latexmk -pdf main.tex`. MiKTeX installs missing packages on first run.

## Before submission — checklist
- [ ] Search `main.tex` for `[TBD` and `[CITATION NEEDED]` and resolve every placeholder.
- [ ] Verify every BibTeX entry (authors, venue, pages, DOI) against the publisher page.
- [ ] Re-check every number in tables against your raw logs.
- [ ] Switch the IEEE class option (`conference` → `journal`) or ACM format (`sigconf` → `acmsmall`) if your venue requires it.
"""


def build_zip() -> bytes:
    p = load_project()
    main, bib, report = assemble(p)
    readme = (README_TEMPLATE.replace("<<TITLE>>", p.get("title") or "Untitled Manuscript")
              .replace("<<DATE>>", date.today().isoformat())
              .replace("<<STYLE>>", p.get("style", "IEEE"))
              .replace("<<NREF>>", str(report["n_references"])))
    buf = io.BytesIO()
    rdir = refs_dir()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("main.tex", main)
        z.writestr("references.bib", bib)
        z.writestr("README.md", readme)
        z.writestr("references/", "")
        for e in included():
            f = rdir / e["file"]
            if f.exists():
                z.write(f, f"references/{e['file']}")
    return buf.getvalue()
