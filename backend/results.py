"""v3.1 Research results provided by the researcher (work done outside the app) + the unified results pool.

Stored per project in <data>/results/:
    index.json              metadata of every result item
    <id>/<original file>    the uploaded file (image, PDF, LaTeX, Markdown, CSV, notebook, …)
    <id>/extracted.txt      text the agents read (empty for images: the researcher's description + AI analysis are used)
    _trash/<id>/            deleted items (recoverable)

The *pool* combines these uploads with sandbox runs (metrics + figures), the Paper Writer's LaTeX tables and its results
notes, so the Writer can pick exactly which results each section presents. Nothing here ever invents a number: agents get
only the extracted text, the researcher's notes and AI findings that are grounded in that text/image.
"""
from __future__ import annotations

import base64
import json
import re
import secrets
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import data_dir

MAX_FILE = 40 * 1024 * 1024
MAX_TEXT = 200_000
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
              ".svg": "image/svg+xml", ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff"}
VISION_OK = {".png", ".jpg", ".jpeg", ".gif", ".webp"}          # formats the AI providers accept as vision input
LATEX_FIGURE_OK = {".png", ".jpg", ".jpeg", ".pdf", ".eps"}      # formats \includegraphics accepts with pdfLaTeX
KINDS = ("figure", "table", "document", "data", "code", "note")
PRESENT_AS = ("auto", "table", "figure", "text", "comparison", "highlight")
_lock = threading.Lock()


class ResultError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rdir() -> Path:
    d = data_dir() / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load() -> list:
    try:
        return json.loads((rdir() / "index.json").read_text("utf-8")).get("items", [])
    except Exception:
        return []


def _save(items: list) -> None:
    p = rdir() / "index.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(p)


def get(rid: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{10}", rid or ""):
        raise ResultError("Invalid result id")
    for it in load():
        if it["id"] == rid:
            return it
    raise ResultError("Result not found")


def file_path(rid: str) -> Path:
    it = get(rid)
    if not it.get("file"):
        raise ResultError("This result has no file")
    p = rdir() / rid / it["file"]
    if not p.exists():
        raise ResultError("File missing on disk")
    return p


def text(rid: str) -> str:
    p = rdir() / rid / "extracted.txt"
    return p.read_text("utf-8", errors="replace") if p.exists() else ""


def _safe_name(name: str) -> str:
    stem, ext = Path(name).stem, Path(name).suffix.lower()
    stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.A).strip("._") or "file"
    return stem[:80] + ext


def _guess_kind(ext: str, txt: str) -> str:
    if ext in IMAGE_MIME or ext == ".eps":
        return "figure"
    if ext in (".csv", ".tsv", ".xlsx", ".xlsm"):
        return "table"
    if ext == ".tex":
        return "table" if re.search(r"\\begin\{(table|tabular)", txt) else "document"
    if ext == ".md":
        return "table" if re.search(r"^\s*\|.*\|\s*$\n^\s*\|[\s:|-]+\|\s*$", txt, re.M) else "document"
    if ext in (".py", ".ipynb", ".m", ".r", ".jl", ".cpp", ".c", ".cu", ".sh"):
        return "code"
    if ext in (".json", ".log", ".txt", ".yaml", ".yml", ".out", ".dat", ".xml"):
        return "data"
    return "document"


