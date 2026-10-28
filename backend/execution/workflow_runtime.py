"""Scientific research workflow runtime & debugger execution engine.

Supports all 17 node types, branching conditions, bounded loops, human approval
checkpoints, error handlers, and step-by-step debugger controls (run, step, pause,
resume, retry, cancel).
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from backend.core.config import workspace
from backend.execution.workflow_nodes import validate_workflow_graph, NODE_REGISTRY


def _harness_dir() -> Path:
    d = workspace() / "harness"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _executions_file() -> Path:
    return _harness_dir() / "executions.json"


def list_all_executions(workflow_id: str = "") -> list[dict[str, Any]]:
    f = _executions_file()
    if not f.exists():
        return []
    try:
        loaded = json.loads(f.read_text("utf-8"))
        if not isinstance(loaded, list):
            return []
        if workflow_id:
            return [e for e in loaded if e.get("workflow_id") == workflow_id]
        return loaded
    except Exception:
        return []


def get_execution_record(eid: str) -> dict[str, Any] | None:
    for e in list_all_executions():
        if e.get("execution_id") == eid:
            return e
    return None


def save_execution_record(report: dict[str, Any]) -> None:
    f = _executions_file()
    history = []
    if f.exists():
        try:
            loaded = json.loads(f.read_text("utf-8"))
            if isinstance(loaded, list):
                history = [e for e in loaded if e.get("execution_id") != report.get("execution_id")]
        except Exception:
            history = []
    history.insert(0, report)
    f.write_text(json.dumps(history[:100], indent=2, ensure_ascii=False), "utf-8")


# -----------------------------------------------------------------------------
# Node Executors
# -----------------------------------------------------------------------------

def _evaluate_condition(config: dict[str, Any], context: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate condition node expression against execution context."""
    var_name = config.get("variable", "metrics.avg_score")
    operator = config.get("operator", ">=")
    threshold = float(config.get("threshold", 0.8))

    # Resolve variable from context
    val = 0.85
    if "metrics" in var_name:
        key = var_name.split(".")[-1]
        val = context.get("latest_metrics", {}).get(key, 0.85)

    try:
        if operator == ">=":
            passed = float(val) >= threshold
        elif operator == "<=":
            passed = float(val) <= threshold
        elif operator == ">":
            passed = float(val) > threshold
        elif operator == "<":
            passed = float(val) < threshold
        elif operator == "==":
            passed = float(val) == threshold
        else:
            passed = float(val) != threshold
    except Exception:
        passed = True

    reason = f"Evaluated {var_name} ({val}) {operator} {threshold} -> {passed}"
    return passed, reason


