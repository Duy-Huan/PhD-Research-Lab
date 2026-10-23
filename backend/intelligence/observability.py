"""Module B — Agent Observability & Diagnostics (v6.4.2).

Provides correlated cross-engine spans, structured trace events, secret redaction,
and recovery-gap reporting without requiring any external cloud tracing SaaS.
"""
from __future__ import annotations

import hashlib
import json

from backend.core.telemetry import redact
from backend.knowledge import research_store as S

EVENT_TYPES = {
    "MISSION_STARTED",
    "TASK_QUEUED",
    "TASK_STARTED",
    "TASK_WAITING_APPROVAL",
    "TASK_COMPLETED",
    "TASK_FAILED",
    "TASK_CANCELLED",
    "RUNTIME_AVAILABLE",
    "RUNTIME_DISCONNECTED",
    "RUNTIME_QUOTA_LIMITED",
    "RUNTIME_RECOVERY_GAP",
    "CONTEXT_PACK_BUILT",
    "ROUTING_DECISION",
    "TOOL_EXECUTION",
    "ARTIFACT_REGISTERED",
    "FIGURE_VALIDATED",
    "VERIFICATION_REJECTED",
}


def emit_trace_event(
    *,
    topic_id: str,
    event_type: str,
    mission_id: str = "",
    team_id: str = "",
    task_id: str = "",
    runtime_id: str = "phdlab",
    span_name: str = "task.execute",
    parent_span_id: str = "",
    severity: str = "info",
    payload: dict | None = None,
    dedup_key: str = "",
) -> dict:
    """Record a redacted, deduplicated trace event with correlation IDs."""
    S.get_topic(topic_id)
    pid = S.project_id()
    trace_id = f"trace-{mission_id or topic_id}"
    span_id = f"span-{hashlib.sha256(f'{mission_id}:{task_id}:{span_name}'.encode()).hexdigest()[:12]}"
    clean_payload = json.loads(redact(S.dumps(payload or {})))
    fp_source = dedup_key or f"{trace_id}:{span_id}:{event_type}:{S.dumps(clean_payload)}"
    fp = hashlib.sha256(fp_source.encode("utf-8")).hexdigest()

    with S.db() as c:
        existing = c.execute("SELECT * FROM research_trace_events WHERE fingerprint=?", (fp,)).fetchone()
        if existing:
            return {**dict(existing), "payload": json.loads(existing["payload"]), "deduplicated": True}
        max_seq = c.execute(
            "SELECT coalesce(max(seq), 0) FROM research_trace_events WHERE topic_id=? AND mission_id=?",
            (topic_id, mission_id),
        ).fetchone()[0]
        seq = int(max_seq) + 1
        eid = f"tev-{S.uid()[:10]}"
        at = S.now()
        c.execute(
            "INSERT INTO research_trace_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                eid,
                trace_id,
                span_id,
                parent_span_id,
                pid,
                topic_id,
                mission_id,
                team_id,
                task_id,
                runtime_id,
                event_type,
                severity,
                fp,
                seq,
                S.dumps(clean_payload),
                at,
            ),
        )
        return {
            "id": eid,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "project_id": pid,
            "topic_id": topic_id,
            "mission_id": mission_id,
            "team_id": team_id,
            "task_id": task_id,
            "runtime_id": runtime_id,
            "event_type": event_type,
            "severity": severity,
            "fingerprint": fp,
            "seq": seq,
            "payload": clean_payload,
            "created_at": at,
            "deduplicated": False,
        }


def get_mission_trace(mission_id: str, topic_id: str = "") -> dict:
    """Build correlated Mission Trace tree combining spans, tasks, routing decisions, and artifacts."""
    from backend.agent import missions as M
    from backend.intelligence import urap

    m = M.get(mission_id, topic_id)
    tid = m["topic_id"]
    spec = m["payload"].get("spec") or {}

    with S.db() as c:
        trace_events = [
            {**dict(r), "payload": json.loads(r["payload"])}
            for r in c.execute(
                "SELECT * FROM research_trace_events WHERE topic_id=? AND mission_id=? ORDER BY seq ASC",
                (tid, mission_id),
            )
        ]
        routing_rows = [
            {**dict(r), "payload": json.loads(r["payload"])}
            for r in c.execute(
                "SELECT * FROM routing_decisions WHERE topic_id=? AND mission_id=? ORDER BY created_at DESC",
                (tid, mission_id),
            )
        ]
        ledger_rows = [
            {**dict(r), "payload": json.loads(r["payload"])}
            for r in c.execute(
                "SELECT seq, entity_id, kind, at, payload FROM decision_ledger WHERE topic_id=? AND entity_id=? ORDER BY seq ASC",
                (tid, mission_id),
            )
        ]

    artifacts = urap.list_artifacts(tid, mission_id=mission_id)
    task_spans = []
    for t in m.get("tasks") or []:
        tspec = (t.get("payload") or {}).get("spec") or {}
        tresult = (t.get("payload") or {}).get("result") or {}
        task_spans.append(
            {
                "span_id": f"span-task-{t['id']}",
                "parent_span_id": f"span-mission-{mission_id[:8]}",
                "task_id": t["id"],
                "capability": tspec.get("capability", ""),
                "preferred_engine": tspec.get("preferred_engine", "deterministic"),
                "selected_engine": tresult.get("engine", tspec.get("preferred_engine", "deterministic")),
                "status": t["status"],
                "attempts": (t.get("payload") or {}).get("attempts", 0),
                "depends_on": tspec.get("depends_on") or [],
                "artifacts": tresult.get("artifacts") or [],
                "limitations": tresult.get("limitations") or [],
            }
        )

    recovery_gaps = [e for e in trace_events if e["event_type"] == "RUNTIME_RECOVERY_GAP"]
    if m["status"] == "interrupted" and not recovery_gaps:
        recovery_gaps.append(
            {
                "event_type": "RUNTIME_RECOVERY_GAP",
                "severity": "warning",
                "payload": {"reason": "Mission was interrupted; uncertain admissions require explicit reconciliation."},
            }
        )

    return {
        "trace_id": f"trace-{mission_id}",
        "project_id": S.project_id(),
        "topic_id": tid,
        "mission_id": mission_id,
        "mission_status": m["status"],
        "objective": spec.get("objective", ""),
        "reasoning_calls": m["payload"].get("reasoning_calls", 0),
        "active_seconds": m["payload"].get("active_seconds", 0),
        "blocking_reason": m["payload"].get("blocking_reason", ""),
        "task_spans": task_spans,
        "trace_events": trace_events,
        "routing_decisions": routing_rows,
        "ledger_events": ledger_rows,
        "artifacts": artifacts,
        "recovery_gaps": recovery_gaps,
        "resource_usage": {
            "reasoning_calls": m["payload"].get("reasoning_calls", 0),
            "active_seconds": m["payload"].get("active_seconds", 0),
            "provider_tokens": "unknown",
            "gpu_seconds": 0,
        },
    }
