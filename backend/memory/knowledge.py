"""Knowledge Memory (CONTEXT_MEMORY.md tier "Knowledge"): durable academic knowledge.

    papers    derived live from the project's reference library (BibTeX key, title, year, abstract) — never copied
    concepts  scientific concepts the researcher curated (name, definition, related bib keys)
    methods   proven methods / reference implementations (name, description, code reference)
"""
from __future__ import annotations

import secrets

from . import mem_dir
from .store import JsonStore, now

_store = JsonStore(lambda: mem_dir() / "knowledge.json", {"concepts": [], "methods": []})
KINDS = {"concept": "concepts", "method": "methods"}


class KnowledgeError(ValueError):
    pass


def load() -> dict:
    return _store.load()


def add(kind: str, name: str, text: str, refs=None, code_ref: str = "") -> dict:
    if kind not in KINDS:
        raise KnowledgeError("kind must be concept or method")
    if not (name or "").strip() or not (text or "").strip():
        raise KnowledgeError("Name and description are required")
    item = {"id": ("K-" if kind == "concept" else "M-") + secrets.token_hex(3), "name": name.strip()[:160], "text": text.strip()[:6000],
            "refs": [str(r)[:80] for r in (refs or []) if str(r).strip()][:20], "code_ref": code_ref[:300], "created": now()}
    _store.update(lambda st: st[KINDS[kind]].append(item))
    return item


def delete(item_id: str) -> None:
    def put(st):
        for k in KINDS.values():
            st[k] = [x for x in st[k] if x["id"] != item_id]
    _store.update(put)


def papers(limit: int = 300) -> list:
    try:
        from ..library import included
        return [{"key": e.get("key", ""), "title": e.get("title", ""), "year": e.get("year", ""), "venue": e.get("venue", ""),
                 "abstract": (e.get("abstract") or "")[:1500], "authors": e.get("authors") or []} for e in included()[:limit]]
    except Exception:
        return []
