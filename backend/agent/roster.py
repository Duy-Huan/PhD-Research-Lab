"""One live roster of every agent (v6.6.2) for 3D Lab, Harness and the agent status views.

Sources: the configured roles (config.AGENTS), every agent the Harness created (custom profiles and the agent nodes of
user-saved workflows; a team node contributes one agent per member), Hermes, and MCP clients active in the last 30
minutes. States come only from real records: running tool jobs (principal/actor), running chat turns, the latest
Harness execution of each workflow, and the Hermes runtime. Nothing is inferred from text.

States: idle | thinking | tool | waiting | error | done | offline.
"""
from __future__ import annotations

import hashlib
import json
import time

ACTIVE_CLIENT_S = 1800
NODE_STATE = {"running": "thinking", "waiting_approval": "waiting", "completed": "done", "failed": "error",
              "blocked": "error", "unsupported": "error", "cancelled": "idle"}
TEAM_DEFAULT = [{"role": "director", "name": "Lead Researcher"}, {"role": "coder", "name": "Implementation Specialist"},
                {"role": "reviewer", "name": "Rigorous Reviewer"}]


def _agent(aid, name, kind, source, role="", state="idle", detail="", **extra) -> dict:
    return {"id": aid, "name": name, "kind": kind, "source": source, "role": role, "state": state, "detail": detail,
            "tool": "", "job": "", **extra}


def _roles() -> list:
    from backend.core.config import AGENTS, load_config
    modes = load_config().get("agent_modes") or {}
    return [_agent(f"role:{r}", r.capitalize(), "role", "config", role=r, provider=modes.get(r, meta.get("default", "auto")))
            for r, meta in AGENTS.items()]


def _harness() -> list:
    from backend.agent.workflow_architect import PRESET_AGENTS, list_agent_profiles
    from backend.execution import harness as H, workflow_runtime as WR
    preset_ids = {a["id"] for a in PRESET_AGENTS}
    out = [_agent(f"harness-profile:{p['id']}", p.get("name") or p["id"], "harness", "harness-profile", role=p.get("role", ""))
           for p in list_agent_profiles() if p.get("id") not in preset_ids]
    templates = {w.get("id") for w in H._get_preset_workflows()}
    latest = {}
    for ex in sorted(WR.list_all_executions(""), key=lambda e: str(e.get("created_at", ""))):
        latest[ex.get("workflow_id")] = {s.get("node_id"): s.get("status") for s in ex.get("node_statuses") or []}
    for wf in H.list_workflows(""):
        if wf.get("id") in templates:
            continue
        statuses = latest.get(wf.get("id"), {})
        for node in wf.get("nodes") or []:
            data = node.get("data") or {}
            ntype = node.get("type") or data.get("node_type")
            config = data.get("config") or data.get("params") or {}
            state = NODE_STATE.get(statuses.get(node.get("id")), "idle")
            base = f"harness:{wf['id']}:{node.get('id')}"
            detail = f"{wf.get('name', wf['id'])} / {data.get('label', node.get('id'))}"
            if ntype == "agent_task":
                out.append(_agent(base, data.get("label") or "Agent", "harness", "workflow", role=config.get("agent_role", ""),
                                  state=state, detail=detail, workflow=wf["id"], node=node.get("id")))
            elif ntype == "multi_agent_team":
                for i, member in enumerate(config.get("agents") or TEAM_DEFAULT):
                    out.append(_agent(f"{base}:{i}", member.get("name") or member.get("role", "Agent"), "harness", "workflow",
                                      role=member.get("role", ""), state=state, detail=detail, workflow=wf["id"],
                                      node=node.get("id")))
    return out


def _hermes_state() -> tuple[str, str]:
    from backend.providers import gateway, hermes
    if any(r.get("provider") == "hermes" and r.get("status") in ("starting", "running") for r in gateway.REQS.values()):
        return "thinking", "Working on a chat request"
    try:
        st = hermes.status(hermes.runtime_profile())
    except Exception as e:  # noqa: BLE001 - an unavailable runtime is a state, not an error of the roster
        return "offline", type(e).__name__
    return ("idle" if st.get("ready") else "offline"), str(st.get("detail", ""))[:200]


def _clients() -> list:
    from backend.providers import mcp_server
    now, seen = time.time(), {}
    for sess in list(mcp_server.SESSIONS.values()):
        name = str(sess.get("name") or "mcp-client")
        if now - float(sess.get("started") or 0) <= ACTIVE_CLIENT_S:
            seen[name] = _agent(f"mcp:{name}", name, "mcp_client", "mcp")
    try:
        from backend.tools import chatgpt_gateway
        if chatgpt_gateway.STATE.get("enabled") and chatgpt_gateway.STATE.get("access"):
            seen.setdefault("chatgpt", _agent("mcp:chatgpt", "ChatGPT", "mcp_client", "chatgpt-gateway"))
    except Exception:  # noqa: BLE001
        pass
    return list(seen.values())


def _apply_live(agents: dict) -> None:
    from backend.agent import orchestrator
    from backend.tools.runtime import RUNTIME
    if orchestrator._running and "role:assistant" in agents:
        agents["role:assistant"]["state"] = "thinking"
    for job in sorted(list(RUNTIME.jobs.values()), key=lambda j: j.get("started") or 0):
        if job.get("status") not in ("queued", "running"):
            continue
        principal = str(job.get("principal", ""))
        if principal.startswith("session:"):
            target = "role:assistant"
        elif principal.startswith("mcp:"):
            name = principal.split(":")[1]
            target = f"mcp:{name}"
            agents.setdefault(target, _agent(target, name, "mcp_client", "mcp"))
        else:
            continue
        if target in agents:
            agents[target].update(state="tool", tool=job.get("tool", ""), job=job.get("id", ""), actor=job.get("actor", ""))


def roster() -> dict:
    agents = {a["id"]: a for a in _roles() + _harness() + _clients()}
    state, detail = _hermes_state()
    agents["hermes"] = _agent("hermes", "Hermes", "runtime", "hermes", state=state, detail=detail)
    _apply_live(agents)
    rows = list(agents.values())
    counts = {"total": len(rows), **{k: sum(1 for a in rows if a["kind"] == k) for k in ("role", "harness", "runtime", "mcp_client")},
              "busy": sum(1 for a in rows if a["state"] in ("thinking", "tool", "waiting"))}
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return {"agents": rows, "counts": counts, "digest": digest, "generated": time.time()}
