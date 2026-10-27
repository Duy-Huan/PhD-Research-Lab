"""Adapter of SakanaAI/AI-Scientist-v2 (installed as a plugin from GitHub) for the paper-writing backend.

The repository's own prompts are read from its source (ast, never imported or executed — it needs torch, its own API
clients and a GPU tree search that does not fit this workstation) and reused with the app's models:

    /ais-idea      ideation (perform_ideation_temp_free.py): a grant-style idea JSON grounded in the project library
    /ais-review    NeurIPS review form (perform_llm_review.py): THOUGHT + REVIEW JSON scores, Accept/Reject
    /ais-write     write-up guidance (perform_writeup.py) for sections saved with write_section
    writeup()      the full manuscript: writeup_prompt + the ICML / ICBINB LaTeX template of the repository, filled from
                   the outline, MEASURED results, pinned results, figures and the project bibliography

AI Scientist Source Code License §3.2(i): every generated manuscript must disclose prominently that it was produced
with The AI Scientist — writeup() always inserts that disclosure.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import time
from pathlib import Path

NAME = "ai_scientist"
REPO = "SakanaAI/AI-Scientist-v2"
PLUGIN_ID = "sakanaai-ai-scientist-v2"
URL = "https://github.com/SakanaAI/AI-Scientist-v2"
TEMPLATES = {"icml": "blank_icml_latex", "icbinb": "blank_icbinb_latex"}
DISCLOSURE = ("This manuscript was machine-generated with the assistance of The AI Scientist "
              "(Sakana AI, AI-Scientist-v2) inside PhD Research Lab and reviewed by the authors.")
_cache: dict = {}

# Used only when the repository no longer defines a prompt under the expected name.
FALLBACK = {
    "reviewer_system_prompt_neg": "You are an AI researcher who is reviewing a paper that was submitted to a prestigious ML venue. "
                                  "Be critical and cautious in your decision. If a paper is bad or you are unsure, give it bad scores and reject it.",
    "neurips_form": "Review the paper with the NeurIPS form: Summary, Strengths, Weaknesses, Originality/Quality/Clarity/Significance "
                    "(1-4), Questions, Limitations, Ethical Concerns, Soundness/Presentation/Contribution (1-4), Overall (1-10), "
                    "Confidence (1-5), Decision (Accept/Reject). Respond with THOUGHT: … then REVIEW JSON: ```json {…}```.",
    "writeup_system_message_template": "You are an ambitious AI researcher who is looking to publish a paper that will contribute "
                                       "significantly to the field. Ensure that the paper is scientifically accurate, objective, and "
                                       "truthful. The main paper is limited to {page_limit} pages. Do not hallucinate new citations or "
                                       "any results not in the logs. Return the LaTeX in a ```latex fenced block.",
    "writeup_prompt": "Your goal is to write up the following idea:\n```markdown\n{idea_text}\n```\nExperiment summaries (JSON):\n"
                      "```json\n{summaries}\n```\nPlot script:\n```python\n{aggregator_code}\n```\nAvailable plots:\n```\n{plot_list}\n```\n"
                      "Figure descriptions:\n```\n{plot_descriptions}\n```\nCurrent LaTeX:\n```latex\n{latex_writeup}\n```\n"
                      "Return the entire file in full in a ```latex block.",
    "idea_system": "You are an experienced AI researcher who aims to propose high-impact research ideas resembling exciting grant "
                   "proposals. Each proposal should stem from a simple and elegant question, observation, or hypothesis. Clearly clarify "
                   "how the proposal distinguishes from the existing literature. Ensure that the proposal does not require resources "
                   "beyond what an academic lab could afford.",
}


# ------------------------------------------------------------------ prompts from the repository source
def _eval(node, env: dict):
    """String constants, '+' concatenations and names already evaluated; anything else is not a static prompt."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _eval(node.left, env), _eval(node.right, env)
        return a + b if a is not None and b is not None else None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.JoinedStr):  # f-string: keep the literal parts (tool lists are filled at run time upstream)
        parts = [v.value for v in node.values if isinstance(v, ast.Constant)]
        return "".join(parts) if parts else None
    return None


