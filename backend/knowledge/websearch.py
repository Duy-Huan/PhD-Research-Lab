"""Internet search for the AI agents (v2.6).

Scholarly sources (free, no key needed): OpenAlex, arXiv, Semantic Scholar (optional key).
General web: DuckDuckGo (free, no key), or Tavily / Brave Search with your own API key.

Results are REAL metadata from these services — the AI only reads and cites them, it never invents a source.
Each search returns numbered sources [S1], [S2] … that the agent cites as Markdown links.
Nothing about your project is sent anywhere except the search queries themselves.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from defusedxml import ElementTree as ET
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx

from backend.knowledge.attachments import html_to_text
from backend.core.config import load_config

# Endpoints can be redirected (tests, institutional proxies) with PHDLAB_SEARCH_BASE=http://host:port
_BASE = os.environ.get("PHDLAB_SEARCH_BASE", "").rstrip("/")
EP = {
    "openalex": f"{_BASE}/openalex/works" if _BASE else "https://api.openalex.org/works",
    "arxiv": f"{_BASE}/arxiv" if _BASE else "https://export.arxiv.org/api/query",
    "s2": f"{_BASE}/s2/paper/search" if _BASE else "https://api.semanticscholar.org/graph/v1/paper/search",
    "ddg": f"{_BASE}/ddg" if _BASE else "https://html.duckduckgo.com/html/",
    "tavily": f"{_BASE}/tavily" if _BASE else "https://api.tavily.com/search",
    "brave": f"{_BASE}/brave" if _BASE else "https://api.search.brave.com/res/v1/web/search",
    "ieee": f"{_BASE}/ieee" if _BASE else "https://ieeexploreapi.ieee.org/api/v1/search/articles",
    "scholar": f"{_BASE}/scholar" if _BASE else "https://serpapi.com/search.json",
}
UA = "Mozilla/5.0 (X11; Linux x86_64) PhD-Research-Lab/2.6 (+local research assistant)"
MODES = ("off", "papers", "web", "both")
PAGE_CHARS = 3500
ABSTRACT_CHARS = 1200


class SearchError(Exception):
    pass


def _client(timeout: float = 15) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": UA})


def _clean(t) -> str:
    return re.sub(r"\s+", " ", str(t or "")).strip()


# ------------------------------------------------------------------ scholarly sources
def _oa_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = sorted((p, w) for w, ps in inv.items() for p in ps)
    return " ".join(w for _, w in pos)


async def openalex(q: str, n: int, mailto: str = "", year_from: int | None = None, key: str = "") -> list:
    params = {"search": q, "per-page": n,
              "select": "id,doi,display_name,publication_year,authorships,primary_location,cited_by_count,"
                        "open_access,best_oa_location,abstract_inverted_index,type"}
    if mailto:
        params["mailto"] = mailto
    if key:
        params["api_key"] = key
    if year_from:
        params["filter"] = f"from_publication_date:{year_from}-01-01"
    async with _client() as c:
        r = await c.get(EP["openalex"], params=params)
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []):
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        loc = w.get("primary_location") or {}
        best = w.get("best_oa_location") or {}
        venue = loc.get("source") or {}
        out.append({"kind": "paper", "source": "OpenAlex", "title": _clean(w.get("display_name")),
                    "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])[:8] if a.get("author")],
                    "year": w.get("publication_year"), "venue": _clean(((loc.get("source") or {}) or {}).get("display_name")),
                    "doi": doi, "citations": w.get("cited_by_count"),
                    "url": f"https://doi.org/{doi}" if doi else (loc.get("landing_page_url") or w.get("id")),
                    "pdf_url": best.get("pdf_url") or "", "abstract": _oa_abstract(w.get("abstract_inverted_index"))[:ABSTRACT_CHARS]})
        out[-1].update(source_id=venue.get("id", ""), issn=venue.get("issn") or [], publication_type=venue.get("type", ""))
        out[-1]["flags"] = ["retracted"] if w.get("is_retracted") else []
        out[-1]["openalex_id"] = w.get("id", "")
        out[-1]["references"] = (w.get("referenced_works") or [])[:2000]
        out[-1]["oa_locations"] = [{"url": l["pdf_url"], "provider": "OpenAlex", "access": "open",
                                    "license": l.get("license") or "unknown", "version": l.get("version") or "unknown"}
                                   for l in w.get("locations") or [] if l.get("is_oa") and l.get("pdf_url")]
    return out


async def ieee(q: str, n: int, key: str, year_from: int | None = None) -> list:
    """IEEE's metadata API; a subscription-only PDF is never presented as open access."""
    params = {"apikey": key, "querytext": q, "max_records": min(n, 30), "format": "json"}
    if year_from:
        params["start_year"] = year_from
    async with _client() as c:
        r = await c.get(EP["ieee"], params=params)
    r.raise_for_status()
    data = r.json()
    if data.get("error") or data.get("errors"):
        raise SearchError("IEEE Xplore rejected the search; check the API key and quota")
    out = []
    for p in data.get("articles") or []:
        typ = str(p.get("content_type") or "").lower()
        out.append({"kind": "paper", "source": "IEEE Xplore", "title": _clean(p.get("title")),
                    "authors": [a.get("full_name", "") for a in (p.get("authors") or {}).get("authors", [])],
                    "year": _year(p.get("publication_year")), "venue": _clean(p.get("publication_title")),
                    "doi": p.get("doi", ""), "url": p.get("abstract_url") or f"https://doi.org/{p.get('doi', '')}",
                    "pdf_url": p.get("pdf_url", "") if p.get("access_type", p.get("accessType")) in ("Open Access", "Ephemera") else "",
                    "abstract": _clean(p.get("abstract"))[:ABSTRACT_CHARS], "issn": [p["issn"]] if p.get("issn") else [],
                    "publication_type": "conference" if "conference" in typ else "journal" if "journal" in typ else ""})
    return out