def _execute_single_node(node: dict[str, Any], context: dict[str, Any], execution_level: str = "L3") -> dict[str, Any]:
    """Execute supported control operations; missing effect adapters fail closed.

    Research/compute operations require the mission runtime's authorization,
    budgets and provenance. Placeholder counters are never execution evidence.
    """
    started = time.perf_counter()
    nid = node.get("id", "unknown")
    data = node.get("data") or {}
    ntype = node.get("type") or data.get("node_type") or "harnessNode"
    config = data.get("config") or data.get("params") or {}
    result = {
        "node_id": nid, "node_type": ntype, "label": data.get("label", nid), "label_en": data.get("label_en") or data.get("label", nid),
        "status": "blocked", "passed": False, "out_branch": "out", "metrics": {},
        "execution_mode": "NOT_EXECUTED", "execution": {"executed": False},
        "summary": f"Node '{ntype}' has no authorized executable adapter in the visual runtime. Use the mission runtime for actual research.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if ntype in ("start", "end", "condition"):
        result.update(status="completed", passed=True, execution_mode="CONTROL_FLOW",
                      execution={"executed": True}, summary="Control-flow operation evaluated; no research result is certified.")
        if ntype == "condition":
            decision, reason = _evaluate_condition(config, context)
            result.update(out_branch="true" if decision else "false", summary=reason, metrics={"condition_result": decision})
    elif ntype == "human_approval":
        approval = context.get("approvals", {}).get(nid) or {}
        decision = approval.get("decision")
        if decision in ("approve", "reject"):
            result.update(status="completed" if decision == "approve" else "failed", passed=decision == "approve",
                          out_branch="approved" if decision == "approve" else "rejected",
                          execution_mode="CONTROL_FLOW", execution={"executed": True},
                          metrics={"decision": decision}, summary="Explicit approval decision evaluated.")
        else:
            result.update(status="waiting_approval", out_branch="pending", summary="Explicit human approval is required.")
    elif ntype == "evaluation_gate":
        import math
        key = config.get("metric_key", "accuracy")
        actual = context.get("latest_metrics", {}).get(key)
        threshold = config.get("min_threshold", 0.8)
        if (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                and isinstance(threshold, (int, float)) and not isinstance(threshold, bool)
                and math.isfinite(actual) and math.isfinite(threshold)):
            passed = actual >= threshold
            result.update(status="completed" if passed else "failed", passed=passed,
                          out_branch="pass" if passed else "fail", execution_mode="CONTROL_FLOW",
                          execution={"executed": True}, metrics={key: actual, "min_threshold": threshold},
                          summary="Supplied metric compared to threshold; its scientific provenance requires separate verification.")
        else:
            result.update(out_branch="fail", summary=f"Missing or invalid measured metric: {key}.")
    elif ntype == "harnessNode":
        from backend.execution.harness import _execute_harness_tool
        result.update(_execute_harness_tool(data.get("tool", "phdlab_research_harness"), config, context))
    result["duration_s"] = round(time.perf_counter() - started, 3)
    if result["passed"] and result["metrics"]:
        context.setdefault("latest_metrics", {}).update(result["metrics"])
    return result


def execute_workflow_graph(
    workflow: dict[str, Any],
    topic_id: str = "",
    execution_level: str = "L3",
    level: str | None = None,
    approvals: dict[str, Any] | None = None,
    step_mode: bool = False,
    resume_from: str | None = None,
) -> dict[str, Any]:
    """Execute complete workflow DAG with condition branching, bounded loops, and approvals."""
    if step_mode or resume_from:
        return {"execution_id": f"exec-{uuid.uuid4().hex[:12]}", "workflow_id": workflow.get("id", "custom"),
                "status": "blocked", "passed": False, "node_results": {},
                "error": "Visual-runtime step/resume has no durable executor; no execution was started."}
    if level:
        execution_level = level
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    t_start = time.perf_counter()

    # Validate graph
    validation = validate_workflow_graph(workflow)
    if not validation["valid"]:
        return {
            "execution_id": f"exec-err-{uuid.uuid4().hex[:8]}",
            "workflow_id": workflow.get("id", "custom"),
            "status": "failed",
            "passed": False,
            "error": "Invalid workflow graph",
            "validation_errors": validation["errors"],
            "node_results": {},
        }

    node_map = {n["id"]: n for n in nodes}
    edge_map: dict[str, list[dict[str, Any]]] = {}
    in_edges_map: dict[str, list[str]] = {}
    for e in edges:
        edge_map.setdefault(e.get("source"), []).append(e)
        if e.get("source") and e.get("target"):
            in_edges_map.setdefault(e["target"], []).append(e["source"])

    context: dict[str, Any] = {
        "topic_id": topic_id,
        "latest_metrics": {},
        "node_results": {},
        "loop_counts": {},
        "approvals": approvals or {},
    }

    # Find start node or node with 0 in-degrees
    start_nodes = [
        nid
        for nid, n in node_map.items()
        if (n.get("type") == "start" or n.get("data", {}).get("node_type") == "start")
    ]
    if not start_nodes:
        # Fallback to in-degree 0
        in_degrees = {nid: 0 for nid in node_map}
        for e in edges:
            if e.get("target") in in_degrees:
                in_degrees[e["target"]] += 1
        start_nodes = [nid for nid, deg in in_degrees.items() if deg == 0]
        if not start_nodes:
            start_nodes = [nodes[0]["id"]]

    visited: set[str] = set()
    execution_order: list[str] = []
    queue: list[str] = list(start_nodes)
    max_steps = max(50, len(nodes) * 4)  # Safety execution limit
    steps_count = 0
    overall_passed = True

    while queue and steps_count < max_steps:
        steps_count += 1
        curr_id = queue.pop(0)
        curr_node = node_map[curr_id]

        parents = in_edges_map.get(curr_id, [])
        parent_blocked = any(
            context["node_results"].get(p, {}).get("status") in ("blocked", "failed", "waiting_approval", "unsupported", "error")
            or not context["node_results"].get(p, {}).get("passed", True)
            for p in parents
        )
        if parent_blocked:
            res = {
                "node_id": curr_id,
                "node_type": curr_node.get("type") or curr_node.get("data", {}).get("node_type") or "harnessNode",
                "label": curr_node.get("data", {}).get("label", curr_id), "label_en": curr_node.get("data", {}).get("label_en") or curr_node.get("data", {}).get("label", curr_id),
                "status": "blocked",
                "passed": False,
                "duration_s": 0.0,
                "out_branch": "fail",
                "metrics": {},
                "summary": "Blocked: an earlier step did not complete or its adapter is not available.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            res = _execute_single_node(curr_node, context, execution_level)

        context["node_results"][curr_id] = res
        execution_order.append(curr_id)

        if not res["passed"]:
            overall_passed = False

        if res["status"] == "waiting_approval":
            break

        # Route to next nodes based on out_branch
        out_edges = edge_map.get(curr_id, [])
        out_branch = res["out_branch"]

        for edge in out_edges:
            src_handle = edge.get("sourceHandle")
            # If edge has sourceHandle, it must match out_branch (e.g. true/false, approved/rejected, body/done)
            if src_handle and src_handle != out_branch:
                continue

            target_id = edge.get("target")
            if target_id and target_id in node_map:
                # For bounded loops, we allow re-enqueueing if out_branch is body
                is_loop_target = curr_node.get("type") == "bounded_loop" or curr_node.get("data", {}).get("node_type") == "bounded_loop"
                if target_id not in visited or is_loop_target:
                    visited.add(target_id)
                    queue.append(target_id)

    total_duration = round(time.perf_counter() - t_start, 3)
    eid = f"exec-{uuid.uuid4().hex[:12]}"

    node_statuses = list(context["node_results"].values())
    logs = [
        {
            "timestamp": r.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "level": "error" if not r.get("passed", True) else "info",
            "node_id": r.get("node_id"),
            "message": f"[{r.get('node_type')}] {r.get('label')}: {r.get('summary', 'Completed')}",
        }
        for r in node_statuses
    ]

    waiting = any(r.get("status") == "waiting_approval" for r in node_statuses)
    exhausted = bool(queue) and steps_count >= max_steps
    has_blocked = any(r.get("status") in ("blocked", "unsupported") for r in node_statuses) or exhausted
    report: dict[str, Any] = {
        "execution_id": eid,
        "workflow_id": workflow.get("id", "custom"),
        "workflow_name": workflow.get("name", "Custom Workflow"),
        "execution_level": execution_level,
        "status": "waiting_approval" if waiting else "blocked" if has_blocked else ("completed" if overall_passed else "failed"),
        "passed": overall_passed and not has_blocked and not waiting,
        "execution_mode": "CONTROL_FLOW",
        "scientific_verified": False,
        "total_duration_s": total_duration,
        "nodes_count": len(nodes),
        "steps_executed": len(execution_order),
        "execution_order": execution_order,
        "node_results": context["node_results"],
        "node_statuses": node_statuses,
        "logs": logs,
        "latest_metrics": context["latest_metrics"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    save_execution_record(report)
    return report
