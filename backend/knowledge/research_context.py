"""Scoped source resolution; scholarly statements always retain untrusted provenance."""
import json

from backend.knowledge import corpus, research_store as S


def resolve(tid: str, sid: str, expanded: bool = False) -> dict | None:
    from backend.agent.project_context import src
    kind, _, key = sid.partition(":")
    try:
        if kind=="claim":
            from backend.knowledge import governance
            claim=governance.get(tid,key)
            if claim["status"]=="human_approved":claim=governance.evaluate(tid,key)
            text=f"Scientific claim {key}; workflow status {claim['status']} (not universal scientific validity).\n{claim['payload']['text']}\nEvidence IDs: {[e['payload']['source_id'] for e in claim['evidence']]}"
            return src(sid,"scientific_claim","Claim "+key,text,"untrusted","explicitly selected claim with review status")
        if kind == "paper":
            p = corpus.paper(tid, key)
            text = f"{p['title']} | DOI {p['doi'] or 'unknown'} | L{p['level']} | flags {p['flags']}\nAbstract metadata (not full-text verification):\n{p['abstract']}"
            for v in p["versions"]:
                text += f"\nVersion {v['id']} ({v['source']}, {v['version']}), source {v['url']}"
            if expanded:
                with S.db() as c:
                    rows = c.execute("SELECT ch.* FROM chunks ch JOIN versions v ON v.id=ch.version_id WHERE v.paper_id=? LIMIT 8", (key,))
                    for r in rows:
                        text += f"\n[evidence:{r['id']}] version {r['version_id']}, page {r['page']}: {r['text']}"
            return src(sid, "scientific_paper", p["title"], text, "untrusted", "selected topic paper")
        if kind == "evidence":
            with S.db() as c:
                row = c.execute("SELECT ch.*,v.paper_id FROM chunks ch JOIN versions v ON v.id=ch.version_id "
                                "JOIN paper_topics pt ON pt.paper_id=v.paper_id WHERE ch.id=? AND pt.topic_id=?", (key, tid)).fetchone()
                if not row:
                    return None
                p = corpus._paper(c, tid, row["paper_id"])
                return src(sid, "scientific_evidence", p["title"], f"{p['title']}; DOI {p['doi']}; version {row['version_id']}; page {row['page']}; L{p['level']}; flags {p['flags']}\n{row['text']}", "untrusted", "page evidence")
        if kind == "artifact":
            from backend.research_engines.workspaces import artifact_text
            r = artifact_text(tid, key)
            return src(sid, "engine_artifact", r["title"], r["text"], "untrusted", "selected observed artifact")
    except ValueError:
        return None
    return None


def validate_sources(tid: str, ids: list):
    for sid in ids:
        if sid.startswith("att:"):
            continue  # Explicit uploads use the existing project attachment resolver.
        if not resolve(tid, sid):
            raise ValueError("Selected source is unavailable or outside this topic: " + sid)


def finding(tid: str, text: str, refs: list[str]) -> dict:
    if not text.strip() or not refs or len(refs) > 30:
        raise ValueError("Finding requires text and 1–30 source references")
    validate_sources(tid, refs)
    if any(r.startswith("att:") for r in refs):
        raise ValueError("Use registered paper/evidence/artifact references for durable findings")
    with S.db() as c:
        S.topic(c, tid)
        fid = S.uid()
        payload = {"text": text[:16000], "source_evidence_ids": refs, "created": S.now(), "origin": "proposal", "review_status": "pending"}
        c.execute("INSERT INTO findings VALUES(?,?,?,?)", (fid, tid, "pending", S.dumps(payload)))
        S.event(c, tid, "finding.proposed", {"finding_id": fid, **payload})
        return {"id": fid, "status": "pending", **payload}


def findings(tid: str) -> list:
    with S.db() as c:
        S.topic(c, tid)
        return [{"id": r["id"], "status": r["status"], **json.loads(r["payload"])} for r in c.execute("SELECT * FROM findings WHERE topic_id=?", (tid,))]


def review_finding(tid: str, fid: str, approve: bool, note: str) -> dict:
    if not note.strip():
        raise ValueError("A researcher review note is required")
    with S.db() as c:
        r = c.execute("SELECT * FROM findings WHERE id=? AND topic_id=?", (fid, tid)).fetchone()
        if not r or r["status"] != "pending":
            raise ValueError("Pending finding not found in this topic")
        p = json.loads(r["payload"])
        # Source validity checked before approval, without writing global memory.
    validate_sources(tid, p["source_evidence_ids"])
    with S.db() as c:
        status = "approved" if approve else "rejected"
        p.update(review_status=status, reviewed_at=S.now(), reviewed_by="researcher", review_note=note[:8000])
        changed = c.execute("UPDATE findings SET status=?,payload=? WHERE id=? AND status='pending'", (status, S.dumps(p), fid))
        if changed.rowcount != 1:
            raise ValueError("Finding has already been reviewed")
        S.event(c, tid, "finding." + status, {"finding_id": fid, **p})
    return {"id": fid, "status": status, **p}