def _year(value) -> int | None:
    match = re.search(r"\b(?:19|20)\d{2}\b", str(value or ""))
    return int(match[0]) if match else None


async def google_scholar(q: str, n: int, key: str, year_from: int | None = None) -> list:
    """Google Scholar records through SerpAPI (requires the researcher's key)."""
    params = {"engine": "google_scholar", "q": q, "api_key": key, "num": min(n, 20)}
    if year_from:
        params["as_ylo"] = year_from
    async with _client(25) as c:
        r = await c.get(EP["scholar"], params=params)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise SearchError("Google Scholar / SerpAPI rejected the search; check the API key and quota")
    out = []
    for p in data.get("organic_results") or []:
        info = p.get("publication_info") or {}
        out.append({"kind": "paper", "source": "Google Scholar", "title": _clean(p.get("title")),
                    "authors": [a.get("name", "") for a in info.get("authors") or []],
                    "year": _year(info.get("summary")), "venue": "", "publication_info": info.get("summary", ""),
                    "url": p.get("link", ""), "pdf_url": next((a.get("link", "") for a in p.get("resources") or []
                                                                              if a.get("file_format") == "PDF"), ""),
                    "citations": ((p.get("inline_links") or {}).get("cited_by") or {}).get("total"),
                    "abstract": _clean(p.get("snippet"))[:ABSTRACT_CHARS]})
    return out


async def arxiv(q: str, n: int) -> list:
    query = " AND ".join(f"all:{t}" for t in re.findall(r"[\w\-]+", q)[:8]) or q
    async with _client() as c:
        r = await c.get(EP["arxiv"], params={"search_query": query, "start": 0, "max_results": n, "sortBy": "relevance"})
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    out = []
    for e in ET.fromstring(r.text).findall("a:entry", ns):
        abs_url = _clean(e.findtext("a:id", "", ns))
        pdf = next((l.get("href") for l in e.findall("a:link", ns) if l.get("title") == "pdf"), "")
        doi = _clean(e.findtext("arxiv:doi", "", ns))
        out.append({"kind": "paper", "source": "arXiv", "title": _clean(e.findtext("a:title", "", ns)),
                    "authors": [_clean(a.findtext("a:name", "", ns)) for a in e.findall("a:author", ns)][:8],
                    "year": int((e.findtext("a:published", "", ns) or "0000")[:4] or 0) or None,
                    "venue": "arXiv preprint", "doi": doi, "citations": None, "url": abs_url,
                    "pdf_url": pdf.replace("http://", "https://") if pdf else "",
                    "abstract": _clean(e.findtext("a:summary", "", ns))[:ABSTRACT_CHARS]})
    return out


