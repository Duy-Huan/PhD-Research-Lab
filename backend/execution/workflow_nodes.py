"""Extensible node registry and schema contracts for PhD Research Lab Workflow IDE.

Defines schemas, execution contracts, input/output port definitions, and validation
for all 17 workflow node types:
- start / end
- agent_task / multi_agent_team
- research_engine (Feynman, OpenScience, OpenCode, PaperOrchestra)
- tool_skill / mcp_tool
- input / output
- condition / parallel_branch / join / bounded_loop
- human_approval / evaluation_gate
- artifact_transformation / memory_read / memory_write
- error_handler / checkpoint
"""
from __future__ import annotations

import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


NodeType = Literal[
    "start",
    "end",
    "agent_task",
    "multi_agent_team",
    "research_engine",
    "tool_skill",
    "mcp_tool",
    "input",
    "output",
    "condition",
    "parallel_branch",
    "join",
    "bounded_loop",
    "human_approval",
    "evaluation_gate",
    "artifact_transformation",
    "memory_read",
    "memory_write",
    "error_handler",
    "checkpoint",
    # Backward compatibility with existing harness nodes
    "harnessNode",
]


class NodePort(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    type: Literal["control", "data", "artifact", "boolean"] = "control"
    direction: Literal["input", "output"]
    required: bool = False
    description: str = ""


class NodeMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: NodeType
    label: str
    label_en: str
    category: Literal[
        "flow",
        "agent",
        "engine",
        "tool",
        "data",
        "governance",
        "benchmark",
    ]
    icon: str
    description: str
    description_en: str
    inputs: list[NodePort]
    outputs: list[NodePort]
    default_config: dict[str, Any]
    config_schema: dict[str, Any]


NODE_REGISTRY: dict[NodeType, NodeMetadata] = {
    "start": NodeMetadata(
        type="start",
        label="Điểm Bắt đầu",
        label_en="Workflow Start",
        category="flow",
        icon="Play",
        description="Điểm khởi đầu của quy trình nghiên cứu, cấu hình tham số đầu vào và mục tiêu.",
        description_en="Workflow entry point configuring initial parameters and research objectives.",
        inputs=[],
        outputs=[NodePort(id="out", name="Next", type="control", direction="output")],
        default_config={"objective": "", "parameters": {}},
        config_schema={
            "type": "object",
            "properties": {
                "objective": {"type": "string", "title": "Research Objective"},
                "parameters": {"type": "object", "title": "Global Parameters"},
            },
        },
    ),
    "end": NodeMetadata(
        type="end",
        label="Điểm Kết thúc",
        label_en="Workflow End",
        category="flow",
        icon="CheckCircle",
        description="Điểm kết thúc quy trình, tổng hợp báo cáo và minh chứng nghiên cứu.",
        description_en="Workflow terminal point aggregating reports and research evidence.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[],
        default_config={"require_summary": True, "export_ro_crate": True},
        config_schema={
            "type": "object",
            "properties": {
                "require_summary": {"type": "boolean", "default": True},
                "export_ro_crate": {"type": "boolean", "default": True},
            },
        },
    ),
    "agent_task": NodeMetadata(
        type="agent_task",
        label="Tác vụ Agent Độc lập",
        label_en="Agent Task",
        category="agent",
        icon="Bot",
        description="Thực thi tác vụ thông qua AI Agent được gán vai trò, prompt, mô hình và công cụ.",
        description_en="Execute a task via an individual AI Agent with assigned role, prompt, model, and tools.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[
            NodePort(id="out", name="Next", type="control", direction="output"),
            NodePort(id="error", name="Error", type="control", direction="output"),
        ],
        default_config={
            "agent_role": "researcher",
            "prompt": "",
            "provider": "auto",
            "model": "",
            "reasoning_effort": "auto",
            "timeout_seconds": 300,
            "max_retries": 2,
        },
        config_schema={
            "type": "object",
            "properties": {
                "agent_role": {"type": "string", "enum": ["researcher", "literature", "coder", "reviewer", "writer"]},
                "prompt": {"type": "string", "title": "Task Instructions"},
                "provider": {"type": "string", "default": "auto"},
                "model": {"type": "string"},
                "reasoning_effort": {"type": "string", "enum": ["auto", "low", "medium", "high", "off"]},
                "timeout_seconds": {"type": "integer", "default": 300},
                "max_retries": {"type": "integer", "default": 2},
            },
            "required": ["prompt"],
        },
    ),
    "multi_agent_team": NodeMetadata(
        type="multi_agent_team",
        label="Nhóm Đa Agent Phối hợp",
        label_en="Multi-Agent Team",
        category="agent",
        icon="Users",
        description="Đội ngũ nhiều agent phối hợp (Lead, Coder, Reviewer) giải quyết bài toán phức tạp theo L3.",
        description_en="Coordinated team of multiple agents (Lead, Coder, Reviewer) tackling complex problems under L3.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[
            NodePort(id="out", name="Success", type="control", direction="output"),
            NodePort(id="error", name="Failed", type="control", direction="output"),
        ],
        default_config={
            "team_name": "Scientific Exploration Team",
            "coordination_mode": "adaptive",
            "agents": [
                {"role": "director", "name": "Lead Researcher", "provider": "auto"},
                {"role": "coder", "name": "Implementation Specialist", "provider": "auto"},
                {"role": "reviewer", "name": "Rigorous Reviewer", "provider": "auto"},
            ],
            "max_rounds": 3,
            "consensus_required": True,
        },
        config_schema={
            "type": "object",
            "properties": {
                "team_name": {"type": "string"},
                "coordination_mode": {"type": "string", "enum": ["single", "fixed", "adaptive"]},
                "agents": {"type": "array", "items": {"type": "object"}},
                "max_rounds": {"type": "integer", "default": 3},
                "consensus_required": {"type": "boolean", "default": True},
            },
        },
    ),
    "research_engine": NodeMetadata(
        type="research_engine",
        label="Công cụ Nghiên cứu Lõi",
        label_en="Research Engine",
        category="engine",
        icon="Cpu",
        description="Kích hoạt động cơ nghiên cứu tích hợp: PaperOrchestra, Feynman, OpenScience, hoặc OpenCode.",
        description_en="Invoke integrated research engines: PaperOrchestra, Feynman, OpenScience, or OpenCode.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[
            NodePort(id="out", name="Done", type="control", direction="output"),
            NodePort(id="error", name="Error", type="control", direction="output"),
        ],
        default_config={
            "engine": "paperorchestra",
            "action": "generate_section",
            "backend_mode": "skill",
            "params": {"section": "methodology", "iterations": 1},
        },
        config_schema={
            "type": "object",
            "properties": {
                "engine": {"type": "string", "enum": ["paperorchestra", "feynman", "openscience", "opencode"]},
                "action": {"type": "string"},
                "backend_mode": {"type": "string", "enum": ["cli", "skill", "hybrid"]},
                "params": {"type": "object"},
            },
            "required": ["engine"],
        },
    ),
    "tool_skill": NodeMetadata(
        type="tool_skill",
        label="Kỹ năng PhD Lab (/skill)",
        label_en="Skill (/skill)",
        category="tool",
        icon="Sparkles",
        description="Chạy một kỹ năng nội bộ của hệ thống (/lit, /outline, /verify, /latex, /feynman).",
        description_en="Execute a PhD Lab built-in skill (/lit, /outline, /verify, /latex, /feynman).",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[NodePort(id="out", name="Next", type="control", direction="output")],
        default_config={"skill": "lit", "input_arg": ""},
        config_schema={
            "type": "object",
            "properties": {
                "skill": {"type": "string", "enum": ["lit", "outline", "verify", "latex", "feynman", "search", "compare"]},
                "input_arg": {"type": "string"},
            },
            "required": ["skill"],
        },
    ),
    "mcp_tool": NodeMetadata(
        type="mcp_tool",
        label="Công cụ MCP Gateway",
        label_en="MCP Tool",
        category="tool",
        icon="Terminal",
        description="Gọi công cụ nghiên cứu chuẩn MCP (web_search, files_read, sandbox_run_code, research_analyze_image).",
        description_en="Call an MCP research tool (web_search, files_read, sandbox_run_code, research_analyze_image).",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[NodePort(id="out", name="Next", type="control", direction="output")],
        default_config={"tool_name": "web_search", "args": {"query": "", "kind": "papers"}},
        config_schema={
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "args": {"type": "object"},
            },
            "required": ["tool_name"],
        },
    ),
    "condition": NodeMetadata(
        type="condition",
        label="Rẽ nhánh Điều kiện",
        label_en="Condition Branch",
        category="flow",
        icon="GitBranch",
        description="Rẽ nhánh luồng thực thi dựa trên biểu thức điều kiện hoặc giá trị metric.",
        description_en="Branch execution flow based on conditional expressions or metric values.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[
            NodePort(id="true", name="True (Đạt)", type="control", direction="output"),
            NodePort(id="false", name="False (Không đạt)", type="control", direction="output"),
        ],
        default_config={
            "expression": "metrics.avg_score >= 0.80",
            "variable": "metrics.avg_score",
            "operator": ">=",
            "threshold": 0.80,
        },
        config_schema={
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
                "variable": {"type": "string"},
                "operator": {"type": "string", "enum": [">=", "<=", ">", "<", "==", "!="]},
                "threshold": {"type": "number"},
            },
        },
    ),
    "parallel_branch": NodeMetadata(
        type="parallel_branch",
        label="Phân luồng Song song",
        label_en="Parallel Fork",
        category="flow",
        icon="GitFork",
        description="Phân tách quy trình thành nhiều nhánh chạy song song độc lập.",
        description_en="Split the workflow into multiple concurrent execution branches.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[
            NodePort(id="branch_1", name="Branch 1", type="control", direction="output"),
            NodePort(id="branch_2", name="Branch 2", type="control", direction="output"),
            NodePort(id="branch_3", name="Branch 3", type="control", direction="output"),
        ],
        default_config={"max_concurrency": 3},
        config_schema={
            "type": "object",
            "properties": {"max_concurrency": {"type": "integer", "default": 3, "minimum": 2, "maximum": 8}},
        },
    ),
    "join": NodeMetadata(
        type="join",
        label="Hội tụ Nhánh (Join)",
        label_en="Join / Merge",
        category="flow",
        icon="GitMerge",
        description="Đồng bộ và hội tụ các nhánh chạy song song trước khi tiếp tục.",
        description_en="Synchronize and merge parallel execution branches before proceeding.",
        inputs=[
            NodePort(id="in_1", name="In 1", type="control", direction="input"),
            NodePort(id="in_2", name="In 2", type="control", direction="input"),
        ],
        outputs=[NodePort(id="out", name="Next", type="control", direction="output")],
        default_config={"join_strategy": "wait_all"},
        config_schema={
            "type": "object",
            "properties": {"join_strategy": {"type": "string", "enum": ["wait_all", "wait_any"]}},
        },
    ),
    "bounded_loop": NodeMetadata(
        type="bounded_loop",
        label="Vòng lặp Có giới hạn",
        label_en="Bounded Loop",
        category="flow",
        icon="Repeat",
        description="Lặp lại khối tác vụ tối đa N lần hoặc cho tới khi thỏa mãn điều kiện dừng.",
        description_en="Iterate a task block up to N times or until a stopping condition is met.",
        inputs=[
            NodePort(id="in", name="Enter", type="control", direction="input"),
            NodePort(id="loop_in", name="Next Iteration", type="control", direction="input"),
        ],
        outputs=[
            NodePort(id="body", name="Loop Body", type="control", direction="output"),
            NodePort(id="done", name="Loop Done", type="control", direction="output"),
        ],
        default_config={"max_iterations": 3, "stop_condition": "metrics.pass_rate >= 0.90"},
        config_schema={
            "type": "object",
            "properties": {
                "max_iterations": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10},
                "stop_condition": {"type": "string"},
            },
            "required": ["max_iterations"],
        },
    ),
    "human_approval": NodeMetadata(
        type="human_approval",
        label="Cổng Phê duyệt Chuyên gia",
        label_en="Human Approval Gate",
        category="governance",
        icon="ShieldAlert",
        description="Tạm dừng quy trình chờ nhà nghiên cứu Chấp nhận / Từ chối (L2/L3 Checkpoint).",
        description_en="Pause workflow awaiting researcher Accept/Reject decision (L2/L3 Checkpoint).",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[
            NodePort(id="approved", name="Chấp nhận", type="control", direction="output"),
            NodePort(id="rejected", name="Từ chối", type="control", direction="output"),
        ],
        default_config={
            "checkpoint_title": "Xem xét kết quả nghiên cứu",
            "required_role": "lead_researcher",
            "timeout_hours": 24,
            "auto_reject_on_timeout": True,
        },
        config_schema={
            "type": "object",
            "properties": {
                "checkpoint_title": {"type": "string"},
                "required_role": {"type": "string"},
                "timeout_hours": {"type": "integer", "default": 24},
            },
        },
    ),
    "evaluation_gate": NodeMetadata(
        type="evaluation_gate",
        label="Cổng Kiểm định Khoa học",
        label_en="Scientific Evaluation Gate",
        category="governance",
        icon="Award",
        description="Kiểm tra ngưỡng định lượng, độ tái lập, hoặc chạy benchmark kiểm định chất lượng.",
        description_en="Evaluate quantitative thresholds, reproducibility, or run benchmark quality checks.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[
            NodePort(id="pass", name="Đạt chuẩn", type="control", direction="output"),
            NodePort(id="fail", name="Không đạt", type="control", direction="output"),
        ],
        default_config={
            "metric_key": "accuracy",
            "min_threshold": 0.80,
            "verify_sha256": True,
            "reproducibility_trials": 2,
        },
        config_schema={
            "type": "object",
            "properties": {
                "metric_key": {"type": "string"},
                "min_threshold": {"type": "number"},
                "verify_sha256": {"type": "boolean", "default": True},
                "reproducibility_trials": {"type": "integer", "default": 2},
            },
        },
    ),
    "artifact_transformation": NodeMetadata(
        type="artifact_transformation",
        label="Chuyển đổi Artifact",
        label_en="Artifact Transformation",
        category="data",
        icon="FileCode",
        description="Chuyển đổi định dạng tệp: Markdown sang LaTeX, CSV sang biểu đồ, trích xuất dữ liệu.",
        description_en="Transform artifact formats: Markdown to LaTeX, CSV to chart, extract structured data.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[NodePort(id="out", name="Next", type="control", direction="output")],
        default_config={
            "transform_type": "markdown_to_latex",
            "source_path": "",
            "target_path": "",
        },
        config_schema={
            "type": "object",
            "properties": {
                "transform_type": {
                    "type": "string",
                    "enum": ["markdown_to_latex", "extract_tables", "code_patch", "compile_pdf"],
                },
                "source_path": {"type": "string"},
                "target_path": {"type": "string"},
            },
        },
    ),
    "memory_read": NodeMetadata(
        type="memory_read",
        label="Đọc Bộ nhớ Nghiên cứu",
        label_en="Memory Read",
        category="data",
        icon="BookOpen",
        description="Truy xuất giả thuyết, quyết định, thất bại đã ghi nhận từ bộ nhớ dự án.",
        description_en="Retrieve hypotheses, decisions, and failure records from project memory.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[NodePort(id="out", name="Next", type="control", direction="output")],
        default_config={"query": "", "record_types": ["hypothesis", "decision", "evidence"], "limit": 5},
        config_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "record_types": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 5},
            },
        },
    ),
    "memory_write": NodeMetadata(
        type="memory_write",
        label="Ghi Bộ nhớ Nghiên cứu",
        label_en="Memory Write",
        category="data",
        icon="BookmarkPlus",
        description="Lưu giữ phát hiện, quyết định hoặc kết quả vào sổ cái minh chứng dự án.",
        description_en="Persist findings, decisions, or results into project research memory.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[NodePort(id="out", name="Next", type="control", direction="output")],
        default_config={"kind": "finding", "text": "", "evidence_refs": []},
        config_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["finding", "decision", "hypothesis", "failure"]},
                "text": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
        },
    ),
    "error_handler": NodeMetadata(
        type="error_handler",
        label="Bắt lỗi & Dự phòng",
        label_en="Error Handler",
        category="flow",
        icon="LifeBuoy",
        description="Bắt ngoại lệ từ tác vụ lỗi, kích hoạt chiến lược thử lại (retry) hoặc nhánh dự phòng.",
        description_en="Catch exceptions, apply retry policies, or redirect to a fallback branch.",
        inputs=[NodePort(id="error_in", name="Error In", type="control", direction="input")],
        outputs=[
            NodePort(id="retry", name="Thử lại", type="control", direction="output"),
            NodePort(id="fallback", name="Nhánh dự phòng", type="control", direction="output"),
        ],
        default_config={"max_retries": 2, "backoff_seconds": 5, "fallback_strategy": "degrade_gracefully"},
        config_schema={
            "type": "object",
            "properties": {
                "max_retries": {"type": "integer", "default": 2},
                "backoff_seconds": {"type": "integer", "default": 5},
                "fallback_strategy": {"type": "string"},
            },
        },
    ),
    "checkpoint": NodeMetadata(
        type="checkpoint",
        label="Điểm Lưu Checkpoint",
        label_en="Checkpoint",
        category="flow",
        icon="Save",
        description="Lưu snapshot trạng thái quy trình để phục hồi hoặc tiếp tục chạy sau khi dừng.",
        description_en="Save workflow state snapshot for recovery and resumption after stop.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[NodePort(id="out", name="Next", type="control", direction="output")],
        default_config={"save_artifacts": True, "tag": ""},
        config_schema={
            "type": "object",
            "properties": {
                "save_artifacts": {"type": "boolean", "default": True},
                "tag": {"type": "string"},
            },
        },
    ),
    "input": NodeMetadata(
        type="input",
        label="Dữ liệu Đầu vào",
        label_en="Input Data",
        category="data",
        icon="FileInput",
        description="Cung cấp tệp dữ liệu, mã nguồn hoặc tài liệu đầu vào cho bước tiếp theo.",
        description_en="Feed data files, source code, or input documents to downstream nodes.",
        inputs=[],
        outputs=[NodePort(id="out", name="Data", type="data", direction="output")],
        default_config={"source_type": "file", "path": "", "value": ""},
        config_schema={
            "type": "object",
            "properties": {
                "source_type": {"type": "string", "enum": ["file", "text", "dataset", "url"]},
                "path": {"type": "string"},
                "value": {"type": "string"},
            },
        },
    ),
    "output": NodeMetadata(
        type="output",
        label="Xuất Bản Artifact",
        label_en="Publish Artifact",
        category="data",
        icon="FileOutput",
        description="Xuất bản tệp đầu ra (báo cáo, mô hình, PDF, zip) với mã băm sha256.",
        description_en="Publish output files (report, model, PDF, zip) with verifiable SHA-256 hash.",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[],
        default_config={"target_filename": "output.json", "format": "json"},
        config_schema={
            "type": "object",
            "properties": {
                "target_filename": {"type": "string"},
                "format": {"type": "string", "enum": ["json", "markdown", "latex", "pdf", "zip"]},
            },
        },
    ),
    # Backward compatibility with existing harness nodes
    "harnessNode": NodeMetadata(
        type="harnessNode",
        label="Harness Benchmark",
        label_en="Harness Benchmark",
        category="benchmark",
        icon="Gauge",
        description="Node benchmark mã nguồn mở (LM-Eval, Inspect AI, Promptfoo, Ragas, SWE-Bench, Pytest).",
        description_en="Open-source benchmark harness node (LM-Eval, Inspect AI, Promptfoo, Ragas, SWE-Bench, Pytest).",
        inputs=[NodePort(id="in", name="In", type="control", direction="input")],
        outputs=[NodePort(id="out", name="Out", type="control", direction="output")],
        default_config={"tool": "phdlab_research_harness", "params": {}},
        config_schema={"type": "object", "properties": {"tool": {"type": "string"}, "params": {"type": "object"}}},
    ),
}


