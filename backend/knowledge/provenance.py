"""Artifact provenance (v3.2) — CLAUDE_DEVELOPMENT_PROMPT Task 3 / CUSTOMER_REQUIREMENT scenario 3.

When a run finishes, every artifact inside runs/<run_id>/ is sealed with where it came from:
    PNG   tEXt chunks  phd_run_id, phd_git_sha, phd_clearml_task_id, phd_provenance (JSON)
    JPEG  a COM segment "PHD-PROVENANCE {json}" (inserted after the APPn headers, so JFIF/EXIF stay valid)
    SVG   an XML comment <!-- PHD-PROVENANCE {json} -->
    CSV   first line "# Provenance: run_id=…, git_sha=…, clearml_task_id=…" (read it with pandas.read_csv(comment="#"))
plus runs/<run_id>/provenance.json: sha256 of every sealed file → also finds artifacts whose metadata was stripped
(e.g. re-saved by another program) or formats without metadata (PDF).

Pure Python (zlib + struct) — no Pillow, no native code. Only files inside the run folder are touched (they are the run's
outputs or copies of them); the researcher's source tree code/ is never modified.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
PREFIX = "PHD-PROVENANCE "
SEAL_EXT = {".png", ".jpg", ".jpeg", ".svg", ".csv", ".tsv"}
CSV_RE = re.compile(r"^# Provenance: (.*)$")


class ProvenanceError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record(run_id: str, meta: dict) -> dict:
    git = meta.get("git") or {}
    cm = meta.get("clearml") or {}
    try:
        from backend.core.config import APP_VERSION
    except Exception:
        APP_VERSION = "?"
    return {"run_id": run_id, "git_sha": git.get("sha", ""), "git_dirty": bool(git.get("dirty")), "git_branch": git.get("branch", ""),
            "clearml_task_id": cm.get("task_id", ""), "cmd": (meta.get("cmd") or "")[:300], "sealed": _now(),
            "app": f"PhD Research Lab {APP_VERSION}"}


# ------------------------------------------------------------------ PNG
def _png_chunks(data: bytes):
    if not data.startswith(PNG_SIG):
        raise ProvenanceError("not a PNG file")
    i = 8
    while i + 8 <= len(data):
        (n,) = struct.unpack(">I", data[i:i + 4])
        typ = data[i + 4:i + 8]
        yield typ, data[i + 8:i + 8 + n], data[i:i + 12 + n]
        i += 12 + n
        if typ == b"IEND":
            return
    raise ProvenanceError("truncated PNG")


def _png_chunk(typ: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)


def png_write(data: bytes, rec: dict) -> bytes:
    fields = {"phd_run_id": rec["run_id"], "phd_git_sha": rec["git_sha"], "phd_clearml_task_id": rec["clearml_task_id"],
              "phd_provenance": json.dumps(rec, ensure_ascii=True, sort_keys=True)}
    out = [PNG_SIG]
    for typ, body, raw in _png_chunks(data):
        if typ == b"tEXt" and body.split(b"\x00", 1)[0].startswith(b"phd_"):
            continue  # replace an older seal
        if typ == b"IEND":
            out += [_png_chunk(b"tEXt", k.encode("latin-1") + b"\x00" + str(v).encode("latin-1", "replace")) for k, v in fields.items()]
        out.append(raw)
    return b"".join(out)


def png_read(data: bytes) -> dict:
    found = {}
    for typ, body, _ in _png_chunks(data):
        if typ == b"tEXt" and b"\x00" in body:
            k, v = body.split(b"\x00", 1)
            if k.startswith(b"phd_"):
                found[k.decode("latin-1")] = v.decode("latin-1", "replace")
        elif typ == b"iTXt" and body.startswith(b"phd_") and b"\x00" in body:
            # keyword \0 compression-flag(1 byte) compression-method(1 byte) language \0 translated-keyword \0 text
            key, rest = body.split(b"\x00", 1)
            parts = rest[2:].split(b"\x00", 2)
            if len(rest) >= 2 and len(parts) == 3:
                found[key.decode("latin-1")] = parts[2].decode("utf-8", "replace")
    if "phd_provenance" in found:
        try:
            return json.loads(found["phd_provenance"])
        except ValueError:
            pass
    return {"run_id": found.get("phd_run_id", ""), "git_sha": found.get("phd_git_sha", ""),
            "clearml_task_id": found.get("phd_clearml_task_id", "")} if found else {}


# ------------------------------------------------------------------ JPEG
def _jpeg_segments(data: bytes):
    """(marker, segment bytes incl. marker) up to SOS; then ('rest', remaining bytes)."""
    if not data.startswith(b"\xff\xd8"):
        raise ProvenanceError("not a JPEG file")
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            raise ProvenanceError("corrupt JPEG")
        marker = data[i + 1]
        if marker == 0xDA:  # start of scan: the rest is entropy-coded data
            yield "rest", data[i:]
            return
        (n,) = struct.unpack(">H", data[i + 2:i + 4])
        yield marker, data[i:i + 2 + n]
        i += 2 + n
    raise ProvenanceError("truncated JPEG")


def jpeg_write(data: bytes, rec: dict) -> bytes:
    payload = (PREFIX + json.dumps(rec, ensure_ascii=True, sort_keys=True)).encode("ascii")
    com = b"\xff\xfe" + struct.pack(">H", len(payload) + 2) + payload
    out, inserted = [b"\xff\xd8"], False
    for marker, seg in _jpeg_segments(data):
        if marker == 0xFE and seg[4:4 + len(PREFIX)] == PREFIX.encode():
            continue
        if not inserted and not (isinstance(marker, int) and 0xE0 <= marker <= 0xEF):
            out.append(com)
            inserted = True
        out.append(seg)
    return b"".join(out)


def jpeg_read(data: bytes) -> dict:
    for marker, seg in _jpeg_segments(data):
        if marker == 0xFE and seg[4:4 + len(PREFIX)] == PREFIX.encode():
            try:
                return json.loads(seg[4 + len(PREFIX):].decode("ascii", "replace"))
            except ValueError:
                return {}
    return {}


# ------------------------------------------------------------------ SVG / CSV
SVG_RE = re.compile(r"<!-- PHD-PROVENANCE (\{.*?\}) -->\n?", re.S)


def svg_write(text: str, rec: dict) -> str:
    text = SVG_RE.sub("", text)
    # "--" may not appear in an XML comment; it can only occur inside JSON strings, where "--" decodes back exactly
    c = f"<!-- {PREFIX}{json.dumps(rec, ensure_ascii=True, sort_keys=True).replace('--', '-' + chr(92) + 'u002d')} -->\n"
    m = re.match(r"\s*<\?xml[^>]*\?>\s*", text)
    return text[:m.end()] + c + text[m.end():] if m else c + text


def svg_read(text: str) -> dict:
    m = SVG_RE.search(text)
    try:
        return json.loads(m.group(1)) if m else {}
    except ValueError:
        return {}


def csv_line(rec: dict) -> str:
    return f"# Provenance: run_id={rec['run_id']}, git_sha={rec['git_sha'] or 'none'}, clearml_task_id={rec['clearml_task_id'] or 'none'}"


def csv_write(text: str, rec: dict) -> str:
    first, _, rest = text.partition("\n")
    if CSV_RE.match(first.rstrip("\r")):  # replace an older seal
        text = rest
    return csv_line(rec) + "\n" + text


def csv_read(text: str) -> dict:
    m = CSV_RE.match(text.split("\n", 1)[0].rstrip("\r"))
    if not m:
        return {}
    d = dict(kv.split("=", 1) for kv in [x.strip() for x in m.group(1).split(",")] if "=" in kv)
    return {k: ("" if v == "none" else v) for k, v in d.items()}


# ------------------------------------------------------------------ seal / inspect
def seal_bytes(name: str, data: bytes, rec: dict, csv_header: bool = True) -> bytes | None:
    ext = Path(name).suffix.lower()
    if ext == ".png":
        return png_write(data, rec)
    if ext in (".jpg", ".jpeg"):
        return jpeg_write(data, rec)
    if ext == ".svg":
        return svg_write(data.decode("utf-8", "replace"), rec).encode("utf-8")
    if ext in (".csv", ".tsv") and csv_header:
        return csv_write(data.decode("utf-8", "replace"), rec).encode("utf-8")
    return None


def read_bytes(name: str, data: bytes) -> dict:
    ext = Path(name).suffix.lower()
    try:
        if data.startswith(PNG_SIG):
            return png_read(data)
        if data.startswith(b"\xff\xd8"):
            return jpeg_read(data)
        head = data.lstrip()[:64]
        if ext == ".svg" or head[:5] in (b"<?xml", b"<svg ") or head.startswith(b"<!-- " + PREFIX.encode()):
            return svg_read(data.decode("utf-8", "replace"))
        if ext in (".csv", ".tsv", ".txt"):
            return csv_read(data.decode("utf-8", "replace"))
    except ProvenanceError:
        return {}
    return {}


def seal_run(run_dir: Path, run_id: str, meta: dict, csv_header: bool = True) -> dict:
    """Seal every artifact of one run and write runs/<id>/provenance.json. Returns a short report."""
    rec = record(run_id, meta)
    manifest = {"record": rec, "files": {}}
    errors = []
    for f in sorted(Path(run_dir).rglob("*")):
        if not f.is_file() or f.suffix.lower() not in SEAL_EXT or f.name.endswith(".provenance.json"):
            continue
        rel = str(f.relative_to(run_dir)).replace("\\", "/")
        try:
            data = f.read_bytes()
            new = seal_bytes(f.name, data, rec, csv_header)
            if new is not None and new != data:
                tmp = f.with_name(f.name + ".sealtmp")
                tmp.write_bytes(new)
                tmp.replace(f)
                data = new
            manifest["files"][rel] = sha256(data)
        except Exception as e:  # a malformed image must not break the run record
            errors.append(f"{rel}: {e}")
    (Path(run_dir) / "provenance.json").write_text(json.dumps(manifest, indent=1), "utf-8")
    return {"sealed": len(manifest["files"]), "errors": errors[:10]}