async def semantic_scholar(q: str, n: int, key: str = "", year_from: int | None = None) -> list:
    params = {"query": q, "limit": n, "fields": "title,abstract,year,venue,authors,citationCount,externalIds,openAccessPdf,url"}
    if year_from:
        params["year"] = f"{year_from}-"
    async with _client() as c:
        r = await c.get(EP["s2"], params=params, headers={"x-api-key": key} if key else {})
    if r.status_code == 429:
        raise SearchError("Semantic Scholar rate limit (add a free API key in settings for more)")
    r.raise_for_status()
    out = []
    for p in r.json().get("data", []) or []:
        doi = (p.get("externalIds") or {}).get("DOI", "")
        out.append({"kind": "paper", "source": "Semantic Scholar", "title": _clean(p.get("title")),
                    "authors": [a.get("name", "") for a in (p.get("authors") or [])[:8]], "year": p.get("year"),
                    "venue": _clean(p.get("venue")), "doi": doi, "citations": p.get("citationCount"),
                    "url": f"https://doi.org/{doi}" if doi else p.get("url", ""),
                    "pdf_url": ((p.get("openAccessPdf") or {}) or {}).get("url", "") or "",
                    "abstract": _clean(p.get("abstract"))[:ABSTRACT_CHARS]})
        out[-1]["arxiv_id"] = (p.get("externalIds") or {}).get("ArXiv", "")
        out[-1]["pmid"] = (p.get("externalIds") or {}).get("PubMed", "")
    return out


# ------------------------------------------------------------------ general web
async def duckduckgo(q: str, n: int) -> list:
    async with _client() as c:
        r = await c.post(EP["ddg"], data={"q": q, "kl": "wt-wt"})
    r.raise_for_status()
    html = r.text
    out = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|$)', html, re.S):
        href, title, rest = m.group(1), m.group(2), m.group(3)
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href if href.startswith("http") else "https:" + href).query).get("uddg", [href])[0])
        if href.startswith("//"):
            href = "https:" + href
        if "duckduckgo.com/y.js" in href:  # ads
            continue
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
        out.append({"kind": "web", "source": "DuckDuckGo", "title": _clean(re.sub("<[^>]+>", "", title)), "url": href,
                    "snippet": _clean(re.sub("<[^>]+>", "", sn.group(1))) if sn else ""})
        if len(out) >= n:
            break
    if not out and "anomaly" in html.lower():
        raise SearchError("DuckDuckGo temporarily blocked automated searches — try again later or use Tavily / Brave")
    return out


async def tavily(q: str, n: int, key: str) -> list:
    if not key:
        raise SearchError("Tavily selected but no API key set (sidebar → 🌐 Internet search)")
    async with _client(25) as c:
        r = await c.post(EP["tavily"], json={"api_key": key, "query": q, "max_results": n, "search_depth": "basic"})
    if r.status_code in (401, 403):
        raise SearchError("Tavily rejected the API key")
    r.raise_for_status()
    return [{"kind": "web", "source": "Tavily", "title": _clean(x.get("title")), "url": x.get("url", ""),
             "snippet": _clean(x.get("content"))[:600], "page": _clean(x.get("content"))[:PAGE_CHARS]} for x in r.json().get("results", [])]


async def brave(q: str, n: int, key: str) -> list:
    if not key:
        raise SearchError("Brave Search selected but no API key set (sidebar → 🌐 Internet search)")
    async with _client() as c:
        r = await c.get(EP["brave"], params={"q": q, "count": n}, headers={"X-Subscription-Token": key, "Accept": "application/json"})
    if r.status_code in (401, 403, 422):
        raise SearchError("Brave Search rejected the API key")
    r.raise_for_status()
    return [{"kind": "web", "source": "Brave", "title": _clean(x.get("title")), "url": x.get("url", ""),
             "snippet": _clean(re.sub("<[^>]+>", "", x.get("description", "")))} for x in (r.json().get("web") or {}).get("results", [])[:n]]


async def read_page(url: str) -> str:
    try:
        return await asyncio.wait_for(_read_page(url), timeout=15)
    except Exception:
        return ""


async def _read_page(url: str) -> str:
    from urllib.parse import urljoin
    from backend.knowledge.download import public_url
    async with _client(12) as c:
        for _ in range(4):
            await public_url(url)
            async with c.stream("GET", url, follow_redirects=False) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code >= 400 or "html" not in r.headers.get("content-type", "").lower():
                    return ""
                raw = bytearray()
                async for chunk in r.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 600_000:
                        break
                return html_to_text(raw[:600_000].decode(r.encoding or "utf-8", "replace"))[1][:PAGE_CHARS]
    return ""


# ------------------------------------------------------------------ orchestration
def _key(s: dict) -> str:
    if s.get("doi"):
        return "doi:" + re.sub(r"^https?://(?:dx\.)?doi.org/", "", s["doi"].strip().lower())
    return "t:" + re.sub(r"[\W_]", "", (s.get("title") or s.get("url", "")).casefold())