def list_node_types() -> list[dict[str, Any]]:
    """Return catalog of all supported workflow node types."""
    return [meta.model_dump() for meta in NODE_REGISTRY.values()]


def get_node_metadata(node_type: str) -> dict[str, Any] | None:
    """Retrieve metadata and schema for a specific node type."""
    meta = NODE_REGISTRY.get(node_type)  # type: ignore[arg-type]
    return meta.model_dump() if meta else None


def validate_workflow_graph(workflow: dict[str, Any]) -> dict[str, Any]:
    """Validate workflow nodes, connections, and topology.
    Returns: {"valid": bool, "errors": list[str], "warnings": list[str]}
    """
    errors: list[str] = []
    warnings: list[str] = []

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])

    if not isinstance(nodes, list) or len(nodes) == 0:
        return {"valid": False, "errors": ["Workflow must contain at least one node."], "warnings": []}
    if (not isinstance(edges, list) or any(not isinstance(n, dict) or not isinstance(n.get('data', {}), dict) for n in nodes)
            or any(not isinstance(e, dict) for e in edges)):
        return {'valid': False, 'errors': ['Nodes, edges and node data must have the declared object schemas.'], 'warnings': []}

    node_ids: set[str] = set()
    node_map: dict[str, dict[str, Any]] = {}

    start_nodes = 0
    end_nodes = 0

    for idx, node in enumerate(nodes):
        nid = node.get("id")
        if not nid:
            errors.append(f"Node at index {idx} has missing 'id'.")
            continue
        if nid in node_ids:
            errors.append(f"Duplicate node ID detected: '{nid}'.")
        node_ids.add(nid)
        node_map[nid] = node

        ntype = node.get("type") or node.get("data", {}).get("node_type") or "harnessNode"
        if ntype not in NODE_REGISTRY:
            errors.append(f"Node '{nid}' uses unregistered type '{ntype}'.")

        if ntype == "start":
            start_nodes += 1
        elif ntype == "end":
            end_nodes += 1

    # Validate edges
    edge_ids: set[str] = set()
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    in_degrees: dict[str, int] = {nid: 0 for nid in node_ids}

    for idx, edge in enumerate(edges):
        eid = edge.get("id") or f"e-{idx}"
        src = edge.get("source")
        tgt = edge.get("target")

        if not src or not tgt:
            errors.append(f"Edge '{eid}' is missing source or target.")
            continue
        if src not in node_ids:
            errors.append(f"Edge '{eid}' references non-existent source node '{src}'.")
        if tgt not in node_ids:
            errors.append(f"Edge '{eid}' references non-existent target node '{tgt}'.")

        if src in node_ids and tgt in node_ids:
            adj[src].append(tgt)
            in_degrees[tgt] += 1

    # Cycle detection (ignoring explicit bounded_loop nodes which have loopback connections)
    # Filter out back-edges from bounded_loop nodes
    loop_node_ids = {
        nid
        for nid, n in node_map.items()
        if (n.get("type") == "bounded_loop" or n.get("data", {}).get("node_type") == "bounded_loop")
    }

    # Tarjan's or Kahn's for DAG validation
    temp_in = dict(in_degrees)
    # Reduce in-degrees for loopback edges entering bounded_loop nodes
    for e in edges:
        if e.get("target") in loop_node_ids and e.get("targetHandle") == "loop_in":
            temp_in[e["target"]] = max(0, temp_in[e["target"]] - 1)

    queue = [nid for nid, deg in temp_in.items() if deg == 0]
    visited_count = 0

    while queue:
        curr = queue.pop(0)
        visited_count += 1
        for nxt in adj[curr]:
            temp_in[nxt] -= 1
            if temp_in[nxt] == 0:
                queue.append(nxt)

    if visited_count < len(node_ids) and not loop_node_ids:
        errors.append("Cyclic dependency detected in workflow DAG (non-loop nodes form an infinite cycle).")

    # Warnings for unconnected nodes
    for nid in node_ids:
        ntype = node_map[nid].get("type") or node_map[nid].get("data", {}).get("node_type")
        if ntype not in ("start", "input") and in_degrees[nid] == 0 and len(nodes) > 1:
            warnings.append(f"Node '{nid}' ({node_map[nid].get('data', {}).get('label', nid)}) has no incoming edges.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
