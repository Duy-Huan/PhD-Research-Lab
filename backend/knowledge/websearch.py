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
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .attachments import html_to_text
from .config import load_config

# Endpoints can be redirected (tests, institutional proxies) with PHDLAB_SEARCH_BASE=http://host:port
_BASE = os.environ.get("PHDLAB_SEARCH_BASE", "").rstrip("/")
EP = {
    "openalex": f"{_BASE}/openalex/works" if _BASE else "https://api.openalex.org/works",
    "arxiv": f"{_BASE}/arxiv" if _BASE else "https://export.arxiv.org/api/query",
    "s2": f"{_BASE}/s2/paper/search" if _BASE else "https://api.semanticscholar.org/graph/v1/paper/search",
    "ddg": f"{_BASE}/ddg" if _BASE else "https://html.duckduckgo.com/html/",
    "tavily": f"{_BASE}/tavily" if _BASE else "https://api.tavily.com/search",
    "brave": f"{_BASE}/brave" if _BASE else "https://api.search.brave.com/res/v1/web/search",
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


async def openalex(q: str, n: int, mailto: str = "", year_from: int | None = None) -> list:
    params = {"search": q, "per-page": n,
              "select": "id,doi,display_name,publication_year,authorships,primary_location,cited_by_count,"
                        "open_access,best_oa_location,abstract_inverted_index,type"}
    if mailto:
        params["mailto"] = mailto
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
        out.append({"kind": "paper", "source": "OpenAlex", "title": _clean(w.get("display_name")),
                    "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])[:8] if a.get("author")],
                    "year": w.get("publication_year"), "venue": _clean(((loc.get("source") or {}) or {}).get("display_name")),
                    "doi": doi, "citations": w.get("cited_by_count"),
                    "url": f"https://doi.org/{doi}" if doi else (loc.get("landing_page_url") or w.get("id")),
                    "pdf_url": best.get("pdf_url") or "", "abstract": _oa_abstract(w.get("abstract_inverted_index"))[:ABSTRACT_CHARS]})
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
        async with _client(12) as c:
            r = await c.get(url)
        ctype = r.headers.get("content-type", "").lower()
        if r.status_code >= 400 or "html" not in ctype:
            return ""
        return html_to_text(r.text[:600_000])[1][:PAGE_CHARS]
    except Exception:
        return ""


# ------------------------------------------------------------------ orchestration
def _key(s: dict) -> str:
    if s.get("doi"):
        return "doi:" + s["doi"].lower()
    return "t:" + re.sub(r"[^a-z0-9]", "", (s.get("title") or s.get("url", "")).lower())[:80]


def _interleave(lists: list) -> list:
    out, seen = [], set()
    for i in range(max((len(x) for x in lists), default=0)):
        for lst in lists:
            if i < len(lst):
                k = _key(lst[i])
                if k in seen:  # keep the richer record (e.g. citation count / pdf from another source)
                    old = next(o for o in out if _key(o) == k)
                    for f in ("pdf_url", "abstract", "citations", "venue", "doi"):
                        if not old.get(f) and lst[i].get(f):
                            old[f] = lst[i][f]
                    continue
                seen.add(k)
                out.append(lst[i])
    return out


async def _safe(name: str, coro, errors: list) -> list:
    try:
        return await coro
    except SearchError as e:
        errors.append(str(e))
    except httpx.HTTPStatusError as e:
        errors.append(f"{name}: HTTP {e.response.status_code}")
    except httpx.HTTPError as e:
        errors.append(f"{name}: {type(e).__name__} (no internet connection?)")
    except Exception as e:  # malformed responses must never break the chat
        errors.append(f"{name}: {type(e).__name__}: {e}")
    return []


async def search(mode: str, paper_queries: list, web_queries: list, n: int | None = None, year_from: int | None = None) -> dict:
    """Run the searches for `mode` (papers | web | both). Returns {sources, errors, queries}."""
    cfg = load_config()["search"]
    n = int(n or cfg.get("n_results") or 8)
    errors, tasks_p, tasks_w = [], [], []
    if mode in ("papers", "both"):
        for q in paper_queries[:3]:
            tasks_p += [_safe("OpenAlex", openalex(q, n, cfg.get("mailto", ""), year_from), errors),
                        _safe("Semantic Scholar", semantic_scholar(q, max(3, n // 2), cfg.get("s2_key", ""), year_from), errors),
                        _safe("arXiv", arxiv(q, max(3, n // 2)), errors)]
    if mode in ("web", "both"):
        eng = cfg.get("web_engine", "duckduckgo")
        for q in web_queries[:3]:
            if eng == "tavily":
                tasks_w.append(_safe("Tavily", tavily(q, n, cfg.get("tavily_key", "")), errors))
            elif eng == "brave":
                tasks_w.append(_safe("Brave", brave(q, n, cfg.get("brave_key", "")), errors))
            else:
                tasks_w.append(_safe("DuckDuckGo", duckduckgo(q, n), errors))
    res = await asyncio.gather(*tasks_p, *tasks_w)
    papers = _interleave(list(res[:len(tasks_p)]))[: n + 4]
    if year_from:
        papers = [p for p in papers if not p.get("year") or p["year"] >= year_from]
    web = _interleave(list(res[len(tasks_p):]))[:n]
    if web and cfg.get("read_pages", True):
        todo = [w for w in web[:3] if not w.get("page")]
        pages = await asyncio.gather(*(read_page(w["url"]) for w in todo))
        for w, t in zip(todo, pages):
            w["page"] = t
    sources = []
    for i, s in enumerate(papers + web):
        s["id"] = f"S{i + 1}"
        sources.append(s)
    return {"sources": sources, "errors": sorted(set(errors)),
            "queries": {"papers": paper_queries[:3] if mode in ("papers", "both") else [],
                        "web": web_queries[:3] if mode in ("web", "both") else []}}


# ------------------------------------------------------------------ query planning (one small AI call)
PLANNER_SYS = """You write search-engine queries for a research assistant. Given the conversation, return ONLY a JSON object:
{"papers": ["..."], "web": ["..."], "year_from": null}
- "papers": 1-3 short English keyword queries for scholarly databases (OpenAlex / arXiv / Semantic Scholar): 3-8 technical terms each, no boolean operators, no quotes.
- "web": 1-2 natural queries for a general web search engine, in the language that will find the best pages (usually English for technical topics; the user's language for local/regional facts).
- "year_from": an integer year if the user asks for recent / latest / since-YEAR work, else null.
Focus on what the LATEST user message needs."""


def heuristic_queries(text: str) -> dict:
    t = re.sub(r"\s+", " ", text).strip()
    return {"papers": [t[:150]], "web": [t[:200]], "year_from": None}


async def plan_queries(call_agent, conversation: str) -> dict:
    """Ask the planner agent for queries; fall back to the raw question if the call fails."""
    last = conversation.rsplit("USER:", 1)[-1]
    try:
        r = await call_agent("web_query", PLANNER_SYS, conversation[-6000:], max_tokens=400, temperature=0.1)
        m = re.search(r"\{.*\}", r["text"], re.S)
        d = json.loads(m.group(0)) if m else {}
        papers = [_clean(q) for q in d.get("papers") or [] if _clean(q)][:3]
        web = [_clean(q) for q in d.get("web") or [] if _clean(q)][:3]
        yf = d.get("year_from")
        yf = int(yf) if isinstance(yf, (int, float, str)) and str(yf).isdigit() and 1900 < int(yf) < 2100 else None
        if papers or web:
            h = heuristic_queries(last)
            return {"papers": papers or h["papers"], "web": web or h["web"], "year_from": yf}
    except Exception:
        pass
    return heuristic_queries(last)


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
    keep = ("id", "kind", "source", "title", "url", "authors", "year", "venue", "doi", "citations", "pdf_url", "snippet")
    out = []
    for s in sources[:30]:
        d = {k: s.get(k) for k in keep if s.get(k) not in (None, "", [])}
        if s.get("abstract"):
            d["snippet"] = s["abstract"][:300]
        out.append(d)
    return out


def safe_pdf_name(title: str, year) -> str:
    stem = re.sub(r"[^\w\- ]+", "", title or "paper").strip()[:80].replace(" ", "_") or "paper"
    return f"{stem}{'_' + str(year) if year else ''}.pdf"
