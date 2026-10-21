"""Chat attachments: uploaded files, web links and papers from the project library.

Everything is stored per project in <workspace>/attachments/:
    index.json           metadata of every attachment
    <id>.<ext>           original file (uploads, downloaded PDFs)
    <id>.txt             extracted text that is sent to the AI

Supported: PDF, DOCX, PPTX, XLSX, Jupyter notebooks, HTML, plain text / data / code files, images
(sent as vision input to providers that support it), web pages and online PDFs, library papers.
"""
from __future__ import annotations

import base64
import html
import json
import re
import secrets
import threading
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.core.config import refs_dir, workspace
from backend.knowledge.library import load_library, pdf_text

MAX_UPLOAD = 25 * 1024 * 1024
MAX_TEXT = 200_000
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".json", ".log", ".py", ".m", ".tex", ".bib", ".yaml", ".yml", ".c", ".cc",
            ".cpp", ".h", ".hpp", ".v", ".sv", ".vhd", ".vhdl", ".java", ".js", ".ts", ".r", ".jl", ".out", ".dat", ".xml",
            ".sh", ".bat", ".ini", ".cfg", ".toml", ".sql", ".rst", ".cu", ".scala", ".go", ".rs"}
_lock = threading.Lock()


class AttachmentError(Exception):
    pass


def _dir() -> Path:
    d = workspace() / "attachments"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index() -> dict:
    p = _dir() / "index.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except ValueError:
        from backend.memory.store import quarantine
        quarantine(p)  # never let the next upload overwrite the only copy of every attachment's metadata
        return {}
    except OSError:
        return {}


def _save_index(idx: dict) -> None:
    p = _dir() / "index.json"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(p)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _register(meta: dict, text: str) -> dict:
    meta["chars"] = len(text)
    meta["created"] = _now()
    (_dir() / f"{meta['id']}.txt").write_text(text, "utf-8")
    with _lock:
        idx = _index()
        idx[meta["id"]] = meta
        _save_index(idx)
    return meta


def get_meta(att_id: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{12}", att_id or ""):
        raise AttachmentError("Invalid attachment id")
    m = _index().get(att_id)
    if not m:
        raise AttachmentError("Attachment not found")
    return m


def get_text(att_id: str) -> str:
    get_meta(att_id)
    f = _dir() / f"{att_id}.txt"
    return f.read_text("utf-8") if f.exists() else ""


# ------------------------------------------------------------------ extraction
def _xml_text(xml: str, para_tag: str) -> str:
    xml = re.sub(rf"</{para_tag}>", "\n", xml)
    xml = re.sub(r"<w:tab/>|<a:tab/>", "\t", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def _docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return _xml_text(z.read("word/document.xml").decode("utf8", "ignore"), "w:p")


def _pptx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                        key=lambda n: int(re.findall(r"\d+", n)[-1]))
        return "\n\n".join(f"--- Slide {i + 1} ---\n" + _xml_text(z.read(n).decode("utf8", "ignore"), "a:p")
                           for i, n in enumerate(slides))


def _xlsx(path: Path, max_rows: int = 2000) -> str:
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sx = z.read("xl/sharedStrings.xml").decode("utf8", "ignore")
            shared = [html.unescape(re.sub(r"<[^>]+>", "", si)) for si in re.findall(r"<si>(.*?)</si>", sx, re.S)]
        out = []
        sheets = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        for n in sheets[:5]:
            out.append(f"--- {Path(n).stem} ---")
            sx = z.read(n).decode("utf8", "ignore")
            for row in re.findall(r"<row[^>]*>(.*?)</row>", sx, re.S)[:max_rows]:
                cells = []
                for attrs, body in re.findall(r"<c([^>]*)>(.*?)</c>", row, re.S):
                    v = re.search(r"<v>(.*?)</v>", body, re.S)
                    t = re.search(r'\bt="(\w+)"', attrs)
                    val = v.group(1) if v else html.unescape(re.sub(r"<[^>]+>", "", body))
                    if t and t.group(1) == "s" and v and val.isdigit() and int(val) < len(shared):
                        val = shared[int(val)]
                    cells.append(val.replace(",", ";"))
                out.append(",".join(cells))
        return "\n".join(out)


def _ipynb(path: Path) -> str:
    nb = json.loads(path.read_text("utf-8", errors="ignore"))
    parts = []
    for c in nb.get("cells", []):
        src = "".join(c.get("source", []))
        parts.append(f"```{'python' if c.get('cell_type') == 'code' else 'markdown'}\n{src}\n```")
    return "\n\n".join(parts)


class _Readable(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "svg", "form", "aside"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "pre", "blockquote"}

    def __init__(self):
        super().__init__()
        self.out, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.out.append("\n")
        if tag in ("h1", "h2", "h3"):
            self.out.append("## ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)

    def text(self) -> str:
        t = "".join(self.out)
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def html_to_text(raw: str) -> tuple[str, str]:
    p = _Readable()
    try:
        p.feed(raw)
    except Exception:
        pass
    return p.title.strip(), p.text()


def _extract(path: Path, ext: str) -> tuple[str, str, dict]:
    """Returns (kind, text, extra-meta)."""
    if ext in IMAGE_TYPES:
        return "image", "", {"media_type": IMAGE_TYPES[ext]}
    if ext == ".pdf":
        text, pages = pdf_text(path)
        if not text.strip():
            raise AttachmentError("PDF has no extractable text (scanned?) — run OCR first")
        return "pdf", text, {"pages": pages}
    if ext == ".docx":
        return "docx", _docx(path), {}
    if ext == ".pptx":
        return "pptx", _pptx(path), {}
    if ext in (".xlsx", ".xlsm"):
        return "xlsx", _xlsx(path), {}
    if ext == ".ipynb":
        return "notebook", _ipynb(path), {}
    if ext in (".html", ".htm"):
        title, text = html_to_text(path.read_text("utf-8", errors="ignore"))
        return "html", text, {"title": title}
    if ext in TEXT_EXT or ext == "":
        return "text", path.read_text("utf-8", errors="replace"), {}
    raise AttachmentError(f"Unsupported file type {ext or '(none)'}")


# ------------------------------------------------------------------ public API
def add_upload(filename: str, data: bytes) -> dict:
    name = Path(filename or "file").name[:150]
    if len(data) > MAX_UPLOAD:
        raise AttachmentError(f"{name}: larger than {MAX_UPLOAD // 1024 // 1024} MB")
    ext = Path(name).suffix.lower()
    att_id = secrets.token_hex(6)
    stored = f"{att_id}{ext}"
    path = _dir() / stored
    path.write_bytes(data)
    try:
        kind, text, extra = _extract(path, ext)
    except AttachmentError:
        path.unlink(missing_ok=True)
        raise
    except Exception as e:
        path.unlink(missing_ok=True)
        raise AttachmentError(f"{name}: could not read file ({e})")
    meta = {"id": att_id, "name": name, "kind": kind, "size": len(data), "stored": stored, **extra}
    return _register(meta, text[:MAX_TEXT])


# ------------------------------------------------------------------ prompt assembly
SAFE_FIELDS = ("id", "name", "kind", "size", "chars", "url", "title", "media_type", "key", "pages")
