"""Append-only, hash-linked revisions. Detects tampering; not a substitute for OS access control."""
import hashlib
import json
from backend.knowledge import research_store as S


def digest(value) -> str:
    return hashlib.sha256(S.dumps(value).encode()).hexdigest()


def append(c, tid: str, entity: str, kind: str, payload: dict):
    from backend.core.telemetry import redact
    previous = c.execute("SELECT hash FROM decision_ledger ORDER BY seq DESC LIMIT 1").fetchone()
    item = {"topic_id":tid, "entity_id":entity, "kind":kind, "at":S.now(),
            "payload":json.loads(redact(S.dumps(payload))), "previous_hash":previous[0] if previous else ""}
    value = digest(item)
    c.execute("INSERT INTO decision_ledger(topic_id,entity_id,kind,at,payload,previous_hash,hash) VALUES(?,?,?,?,?,?,?)",
              (tid,entity,kind,item["at"],S.dumps(item["payload"]),item["previous_hash"],value))
    return value


def export(tid: str) -> dict:
    with S.db() as c:
        S.topic(c, tid)
        previous, valid, items = "", True, []
        for r in c.execute("SELECT * FROM decision_ledger ORDER BY seq"):
            item = {k:r[k] for k in ("topic_id","entity_id","kind","at","previous_hash")}
            item["payload"] = json.loads(r["payload"])
            valid &= r["previous_hash"] == previous and digest(item) == r["hash"]
            previous = r["hash"]
            if r["topic_id"] == tid:
                items.append({"seq":r["seq"], **item, "hash":r["hash"]})
        return {"events":items,"project_chain_valid":bool(valid),"project_head_hash":previous,
                "limitations":"Hash-linked local ledger; an OS administrator can replace the entire database. Retain independent backups."}
