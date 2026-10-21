"""Retrieval Engine (CONTEXT_MEMORY.md §3.1-3.2): Tri-Search → Reciprocal Rank Fusion → Reranker.

    keyword  BM25 over LOD 1-6 text — catches exact identifiers (function names, ClearML task ids, git SHAs, HYPE-ids)
    vector   cosine similarity of embeddings (embeddings.py; neural via Ollama or lexical hashing fallback)
    graph    spreading activation along node links (experiment → hypothesis, episode → run/task, overlay edges)
    fusion   Reciprocal Rank Fusion (k = 60) of the three rankings
    rerank   heuristic (query-term coverage, pinned/locked, recency, status) or an HTTP cross-encoder (bge-reranker served
             by a TEI / Jina / Cohere-compatible /rerank endpoint at memory.rerank_url)

This module only READS memory (write isolation): the only write is the derived embedding cache.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import httpx

from backend.memory.embeddings import get_embedder, similarity, tokenize
from backend.memory.lod import MemoryNode


class BM25:
    def __init__(self, docs: list, k1: float = 1.5, b: float = 0.75, tokenizer=tokenize):
        self.k1, self.b = k1, b
        self.tokenizer = tokenizer
        self.docs = [tokenizer(d) for d in docs]
        self.avg = (sum(len(d) for d in self.docs) / len(self.docs)) if self.docs else 0.0
        df: dict = {}
        for d in self.docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf = []
        for d in self.docs:
            c: dict = {}
            for t in d:
                c[t] = c.get(t, 0) + 1
            self.tf.append(c)

    def scores(self, query: str) -> list:
        q = set(self.tokenizer(query))
        out = []
        for i, d in enumerate(self.docs):
            s, dl = 0.0, len(d) or 1
            for t in q:
                f = self.tf[i].get(t)
                if f:
                    s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1)))
            out.append(s)
        return out


def _rank(scores: dict) -> list:
    """ids ordered by score (desc), ties broken by id → deterministic."""
    return [k for k, v in sorted(scores.items(), key=lambda kv: (-round(kv[1], 9), kv[0])) if v > 0]


def rrf(rankings: list, k: int = 60) -> dict:
    out: dict = {}
    for ranking in rankings:
        for pos, nid in enumerate(ranking):
            out[nid] = out.get(nid, 0.0) + 1.0 / (k + pos + 1)
    return out


def graph_scores(nodes: list, seeds: dict, hops: int = 2, decay: float = 0.5) -> dict:
    """Spreading activation from seed scores over undirected node links."""
    adj: dict = {}
    for n in nodes:
        for l in n.links:
            adj.setdefault(n.id, set()).add(l)
            adj.setdefault(l, set()).add(n.id)
    act = dict(seeds)
    frontier = dict(seeds)
    for _ in range(hops):
        nxt: dict = {}
        for nid, s in frontier.items():
            for nb in adj.get(nid, ()):
                v = s * decay
                if v > nxt.get(nb, 0.0):
                    nxt[nb] = v
        for nb, v in nxt.items():
            act[nb] = max(act.get(nb, 0.0), v)
        frontier = nxt
    ids = {n.id for n in nodes}
    return {k: v for k, v in act.items() if k in ids and k not in seeds}


def _age_days(ts: str) -> float:
    try:
        t = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - t).total_seconds() / 86400)
    except ValueError:
        return 365.0


def heuristic_rerank(query: str, nodes: list, fused: dict) -> dict:
    q = set(tokenize(query))
    out = {}
    for n in nodes:
        if n.id not in fused:
            continue
        toks = set(tokenize(n.text()))
        coverage = len(q & toks) / len(q) if q else 0.0
        exact = 1.0 if any(len(t) >= 5 and t in toks for t in q if any(c.isdigit() for c in t)) else 0.0  # id hit
        s = fused[n.id] * 60  # RRF scaled to ~[0, 3]
        s += 0.8 * coverage + 0.6 * exact
        s += 0.4 if n.pinned else 0.0
        s += 0.3 / (1 + _age_days(n.ts) / 30) if n.ts else 0.0
        s += {"testing": 0.2, "supported": 0.15, "refuted": 0.1, "validated failure": 0.15}.get(n.status, 0.0)
        out[n.id] = s
    return out


def http_rerank(url: str, model: str, query: str, nodes: list, timeout: float = 8) -> dict:
    """bge-reranker (or any cross-encoder) behind a TEI-style or Jina/Cohere-style /rerank endpoint."""
    texts = [n.text()[:2000] for n in nodes]
    r = httpx.post(url, json={"model": model or None, "query": query, "texts": texts, "documents": texts}, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    items = d.get("results", d) if isinstance(d, dict) else d
    out = {}
    for it in items:
        i = it.get("index")
        s = it.get("score", it.get("relevance_score"))
        if isinstance(i, int) and 0 <= i < len(nodes) and isinstance(s, (int, float)):
            out[nodes[i].id] = float(s)
    if not out:
        raise ValueError("reranker returned no scores")
    return out


def search(query: str, nodes: list, cfg: dict, k: int = 24, rerank_pool: int = 40) -> dict:
    """Return {"hits": [{id, score, ranks}], "diagnostics": {...}} for `query` over `nodes` (deterministic)."""
    diag = {"nodes": len(nodes), "query_tokens": len(tokenize(query)), "vector_engine": "–", "reranker": "–"}
    if not nodes:
        return {"hits": [], "diagnostics": diag}
    texts = [n.text() for n in nodes]
    ids = [n.id for n in nodes]
    by_id = {n.id: n for n in nodes}
    rankings, ranks = [], {}

    bm = BM25(texts).scores(query)
    kw = _rank(dict(zip(ids, bm)))
    rankings.append(kw)
    ranks["keyword"] = kw

    emb = get_embedder(cfg)
    try:
        vecs = emb.embed_unit(texts + [query])  # v3.3: unit vectors (sparse for hashing) + in-process cache — same scores
    except Exception as e:  # neural engine failed → the whole call uses the lexical vectors (never mix spaces)
        diag["vector_error"] = f"{type(e).__name__}: {e}"[:200]
        emb.engine, emb.model = "hashing", "hashing"
        vecs = emb.embed_unit(texts + [query])
    diag["vector_engine"] = emb.label
    qv = vecs[-1]
    vs = {nid: similarity(v, qv) for nid, v in zip(ids, vecs[:-1])}
    vec = _rank({k2: v for k2, v in vs.items() if v > 0.05})
    rankings.append(vec)
    ranks["vector"] = vec

    seeds = {nid: 1.0 / (i + 1) for i, nid in enumerate(_rank(rrf([kw[:15], vec[:15]]))[:10])}
    gr = _rank(graph_scores(nodes, seeds))
    rankings.append(gr)
    ranks["graph"] = gr

    fused = rrf(rankings)
    pool = sorted(fused, key=lambda x: (-round(fused[x], 9), x))[:rerank_pool]
    pool_nodes = [by_id[i] for i in pool]
    url = (cfg["memory"].get("rerank_url") or "").strip()
    scores, diag["reranker"] = None, "heuristic"
    if url and pool_nodes:
        try:
            scores = http_rerank(url, cfg["memory"].get("rerank_model", ""), query, pool_nodes)
            diag["reranker"] = f"http:{url}"
        except Exception as e:
            diag["rerank_error"] = f"{type(e).__name__}: {e}"[:200]
    if scores is None:
        scores = heuristic_rerank(query, pool_nodes, fused)
    pos = {name: {nid: i + 1 for i, nid in enumerate(r)} for name, r in ranks.items()}
    hits = [{"id": nid, "score": round(scores.get(nid, 0.0), 6),
             "ranks": {name: pos[name].get(nid) for name in pos}} for nid in pool]
    hits.sort(key=lambda h: (-h["score"], h["id"]))
    return {"hits": hits[:k], "diagnostics": diag}
