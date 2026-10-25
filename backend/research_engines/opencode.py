"""OpenCode Parallel Core Runtime Adapter (v6.4.1).

Integrates OpenCode as a first-class, isolated peer runtime under PhD Lab's
Research Control Plane while enforcing zero-paid-API defaults, per-topic
`opencode_prj/` isolation, event fingerprint deduplication, and approval gates.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from backend.agent import decision_ledger as L
from backend.core.config import data_dir, load_config
from backend.core.telemetry import redact
from backend.knowledge import research_store as S
from backend.research_engines import workspaces as W
from backend.research_engines.contracts import (
    EngineDescriptor,
    EngineEvent,
    EngineFailure,
    EngineResult,
    EngineTask,
)

_server_lock = threading.Lock()
_server_proc: subprocess.Popen | None = None
_server_password: str = os.environ.get("OPENCODE_SERVER_PASSWORD") or secrets.token_urlsafe(24)

DECLARED_CAPABILITIES = [
    "repository_analysis",
    "code_edit",
    "test_execution",
    "refactor",
    "artifact_generation",
    "figure_script_generation",
    "prototype",
    "analysis",
]

DENIED_BY_DEFAULT = {
    "publish_external",
    "delete_project",
    "install_paid_provider",
    "enable_opencode_zen",
    "write_outside_workspace",
}


class OpenCodeTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str = Field(min_length=1, max_length=120)
    mission_id: str = Field(default="", max_length=120)
    task_id: str = Field(default="", max_length=120)
    goal: str = Field(min_length=1, max_length=20000)
    workspace_id: str = Field(default="", max_length=120)
    allowed_capabilities: list[str] = Field(
        default_factory=lambda: ["read_code", "edit_code", "run_tests", "figure_script_generation"],
        max_length=20,
    )
    denied_capabilities: list[str] = Field(
        default_factory=lambda: ["publish_external", "delete_project", "install_paid_provider"],
        max_length=20,
    )
    time_budget_seconds: int = Field(default=600, ge=10, le=7200)
    usage_policy: Literal["subscription_limited", "local_only"] = "subscription_limited"
    allow_metered_api: bool = False
    max_delegation_depth: int = Field(default=2, ge=0, le=3)
    delegation_path: list[str] = Field(default_factory=list, max_length=8)
    source_artifact_refs: list[str] = Field(default_factory=list, max_length=50)
    expected_outputs: list[str] = Field(
        default_factory=lambda: ["code_diff", "test_report", "evidence_manifest"],
        max_length=20,
    )
    approval_policy: Literal["require_for_destructive_and_external_actions", "strict_manual"] = (
        "require_for_destructive_and_external_actions"
    )
    enable_bridge_plugin: bool = True


def _opencode_cfg() -> dict:
    cfg = load_config()
    oc = cfg.get("opencode") if isinstance(cfg.get("opencode"), dict) else {}
    return {
        "enabled": bool(oc.get("enabled", True)),
        "base_url": str(oc.get("base_url") or "http://127.0.0.1:4097").rstrip("/"),
        "allow_metered_api": bool(oc.get("allow_metered_api", False)),
        "provider_priority": list(oc.get("provider_priority") or ["chatgpt_subscription", "ollama_local", "codex_cli", "claude_code_cli"]),
        "timeout_s": int(oc.get("timeout_s", 600)),
    }


def probe_binary() -> dict:
    from backend.execution.tools import which, NO_WINDOW, node_argv

    binary = which("opencode")
    version = None
    if binary:
        try:
            prefix = node_argv(binary, "opencode-ai/bin/opencode")
            res = subprocess.run(
                [*prefix, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=NO_WINDOW,
            )
            if res.returncode == 0:
                version = (res.stdout or res.stderr).strip().splitlines()[0][:80]
        except Exception:
            version = "installed-unverified"
    return {
        "binary": binary,
        "installed": bool(binary),
        "version": version or ("available" if binary else "not_installed"),
        "spdx_license": "MIT",
    }


def health() -> dict:
    cfg = _opencode_cfg()
    info = probe_binary()
    url = cfg["base_url"]
    if not url.startswith(("http://127.0.0.1:", "http://localhost:")):
        return {
            "ready": False,
            "state": "security_blocked",
            "error_code": "non_loopback_rejected",
            "detail": "OpenCode server must bind to loopback (127.0.0.1 / localhost) by default.",
            **info,
        }
    server_reachable = False
    server_detail = "Server not running (offline/standby mode ready)"
    try:
        r = httpx.get(
            f"{url}/openapi.json",
            auth=("opencode", _server_password),
            timeout=1.2,
        )
        server_reachable = r.status_code == 200 and bool(r.json().get("openapi"))
        server_detail = f"Loopback HTTP server reachable ({r.status_code})"
    except Exception:
        server_reachable = False

    return {
        "engine": "opencode",
        "ready": bool(cfg["enabled"] and (info["installed"] or server_reachable)),
        "state": "running" if server_reachable else ("installed" if info["installed"] else "not_installed"),
        "server_reachable": server_reachable,
        "base_url": url,
        "loopback_only": True,
        "auth_mode": "http_basic_ephemeral_secret",
        "metered_api_allowed": cfg["allow_metered_api"],
        "opencode_zen_enabled": False,
        "provider_priority": cfg["provider_priority"],
        "capabilities": DECLARED_CAPABILITIES,
        "detail": server_detail,
        **info,
    }


def ensure_server_running(port: int = 4097) -> dict:
    """Verify loopback OpenCode server status and launch background process if binary is present."""
    global _server_proc
    h = health()
    if h.get("server_reachable"):
        return {"running": True, "state": "running", "base_url": h["base_url"], "detail": "Loopback server is already active"}
    info = probe_binary()
    binary = info.get("binary")
    if not binary:
        return {
            "running": False,
            "state": "standby_internal_fallback",
            "installed": False,
            "detail": "OpenCode binary not found on PATH; falling back to internal sandbox",
            "setup": ["npm install -g opencode-ai"],
        }
    with _server_lock:
        if _server_proc and _server_proc.poll() is None:
            return {"running": False, "state": "starting", "pid": _server_proc.pid, "detail": "Process active but HTTP readiness is unverified"}
        try:
            from backend.execution.tools import NO_WINDOW, node_argv
            from backend.providers.cli_space import minimal_env, open_session
            env = minimal_env()
            env["OPENCODE_SERVER_PASSWORD"] = _server_password
            prefix = node_argv(binary, "opencode-ai/bin/opencode")
            _server_proc = subprocess.Popen(
                [*prefix, "serve", "--port", str(port), "--hostname", "127.0.0.1"],
                env=env,
                cwd=open_session("opencode", "native-server", "review")["cwd"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
            )
            for _ in range(50):
                if _server_proc.poll() is not None:
                    return {"running": False, "state": "error", "detail": f"OpenCode exited during startup ({_server_proc.returncode})"}
                if health().get("server_reachable"):
                    return {"running": True, "state": "running", "pid": _server_proc.pid, "port": port}
                time.sleep(0.1)
            return {"running": False, "state": "starting", "pid": _server_proc.pid, "detail": "Process started but HTTP readiness has not been verified"}
        except Exception as e:
            return {"running": False, "state": "error", "detail": f"Failed to launch background server: {e}"}

def ensure_topic_workspace(tid: str, workspace_id: str = "", enable_plugin: bool = True) -> dict:
    """Get or create the isolated `<topic>/opencode_prj` workspace and write safe bridge config."""
    S.get_topic(tid)
    existing = [w for w in W.list_workspaces(tid) if w["engine"] == "opencode"]
    if workspace_id:
        w = W.get(workspace_id)
        if w["topic_id"] != tid or w["engine"] != "opencode":
            raise ValueError("Workspace does not belong to this Topic or is not an OpenCode workspace")
    elif existing:
        w = existing[0]
    else:
        w = W.link(tid, W.WorkspaceInput(engine="opencode"))

    root = Path(w["path"]).resolve()
    S.safe_child(root)
    # Ensure opencode_prj is never a symlink to openscience_prj or feynman_prj
    for other in W.list_workspaces(tid):
        if other["id"] != w["id"]:
            other_path = Path(other["path"]).resolve()
            if root == other_path or root.is_relative_to(other_path) or other_path.is_relative_to(root):
                raise ValueError("OpenCode workspace cannot overlap OpenScience or Feynman workspaces")

    cfg_file = S.safe_child(root, "opencode.json")
    safe_config = {
        "$schema": "https://opencode.ai/config.json",
        "project_id": S.project_id(),
        "topic_id": tid,
        "workspace_id": w["id"],
        "metered_api": "disabled",
        "opencode_zen": "disabled",
        "permissions": {
            "edit": "allow_within_workspace",
            "bash": "ask_for_destructive",
            "webfetch": "ask",
            "external_publish": "deny",
        },
    }
    cfg_file.write_text(json.dumps(safe_config, indent=2, ensure_ascii=False), "utf-8")

    plugin_dir = S.safe_child(root, ".opencode", "plugins")
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugin_file = S.safe_child(plugin_dir, "phdlab-opencode-bridge.js")
    if enable_plugin:
        plugin_file.write_text(
            "// PhD Research Lab v6.4.1 — Optional OpenCode Local Bridge Plugin\n"
            "// Forwards minimal normalized correlation events; never bypasses safety checks.\n"
            "export const PhDLabBridgePlugin = async ({ project, directory }) => ({\n"
            "  event: async ({ event }) => {\n"
            "    // Stamped with topic/task correlation by PhD Lab Runtime Gateway\n"
            "    return { observed: true, type: event?.type || 'unknown' };\n"
            "  }\n"
            "});\n",
            "utf-8",
        )
    elif plugin_file.exists():
        plugin_file.unlink()

    return w


def _event_fingerprint(session_id: str, seq: int, event_type: str, key_hint: str = "") -> str:
    raw = f"{session_id}:{seq}:{event_type}:{key_hint}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_event(
    tid: str,
    session_id: str,
    event_type: str,
    payload: dict,
    *,
    seq: int | None = None,
    key_hint: str = "",
) -> dict:
    """Idempotently record a normalized OpenCode event (deduplicating server + plugin streams)."""
    clean_payload = json.loads(redact(S.dumps(payload)))
    with S.db() as c:
        srow = c.execute("SELECT * FROM opencode_sessions WHERE id=? AND topic_id=?", (session_id, tid)).fetchone()
        if not srow:
            raise ValueError("OpenCode session not found in this Topic")
        if seq is None:
            max_seq = c.execute("SELECT coalesce(max(seq), 0) FROM opencode_events WHERE session_id=?", (session_id,)).fetchone()[0]
            seq = int(max_seq) + 1
        fp = _event_fingerprint(session_id, seq, event_type, key_hint or S.dumps(clean_payload))
        existing = c.execute("SELECT * FROM opencode_events WHERE fingerprint=?", (fp,)).fetchone()
        if existing:
            return {**dict(existing), "payload": json.loads(existing["payload"]), "deduplicated": True}
        eid = S.uid()
        at = S.now()
        c.execute(
            "INSERT INTO opencode_events VALUES(?,?,?,?,?,?,?,?)",
            (eid, session_id, tid, fp, seq, event_type, S.dumps(clean_payload), at),
        )
        return {
            "id": eid,
            "session_id": session_id,
            "topic_id": tid,
            "fingerprint": fp,
            "seq": seq,
            "event_type": event_type,
            "payload": clean_payload,
            "created": at,
            "deduplicated": False,
        }


def start_session(spec: OpenCodeTaskSpec) -> dict:
    """Validate task boundaries, prevent delegation cycles, and create an isolated OpenCode session."""
    S.get_topic(spec.topic_id)
    if spec.allow_metered_api and not _opencode_cfg()["allow_metered_api"]:
        raise ValueError("Metered API usage is disabled by policy; use subscription or local models.")
    if "opencode" in spec.delegation_path or len(spec.delegation_path) > spec.max_delegation_depth:
        raise ValueError("Recursive delegation loop or max delegation depth exceeded (PhD Lab -> OpenCode cycle blocked).")
    forbidden = set(spec.allowed_capabilities) & DENIED_BY_DEFAULT
    if forbidden:
        raise ValueError(f"Task requests denied capabilities: {', '.join(sorted(forbidden))}")

    w = ensure_topic_workspace(spec.topic_id, spec.workspace_id, spec.enable_bridge_plugin)
    sid = f"oc-sess-{S.uid()[:8]}"
    native_sid = ""  # no native session exists until a real runtime has created one
    at = S.now()

    status = "paused"
    blocking_reason = "Workspace prepared; no native inference request submitted. Open the native runtime and sync its saved artifacts."

    session_payload = {
        "spec": spec.model_dump(mode="json"),
        "workspace_path": w["path"],
        "delegation_path": [*spec.delegation_path, "phdlab", "opencode"],
        "blocking_reason": blocking_reason,
        "bridge_plugin_enabled": spec.enable_bridge_plugin,
        "artifacts": [],
        "diff_summary": [],
    }

    with S.db() as c:
        c.execute(
            "INSERT INTO opencode_sessions VALUES(?,?,?,?,?,?,?,?,?,?)",
            (sid, spec.topic_id, spec.mission_id, spec.task_id, w["id"], native_sid, status, S.dumps(session_payload), at, at),
        )
        L.append(
            c,
            spec.topic_id,
            sid,
            "opencode.session_started",
            {"task_id": spec.task_id, "workspace_id": w["id"], "status": status, "usage_policy": spec.usage_policy},
        )

    record_event(
        spec.topic_id,
        sid,
        "session.started",
        {"goal": spec.goal[:500], "workspace_id": w["id"], "status": status, "bridge_plugin": spec.enable_bridge_plugin},
        seq=1,
        key_hint="init",
    )
    if status == "blocked_by_quota":
        record_event(
            spec.topic_id,
            sid,
            "runtime.quota_limited",
            {"reason": blocking_reason, "metered_fallback": False},
            seq=2,
            key_hint="quota",
        )
    return get_session(spec.topic_id, sid)


def request_approval(tid: str, sid: str, action: str, scope: str, risk: str = "high") -> dict:
    """Create a fail-closed permission request for a destructive or external action."""
    with S.db() as c:
        srow = c.execute("SELECT * FROM opencode_sessions WHERE id=? AND topic_id=?", (sid, tid)).fetchone()
        if not srow:
            raise ValueError("OpenCode session not found in this Topic")
        aid = f"oc-app-{S.uid()[:8]}"
        at = S.now()
        payload = {"action": action, "scope": scope, "risk": risk, "decision": None, "note": ""}
        c.execute(
            "INSERT INTO opencode_approvals VALUES(?,?,?,?,?,?,?,?,?)",
            (aid, sid, tid, action, risk, "pending", S.dumps(payload), at, at),
        )
        c.execute("UPDATE opencode_sessions SET status='awaiting_approval',updated=? WHERE id=?", (at, sid))
        L.append(c, tid, sid, "opencode.approval_requested", {"approval_id": aid, "action": action, "risk": risk})
    record_event(tid, sid, "permission.requested", {"approval_id": aid, "action": action, "scope": scope, "risk": risk})
    return get_session(tid, sid)


def decide_approval(tid: str, sid: str, aid: str, decision: Literal["approve", "reject"], note: str = "") -> dict:
    if decision not in ("approve", "reject"):
        raise ValueError("Decision must be 'approve' or 'reject'")
    with S.db() as c:
        arow = c.execute(
            "SELECT * FROM opencode_approvals WHERE id=? AND session_id=? AND topic_id=?",
            (aid, sid, tid),
        ).fetchone()
        if not arow:
            raise ValueError("Approval request not found in this session/topic")
        if arow["status"] != "pending":
            raise ValueError("Approval request was already decided")
        if arow["action"] in DENIED_BY_DEFAULT and decision == "approve":
            raise ValueError(f"Action '{arow['action']}' is prohibited by workspace security policy and cannot be granted")
        payload = json.loads(arow["payload"])
        payload.update(decision=decision, note=note[:2000], decided_at=S.now(), by="researcher")
        new_status = "approved" if decision == "approve" else "rejected"
        sess_status = "paused"  # recording a local approval does not submit a native prompt
        c.execute(
            "UPDATE opencode_approvals SET status=?,payload=?,updated=? WHERE id=?",
            (new_status, S.dumps(payload), S.now(), aid),
        )
        c.execute("UPDATE opencode_sessions SET status=?,updated=? WHERE id=?", (sess_status, S.now(), sid))
        L.append(c, tid, sid, f"opencode.approval_{new_status}", {"approval_id": aid, "note": note[:500]})
    record_event(tid, sid, f"permission.{new_status}", {"approval_id": aid, "decision": decision, "note": note[:500]})
    return get_session(tid, sid)


def cancel_session(tid: str, sid: str) -> dict:
    with S.db() as c:
        srow = c.execute("SELECT * FROM opencode_sessions WHERE id=? AND topic_id=?", (sid, tid)).fetchone()
        if not srow:
            raise ValueError("OpenCode session not found in this Topic")
        c.execute("UPDATE opencode_sessions SET status='cancelled',updated=? WHERE id=?", (S.now(), sid))
        L.append(c, tid, sid, "opencode.session_cancelled", {"by": "researcher"})
    record_event(tid, sid, "session.cancelled", {"by": "researcher"})
    return get_session(tid, sid)


def reconcile_session(tid: str, sid: str, simulate_gap: bool = False) -> dict:
    """Reconcile session state and workspace artifacts after disconnect/restart without fabricating missing events."""
    sess = get_session(tid, sid)
    wid = sess["workspace_id"]
    sync_report = W.sync(wid) if wid else {"changed": 0, "observed": 0, "complete": True}
    arts = W.artifacts(tid, wid) if wid else []
    with S.db() as c:
        row = c.execute("SELECT payload,status FROM opencode_sessions WHERE id=? AND topic_id=?", (sid, tid)).fetchone()
        payload = json.loads(row["payload"])
        payload["last_reconciled_at"] = S.now()
        payload["sync_report"] = sync_report
        payload["artifacts"] = [
            {"id": a["id"], "path": a["path"], "sha256": a["sha256"], "bytes": a["bytes"], "version": a["version"]}
            for a in arts[:50]
        ]
        if simulate_gap:
            payload["sync_gap"] = True
            payload["sync_gap_note"] = "Simulated reconciliation gap requested; only saved artifacts were reconciled. No native event replay is claimed."
        new_status = row["status"]
        if new_status == "running" and simulate_gap:
            new_status = "reconciled_with_gap"
        c.execute(
            "UPDATE opencode_sessions SET status=?,payload=?,updated=? WHERE id=?",
            (new_status, S.dumps(payload), S.now(), sid),
        )
        L.append(
            c,
            tid,
            sid,
            "opencode.session_reconciled",
            {"artifacts_observed": len(arts), "sync_gap": bool(payload.get("sync_gap"))},
        )
    if simulate_gap:
        record_event(tid, sid, "runtime.recovery_gap", {"detail": payload["sync_gap_note"]})
    else:
        record_event(tid, sid, "session.reconciled", {"artifacts_observed": len(arts)})
    return get_session(tid, sid)


def list_sessions(tid: str) -> list[dict]:
    S.get_topic(tid)
    with S.db() as c:
        rows = c.execute("SELECT id FROM opencode_sessions WHERE topic_id=? ORDER BY updated DESC LIMIT 100", (tid,)).fetchall()
        return [get_session(tid, r[0]) for r in rows]


def get_session(tid: str, sid: str) -> dict:
    S.get_topic(tid)
    with S.db() as c:
        row = c.execute("SELECT * FROM opencode_sessions WHERE id=? AND topic_id=?", (sid, tid)).fetchone()
        if not row:
            raise ValueError("OpenCode session not found in this Topic")
        events = [
            {**dict(e), "payload": json.loads(e["payload"])}
            for e in c.execute("SELECT * FROM opencode_events WHERE session_id=? ORDER BY seq ASC", (sid,))
        ]
        approvals = [
            {**dict(a), "payload": json.loads(a["payload"])}
            for a in c.execute("SELECT * FROM opencode_approvals WHERE session_id=? ORDER BY created DESC", (sid,))
        ]
        payload = json.loads(row["payload"])
        return {
            **dict(row),
            "payload": payload,
            "events": events,
            "approvals": approvals,
        }


class OpenCodeEngine:
    """Implements the ResearchEngine protocol for registry integration."""

    descriptor = EngineDescriptor(
        id="opencode",
        capabilities=[],
        transport="http_loopback",
        token_streaming=False,
        native_sessions=False,
    )

    def health(self) -> dict:
        return {**health(), "ready": False, "state": "NOT_CONFIGURED",
                "detail": "OpenCode native prompt dispatch is not connected; open the native workspace and sync artifacts."}

    def execute(
        self,
        task: EngineTask,
        emit: Callable[[EngineEvent], None],
        cancelled: Callable[[], bool],
    ) -> EngineResult:
        if cancelled():
            raise EngineFailure("Cancelled before dispatch", "cancelled")
        # This bridge observes workspaces; it has no native prompt dispatch yet.
        # A generated manifest is not execution evidence and must never become a completed task.
        raise EngineFailure("OpenCode native prompt dispatch is not connected. Open its native workspace to run the task; PhD Lab can sync persisted artifacts afterwards.", "capability")
