"""Optional public scholarly connectors. No authentication, scraping or model calls.

Venue packs use OpenAlex's documented source/works API, not invented venue search APIs.
PDF candidates come only from explicit public repository fields; download.py still validates them.
"""
import re
from urllib.parse import urlparse

from backend.knowledge import websearch as WS


VENUES = {
    "cvf": ["IEEE/CVF Conference on Computer Vision and Pattern Recognition", "IEEE/CVF International Conference on Computer Vision", "IEEE/CVF Winter Conference on Applications of Computer Vision"],
    "pmlr": ["Proceedings of Machine Learning Research"],
    "neurips": ["Advances in Neural Information Processing Systems"],
    "acl_anthology": ["Proceedings of the Annual Meeting of the Association for Computational Linguistics", "Proceedings of the Conference on Empirical Methods in Natural Language Processing", "Transactions of the Association for Computational Linguistics"],
}
DIRECT = {"zenodo": "https://developers.zenodo.org/", "europe_pmc": "https://europepmc.org/RestfulWebService",
          "hal": "https://api.archives-ouvertes.fr/docs/search", "openreview": "https://docs.openreview.net/reference/api-v2/openapi-definition"}
IDS = (*VENUES, *DIRECT)


def catalog():
    return [{"id": name, "mode": "openalex_source_index" if name in VENUES else "public_api",
             "documentation": "https://help.openalex.org/api/filtering/" if name in VENUES else DIRECT[name],
             "coverage": "Indexed source matches only; not a complete proceedings harvest" if name in VENUES else "Public records only; availability and rate limits may vary",
             "live_qualified": False, "paid_llm": False} for name in IDS]


async def _json(url, params):
    from backend.knowledge.sources import _paced
    async with WS._client() as client:
        response = await _paced(urlparse(url).hostname, lambda: client.get(url, params=params))
        response.raise_for_status()
        return response.json()


def _oa(url, provider, license="unknown", version="unknown"):
    if not url or urlparse(url).scheme != "https":
        return []
    return [{"url": url, "provider": provider, "access": "open", "license": license or "unknown", "version": version}]


async def search(name, query, limit, year, cfg):
    if name in VENUES:
        return await venue_search(name, query, limit, year, cfg)
    if name == "zenodo":
        data = await _json("https://zenodo.org/api/records", {"q": query, "size": min(limit, 100), "sort": "bestmatch"})
        out = []
        for hit in data.get("hits", {}).get("hits", []):
            m = hit.get("metadata") or {}; public = m.get("access_right") == "open"
            license = m.get("license") or {}
            if isinstance(license, dict): license = license.get("id", "unknown")
            locations = [loc for f in hit.get("files", []) if public and str(f.get("key", "")).lower().endswith(".pdf")
                         for loc in _oa((f.get("links") or {}).get("self"), "Zenodo", license, "deposited version")]
            out.append({"title": m.get("title"), "authors": [a.get("name", "") for a in m.get("creators", [])],
                        "doi": m.get("doi", ""), "year": str(m.get("publication_date", ""))[:4], "abstract": WS._clean(re.sub(r"<[^>]+>", " ", m.get("description", ""))),
                        "source": "Zenodo", "url": (hit.get("links") or {}).get("html", ""), "oa_locations": locations,
                        "license": license, "publication_type": (m.get("resource_type") or {}).get("type", "unknown")})
        return out
    if name == "europe_pmc":
        data = await _json("https://www.ebi.ac.uk/europepmc/webservices/rest/search", {"query": query, "pageSize": min(limit, 100), "resultType": "core", "format": "json"})
        out = []
        for r in data.get("resultList", {}).get("result", []):
            locations = [loc for f in (r.get("fullTextUrlList") or {}).get("fullTextUrl", [])
                         if r.get("isOpenAccess") == "Y" and f.get("documentStyle") == "pdf" and f.get("availabilityCode") == "OA"
                         for loc in _oa(f.get("url"), "Europe PMC", r.get("license"))]
            out.append({"title": r.get("title"), "doi": r.get("doi", ""), "pmid": r.get("pmid", ""), "year": r.get("pubYear"),
                        "authors": [a.get("fullName", "") for a in (r.get("authorList") or {}).get("author", [])],
                        "abstract": r.get("abstractText", ""), "venue": ((r.get("journalInfo") or {}).get("journal") or {}).get("title", ""),
                        "citations": int(r["citedByCount"]) if str(r.get("citedByCount", "")).isdigit() else None,
                        "source": "Europe PMC", "url": "https://europepmc.org/article/" + str(r.get("source", "MED")) + "/" + str(r.get("id", "")),
                        "flags": ["retracted"] if r.get("isRetracted") == "Y" else [], "oa_locations": locations})
        return out
    if name == "hal":
        fields = "title_s,authFullName_s,doiId_s,producedDateY_i,journalTitle_s,abstract_s,uri_s,fileMain_s,licence_s,docType_s"
        data = await _json("https://api.archives-ouvertes.fr/search/", {"q": query, "fq": f"producedDateY_i:[{year} TO *]", "rows": min(limit, 100), "wt": "json", "fl": fields})
        first = lambda v: v[0] if isinstance(v, list) and v else v
        return [{"title": first(r.get("title_s", "")), "authors": r.get("authFullName_s", []), "doi": first(r.get("doiId_s", "")),
                 "year": r.get("producedDateY_i"), "abstract": first(r.get("abstract_s", "")), "venue": r.get("journalTitle_s", ""),
                 "source": "HAL", "url": r.get("uri_s", ""), "publication_type": r.get("docType_s", "unknown"),
                 "oa_locations": _oa(r.get("fileMain_s"), "HAL", first(r.get("licence_s", "unknown")), "repository deposit")}
                for r in data.get("response", {}).get("docs", [])]
    if name == "openreview":
        data = await _json("https://api2.openreview.net/notes/search", {"term": query, "content": "all", "limit": min(limit, 100)})
        out = []
        for note in data.get("notes", []):
            if "everyone" not in note.get("readers", []) or note.get("ddate"): continue
            content = note.get("content") or {}
            value = lambda k, default="": (content.get(k) or {}).get("value", default)
            # A hidden PDF field is not inferred from the existence of a public note.
            pdf = value("pdf")
            if isinstance(pdf, str) and pdf.startswith("/"): pdf = "https://openreview.net" + pdf
            out.append({"title": value("title"), "authors": value("authors", []), "abstract": value("abstract"), "doi": value("doi"),
                        "source": "OpenReview", "url": "https://openreview.net/forum?id=" + str(note["id"]), "venue": value("venue"),
                        "flags": ["submission"], "peer_review_status": "unverified_submission",
                        "oa_locations": _oa(pdf, "OpenReview", value("license", "unknown"), "public submission")})
        return out
    raise ValueError("Unsupported scholarly source pack")