def _json_metrics(txt: str) -> dict:
    try:
        d = json.loads(txt)
    except Exception:
        return {}
    if isinstance(d, dict):
        return {str(k)[:40]: v for k, v in d.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return {}


def add_file(filename: str, data: bytes, title: str = "", notes: str = "", tags=None) -> dict:
    """Store one uploaded file as a result item and extract its text for the agents."""
    from .attachments import AttachmentError, _extract
    name = _safe_name(Path(filename or "file").name)
    if len(data) > MAX_FILE:
        raise ResultError(f"{name}: larger than {MAX_FILE // 1024 // 1024} MB")
    if not data:
        raise ResultError(f"{name}: empty file")
    ext = Path(name).suffix.lower()
    rid = secrets.token_hex(5)
    folder = rdir() / rid
    folder.mkdir(parents=True)
    path = folder / name
    path.write_bytes(data)
    txt, warning, extra = "", "", {}
    if ext in IMAGE_MIME or ext == ".eps":
        extra["mime"] = IMAGE_MIME.get(ext, "application/postscript")
    else:
        try:
            _kind, txt, meta = _extract(path, ext)
            extra.update({k: v for k, v in meta.items() if k in ("pages", "title")})
        except AttachmentError as e:
            if ext == ".pdf":
                warning = "No extractable text (scanned or a vector figure) — describe it below or press ✨ Analyze."
            else:
                shutil.rmtree(folder, ignore_errors=True)
                raise ResultError(f"{name}: {e}")
        except Exception as e:
            shutil.rmtree(folder, ignore_errors=True)
            raise ResultError(f"{name}: could not read file ({e})")
    txt = (txt or "")[:MAX_TEXT]
    (folder / "extracted.txt").write_text(txt, "utf-8")
    kind = _guess_kind(ext, txt)
    if ext == ".pdf" and not txt.strip():
        kind = "figure"
    item = {"id": rid, "title": (title or Path(filename or name).stem)[:160], "kind": kind, "file": name, "ext": ext,
            "size": len(data), "created": _now(), "notes": notes[:8000], "tags": [str(t)[:30] for t in (tags or [])][:12],
            "findings": "", "metrics": _json_metrics(txt) if ext == ".json" else {}, "chars": len(txt), "warning": warning, **extra}
    with _lock:
        items = load()
        items.insert(0, item)
        _save(items)
    return item


def add_note(title: str, body: str, tags=None, kind: str = "note") -> dict:
    """A result typed in by the researcher (e.g. numbers from a lab notebook)."""
    if not (body or "").strip():
        raise ResultError("Write the result first")
    rid = secrets.token_hex(5)
    folder = rdir() / rid
    folder.mkdir(parents=True)
    (folder / "extracted.txt").write_text(body[:MAX_TEXT], "utf-8")
    item = {"id": rid, "title": (title or body.strip().splitlines()[0])[:160], "kind": kind if kind in KINDS else "note",
            "file": "", "ext": "", "size": 0, "created": _now(), "notes": "", "tags": [str(t)[:30] for t in (tags or [])][:12],
            "findings": "", "metrics": {}, "chars": len(body), "warning": ""}
    with _lock:
        items = load()
        items.insert(0, item)
        _save(items)
    return item


def update(rid: str, fields: dict) -> dict:
    get(rid)
    with _lock:
        items = load()
        for it in items:
            if it["id"] != rid:
                continue
            for k in ("title", "notes", "findings"):
                if k in fields:
                    it[k] = str(fields[k] or "")[: 160 if k == "title" else 20000]
            if fields.get("kind") in KINDS:
                it["kind"] = fields["kind"]
            if isinstance(fields.get("tags"), list):
                it["tags"] = [str(t)[:30] for t in fields["tags"] if str(t).strip()][:12]
            if isinstance(fields.get("metrics"), dict):
                it["metrics"] = {str(k)[:40]: v for k, v in fields["metrics"].items() if isinstance(v, (int, float))}
            if "text" in fields and not it.get("file"):
                (rdir() / rid / "extracted.txt").write_text(str(fields["text"])[:MAX_TEXT], "utf-8")
                it["chars"] = len(str(fields["text"]))
            it["updated"] = _now()
            _save(items)
            return it
    raise ResultError("Result not found")


def delete(rid: str) -> dict:
    get(rid)
    with _lock:
        items = [it for it in load() if it["id"] != rid]
        src = rdir() / rid
        if src.exists():
            dst = rdir() / "_trash" / rid
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.move(str(src), str(dst))
        _save(items)
    return {"deleted": rid}


# ---------------------------------------------------------------- figures for LaTeX
def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:40] or "fig"


def figure_name(it: dict) -> str:
    """Stable file name of an uploaded figure inside the paper's figures/ folder."""
    return f"{_slug(it['title'])}-{it['id']}{it['ext']}"


