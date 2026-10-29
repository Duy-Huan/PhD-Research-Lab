"""Custom research harness engine integrating open-source harness tools.

Provides:
- Catalog of open-source evaluation and test harness tools (lm-evaluation-harness, inspect_ai, promptfoo, ragas, swe-bench, pytest, phdlab).
- Custom DAG workflow templates and storage.
- Step-by-step pipeline execution engine with metric aggregation and verification gates.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.config import workspace

# -----------------------------------------------------------------------------
# 1. Open-Source Harness Tools Catalog
# -----------------------------------------------------------------------------

OPEN_SOURCE_HARNESS_TOOLS: list[dict[str, Any]] = [
    {
        "id": "lm_evaluation_harness",
        "name": "LM-Evaluation-Harness (EleutherAI)",
        "category": "benchmark",
        "icon": "Gauge",
        "description": "Chuẩn mở đánh giá mô hình ngôn ngữ lớn (MMLU, GSM8K, ARC, HellaSwag, TruthfulQA, Winogrande).",
        "description_en": "Open standard evaluation harness for LLMs (MMLU, GSM8K, ARC, HellaSwag, TruthfulQA).",
        "default_params": {
            "tasks": "gsm8k,mmlu",
            "num_fewshot": 5,
            "metric_target": "acc_norm",
            "min_pass_score": 0.75,
            "timeout_seconds": 180,
        },
        "available_metrics": ["acc", "acc_norm", "f1", "exact_match", "perplexity"],
        "docs_url": "https://github.com/EleutherAI/lm-evaluation-harness",
    },
    {
        "id": "inspect_ai",
        "name": "Inspect AI (UK AI Safety Institute)",
        "category": "agent_eval",
        "icon": "ShieldCheck",
        "description": "Framework đánh giá tự động đa bước cho AI Agents, kiểm thử năng lực suy luận và an toàn mô hình.",
        "description_en": "Multi-step automated evaluation framework for AI agents, reasoning capability, and safety.",
        "default_params": {
            "eval_suite": "agent_reasoning",
            "max_tool_calls": 8,
            "strict_sandbox": True,
            "min_pass_rate": 0.80,
            "timeout_seconds": 240,
        },
        "available_metrics": ["pass_at_1", "tool_accuracy", "safety_score", "reasoning_steps"],
        "docs_url": "https://github.com/UKGovernmentBEIS/inspect_ai",
    },
    {
        "id": "promptfoo",
        "name": "Promptfoo (Test Harness & Red-Teaming)",
        "category": "prompt_test",
        "icon": "CheckSquare",
        "description": "Công cụ CLI kiểm thử ma trận prompt, ma trận đánh giá tự động với assertions và red-teaming an toàn.",
        "description_en": "CLI test harness for prompt matrix testing, automated assertions, and security red-teaming.",
        "default_params": {
            "assertions": ["contains", "llm-rubric", "latency"],
            "max_latency_ms": 1500,
            "rubric_threshold": 0.85,
            "test_cases_count": 20,
        },
        "available_metrics": ["assertion_pass_rate", "avg_latency_ms", "token_cost", "rubric_score"],
        "docs_url": "https://github.com/promptfoo/promptfoo",
    },
    {
        "id": "ragas",
        "name": "Ragas (RAG Assessment Harness)",
        "category": "rag_eval",
        "icon": "Database",
        "description": "Bộ chỉ số đánh giá chuyên sâu kiến trúc RAG: Độ tin cậy (Faithfulness), Độ liên quan (Relevancy), Độ chính xác ngữ cảnh.",
        "description_en": "In-depth RAG evaluation harness: Faithfulness, Answer Relevance, Context Precision & Recall.",
        "default_params": {
            "metrics": ["faithfulness", "answer_relevance", "context_precision"],
            "embedding_model": "text-embedding-3-small",
            "min_faithfulness": 0.90,
            "min_relevance": 0.85,
        },
        "available_metrics": ["faithfulness", "answer_relevance", "context_precision", "context_recall"],
        "docs_url": "https://github.com/explodinggradients/ragas",
    },
    {
        "id": "swe_bench",
        "name": "SWE-Bench / Coding Agent Harness",
        "category": "code_benchmark",
        "icon": "Code",
        "description": "Benchmark kiểm thử tác vụ kỹ thuật phần mềm thực tế trên GitHub repos, biên dịch bản vá và chạy test suite.",
        "description_en": "Software engineering benchmark evaluating coding agents on real-world repository tasks and test suites.",
        "default_params": {
            "task_set": "lite",
            "max_patch_retries": 3,
            "verify_tests": True,
            "min_pass_rate": 0.70,
        },
        "available_metrics": ["resolved_rate", "patch_validity", "test_pass_rate", "diff_lines"],
        "docs_url": "https://github.com/princeton-nlp/SWE-bench",
    },
    {
        "id": "pytest_harness",
        "name": "Pytest / Coverage Harness",
        "category": "test_runner",
        "icon": "Cpu",
        "description": "Trình thực thi kiểm thử cục bộ xác định, đo độ bao phủ nhánh và kiểm định tính toàn vẹn mã nguồn.",
        "description_en": "Deterministic local test execution harness measuring branch coverage and code integrity.",
        "default_params": {
            "test_path": "tests/",
            "min_coverage_pct": 85.0,
            "fail_fast": False,
            "measure_branch": True,
        },
        "available_metrics": ["tests_passed", "tests_total", "coverage_pct", "duration_seconds"],
        "docs_url": "https://docs.pytest.org/",
    },
    {
        "id": "phdlab_research_harness",
        "name": "PhDLab Research Harness",
        "category": "scientific_audit",
        "icon": "Award",
        "description": "Harness nghiên cứu khoa học có giám sát: Tái lập thí nghiệm CPU, đối soát dữ liệu và ký sổ cái hash-chain.",
        "description_en": "Supervised scientific research harness: CPU reproducibility, evidence reconciliation, and ledger audit.",
        "default_params": {
            "stage": "6.3",
            "verify_ledger": True,
            "reproducibility_trials": 2,
            "require_signed_receipts": True,
        },
        "available_metrics": ["reproducibility_score", "ledger_chain_valid", "evidence_verified", "audit_receipts"],
        "docs_url": "https://github.com/phd-research-lab/phdlab",
    },
]

HARNESS_TOOL_MAP = {tool["id"]: tool for tool in OPEN_SOURCE_HARNESS_TOOLS}


# -----------------------------------------------------------------------------
# 2. Storage Directory and Presets
# -----------------------------------------------------------------------------

def harness_dir() -> Path:
    d = workspace() / "harness"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _workflows_file() -> Path:
    return harness_dir() / "workflows.json"


def _executions_file() -> Path:
    return harness_dir() / "executions.json"


def _get_preset_workflows() -> list[dict[str, Any]]:
    return [
        {
            "id": "hw-preset-llm-eval",
            "name": "Quy trình Đánh giá Năng lực Mô hình (LM-Eval + Safety)",
            "name_en": "Model Capability & Safety Audit Pipeline (LM-Eval + Safety)",
            "description": "Tích hợp LM-Evaluation-Harness (GSM8K/MMLU) và Inspect AI để đo lường độ chính xác suy luận và tính an toàn.",
            "description_en": "Integrated pipeline with LM-Eval (GSM8k/MMLU) and Inspect AI to measure reasoning accuracy and safety.",
            "is_preset": True,
            "nodes": [
                {
                    "id": "node-1",
                    "type": "harnessNode",
                    "position": {"x": 60, "y": 80},
                    "data": {
                        "label": "Thu nạp Dữ liệu Benchmark",
                        "label_en": "Benchmark data intake",
                        "tool": "lm_evaluation_harness",
                        "category": "benchmark",
                        "params": {"tasks": "gsm8k,mmlu", "num_fewshot": 5, "min_pass_score": 0.75},
                        "status": "idle",
                    },
                },
                {
                    "id": "node-2",
                    "type": "harnessNode",
                    "position": {"x": 340, "y": 80},
                    "data": {
                        "label": "Inspect AI Agent Eval",
                        "label_en": "Inspect AI agent eval",
                        "tool": "inspect_ai",
                        "category": "agent_eval",
                        "params": {"eval_suite": "agent_reasoning", "max_tool_calls": 6, "min_pass_rate": 0.80},
                        "status": "idle",
                    },
                },
                {
                    "id": "node-3",
                    "type": "harnessNode",
                    "position": {"x": 620, "y": 80},
                    "data": {
                        "label": "Cổng Kiểm định Chất lượng",
                        "label_en": "Quality gate",
                        "tool": "phdlab_research_harness",
                        "category": "scientific_audit",
                        "params": {"stage": "6.3", "verify_ledger": True, "reproducibility_trials": 2},
                        "status": "idle",
                    },
                },
            ],
            "edges": [
                {"id": "e1-2", "source": "node-1", "target": "node-2"},
                {"id": "e2-3", "source": "node-2", "target": "node-3"},
            ],
            "created_at": "2026-10-24T00:00:00Z",
            "updated_at": "2026-10-24T00:00:00Z",
        },
        {
            "id": "hw-preset-rag-audit",
            "name": "Quy trình Đánh giá RAG & Kiểm định Bằng chứng (Ragas + Promptfoo)",
            "name_en": "RAG Assessment & Grounding Pipeline (Ragas + Promptfoo)",
            "description": "Đo lường tính xác thực (Faithfulness), độ khớp ngữ cảnh (Context Precision) và độ trễ phản hồi qua Ragas và Promptfoo.",
            "description_en": "Measure Faithfulness, Context Precision, and latency via Ragas and Promptfoo assertions.",
            "is_preset": True,
            "nodes": [
                {
                    "id": "node-1",
                    "type": "harnessNode",
                    "position": {"x": 60, "y": 80},
                    "data": {
                        "label": "Đánh giá Truy hồi & Grounding (Ragas)",
                        "label_en": "Retrieval & grounding eval (Ragas)",
                        "tool": "ragas",
                        "category": "rag_eval",
                        "params": {"metrics": ["faithfulness", "context_precision"], "min_faithfulness": 0.90},
                        "status": "idle",
                    },
                },
                {
                    "id": "node-2",
                    "type": "harnessNode",
                    "position": {"x": 340, "y": 80},
                    "data": {
                        "label": "Kiểm thử Ranh giới Promptfoo",
                        "label_en": "Promptfoo boundary tests",
                        "tool": "promptfoo",
                        "category": "prompt_test",
                        "params": {"assertions": ["contains", "llm-rubric"], "max_latency_ms": 1200},
                        "status": "idle",
                    },
                },
                {
                    "id": "node-3",
                    "type": "harnessNode",
                    "position": {"x": 620, "y": 80},
                    "data": {
                        "label": "Chứng chỉ Bằng chứng Khoa học",
                        "label_en": "Scientific evidence certificate",
                        "tool": "phdlab_research_harness",
                        "category": "scientific_audit",
                        "params": {"verify_ledger": True, "require_signed_receipts": True},
                        "status": "idle",
                    },
                },
            ],
            "edges": [
                {"id": "e1-2", "source": "node-1", "target": "node-2"},
                {"id": "e2-3", "source": "node-2", "target": "node-3"},
            ],
            "created_at": "2026-10-24T00:00:00Z",
            "updated_at": "2026-10-24T00:00:00Z",
        },
        {
            "id": "hw-preset-code-swe",
            "name": "Quy trình Tự động Hóa Mã nguồn & Regression (Pytest + SWE-Bench)",
            "name_en": "Automated Code Verification & Regression (Pytest + SWE-Bench)",
            "description": "Chạy bộ kiểm thử định thức Pytest, đo coverage và xác thực độ hoàn thiện bản vá mã nguồn SWE-Bench.",
            "description_en": "Execute deterministic Pytest suite, measure coverage, and verify SWE-Bench patch validity.",
            "is_preset": True,
            "nodes": [
                {
                    "id": "node-1",
                    "type": "harnessNode",
                    "position": {"x": 60, "y": 80},
                    "data": {
                        "label": "Kiểm thử Đơn vị & Độ bao phủ (Pytest)",
                        "label_en": "Unit tests & coverage (Pytest)",
                        "tool": "pytest_harness",
                        "category": "test_runner",
                        "params": {"test_path": "tests/", "min_coverage_pct": 85.0},
                        "status": "idle",
                    },
                },
                {
                    "id": "node-2",
                    "type": "harnessNode",
                    "position": {"x": 340, "y": 80},
                    "data": {
                        "label": "Xác thực Bản vá SWE-Bench",
                        "label_en": "SWE-Bench patch validation",
                        "tool": "swe_bench",
                        "category": "code_benchmark",
                        "params": {"task_set": "lite", "min_pass_rate": 0.70},
                        "status": "idle",
                    },
                },
                {
                    "id": "node-3",
                    "type": "harnessNode",
                    "position": {"x": 620, "y": 80},
                    "data": {
                        "label": "Kiểm tra Sổ cái Minh chứng",
                        "label_en": "Evidence ledger check",
                        "tool": "phdlab_research_harness",
                        "category": "scientific_audit",
                        "params": {"stage": "6.3", "verify_ledger": True},
                        "status": "idle",
                    },
                },
            ],
            "edges": [
                {"id": "e1-2", "source": "node-1", "target": "node-2"},
                {"id": "e2-3", "source": "node-2", "target": "node-3"},
            ],
            "created_at": "2026-10-24T00:00:00Z",
            "updated_at": "2026-10-24T00:00:00Z",
        },
    ]


# -----------------------------------------------------------------------------
# 3. Workflow CRUD Operations
# -----------------------------------------------------------------------------

def list_workflows(topic_id: str = "") -> list[dict[str, Any]]:
    presets = _get_preset_workflows()
    f = _workflows_file()
    if not f.exists():
        return presets
    try:
        saved = json.loads(f.read_text("utf-8"))
        if not isinstance(saved, list):
            return presets
        # Merge presets with custom saved workflows
        existing_ids = {w["id"] for w in saved}
        combined = [p for p in presets if p["id"] not in existing_ids] + saved
        if topic_id:
            combined = [w for w in combined if not w.get("topic_id") or w.get("topic_id") == topic_id]
        return combined
    except Exception:
        return presets


def get_workflow(wid: str) -> dict[str, Any] | None:
    for w in list_workflows():
        if w["id"] == wid:
            return w
    return None


def save_workflow(workflow_data: dict[str, Any]) -> dict[str, Any]:
    wid = workflow_data.get("id") or f"hw-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    wf: dict[str, Any] = {
        "id": wid,
        "name": str(workflow_data.get("name", "Custom Harness Workflow")).strip()[:100],
        "description": str(workflow_data.get("description", "")).strip()[:1000],
        "topic_id": str(workflow_data.get("topic_id", "")).strip(),
        "is_preset": False,
        "nodes": workflow_data.get("nodes", []),
        "edges": workflow_data.get("edges", []),
        "created_at": workflow_data.get("created_at", now),
        "updated_at": now,
    }

    f = _workflows_file()
    saved: list[dict[str, Any]] = []
    if f.exists():
        try:
            loaded = json.loads(f.read_text("utf-8"))
            if isinstance(loaded, list):
                saved = [w for w in loaded if w.get("id") != wid]
        except Exception:
            saved = []
    saved.append(wf)
    f.write_text(json.dumps(saved, indent=2, ensure_ascii=False), "utf-8")
    return wf


def delete_workflow(wid: str) -> bool:
    f = _workflows_file()
    if not f.exists():
        return False
    try:
        loaded = json.loads(f.read_text("utf-8"))
        if not isinstance(loaded, list):
            return False
        remaining = [w for w in loaded if w.get("id") != wid]
        if len(remaining) == len(loaded):
            return False
        f.write_text(json.dumps(remaining, indent=2, ensure_ascii=False), "utf-8")
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# 4. Harness Tool Execution Engine
# -----------------------------------------------------------------------------

def _is_tool_available(tool_id: str) -> bool:
    """Check if the real underlying harness tool or CLI is installed and available."""
    import shutil
    import importlib.util
    if tool_id == "lm_evaluation_harness":
        return bool(shutil.which("lm_eval") or importlib.util.find_spec("lm_eval"))
    elif tool_id == "inspect_ai":
        return bool(shutil.which("inspect") or importlib.util.find_spec("inspect_ai"))
    elif tool_id == "ragas":
        return bool(importlib.util.find_spec("ragas"))
    elif tool_id == "promptfoo":
        return bool(shutil.which("promptfoo"))
    elif tool_id == "swe_bench":
        return bool(importlib.util.find_spec("swebench"))
    elif tool_id == "pytest_harness":
        return bool(shutil.which("pytest") or importlib.util.find_spec("pytest"))
    elif tool_id == "phdlab_research_harness":
        return True
    return False


def _execute_harness_tool(tool_id: str, params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """A detected package is not an executor or a completed benchmark.

    Catalog adapters currently have no bounded dispatch/parser implementation.
    Preserve the workflow definition, but never emit invented benchmark results.
    Actual research execution uses workflow_runtime and its registered nodes.
    """
    known = tool_id in HARNESS_TOOL_MAP
    detected = _is_tool_available(tool_id) if known else False
    return {
        "status": "blocked" if known else "unsupported",
        "passed": False,
        "duration_s": 0.0,
        "metrics": {},
        "execution_mode": "NOT_EXECUTED",
        "execution": {"executed": False, "adapter_detected": detected},
        "summary": (f"Harness '{tool_id}' is not configured with an executable benchmark adapter; no evaluation ran."
                    if known else f"Unknown harness adapter: {tool_id}. No evaluation ran."),
    }


def execute_workflow(workflow: dict[str, Any], topic_id: str = "") -> dict[str, Any]:
    """Execute all nodes in the custom harness workflow respecting DAG dependencies."""
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    if (not isinstance(nodes, list) or not isinstance(edges, list)
            or not all(isinstance(n, dict) and "id" in n for n in nodes) or not all(isinstance(e, dict) for e in edges)):
        nodes, edges = [], []  # malformed graph: reported as invalid below, never a server error
    t_start = time.perf_counter()

    # Build adjacency and compute in-degrees
    node_map = {n["id"]: n for n in nodes}
    in_degree: dict[str, int] = {nid: 0 for nid in node_map}
    adj: dict[str, list[str]] = {nid: [] for nid in node_map}

    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src in node_map and tgt in node_map:
            adj[src].append(tgt)
            in_degree[tgt] += 1

    # Topological sort (Kahn's algorithm)
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    sorted_nodes = []
    while queue:
        curr = queue.pop(0)
        sorted_nodes.append(curr)
        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    invalid = (not nodes or len(node_map) != len(nodes)
               or any(e.get("source") not in node_map or e.get("target") not in node_map for e in edges)
               or len(sorted_nodes) != len(nodes))
    if invalid:
        return {
            "execution_id": f"exec-{uuid.uuid4().hex[:12]}",
            "workflow_id": workflow.get("id", "custom"),
            "workflow_name": workflow.get("name", "Custom Harness Workflow"),
            "status": "failed", "passed": False, "total_duration_s": 0.0,
            "nodes_count": len(nodes), "node_results": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "error": "Graph must be nonempty, have unique node IDs, valid edges and no cycles.",
        }

    node_results: dict[str, Any] = {}
    context: dict[str, Any] = {"topic_id": topic_id, "prev_outputs": {}}
    overall_passed = True

    for nid in sorted_nodes:
        node = node_map[nid]
        data = node.get("data", {})
        tool_id = data.get("tool", "phdlab_research_harness")
        params = data.get("params", {})

        parents = [src for src, tgts in adj.items() if nid in tgts]
        upstream_blocked = any(
            node_results.get(p, {}).get("status") in ("blocked", "failed")
            or not node_results.get(p, {}).get("passed", True)
            for p in parents
        )
        if upstream_blocked:
            result = {
                "status": "blocked",
                "passed": False,
                "duration_s": 0.0,
                "metrics": {},
                "summary": "Blocked: an earlier step did not complete or its adapter is not available.",
            }
        else:
            result = _execute_harness_tool(tool_id, params, context)

        node_results[nid] = {
            "node_id": nid,
            "label": data.get("label", nid),
            "tool_id": tool_id,
            "tool_name": HARNESS_TOOL_MAP.get(tool_id, {}).get("name", tool_id),
            "status": result["status"],
            "passed": result["passed"],
            "duration_s": result["duration_s"],
            "metrics": result.get("metrics", {}),
            "summary": result.get("summary", ""),
            "execution_mode": result.get("execution_mode", "NOT_EXECUTED"),
            "execution": result.get("execution", {"executed": False}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        context["prev_outputs"][nid] = result
        if not result["passed"]:
            overall_passed = False

    total_duration = round(time.perf_counter() - t_start, 3)
    eid = f"exec-{uuid.uuid4().hex[:12]}"

    has_blocked = any(r.get("status") == "blocked" for r in node_results.values())
    status = "blocked" if has_blocked else ("completed" if overall_passed else "failed")

    report: dict[str, Any] = {
        "execution_id": eid,
        "workflow_id": workflow.get("id", "custom"),
        "workflow_name": workflow.get("name", "Custom Harness Workflow"),
        "status": status,
        "passed": overall_passed and not has_blocked,
        "total_duration_s": total_duration,
        "nodes_count": len(nodes),
        "node_results": node_results,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save execution history
    f = _executions_file()
    history = []
    if f.exists():
        try:
            loaded = json.loads(f.read_text("utf-8"))
            if isinstance(loaded, list):
                history = loaded
        except Exception:
            history = []
    history.insert(0, report)
    f.write_text(json.dumps(history[:50], indent=2, ensure_ascii=False), "utf-8")

    return report


def list_executions(workflow_id: str = "") -> list[dict[str, Any]]:
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


def get_execution(eid: str) -> dict[str, Any] | None:
    for e in list_executions():
        if e.get("execution_id") == eid:
            return e
    return None
