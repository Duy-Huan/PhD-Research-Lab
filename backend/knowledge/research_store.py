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
 engine TEXT NOT NULL CHECK(engine IN ('openscience','feynman')), path TEXT UNIQUE NOT NULL, payload TEXT NOT NULL);
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
"""
SCHEMA_VERSION = 2
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
            if version < SCHEMA_VERSION:
                c.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            c.execute("INSERT OR IGNORE INTO meta VALUES('schema',?)", (str(SCHEMA_VERSION),))
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
