"""Journal indicators with provenance. OpenAlex statistics are never labelled SJR, JIF or a paper quality score.

SJR/quartiles come only from a SCImago CSV explicitly imported with its ranking year. Unknown remains unknown.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote

from backend.core.config import GLOBAL_DIR

_cache: dict = {}
_lock = threading.RLock()
NOTE = "Journal-level indicators describe the venue, not the quality or correctness of this individual paper."


def _normal(value) -> str:
    return re.sub(r"[\W_]", "", str(value or "").casefold())


def _issns(value) -> set:
    return {x.upper().replace("-", "") for x in re.findall(r"\b\d{4}-?\d{3}[\dXx]\b", str(value or ""))}


def _number(value):
    try:
        n = float(str(value).replace(",", "."))
        return n if math.isfinite(n) and n >= 0 else None
    except (ValueError, TypeError):
        return None


def _path():
    return GLOBAL_DIR / "journal_rankings.json"


def import_scimago(text: str, year: int) -> dict:
    if not 1900 <= year <= datetime.now().year:
        raise ValueError("Supply the ranking year of this SCImago export")
    delim = ";" if text.splitlines() and text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
    rows = []
    for raw in csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=delim):
        r = {_normal(k): str(v or "").strip() for k, v in raw.items()}
        title, issn = r.get("title", ""), sorted(_issns(r.get("issn")))
        q = r.get("sjrbestquartile") or r.get("quartile") or ""
        q = q.upper() if re.fullmatch(r"Q[1-4]", q.upper()) else ""
        sjr = _number(r.get("sjr"))
        if not title or not issn or (not q and sjr is None):
            continue
        sourceid = r.get("sourceid", "")
        rows.append({"title": title, "issn": issn, "quartile": q, "sjr": sjr, "year": year,
                     "categories": r.get("categories", ""), "source": "SCImago (imported CSV)",
                     "source_url": "https://www.scimagojr.com/" + ("journalsearch.php?q=" + sourceid + "&tip=sid" if sourceid.isdigit()
                                                                else "journalrank.php?string=" + quote(title))})
    if not rows:
        raise ValueError("No valid SCImago rows: expected Title, Issn, SJR and/or SJR Best Quartile columns")
    doc = {"year": year, "imported_at": datetime.now(timezone.utc).isoformat(), "records": rows}
    from backend.memory.store import replace_retry
    with _lock:
        tmp = _path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
        replace_retry(tmp, _path())
    return {"year": year, "records": len(rows), "source": "SCImago (imported CSV)"}


def _local_records() -> list:
    try:
        doc = json.loads(_path().read_text("utf-8"))
        return doc.get("records", []) if isinstance(doc, dict) else []
    except (OSError, ValueError):
        return []


def _match(paper: dict, records: list) -> dict:
    ids, venue = _issns(paper.get("issn")), _normal(paper.get("venue"))
    for r in records:
        if ids and ids.intersection(r.get("issn") or []):
            return r
    # Exact name fallback only when there is no conflicting ISSN; no fuzzy journal identity guesses.
    for r in records:
        if venue and venue == _normal(r.get("title")) and not ids:
            return r
    return {}


async def _openalex(paper: dict, cfg: dict) -> dict:
    from backend.knowledge.websearch import _BASE, _client
    sid = str(paper.get("source_id") or "").rsplit("/", 1)[-1]
    ids = sorted(_issns(paper.get("issn")))
    venue = str(paper.get("venue") or "").strip()
    params = {"api_key": cfg["openalex_key"]} if cfg.get("openalex_key") else {}
    base = f"{_BASE}/openalex/sources" if _BASE else "https://api.openalex.org/sources"
    if re.fullmatch(r"S\d+", sid):
        url, identity = base + "/" + sid, sid
    elif ids:
        issn = ids[0][:4] + "-" + ids[0][4:]
        url, identity = base + "/issn:" + issn, issn
    elif venue:
        url, identity = base, venue.casefold()
        params.update(search=venue, **{"per-page": 5})
    else:
        return {}
    hit = _cache.get(identity)
    if hit and time.monotonic() - hit[0] < 86400:
        return hit[1]
    async with _client(8) as c:
        r = await c.get(url, params=params)
    r.raise_for_status()
    doc = r.json()
    if url == base:
        doc = next((r for r in doc.get("results") or [] if _normal(r.get("display_name")) == _normal(venue)), {})
    if doc.get("type") != "journal":
        return {}
    stats = doc.get("summary_stats") or {}
    out = {"source": "OpenAlex", "source_url": doc.get("id", ""), "title": doc.get("display_name", ""),
           "issn": doc.get("issn") or [], "h_index": stats.get("h_index"),
           "two_year_mean_citedness": stats.get("2yr_mean_citedness"), "works_count": doc.get("works_count"),
           "cited_by_count": doc.get("cited_by_count"), "updated_date": doc.get("updated_date"),
           "retrieved_at": datetime.now(timezone.utc).isoformat()}
    with _lock:
        _cache[identity] = (time.monotonic(), out)
        while len(_cache) > 256:
            _cache.pop(next(iter(_cache)))
    return out


async def enrich(papers: list, cfg: dict) -> None:
    records = _local_records()
    gate = asyncio.Semaphore(4)
    lookups = {}

    async def lookup(p):
        # Includes time waiting for a slot: a long result list must never turn journal enrichment into a minute wait.
        async with gate:
            return await _openalex(p, cfg)

    async def one(p):
        venue = p.get("venue") or ""
        if (p.get("publication_type") in ("repository", "conference") or re.search(r"preprint|conference|proceedings", venue, re.I)):
            p["journal_ranking"] = {"status": "not_applicable", "note": "Preprint/conference: journal quartile is not applicable. " + NOTE}
            return
        local = _match(p, records)
        stats, error = {}, ""
        try:
            identity = p.get("source_id") or ",".join(sorted(_issns(p.get("issn")))) or _normal(venue)
            if identity not in lookups:
                lookups[identity] = asyncio.create_task(asyncio.wait_for(lookup(p), timeout=10))
            stats = await lookups[identity]
        except Exception:
            error = "OpenAlex journal metrics unavailable; retry later or check the search API key."
        if stats:
            local = local or _match({"venue": stats["title"], "issn": stats["issn"]}, records)
        p["journal_ranking"] = {**stats, **local, "status": "ranked" if local else "metrics" if stats else "unavailable",
                                "note": NOTE, "lookup_url": "https://www.scimagojr.com/journalrank.php?string=" + quote(venue),
                                "openalex_metrics": stats}
        if not local:
            p["journal_ranking"]["note"] += " SJR/quartile not verified; import the SCImago CSV with its year to display them."
        if error:
            p["journal_ranking"]["error"] = error

    await asyncio.gather(*(one(p) for p in papers))
