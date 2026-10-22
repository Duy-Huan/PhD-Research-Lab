"""Venue indicators with provenance. OpenAlex statistics are never labelled SJR, JIF or a paper quality score.

SJR/quartiles come only from a SCImago CSV imported with its ranking year — by hand, or automatically when a
scimagojr*.csv appears in the Downloads folder (SCImago's bot protection blocks direct downloads). Conference ranks
(A*, A, B, C) come from the CORE portal export, downloaded and refreshed automatically (config "ranking").
Data lives in <data>/plugins/ranking/. Unknown remains unknown: no fuzzy venue identity guesses.
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


def _dir():
    d = GLOBAL_DIR / "plugins" / "ranking"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path():
    legacy = GLOBAL_DIR / "journal_rankings.json"
    new = _dir() / "scimago.json"
    if legacy.exists() and not new.exists():  # v5.0 location
        from backend.memory.store import replace_retry
        replace_retry(legacy, new)
    return new


def _core_path():
    return _dir() / "core.json"


def import_scimago(text: str, year: int, origin: str = "") -> dict:
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
    doc = {"year": year, "imported_at": datetime.now(timezone.utc).isoformat(), "records": rows, "origin": origin}
    from backend.memory.store import replace_retry
    with _lock:
        tmp = _path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
        replace_retry(tmp, _path())
    with _lock:
        _cache.pop("_records", None)
    return {"year": year, "records": len(rows), "source": "SCImago (imported CSV)"}


# ------------------------------------------------------------------ automatic sources
CORE_URL = "https://portal.core.edu.au/conf-ranks/?search=&by=all&source={source}&sort=arank&page=1&do=Export"
CORE_RANKS = ("A*", "A", "B", "C")


def refresh_core(source: str = "ICORE2026") -> dict:
    """Download the CORE conference ranking export (id, title, acronym, source, rank, …) → plugins/ranking/core.json."""
    import httpx
    if not re.fullmatch(r"[A-Z]*CORE\d{4}|ERA2010", source or ""):
        raise ValueError("CORE source must look like ICORE2026 or CORE2023")
    r = httpx.get(CORE_URL.format(source=source), timeout=60, follow_redirects=True, headers={"User-Agent": "PhD-Research-Lab"})
    r.raise_for_status()
    rows = []
    for row in csv.reader(io.StringIO(r.content.decode("utf-8", errors="replace"))):
        if len(row) < 5 or not row[1].strip():
            continue
        rank = row[4].strip()
        rows.append({"title": row[1].strip(), "acronym": row[2].strip(), "rank": rank if rank in CORE_RANKS else "",
                     "rank_raw": rank, "core_id": row[0].strip(), "source": row[3].strip() or source})
    if len(rows) < 50:
        raise ValueError("The CORE export looks incomplete — try again later")
    doc = {"source": source, "fetched_at": datetime.now(timezone.utc).isoformat(), "records": rows}
    from backend.memory.store import replace_retry
    with _lock:
        tmp = _core_path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
        replace_retry(tmp, _core_path())
        _cache.pop("_core", None)
    return {"source": source, "records": len(rows), "ranked": sum(1 for x in rows if x["rank"])}


def _core() -> dict:
    with _lock:
        try:
            mt = _core_path().stat().st_mtime_ns
        except OSError:
            return {}
        hit = _cache.get("_core")
        if hit and hit[0] == mt:
            return hit[1]
        try:
            doc = json.loads(_core_path().read_text("utf-8"))
        except (OSError, ValueError):
            return {}
        by_acr, by_title = {}, {}
        for r in doc.get("records") or []:
            was = re.findall(r"\(was ([^)]+)\)", r.get("title", ""))
            for a in [r.get("acronym", "")] + [x.strip() for w in was for x in w.split(",")]:
                if a:
                    by_acr.setdefault(a.upper(), r)
            by_title.setdefault(_normal(re.sub(r"\([^)]*\)", "", r.get("title", ""))), r)
        out = {"doc": doc, "acr": by_acr, "title": by_title}
        _cache["_core"] = (mt, out)
        return out


def _core_url(c: dict) -> str:
    return f"https://portal.core.edu.au/conf-ranks/{c['core_id']}/" if str(c.get("core_id", "")).isdigit() else ""


def match_core(venue: str) -> dict:
    """CORE record of a conference venue string: its normalised full title contained in the venue, or a standalone
    upper-case acronym token of at least 3 characters ('CVPR 2025', 'Proc. ICCV'). No fuzzy matching."""
    idx = _core()
    if not idx or not venue:
        return {}
    nv = _normal(venue)
    best = None
    for t, r in idx["title"].items():
        if len(t) >= 12 and t in nv and (not best or len(t) > len(_normal(best["title"]))):
            best = r
    if best:
        return best
    for tok in re.findall(r"(?<![A-Za-z])([A-Za-z][A-Za-z0-9]{2,11})(?![A-Za-z])", venue):
        if sum(ch.isupper() for ch in tok) >= 2 and tok.upper() in idx["acr"]:  # CVPR, NeurIPS — never plain words
            return idx["acr"][tok.upper()]
    return {}


def _downloads() -> list:
    import os
    from pathlib import Path
    d = Path(os.environ.get("PHDLAB_DOWNLOADS") or Path(os.environ.get("USERPROFILE") or Path.home()) / "Downloads")
    if not d.is_dir():
        return []
    return sorted((f for f in d.glob("scimagojr*.csv") if f.is_file()), key=lambda f: f.stat().st_mtime, reverse=True)


def scan_downloads() -> dict:
    """Import the newest scimagojr*.csv from Downloads when it differs from the last import (year from its name)."""
    files = _downloads()
    if not files:
        return {"imported": False}
    f = files[0]
    origin = f"{f.name}:{f.stat().st_mtime_ns}"
    try:
        cur = json.loads(_path().read_text("utf-8"))
    except (OSError, ValueError):
        cur = {}
    if cur.get("origin") == origin:
        return {"imported": False, "file": f.name}
    m = re.search(r"(?:19|20)\d{2}", f.name)
    year = min(int(m.group(0)) if m else datetime.now().year - 1, datetime.now().year)
    raw = f.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    return {"imported": True, "file": f.name, **import_scimago(text, year, origin=origin)}


def auto_refresh(cfg: dict, force: bool = False) -> dict:
    """Keep the automatic sources fresh (start-up, Settings and the ranking check of the library)."""
    rc = cfg.get("ranking") or {}
    out = {}
    if not rc.get("auto", True) and not force:
        return out
    if rc.get("watch_downloads", True):
        try:
            out["scimago"] = scan_downloads()
        except (OSError, ValueError) as e:
            out["scimago"] = {"error": str(e)[:200]}
    core = _core().get("doc") or {}
    try:
        age = (time.time() - datetime.fromisoformat(core["fetched_at"]).timestamp()) / 86400
    except (KeyError, ValueError, TypeError):
        age = 1e9
    want = rc.get("core_source") or "ICORE2026"
    if force or age > max(1, int(rc.get("refresh_days", 30))) or core.get("source") != want:
        try:
            out["core"] = refresh_core(want)
        except Exception as e:  # offline: keep the previous data
            out["core"] = {"error": str(e)[:200]}
    return out


def status() -> dict:
    try:
        sj = json.loads(_path().read_text("utf-8"))
    except (OSError, ValueError):
        sj = {}
    core = _core().get("doc") or {}
    return {"journals": {"year": sj.get("year"), "records": len(sj.get("records") or []), "imported_at": sj.get("imported_at"),
                         "origin": (sj.get("origin") or "").rsplit(":", 1)[0]},
            "conferences": {"source": core.get("source"), "records": len(core.get("records") or []),
                            "fetched_at": core.get("fetched_at")},
            "downloads": [f.name for f in _downloads()[:3]],
            "scimago_url": "https://www.scimagojr.com/journalrank.php?out=xls"}


def lookup(venue: str = "", issn: str = "") -> dict:
    """Ranking of one venue from local data only (no network): journal SJR/quartile and/or CORE conference rank."""
    out = {"venue": venue}
    j = _match({"venue": venue, "issn": issn}, _local_records())
    if j:
        out["journal"] = {k: j.get(k) for k in ("title", "quartile", "sjr", "year", "categories", "source", "source_url")}
    c = match_core(venue)
    if c:
        out["conference"] = {"title": c["title"], "acronym": c["acronym"], "rank": c["rank"], "rank_raw": c["rank_raw"],
                             "source": "CORE " + c["source"], "source_url": _core_url(c)}
    return out


def rank_entry(e: dict) -> dict:
    """journal_ranking of a library entry from local data (used by the automatic library check)."""
    venue = e.get("venue") or e.get("journal") or e.get("booktitle") or ""
    found = lookup(venue, e.get("issn", ""))
    if "journal" in found:
        j = found["journal"]
        return {**j, "status": "ranked", "note": NOTE}
    if "conference" in found:
        c = found["conference"]
        return {"status": "conference", "core_rank": c["rank"] or c["rank_raw"], "acronym": c["acronym"], "conference": c["title"],
                "source": c["source"], "source_url": c["source_url"], "note": NOTE}
    return {"status": "unavailable", "note": NOTE + " No imported SCImago / CORE record matches this venue.",
            "lookup_url": "https://www.scimagojr.com/journalrank.php?string=" + quote(venue)} if venue else {}


def _local_records() -> list:
    with _lock:
        try:
            mt = _path().stat().st_mtime_ns
        except OSError:
            return []
        hit = _cache.get("_records")
        if hit and hit[0] == mt:
            return hit[1]
        try:
            doc = json.loads(_path().read_text("utf-8"))
            recs = doc.get("records", []) if isinstance(doc, dict) else []
        except (OSError, ValueError):
            return []
        _cache["_records"] = (mt, recs)
        return recs


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
        if (p.get("publication_type") in ("repository", "conference")
                or re.search(r"preprint|conference|proceedings|symposium|workshop", venue, re.I)):
            c = match_core(venue)
            p["journal_ranking"] = {"status": "not_applicable", "note": "Preprint/conference: journal quartile is not applicable. " + NOTE}
            if c:
                p["journal_ranking"].update(status="conference", core_rank=c["rank"] or c["rank_raw"], acronym=c["acronym"],
                                            conference=c["title"], source="CORE " + c["source"], source_url=_core_url(c))
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
