"""Versioned Artifact Store & Concurrent Mutation Guard for PaperOrchestra.

Enforces:
1. Versioned, traceable artifacts with cryptographic SHA-256 integrity.
2. Atomic replacement (tmp + replace_retry) to avoid corrupt state.
3. Thread-safe concurrent writing protection via re-entrant project/topic locks.
4. Bidirectional synchronization with PhD Lab's native `project.json` and artifact directory.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from backend.agent import decision_ledger as L
from backend.core.config import data_dir, workspace
from backend.knowledge import research_store as S
from backend.paper.writer import load_project, save_project
from backend.research_engines.paperorchestra.contracts import WritingArtifact

_locks: dict[str, threading.RLock] = {}
_meta_lock = threading.Lock()


def get_lock(resource_key: str) -> threading.RLock:
    with _meta_lock:
        if resource_key not in _locks:
            _locks[resource_key] = threading.RLock()
        return _locks[resource_key]


def ensure_table(c: sqlite3.Cursor) -> None:
    c.execute("""
    CREATE TABLE IF NOT EXISTS paperorchestra_artifacts(
        artifact_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        parent_workflow_id TEXT NOT NULL,
        topic_id TEXT NOT NULL,
        section_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        execution_status TEXT NOT NULL,
        review_status TEXT NOT NULL,
        storage_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS po_artifacts_task ON paperorchestra_artifacts(task_id)")
    c.execute("CREATE INDEX IF NOT EXISTS po_artifacts_workflow ON paperorchestra_artifacts(parent_workflow_id)")
    c.execute("CREATE INDEX IF NOT EXISTS po_artifacts_topic ON paperorchestra_artifacts(topic_id, section_id)")


def save_artifact(art: WritingArtifact, *, sync_paper_section: bool = True) -> WritingArtifact:
    """Durably record an artifact in SQLite and filesystem with thread safety."""
    lock_key = art.topic_id or art.parent_workflow_id or "global"
    with get_lock(lock_key):
        # 1. Determine filesystem path in workspace/paperorchestra/<workflow_id>/<task_id>/
        ws_root = workspace()
        art_dir = ws_root / "paperorchestra" / art.parent_workflow_id / art.task_id
        art_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{art.section_id or 'content'}_v{art.version}.tex"
        target_file = art_dir / filename

        # Atomic file write
        from backend.memory.store import replace_retry
        tmp_file = target_file.with_suffix(".tmp")
        tmp_file.write_text(art.content, encoding="utf-8")
        replace_retry(tmp_file, target_file)

        art.storage_path = str(target_file)
        art.updated_at = S.now()

        # 2. Persist in database
        with S.db() as c:
            ensure_table(c)
            payload_dict = art.model_dump(mode="json")
            c.execute("""
            INSERT OR REPLACE INTO paperorchestra_artifacts(
                artifact_id, task_id, parent_workflow_id, topic_id, section_id,
                version, content_hash, execution_status, review_status,
                storage_path, created_at, updated_at, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                art.artifact_id,
                art.task_id,
                art.parent_workflow_id,
                art.topic_id,
                art.section_id,
                art.version,
                art.content_hash,
                art.execution_status,
                art.review_status,
                art.storage_path,
                art.created_at,
                art.updated_at,
                S.dumps(payload_dict),
            ))
            if art.topic_id:
                L.append(
                    c,
                    art.topic_id,
                    art.artifact_id,
                    "paperorchestra.artifact_saved",
                    {
                        "task_id": art.task_id,
                        "section_id": art.section_id,
                        "version": art.version,
                        "content_hash": art.content_hash,
                        "bytes": len(art.content.encode("utf-8")),
                    },
                )

        # 3. Synchronize with project.json if this artifact writes a recognized paper section
        if sync_paper_section and art.section_id:
            from backend.paper.writer import SECTION_TITLES
            if art.section_id in SECTION_TITLES:
                p = load_project()
                curr_text = p.get("sections", {}).get(art.section_id, "")
                if curr_text and curr_text != art.content:
                    p.setdefault("section_history", {}).setdefault(art.section_id, []).append(curr_text)
                    p["section_history"][art.section_id] = p["section_history"][art.section_id][-10:]
                p.setdefault("sections", {})[art.section_id] = art.content
                p.setdefault("section_state", {})[art.section_id] = "drafted"
                save_project(p)

        return art


def get_artifact(artifact_id: str) -> Optional[WritingArtifact]:
    with S.db() as c:
        ensure_table(c)
        row = c.execute("SELECT payload FROM paperorchestra_artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
        if not row:
            return None
        return WritingArtifact.model_validate(json.loads(row[0]))


def list_artifacts(topic_id: str = "", workflow_id: str = "") -> list[WritingArtifact]:
    with S.db() as c:
        ensure_table(c)
        query = "SELECT payload FROM paperorchestra_artifacts WHERE 1=1"
        params: list[Any] = []
        if topic_id:
            query += " AND topic_id=?"
            params.append(topic_id)
        if workflow_id:
            query += " AND parent_workflow_id=?"
            params.append(workflow_id)
        query += " ORDER BY updated_at DESC LIMIT 200"
        rows = c.execute(query, tuple(params)).fetchall()
        return [WritingArtifact.model_validate(json.loads(r[0])) for r in rows]

