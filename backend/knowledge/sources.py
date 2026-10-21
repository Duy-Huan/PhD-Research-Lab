"""Deterministic scholarly discovery reusing existing clients; metadata is never proof of OA."""
from __future__ import annotations

import asyncio
import re
import threading
import time
from urllib.parse import quote

import httpx

from backend.core.config import load_config
from backend.knowledge import websearch as WS

PROVIDER_IDS = ("openalex", "arxiv", "semantic_scholar", "crossref")
_rate_lock = threading.Lock()
_next_request: dict[str, float] = {}


async def _paced(name: str, operation):
    with _rate_lock:
        at = max(time.monotonic(), _next_request.get(name, 0))
        _next_request[name] = at + (3 if name == "arxiv" else 1)
    delay = at - time.monotonic()
    if delay > 0:
        await asyncio.sleep(delay)
    return await operation()


def doi(value) -> str:
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", str(value or "").strip(), flags=re.I).lower()
    return text if re.fullmatch(r"10\.\d{4,9}/\S+", text) else ""


def arxiv_id(value) -> str:
    m = re.search(r"(?:arxiv\.org/(?:abs|pdf)/|^)(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?(?:\.pdf)?$", str(value or ""), re.I)
    return m[1].lower() if m else ""


async def crossref(query: str, n: int, year: int, cfg: dict) -> list:
    params = {"query.bibliographic": query, "rows": min(n, 100), "filter": f"from-pub-date:{year}-01-01"}
    if cfg.get("mailto"):
        params["mailto"] = cfg["mailto"]
    async with WS._client() as client:
        r = await client.get("https://api.crossref.org/works", params=params)
        r.raise_for_status()
    out = []
    for w in r.json().get("message", {}).get("items", []):
        dates = (w.get("published") or w.get("issued") or {}).get("date-parts") or [[]]
        out.append({"title": next(iter(w.get("title") or []), ""), "doi": doi(w.get("DOI")),
                    "authors": [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in w.get("author") or []],
                    "year": dates[0][0] if dates[0] else None, "venue": next(iter(w.get("container-title") or []), ""),
                    "abstract": re.sub(r"<[^>]+>", " ", w.get("abstract") or ""), "url": w.get("URL", ""),
                    "source": "Crossref", "publication_type": w.get("type", ""), "pdf_url": "",
                    "rights_note": "Publisher links are metadata, not open-access permission", "license": w.get("license") or [],
                    "flags": ["expression_of_concern"] if w.get("update-to") else []})
    return out


async def discover(profile: dict) -> dict:
    cfg = load_config()["search"]
    query = " ".join((profile["keywords"] or [profile["title"]]) + profile["synonyms"][:2])[:1000]
    n, year = profile["metadata_limit"], profile["min_year"]
    errors = []
    calls = {
        "openalex": lambda: WS.openalex(query, min(n, 30), cfg.get("mailto", ""), year, cfg.get("openalex_key", "")),
        "arxiv": lambda: WS.arxiv(query, min(n, 30)),
        "semantic_scholar": lambda: WS.semantic_scholar(query, min(n, 30), cfg.get("s2_key", ""), year),
        "crossref": lambda: crossref(query, n, year, cfg),
    }
    results = await asyncio.gather(*(WS._safe(p, _paced(p, calls[p]), errors) for p in profile["sources"]))
    # Do not use title-only merging: distinct works/versions can have the same title.
    records = [batch[i] for i in range(max((len(batch) for batch in results), default=0))
               for batch in results if i < len(batch) and batch[i].get("title")]
    records = [r for r in records if not r.get("year") or int(r["year"]) >= year]
    records = [r for r in records if not any(x.casefold() in (r["title"] + " " + str(r.get("abstract", ""))).casefold()
                                          for x in profile["exclusions"])]
    return {"records": records, "errors": errors, "query": query}


async def resolve_oa(paper: dict) -> list:
    """Only provider-declared OA candidates; Crossref links are deliberately excluded."""
    candidates = list(paper.get("oa_locations") or [])
    identifier = doi(paper.get("doi"))
    cfg = load_config()["search"]
    if identifier and cfg.get("mailto"):
        try:
            async with WS._client() as client:
                r = await client.get("https://api.unpaywall.org/v2/" + quote(identifier, safe=""), params={"email": cfg["mailto"]})
                r.raise_for_status()
            data = r.json()
            if data.get("is_oa"):
                for loc in data.get("oa_locations") or []:
                    if loc.get("url_for_pdf"):
                        candidates.append({"url": loc["url_for_pdf"], "provider": "Unpaywall", "license": loc.get("license") or "unknown",
                                           "version": loc.get("version") or "unknown", "access": "open", "checked_at": data.get("updated")})
        except (httpx.HTTPError, ValueError):
            if not candidates:
                raise ValueError("Unpaywall lookup failed and no other declared OA location is available")
    seen, out = set(), []
    for loc in candidates:
        if loc.get("access") == "open" and loc.get("url") and loc["url"] not in seen:
            seen.add(loc["url"])
            out.append(loc)
    return out
