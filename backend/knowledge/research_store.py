"""Project-scoped scientific corpus and provenance. No writes to trusted memory or library.json."""
from __future__ import annotations

import json
import sqlite3
import uuid
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from backend.core.config import data_dir


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def uid() -> str:
    return str(uuid.uuid4())


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class TopicInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    objectives: str = Field(default="", max_length=8000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    synonyms: list[str] = Field(default_factory=list, max_length=30)
    exclusions: list[str] = Field(default_factory=list, max_length=30)
    sources: list[str] = Field(default_factory=lambda: ["openalex", "arxiv", "semantic_scholar", "crossref"])
    min_year: int = Field(default=2019, ge=1900, le=2100)
    cadence: str = Field(default="manual", pattern="^(off|manual|daily|weekly)$")
    enabled: bool = False
    metadata_limit: int = Field(default=30, ge=1, le=100)
    pdf_limit: int = Field(default=10, ge=0, le=25)
    max_pdf_mb: int = Field(default=25, ge=1, le=30)
    storage_mb: int = Field(default=1024, ge=1, le=102400)
    auto_download: bool = False
    parser: str = Field(default="existing", pattern="^(existing|docling)$")
    archived: bool = False


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS topics(id TEXT PRIMARY KEY, payload TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS papers(id TEXT PRIMARY KEY, payload TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS aliases(alias TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id));
CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id),
 signature TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(paper_id,signature));
CREATE TABLE IF NOT EXISTS paper_topics(topic_id TEXT NOT NULL REFERENCES topics(id), paper_id TEXT NOT NULL REFERENCES papers(id),
 level INTEGER NOT NULL DEFAULT 0 CHECK(level BETWEEN 0 AND 4), state TEXT NOT NULL DEFAULT 'candidate',
 payload TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(topic_id,paper_id));
