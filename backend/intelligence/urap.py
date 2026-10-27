"""Module A — Unified Research Artifact Protocol (URAP v6.4.2).

Normalizes and traces research outputs across native research roles, historical software outputs,
Claude Code/Codex, Python/Docker, and Figure Studio with content-addressed
SHA-256 verification and cross-engine lineage graphs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.agent import decision_ledger as L
from backend.knowledge import research_store as S

ARTIFACT_TYPES = {
    "paper_metadata",
    "paper_pdf",
    "literature_report",
    "citation_manifest",
    "hypothesis",
    "research_plan",
    "decision_record",
    "review_report",
    "source_code",
    "code_diff",
    "notebook",
    "execution_log",
    "environment_manifest",
    "dataset_reference",
    "experiment_config",
    "experiment_result",
    "metrics_table",
    "model_checkpoint",
    "figure_spec",
    "figure_source",
    "figure_render",
    "figure_integrity_report",
    "manuscript_draft",
    "research_report",
    "reproducibility_pack",
}

VERIFICATION_STATES = {
    "unverified",
    "auto_screened",
    "user_verified",
    "rejected",
    "superseded",
    "stale",
}


class ArtifactCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(min_length=1, max_length=120)
    mission_id: str = Field(default="", max_length=120)
    task_id: str = Field(default="", max_length=120)
    artifact_type: str = Field(default="experiment_result", max_length=80)
    producer_runtime: str = Field(default="phdlab", max_length=80)
    producer_version: str = Field(default="6.4.2", max_length=80)
    session_id: str = Field(default="", max_length=120)
    agent_id: str = Field(default="researcher", max_length=120)
    uri: str = Field(default="", max_length=2000)
    media_type: str = Field(default="application/json", max_length=120)
    content_text: str = Field(default="", max_length=200000)
    sha256: str = Field(default="", max_length=128)
    byte_size: int = Field(default=0, ge=0)
    input_artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    experiment_id: str = Field(default="", max_length=120)
    code_revision: str = Field(default="", max_length=120)
    verification_status: Literal["unverified", "auto_screened", "user_verified", "rejected", "superseded", "stale"] = "unverified"
    metadata: dict = Field(default_factory=dict)


def register_artifact(
    *,
    topic_id: str,
    artifact_type: str,
    sha256: str = "",
    byte_size: int = 0,
    uri: str = "",
    media_type: str = "application/json",
    content_text: str = "",
    mission_id: str = "",
    task_id: str = "",
    producer_runtime: str = "phdlab",
    producer_version: str = "6.4.2",
    session_id: str = "",
    agent_id: str = "researcher",
    input_artifact_ids: list[str] | None = None,
    experiment_id: str = "",
    code_revision: str = "",
    verification_status: str = "unverified",
    metadata: dict | None = None,
) -> dict:
    """Idempotently register a normalized URAP 1.0.0 artifact envelope and its lineage edges."""
    S.get_topic(topic_id)
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"Unsupported artifact_type: {artifact_type}")
    if verification_status not in VERIFICATION_STATES:
        raise ValueError(f"Unsupported verification_status: {verification_status}")

    # Resolve file hash if URI points to a local file inside project
    file_path: Path | None = None
    if uri and not uri.startswith(("artifact://", "http://", "https://")):
        p = Path(uri)
        if p.is_file():
            file_path = p.resolve()
            raw = file_path.read_bytes()
            sha256 = hashlib.sha256(raw).hexdigest()
            byte_size = len(raw)
    if not sha256:
        raw_bytes = content_text.encode("utf-8") if content_text else S.dumps({"uri": uri, "meta": metadata or {}}).encode("utf-8")
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        byte_size = byte_size or len(raw_bytes)

    canonical_uri = str(file_path) if file_path else (uri or f"artifact://sha256/{sha256}")
    pid = S.project_id()
    inputs = list(dict.fromkeys(input_artifact_ids or []))

    # Validate that any referenced parent artifact in research_artifacts belongs to the same topic
    with S.db() as c:
        for parent_id in inputs:
            prow = c.execute("SELECT topic_id FROM research_artifacts WHERE id=?", (parent_id,)).fetchone()
            if prow and prow["topic_id"] != topic_id:
                raise ValueError(f"Cross-topic lineage reference forbidden without Charter grant: {parent_id}")

        # Check idempotent existing record for same (topic_id, task_id, artifact_type, sha256)
        existing = c.execute(
            "SELECT * FROM research_artifacts WHERE topic_id=? AND task_id=? AND artifact_type=? AND sha256=?",
            (topic_id, task_id, artifact_type, sha256),
        ).fetchone()
        at = S.now()
        if existing:
            aid = existing["id"]
            envelope = json.loads(existing["payload"])
            envelope["deduplicated"] = True
        else:
            aid = f"art-{S.uid()[:10]}"
            envelope = {
                "schema_version": "1.0.0",
                "artifact_id": aid,
                "artifact_type": artifact_type,
                "project_id": pid,
                "topic_id": topic_id,
                "mission_id": mission_id,
                "task_id": task_id,
                "producer": {
                    "runtime_id": producer_runtime,
                    "runtime_version": producer_version,
                    "session_id": session_id,
                    "agent_id": agent_id,
                },
                "content": {
                    "uri": canonical_uri,
                    "media_type": media_type,
                    "byte_size": byte_size,
                    "sha256": sha256,
                    "hash_algorithm": "sha256",
                },
                "lineage": {
                    "input_artifact_ids": inputs,
                    "experiment_id": experiment_id,
                    "code_revision": code_revision or None,
                },
                "verification": {
                    "status": verification_status,
                    "verifier_task_id": None,
                    "evidence_artifact_ids": [],
                },
                "metadata": metadata or {},
                "created_at": at,
            }
            c.execute(
                "INSERT INTO research_artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (aid, pid, topic_id, mission_id, task_id, artifact_type, sha256, byte_size, verification_status, 1, S.dumps(envelope), at),
            )
            L.append(
                c,
                topic_id,
                aid,
                "urap.artifact_registered",
                {"artifact_type": artifact_type, "sha256": sha256, "producer": producer_runtime, "task_id": task_id},
            )

        for parent_id in inputs:
            c.execute(
                "INSERT OR IGNORE INTO artifact_edges VALUES(?,?,?,?,?,?)",
                (S.uid(), topic_id, parent_id, aid, "derived_from", at),
            )

    return get_artifact(aid, topic_id)


def get_artifact(artifact_id: str, topic_id: str = "") -> dict:
    with S.db() as c:
        row = c.execute(
            "SELECT * FROM research_artifacts WHERE id=? AND (?='' OR topic_id=?)",
            (artifact_id, topic_id, topic_id),
        ).fetchone()
        if not row:
            raise ValueError("Artifact not found in this Topic/project")
        env = json.loads(row["payload"])
        env["verification"]["status"] = row["verification_status"]
        return env


def list_artifacts(topic_id: str, mission_id: str = "", task_id: str = "", artifact_type: str = "") -> list[dict]:
    S.get_topic(topic_id)
    with S.db() as c:
        rows = c.execute(
            "SELECT id, verification_status, payload FROM research_artifacts "
            "WHERE topic_id=? AND (?='' OR mission_id=?) AND (?='' OR task_id=?) AND (?='' OR artifact_type=?) "
            "ORDER BY created_at DESC LIMIT 250",
            (topic_id, mission_id, mission_id, task_id, task_id, artifact_type, artifact_type),
        ).fetchall()
        out = []
        for r in rows:
            env = json.loads(r["payload"])
            env["verification"]["status"] = r["verification_status"]
            out.append(env)
        return out


def lineage_graph(artifact_id: str, topic_id: str = "") -> dict:
    """Return upstream ancestors and downstream descendants for an artifact."""
    root = get_artifact(artifact_id, topic_id)
    tid = root["topic_id"]
    with S.db() as c:
        edges = [
            dict(r)
            for r in c.execute(
                "SELECT parent_artifact_id, child_artifact_id, relation, created_at FROM artifact_edges WHERE topic_id=?",
                (tid,),
            )
        ]
        nodes_map = {root["artifact_id"]: root}
        visited = {root["artifact_id"]}
        queue = [root["artifact_id"]]
        relevant_edges = []
        seen_edges = set()
        while queue:
            cur = queue.pop(0)
            for e in edges:
                if e["parent_artifact_id"] == cur or e["child_artifact_id"] == cur:
                    edge_key = (e["parent_artifact_id"], e["child_artifact_id"], e["relation"])
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        relevant_edges.append(e)
                    for neighbor in (e["parent_artifact_id"], e["child_artifact_id"]):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                            nrow = c.execute(
                                "SELECT verification_status, payload FROM research_artifacts WHERE id=? AND topic_id=?",
                                (neighbor, tid),
                            ).fetchone()
                            if nrow:
                                nenv = json.loads(nrow["payload"])
                                nenv["verification"]["status"] = nrow["verification_status"]
                                nodes_map[neighbor] = nenv
                            else:
                                nodes_map[neighbor] = {"artifact_id": neighbor, "external_ref": True}
    return {
        "root_artifact_id": artifact_id,
        "topic_id": tid,
        "nodes": list(nodes_map.values()),
        "edges": relevant_edges,
    }


def verify_integrity(artifact_id: str, topic_id: str = "") -> dict:
    """Deterministically verify artifact content hash on disk; mark downstream stale if tampered."""
    env = get_artifact(artifact_id, topic_id)
    tid = env["topic_id"]
    uri = env["content"].get("uri", "")
    expected_sha = env["content"].get("sha256", "")
    tampered = False
    detail = "Content-addressed hash verified."

    if uri and not uri.startswith(("artifact://", "http://", "https://")):
        p = Path(uri)
        if not p.is_file():
            tampered = True
            detail = "Backing file is missing on disk."
        else:
            raw = p.read_bytes()
            actual_sha = hashlib.sha256(raw).hexdigest()
            if actual_sha != expected_sha:
                tampered = True
                detail = f"SHA-256 mismatch: expected {expected_sha[:16]}..., got {actual_sha[:16]}..."

    stale_downstream: list[str] = []
    with S.db() as c:
        if tampered:
            c.execute("UPDATE research_artifacts SET verification_status='stale' WHERE id=?", (artifact_id,))
            # Propagate stale status to downstream children
            queue = [artifact_id]
            seen = {artifact_id}
            while queue:
                cur = queue.pop(0)
                children = [
                    r[0]
                    for r in c.execute(
                        "SELECT child_artifact_id FROM artifact_edges WHERE topic_id=? AND parent_artifact_id=?",
                        (tid, cur),
                    )
                ]
                for child_id in children:
                    if child_id not in seen:
                        seen.add(child_id)
                        queue.append(child_id)
                        stale_downstream.append(child_id)
                        c.execute("UPDATE research_artifacts SET verification_status='stale' WHERE id=?", (child_id,))
            L.append(
                c,
                tid,
                artifact_id,
                "urap.integrity_failed",
                {"detail": detail, "stale_downstream": stale_downstream},
            )
        else:
            L.append(c, tid, artifact_id, "urap.integrity_verified", {"sha256": expected_sha})

    return {
        "artifact_id": artifact_id,
        "topic_id": tid,
        "integrity_ok": not tampered,
        "valid": not tampered,
        "status": "stale" if tampered else env["verification"]["status"],
        "detail": detail,
        "stale_downstream": stale_downstream,
        "stale_downstream_artifact_ids": stale_downstream,
        "checked_at": S.now(),
    }