def figure_label(it: dict) -> str:
    return f"fig:{_slug(it['title'])[:30]}-{it['id'][:4]}"


def figure_files(tex_sources: list) -> list:
    """(source path, 'figures/<name>') for every uploaded / run figure referenced by \\includegraphics in the paper."""
    used = set()
    for t in tex_sources:
        used.update(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{figures/([^}]+)\}", t or ""))
    if not used:
        return []
    out = []
    for it in load():
        if it.get("file") and it.get("ext") in LATEX_FIGURE_OK:
            n = figure_name(it)
            if n in used:
                out.append((rdir() / it["id"] / it["file"], f"figures/{n}"))
    try:
        from .sandbox import runs_dir
        for n in used:
            m = re.fullmatch(r"run-([\w-]+?)--(.+)", n)
            if m and (runs_dir() / m.group(1) / "figures" / m.group(2)).exists():
                out.append((runs_dir() / m.group(1) / "figures" / m.group(2), f"figures/{n}"))
    except Exception:
        pass
    return [(s, d) for s, d in out if s.exists()]


def copy_figures(tex_sources: list, dest: Path) -> list:
    copied = []
    for src, rel in figure_files(tex_sources):
        t = dest / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        if not t.exists() or t.stat().st_size != src.stat().st_size:
            shutil.copy2(src, t)
        copied.append(rel)
    return copied


# ---------------------------------------------------------------- unified pool (uploads + runs + tables + notes)
def pool() -> list:
    """Every result the researcher can choose to present in the paper. ref formats:
    up:<id> · run:<run_id> · runfig:<run_id>/<file> · table:<index> · notes"""
    out = []
    for it in load():
        out.append({"ref": f"up:{it['id']}", "source": "upload", "kind": it["kind"], "title": it["title"],
                    "sub": (it.get("notes") or it.get("findings") or "")[:140], "ext": it.get("ext", ""),
                    "thumb": f"/api/results/{it['id']}/file" if it.get("ext") in IMAGE_MIME else "",
                    "figure_ok": it.get("ext") in LATEX_FIGURE_OK, "tags": it.get("tags", []), "created": it.get("created", "")})
    try:
        from .sandbox import list_runs
        for r in list_runs(60):
            if r.get("status") != "done":
                continue
            ms = {k: v for k, v in (r.get("metrics") or {}).items() if isinstance(v, (int, float))}
            if ms:
                out.append({"ref": f"run:{r['id']}", "source": "run", "kind": "data", "title": f"Run {r['id']}",
                            "sub": (r.get("cmd") or "")[:60] + " · " + ", ".join(f"{k}={v:.4g}" for k, v in list(ms.items())[:5]),
                            "thumb": "", "figure_ok": False, "tags": [], "created": r.get("started", "")})
            for f in (r.get("figures") or [])[:12]:
                ext = Path(f).suffix.lower()
                out.append({"ref": f"runfig:{r['id']}/{f}", "source": "run", "kind": "figure", "title": f"{f} (run {r['id']})",
                            "sub": (r.get("cmd") or "")[:80], "ext": ext,
                            "thumb": f"/api/sandbox/runs/{r['id']}/file?path=figures/{f}" if ext in IMAGE_MIME else "",
                            "figure_ok": ext in LATEX_FIGURE_OK, "tags": [], "created": r.get("started", "")})
    except Exception:
        pass
    try:
        from .paper import load_project
        p = load_project()
        for i, t in enumerate(p.get("tables") or []):
            cap = re.search(r"\\caption\{([^}]*)\}", t)
            out.append({"ref": f"table:{i}", "source": "writer", "kind": "table", "title": (cap.group(1) if cap else f"LaTeX table {i + 1}")[:120],
                        "sub": "Paper Writer table", "thumb": "", "figure_ok": False, "tags": [], "created": ""})
        if (p.get("results_notes") or "").strip():
            out.append({"ref": "notes", "source": "writer", "kind": "note", "title": "Results notes (Paper project)",
                        "sub": p["results_notes"][:140], "thumb": "", "figure_ok": False, "tags": [], "created": ""})
    except Exception:
        pass
    return out