def module_strings(path: Path) -> dict:
    """Top-level string assignments of a Python file (read with ast, never imported)."""
    try:
        tree = ast.parse(path.read_text("utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {}
    env = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            v = _eval(n.value, env)
            if isinstance(v, str):
                env[n.targets[0].id] = v
    return env


def prompts(repo: Path) -> dict:
    key = (str(repo), tuple((f.name, f.stat().st_mtime_ns) for f in sorted((repo / "ai_scientist").glob("perform_*.py")))
           if (repo / "ai_scientist").is_dir() else ())
    if _cache.get("key") == key:
        return _cache["prompts"]
    p = dict(FALLBACK)
    src = repo / "ai_scientist"
    review = module_strings(src / "perform_llm_review.py")
    writeup = module_strings(src / "perform_writeup.py")
    idea = module_strings(src / "perform_ideation_temp_free.py")
    for k in ("reviewer_system_prompt_neg", "neurips_form", "meta_reviewer_system_prompt"):
        if review.get(k):
            p[k] = review[k]
    for k in ("writeup_system_message_template", "writeup_prompt"):
        if writeup.get(k):
            p[k] = writeup[k]
    if idea.get("system_prompt"):
        # keep the scientific brief; the tool protocol (ACTION / ARGUMENTS) belongs to the upstream agent loop
        p["idea_system"] = idea["system_prompt"].split("You have access to the following tools")[0].strip()
    p["source"] = {"review": bool(review), "writeup": bool(writeup), "ideation": bool(idea)}
    _cache.update(key=key, prompts=p)
    return p


def _fmt(template: str, **values) -> str:
    """str.format that leaves unknown {placeholders} (and LaTeX braces) alone."""
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0),
                  template.replace("{{", "\x00").replace("}}", "\x01")).replace("\x00", "{").replace("\x01", "}")


# ------------------------------------------------------------------ skills
def skills(repo: Path, pid: str) -> list:
    p = prompts(repo)
    base = {"usage": "", "pipeline": "", "provider": "app", "aliases": [], "origin": "plugin", "plugin": pid,
            "mode": "chat", "risk": 0, "file": str(repo / "ai_scientist")}
    idea = (p["idea_system"] + "\n\nWork from the project context (outline, library, research state). Propose exactly one idea "
            "as Markdown with these headings, then the same idea as an IDEA JSON block (Name, Title, Short Hypothesis, Related "
            "Work, Abstract, Experiments, Risk Factors and Limitations). Cite only library sources. Finally propose it:\n"
            "```phdlab-action\n{\"action\": \"create_hypothesis\", \"args\": {\"text\": \"<short hypothesis>\"}}\n```")
    review = (p["reviewer_system_prompt_neg"] + "\n\n" + p["neurips_form"] + "\n\nReview the manuscript or the sections the "
              "researcher points to (attached file or saved paper sections in the context). Answer the THOUGHT in the "
              "researcher's language; keep the REVIEW JSON keys in English.")
    write = (_fmt(p["writeup_system_message_template"], page_limit=8) + "\n\nIn this chat, write the section the researcher "
             "asks for as LaTeX body text (no \\section command), using only MEASURED / pinned results and \\cite{key} keys of "
             "the project library; write [CẦN KIỂM CHỨNG] where evidence is missing. Then propose saving it:\n"
             "```phdlab-action\n{\"action\": \"write_section\", \"args\": {\"section\": \"<abstract|introduction|related_work|"
             "methodology|experiments|discussion|conclusion>\", \"text\": \"…\"}}\n```\nThe whole manuscript in the AI Scientist "
             "template is produced from the Paper panel (Viết toàn bài · AI-Scientist-v2).")
    return [
        {**base, "name": "ais-idea", "title": "AI-Scientist · ý tưởng", "category": "research", "agent": "research",
         "description": "Sinh ý tưởng nghiên cứu kiểu grant proposal theo prompt ideation của AI-Scientist-v2", "instructions": idea},
        {**base, "name": "ais-review", "title": "AI-Scientist · phản biện NeurIPS", "category": "writing", "agent": "reviewer",
         "description": "Phản biện theo form NeurIPS của AI-Scientist-v2 (điểm 1–10, Accept/Reject, JSON)", "instructions": review},
        {**base, "name": "ais-write", "title": "AI-Scientist · viết phần bài", "category": "writing", "agent": "research",
         "description": "Viết một phần bài báo theo hướng dẫn write-up của AI-Scientist-v2", "risk": 1, "instructions": write},
    ]


