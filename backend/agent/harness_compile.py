"""Harness canvas → governed mission, and the AI-proposed team (v6.6.4, agent/PLAN_6.6.4_L3.md A9).

Found by Playwright (2026-10-28): the canvas runtime only evaluates control flow, so a generated workflow completed Start
and blocked every other node; the team came from keyword matching. Now:

propose_team  a model from the model list (the "architect") proposes 1-4 agents with role, purpose, tools and a model
              from the same list. Unknown tools, unknown models and malformed answers are refused; unavailable models
              stay in the proposal marked unavailable (they are never swapped).
compile       turns the canvas into a MissionSpec: agent and code nodes become agent.task on the bound model, literature
              becomes paper.discover, paper writing paperorchestra.full_orchestration, approval nodes review.checkpoint,
              an evaluation gate an artifact.verify of its input (reported as a note), the end node mission.report.
              Conditions and loops are refused (no silent drop). The mission is created as a draft: the researcher
              approves its exact plan in Missions, and teams.validate checks every role's authority.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from backend.agent import team_agents

ROLE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
MAX_AGENTS = 4


def _tool_ids() -> set[str]:
    from backend.tools import registry
    return {s.id for s in registry.builtin_specs()}


def _extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text or "", re.S)
    raw = fenced.group(1) if fenced else (text or "")[(text or "").find("{"):(text or "").rfind("}") + 1]
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("The architect did not answer with a team in JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        raise ValueError("The architect's answer has no agents list")
    return data


def validate_team(agents: list, choices: list[dict] | None = None) -> list[dict]:
    """Normalise and check a team: ids, roles, models from the list, registered tools. Raises ValueError."""
    choices = choices if choices is not None else team_agents.model_choices()
    listed = {c["id"]: c for c in choices}
    tools = _tool_ids()
    if not 1 <= len(agents) <= MAX_AGENTS:
        raise ValueError(f"A team has 1 to {MAX_AGENTS} agents")
    out, seen = [], set()
    for a in agents:
        if not isinstance(a, dict):
            raise ValueError("Each agent must be an object")
        aid = str(a.get("id") or "").strip().lower()
        if not ROLE_ID.match(aid) or aid in seen:
            raise ValueError(f"Agent id {aid!r} must be unique, lowercase, start with a letter")
        model = str(a.get("model") or "")
        if model not in listed:
            raise ValueError(f"Agent {aid}: model {model!r} is not in the model list")
        unknown = [t for t in a.get("tools") or [] if t not in tools]
        if unknown:
            raise ValueError(f"Agent {aid}: unknown tools {unknown[:5]}")
        purpose = str(a.get("purpose") or "").strip()
        if not purpose:
            raise ValueError(f"Agent {aid} needs a purpose")
        seen.add(aid)
        out.append({"id": aid, "role": str(a.get("role") or aid)[:60], "purpose": purpose[:1000],
                    "prompt": str(a.get("prompt") or "")[:4000], "tools": list(dict.fromkeys(a.get("tools") or []))[:30],
                    "model": model, "model_available": bool(listed[model]["available"]), "model_state": listed[model]["state"]})
    return out


def propose_team(objective: str, architect_model: str, allow_api_billing: bool = False) -> dict:
    """The architect model proposes the team; the app only validates it."""
    if not objective.strip():
        raise ValueError("Describe the research objective first")
    choices = team_agents.model_choices()
    from backend.tools import registry
    catalog = "\n".join(f"- {s.id}: {s.description[:120]}" for s in registry.builtin_specs())[:12000]
    models = "\n".join(f"- {c['id']} ({c['label']}; {'available' if c['available'] else 'unavailable: ' + str(c['state'])})" for c in choices)
    system = ("You design a small research team (1-4 agents) for PhD Research Lab. Answer ONLY a JSON object "
              '{"agents":[{"id","role","purpose","prompt","tools":[tool ids],"model"}],"rationale"}. Choose each '
              "agent's model from the model list (prefer available ones) and its tools from the tool catalog. Ids are "
              "lowercase words. Experiments run only as approved protocols; nothing is claimed without evidence.")
    user = f"Objective:\n{objective[:4000]}\n\nModel list:\n{models}\n\nTool catalog:\n{catalog}"
    answer = team_agents.ask(architect_model, system, user, allow_api_billing)
    data = _extract_json(answer)
    agents = validate_team(data["agents"], choices)
    return {"agents": agents, "rationale": str(data.get("rationale") or "")[:2000], "architect_model": architect_model,
            "unavailable": [a["id"] for a in agents if not a["model_available"]]}


def _order(workflow: dict) -> tuple[list[dict], dict[str, list[str]]]:
    nodes = {n["id"]: n for n in workflow.get("nodes", [])}
    parents: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in workflow.get("edges", []):
        if e.get("source") in nodes and e.get("target") in nodes:
            parents[e["target"]].append(e["source"])
    order, done = [], set()
    while len(done) < len(nodes):
        ready = [nid for nid in nodes if nid not in done and set(parents[nid]) <= done]
        if not ready:
            raise ValueError("The canvas has a cycle; loops are not compiled into a mission")
        for nid in ready:
            done.add(nid)
            order.append(nodes[nid])
    return order, parents


def _ntype(node: dict) -> str:
    return node.get("type") or (node.get("data") or {}).get("node_type") or "harnessNode"


def compile_workflow(workflow: dict, topic_id: str, level: str, team: list[dict], objective: str = "") -> dict:
    """The MissionSpec (JSON) of a canvas plus what changed in meaning, for the researcher to review."""
    from backend.agent.mission_contracts import MissionSpec
    if level not in ("L2", "L3"):
        raise ValueError("Compile the canvas at L2 or L3; L4 needs the bounded experiment structure of Missions")
    team = validate_team(team)
    by_role = {}
    for a in team:
        by_role.setdefault(a["role"], a)
        by_role.setdefault(a["id"], a)
    order, parents = _order(workflow)
    start = next((n for n in order if _ntype(n) == "start"), None)
    objective = objective or ((start or {}).get("data", {}).get("config", {}).get("objective") or workflow.get("name") or "")
    if not objective.strip():
        raise ValueError("The canvas has no objective (Start node)")
    tasks, notes, node_task, used = [], [], {}, set()

    def deps(nid):
        out = []
        for p in parents[nid]:
            out += [node_task[p]] if p in node_task else deps(p)
        return list(dict.fromkeys(out))

    def add(nid, capability, args, engine="deterministic"):
        tid = re.sub(r"[^a-z0-9_-]", "-", nid.lower()).strip("-")[:36] or "task"
        tid = tid if tid[0].isalpha() else "t" + tid
        while tid in {t["id"] for t in tasks}:
            tid = tid[:34] + str(len(tasks))
        d = deps(nid)
        tasks.append({"id": tid, "capability": capability, "args": args, "depends_on": d, "preferred_engine": engine})
        node_task[nid] = tid
        return tid

    for node in order:
        nid, kind = node["id"], _ntype(node)
        cfg = (node.get("data") or {}).get("config") or {}
        label = (node.get("data") or {}).get("label_en") or (node.get("data") or {}).get("label") or nid
        if kind == "start":
            continue
        if kind in ("condition", "bounded_loop"):
            raise ValueError(f"Node {label}: conditions and loops are not compiled into a mission yet; remove them or "
                             "keep this canvas in the visual runtime")
        if kind in ("agent_task", "tool_skill"):
            role = cfg.get("agent_id") or cfg.get("agent_role") or ("coder" if kind == "tool_skill" else "")
            agent = by_role.get(role) or (team[0] if len(team) == 1 else None)
            if agent is None:
                raise ValueError(f"Node {label}: no team agent has role {role!r}; add one or set the node's agent")
            instructions = cfg.get("prompt") or cfg.get("instructions") or cfg.get("input_arg") or label
            prev = deps(nid)
            args = {"agent": agent["id"], "model": agent["model"], "instructions": str(instructions)[:20000], "tools": agent["tools"]}
            if prev:
                args["from_task"] = prev[-1]
            add(nid, "agent.task", args, "agent")
            used.add(agent["id"])
        elif kind == "research_engine" and cfg.get("action") == "synthesize_paper":
            add(nid, "paperorchestra.full_orchestration", {"question": objective[:10000]}, "paperorchestra")
        elif kind == "research_engine":
            add(nid, "paper.discover", {"limit": 10})
            notes.append(f"{label}: compiled to paper.discover of the topic's sources")
        elif kind == "human_approval":
            add(nid, "review.checkpoint", {"title": str(cfg.get("checkpoint_title") or label)[:300]})
        elif kind == "evaluation_gate":
            prev = deps(nid)
            if not prev:
                raise ValueError(f"Node {label}: an evaluation gate needs a step before it")
            add(nid, "artifact.verify", {"from_task": prev[-1]})
            notes.append(f"{label}: compiled to an integrity check of the previous step's files; a metric threshold "
                         f"({cfg.get('metric_key', 'metric')} ≥ {cfg.get('min_threshold', '?')}) needs an approved "
                         "experiment protocol (experiment.run + experiment.verify)")
        elif kind == "end":
            add(nid, "mission.report", {"title": "Harness mission report"})
        else:
            raise ValueError(f"Node {label} ({kind}) has no mission capability; remove it or keep this canvas in the "
                             "visual runtime")
    if not tasks:
        raise ValueError("The canvas has no step to run")
    reasoning = sum(1 for t in tasks if not _meta(t["capability"])[1])
    if reasoning > 3:
        raise ValueError(f"The canvas has {reasoning} model steps; a mission allows 3. Split it into missions or merge steps")
    roles = [a for a in team if a["id"] in used] or team[:1]
    caps = sorted({t["capability"] for t in tasks})
    permissions = sorted({p for t in tasks for p in _meta(t["capability"])[2]})
    engines = sorted({t["preferred_engine"] for t in tasks} | {"deterministic"})
    owner_of = {}
    for t in tasks:
        owner_of[t["id"]] = t["args"]["agent"] if t["capability"] == "agent.task" else "coordinator"
    agents = [{"id": a["id"], "purpose": a["purpose"], "capabilities": ["agent.task"], "permissions": ["reasoning", "workspace_write"],
               "engines": ["agent"], "expected_value": a["purpose"][:1000]} for a in roles]
    other = [c for c in caps if c != "agent.task"]
    if other:
        agents.append({"id": "coordinator", "purpose": "Runs the deterministic and writing steps of the canvas",
                       "capabilities": other, "permissions": sorted({p for c in other for p in _meta(c)[2]}),
                       "engines": sorted({t["preferred_engine"] for t in tasks if t["capability"] != "agent.task"}),
                       "expected_value": "Canvas steps that are not agent work run as typed mission tasks"})
    if len(agents) > MAX_AGENTS:
        raise ValueError(f"The canvas uses more than {MAX_AGENTS} roles (including the coordinator); merge agents")
    spec = {
        "topic_id": topic_id, "objective": objective[:8000], "permissions": permissions,
        "limits": {"max_tasks": len(tasks), "max_hops": len(tasks), "max_seconds": 3600, "max_reasoning_calls": max(1, reasoning)},
        "control": {"success_criteria": ["Every canvas step completed with its evidence; scientific review pending"],
                    "allowed_engines": engines, "app_backend": "local", "allow_api_billing": False,
                    "end_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), "max_wall_seconds": 3600},
        "team": {"mode": "fixed", "agents": agents, "max_agents": len(agents),
                 "assignments": [{"task_id": t["id"], "owner": owner_of[t["id"]], "acceptance": [
                     "Result recorded with its artifacts" if t["capability"] != "review.checkpoint" else "Researcher reviewed"]}
                     for t in tasks]},
        "autonomy": {"level": level},
        "tasks": tasks,
    }
    MissionSpec.model_validate(spec)  # contract errors surface before anything is stored
    return {"spec": spec, "notes": notes, "node_tasks": node_task,
            "team": [{k: a[k] for k in ("id", "role", "model", "model_available", "model_state")} for a in roles]}


def _meta(capability: str):
    from backend.agent import capabilities as C
    return C.META[capability]


def create_mission(workflow: dict, topic_id: str, level: str, team: list[dict], objective: str = "") -> dict:
    """Compile and store the mission as a draft for the researcher's plan approval."""
    from backend.agent import missions
    from backend.agent.mission_contracts import MissionSpec
    compiled = compile_workflow(workflow, topic_id, level, team, objective)
    mission = missions.create(MissionSpec.model_validate(compiled["spec"]))
    return {**compiled, "mission": mission}