def resolve(ref: str, budget: int = 6000) -> dict | None:
    """Content of one pool item for an agent prompt: {title, kind, body, figure?: {path, label, ext}}."""
    try:
        if ref.startswith("up:"):
            it = get(ref[3:])
            body = []
            if it.get("notes"):
                body.append(f"Researcher's description: {it['notes']}")
            if it.get("metrics"):
                body.append("Metrics: " + ", ".join(f"{k}={v}" for k, v in it["metrics"].items()))
            if it.get("findings"):
                body.append(f"AI analysis of the file (grounded in it): {it['findings']}")
            t = text(it["id"])
            if t.strip():
                cut = t[:budget]
                body.append(f"Content ({it.get('file') or 'typed by the researcher'}):\n{cut}" + ("\n…[truncated]" if len(cut) < len(t) else ""))
            out = {"title": it["title"], "kind": it["kind"], "body": "\n".join(body) or "(no description yet)"}
            if it.get("ext") in LATEX_FIGURE_OK:
                out["figure"] = {"path": f"figures/{figure_name(it)}", "label": figure_label(it)}
            return out
        if ref.startswith("run:"):
            from .sandbox import get_run
            r = get_run(ref[4:])
            ms = r.get("metrics") or {}
            series = (r.get("parsed") or {}).get("series") or {}
            ser = "; ".join(f"{k}: " + ", ".join(f"{v:.4g}" for v in vals[-12:]) for k, vals in list(series.items())[:6]
                            if isinstance(vals, list) and all(isinstance(v, (int, float)) for v in vals))
            body = (f"Command: {r.get('cmd', '')}\nFinal metrics (measured): " + ", ".join(f"{k}={v}" for k, v in ms.items())
                    + (f"\nPer-epoch series (last values): {ser}" if ser else "") + f"\nLog tail:\n{(r.get('stdout') or '')[-1500:]}")
            return {"title": f"Run {r['id']}", "kind": "data", "body": body[:budget]}
        if ref.startswith("runfig:"):
            run_id, f = ref[7:].split("/", 1)
            ext = Path(f).suffix.lower()
            out = {"title": f"{f} (run {run_id})", "kind": "figure", "body": f"Figure produced by run {run_id}."}
            if ext in LATEX_FIGURE_OK:
                out["figure"] = {"path": f"figures/run-{run_id}--{f}", "label": f"fig:run-{_slug(Path(f).stem)[:24]}"}
            return out
        if ref.startswith("table:"):
            from .paper import load_project
            t = (load_project().get("tables") or [])[int(ref[6:])]
            return {"title": f"LaTeX table {int(ref[6:]) + 1}", "kind": "table", "body": f"Include verbatim:\n{t}"}
        if ref == "notes":
            from .paper import load_project
            return {"title": "Results notes", "kind": "note", "body": load_project().get("results_notes", "")[:budget]}
    except Exception:
        return None
    return None


def digest(budget: int = 5000, purged: set | None = None) -> str:
    """Short catalogue of the researcher's uploaded results for every agent's context."""
    purged = purged or set()
    lines, used = [], 0
    for it in load():
        if f"result:{it['id']}" in purged:
            continue
        bits = [f"- [{it['kind']}] {it['title']}" + (f" ({it['file']})" if it.get("file") else "")]
        if it.get("notes"):
            bits.append(f"  description: {it['notes'][:400]}")
        if it.get("metrics"):
            bits.append("  metrics: " + ", ".join(f"{k}={v}" for k, v in list(it["metrics"].items())[:10]))
        if it.get("findings"):
            bits.append(f"  findings: {it['findings'][:600]}")
        elif not it.get("notes"):
            t = text(it["id"]).strip()
            if t:
                bits.append("  excerpt: " + re.sub(r"\s+", " ", t[:300]))
        block = "\n".join(bits)
        if used + len(block) > budget:
            lines.append(f"- … {len(load()) - len(lines)} more result(s) in the Experiment Design tab")
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)


