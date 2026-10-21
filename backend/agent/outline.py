"""Research outline of a project, built in levels (the first thing a new project asks for):

    1 keywords    từ khoá
    2 topic       chủ đề
    3 direction   chủ đề + định hướng
    4 method      chủ đề + định hướng + phương pháp nghiên cứu
    5 proposal    đề cương nghiên cứu đầy đủ (Markdown)

The researcher can start at any level, type the fields, or attach an existing proposal (PDF, Word .docx, Markdown, text,
LaTeX). The chat (/outline) proposes the next level; a proposal changes the outline only after the researcher accepts
it. Every change keeps the previous version.

    <project>/workspace/outline.json        current outline + versions
    <project>/proposal/<file>               attached files (originals)
    <project>/workspace/outline_text/<id>.txt   extracted text (what the agents read)
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from backend.agent import AIWSError, new_id, now, read_json, write_json

LEVELS = ("keywords", "topic", "direction", "method", "proposal")
LEVEL_LABEL = {"keywords": "Từ khoá", "topic": "Chủ đề", "direction": "Chủ đề + định hướng",
               "method": "Chủ đề + định hướng + phương pháp", "proposal": "Đề cương nghiên cứu"}
ATTACH_EXT = {".pdf", ".docx", ".md", ".markdown", ".txt", ".tex", ".rst"}
MAX_FILE = 40 * 1024 * 1024
LIMITS = {"keywords": 40, "topic": 600, "direction": 4000, "method": 8000, "proposal": 120_000}


def _path() -> Path:
    from backend.core.config import workspace
    return workspace() / "outline.json"


def _empty() -> dict:
    return {"keywords": [], "topic": "", "direction": "", "method": "", "proposal": "", "attachments": [], "versions": [],
            "updated": None}


def get() -> dict:
    d = read_json(_path(), None)
    o = _empty() | (d if isinstance(d, dict) else {})
    o["level"] = level(o)
    o["level_label"] = LEVEL_LABEL[LEVELS[o["level"] - 1]] if o["level"] else ""
    return o


def level(o: dict) -> int:
    """Highest level whose field is filled (0 = nothing yet)."""
    n = 0
    for i, k in enumerate(LEVELS, 1):
        if (o.get(k) if k != "keywords" else [x for x in o.get(k) or [] if x]):
            n = i
    return n


def _clean(patch: dict) -> dict:
    out = {}
    for k, v in (patch or {}).items():
        if k not in LEVELS:
            raise AIWSError(f"Unknown outline field '{k}' (fields: {', '.join(LEVELS)})")
        if k == "keywords":
            items = v if isinstance(v, list) else re.split(r"[,;\n]+", str(v or ""))
            out[k] = list(dict.fromkeys(str(x).strip()[:80] for x in items if str(x).strip()))[:LIMITS[k]]
        else:
            out[k] = str(v or "").strip()[:LIMITS[k]]
    return out


def update(patch: dict, by: str = "researcher", reason: str = "") -> dict:
    p = _clean(patch)
    if not p:
        raise AIWSError("Nothing to change")
    o = get()
    snap = {k: o[k] for k in LEVELS}
    o["versions"] = (o.get("versions") or [])[-29:] + [{"ts": now(), "by": by, "reason": reason[:200], "outline": snap}]
    o.update(p)
    o["updated"] = now()
    o.pop("level", None)
    o.pop("level_label", None)
    write_json(_path(), o)
    goals = [x for x in (o["topic"], o["direction"]) if x]
    if goals or o["method"]:  # the outline is the project's long-term goal for every agent (memory tier 3)
        from backend.memory import set_tier3
        set_tier3({"goals": goals, "notes": o["method"]} if o["method"] else {"goals": goals})
    from backend.core import bus
    bus.publish("outline.updated", fields=sorted(p), by=by)
    return get()


def restore(index: int) -> dict:
    o = get()
    vs = o.get("versions") or []
    if not -len(vs) <= index < len(vs):
        raise AIWSError("No such version")
    return update(vs[index]["outline"], "researcher", f"restore version {index}")


# ------------------------------------------------------------------ attachments
def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        from backend.knowledge.library import first_pages_text
        return first_pages_text(path, 60, 200_000)
    if ext == ".docx":
        try:
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
        except (zipfile.BadZipFile, KeyError, OSError) as e:
            raise AIWSError(f"Cannot read the Word file: {e}")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<w:tab/>", "\t", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        import html
        return re.sub(r"\n{3,}", "\n\n", html.unescape(text)).strip()
    return path.read_text("utf-8", "replace")


def attach(filename: str, data: bytes) -> dict:
    name = re.sub(r"[^\w.\- ]", "_", Path(filename or "").name).strip() or "proposal.txt"
    ext = Path(name).suffix.lower()
    if ext not in ATTACH_EXT:
        raise AIWSError(f"Attach PDF, Word (.docx), Markdown, text or LaTeX — not {ext or 'this file type'}")
    if not data:
        raise AIWSError("The file is empty")
    if len(data) > MAX_FILE:
        raise AIWSError("File larger than 40 MB")
    from backend.core.config import data_dir, workspace
    d = data_dir() / "proposal"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    i = 1
    while f.exists():
        f = d / f"{Path(name).stem}-{i}{ext}"
        i += 1
    f.write_bytes(data)
    text = extract_text(f)
    aid = new_id("att", 4)
    tdir = workspace() / "outline_text"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / f"{aid}.txt").write_text(text, "utf-8")
    a = {"id": aid, "name": f.name, "kind": ext.lstrip("."), "bytes": len(data), "chars": len(text),
         "path": f"proposal/{f.name}", "added": now(), "preview": text[:400]}
    o = get()
    o["attachments"] = (o.get("attachments") or []) + [a]
    o.pop("level", None)
    o.pop("level_label", None)
    write_json(_path(), o)
    from backend.core import bus
    bus.publish("outline.attached", name=f.name)
    return a


def attachment_text(aid: str) -> str:
    from backend.core.config import workspace
    if not re.fullmatch(r"att-[0-9a-f]{8}", aid or ""):
        raise AIWSError("Invalid attachment id")
    f = workspace() / "outline_text" / f"{aid}.txt"
    if not f.exists():
        raise AIWSError("Attachment not found")
    return f.read_text("utf-8", "replace")


def remove_attachment(aid: str) -> dict:
    o = get()
    a = next((x for x in o.get("attachments") or [] if x["id"] == aid), None)
    if not a:
        raise AIWSError("Attachment not found")
    o["attachments"] = [x for x in o["attachments"] if x["id"] != aid]
    o.pop("level", None)
    o.pop("level_label", None)
    write_json(_path(), o)
    return {"removed": aid}


def brief(max_chars: int = 6000) -> str:
    """The outline as context for the agents (shared by every conversation and every provider)."""
    o = get()
    if not o["level"] and not o["attachments"]:
        return "## Research outline\n(not written yet — the researcher can start with keywords, a topic or attach a proposal)"
    parts = [f"## Research outline (level {o['level']}/5 · {o['level_label']})"]
    if o["keywords"]:
        parts.append("Keywords: " + ", ".join(o["keywords"]))
    for k in ("topic", "direction", "method"):
        if o[k]:
            parts.append(f"{LEVEL_LABEL[k]}: {o[k]}")
    if o["proposal"]:
        parts.append("Proposal:\n" + o["proposal"][:max_chars // 2])
    for a in o["attachments"][-3:]:
        try:
            parts.append(f"Attached {a['name']} (excerpt):\n" + attachment_text(a["id"])[:max_chars // 4])
        except AIWSError:
            continue
    return "\n".join(parts)[:max_chars]
