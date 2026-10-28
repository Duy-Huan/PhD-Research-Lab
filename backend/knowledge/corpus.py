"""Versioned scholarly records, exact page evidence and explicit per-topic curation."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from backend.knowledge import research_store as S
from backend.knowledge.sources import arxiv_id, doi


def normalize(record: dict) -> dict:
    for key in ("authors", "sources", "flags", "oa_locations"):
        if key in record and not isinstance(record[key], list):
            raise ValueError(key + " must be a list")
    title = re.sub(r"\s+", " ", str(record.get("title") or "")).strip()[:1000]
    if not title:
        raise ValueError("A paper title is required")
    d = doi(record.get("doi"))
    aid = arxiv_id(record.get("arxiv_id")) or arxiv_id(record.get("url")) or arxiv_id(record.get("pdf_url"))
    provider = str(record.get("source") or "user_imported")[:120]
    native = str(record.get("openalex_id") or "").replace("https://openalex.org/", "")
    native = native if re.fullmatch(r"W\d+", native) else ""
    references = record.get("references") or []
    if not isinstance(references, list) or len(references) > 2000:
        raise ValueError("References must be a list of at most 2000 DOI/OpenAlex identifiers")
    references = list(dict.fromkeys(key for value in references if (key := reference_id(value))))
    urls = list(record.get("oa_locations") or [])
    # Only established discovery adapters declare their PDF fields open-access.
    if record.get("pdf_url") and provider in ("OpenAlex", "arXiv", "Semantic Scholar", "IEEE Xplore"):
        urls.append({"url": record["pdf_url"], "provider": provider, "access": "open", "license": "unknown",
                     "version": "preprint" if "arxiv" in provider.lower() else "unknown"})
    urls = [{k: str(v)[:4000] for k, v in x.items() if k in ("url", "provider", "access", "license", "version", "checked_at")}
            for x in urls if isinstance(x, dict) and x.get("url")][:20]
    return {"title": title, "doi": d, "arxiv_id": aid, "openalex_id": native, "references": references, "pmid": str(record.get("pmid") or "") if str(record.get("pmid") or "").isdigit() else "", "authors": [str(a)[:200] for a in record.get("authors") or []][:50],
            "year": str(record.get("year") or "")[:4], "abstract": str(record.get("abstract") or "")[:50000],
            "venue": str(record.get("venue") or "")[:500], "url": str(record.get("url") or ("https://doi.org/" + d if d else ""))[:4000],
            "source": provider, "sources": list(dict.fromkeys([provider] + list(record.get("sources") or []))),
            "oa_locations": urls, "flags": list(dict.fromkeys([str(f)[:120] for f in record.get("flags") or []] + (["preprint"] if aid else []))),
            "publication_type": str(record.get("publication_type") or "unknown"), "license": record.get("license") or "unknown",
            "citations": record.get("citations") if isinstance(record.get("citations"), int) and not isinstance(record.get("citations"), bool) and record["citations"] >= 0 else None,
            "peer_review_status": str(record.get("peer_review_status") or "unknown")[:100],
            "version": str(record.get("version") or ("preprint" if aid else "unknown"))[:120], "retrieved_at": S.now()}


def _aliases(p: dict) -> list[str]:
    out = (["doi:" + p["doi"]] if p["doi"] else []) + (["arxiv:" + p["arxiv_id"]] if p["arxiv_id"] else [])
    if p.get("pmid"):
        out.append("pmid:" + p["pmid"])
    if p.get("openalex_id"):
        out.append("openalex:" + p["openalex_id"])
    if not out:
        # Exact source metadata fingerprint only, not fuzzy title merging.
        value = [p["title"].casefold(), p["year"], p["authors"], p["url"]]
        out.append("metadata:" + hashlib.sha256(S.dumps(value).encode()).hexdigest())
    return out


def reference_id(value) -> str:
    value = str(value or "")
    d = doi(value)
    if d:
        return "doi:" + d
    value = value.removeprefix("https://openalex.org/").removeprefix("openalex:")
    return "openalex:" + value if re.fullmatch(r"W\d+", value) else ""


def _reset_review(c, pid: str):
    """A new source version is not covered by an earlier paper-level attestation/screen."""
    base = c.execute("SELECT coalesce(max(CASE WHEN d.status='indexed' THEN 2 ELSE 1 END),0) FROM documents d JOIN version_documents vd ON vd.sha256=d.sha256 JOIN versions v ON v.id=vd.version_id WHERE v.paper_id=?", (pid,)).fetchone()[0]
    rows = list(c.execute("SELECT * FROM paper_topics WHERE paper_id=? AND level>=3", (pid,)))
    for row in rows:
        details = json.loads(row["payload"])
        details["review_reset"] = {"at": S.now(), "reason": "New source version requires review", "previous_level": row["level"]}
        c.execute("UPDATE paper_topics SET level=?,payload=? WHERE topic_id=? AND paper_id=?", (base, S.dumps(details), row["topic_id"], pid))
        S.event(c, row["topic_id"], "paper.review_reset", {"paper_id": pid, "previous_level": row["level"], "level": base, "reason": "New source version"})


def ingest(tid: str, records: list[dict]) -> dict:
    added, duplicates, conflicts, paper_ids = [], 0, [], []
    with S.db() as c:
        profile = S.topic(c, tid)
        for record in records[:1000]:
            p = normalize(record)
            aliases = _aliases(p)
            ids = {r[0] for a in aliases for r in c.execute("SELECT paper_id FROM aliases WHERE alias=?", (a,))}
            if len(ids) > 1:
                conflicts.append({"aliases": aliases, "reason": "Conflicting identifiers require manual review"})
                continue
            pid = next(iter(ids), S.uid())
            old = c.execute("SELECT payload FROM papers WHERE id=?", (pid,)).fetchone()
            if old:
                previous = json.loads(old[0])
                if previous["doi"] and p["doi"] and previous["doi"] != p["doi"]:
                    conflicts.append({"aliases": aliases, "reason": "Conflicting DOI for arXiv alias"})
                    continue
                merged = {**previous, **{k: v for k, v in p.items() if v not in ("", [], None, "unknown")}}
                merged["sources"] = list(dict.fromkeys(previous["sources"] + p["sources"]))
                merged["oa_locations"] = list({S.dumps(x): x for x in previous["oa_locations"] + p["oa_locations"]}.values())
                merged["flags"] = list(dict.fromkeys(previous["flags"] + p["flags"]))
                merged["references"] = list(dict.fromkeys(previous.get("references", []) + p["references"]))
                c.execute("UPDATE papers SET payload=? WHERE id=?", (S.dumps(merged), pid))
            else:
                c.execute("INSERT INTO papers VALUES(?,?,?)", (pid, S.dumps(p), S.now()))
            for a in aliases:
                c.execute("INSERT OR IGNORE INTO aliases VALUES(?,?)", (a, pid))
            # A version is source + native URL/version + metadata, not ingestion timestamp.
            version = {k: p[k] for k in ("source", "url", "doi", "arxiv_id", "version", "title", "abstract", "authors", "year", "venue", "publication_type", "flags", "oa_locations", "license")}
            # Empty newly supported metadata must preserve pre-upgrade version digests/attestations.
            if p["references"]:
                version["references"] = p["references"]
            signature = hashlib.sha256(S.dumps(version).encode()).hexdigest()
            created_version = c.execute("INSERT OR IGNORE INTO versions VALUES(?,?,?,?)", (S.uid(), pid, signature, S.dumps({**version, "retrieved_at": p["retrieved_at"]})))
            if old and created_version.rowcount:
                _reset_review(c, pid)
            matched = [k for k in profile["keywords"] if k.casefold() in (p["title"] + " " + p["abstract"]).casefold()]
            cursor = c.execute("INSERT OR IGNORE INTO paper_topics(topic_id,paper_id,payload) VALUES(?,?,?)",
                               (tid, pid, S.dumps({"matched_terms": matched, "relevance": len(matched), "score_kind": "lexical_matches"})))
            paper_ids.append(pid)
            if cursor.rowcount:
                added.append(pid)
                S.event(c, tid, "paper.discovered", {"paper_id": pid, "source": p["source"], "fidelity": "user_imported"})
            else:
                duplicates += 1
    return {"added": added, "duplicates": duplicates, "conflicts": conflicts,"paper_ids":list(dict.fromkeys(paper_ids))}


def _paper(c, tid: str, pid: str) -> dict:
    row = c.execute("SELECT p.*,pt.level,pt.state,pt.payload AS association FROM papers p JOIN paper_topics pt ON p.id=pt.paper_id "
                    "WHERE pt.topic_id=? AND p.id=?", (tid, pid)).fetchone()
    if not row:
        raise ValueError("Paper not found in this topic")
    versions = [{"id": v["id"], **json.loads(v["payload"]), "document": dict(d) if (d := c.execute(
        "SELECT d.* FROM documents d JOIN version_documents vd ON vd.sha256=d.sha256 WHERE vd.version_id=?", (v["id"],)).fetchone()) else None}
        for v in c.execute("SELECT * FROM versions WHERE paper_id=? ORDER BY rowid", (pid,))]
    return {**json.loads(row["payload"]), "id": pid, "topic_id": tid, "level": row["level"], "state": row["state"],
            "association": json.loads(row["association"]), "versions": versions}


def paper(tid: str, pid: str) -> dict:
    with S.db() as c:
        return _paper(c, tid, pid)


def search(tid: str, q: str = "", level: int = -1, state: str = "", source: str = "", year: int = 0,
           oa: bool = False, offset: int = 0, limit: int = 25, sort: str = "relevance", *,
           max_year: int = 0, venue: str = "", publication_type: str = "", tag: str = "",
           pdf: bool | None = None, flag: str = "") -> dict:
    with S.db() as c:
        S.topic(c, tid)
        # JSON extract operates on authoritative metadata; SQL parameters keep filters inert.
        where = "pt.topic_id=? AND (?<0 OR pt.level=?) AND (?='' OR pt.state=?) "
        where += "AND (?='' OR instr(lower(p.payload),lower(?))>0) AND (?=0 OR CAST(json_extract(p.payload,'$.year') AS INTEGER)>=?) "
        where += "AND (?='' OR instr(lower(json_extract(p.payload,'$.sources')),lower(?))>0) "
        where += "AND (?=0 OR json_array_length(json_extract(p.payload,'$.oa_locations'))>0)"
        where += " AND (?=0 OR CAST(json_extract(p.payload,'$.year') AS INTEGER)<=?)"
        where += " AND (?='' OR instr(lower(json_extract(p.payload,'$.venue')),lower(?))>0)"
        where += " AND (?='' OR json_extract(p.payload,'$.publication_type')=?)"
        where += " AND (?='' OR EXISTS(SELECT 1 FROM json_each(pt.payload,'$.tags') WHERE value=?))"
        where += " AND (?='' OR EXISTS(SELECT 1 FROM json_each(p.payload,'$.flags') WHERE value=?))"
        where += " AND (? IS NULL OR EXISTS(SELECT 1 FROM versions v JOIN version_documents vd ON vd.version_id=v.id WHERE v.paper_id=p.id)=?)"
        params = (tid, level, level, state, state, q, q, year, year, source, source, int(oa),
                  max_year, max_year, venue, venue, publication_type, publication_type, tag, tag, flag, flag, pdf, pdf)
        base = " FROM papers p JOIN paper_topics pt ON p.id=pt.paper_id WHERE " + where
        count = c.execute("SELECT count(*)" + base, params).fetchone()[0]
        if sort not in ("relevance", "year", "citations"):
            raise ValueError("Unsupported paper sort")
        order = {"year": "CAST(json_extract(p.payload,'$.year') AS INTEGER) DESC",
                 "citations": "json_extract(p.payload,'$.citations') DESC",
                 "relevance": "CAST(json_extract(pt.payload,'$.relevance') AS INTEGER) DESC"}[sort]
        rows = c.execute("SELECT p.id" + base + " ORDER BY " + order + ",p.id LIMIT ? OFFSET ?", (*params, min(100, max(1, limit)), max(0, offset)))
        return {"papers": [_paper(c, tid, r[0]) for r in rows], "total": count, "offset": max(0, offset)}


def all_papers(tid: str) -> list:
    """A report is a complete scoped snapshot, independent of Explorer page size."""
    with S.db() as c:
        S.topic(c, tid)
        return [_paper(c, tid, r[0]) for r in c.execute("SELECT paper_id FROM paper_topics WHERE topic_id=? ORDER BY paper_id", (tid,))]


def citation_graph(tid: str) -> dict:
    """Only registered source-declared links. Unknown/out-of-Topic targets stay unresolved."""
    papers = all_papers(tid)
    aliases = {a: p["id"] for p in papers for a in _aliases(p)}
    edges = []
    for p in papers:
        for v in p["versions"]:
            for ref in v.get("references", []):
                edges.append({"citing_paper_id": p["id"], "cited_paper_id": aliases.get(ref), "target_identifier": ref,
                              "version_id": v["id"], "source": v["source"], "source_url": v["url"],
                              "trust": "source_declared_unverified"})
    return {"topic_id": tid, "nodes": [{"id": p["id"], "title": p["title"], "doi": p["doi"]} for p in papers],
            "edges": edges, "limits": "Only references explicitly provided by registered source versions; not a complete scholarly citation graph or validation of a citation"}


def tag_papers(tid: str, ids: list[str], tags: list[str], remove: bool = False) -> dict:
    if not 1 <= len(ids) <= 100 or not isinstance(tags, list) or not 1 <= len(tags) <= 30:
        raise ValueError("Select 1–100 papers and 1–30 tags")
    if any(not isinstance(t, str) or not t.strip() or len(t) > 80 for t in tags):
        raise ValueError("Tags must be nonempty strings of at most 80 characters")
    tags = list(dict.fromkeys(t.strip() for t in tags))
    with S.db() as c:
        for pid in dict.fromkeys(ids):
            p = _paper(c, tid, pid)
            details = p["association"]
            previous = details.get("tags", [])
            updated = [t for t in previous if t not in tags] if remove else list(dict.fromkeys(previous + tags))
            if len(updated) > 30:
                raise ValueError("At most 30 tags per paper and Topic")
            details["tags"] = updated
            c.execute("UPDATE paper_topics SET payload=? WHERE topic_id=? AND paper_id=?", (S.dumps(details), tid, pid))
            S.event(c, tid, "paper.tags", {"paper_id": pid, "previous": previous, "tags": updated, "by": "researcher"})
    return {"updated": list(dict.fromkeys(ids))}


def curate(tid: str, ids: list[str], action: str, note: str = "") -> dict:
    if action not in ("accept", "dismiss", "defer", "verify", "screen") or not 1 <= len(ids) <= 100:
        raise ValueError("Choose a supported action and 1–100 papers")
    if action == "verify" and not note.strip():
        raise ValueError("L4 requires an explicit researcher's attestation note")
    with S.db() as c:
        for pid in dict.fromkeys(ids):
            p = _paper(c, tid, pid)
            details = p["association"]
            level, state = p["level"], p["state"]
            if action == "screen":
                if level < 2:
                    raise ValueError("Screening requires indexed full text")
                level = max(level, 3)
                details.pop("review_reset", None)
                details["screening"] = {"rationale": "Text indexed; metadata completeness only. Scientific validity is unassessed.", "version": "rules-1"}
            elif action == "verify":
                level = 4
                details.pop("review_reset", None)
                details["attestation"] = {"by": "researcher", "note": note[:8000], "at": S.now(),
                                          "version_ids": [v["id"] for v in p["versions"]],
                                          "metadata_sha256": hashlib.sha256(S.dumps({k:p[k] for k in ("title","doi","abstract","authors","year")}).encode()).hexdigest()}
            else:
                state = {"accept": "accepted", "dismiss": "dismissed", "defer": "deferred"}[action]
            c.execute("UPDATE paper_topics SET level=?,state=?,payload=? WHERE topic_id=? AND paper_id=?",
                      (level, state, S.dumps(details), tid, pid))
            S.event(c, tid, "paper." + action, {"paper_id": pid, "note": note[:8000], "level": level, "by": "researcher",
                                               "attestation": details.get("attestation") if action == "verify" else None})
    return {"updated": list(dict.fromkeys(ids))}


def associate(tid: str, target: str, ids: list[str]) -> dict:
    if not 1 <= len(ids) <= 100:
        raise ValueError("Select 1–100 papers")
    with S.db() as c:
        S.topic(c, target)
        for pid in ids:
            _paper(c, tid, pid)
            # Curation and attestation never leak from the source topic.
            c.execute("INSERT OR IGNORE INTO paper_topics(topic_id,paper_id) VALUES(?,?)", (target, pid))
            S.event(c, target, "paper.associated", {"paper_id": pid, "from_topic": tid})
    return {"associated": ids}


def object_path(sha: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise ValueError("Invalid object checksum")
    p = S.safe_child(S.store_dir(), "objects", sha + ".pdf")
    p.parent.mkdir(exist_ok=True)
    return p


def add_oa_version(tid: str, pid: str, location: dict) -> str:
    with S.db() as c:
        p = _paper(c, tid, pid)
        version = {"source": location.get("provider", "OA resolver"), "url": location["url"], "doi": p["doi"], "arxiv_id": p["arxiv_id"],
                   "version": location.get("version", "unknown"), "title": p["title"], "abstract": p["abstract"],
                   **{k:p[k] for k in ("authors", "year", "venue", "publication_type", "flags")},
                   "oa_locations": [location], "license": location.get("license", "unknown")}
        signature = hashlib.sha256(S.dumps(version).encode()).hexdigest()
        vid = S.uid()
        created = c.execute("INSERT OR IGNORE INTO versions VALUES(?,?,?,?)", (vid, pid, signature, S.dumps({**version, "retrieved_at": S.now()})))
        if created.rowcount:
            _reset_review(c, pid)
        vid = c.execute("SELECT id FROM versions WHERE paper_id=? AND signature=?", (pid, signature)).fetchone()[0]
        raw = json.loads(c.execute("SELECT payload FROM papers WHERE id=?", (pid,)).fetchone()[0])
        raw["oa_locations"] = list({S.dumps(x):x for x in raw["oa_locations"] + [location]}.values())
        c.execute("UPDATE papers SET payload=? WHERE id=?", (S.dumps(raw), pid))
        S.event(c, tid, "paper.oa_resolved", {"paper_id": pid, "version_id": vid, "url": location["url"]}, key="oa:" + tid + ":" + vid)
        return vid


def store_document(tid: str, pid: str, vid: str, raw: bytes, provenance: dict) -> dict:
    if not raw.startswith(b"%PDF"):
        raise ValueError("Not a PDF")
    sha = hashlib.sha256(raw).hexdigest()
    p = paper(tid, pid)
    if vid not in [v["id"] for v in p["versions"]]:
        raise ValueError("Version does not belong to this paper")
    from backend.memory.store import replace_retry
    with S.db() as c:
        profile = S.topic(c, tid)
        previous = c.execute("SELECT sha256 FROM version_documents WHERE version_id=?", (vid,)).fetchone()
        if previous and previous[0] != sha:
            raise ValueError("PDF bytes changed; register a new source version before replacing a document")
        if len(raw) > profile["max_pdf_mb"] * 1024 * 1024:
            raise ValueError("PDF exceeds the topic's file-size quota")
        occupied = c.execute("SELECT coalesce(sum(bytes),0) FROM documents WHERE sha256 IN (SELECT vd.sha256 FROM version_documents vd JOIN versions v ON v.id=vd.version_id JOIN paper_topics pt ON pt.paper_id=v.paper_id WHERE pt.topic_id=?)", (tid,)).fetchone()[0]
        present = c.execute("SELECT 1 FROM version_documents vd JOIN versions v ON v.id=vd.version_id JOIN paper_topics pt ON pt.paper_id=v.paper_id WHERE pt.topic_id=? AND vd.sha256=? LIMIT 1", (tid, sha)).fetchone()
        if occupied + (0 if present else len(raw)) > profile["storage_mb"] * 1024 * 1024:
            raise ValueError("Topic storage quota reached")
        # File is atomic before the metadata commit; an interruption leaves at most an unreferenced object.
        path = object_path(sha)
        if not path.exists():
            temporary = path.with_suffix('.' + S.uid() + '.tmp')
            try:
                temporary.write_bytes(raw)
                replace_retry(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("Stored PDF checksum mismatch")
        c.execute("INSERT OR IGNORE INTO documents(sha256,bytes,payload) VALUES(?,?,?)", (sha, len(raw), S.dumps(provenance)))
        c.execute("INSERT INTO version_documents VALUES(?,?) ON CONFLICT(version_id) DO UPDATE SET sha256=excluded.sha256", (vid, sha))
        c.execute("UPDATE paper_topics SET level=max(level,1) WHERE paper_id=?", (pid,))
        S.event(c, tid, "paper.downloaded", {"paper_id": pid, "version_id": vid, "sha256": sha, **provenance})
    return {"sha256": sha, "bytes": len(raw), "version_id": vid}


def index_document(tid: str, pid: str, vid: str) -> dict:
    p = paper(tid, pid)
    v = next((v for v in p["versions"] if v["id"] == vid), None)
    if not v or not v["document"]:
        raise ValueError("Download the selected version first")
    doc = v["document"]
    path = object_path(doc["sha256"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != doc["sha256"]:
        raise ValueError("PDF checksum mismatch")
    parser = S.get_topic(tid)["parser"]
    try:
        if parser == "docling":
            from backend.plugins.document_parser import pages as docling_pages
            pages, total = docling_pages(path)
        else:
            from backend.knowledge.pdf_indexer import pages as existing_pages
            pages, total = existing_pages(path)
        chunks = []
        for page, text in enumerate(pages, 1):
            for offset in range(0, min(len(text), 100000), 1800):
                chunk = text[offset:offset + 2000].strip()
                if chunk:
                    digest = hashlib.sha256(f"{vid}:{page}:{offset}:{chunk}".encode()).hexdigest()
                    chunks.append((digest, vid, page, "page text", chunk, hashlib.sha256(chunk.encode()).hexdigest()))
        if not chunks:
            raise ValueError("No extractable text; OCR or an optional parser is required")
    except Exception as exc:
        with S.db() as c:
            c.execute("UPDATE documents SET status='parse_failed',payload=json_set(payload,'$.parse_error',?) WHERE sha256=?", (str(exc)[:500], doc["sha256"]))
        raise ValueError(str(exc)) from exc
    with S.db() as c:
        c.execute("DELETE FROM chunk_search WHERE chunk_id IN (SELECT id FROM chunks WHERE version_id=?)", (vid,))
        # Retain historical evidence IDs even when a different parser produces new chunks.
        c.executemany("INSERT OR IGNORE INTO chunks VALUES(?,?,?,?,?,?)", chunks)
        c.executemany("INSERT INTO chunk_search VALUES(?,?)", [(r[0], r[4]) for r in chunks])
        c.execute("UPDATE documents SET parser=?,status='indexed',payload=json_set(payload,'$.pages',?,'$.total_pages',?,'$.partial',?) WHERE sha256=?",
                  (parser, len(pages), total, int(len(pages) < total or any(not t.strip() for t in pages)), doc["sha256"]))
        c.execute("UPDATE paper_topics SET level=max(level,2) WHERE paper_id=?", (pid,))
        S.event(c, tid, "paper.indexed", {"paper_id": pid, "version_id": vid, "chunks": len(chunks), "pages": len(pages), "total_pages": total})
    return {"chunks": len(chunks), "pages": len(pages), "total_pages": total}


def retrieve(tid: str, query: str, limit: int = 10, paper_id: str = "") -> list:
    terms = re.findall(r"\w+", query, flags=re.UNICODE)[:20]
    if not terms:
        return []
    limit = min(30, max(1, limit))
    match = " OR ".join('"' + t + '"' for t in terms)
    with S.db() as c:
        S.topic(c, tid)
        if paper_id:
            _paper(c, tid, paper_id)
        rows = list(c.execute("SELECT ch.id FROM chunk_search JOIN chunks ch ON ch.id=chunk_search.chunk_id "
                         "JOIN versions v ON v.id=ch.version_id JOIN paper_topics pt ON pt.paper_id=v.paper_id "
                         "WHERE pt.topic_id=? AND pt.state!='dismissed' AND (?='' OR v.paper_id=?) AND chunk_search MATCH ? "
                         "ORDER BY bm25(chunk_search),ch.id LIMIT 100", (tid, paper_id, paper_id, match)))
        from backend.knowledge.evidence_retrieval import rank
        ids, diagnostics = rank(c, tid, query, [r[0] for r in rows], paper_id)
        out = []
        for chunk_id in ids[:limit]:
            r = c.execute("SELECT ch.*,v.paper_id FROM chunks ch JOIN versions v ON v.id=ch.version_id WHERE ch.id=?", (chunk_id,)).fetchone()
            p = _paper(c, tid, r["paper_id"])
            out.append({"id": "evidence:" + r["id"], "paper_id": p["id"], "title": p["title"], "doi": p["doi"],
                        "version_id": r["version_id"], "page": r["page"], "section": r["section"], "text": r["text"],
                        "level": p["level"], "trust": "untrusted", "rank": ids.index(chunk_id) + 1, "status": "full_text_extract",
                        "flags": p["flags"], "retrieval": diagnostics})
        if len(out) < limit:
            clause = " OR ".join("instr(lower(json_extract(p.payload,'$.title') || ' ' || json_extract(p.payload,'$.abstract')),lower(?))>0" for _ in terms)
            metadata = c.execute("SELECT p.id FROM papers p JOIN paper_topics pt ON pt.paper_id=p.id WHERE pt.topic_id=? AND pt.state!='dismissed' AND (?='' OR p.id=?) AND (" + clause + ") ORDER BY p.id LIMIT ?", (tid, paper_id, paper_id, *terms, limit))
            seen = {r["paper_id"] for r in out}
            for r in metadata:
                if r[0] in seen or len(out) >= limit:
                    continue
                p = _paper(c, tid, r[0])
                out.append({"id": "paper:" + p["id"], "paper_id": p["id"], "title": p["title"], "doi": p["doi"],
                            "version_id": None, "page": None, "section": "abstract metadata", "text": p["abstract"],
                            "level": p["level"], "trust": "untrusted", "rank": None, "status": "abstract_metadata_not_full_text_verified",
                            "flags": p["flags"], "retrieval": diagnostics})
    from backend.research_engines.workspaces import search as artifact_search
    return out if paper_id else (out + artifact_search(tid, query, min(5, limit)))[:limit]


def import_legacy(tid: str) -> dict:
    from backend.knowledge.library import load_library
    return ingest(tid, [{**r, "source": "legacy_library"} for r in load_library().values()])


def cite_key(pid: str) -> str:
    """The BibTeX key of a topic paper: the same in the bibliography, the writer's evidence and the citation check."""
    return "skb_" + pid.replace("-", "")[:12]


def bibliography(tid: str) -> str:
    from backend.knowledge.library import build_bibtex
    with S.db() as c:
        S.topic(c, tid)
        rows = c.execute("SELECT paper_id FROM paper_topics WHERE topic_id=? AND state='accepted'", (tid,))
        entries = [{**_paper(c, tid, r[0]), "key": cite_key(r[0]), "entry_type": "article"} for r in rows]
    return build_bibtex(entries)
