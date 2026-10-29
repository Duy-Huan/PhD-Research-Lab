"""Long-work continuity checks for qualification (v6.6.4, agent/PLAN_6.6.4_L3.md B4; RQ-07).

A qualification case runs N turns and M process restarts. Before and after each restart the campaign takes snapshot()
of the topic's commitments and calls compare(): nothing approved may be lost or changed, no approval may run a second
experiment, the ledger must stay intact and only grow, and no other project's data may appear. A real restart is a new
process on the same data folder; recover() is what the app runs at start.
"""
from __future__ import annotations

from backend.agent import decision_ledger as L
from backend.knowledge import research_store as S


def snapshot(tid: str) -> dict:
    """Digests of what the topic has committed to, plus what has been measured."""
    from backend.agent import missions as M
    from backend.execution import protocols as P
    missions = {m["id"]: {"plan_digest": m["payload"]["plan_digest"], "approved": bool(m["payload"].get("approval")),
                          "status": m["status"]} for m in M.listing(tid)}
    protocols = {p["id"]: {"digest": p["digest"], "approved": bool(p["approval"])} for p in P.listing(tid)}
    runs = [{"id": r["id"], "nonce": r["approval_nonce"], "status": r["status"]} for r in P.runs(tid)]
    ledger = L.export(tid)
    return {"project_id": S.project_id(), "topic_id": tid, "missions": missions, "protocols": protocols, "runs": runs,
            "ledger_ok": ledger["ok"], "ledger_length": len(ledger["events"]),
            "ledger_hashes": [e["hash"] for e in ledger["events"]]}


def compare(before: dict, after: dict) -> list[str]:
    """Continuity issues between two snapshots of the same topic (empty when continuity held)."""
    issues = []
    if (before["project_id"], before["topic_id"]) != (after["project_id"], after["topic_id"]):
        issues.append("Snapshots belong to different projects or topics")
    for mid, m in before["missions"].items():
        now = after["missions"].get(mid)
        if now is None:
            issues.append(f"Mission {mid} was lost")
        elif now["plan_digest"] != m["plan_digest"]:
            issues.append(f"Mission {mid} plan changed without a new version")
        elif m["approved"] and not now["approved"] and now["status"] not in ("paused", "cancelled", "interrupted"):
            issues.append(f"Mission {mid} lost its approval")
    for pid, p in before["protocols"].items():
        now = after["protocols"].get(pid)
        if now is None or now["digest"] != p["digest"]:
            issues.append(f"Protocol {pid} was lost or changed")
    nonces = [r["nonce"] for r in after["runs"]]
    for nonce in {n for n in nonces if nonces.count(n) > 1}:
        issues.append(f"Approval {nonce[:8]} ran more than one experiment")
    gone = {r["id"] for r in before["runs"]} - {r["id"] for r in after["runs"]}
    issues += [f"Experiment run {rid} was lost" for rid in sorted(gone)]
    if not after["ledger_ok"]:
        issues.append("Decision ledger integrity failed")
    if after["ledger_hashes"][:before["ledger_length"]] != before["ledger_hashes"]:
        issues.append("Decision ledger history was rewritten")
    return issues


def leakage(tid: str, other_project_dir) -> list[str]:
    """Missions, protocols or runs of `tid` visible from another project (empty when projects are isolated)."""
    from backend.core import config
    found = []
    with config.project_scope(other_project_dir):  # reads the other project without changing the active one
        with S.db() as c:
            for table in ("missions", "experiment_protocols", "experiment_runs"):
                if c.execute(f"SELECT 1 FROM {table} WHERE topic_id=? LIMIT 1", (tid,)).fetchone():
                    found.append(f"{table} of topic {tid} visible in {other_project_dir}")
    return found
