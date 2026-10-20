"""Dense vectors for the retrieval engine.

Engines (memory.embed_engine):
  ollama   neural embeddings from a local Ollama embedding model (memory.embed_model, e.g. nomic-embed-text) via
           POST /api/embed — runs with num_gpu=0 (CPU/RAM) while the GPU is busy with a training run
  hashing  feature-hashed unigram+bigram vectors (pure Python, no model). This is a LEXICAL vector, not a neural one —
           it is reported as such in the retrieval diagnostics.
  auto     ollama when the embedding model is pulled and reachable, otherwise hashing

Document vectors are cached in memory/embeddings.json (derived data: safe to delete).
"""
from __future__ import annotations

import hashlib
from array import array
import math
import re
import time

import httpx

from . import mem_dir
from .store import JsonStore

DIM = 512
TOKEN_RE = re.compile(r"[A-Za-z]+-\d+|[0-9a-f]{7,40}|[^\W_]+", re.UNICODE)
_cache = JsonStore(lambda: mem_dir() / "embeddings.json", {"vectors": {}}, versioned=False)
MAX_CACHE = 6000
_probe = {"t": 0.0, "ok": False, "model": ""}


def tokenize(text: str) -> list:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if len(t) > 1 or t.isdigit()]


def stem(t: str) -> str:
    """Conservative suffix stripping (v3.3): refuted / refutes / refute → refut, experiments → experiment. Identifiers
    (anything with a digit or a dash: HYPE-002, git SHAs, CAVE-v2) and short words are left untouched."""
    if len(t) <= 4 or any(c.isdigit() for c in t) or "-" in t:
        return t
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if t.endswith(suf) and len(t) - len(suf) >= 4 and not (suf == "s" and t.endswith("ss")):
            t = t[: len(t) - len(suf)] + rep
            break
    return t[:-1] if t.endswith("e") and len(t) > 5 else t


def stem_tokens(text: str) -> list:
    return [stem(t) for t in tokenize(text)]


def hashing_vector(text: str, dim: int = DIM) -> list:
    toks = tokenize(text)
    feats = toks + [a + " " + b for a, b in zip(toks, toks[1:])]
    v = [0.0] * dim
    counts: dict = {}
    for f in feats:
        counts[f] = counts.get(f, 0) + 1
    for f, c in counts.items():
        h = int.from_bytes(hashlib.blake2b(f.encode("utf-8"), digest_size=8).digest(), "big")
        v[h % dim] += (1.0 if (h >> 63) & 1 else -1.0) * (1.0 + math.log(c))
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def hashing_sparse(text: str, dim: int = DIM) -> dict:
    """v3.3: the same feature-hashed vector as hashing_vector() but sparse ({index: value}, unit length). A typical memory
    node touches ~30-80 of the 512 buckets, so similarity costs O(nnz) instead of O(512) (profiling: ~10× faster)."""
    from .cache import VECTORS
    key = ("hash", dim, hashlib.sha1((text or "").encode("utf-8", "replace")).digest())
    hit = VECTORS.get(key)
    if hit is not None:
        return hit
    toks = tokenize(text)
    feats = toks + [a + " " + b for a, b in zip(toks, toks[1:])]
    counts: dict = {}
    for f in feats:
        counts[f] = counts.get(f, 0) + 1
    v: dict = {}
    for f, c in counts.items():
        h = int.from_bytes(hashlib.blake2b(f.encode("utf-8"), digest_size=8).digest(), "big")
        i = h % dim
        v[i] = v.get(i, 0.0) + (1.0 if (h >> 63) & 1 else -1.0) * (1.0 + math.log(c))
    n = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return VECTORS.put(key, {i: x / n for i, x in v.items() if x})


def sparse_dot(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(i, 0.0) for i, x in a.items())


def unit(v: list) -> list:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def similarity(a, b) -> float:
    """Cosine of two unit vectors of the same engine (sparse dicts or dense lists)."""
    if isinstance(a, dict):
        return sparse_dot(a, b)
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _ollama_root(cfg: dict) -> str:
    from ..local_ai import ollama_root
    return ollama_root(cfg.get("ollama_base_url"))


