"""Bounded hybrid ranking over exact SKB chunks; reuse the existing local embedding service.

No claim of semantic retrieval is made for hashing vectors. External HTTP rerankers are
deliberately not inherited from memory settings: paper text requires its own disclosure consent.
"""
from backend.core.config import load_config
import ipaddress
from urllib.parse import urlparse

from backend.memory.embeddings import get_embedder, similarity, _ollama_root
from backend.memory.retrieval import rrf


def rank(c, tid, query, keyword_ids, paper_id="", pool_limit=1000):
    rows = list(c.execute("SELECT ch.id,ch.text FROM chunks ch JOIN chunk_search cs ON cs.chunk_id=ch.id JOIN versions v ON v.id=ch.version_id "
                         "JOIN paper_topics pt ON pt.paper_id=v.paper_id JOIN documents d ON d.sha256=(SELECT sha256 FROM version_documents WHERE version_id=v.id) "
                         "WHERE pt.topic_id=? AND pt.state!='dismissed' AND d.status='indexed' AND (?='' OR v.paper_id=?) ORDER BY ch.id LIMIT ?",
                         (tid, paper_id, paper_id, pool_limit + 1)))
    truncated = len(rows) > pool_limit
    rows = rows[:pool_limit]
    cfg = load_config()
    # Configured local embedding only; never send scholarly text to cloud rerankers.
    host = urlparse(_ollama_root(cfg)).hostname or ""
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host.lower() == "localhost"
    if not local:
        cfg = {**cfg, "memory": {**cfg["memory"], "embed_engine": "hashing"}}
    embedder = get_embedder(cfg)
    texts = [r["text"] for r in rows]
    error = ""
    try:
        vectors = embedder.embed_unit(texts + [query])
    except Exception as exc:
        error = type(exc).__name__
        embedder.engine, embedder.model = "hashing", "hashing"
        vectors = embedder.embed_unit(texts + [query])
    scored = [(r["id"], similarity(v, vectors[-1])) for r, v in zip(rows, vectors[:-1])]
    vector_ids = [key for key, score in sorted(scored, key=lambda x: (-x[1], x[0])) if score > 0.05]
    fused = rrf([keyword_ids, vector_ids])
    return sorted(fused, key=lambda key: (-fused[key], key)), {
        "method": "BM25 + vector reciprocal-rank fusion", "vector_engine": embedder.label,
        "embedding_error": error, "vector_pool": len(rows), "vector_pool_truncated": truncated,
        "external_reranker": False, "remote_embedding_refused": not local, "scientific_validity_assessed": False}