async def venue_search(name, query, limit, year, cfg):
    """Discover source identities first; an unavailable index yields no invented paper/PDF."""
    auth = {k: v for k, v in {"api_key": cfg.get("openalex_key"), "mailto": cfg.get("mailto")}.items() if v}
    sources = []
    for title in VENUES[name]:
        data = await _json("https://api.openalex.org/sources", {**auth, "search": title, "per-page": 10})
        for source in data.get("results", []):
            # Exact normalized name/alternate-title match prevents selecting an unrelated journal.
            norm = lambda s: re.sub(r"\W", "", s).casefold()
            titles = [source.get("display_name", ""), *(source.get("alternate_titles") or [])]
            if any(norm(t) == norm(title) for t in titles) and re.fullmatch(r"https://openalex.org/S\d+", str(source.get("id", ""))):
                sources.append(source["id"])
    if not sources:
        raise ValueError(f"{name}: no exact OpenAlex source identity found; direct proceedings harvest is unavailable")
    data = await _json("https://api.openalex.org/works", {**auth, "search": query, "per-page": min(limit, 100),
                       "filter": "locations.source.id:" + "|".join(dict.fromkeys(sources)) + f",from_publication_date:{year}-01-01"})
    out = []
    for w in data.get("results", []):
        primary = w.get("primary_location") or {}
        locations = [loc for l in w.get("locations", []) if l.get("is_oa") for loc in _oa(l.get("pdf_url"), "OpenAlex", l.get("license"), l.get("version", "unknown"))]
        out.append({"title": w.get("display_name"), "doi": w.get("doi", ""), "authors": [(a.get("author") or {}).get("display_name", "") for a in w.get("authorships", [])],
                    "year": w.get("publication_year"), "venue": (primary.get("source") or {}).get("display_name", ""),
                    "url": primary.get("landing_page_url") or w.get("id", ""), "abstract": WS._oa_abstract(w.get("abstract_inverted_index")),
                    "citations": w.get("cited_by_count"), "source": "OpenAlex · " + name, "sources": ["OpenAlex", name],
                    "oa_locations": locations, "openalex_id": w.get("id", ""), "references": (w.get("referenced_works") or [])[:2000], "publication_type": w.get("type", "unknown"), "flags": ["retracted"] if w.get("is_retracted") else []})
    return out