def ollama_available(cfg: dict) -> bool:
    model = cfg["memory"].get("embed_model") or ""
    if not model:
        return False
    if time.time() - _probe["t"] < 60 and _probe["model"] == model:
        return _probe["ok"]
    ok = False
    try:
        r = httpx.get(_ollama_root(cfg) + "/api/tags", timeout=2)
        names = [m.get("name") or m.get("model") or "" for m in r.json().get("models", [])]
        ok = any(n == model or n.split(":")[0] == model.split(":")[0] for n in names)
    except Exception:
        ok = False
    _probe.update(t=time.time(), ok=ok, model=model)
    return ok


def _ollama_embed(cfg: dict, texts: list, timeout: float) -> list:
    body = {"model": cfg["memory"]["embed_model"], "input": texts}
    try:
        from ..resources import gpu_busy
        if gpu_busy():
            body["options"] = {"num_gpu": 0}  # keep VRAM for the training run
    except Exception:
        pass
    r = httpx.post(_ollama_root(cfg) + "/api/embed", json=body, timeout=timeout)
    r.raise_for_status()
    vecs = r.json().get("embeddings") or []
    if len(vecs) != len(texts):
        raise ValueError("Ollama returned a different number of embeddings")
    return vecs


class Embedder:
    def __init__(self, cfg: dict):
        eng = cfg["memory"].get("embed_engine", "auto")
        self.cfg = cfg
        self.engine = "ollama" if eng == "ollama" or (eng == "auto" and ollama_available(cfg)) else "hashing"
        self.model = cfg["memory"].get("embed_model", "") if self.engine == "ollama" else f"hashing-{DIM}"
        self.error = ""

    @property
    def label(self) -> str:
        return f"ollama:{self.model}" if self.engine == "ollama" else f"hashing-{DIM} (lexical, not neural)"

    def embed_unit(self, texts: list, timeout: float = 20) -> list:
        """v3.3 retrieval path: unit vectors ready for similarity() — sparse for hashing, normalised dense for Ollama."""
        if self.engine == "hashing":
            return [hashing_sparse(t) for t in texts]
        from .cache import VECTORS  # in-process layer over the JSON cache (which is re-read from disk on every embed())
        keys = [("dense", self.model, hashlib.sha1(t.encode("utf-8", "replace")).digest()) for t in texts]
        out = [VECTORS.get(k) for k in keys]
        todo = [i for i, v in enumerate(out) if v is None]
        if todo:
            for i, v in zip(todo, self.embed([texts[i] for i in todo], timeout=timeout)):
                out[i] = VECTORS.put(keys[i], array("f", unit(v)))  # float32: ~3 KB per 768-d vector
        return out

    def embed(self, texts: list, cache: bool = True, timeout: float = 20) -> list:
        if self.engine == "hashing":
            return [hashing_vector(t) for t in texts]
        keys = [f"{self.model}:{hashlib.sha1(t.encode('utf-8', 'replace')).hexdigest()}" for t in texts]
        store = _cache.load()["vectors"] if cache else {}
        out = [store.get(k) for k in keys]
        todo = [i for i, v in enumerate(out) if v is None]
        for s in range(0, len(todo), 64):
            idx = todo[s:s + 64]
            vecs = _ollama_embed(self.cfg, [texts[i][:8000] for i in idx], timeout)
            for i, v in zip(idx, vecs):
                out[i] = v
        if cache and todo:
            def put(st):
                vs = st["vectors"]
                for i in todo:
                    vs[keys[i]] = [round(x, 5) for x in out[i]]
                if len(vs) > MAX_CACHE:
                    for k in list(vs)[: len(vs) - MAX_CACHE]:
                        vs.pop(k, None)
            _cache.update(put)
        return out


def get_embedder(cfg: dict) -> Embedder:
    return Embedder(cfg)