# ------------------------------------------------------------------ full manuscript
def repo_dir() -> Path:
    from backend.plugins import _dir
    return _dir(PLUGIN_ID) / "repo"


def status() -> dict:
    from backend.plugins import PluginError, describe
    try:
        man = describe(PLUGIN_ID)
    except PluginError:
        return {"installed": False, "url": URL}
    repo = Path(man["path"]) / "repo"
    return {"installed": True, "enabled": man["enabled"], "commit": man.get("commit", "")[:10], "url": URL,
            "templates": [k for k, d in TEMPLATES.items() if (repo / "ai_scientist" / d / "template.tex").is_file()],
            "prompts": prompts(repo).get("source", {})}


def _figures() -> list:
    from backend.core.config import data_dir
    figs = []
    for d in ("results", "code", "runs"):
        base = data_dir() / d
        if base.is_dir():
            figs += [f for f in base.rglob("*") if f.suffix.lower() in (".png", ".pdf", ".jpg", ".jpeg") and f.stat().st_size < 20e6
                     and "_trash" not in f.parts][:40]
    return figs[:40]


def materials() -> dict:
    """What the write-up may use: idea (outline), measured results, pinned results, figures, bibliography keys."""
    from backend.agent import outline, pins
    from backend.paper.writer import load_project
    o = outline.get()
    idea = "\n\n".join(f"## {k.title()}\n{v if isinstance(v, str) else ', '.join(v)}" for k, v in (
        ("keywords", o.get("keywords")), ("topic", o.get("topic")), ("direction", o.get("direction")),
        ("method", o.get("method")), ("proposal", o.get("proposal"))) if v)
    proj = load_project()
    summaries = {"results_notes": proj.get("results_notes", ""), "method_notes": proj.get("method_notes", ""),
                 "contribution": proj.get("contribution", ""), "tables": proj.get("tables", []),
                 "pinned_results": [{"title": p.get("title"), "status": p.get("status"), "body": str(p.get("body", ""))[:1500]}
                                    for p in pins.list_pins()][:20],
                 "saved_sections": {k: v[:3000] for k, v in (proj.get("sections") or {}).items() if v}}
    return {"idea": idea or proj.get("title", ""), "summaries": summaries, "figures": _figures(), "title": proj.get("title", "")}


def _out_dir() -> Path:
    from backend.core.config import workspace
    d = workspace() / "paper_ais"
    d.mkdir(parents=True, exist_ok=True)
    return d


def prepare(template: str = "icml") -> tuple[str, str, Path]:
    """(system, user, build dir): copies the repository template, the figures and references.bib into paper_ais/."""
    if template not in TEMPLATES:
        raise ValueError("template must be icml or icbinb")
    repo = repo_dir()
    src = repo / "ai_scientist" / TEMPLATES[template]
    if not (src / "template.tex").is_file():
        raise ValueError(f"The installed AI-Scientist-v2 has no {TEMPLATES[template]}/template.tex — update the plugin")
    out = _out_dir()
    for f in src.iterdir():
        if f.is_file() and f.suffix in (".sty", ".bst", ".tex", ".bib", ".cls"):
            shutil.copy2(f, out / f.name)
    figs = out / "figures"
    figs.mkdir(exist_ok=True)
    m = materials()
    names = []
    for f in m["figures"]:
        name = re.sub(r"[^\w.-]", "_", f.name)
        shutil.copy2(f, figs / name)
        names.append(name)
    from backend.knowledge.library import build_bibtex, included
    bib = build_bibtex(included())
    (out / "references.bib").write_text(bib, "utf-8")
    keys = re.findall(r"@\w+\{([^,]+),", bib)
    p = prompts(repo)
    system = _fmt(p["writeup_system_message_template"], page_limit=8 if template == "icml" else 4)
    latex = (src / "template.tex").read_text("utf-8", errors="replace").replace("\\graphicspath{", "\\graphicspath{{figures/}")
    user = _fmt(p["writeup_prompt"], idea_text=m["idea"] or "(no outline yet)",
                summaries=json.dumps(m["summaries"], ensure_ascii=False, indent=1)[:40000], aggregator_code="(not available)",
                plot_list="\n".join(names) or "(no figures)", plot_descriptions="(not available)", latex_writeup=latex)
    user += ("\n\nThe bibliography file is references.bib with exactly these keys (cite nothing else): "
             + (", ".join(keys) or "(empty — do not cite)") + "\nFigures are in figures/. Report only values present in the "
             "summaries above. Add a short 'Disclosure' paragraph stating: " + DISCLOSURE)
    return system, user, out