CREATE TABLE IF NOT EXISTS documents(sha256 TEXT PRIMARY KEY, bytes INTEGER NOT NULL, parser TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'downloaded', payload TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS version_documents(version_id TEXT PRIMARY KEY REFERENCES versions(id),
 sha256 TEXT NOT NULL REFERENCES documents(sha256));
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES versions(id),
 page INTEGER, section TEXT NOT NULL, text TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS chunks_version ON chunks(version_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_search USING fts5(chunk_id UNINDEXED,text);
CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topics(id),
 engine TEXT NOT NULL CHECK(engine IN ('openscience','feynman','opencode')), path TEXT UNIQUE NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifact_versions(id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 path TEXT NOT NULL, signature TEXT NOT NULL, version INTEGER NOT NULL, sha256 TEXT, bytes INTEGER NOT NULL,
 available INTEGER NOT NULL DEFAULT 1, observed TEXT NOT NULL, payload TEXT NOT NULL,
 UNIQUE(workspace_id,path,version));
CREATE INDEX IF NOT EXISTS artifact_workspace ON artifact_versions(workspace_id,path,version);
CREATE VIRTUAL TABLE IF NOT EXISTS artifact_search USING fts5(artifact_id UNINDEXED,text);
CREATE TABLE IF NOT EXISTS checkpoints(workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, event_key TEXT UNIQUE NOT NULL,
 topic_id TEXT NOT NULL REFERENCES topics(id), workspace_id TEXT REFERENCES workspaces(id),
 type TEXT NOT NULL, observed TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_topic ON events(topic_id,observed);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topics(id),
 kind TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, payload TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs(topic_id,kind) WHERE status IN ('queued','running','cancelling');
CREATE TABLE IF NOT EXISTS findings(id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topics(id),
 status TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topics(id),status TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mission_tasks(mission_id TEXT NOT NULL REFERENCES missions(id),id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(mission_id,id));
CREATE TABLE IF NOT EXISTS mission_attempts(key TEXT PRIMARY KEY,mission_id TEXT NOT NULL REFERENCES missions(id),task_id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decision_ledger(seq INTEGER PRIMARY KEY AUTOINCREMENT,topic_id TEXT NOT NULL REFERENCES topics(id),entity_id TEXT NOT NULL,kind TEXT NOT NULL,at TEXT NOT NULL,payload TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT UNIQUE NOT NULL);
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON decision_ledger BEGIN SELECT RAISE(ABORT,'ledger is append only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON decision_ledger BEGIN SELECT RAISE(ABORT,'ledger is append only'); END;
CREATE TABLE IF NOT EXISTS experiment_protocols(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),parent_id TEXT,revision INTEGER NOT NULL,digest TEXT NOT NULL,payload TEXT NOT NULL,approval TEXT);
CREATE TABLE IF NOT EXISTS dataset_versions(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),fingerprint TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(topic_id,fingerprint));
CREATE TABLE IF NOT EXISTS experiment_runs(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),protocol_id TEXT NOT NULL REFERENCES experiment_protocols(id),mission_id TEXT NOT NULL REFERENCES missions(id),approval_nonce TEXT UNIQUE NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiment_trials(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES experiment_runs(id),trial_key TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(run_id,trial_key));
CREATE TABLE IF NOT EXISTS scientific_claims(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),parent_id TEXT,status TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claim_evidence(id TEXT PRIMARY KEY,claim_id TEXT NOT NULL REFERENCES scientific_claims(id),payload TEXT NOT NULL,hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS evidence_no_update BEFORE UPDATE ON claim_evidence BEGIN SELECT RAISE(ABORT,'evidence snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON claim_evidence BEGIN SELECT RAISE(ABORT,'evidence snapshots are immutable'); END;
CREATE TABLE IF NOT EXISTS claim_checks(id TEXT PRIMARY KEY,claim_id TEXT NOT NULL REFERENCES scientific_claims(id),at TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS citation_receipts(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),doi TEXT NOT NULL,payload TEXT NOT NULL,at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS project_charters(id TEXT PRIMARY KEY,digest TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS charter_usage(charter_id TEXT PRIMARY KEY REFERENCES project_charters(id),reasoning_calls INTEGER NOT NULL DEFAULT 0,active_seconds REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS provider_breakers(provider TEXT PRIMARY KEY,until_at TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS task_handoffs(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL REFERENCES missions(id),topic_id TEXT NOT NULL REFERENCES topics(id),task_id TEXT NOT NULL,dependency_id TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(mission_id,task_id,dependency_id));
CREATE TABLE IF NOT EXISTS workstream_usage(mission_id TEXT NOT NULL REFERENCES missions(id),team_id TEXT NOT NULL,reasoning_calls INTEGER NOT NULL DEFAULT 0,active_seconds REAL NOT NULL DEFAULT 0,artifact_bytes INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(mission_id,team_id));
CREATE TABLE IF NOT EXISTS collaboration_messages(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL REFERENCES missions(id),topic_id TEXT NOT NULL REFERENCES topics(id),source_task TEXT NOT NULL,target_task TEXT NOT NULL,status TEXT NOT NULL,digest TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(mission_id,source_task,target_task));
CREATE TABLE IF NOT EXISTS handoff_receipts(message_id TEXT PRIMARY KEY REFERENCES collaboration_messages(id),receiver_team TEXT NOT NULL,payload TEXT NOT NULL,at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS collaboration_disputes(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL REFERENCES missions(id),topic_id TEXT NOT NULL REFERENCES topics(id),status TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS canonical_outputs(topic_id TEXT NOT NULL REFERENCES topics(id),output_key TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(topic_id,output_key));
CREATE TABLE IF NOT EXISTS canonical_revisions(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),output_key TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,UNIQUE(topic_id,output_key,revision));
CREATE TRIGGER IF NOT EXISTS message_snapshot_immutable BEFORE UPDATE OF id,mission_id,topic_id,source_task,target_task,digest,payload ON collaboration_messages BEGIN SELECT RAISE(ABORT,'work orders are immutable'); END;
CREATE TRIGGER IF NOT EXISTS receipt_immutable BEFORE UPDATE ON handoff_receipts BEGIN SELECT RAISE(ABORT,'receipts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS canonical_history_immutable BEFORE UPDATE ON canonical_revisions BEGIN SELECT RAISE(ABORT,'canonical history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS canonical_history_no_delete BEFORE DELETE ON canonical_revisions BEGIN SELECT RAISE(ABORT,'canonical history is append only'); END;
CREATE TRIGGER IF NOT EXISTS receipt_no_delete BEFORE DELETE ON handoff_receipts BEGIN SELECT RAISE(ABORT,'receipts are append only'); END;
CREATE TRIGGER IF NOT EXISTS message_no_delete BEFORE DELETE ON collaboration_messages BEGIN SELECT RAISE(ABORT,'work orders are append only'); END;
CREATE TRIGGER IF NOT EXISTS task_handoff_immutable BEFORE UPDATE ON task_handoffs BEGIN SELECT RAISE(ABORT,'handoff snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS charter_immutable BEFORE UPDATE ON project_charters BEGIN SELECT RAISE(ABORT,'create a new charter revision'); END;
CREATE TRIGGER IF NOT EXISTS protocol_snapshot_immutable BEFORE UPDATE OF id,payload,digest,topic_id,parent_id,revision ON experiment_protocols BEGIN SELECT RAISE(ABORT,'protocol snapshot is immutable'); END;
CREATE TRIGGER IF NOT EXISTS claim_text_immutable BEFORE UPDATE ON scientific_claims WHEN NEW.id IS NOT OLD.id OR NEW.topic_id IS NOT OLD.topic_id OR NEW.parent_id IS NOT OLD.parent_id OR json_extract(NEW.payload,'$.text') IS NOT json_extract(OLD.payload,'$.text') OR json_extract(NEW.payload,'$.kind') IS NOT json_extract(OLD.payload,'$.kind') BEGIN SELECT RAISE(ABORT,'amend the claim through a new revision'); END;
CREATE TABLE IF NOT EXISTS figures(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),mission_id TEXT,title TEXT NOT NULL,category TEXT NOT NULL,current_version INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'draft',payload TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS figure_versions(id TEXT PRIMARY KEY,figure_id TEXT NOT NULL REFERENCES figures(id),topic_id TEXT NOT NULL REFERENCES topics(id),version INTEGER NOT NULL,spec_sha256 TEXT NOT NULL,script_sha256 TEXT NOT NULL,data_sha256 TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(figure_id,version));
CREATE TABLE IF NOT EXISTS figure_verifications(id TEXT PRIMARY KEY,figure_id TEXT NOT NULL REFERENCES figures(id),version INTEGER NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS figure_version_no_update BEFORE UPDATE ON figure_versions BEGIN SELECT RAISE(ABORT,'figure versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS figure_version_no_delete BEFORE DELETE ON figure_versions BEGIN SELECT RAISE(ABORT,'figure versions are append only'); END;
CREATE TABLE IF NOT EXISTS opencode_sessions(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),mission_id TEXT,task_id TEXT,workspace_id TEXT,native_session_id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opencode_events(id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES opencode_sessions(id),topic_id TEXT NOT NULL REFERENCES topics(id),fingerprint TEXT UNIQUE NOT NULL,seq INTEGER NOT NULL,event_type TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opencode_approvals(id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES opencode_sessions(id),topic_id TEXT NOT NULL REFERENCES topics(id),action TEXT NOT NULL,risk TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_artifacts(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,topic_id TEXT NOT NULL REFERENCES topics(id),mission_id TEXT,task_id TEXT,artifact_type TEXT NOT NULL,sha256 TEXT NOT NULL,byte_size INTEGER NOT NULL,verification_status TEXT NOT NULL DEFAULT 'unverified',version INTEGER NOT NULL DEFAULT 1,payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifact_edges(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),parent_artifact_id TEXT NOT NULL,child_artifact_id TEXT NOT NULL,relation TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(parent_artifact_id,child_artifact_id,relation));
CREATE TABLE IF NOT EXISTS research_trace_events(id TEXT PRIMARY KEY,trace_id TEXT NOT NULL,span_id TEXT NOT NULL,parent_span_id TEXT,project_id TEXT NOT NULL,topic_id TEXT NOT NULL,mission_id TEXT,team_id TEXT,task_id TEXT,runtime_id TEXT,event_type TEXT NOT NULL,severity TEXT NOT NULL DEFAULT 'info',fingerprint TEXT UNIQUE NOT NULL,seq INTEGER NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS context_packs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,topic_id TEXT NOT NULL REFERENCES topics(id),mission_id TEXT,task_id TEXT NOT NULL,role TEXT NOT NULL,digest TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS routing_decisions(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),mission_id TEXT,task_id TEXT NOT NULL,selected_engine TEXT NOT NULL,cost_policy TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reproducibility_exports(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),mission_id TEXT NOT NULL,bundle_sha256 TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_manifests(id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES topics(id),mission_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
"""
SCHEMA_VERSION = 8
_schema_lock = threading.RLock()


def safe_child(root: Path, *parts: str) -> Path:
    """Reject links/junctions at every existing component, including dangling ones."""
    root = Path(root).absolute()
    result = root.joinpath(*parts)
    if not result.is_relative_to(root) or ".." in result.parts:
        raise ValueError("Path escapes its owner")
    for p in (result, *result.parents):
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            raise ValueError("Linked paths are not allowed")
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes its owner")
    return result


def store_dir() -> Path:
    p = safe_child(data_dir(), "workspace", "research")
    p.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def db():
    path = safe_child(store_dir(), "research.sqlite3")
    c = sqlite3.connect(path, timeout=20)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA foreign_keys=ON")
        with _schema_lock:
            version = c.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("Research store was created by a newer version; upgrade PhD Lab before opening it")
            if 0 < version < SCHEMA_VERSION:
                backup = safe_child(store_dir(), f"research.v{version}.sqlite3.bak")
                if not backup.exists():
                    with sqlite3.connect(backup) as target:
                        c.backup(target)
            c.executescript(SCHEMA)
            ws_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='workspaces'").fetchone()
            if ws_sql and "'opencode'" not in (ws_sql[0] or ""):
                c.executescript("""
                PRAGMA foreign_keys=OFF;
                ALTER TABLE workspaces RENAME TO _workspaces_v7;
                CREATE TABLE workspaces(id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES topics(id),
                 engine TEXT NOT NULL CHECK(engine IN ('openscience','feynman','opencode')), path TEXT UNIQUE NOT NULL, payload TEXT NOT NULL);
                INSERT INTO workspaces SELECT * FROM _workspaces_v7;
                DROP TABLE _workspaces_v7;
                PRAGMA foreign_keys=ON;
                """)
            if version < SCHEMA_VERSION:
                c.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            c.execute("INSERT INTO meta VALUES('schema',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))
            c.execute("INSERT OR IGNORE INTO meta VALUES('project_id',?)", (uid(),))
            c.commit()
        c.execute("BEGIN IMMEDIATE")
        yield c
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()


def project_id() -> str:
    with db() as c:
        return c.execute("SELECT value FROM meta WHERE key='project_id'").fetchone()[0]


def topic(c, tid: str) -> dict:
    row = c.execute("SELECT * FROM topics WHERE id=?", (tid,)).fetchone()
    if not row:
        raise ValueError("Topic not found in this project")
    return {**json.loads(row["payload"]), "id": row["id"], "created": row["created"], "updated": row["updated"]}


def topics() -> list:
    with db() as c:
        return [topic(c, r[0]) for r in c.execute("SELECT id FROM topics ORDER BY created")]


def save_topic(body: TopicInput, tid: str = "") -> dict:
    from backend.knowledge.sources import PROVIDER_IDS
    data = body.model_dump()
    data["title"] = data["title"].strip()
    if not data["title"] or any(s not in PROVIDER_IDS for s in data["sources"]) or not data["sources"]:
        raise ValueError("Topic title and supported sources are required")
    for field in ("keywords", "synonyms", "exclusions"):
        data[field] = list(dict.fromkeys(s.strip()[:200] for s in data[field] if s.strip()))
    with db() as c:
        old = topic(c, tid) if tid else None
        tid = tid or uid()
        c.execute("INSERT INTO topics VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated",
                  (tid, dumps(data), old["created"] if old else now(), now()))
        if not old:
            from backend.agent import decision_ledger as L
            L.append(c, tid, tid, "topic_created", {"title": data["title"], "sources": data["sources"]})
        return topic(c, tid)


def get_topic(tid: str) -> dict:
    with db() as c:
        return topic(c, tid)


def event(c, tid: str, kind: str, payload: dict, *, key: str = "", wid: str | None = None):
    eid = uid()
    payload = {"project_id": c.execute("SELECT value FROM meta WHERE key='project_id'").fetchone()[0],
               "topic_id": tid, "workspace_id": wid, "captured_at": now(), **payload}
    if wid:
        payload["source_engine"] = c.execute("SELECT engine FROM workspaces WHERE id=?", (wid,)).fetchone()[0]
    c.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?)",
              (eid, key or eid, tid, wid, kind, now(), dumps(payload)))


def timeline(tid: str, limit: int = 100, workspace_id: str = "", kind: str = "") -> list:
    with db() as c:
        topic(c, tid)
        rows = c.execute("SELECT * FROM events WHERE topic_id=? AND (?='' OR workspace_id=?) AND (?='' OR type=?) "
                         "ORDER BY observed DESC LIMIT ?", (tid, workspace_id, workspace_id, kind, kind, min(500, max(1, limit))))
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]
