"""Page-store: immutable raw snapshots that compressed memories point to (Level Of Detail 7).

Design after General Agentic Memory (GAM, arXiv:2511.18423): the memorizer writes a short *memo* for the agents AND a
*page* {header, content} that keeps the raw material losslessly. Here:
  • only the compressor (the single writer of long-term memory) calls add_page();
  • a page is never modified or deleted by the app — pages/<id>.txt is written once (write isolation);
  • readers (retrieval, compiler, UI) only call get_page()/list_pages().
So a summary can always be expanded back to the exact chat turns / run logs it was made from, even if the original chat
session is later deleted.
"""
from __future__ import annotations

import hashlib
import re
import secrets

from . import mem_dir
from .store import JsonStore, now

_index = JsonStore(lambda: mem_dir() / "pages.json", {"pages": []}, versioned=False)
ID_RE = re.compile(r"^P[0-9a-f]{8}$")


def _dir():
    d = mem_dir() / "pages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_page(kind: str, source: str, span, content: str, header: str = "") -> dict:
    """Store raw `content` once. Identical content from the same source returns the existing page."""
    digest = hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()

    def put(st):
        for p in st["pages"]:
            if p["sha256"] == digest and p["source"] == source:
                return p
        pid = "P" + secrets.token_hex(4)
        while (_dir() / f"{pid}.txt").exists():
            pid = "P" + secrets.token_hex(4)
        with open(_dir() / f"{pid}.txt", "x", encoding="utf-8") as f:  # "x": fails instead of overwriting
            f.write(content)
        page = {"id": pid, "kind": kind, "source": source, "span": span, "header": header[:400], "sha256": digest,
                "chars": len(content), "tokens": (len(content) + 3) // 4, "created": now()}
        st["pages"].append(page)
        return page
    return _index.update(put)


def list_pages(limit: int = 200) -> list:
    return _index.load()["pages"][-limit:]


def get_page(pid: str) -> dict:
    if not ID_RE.match(pid or ""):
        raise ValueError("Invalid page id")
    meta = next((p for p in _index.load()["pages"] if p["id"] == pid), None)
    if not meta:
        raise KeyError(pid)
    f = _dir() / f"{pid}.txt"
    return {**meta, "content": f.read_text("utf-8", errors="replace") if f.exists() else ""}