def finish(text: str, out: Path) -> dict:
    """Extract the LaTeX answer, enforce the disclosure and drop citations missing from references.bib."""
    m = re.findall(r"```latex\s*\n(.*?)```", text, re.S)
    tex = (m[-1] if m else text).strip()
    if "\\begin{document}" not in tex:
        raise ValueError("The model did not return a complete LaTeX file — try again or use a stronger model")
    if "The AI Scientist" not in tex:
        tex = re.sub(r"(\\end\{abstract\})", lambda mm: mm.group(1) + "\n\\paragraph{Disclosure.} " + DISCLOSURE + "\n", tex, count=1) \
            if "\\end{abstract}" in tex else tex.replace("\\end{document}", "\\section*{Disclosure}\n" + DISCLOSURE + "\n\\end{document}")
    keys = set(re.findall(r"@\w+\{([^,]+),", (out / "references.bib").read_text("utf-8")))
    dropped = []

    def cite(mm):
        ks = [k.strip() for k in mm.group(2).split(",")]
        ok = [k for k in ks if k in keys]
        dropped.extend(k for k in ks if k not in keys)
        return f"\\{mm.group(1)}{{{','.join(ok)}}}" if ok else ""
    tex = re.sub(r"\\(cite[tp]?)\{([^}]*)\}", cite, tex)
    (out / "template.tex").write_text(tex, "utf-8")
    meta = {"ts": time.time(), "chars": len(tex), "dropped_citations": sorted(set(dropped))}
    (out / "writeup.json").write_text(json.dumps(meta), "utf-8")
    return {**meta, "path": str(out / "template.tex")}


def compile_pdf() -> dict:
    """Compile paper_ais/template.tex with the installed TeX engine (bibtex pass included when available)."""
    from backend.paper import latex as LX
    out = _out_dir()
    if not (out / "template.tex").is_file():
        raise ValueError("Write the manuscript first")
    eng = next((e for e in ("pdflatex", "xelatex", "lualatex") if LX.which(e)), None)
    if not eng:
        return {"ok": False, "log": "", "help": LX.install_help()}
    log = ""
    for cmd in ([eng, "-interaction=nonstopmode", "template.tex"], ["bibtex", "template"],
                [eng, "-interaction=nonstopmode", "template.tex"], [eng, "-interaction=nonstopmode", "template.tex"]):
        if cmd[0] == "bibtex" and not LX.which("bibtex"):
            continue
        _, part = LX._run([LX.which(cmd[0]) or cmd[0]] + cmd[1:], out, 240)
        log += part[-4000:]
    pdf = out / "template.pdf"
    return {"ok": pdf.is_file(), "log": log[-12000:], "pdf": str(pdf) if pdf.is_file() else ""}


def bundle() -> bytes:
    import io
    import zipfile
    out = _out_dir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in out.rglob("*"):
            if f.is_file() and f.suffix not in (".aux", ".log", ".out", ".blg", ".tmp"):
                z.write(f, f.relative_to(out).as_posix())
    return buf.getvalue()
