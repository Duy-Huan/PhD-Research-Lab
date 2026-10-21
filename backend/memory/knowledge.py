"""Knowledge Memory: the project's papers, derived live from the reference library (BibTeX key, title, year, venue,
abstract, authors) — never copied, so the memory can never disagree with the library."""
from __future__ import annotations

import hashlib
import json


def legacy_notes() -> list:
    """Read curated v1-v4 concepts/methods as notes without changing the original store.

    A stable content id makes import safe to retry after a restart; the complete old record stays attached so custom
    fields, BibTeX links and code references survive the change of storage format. These are curated notes, not newly
    verified scientific evidence.
    """
    from backend.memory import mem_dir
    from backend.memory.store import read_retry
    path = mem_dir() / "knowledge.json"
    try:
        payload = json.loads(read_retry(path))
    except (OSError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    out = []
    for kind, plural in (("concept", "concepts"), ("method", "methods")):
        records = payload.get(plural, [])
        if not isinstance(records, list):
            continue
        for item in records:
            if not isinstance(item, dict):
                continue
            raw = json.dumps({"kind": kind, "record": item}, ensure_ascii=False, sort_keys=True)
            nid = "legacy-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
            text = f"{item.get('name') or kind}: {item.get('text') or ''}"
            if item.get("refs"):
                text += "\nReferences: " + json.dumps(item["refs"], ensure_ascii=False)
            if item.get("code_ref"):
                text += "\nCode reference: " + str(item["code_ref"])
            out.append({"id": nid, "tool": "data", "text": text,
                        "source": f"memory/knowledge.json#{item.get('id') or nid}",
                        "ts": item.get("created") or "", "legacy_knowledge": {"kind": kind, "record": item}})
    return out


def papers(limit: int = 20000) -> list:
    """The whole included library (a cut in key order once silently lost every paper whose key sorted late)."""
    from backend.knowledge.library import included
    return [{"key": e.get("key", ""), "title": e.get("title", ""), "year": e.get("year", ""), "venue": e.get("venue", ""),
             "abstract": (e.get("abstract") or "")[:1500], "authors": e.get("authors") or []} for e in included()[:limit]]
