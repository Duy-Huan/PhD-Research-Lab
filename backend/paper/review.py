"""External Paper Review (v2.5): review a finished manuscript (PDF / DOCX / LaTeX / Markdown) as a real venue would.

Storage (per research project):  <workspace>/paper_reviews/<rid>/
    meta.json        title, file, venue settings, desk-check facts
    original.<ext>   the uploaded manuscript (never modified)
    paper.txt        extracted text with [[Page N]] markers
    state.json       reviewer reports, meta-review, issues, fixes, response letter
    source.tex       optional LaTeX source uploaded for auto-apply; source_revised.tex = after applying fixes
Deleting a review moves its folder to paper_reviews/_trash/ (recoverable).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from backend.core.config import workspace
from backend.knowledge.library import pdf_pages

PAPER_BUDGET = 150_000      # characters of manuscript text sent to the reviewers
MAX_UPLOAD = 60 * 1024 * 1024
MANUSCRIPT_EXT = {".pdf", ".docx", ".tex", ".md", ".txt", ".markdown"}
SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "typo": 3}
_lock = threading.Lock()


class ReviewError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _root() -> Path:
    d = workspace() / "paper_reviews"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dir(rid: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{10}", rid or ""):
        raise ReviewError("Invalid review id")
    d = _root() / rid
    if not d.is_dir():
        raise ReviewError("Review not found (it may belong to another project)")
    return d


def _write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text("utf-8"))
    except ValueError:
        from backend.memory.store import quarantine
        quarantine(path)  # reviewer reports cost real model calls: keep the damaged file instead of overwriting it
        return default
    except OSError:
        return default


EMPTY_STATE = {"reviewers": {}, "meta": None, "issues": [], "fixes": {}, "response": None}


def load_state(rid: str) -> dict:
    st = _read_json(_dir(rid) / "state.json", {})
    out = json.loads(json.dumps(EMPTY_STATE))
    out.update(st)
    return out


def update_state(rid: str, fn) -> dict:
    """Read-modify-write under the lock (finalizers of concurrent requests must not lose each other's data)."""
    with _lock:
        st = load_state(rid)
        fn(st)
        _write_json(_dir(rid) / "state.json", st)
        m = load_meta(rid)
        m["updated"] = _now()
        _write_json(_dir(rid) / "meta.json", m)
    return st


def load_meta(rid: str) -> dict:
    return _read_json(_dir(rid) / "meta.json", {})


def save_meta(rid: str, meta: dict) -> dict:
    with _lock:
        meta["updated"] = _now()
        _write_json(_dir(rid) / "meta.json", meta)
    return meta


def paper_text(rid: str) -> str:
    f = _dir(rid) / "paper.txt"
    return f.read_text("utf-8") if f.exists() else ""


def set_active(rid: str) -> None:
    (_root() / "_active").write_text(rid, "utf-8")


def get_active() -> str:
    f = _root() / "_active"
    rid = f.read_text("utf-8").strip() if f.exists() else ""
    return rid if rid and (_root() / rid).is_dir() else ""


# ------------------------------------------------------------------ extraction
def _docx_text(path: Path) -> str:
    from backend.knowledge.attachments import _docx  # same extractor as chat attachments (pure Python)
    return _docx(path)


def extract(path: Path, ext: str) -> tuple[str, int]:
    """Return (text with [[Page N]] markers when pages are known, page_count or 0)."""
    if ext == ".pdf":
        pages, n = pdf_pages(path, 80)
        if not "".join(pages).strip():
            raise ReviewError("This PDF has no extractable text (scanned images?). Run OCR first (e.g. ocrmypdf).")
        return "\n".join(f"[[Page {i + 1}]]\n{t.strip()}" for i, t in enumerate(pages)), n
    if ext == ".docx":
        return _docx_text(path), 0
    return path.read_text("utf-8", errors="replace"), 0


def _detect_title(text: str, ext: str) -> str:
    if ext == ".tex":
        m = re.search(r"\\title(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})+)\}", text)
        if m:
            return re.sub(r"(?:\s|\\\\)+", " ", m.group(1)).strip()[:250]  # "A \\ Title" → "A Title"
    if ext in (".md", ".markdown"):
        m = re.search(r"^#\s+(.+)$", text, re.M)
        if m:
            return m.group(1).strip()[:250]
    for line in text.splitlines()[:40]:
        s = line.strip()
        if len(s) > 15 and not s.startswith("[[Page") and not re.match(r"^(arxiv|doi|preprint|ieee|proceedings|vol\.|http)", s, re.I):
            return s[:250]
    return ""


# ------------------------------------------------------------------ automatic desk check (no AI)
SECTION_PATTERNS = {
    "abstract": r"\babstract\b",
    "introduction": r"\bintroduction\b",
    "related work": r"\brelated\s+work|\bliterature\s+review|\bbackground\b",
    "method": r"\bmethod(?:ology|s)?\b|\bproposed\s+(?:method|approach|framework)\b|\bapproach\b",
    "experiments": r"\bexperiment(?:s|al)?\b|\bevaluation\b|\bresults\b",
    "conclusion": r"\bconclusions?\b",
    "references": r"\breferences\b|\bbibliography\b|\\bibliography|\\begin\{thebibliography\}",
}
PLACEHOLDER_RE = re.compile(r"\bTODO\b|\bTBD\b|\bXXX\b|\?\?|Error! Reference source not found|\[CITATION NEEDED\]|lorem ipsum", re.I)


def prescreen(text: str, pages: int, ext: str, blind: bool) -> dict:
    low = text.lower()
    words = len(re.findall(r"\w+", text))
    figs = {m.group(1) for m in re.finditer(r"\bfig(?:ure|\.)?\s*(\d+)", text, re.I)}
    tabs = {m.group(1).upper() for m in re.finditer(r"\btable\s+([IVX]+|\d+)\b", text, re.I)}
    eqs = len(re.findall(r"\\begin\{(?:equation|align)", text)) if ext == ".tex" else len(set(re.findall(r"\((\d{1,2})\)\s*$", text, re.M)))
    # references: count numbered entries after the last "References" heading
    refs = 0
    if ext == ".tex":
        refs = len(re.findall(r"\\bibitem", text)) or len(set(re.findall(r"\\cite[tp]?\{([^}]+)\}", text)))
    else:
        idx = max(low.rfind("\nreferences"), low.rfind("\nbibliography"))
        if idx > 0:
            tail = text[idx:]
            refs = len(re.findall(r"^\s*\[\d{1,3}\]", tail, re.M)) or len(re.findall(r"^\s*\d{1,3}\.\s+[A-Z]", tail, re.M))
    sections = {k: bool(re.search(p, low)) for k, p in SECTION_PATTERNS.items()}
    head = text[:4000]
    anon = []
    if blind:
        emails = sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", head)))[:5]
        if emails:
            anon.append(f"e-mail addresses near the title: {', '.join(emails)}")
        if re.search(r"\backnowledg(e)?ments?\b", low):
            anon.append("an Acknowledgment section is present (often must be removed for double-blind review)")
        for phr in ("our previous work", "our prior work", "our earlier work", "we previously", "in our previous paper"):
            if phr in low:
                anon.append(f'self-identifying phrase: "{phr}"')
        gh = sorted(set(re.findall(r"github\.com/[\w.-]+", text)))[:3]
        if gh:
            anon.append(f"non-anonymous repository links: {', '.join(gh)}")
        if re.search(r"\\author\{(?!\s*(anonymous|\}))", text, re.I):
            anon.append("\\author{...} is filled in the LaTeX source")
    placeholders = sorted(set(m.group(0) for m in PLACEHOLDER_RE.finditer(text)))[:10]
    return {"pages": pages, "words": words, "figures": len(figs), "tables": len(tabs), "equations": eqs,
            "references": refs, "sections": sections, "anonymity": anon, "placeholders": placeholders}


def prescreen_text(ps: dict, truncated: bool) -> str:
    missing = [k for k, v in ps.get("sections", {}).items() if not v]
    lines = [f"- Pages: {ps.get('pages') or 'n/a (not a PDF)'}; words ≈ {ps.get('words')}; figures referenced ≈ {ps.get('figures')}; "
             f"tables referenced ≈ {ps.get('tables')}; numbered equations ≈ {ps.get('equations')}; references ≈ {ps.get('references')}",
             f"- Standard sections not detected: {', '.join(missing) or 'none'}"]
    if ps.get("anonymity"):
        lines.append("- Possible anonymity problems: " + "; ".join(ps["anonymity"]))
    if ps.get("placeholders"):
        lines.append("- Leftover placeholders / broken references: " + ", ".join(ps["placeholders"]))
    if truncated:
        lines.append(f"- NOTE: the manuscript text was truncated to the first {PAPER_BUDGET:,} characters for reviewing.")
    return "\n".join(lines)


# ------------------------------------------------------------------ CRUD
def create_review(filename: str, data: bytes) -> dict:
    name = Path(filename or "paper.pdf").name[:150]
    ext = Path(name).suffix.lower()
    if ext not in MANUSCRIPT_EXT:
        raise ReviewError(f"Unsupported manuscript type {ext or '(none)'} — use PDF, DOCX, TEX, MD or TXT")
    if len(data) > MAX_UPLOAD:
        raise ReviewError("File larger than 60 MB")
    rid = secrets.token_hex(5)
    d = _root() / rid
    d.mkdir(parents=True)
    orig = d / f"original{ext}"
    orig.write_bytes(data)
    try:
        text, pages = extract(orig, ext)
    except ReviewError:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise ReviewError(f"Could not read {name}: {e}")
    if len(text.strip()) < 500:
        shutil.rmtree(d, ignore_errors=True)
        raise ReviewError("Too little text could be extracted (< 500 characters). Is this the full paper?")
    (d / "paper.txt").write_text(text, "utf-8")
    if ext == ".tex":  # the manuscript itself is the LaTeX source → fixes can be applied directly
        shutil.copyfile(orig, d / "source.tex")
    meta = {"id": rid, "file": name, "ext": ext, "title": _detect_title(text, ext), "pages": pages,
            "chars": len(text), "truncated": len(text) > PAPER_BUDGET, "created": _now(), "updated": _now(),
            "venue": {"type": "conference", "scale": "icore", "rank": "A", "h5": "50-99", "quartile": "Q1",
                      "name": "", "field": "", "blind": True},
            "n_reviewers": 3, "source": "source.tex" if ext == ".tex" else "",
            "prescreen": prescreen(text, pages, ext, True)}
    _write_json(d / "meta.json", meta)
    _write_json(d / "state.json", EMPTY_STATE)
    set_active(rid)
    return meta


def list_reviews() -> list:
    out = []
    for d in _root().iterdir():
        if d.is_dir() and not d.name.startswith("_") and (d / "meta.json").exists():
            m = _read_json(d / "meta.json", {})
            st = _read_json(d / "state.json", {})
            meta = st.get("meta") or {}
            out.append({"id": m.get("id", d.name), "title": m.get("title") or m.get("file"), "file": m.get("file"),
                        "venue": m.get("venue"), "updated": m.get("updated"), "created": m.get("created"),
                        "decision": meta.get("decision", ""), "n_issues": len(st.get("issues") or [])})
    return sorted(out, key=lambda x: x.get("updated") or "", reverse=True)


def get_review(rid: str) -> dict:
    set_active(rid)
    return {"meta": load_meta(rid), "state": load_state(rid)}


def delete_review(rid: str) -> None:
    d = _dir(rid)
    trash = _root() / "_trash"
    trash.mkdir(exist_ok=True)
    shutil.move(str(d), str(trash / f"{rid}-{datetime.now().strftime('%Y%m%d%H%M%S')}"))
    if get_active() == rid:
        (_root() / "_active").unlink(missing_ok=True)


def set_settings(rid: str, body: dict) -> dict:
    meta = load_meta(rid)
    v = dict(meta.get("venue") or {})
    for k in ("type", "scale", "rank", "h5", "quartile", "name", "field", "blind"):
        if k in (body.get("venue") or {}):
            v[k] = body["venue"][k]
    if v.get("type") not in ("conference", "journal"):
        v["type"] = "conference"
    meta["venue"] = v
    if body.get("n_reviewers") in (1, 2, 3):
        meta["n_reviewers"] = body["n_reviewers"]
    if body.get("title"):
        meta["title"] = str(body["title"])[:250]
    meta["prescreen"] = prescreen(paper_text(rid), meta.get("pages", 0), meta.get("ext", ""), bool(v.get("blind", True)))
    return save_meta(rid, meta)


def add_source(rid: str, filename: str, data: bytes) -> dict:
    if Path(filename or "").suffix.lower() != ".tex":
        raise ReviewError("Upload the main LaTeX file (.tex) of the manuscript")
    (_dir(rid) / "source.tex").write_bytes(data)
    (_dir(rid) / "source_revised.tex").unlink(missing_ok=True)
    meta = load_meta(rid)
    meta["source"] = "source.tex"
    meta["source_name"] = Path(filename).name
    return save_meta(rid, meta)


def source_text(rid: str, revised: bool = True) -> str:
    d = _dir(rid)
    for name in (["source_revised.tex"] if revised else []) + ["source.tex"]:
        if (d / name).exists():
            return (d / name).read_text("utf-8", errors="replace")
    return ""


# ------------------------------------------------------------------ text matching helpers
def _norm(s: str) -> str:
    s = s.replace("\u00ad", "").replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff").replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"-\s*\n\s*", "", s)  # PDF hyphenation at line breaks
    return re.sub(r"\s+", " ", s).strip().lower()


def find_span(haystack: str, needle: str) -> tuple[int, int] | None:
    """Locate needle in haystack ignoring whitespace differences. Returns (start, end) in haystack or None."""
    needle = (needle or "").strip()
    if len(needle) < 6:
        return None
    i = haystack.find(needle)
    if i >= 0:
        return i, i + len(needle)
    toks = needle.split()
    pat = r"\s*".join(re.escape(t) for t in toks)  # whitespace-insensitive (also across line breaks)
    m = re.search(pat, haystack)
    if m:
        return m.start(), m.end()
    m = re.search(pat, haystack, re.I)
    return (m.start(), m.end()) if m else None


def quote_found(text: str, quote: str) -> bool:
    if not quote or len(quote.strip()) < 6:
        return False
    return find_span(text, quote) is not None or _norm(quote) in _norm(text)


# ------------------------------------------------------------------ AI output parsing
def parse_review_header(text: str) -> dict:
    rec = re.search(r"\*\*Recommendation:\*\*\s*([^\n*]+)", text)
    score = re.search(r"\*\*Overall score:\*\*\s*(\d{1,2})\s*/\s*10", text)
    conf = re.search(r"\*\*Confidence:\*\*\s*(\d)\s*/\s*5", text)
    return {"recommendation": rec.group(1).strip(" .") if rec else "",
            "score": int(score.group(1)) if score else None, "confidence": int(conf.group(1)) if conf else None}


def parse_meta_header(text: str) -> dict:
    dec = re.search(r"\*\*Decision:\*\*\s*([^\n*]+)", text)
    sc = re.search(r"\*\*Consensus score:\*\*\s*(\d{1,2})\s*/\s*10", text)
    return {"decision": dec.group(1).strip(" .") if dec else "", "score": int(sc.group(1)) if sc else None}


def normalise_issues(raw: list, text: str) -> list:
    out, seen = [], set()
    for i, it in enumerate(raw or []):
        if not isinstance(it, dict):
            continue
        sev = str(it.get("severity", "minor")).lower().strip()
        sev = sev if sev in SEVERITY_ORDER else ("critical" if "crit" in sev else "major" if "maj" in sev else "typo" if "typo" in sev else "minor")
        iid = str(it.get("id") or f"I{i + 1}")
        while iid in seen:
            iid += "b"
        seen.add(iid)
        quote = str(it.get("quote") or "").strip()
        out.append({"id": iid, "severity": sev, "category": str(it.get("category") or "clarity"),
                    "title": str(it.get("title") or it.get("problem") or "")[:160],
                    "location": str(it.get("location") or ""), "quote": quote[:600],
                    "quote_found": quote_found(text, quote), "problem": str(it.get("problem") or ""),
                    "fix": str(it.get("fix") or ""), "fix_type": str(it.get("fix_type") or "text"),
                    "effort": str(it.get("effort") or ""), "raised_by": [str(x) for x in (it.get("raised_by") or [])][:6],
                    "status": "open"})
    out.sort(key=lambda x: SEVERITY_ORDER[x["severity"]])
    return out


FIX_BLOCK = re.compile(r"<<<\s*(ORIGINAL|REVISED|NOTE|PLAN)\s*\n?(.*?)\n?\s*>>>", re.S | re.I)


def parse_fix(text: str) -> dict:
    parts = {k.lower(): v.strip() for k, v in FIX_BLOCK.findall(text)}
    if not parts:  # model ignored the format: keep everything as a note
        return {"original": "", "revised": "", "note": text.strip(), "plan": ""}
    return {"original": parts.get("original", ""), "revised": parts.get("revised", ""),
            "note": parts.get("note", ""), "plan": parts.get("plan", "")}


# ------------------------------------------------------------------ excerpts for the fixer
def excerpt_for(rid: str, issue: dict, window: int = 3500) -> tuple[str, str]:
    """Best excerpt to fix an issue: the LaTeX source around the quote when available, else the extracted text."""
    quote = issue.get("quote") or ""
    src = source_text(rid)
    for text, fmt in ((src, "LaTeX source"), (paper_text(rid), "plain text extracted from the manuscript")):
        if not text:
            continue
        span = find_span(text, quote) if quote else None
        if span:
            a, b = max(0, span[0] - window), min(len(text), span[1] + window)
            return text[a:b], fmt
    # no quote match: use the section named in the location, else the beginning of the paper
    text, fmt = (src, "LaTeX source") if src else (paper_text(rid), "plain text extracted from the manuscript")
    loc = (issue.get("location") or "").lower()
    for key in ("abstract", "introduction", "related", "method", "experiment", "result", "discussion", "conclusion"):
        if key in loc:
            m = re.search(key, text, re.I)
            if m:
                return text[max(0, m.start() - 500): m.start() + 2 * window], fmt
    return text[: 2 * window], fmt


# ------------------------------------------------------------------ applying accepted fixes to the LaTeX source
def apply_fixes(rid: str, ids: list | None = None) -> dict:
    st = load_state(rid)
    src = source_text(rid, revised=False)
    if not src:
        raise ReviewError("Upload the LaTeX source (.tex) first — fixes can only be applied to a source file")
    applied, missing, skipped = [], [], []
    for iid, fx in st["fixes"].items():
        if ids and iid not in ids:
            continue
        if fx.get("status") not in ("accepted", "applied"):
            continue
        orig, rev = fx.get("original", ""), fx.get("revised", "")
        if not orig or not rev:
            skipped.append(iid)  # insertions / plans must be placed by the author
            continue
        span = find_span(src, orig)
        if not span:
            missing.append(iid)
            continue
        src = src[:span[0]] + rev + src[span[1]:]
        applied.append(iid)
    (_dir(rid) / "source_revised.tex").write_text(src, "utf-8")

    def mark(s):
        for iid in applied:
            s["fixes"][iid]["status"] = "applied"
            for it in s["issues"]:
                if it["id"] == iid:
                    it["status"] = "done"
    update_state(rid, mark)
    return {"applied": applied, "not_found": missing, "skipped": skipped, "file": "source_revised.tex"}


# ------------------------------------------------------------------ reports
def reviews_digest(st: dict, per: int = 30_000) -> str:
    return "\n\n".join(r["text"][:per] for _, r in sorted(st["reviewers"].items()))


def issues_digest(st: dict) -> str:
    lines = []
    for it in st["issues"]:
        fx = st["fixes"].get(it["id"]) or {}
        status = "DONE" if it["status"] == "done" or fx.get("status") == "applied" else \
                 "WON'T FIX" if it["status"] == "wontfix" else \
                 "ACCEPTED FIX (author still has to insert it)" if fx.get("status") == "accepted" else "OPEN"
        lines.append(f"- [{it['id']}] ({it['severity']}, raised by {', '.join(it['raised_by']) or '?'}) {it['title']} — {it['location']}\n"
                     f"  problem: {it['problem']}\n  status: {status}" + (f"\n  change made: {fx.get('note', '')}" if status.startswith(("DONE", "ACCEPTED")) and fx.get("note") else ""))
    return "\n".join(lines) or "(no issues extracted)"


def report_md(rid: str) -> str:
    from backend.paper.review_prompts import venue_label
    m, st = load_meta(rid), load_state(rid)
    out = [f"# Review report — {m.get('title') or m.get('file')}", "",
           f"- Manuscript: `{m.get('file')}`  ", f"- Venue standard: **{venue_label(m.get('venue') or {})}**  ",
           f"- Generated: {_now()} by PhD Research Lab (AI-simulated peer review — verify before acting)", ""]
    if st.get("meta"):
        out += [st["meta"]["text"], ""]
    if st["issues"]:
        out += ["# Issue checklist (critical → minor)", ""]
        for it in st["issues"]:
            fx = st["fixes"].get(it["id"]) or {}
            done = it["status"] == "done" or fx.get("status") == "applied"
            out.append(f"- [{'x' if done else ' '}] **{it['id']} · {it['severity'].upper()}** — {it['title']} *({it['location']})*  ")
            out.append(f"  {it['problem']}  ")
            out.append(f"  → **Fix:** {it['fix']}")
            if fx.get("revised"):
                out.append(f"\n  ```\n  {fx['revised'][:1500]}\n  ```")
        out.append("")
    for _, r in sorted(st["reviewers"].items()):
        out += ["---", "", r["text"], ""]
    return "\n".join(out)


def fixes_md(rid: str) -> str:
    st = load_state(rid)
    out = ["# Proposed fixes", ""]
    for it in st["issues"]:
        fx = st["fixes"].get(it["id"])
        if not fx:
            continue
        out += [f"## {it['id']} · {it['severity']} — {it['title']}", f"*Location:* {it['location']} · *Status:* {fx.get('status', 'proposed')}", ""]
        if fx.get("original"):
            out += ["**Original**", "", "```", fx["original"], "```", ""]
        if fx.get("revised"):
            out += ["**Revised**", "", "```", fx["revised"], "```", ""]
        if fx.get("note"):
            out += [f"> {fx['note']}", ""]
        if fx.get("plan"):
            out += ["**Plan**", "", fx["plan"], ""]
    return "\n".join(out)
