"""Local reference library: PDF ingestion (PyMuPDF or pure-Python pypdf), metadata store and BibTeX.

PyMuPDF ships a native DLL that Windows 11 Smart App Control / Application Control may block.
In that case (or when PHDLAB_PDF_BACKEND=pypdf) the lab falls back to pypdf, which is pure Python.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import unicodedata
from pathlib import Path

import os

fitz = None
PdfReader = None
PDF_BACKEND = "none"
PDF_BACKEND_ERROR = ""
if os.environ.get("PHDLAB_PDF_BACKEND", "").lower() != "pypdf":
    try:
        import pymupdf as fitz  # PyMuPDF >= 1.24
        PDF_BACKEND = "pymupdf"
    except Exception as _e:  # ImportError, blocked DLL (OSError), ...
        fitz = None
        PDF_BACKEND_ERROR = f"PyMuPDF unavailable: {_e}"
if fitz is None:
    try:
        from pypdf import PdfReader
        PDF_BACKEND = "pypdf"
    except Exception as _e:
        PDF_BACKEND_ERROR += f" | pypdf unavailable: {_e}"

from backend.core.config import data_dir, refs_dir


def _lib_path():
    return data_dir() / "library.json"  # per project
_lock = threading.RLock()

FIELDS = ["title", "authors", "year", "venue", "entry_type", "volume", "number",
          "pages", "doi", "publisher", "abstract"]
STOPWORDS = {"a", "an", "the", "on", "of", "for", "in", "to", "and", "with", "towards", "toward", "via", "using"}


# ------------------------------------------------------------------ storage
def load_library() -> dict:
    p = _lib_path()
    if p.exists():
        try:
            d = json.loads(p.read_text("utf-8"))
            if isinstance(d, dict):
                return d
            raise ValueError("library.json is not an object")
        except ValueError:
            from backend.memory.store import quarantine
            quarantine(p)  # keep it: the next save would otherwise erase every curated reference (keys, metadata)
            return {}
        except OSError:
            return {}
    return {}


def save_library(lib: dict) -> None:
    from backend.memory.store import replace_retry
    with _lock:
        assign_keys(lib)
        p = _lib_path()
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(lib, indent=2, ensure_ascii=False), "utf-8")
        replace_retry(tmp, p)


def included(lib: dict | None = None) -> list:
    lib = lib if lib is not None else load_library()
    return sorted([e for e in lib.values() if e.get("include", True)], key=lambda e: e.get("key", ""))


# ------------------------------------------------------------------ extraction
def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _require_backend() -> None:
    if PDF_BACKEND == "none":
        raise RuntimeError("No PDF library available. Run: pip install pypdf  (" + PDF_BACKEND_ERROR + ")")


def _pick_title(spans: list, top_is_small_y: bool, height: float) -> str:
    """spans: (size, y, text). Pick the largest-font text in the top half of page 1."""
    top = [s for s in spans if (s[1] < height * 0.5 if top_is_small_y else s[1] > height * 0.5)]
    if not top:
        return ""
    mx = max(s[0] for s in top)
    ordered = sorted(top, key=lambda x: x[1], reverse=not top_is_small_y)
    title = " ".join(t for sz, _, t in ordered if sz >= mx - 0.5)
    title = re.sub(r"\s+", " ", title).strip()
    return title if 10 < len(title) < 300 else ""


def _read_pdf(path: Path, n_pages: int = 2, want_title: bool = True) -> dict:
    """Return {meta:{title,author,creationDate}, pages:int, text:str, font_title:str}."""
    _require_backend()
    if PDF_BACKEND == "pymupdf":
        with fitz.open(path) as doc:
            meta = doc.metadata or {}
            pages = doc.page_count
            text = "\n".join(doc[i].get_text() for i in range(min(n_pages, pages)))
            font_title = ""
            if want_title and pages:
                pg = doc[0]
                spans = []
                for b in pg.get_text("dict").get("blocks", []):
                    for line in b.get("lines", []):
                        for sp in line.get("spans", []):
                            t = sp["text"].strip()
                            if len(t) > 2:
                                spans.append((round(sp["size"], 1), sp["bbox"][1], t))
                font_title = _pick_title(spans, True, pg.rect.height)
        return {"meta": meta, "pages": pages, "text": text, "font_title": font_title}

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass
    info = reader.metadata or {}
    meta = {"title": str(info.get("/Title") or ""), "author": str(info.get("/Author") or ""),
            "creationDate": str(info.get("/CreationDate") or "")}
    pages = len(reader.pages)
    texts, spans = [], []
    font_title = ""
    for i in range(min(n_pages, pages)):
        pg = reader.pages[i]
        if i == 0 and want_title:
            def visit(text, cm, tm, font_dict, font_size):
                t = (text or "").strip()
                if len(t) < 3:
                    return
                try:
                    scale = abs(tm[3] * cm[3]) or abs(tm[0] * cm[0]) or 1.0
                    y = tm[5] * cm[3] + cm[5]
                    spans.append((round(float(font_size) * scale, 1), float(y), t))
                except Exception:
                    pass
            try:
                texts.append(pg.extract_text(visitor_text=visit) or "")
            except Exception:
                texts.append(pg.extract_text() or "")
            font_title = _pick_title(spans, False, float(pg.mediabox.height))
        else:
            texts.append(pg.extract_text() or "")
    text = "\n".join(texts)
    if want_title and not font_title:  # fallback: first plausible line
        for line in text.splitlines():
            ln = line.strip()
            if 15 < len(ln) < 250 and not re.search(r"IEEE|ACM|Vol\.|doi|©|arXiv|Proceedings|Journal|http", ln, re.I):
                font_title = ln
                break
    return {"meta": meta, "pages": pages, "text": text, "font_title": font_title}


def first_pages_text(path: Path, pages: int = 2, limit: int = 8000) -> str:
    try:
        return _read_pdf(path, pages, want_title=False)["text"][:limit]
    except Exception:
        return ""


def _valid_meta_title(t: str) -> bool:
    t = (t or "").strip()
    bad = ("untitled", "microsoft word", ".dvi", ".pdf", ".doc", "paper title")
    return len(t) > 10 and not any(b in t.lower() for b in bad)


def _split_authors(s: str) -> list:
    if not s:
        return []
    parts = re.split(r";|\band\b|,(?=\s*[A-Z][a-z]+\s)", s)
    return [p.strip() for p in parts if len(p.strip()) > 2][:20]


def heuristic_metadata(path: Path) -> dict:
    meta, text, pages, title = {}, "", 0, ""
    try:
        r = _read_pdf(path, 2)
        meta, pages, text = r["meta"], r["pages"], r["text"]
        title = meta.get("title", "") if _valid_meta_title(meta.get("title", "")) else r["font_title"]
    except Exception as e:
        return {"title": path.stem, "error": f"Could not open PDF: {e}"}

    abstract = ""
    m = re.search(
        r"Abstract[\s—–\-:.]*(.+?)(?:\n\s*(?:Index Terms|Keywords|CCS Concepts|"
        r"I\.\s*I\s*NTRODUCTION|I\.\s*INTRODUCTION|1\.?\s*Introduction|Introduction\n))",
        text, flags=re.S | re.I)
    if m:
        abstract = re.sub(r"\s+", " ", m.group(1)).strip().lstrip("·—–-:. ")[:2500]

    doi = ""
    dm = re.search(r"\b(10\.\d{4,9}/[^\s\"<>,;]+)", text)
    if dm:
        doi = dm.group(1).rstrip(".)")

    year = ""
    cd = meta.get("creationDate") or ""
    ym = re.search(r"(19|20)\d{2}", cd) or re.search(r"(?:©|\(c\)|Copyright)\s*((?:19|20)\d{2})", text)
    if ym:
        year = re.search(r"(19|20)\d{2}", ym.group(0)).group(0)

    venue = ""
    # "IEEE Transactions on …", "IEEE Geoscience and Remote Sensing Letters", "IEEE/CVF Conference on …", "IEEE Access"
    vm = re.search(r"(IEEE(?:/CVF)? (?:[A-Z][A-Za-z\-]* |and |of |on )*(?:Transactions|Journal|Letters|Conference|Access)\b[A-Za-z ,\-]*|"
                   r"Proceedings of [^\n]+|ACM [A-Z][A-Za-z ]+)", text)
    if vm:
        venue = vm.group(0).strip()[:200]

    return {
        "title": re.sub(r"\s+", " ", title or path.stem.replace("_", " ")).strip(),
        "authors": _split_authors(meta.get("author", "")),
        "year": year, "venue": venue, "doi": doi, "abstract": abstract,
        "entry_type": "inproceedings" if re.search(r"conference|proceedings|symposium|workshop", venue, re.I) else "article",
        "volume": "", "number": "", "pages": "", "publisher": "",
        "page_count": pages,
    }


def scan_directory() -> dict:
    """Sync library.json with the PDFs present in the references directory."""
    with _lock:
        return _scan_directory()


def canonical_pdf_name(metadata: dict, digest: str) -> str:
    """PhD Lab: YEAR_Author_Title_SHA256[0:12].pdf, ASCII and bounded for Windows."""
    def slug(value, limit):
        return re.sub(r"[^a-zA-Z0-9]+", "-", _ascii(str(value))).strip("-")[:limit].rstrip("-")
    year = str(metadata.get("year") or "")
    year = year if re.fullmatch(r"(?:19|20)\d{2}", year) else "nd"
    authors = metadata.get("authors") or []
    if isinstance(authors, str):
        authors = _split_authors(authors)
    author = slug(_last_name(str(authors[0])), 24) if authors else "Unknown"
    title = slug(metadata.get("title") or "Untitled", 80) or "Untitled"
    return f"{year}_{author or 'Unknown'}_{title}_{digest[:12]}.pdf"


def _pdf_target(metadata: dict, data: bytes) -> Path:
    digest = hashlib.sha256(data).hexdigest()
    target = refs_dir() / canonical_pdf_name(metadata, digest)
    if target.exists() and target.read_bytes() != data:
        target = target.with_name(target.stem + "_" + digest[12:] + ".pdf")
    return target


def ingest_pdf(original_name: str, data: bytes) -> dict:
    """Upload without overwriting another paper; keep original name as provenance."""
    import tempfile
    if not original_name.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
        raise ValueError("A PDF file is required")
    if len(data) > 30 * 1024 * 1024:
        raise ValueError("PDF exceeds the 30 MB upload limit")
    with _lock:
        lib = load_library()
        digest = hashlib.sha1(data).hexdigest()
        for entry in lib.values():
            if entry.get("sha1") == digest and (refs_dir() / entry["file"]).is_file():
                return entry
        with tempfile.NamedTemporaryFile(suffix=".pdf", dir=refs_dir(), delete=False) as f:
            temporary = Path(f.name)
            f.write(data)
        try:
            meta = heuristic_metadata(temporary)
            if meta.get("error") or meta.get("title") == temporary.stem:
                meta["title"] = Path(original_name.replace("\\", "/")).stem
            target = _pdf_target(meta, data)
            if not target.exists():
                # Exclusive creation also protects an external writer racing ingestion.
                with target.open("xb") as dest:
                    dest.write(data)
            meta.update(file=target.name, original_name=Path(original_name.replace("\\", "/")).name,
                        sha1=digest, include=True, key_locked=False, llm_refined=False, pdf_available=True)
            lib[target.name] = meta
            save_library(lib)
            return lib[target.name]
        finally:
            temporary.unlink(missing_ok=True)


def _scan_directory() -> dict:
    rdir = refs_dir()
    lib = load_library()
    present = {p.name: p for p in rdir.glob("*.pdf")} | {p.name: p for p in rdir.glob("*.PDF")}
    removed = False
    for name in list(lib):
        if name not in present and not lib[name].get("metadata_only"):
            del lib[name]
            removed = True
    if removed:
        # ingest_pdf reads the store too; do not resurrect missing records during the same scan.
        save_library(lib)
    added = []
    for name, p in present.items():
        digest = sha1(p)
        if name in lib and lib[name].get("sha1") == digest:
            lib[name]["pdf_available"] = not lib[name].get("ingest_rejected", False)
            continue
        if name not in lib:
            try:
                entry = ingest_pdf(name, p.read_bytes())
            except ValueError as error:
                # One malformed/oversized file dropped in references must not hide the other papers.
                lib[name] = {"file": name, "title": p.stem, "sha1": digest, "include": False,
                             "pdf_available": False, "ingest_rejected": True, "error": str(error)}
                added.append(name)
                save_library(lib)
                continue
            lib = load_library()
            if p.resolve() != (rdir / entry["file"]).resolve():
                p.unlink()
            added.append(entry["file"])
            continue
        entry = heuristic_metadata(p)
        entry.update({"file": name, "sha1": digest, "include": True, "llm_refined": False, "key_locked": False, "pdf_available": True})
        lib[name] = entry
        added.append(name)
    save_library(lib)
    return {"library": lib, "added": added}


def save_source(source: dict, pdf: bytes | None = None) -> dict:
    """Keep a real retrieved record even when its publisher does not offer a downloadable PDF."""
    from urllib.parse import urlsplit
    title = re.sub(r"\s+", " ", str(source.get("title") or "")).strip()[:1000]
    doi = re.sub(r"^https?://(?:dx\.)?doi.org/", "", str(source.get("doi") or "").strip(), flags=re.I)[:300]
    url = str(source.get("url") or (f"https://doi.org/{doi}" if doi else "")).strip()[:4000]
    parsed = urlsplit(url)
    if not title or parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A paper title and valid public HTTP(S) source URL are required")
    identity = "doi:" + doi.casefold() if doi else "url:" + url.rstrip("/")
    with _lock:
        lib = load_library()
        if pdf:
            for e in lib.values():
                if e.get("sha1") == hashlib.sha1(pdf).hexdigest() and (refs_dir() / e["file"]).is_file():
                    return {"entry": e, "already_saved": True, "pdf_saved": True}
        for e in lib.values():
            if (doi and str(e.get("doi") or "").casefold() == doi.casefold()) or url == e.get("source_url"):
                if pdf and e.get("metadata_only"):
                    name = _pdf_target(e, pdf).name
                    if not (refs_dir() / name).exists():
                        with (refs_dir() / name).open("xb") as dest:
                            dest.write(pdf)
                    lib.pop(e["file"])
                    e.update(file=name, pdf_available=True, metadata_only=False, sha1=hashlib.sha1(pdf).hexdigest(),
                             pdf_url=str(source.get("pdf_url") or ""))
                    lib[name] = e
                    save_library(lib)
                    return {"entry": e, "already_saved": True, "pdf_saved": True, "upgraded": True}
                return {"entry": e, "already_saved": True, "pdf_saved": bool(e.get("pdf_available", not e.get("metadata_only")))}
        token = hashlib.sha256(identity.encode()).hexdigest()[:20]
        name = _pdf_target(source, pdf).name if pdf else "paper-" + token + ".paper.json"
        if pdf:
            if not (refs_dir() / name).exists():
                with (refs_dir() / name).open("xb") as dest:
                    dest.write(pdf)
        authors = source.get("authors") or []
        if not isinstance(authors, list):
            authors = _split_authors(str(authors))
        entry = {"file": name, "title": title, "authors": [str(a)[:200] for a in authors[:30]],
                 "year": str(source.get("year") or "")[:4], "venue": str(source.get("venue") or "")[:500],
                 "doi": doi, "abstract": str(source.get("abstract") or source.get("snippet") or "")[:12000],
                 "source_url": url, "url": url, "source": str(source.get("source") or "")[:200],
                 "pdf_url": str(source.get("pdf_url") or "")[:4000], "metadata_only": not bool(pdf),
                 "citations": source.get("citations"), "sources": source.get("sources") or [str(source.get("source") or "")],
                 "pdf_available": bool(pdf), "include": True, "key_locked": False, "llm_refined": False,
                 "entry_type": "misc" if "arxiv" in str(source.get("venue") or source.get("source")).lower() else
                               "inproceedings" if source.get("publication_type") == "conference" else "article"}
        if isinstance(source.get("journal_ranking"), dict):
            entry["journal_ranking"] = source["journal_ranking"]
        if pdf:
            entry["sha1"] = hashlib.sha1(pdf).hexdigest()
        lib[name] = entry
        save_library(lib)
        return {"entry": lib[name], "already_saved": False, "pdf_saved": bool(pdf)}


def merge_llm_metadata(entry: dict, data: dict) -> dict:
    for f in FIELDS:
        v = data.get(f)
        if f == "authors":
            if isinstance(v, str):
                v = _split_authors(v)
            if isinstance(v, list) and v:
                entry["authors"] = [str(a).strip() for a in v if str(a).strip()][:30]
            continue
        if v not in (None, "", [], "null", "unknown", "Unknown"):
            entry[f] = str(v).strip()
    if entry.get("entry_type") not in ("article", "inproceedings", "misc", "book", "incollection", "techreport"):
        entry["entry_type"] = "article"
    entry["llm_refined"] = True
    if not entry.get("key_locked"):
        entry.pop("key", None)
    return entry


# ------------------------------------------------------------------ BibTeX
def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _last_name(author: str) -> str:
    a = author.strip()
    if "," in a:
        return a.split(",")[0].strip()
    toks = a.split()
    return toks[-1] if toks else "anon"


def make_key(e: dict) -> str:
    authors = e.get("authors") or []
    last = re.sub(r"[^a-z]", "", _ascii(_last_name(authors[0])).lower()) if authors else "anon"
    words = [w for w in re.findall(r"[A-Za-z]+", _ascii(e.get("title", ""))) if w.lower() not in STOPWORDS]
    first = words[0].lower() if words else "paper"
    return f"{last or 'anon'}{e.get('year') or 'nd'}{first}"


def assign_keys(lib: dict) -> None:
    seen = set()
    for name in sorted(lib):
        e = lib[name]
        if e.get("key_locked") and e.get("key"):
            seen.add(e["key"])
    for name in sorted(lib):
        e = lib[name]
        if e.get("key_locked") and e.get("key"):
            continue
        base = make_key(e)
        key, i = base, 0
        while key in seen:
            key = base + "abcdefghijklmnopqrstuvwxyz"[i % 26] + ("" if i < 26 else str(i // 26))
            i += 1
        e["key"] = key
        seen.add(key)


def _esc(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    chars = "&%#" if "$" in s else "&%#_"  # leave inline math ($\ell_1$) intact
    return re.sub(r"(?<!\\)([" + chars + "])", r"\\\1", s)


def _protect(title: str) -> str:
    # keep acronyms / capitalised tokens (CNN, RISC-V, SystemC) from being lower-cased by the style
    return re.sub(r"\b([A-Za-z0-9\-]*[A-Z][A-Za-z0-9\-]*[A-Z0-9][A-Za-z0-9\-]*)\b", r"{\1}", title)


def entry_to_bibtex(e: dict) -> str:
    typ = e.get("entry_type") or "article"
    fields = [("title", "{" + _protect(_esc(e.get("title", "Untitled"))) + "}")]
    if e.get("authors"):
        fields.append(("author", "{" + " and ".join(_esc(a) for a in e["authors"]) + "}"))
    venue = e.get("venue", "")
    if venue:
        fields.append(("booktitle" if typ in ("inproceedings", "incollection") else
                       "journal" if typ == "article" else "howpublished", "{" + _esc(venue) + "}"))
    for f in ("volume", "number"):
        if e.get(f):
            fields.append((f, "{" + _esc(e[f]) + "}"))
    if e.get("pages"):
        fields.append(("pages", "{" + re.sub(r"\s*[-–—]+\s*", "--", _esc(e["pages"])) + "}"))
    if e.get("year"):
        fields.append(("year", "{" + _esc(e["year"]) + "}"))
    if e.get("publisher"):
        fields.append(("publisher", "{" + _esc(e["publisher"]) + "}"))
    if e.get("doi"):
        fields.append(("doi", "{" + e["doi"].strip() + "}"))
    if e.get("source_url"):
        fields.append(("url", "{" + _esc(e["source_url"]) + "}"))
    body = ",\n".join(f"  {k:<9} = {v}" for k, v in fields)
    return f"@{typ}{{{e['key']},\n{body}\n}}"


def build_bibtex(entries: list | None = None) -> str:
    entries = entries if entries is not None else included()
    head = ("% references.bib - generated by PhD Interactive Autonomous Research Lab\n"
            f"% {len(entries)} entries from the local references/ PDF pool. Verify fields before submission.\n\n")
    return head + "\n\n".join(entry_to_bibtex(e) for e in entries) + "\n"


def pdf_text(path: Path, max_pages: int = 40, limit: int = 200_000) -> tuple[str, int]:
    """Full text of the first `max_pages` pages (for chat attachments). Returns (text, page_count)."""
    r = _read_pdf(path, max_pages, want_title=False)
    return r["text"][:limit], r["pages"]


def pdf_pages(path: Path, max_pages: int = 80) -> tuple[list, int]:
    """Text of each page (for page-referenced reviewing). Returns ([page_text, ...], page_count)."""
    _require_backend()
    if PDF_BACKEND == "pymupdf":
        with fitz.open(path) as doc:
            return [doc[i].get_text() for i in range(min(max_pages, doc.page_count))], doc.page_count
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass
    out = []
    for i in range(min(max_pages, len(reader.pages))):
        try:
            out.append(reader.pages[i].extract_text() or "")
        except Exception:
            out.append("")
    return out, len(reader.pages)
