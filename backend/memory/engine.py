"""Research-state-aware hybrid retrieval (v3.3 §5, §8, §13) — the v3.3 front door of Context Memory.

    RetrievalContext   query + role + Research State (objective, active hypothesis, current experiment, constraints,
                       recent decisions, known failures, datasets/models) + metadata filters + temporal mode
          │
          ▼
    six rankings over the cached index (one index per memory fingerprint, cache.py)
        keyword   BM25 of the query                       (exact ids, task ids, SHAs, model names)
        vector    similarity of the query                 (hashing sparse vectors or Ollama embeddings)
        state     BM25 of the research-state query        (active hypothesis, current experiment, datasets, hardware)
        graph     spreading activation from the top hits AND from the state records (hypothesis → experiment → evidence …)
        metadata  nodes whose dataset/model/source_type matches what the query names
        temporal  newest research records, only for "current / latest / best / next" questions
          │  weighted Reciprocal Rank Fusion
          ▼
    explainable scoring (policy.py weights per role):
        relevance + importance + recency + confidence + evidence_strength + research_centrality + failure_prevention
        + task_fit − low_confidence (candidate / AI-originated / rejected / superseded)
    every hit carries its component scores, the rank it got from every source and human-readable reasons
    → "Why was this memory retrieved?" is answered by the hit itself.

Deterministic (stable sort by score then id), read-only (write isolation), cached by (fingerprint, context, settings).
The v3.2 API retrieval.search() is unchanged and still used by older callers.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field

from . import cache
from . import lod as LOD
from . import policy as P
from .embeddings import get_embedder, similarity, stem, stem_tokens, tokenize
from .retrieval import BM25, _age_days, _rank, graph_scores, http_rerank, rrf

SOURCE_WEIGHTS = {"keyword": 1.0, "vector": 1.0, "metadata": 1.0, "intent": 1.0, "graph": 0.8, "state": 0.7, "temporal": 0.5}
# what KIND of record the question asks for → node types (query construction from the question's intent, §13)
INTENTS = (
    (re.compile(r"(?i)\b(papers?|literature|cit(e|es|ed|ation|ations)|references?|publications?|stud(y|ies))\b"), ("paper", "claim")),
    (re.compile(r"(?i)\b(experiments?|runs?|trials?|ablations?|tested|results?)\b"), ("experiment", "evidence")),
    (re.compile(r"(?i)\b(hypothes[ie]s)\b"), ("hypothesis",)),
    (re.compile(r"(?i)\b(fail(s|ed|ure|ures)?|oom|out of memory|crash(es|ed)?|errors?|diverg\w*|nan|broke)\b"), ("failure", "experiment")),
    (re.compile(r"(?i)\b(decid(e|ed)|decisions?|chose|chosen|rejected)\b"), ("decision",)),
    (re.compile(r"(?i)\b(claims?|support(s|ed)?|evidence|prove[sn]?)\b"), ("claim", "evidence")),
    (re.compile(r"(?i)\b(best|psnr|ssim|accuracy|metrics?|scores?|commit|sha|git)\b"), ("experiment", "evidence", "metric")),
    (re.compile(r"(?i)\b(next|should|plan(ning)?|design|propose|try|use|recommend)\b"),
     ("hypothesis", "failure", "decision", "constraint", "experiment")),
)
TEMPORAL_RE = re.compile(r"(?i)\b(current(ly)?|latest|now|recent(ly)?|best|next|active|today|so far|state of)\b")
HISTORY_RE = re.compile(r"(?i)\b(history|previous(ly)?|past|earlier|before|ever|all|why did|tried)\b")
TYPE_IMPORTANCE = {"decision": 0.7, "constraint": 0.7, "hypothesis": 0.6, "failure": 0.6, "claim": 0.6, "evidence": 0.6,
                   "objective": 0.7, "experiment": 0.5, "metric": 0.5, "method": 0.4, "concept": 0.35, "paper": 0.4,
                   "episode": 0.3, "note": 0.4, "assumption": 0.4}
FILTER_KEYS = ("types", "tiers", "dataset", "model", "source_type", "evidence_status", "origin", "since", "until", "ids")


@dataclass
class RetrievalContext:
    query: str
    role: str = "default"
    session_id: str = ""
    filters: dict = field(default_factory=dict)
    temporal: str = "auto"                  # auto | current | history
    state: dict = field(default_factory=dict)
    k: int = 24
    purged: frozenset = frozenset()
    allowed: tuple = ()                     # sensitivity classes allowed out (empty = no filter, local use)

    def state_query(self) -> str:
        s = self.state or {}
        parts = [h["text"] for h in s.get("active_hypotheses", [])[:2]]
        e = s.get("current_experiment") or {}
        parts += [e.get("title", ""), e.get("dataset_version", "")]
        parts += s.get("datasets", [])[:3] + s.get("models", [])[:3] + s.get("hardware", [])[:2]
        return " ".join(p for p in parts if p)

    def temporal_mode(self) -> str:
        if self.temporal in ("current", "history"):
            return self.temporal
        if HISTORY_RE.search(self.query or ""):
            return "history"
        return "current" if TEMPORAL_RE.search(self.query or "") else "neutral"

    def key(self) -> str:
        body = {"q": self.query, "r": self.role, "s": self.session_id, "f": self.filters, "t": self.temporal, "k": self.k,
                "p": sorted(self.purged), "a": list(self.allowed), "v": self.state.get("context_version", "")}
        return hashlib.sha1(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()

    def to_dict(self) -> dict:
        return {"query": self.query, "role": self.role, "session_id": self.session_id, "filters": self.filters,
                "temporal": self.temporal_mode(), "k": self.k, "state_query": self.state_query()[:400],
                "sensitivity_allowed": list(self.allowed)}


def build_context(query: str, role: str = "", tool: str = "", session_id: str = "", filters: dict | None = None,
                  temporal: str = "auto", purged=None, allowed=(), k: int = 24) -> RetrievalContext:
    from .state import current
    bad = set(filters or {}) - set(FILTER_KEYS)
    if bad:
        raise ValueError(f"Unknown filter(s): {', '.join(sorted(bad))}")
    pg = frozenset(purged or ())
    return RetrievalContext(query=(query or "").strip()[:2000], role=P.resolve_role(role, tool), session_id=session_id,
                            filters=dict(filters or {}), temporal=temporal, state=current(set(pg)), k=k, purged=pg,
                            allowed=tuple(allowed or ()))


# ------------------------------------------------------------------ index (one per memory fingerprint)
class Index:
    def __init__(self, nodes: list, cfg: dict):
        self.nodes = nodes
        self.by_id = {n.id: n for n in nodes}
        self.ids = [n.id for n in nodes]
        self.texts = [n.text() for n in nodes]
        self.bm25 = BM25(self.texts, tokenizer=stem_tokens)  # v3.3: stemmed (refuted ≈ refutes)
        self.stems = [set(d) for d in self.bm25.docs]
        self.pos = {nid: i for i, nid in enumerate(self.ids)}
        self.embedder = get_embedder(cfg)
        self.vec_error = ""
        try:
            self.vecs = self.embedder.embed_unit(self.texts)
        except Exception as e:  # neural engine failed → the whole index uses lexical vectors (never mix spaces)
            self.vec_error = f"{type(e).__name__}: {e}"[:200]
            self.embedder.engine, self.embedder.model = "hashing", "hashing"
            self.vecs = self.embedder.embed_unit(self.texts)
        self.adj: dict = {}
        for n in nodes:
            for l in n.links:
                self.adj.setdefault(n.id, set()).add(l)
                self.adj.setdefault(l, set()).add(n.id)
        self.meta_values: dict = {}
        for n in nodes:
            for k in ("dataset", "model"):
                v = (n.meta.get(k) or "").strip()
                if v:
                    for t in tokenize(v):
                        if len(t) > 2:
                            self.meta_values.setdefault(t, set()).add(n.id)


def index(purged=frozenset(), cfg: dict | None = None) -> tuple:
    """(Index, cache_hit). Keyed by fingerprint + purged set + embedding engine settings."""
    from ..config import load_config
    cfg = cfg or load_config()
    mcfg = cfg["memory"]
    key = (cache.fingerprint(), tuple(sorted(purged)), mcfg.get("embed_engine"), mcfg.get("embed_model"))
    hit = cache.NODES.get(key)
    if hit is not None:
        return hit, True
    return cache.NODES.put(key, Index(LOD.collect(set(purged)), cfg)), False


# ------------------------------------------------------------------ filters
def _passes(n: LOD.MemoryNode, f: dict, allowed: tuple) -> bool:
    if allowed and n.classification not in allowed:
        return False
    if f.get("ids") and n.id not in set(f["ids"]):
        return False
    if f.get("types") and n.type not in set(f["types"]):
        return False
    if f.get("tiers") and n.tier not in set(f["tiers"]):
        return False
    for k in ("dataset", "model"):
        if f.get(k) and str(f[k]).lower() not in (n.meta.get(k) or "").lower():
            return False
    for k in ("source_type", "evidence_status", "origin"):
        if f.get(k) and (n.meta.get(k) or "") != f[k]:
            return False
    if f.get("since") and (n.ts or "") < str(f["since"]):
        return False
    if f.get("until") and n.ts and n.ts > str(f["until"]):
        return False
    return True


# ------------------------------------------------------------------ scoring
def _components(n: LOD.MemoryNode, ctx: RetrievalContext, idx: Index, fused_norm: float, coverage: float,
                state_ids: set, central: set, pol: P.RolePolicy, mode: str) -> dict:
    st = (n.status or "").lower()
    origin = (n.meta.get("origin") or "").lower()
    c = {"relevance": round(0.65 * fused_norm + 0.35 * coverage, 4)}
    c["importance"] = 1.0 if n.pinned else TYPE_IMPORTANCE.get(n.type, 0.3)
    # timeless knowledge (papers, concepts, methods without a date) is neither fresh nor stale
    c["recency"] = round(1.0 / (1 + _age_days(n.ts) / 30), 4) if n.ts else (0.5 if n.tier == "knowledge" else 0.0)
    conf = 0.6
    if st in ("validated", "supported", "supports", "validated failure", "refutes") or st.startswith("locked"):
        conf = 1.0
    elif st in ("candidate", "proposed", "open", "inconclusive", "contested"):
        conf = 0.4
    c["confidence"] = conf
    strength = 0.0
    if any(n.refs.get(k) for k in ("git", "clearml_task", "run", "dataset")):
        strength += 0.4
    if re.search(r"\d+\.\d+", n.short or ""):
        strength += 0.3
    ev_links = sum(1 for x in idx.adj.get(n.id, ()) if x.startswith("EVID-"))
    strength += min(0.3, 0.15 * ev_links)
    if n.type == "paper" and any(x.startswith("CLM-") for x in idx.adj.get(n.id, ())):
        strength += 0.4  # a source a recorded claim relies on
    if n.type == "evidence" and st == "validated":
        strength = max(strength, 0.9)
    c["evidence_strength"] = round(min(1.0, strength), 4)
    deg = len(idx.adj.get(n.id, ()))
    c["research_centrality"] = round(min(1.0, (1.0 if n.id in central else 0.0) + (0.7 if n.id in state_ids else 0.0)
                                         + min(0.3, deg / 20)), 4)
    fp = 1.0 if n.type == "failure" else (0.8 if "rejected" in st else (0.5 if st in ("refutes", "inconclusive", "refuted") else 0.0))
    c["failure_prevention"] = fp
    c["task_fit"] = pol.type_fit.get(n.type, 0.4)
    want = ctx_intent(ctx)  # graded: the first kind of record the question names counts most
    c["intent_fit"] = round(max(0.4, 1.0 - 0.2 * want.index(n.type)), 2) if n.type in want else 0.0
    low = 0.0
    if st in ("candidate", "rejected") or origin.startswith("provider:") or origin == "ai":
        low = 1.0 if st == "rejected" else 0.6
    if mode == "current" and (st == "superseded" or (n.type == "hypothesis" and st in ("refuted", "abandoned"))):
        low = max(low, 0.7)
    c["low_confidence"] = low
    return c


INTENT_WEIGHT = 0.8
PRIORS = ("importance", "recency", "confidence", "evidence_strength", "failure_prevention", "task_fit")


def ctx_intent(ctx: RetrievalContext) -> tuple:
    q = ctx.query or ""
    return tuple(dict.fromkeys(t for rx, types in INTENTS if rx.search(q) for t in types))


PLANNING_RE = re.compile(r"(?i)\b(next|should|plan(ning)?|propose|recommend|what now|where are we|status)\b")


def _score(c: dict, pol: P.RolePolicy, state_weight: float = 0.6) -> float:
    """relevance + centrality + gate × Σ priors − low-confidence penalty.
    The gate (= max(relevance, w × centrality); w = 1 for planning / "current state" questions, else 0.6) makes priors amplify RELEVANT records only: an important but unrelated
    record (a failure of another project branch, a pinned note about something else) cannot outrank a relevant one."""
    gate = max(c["relevance"], state_weight * c["research_centrality"])
    c["gate"] = round(gate, 4)
    # centrality counts fully for planning / current-state questions; otherwise only in proportion to relevance
    s = pol.weight("relevance") * c["relevance"] + pol.weight("research_centrality") * c["research_centrality"] * \
        (1.0 if state_weight >= 1.0 else c["relevance"])
    s += gate * sum(pol.weight(d) * c[d] for d in PRIORS)
    s += INTENT_WEIGHT * gate * c.get("intent_fit", 0.0)
    return round(s - pol.weight("low_confidence") * c["low_confidence"], 6)


def _reasons(n, c: dict, ranks: dict, q_terms: list, state_ids: set, central: set, mode: str) -> list:
    out = []
    srcs = [f"{k} #{v}" for k, v in ranks.items() if v]
    if srcs:
        out.append("found by " + ", ".join(srcs))
    toks = {stem(t) for t in tokenize(n.text())}
    hit = [t for t in q_terms if stem(t) in toks][:5]
    if hit:
        out.append("matches query terms: " + ", ".join(hit))
    if c.get("intent_fit"):
        out.append(f"is a {n.type}, the kind of record the question asks for")
    if n.id in state_ids:
        out.append("part of the current research state")
    elif n.id in central:
        out.append("linked to the active hypothesis / current experiment")
    if c["failure_prevention"] >= 0.8:
        out.append("prior failure / rejected direction — prevents repeating it")
    if c["evidence_strength"] >= 0.6:
        out.append("carries evidence (metrics / provenance pointers)")
    if n.pinned:
        out.append("pinned or locked by the researcher")
    if c["low_confidence"] >= 0.6:
        out.append("penalised: " + ("superseded / no longer current" if mode == "current" and n.status in ("superseded", "refuted", "abandoned")
                                    else "low confidence (candidate / AI-originated / rejected)"))
    return out


def retrieve(ctx: RetrievalContext, cfg: dict | None = None, nodes: list | None = None, rerank_pool: int = 48) -> dict:
    from ..config import load_config
    from ..telemetry import span
    cfg = cfg or load_config()
    mcfg = cfg["memory"]
    rkey = (cache.fingerprint(), ctx.key(), mcfg.get("embed_engine"), mcfg.get("embed_model"), mcfg.get("rerank_url"))
    with span("memory.retrieve", session_id=ctx.session_id or None, role=ctx.role) as sp:
        if nodes is None:
            hit = cache.RESULTS.get(rkey)
            if hit is not None:
                sp.update(cache_hit=True, candidate_count=hit["diagnostics"]["candidates"], selected_count=len(hit["hits"]))
                return {**hit, "diagnostics": {**hit["diagnostics"], "cache_hit": True}}
        t0 = time.perf_counter()
        if nodes is None:
            idx, idx_hit = index(ctx.purged, cfg)
        else:
            idx, idx_hit = Index(nodes, cfg), False
        out = _retrieve(ctx, cfg, idx, rerank_pool)
        out["diagnostics"].update(index_cache_hit=idx_hit, cache_hit=False, latency_ms=round((time.perf_counter() - t0) * 1000, 2))
        sp.update(cache_hit=False, candidate_count=out["diagnostics"]["candidates"], selected_count=len(out["hits"]),
                  nodes=len(idx.nodes))
        if nodes is None:
            cache.RESULTS.put(rkey, out)
        return out


def _retrieve(ctx: RetrievalContext, cfg: dict, idx: Index, rerank_pool: int) -> dict:
    pol = P.get(ctx.role)
    mode = ctx.temporal_mode()
    allowed_ids = {n.id for n in idx.nodes if _passes(n, ctx.filters, ctx.allowed)}
    blocked = sorted(n.id for n in idx.nodes if ctx.allowed and n.classification not in ctx.allowed)
    q = ctx.query or ctx.state_query() or "research project"
    diag = {"nodes": len(idx.nodes), "candidates": len(allowed_ids), "vector_engine": idx.embedder.label, "reranker": "explainable",
            "temporal": mode, "role": ctx.role, "query_terms": len(tokenize(q)), "blocked_by_sensitivity": len(blocked)}
    if idx.vec_error:
        diag["vector_error"] = idx.vec_error
    if not allowed_ids:
        return {"hits": [], "diagnostics": diag, "context": ctx.to_dict(), "blocked": blocked}

    def ranked(scores: dict) -> list:
        return _rank({k: v for k, v in scores.items() if k in allowed_ids})

    rankings: dict = {}
    rankings["keyword"] = ranked(dict(zip(idx.ids, idx.bm25.scores(q))))
    try:
        qv = idx.embedder.embed_unit([q])[0]
    except Exception:
        from .embeddings import hashing_sparse
        qv = hashing_sparse(q) if isinstance(idx.vecs[0], dict) else None
    if qv is not None:
        rankings["vector"] = ranked({nid: s for nid, s in ((i, similarity(v, qv)) for i, v in zip(idx.ids, idx.vecs)) if s > 0.05})
    from .state import ids as state_ids_of
    state_ids = state_ids_of(ctx.state) & set(idx.by_id)
    # state ranking: the records of the research state themselves (active hypothesis, current experiment, known failures,
    # recent decisions — in that order), then whatever matches the research-state query
    s = ctx.state or {}
    ordered = [h["id"] for h in s.get("active_hypotheses", [])[:2]] +         ([s["current_experiment"]["id"]] if s.get("current_experiment") else []) +         [f["id"] for f in s.get("known_failures", [])[:4]] + [d["id"] for d in s.get("recent_decisions", [])[:4]]
    sq = ctx.state_query()
    st_rank = [i for i in dict.fromkeys(ordered) if i in allowed_ids]
    if sq:
        st_rank += [i for i in ranked(dict(zip(idx.ids, idx.bm25.scores(sq)))) if i not in st_rank][:30]
    if st_rank:
        rankings["state"] = st_rank
    central = set()
    for sid in [h["id"] for h in ctx.state.get("active_hypotheses", [])[:2]] + \
               ([ctx.state["current_experiment"]["id"]] if ctx.state.get("current_experiment") else []):
        central |= idx.adj.get(sid, set())
    seeds = {nid: 1.0 / (i + 1) for i, nid in enumerate(_rank(rrf([rankings["keyword"][:15], rankings.get("vector", [])[:15]]))[:10])}
    for sid in state_ids:
        seeds.setdefault(sid, 0.5)
    rankings["graph"] = ranked(graph_scores(idx.nodes, seeds))
    want = list(ctx_intent(ctx)) if ctx.query else []
    if want:
        base = rrf([rankings["keyword"], rankings.get("vector", []), rankings.get("state", [])])
        prio = {t: i for i, t in enumerate(dict.fromkeys(want))}
        typed = [i for i in allowed_ids if idx.by_id[i].type in prio and base.get(i, 0) > 0]
        rankings["intent"] = sorted(typed, key=lambda i: (-round(base[i], 9), prio[idx.by_id[i].type], i))[:40]
        diag["intent"] = list(prio)
    q_toks = [t for t in dict.fromkeys(tokenize(q)) if len(t) > 2]
    meta_hits: dict = {}
    for t in q_toks:
        for nid in idx.meta_values.get(t, ()):
            meta_hits[nid] = meta_hits.get(nid, 0) + 1
    if meta_hits:
        rankings["metadata"] = ranked(meta_hits)
    if mode == "current":
        research_types = {"experiment", "evidence", "hypothesis", "decision", "metric", "claim", "failure"}
        rankings["temporal"] = [n.id for n in sorted((idx.by_id[i] for i in allowed_ids if idx.by_id[i].type in research_types),
                                                     key=lambda n: (_age_days(n.ts), n.id))][:30]
    fused: dict = {}
    for name, r in rankings.items():
        w = SOURCE_WEIGHTS[name]
        for pos, nid in enumerate(r):
            fused[nid] = fused.get(nid, 0.0) + w / (60 + pos + 1)
    # pool = best fused candidates ∪ the top of EVERY source, so a record that only one source finds (e.g. the active
    # hypothesis via the research state) still reaches the explainable scorer instead of losing to RRF dilution
    pool = sorted(fused, key=lambda x: (-round(fused[x], 9), x))[:rerank_pool]
    for r in rankings.values():
        pool += [i for i in r[:6] if i not in pool]
    top = fused[pool[0]] if pool else 1.0
    pos = {name: {nid: i + 1 for i, nid in enumerate(r)} for name, r in rankings.items()}
    ext = None
    url = (cfg["memory"].get("rerank_url") or "").strip()
    if url and pool:
        try:
            ext = http_rerank(url, cfg["memory"].get("rerank_model", ""), q, [idx.by_id[i] for i in pool])
            mx = max(ext.values()) or 1.0
            ext = {k: v / mx for k, v in ext.items()}
            diag["reranker"] = f"explainable + cross-encoder http:{url}"
        except Exception as e:
            diag["rerank_error"] = f"{type(e).__name__}: {e}"[:200]
            ext = None
    qset = {stem(t) for t in q_toks}
    planning = bool(PLANNING_RE.search(ctx.query or "")) or mode == "current" or not ctx.query
    diag["planning"] = planning
    hits = []
    for nid in pool:
        n = idx.by_id[nid]
        toks = idx.stems[idx.pos[nid]]
        coverage = len(qset & toks) / len(qset) if qset else 0.0
        rel_in = ext.get(nid, 0.0) if ext is not None else fused[nid] / top
        comp = _components(n, ctx, idx, rel_in, coverage, state_ids, central, pol, mode)
        ranks = {name: pos[name].get(nid) for name in pos}
        hits.append({"id": nid, "type": n.type, "tier": n.tier, "score": _score(comp, pol, 1.0 if planning else 0.6), "components": comp,
                     "ranks": ranks, "fused": round(fused[nid], 6),
                     "reasons": _reasons(n, comp, ranks, q_toks, state_ids, central, mode)})
    hits.sort(key=lambda h: (-h["score"], h["id"]))
    diag["sources"] = {name: len(r) for name, r in rankings.items()}
    return {"hits": hits[:ctx.k], "diagnostics": diag, "context": ctx.to_dict(), "blocked": blocked}


def explain(item_id: str, query: str, role: str = "", **kw) -> dict:
    """Why was (or wasn't) `item_id` retrieved for `query`? Returns its hit (components, ranks, reasons) or why not."""
    ctx = build_context(query, role=role, k=200, **kw)
    res = retrieve(ctx)
    for i, h in enumerate(res["hits"]):
        if h["id"] == item_id:
            return {"retrieved": True, "position": i + 1, **h}
    idx, _ = index(ctx.purged)
    if item_id not in idx.by_id:
        return {"retrieved": False, "reason": "not in memory (unknown, purged or deleted)"}
    if item_id in res.get("blocked", []):
        return {"retrieved": False, "reason": "blocked by the sensitivity policy"}
    return {"retrieved": False, "reason": "no retrieval source ranked it into the candidate pool (no term, vector, graph, "
                                          "state or metadata match)"}