def _interleave(lists: list) -> list:
    out, seen = [], {}
    for i in range(max((len(x) for x in lists), default=0)):
        for lst in lists:
            if i < len(lst):
                item = lst[i]
                k = _key(item)
                title = "t:" + re.sub(r"[\W_]", "", (item.get("title") or item.get("url", "")).casefold())
                old = seen.get(k) or seen.get(title)
                if old and old.get("doi") and item.get("doi") and _key(old) != k:
                    old = None
                if old:
                    if (old.get("publication_type") == "repository" or re.search(r"preprint", old.get("venue", ""), re.I)) \
                            and item.get("publication_type") in ("journal", "conference"):
                        for f in ("venue", "publication_type", "source_id", "issn"):
                            if item.get(f):
                                old[f] = item[f]
                    for f in ("pdf_url", "abstract", "citations", "venue", "doi", "authors", "year", "source_id", "issn", "publication_type"):
                        if old.get(f) in (None, "", []) and item.get(f) not in (None, "", []):
                            old[f] = item[f]
                    old["sources"] = list(dict.fromkeys(old["sources"] + [item.get("source", "")]))
                    seen[k] = old
                    continue
                rec = {**item, "sources": [item.get("source", "")]}
                seen[k] = seen[title] = rec
                out.append(rec)
    return out


async def _safe(name: str, coro, errors: list) -> list:
    try:
        return await coro
    except SearchError as e:
        errors.append(str(e))
    except httpx.HTTPStatusError as e:
        errors.append(f"{name}: HTTP {e.response.status_code}")
    except httpx.TimeoutException:
        errors.append(f"{name}: timed out; other sources are still shown. Retry this source later.")
    except httpx.HTTPError as e:
        errors.append(f"{name}: {type(e).__name__} (no internet connection?)")
    except Exception as e:  # malformed responses must never break the chat
        errors.append(f"{name}: {type(e).__name__}: {e}")
    return []


async def web_query(q: str, n: int, cfg: dict) -> list:
    eng = cfg.get("web_engine", "duckduckgo")
    if eng == "tavily":
        return await tavily(q, n, cfg.get("tavily_key", ""))
    if eng == "brave":
        return await brave(q, n, cfg.get("brave_key", ""))
    return await duckduckgo(q, n)


async def ieee_discovery(q: str, n: int, cfg: dict) -> list:
    """Publisher-domain discovery when no IEEE API key was provided. Do not infer unknown metadata."""
    items = await web_query("site:ieeexplore.ieee.org/document/ " + q, n, cfg)
    return [{**s, "kind": "paper", "source": "IEEE Xplore (web discovery)", "abstract": s.get("snippet", "")}
            for s in items if (urlparse(s.get("url", "")).hostname or "").lower() == "ieeexplore.ieee.org"
            and re.match(r"/(?:abstract/)?document/\d+", urlparse(s.get("url", "")).path)]


async def arxiv_search(q: str, n: int, cfg: dict, errors: list) -> list:
    results = await _safe("arXiv", arxiv(q, n), errors)
    if results:
        return results
    items = await _safe("arXiv web discovery", web_query("site:arxiv.org/abs/ " + q, n, cfg), errors)
    out = []
    for item in items:
        url = urlparse(item.get("url", ""))
        if url.hostname not in ("arxiv.org", "www.arxiv.org") or not url.path.startswith("/abs/") or len(url.path) <= 5:
            continue
        out.append({**item, "kind": "paper", "source": "arXiv (web discovery)", "venue": "arXiv preprint",
                    "publication_type": "repository", "pdf_url": "https://arxiv.org/pdf/" + url.path[5:],
                    "abstract": item.get("snippet", "")})
    return out