# ---------------------------------------------------------------- AI analysis
ANALYST_SYS = """You analyse ONE research result that a PhD researcher produced outside this app (a figure, table, PDF report,
LaTeX, Markdown, data or code output) so that other AI agents (planner, experiment designer, paper author) can use it.
Rules:
- Use ONLY what is visible in the provided file content / image and the researcher's description. Never invent numbers,
  datasets, baselines or conclusions. If something is unreadable or ambiguous, say so.
- Copy numbers exactly as they appear (keep units and decimals).
Output Markdown, concise:
**What it shows:** one or two sentences.
**Key numbers:** bullet list `metric / setting = value` (only values present in the result).
**Findings:** 2-5 bullets (comparisons, trends, best/worst, ablation effects) strictly supported by the result.
**Caveats:** missing information a reviewer would ask for (e.g. no std, unclear baseline), if any.
**Suggested caption:** one sentence suitable for a paper figure/table caption."""


async def analyze(rid: str) -> dict:
    from .llm import call_agent
    it = get(rid)
    user = (f"RESULT TITLE: {it['title']}\nTYPE: {it['kind']}  FILE: {it.get('file') or '(typed note)'}\n"
            f"RESEARCHER'S DESCRIPTION: {it.get('notes') or '(none)'}\n\n")
    images = []
    if it.get("ext") in VISION_OK:
        data = file_path(rid).read_bytes()
        if len(data) > 5 * 1024 * 1024:
            raise ResultError("Image larger than 5 MB — the AI providers cannot read it; describe it instead.")
        images.append({"media_type": IMAGE_MIME[it["ext"]], "data": base64.b64encode(data).decode(), "name": it["file"]})
        user += "The result is the attached image."
    else:
        t = text(rid)
        if not t.strip():
            if it.get("ext") in IMAGE_MIME:
                raise ResultError(f"{it['ext']} images cannot be sent to the AI — convert to PNG/JPG or describe it.")
            raise ResultError("This result has no readable text — add a description first.")
        user += f"CONTENT:\n{t[:60000]}"
    r = await call_agent("results_analyst", ANALYST_SYS, messages=[{"role": "user", "content": user, "images": images}],
                         max_tokens=2000, temperature=0.1)
    findings = r["text"].strip()
    upd = update(rid, {"findings": findings})
    return {"item": upd, "engine": r["engine"], "note": r.get("note", "")}


TABLE_SYS = """Convert the research result below into ONE publication-ready LaTeX table (booktabs) for an IEEE/ACM paper.
Rules: use ONLY values present in the input, copied exactly; never invent rows, columns or numbers; bold the best value per
metric column when "best" is unambiguous (higher is better unless the metric is a loss/error/time/size). Output only:
\\begin{table}[t] \\centering \\caption{...} \\label{tab:...} \\begin{tabular}{...} \\toprule ... \\bottomrule \\end{tabular} \\end{table}
No Markdown fences, no commentary. Wrap wide tables in \\resizebox{\\columnwidth}{!}{...}."""


async def to_latex_table(rid: str) -> dict:
    from .llm import call_agent, strip_fences
    it = get(rid)
    t = text(rid)
    if not t.strip():
        raise ResultError("No tabular text in this result")
    if it.get("ext") == ".tex" and re.search(r"\\begin\{table", t):
        m = re.search(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", t, re.S)
        if m:
            return {"latex": m.group(0), "engine": "verbatim", "note": ""}
    r = await call_agent("data_extractor", TABLE_SYS,
                         f"TITLE: {it['title']}\nDESCRIPTION: {it.get('notes') or ''}\n\nDATA:\n{t[:40000]}",
                         max_tokens=4000, temperature=0.0)
    latex = strip_fences(r["text"]).strip()
    m = re.search(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", latex, re.S)
    if not m and "\\begin{tabular" not in latex:
        raise ResultError(f"The model ({r['engine']}) did not return a LaTeX table — try again or set the "
                          "'Data Extractor' agent to a stronger model.")
    return {"latex": m.group(0) if m else latex, "engine": r["engine"], "note": r.get("note", "")}