async def search(mode: str, paper_queries: list, web_queries: list, n: int | None = None, year_from: int | None = None) -> dict:
    """Run the searches for `mode` (papers | web | both). Returns {sources, errors, queries}."""
    cfg = load_config()["search"]
    n = max(1, min(30, int(n or cfg.get("n_results") or 8)))
    errors, tasks_p, tasks_w = [], [], []
    if mode in ("papers", "both"):
        for q in paper_queries[:3]:
            tasks_p += [_safe("OpenAlex", openalex(q, n, cfg.get("mailto", ""), year_from, cfg.get("openalex_key", "")), errors),
                        _safe("Semantic Scholar", semantic_scholar(q, max(3, n // 2), cfg.get("s2_key", ""), year_from), errors),
                        arxiv_search(q, max(3, n // 2), cfg, errors),
                        _safe("IEEE Xplore", ieee(q, n, cfg["ieee_key"], year_from) if cfg.get("ieee_key")
                              else ieee_discovery(q, max(3, n // 2), cfg), errors)]
            if cfg.get("serpapi_key"):
                tasks_p.append(_safe("Google Scholar", google_scholar(q, n, cfg["serpapi_key"], year_from), errors))
    if mode in ("web", "both"):
        for q in web_queries[:3]:
            tasks_w.append(_safe("Web search", web_query(q, n, cfg), errors))
    res = await asyncio.gather(*tasks_p, *tasks_w)
    papers = _interleave(list(res[:len(tasks_p)]))
    if year_from:
        papers = [p for p in papers if not p.get("year") or p["year"] >= year_from]
    papers = papers[:n + 4]
    web = _interleave(list(res[len(tasks_p):]))[:n]
    if web and cfg.get("read_pages", True):
        todo = [w for w in web[:3] if not w.get("page")]
        pages = await asyncio.gather(*(read_page(w["url"]) for w in todo))
        for w, t in zip(todo, pages):
            w["page"] = t
    sources = []
    ordered = papers + web
    if len(ordered) > 30:
        ordered = (papers[:24] + web[:6]) if web and papers else ordered[:30]
    for i, s in enumerate(ordered):
        s["id"] = f"S{i + 1}"
        sources.append(s)
    if papers:
        from backend.knowledge.ranking import enrich
        await enrich([s for s in sources if s["kind"] == "paper"], cfg)
    return {"sources": sources, "errors": sorted(set(errors)),
            "provider_status": {"google_scholar": "configured" if cfg.get("serpapi_key") else "requires_serpapi_key",
                                "ieee": "api" if cfg.get("ieee_key") else "web_discovery"},
            "search_links": {"google_scholar": "https://scholar.google.com/scholar?q=" + quote(" ".join(paper_queries[:1])),
                             "ieee": "https://ieeexplore.ieee.org/search/searchresult.jsp?queryText=" + quote(" ".join(paper_queries[:1]))},
            "queries": {"papers": paper_queries[:3] if mode in ("papers", "both") else [],
                        "web": web_queries[:3] if mode in ("web", "both") else []}}


# ------------------------------------------------------------------ query planning (one small AI call)
PLANNER_SYS = """You write search-engine queries for a research assistant. Given the conversation, return ONLY a JSON object:
{"papers": ["..."], "web": ["..."], "year_from": null}
- "papers": 1-3 short English keyword queries for scholarly databases (OpenAlex / arXiv / Semantic Scholar): 3-8 technical terms each, no boolean operators, no quotes.
- "web": 1-2 natural queries for a general web search engine, in the language that will find the best pages (usually English for technical topics; the user's language for local/regional facts).
- "year_from": an integer year if the user asks for recent / latest / since-YEAR work, else null.
Focus on what the LATEST user message needs."""


# ------------------------------------------------------------------ prompt blocks & storage
def sources_block(sources: list) -> str:
    lines = []
    for s in sources:
        if s["kind"] == "paper":
            au = ", ".join(s.get("authors") or [])[:160]
            meta = " · ".join(str(x) for x in (au, s.get("year"), s.get("venue"),
                                                f"cited by {s['citations']}" if s.get("citations") is not None else "") if x)
            body = s.get("abstract") or "(no abstract available)"
            lines.append(f"[{s['id']}] PAPER: {s['title']}\n{meta}\nURL: {s['url']}\nAbstract: {body}")
        else:
            body = s.get("page") or s.get("snippet") or ""
            lines.append(f"[{s['id']}] WEB PAGE: {s['title']}\nURL: {s['url']}\nContent: {body}")
    return "\n\n".join(lines)


WEB_RULES = """

# INTERNET SEARCH RESULTS (retrieved just now for the latest question)
These numbered sources come from real search engines and scholarly databases (OpenAlex, arXiv, Semantic Scholar, web search).
- Use them for up-to-date facts and recent literature; prefer them over your memory when they disagree, and say so.
- Cite them inline as Markdown links using their number, e.g. [S3](https://...). Cite ONLY sources from this list — never invent papers, authors, numbers or URLs.
- Judge relevance and quality critically: some results may be off-topic, preprints or low-quality pages; ignore irrelevant ones and say when the results do not answer the question.
- Paper sources only show the abstract: do not claim details beyond it.
- Local-library papers are still cited as [bib_key].
"""


def compact(sources: list) -> list:
    """What is stored with the chat message (no page text)."""
    keep = ("id", "kind", "source", "sources", "title", "url", "authors", "year", "venue", "doi", "citations", "pdf_url", "snippet",
            "source_id", "issn", "publication_type", "publication_info", "journal_ranking")
    out = []
    for s in sources[:30]:
        d = {k: s.get(k) for k in keep if s.get(k) not in (None, "", [])}
        if s.get("abstract"):
            d["snippet"] = s["abstract"][:300]
        out.append(d)
    return out
