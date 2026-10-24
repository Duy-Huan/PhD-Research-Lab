"""AI Workflow Architect and Dynamic Agent Team Builder for PhD Research Lab.

Capabilities:
1. Dynamic Agent Team Builder:
   - Custom agent profiles (role, prompt, provider, model, tools, limits, retry rules).
   - Preset scientific specialist agent catalog.
   - Automated balanced team formation.
2. AI Workflow Architect:
   - Generates editable, typed DAG workflow graphs from natural-language research objectives.
   - Strictly conforms to the same schema and validation as visual editor workflows.
   - Never auto-executes before researcher review and explicit approval.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from backend.core.config import workspace
from backend.execution.workflow_nodes import validate_workflow_graph, NODE_REGISTRY


# -----------------------------------------------------------------------------
# 1. Custom Agent Profile & Team Catalog
# -----------------------------------------------------------------------------

class CustomAgentProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    role: str
    purpose: str
    system_prompt: str = ""
    provider: str = "auto"
    model: str = ""
    reasoning_effort: str = "auto"
    skills: list[str] = Field(default_factory=list)
    mcp_tools: list[str] = Field(default_factory=list)
    memory_scope: str = "project_shared"  # ephemeral, session, project_shared
    permissions: list[str] = Field(default_factory=lambda: ["read", "reasoning"])
    max_tokens: int = 4000
    timeout_seconds: int = 300
    max_retries: int = 2
    fallback_provider: str = ""


PRESET_AGENTS: list[dict[str, Any]] = [
    {
        "id": "agent-principal-investigator",
        "name": "Giáo sư Hướng dẫn (Principal Investigator)",
        "role": "director",
        "purpose": "Định hướng mục tiêu tổng thể, phân tích tính khả thi và thẩm định chất lượng nghiên cứu.",
        "system_prompt": "You are a Principal AI Research Scientist. Formulate hypotheses, supervise rigor, identify flaws, and maintain high publication standards.",
        "provider": "auto",
        "model": "",
        "reasoning_effort": "high",
        "skills": ["outline", "verify", "compare"],
        "mcp_tools": ["research_get_current_state", "research_get_decisions", "research_search_memory"],
        "memory_scope": "project_shared",
        "permissions": ["read", "reasoning"],
    },
    {
        "id": "agent-literature-specialist",
        "name": "Chuyên viên Tổng quan Văn hiến (Literature Specialist)",
        "role": "literature",
        "purpose": "Tìm kiếm tài liệu học thuật, đối chiếu công trình trước và phát hiện khoảng trống nghiên cứu.",
        "system_prompt": "You are a Senior Academic Literature Specialist. Synthesize state-of-the-art papers, trace citations, identify gaps, and maintain strict provenance.",
        "provider": "auto",
        "model": "",
        "reasoning_effort": "auto",
        "skills": ["lit", "search", "feynman"],
        "mcp_tools": ["web_search", "web_fetch", "research_get_evidence"],
        "memory_scope": "project_shared",
        "permissions": ["read", "network"],
    },
    {
        "id": "agent-experiment-coder",
        "name": "Kỹ sư Thực nghiệm & Mã nguồn (Experiment Coder)",
        "role": "coder",
        "purpose": "Lập trình kịch bản thí nghiệm, huấn luyện mô hình và đo lường metrics trong sandbox.",
        "system_prompt": "You are a Research Software Engineer. Write clean, reproducible scientific Python code with fixed seeds, modular structure, and logging.",
        "provider": "auto",
        "model": "",
        "reasoning_effort": "medium",
        "skills": ["opencode"],
        "mcp_tools": ["sandbox_run_code", "sandbox_manage_files", "sandbox_get_metrics"],
        "memory_scope": "project_shared",
        "permissions": ["read", "workspace_write", "compute"],
    },
    {
        "id": "agent-rigorous-reviewer",
        "name": "Phản biện Khoa học Độc lập (Rigorous Reviewer)",
        "role": "reviewer",
        "purpose": "Phản biện khách quan theo chuẩn hội nghị hàng đầu (ICLR/NeurIPS/CVPR), kiểm tra rò rỉ dữ liệu và ảo giác.",
        "system_prompt": "You are a Tier-1 Conference Reviewer. Scrutinize claims, audit empirical evidence, check baseline fairness, and challenge unsupported statements.",
        "provider": "auto",
        "model": "",
        "reasoning_effort": "high",
        "skills": ["verify"],
        "mcp_tools": ["research_get_failures", "research_get_provenance"],
        "memory_scope": "project_shared",
        "permissions": ["read", "reasoning"],
    },
    {
        "id": "agent-scientific-writer",
        "name": "Biên soạn Bài báo Học thuật (PaperOrchestra Writer)",
        "role": "writer",
        "purpose": "Soạn thảo văn bản học thuật chuẩn LaTeX, biên soạn cấu trúc dàn ý 5 cấp và tích hợp bảng biểu.",
        "system_prompt": "You are an Academic Scientific Writer. Produce concise, clear, and mathematically accurate text conforming to conference LaTeX styles.",
        "provider": "auto",
        "model": "",
        "reasoning_effort": "medium",
        "skills": ["latex", "outline", "paperorchestra"],
        "mcp_tools": ["files_read", "research_analyze_image"],
        "memory_scope": "project_shared",
        "permissions": ["read", "workspace_write"],
    },
    {
        "id": "agent-benchmark-evaluator",
        "name": "Chuyên gia Đánh giá Benchmark (Benchmark Evaluator)",
        "role": "evaluator",
        "purpose": "Vận hành các bộ benchmark chuẩn mở (LM-Eval, Inspect AI, Promptfoo, Ragas, SWE-Bench).",
        "system_prompt": "You are a Benchmark Evaluation Specialist. Execute standardized evaluation suites and report unbiased statistics.",
        "provider": "auto",
        "model": "",
        "reasoning_effort": "auto",
        "skills": ["verify"],
        "mcp_tools": ["sandbox_get_metrics"],
        "memory_scope": "project_shared",
        "permissions": ["read", "compute"],
    },
]


def _agents_file() -> Path:
    d = workspace() / "harness"
    d.mkdir(parents=True, exist_ok=True)
    return d / "agents.json"


def list_agent_profiles() -> list[dict[str, Any]]:
    """List preset and custom defined research agent profiles."""
    f = _agents_file()
    if not f.exists():
        return PRESET_AGENTS
    try:
        saved = json.loads(f.read_text("utf-8"))
        if not isinstance(saved, list):
            return PRESET_AGENTS
        preset_ids = {a["id"] for a in PRESET_AGENTS}
        custom = [a for a in saved if a.get("id") not in preset_ids]
        return PRESET_AGENTS + custom
    except Exception:
        return PRESET_AGENTS


def save_agent_profile(agent_data: dict[str, Any]) -> dict[str, Any]:
    """Save or update a custom agent profile."""
    aid = str(agent_data.get("id") or f"agent-{uuid.uuid4().hex[:8]}")
    profile = {
        "id": aid,
        "name": str(agent_data.get("name", "Custom Agent")).strip()[:100],
        "role": str(agent_data.get("role", "researcher")).strip(),
        "purpose": str(agent_data.get("purpose", "")).strip()[:500],
        "system_prompt": str(agent_data.get("system_prompt", "")).strip()[:2000],
        "provider": str(agent_data.get("provider", "auto")).strip(),
        "model": str(agent_data.get("model", "")).strip(),
        "reasoning_effort": str(agent_data.get("reasoning_effort", "auto")),
        "skills": list(agent_data.get("skills", [])),
        "mcp_tools": list(agent_data.get("mcp_tools", [])),
        "memory_scope": str(agent_data.get("memory_scope", "project_shared")),
        "permissions": list(agent_data.get("permissions", ["read"])),
        "max_tokens": int(agent_data.get("max_tokens", 4000)),
        "timeout_seconds": int(agent_data.get("timeout_seconds", 300)),
        "max_retries": int(agent_data.get("max_retries", 2)),
    }

    f = _agents_file()
    current = []
    if f.exists():
        try:
            loaded = json.loads(f.read_text("utf-8"))
            if isinstance(loaded, list):
                current = [a for a in loaded if a.get("id") != aid]
        except Exception:
            current = []
    current.append(profile)
    f.write_text(json.dumps(current, indent=2, ensure_ascii=False), "utf-8")
    return profile


def auto_generate_team(
    objective: str,
    desired_roles: list[str] | None = None,
    roles: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Form an optimal multi-agent research team based on the research objective."""
    wanted = desired_roles or roles
    if wanted:
        # Match from presets
        selected: list[dict[str, Any]] = []
        for r in wanted:
            found = next((a for a in PRESET_AGENTS if a["role"] == r), None)
            if found:
                selected.append(found)
            else:
                selected.append({
                    "id": f"agent-{r}-{uuid.uuid4().hex[:6]}",
                    "name": f"Specialist ({r.capitalize()})",
                    "role": r,
                    "purpose": f"Assigned role for {r}",
                    "system_prompt": f"You are an AI research specialist in {r}.",
                    "provider": "auto",
                    "skills": [],
                })
        return selected

    obj_lower = objective.lower()
    selected_agents: list[dict[str, Any]] = []

    # Lead Researcher is always present
    selected_agents.append(PRESET_AGENTS[0])

    # Literature specialist if lit/survey/theory mentioned
    if any(k in obj_lower for k in ("lit", "văn hiến", "paper", "tài liệu", "survey", "nghiên cứu", "tổng quan")):
        selected_agents.append(PRESET_AGENTS[1])

    # Coder if experiment/code/training/model mentioned
    if any(k in obj_lower for k in ("code", "mã", "thực nghiệm", "train", "huấn luyện", "model", "benchmark", "sandbox", "thử nghiệm")):
        selected_agents.append(PRESET_AGENTS[2])

    # Reviewer if audit/verify/critic/chứng minh mentioned
    if any(k in obj_lower for k in ("review", "phản biện", "kiểm định", "đánh giá", "verify", "audit")):
        selected_agents.append(PRESET_AGENTS[3])

    # Writer if paper/bài báo/latex/viết mentioned
    if any(k in obj_lower for k in ("viết", "write", "paper", "bài báo", "latex", "soạn thảo", "công bố")):
        selected_agents.append(PRESET_AGENTS[4])

    # Ensure between 2 and 4 agents
    if len(selected_agents) < 2:
        selected_agents.append(PRESET_AGENTS[2])  # Add coder
    if len(selected_agents) < 3:
        selected_agents.append(PRESET_AGENTS[3])  # Add reviewer

    return selected_agents[:4]


# -----------------------------------------------------------------------------
# 2. AI Workflow Architect (NL Objective -> DAG Workflow Graph)
# -----------------------------------------------------------------------------

def generate_workflow_from_objective(
    objective: str,
    execution_level: str = "L3",
    level: str | None = None,
    include_writing: bool = True,
    strict_verification: bool = True,
) -> dict[str, Any]:
    """Compile a natural-language research objective into a typed, verified DAG workflow.

    Generated workflows strictly conform to validate_workflow_graph() and require
    researcher approval before execution.
    """
    if level:
        execution_level = level
    obj_clean = (objective or "Nghiên cứu Khoa học Tùy chỉnh").strip()
    obj_lower = obj_clean.lower()
    wf_id = f"aiwf-{uuid.uuid4().hex[:10]}"

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    x_step = 260
    current_x = 60
    y_center = 160

    # 1. Start Node
    start_id = "node-start"
    nodes.append({
        "id": start_id,
        "type": "start",
        "position": {"x": current_x, "y": y_center},
        "data": {
            "node_type": "start",
            "label": f"Khởi đầu: {obj_clean[:30]}",
            "config": {"objective": obj_clean, "execution_level": execution_level},
            "status": "idle",
        },
    })
    prev_id = start_id

    # 2. Literature / Feynman synthesis
    current_x += x_step
    lit_id = "node-literature"
    nodes.append({
        "id": lit_id,
        "type": "research_engine",
        "position": {"x": current_x, "y": y_center},
        "data": {
            "node_type": "research_engine",
            "label": "Tổng quan Văn hiến (Feynman)",
            "config": {
                "engine": "feynman",
                "action": "synthesize_literature",
                "params": {"query": obj_clean[:200]},
            },
            "status": "idle",
        },
    })
    edges.append({"id": f"e-{prev_id}-{lit_id}", "source": prev_id, "target": lit_id})
    prev_id = lit_id

    # 3. Agent Task: Hypothesis & Problem Formulation
    current_x += x_step
    hypo_id = "node-hypothesis"
    nodes.append({
        "id": hypo_id,
        "type": "agent_task",
        "position": {"x": current_x, "y": y_center},
        "data": {
            "node_type": "agent_task",
            "label": "Đề xuất Giả thuyết & Thiết kế",
            "config": {
                "agent_role": "researcher",
                "prompt": f"Dựa trên mục tiêu '{obj_clean}', hãy đề xuất 1 giả thuyết khoa học cụ thể và thiết kế phương án thực nghiệm.",
                "provider": "auto",
                "reasoning_effort": "high" if execution_level in ("L3", "L4") else "auto",
            },
            "status": "idle",
        },
    })
    edges.append({"id": f"e-{prev_id}-{hypo_id}", "source": prev_id, "target": hypo_id})
    prev_id = hypo_id

    # 4. Human Approval Gate (Checkpoint) if L2 or strict
    if execution_level in ("L2", "L3") or strict_verification:
        current_x += x_step
        gate1_id = "node-gate-hypothesis"
        nodes.append({
            "id": gate1_id,
            "type": "human_approval",
            "position": {"x": current_x, "y": y_center},
            "data": {
                "node_type": "human_approval",
                "label": "Duyệt Giả thuyết (Checkpoint)",
                "config": {"checkpoint_title": f"Duyệt giả thuyết cho '{obj_clean[:40]}' trước khi chạy code"},
                "status": "idle",
            },
        })
        edges.append({"id": f"e-{prev_id}-{gate1_id}", "source": prev_id, "target": gate1_id})
        prev_id = gate1_id

    # 5. Experiment / Code Generation (OpenCode)
    current_x += x_step
    code_id = "node-opencode"
    nodes.append({
        "id": code_id,
        "type": "research_engine",
        "position": {"x": current_x, "y": y_center},
        "data": {
            "node_type": "research_engine",
            "label": "Thực nghiệm Mã nguồn (OpenCode)",
            "config": {"engine": "opencode", "action": "generate_prototype"},
            "status": "idle",
        },
    })
    edges.append({"id": f"e-{prev_id}-{code_id}", "source": prev_id, "target": code_id})
    prev_id = code_id

    # 6. Evaluation Gate
    current_x += x_step
    eval_id = "node-evaluation"
    nodes.append({
        "id": eval_id,
        "type": "evaluation_gate",
        "position": {"x": current_x, "y": y_center},
        "data": {
            "node_type": "evaluation_gate",
            "label": "Kiểm định Metrics & Bằng chứng",
            "config": {"metric_key": "accuracy", "min_threshold": 0.80, "verify_sha256": True},
            "status": "idle",
        },
    })
    edges.append({"id": f"e-{prev_id}-{eval_id}", "source": prev_id, "target": eval_id})
    prev_id = eval_id

    # 7. Paper Synthesis (PaperOrchestra) if requested
    if include_writing or any(k in obj_lower for k in ("paper", "viết", "write", "bài báo")):
        current_x += x_step
        paper_id = "node-paperorchestra"
        nodes.append({
            "id": paper_id,
            "type": "research_engine",
            "position": {"x": current_x, "y": y_center},
            "data": {
                "node_type": "research_engine",
                "label": "Soạn thảo Bài báo (PaperOrchestra)",
                "config": {
                    "engine": "paperorchestra",
                    "action": "synthesize_paper",
                    "backend_mode": "skill",
                    "params": {"citation_check": True},
                },
                "status": "idle",
            },
        })
        edges.append({"id": f"e-{prev_id}-{paper_id}", "source": prev_id, "target": paper_id})
        prev_id = paper_id

    # 8. Final Human Approval before publishing
    current_x += x_step
    gate_final = "node-gate-final"
    nodes.append({
        "id": gate_final,
        "type": "human_approval",
        "position": {"x": current_x, "y": y_center},
        "data": {
            "node_type": "human_approval",
            "label": "Phê duyệt Xuất bản & Hoàn tất",
            "config": {"checkpoint_title": "Duyệt toàn bộ kết quả nghiên cứu và minh chứng"},
            "status": "idle",
        },
    })
    edges.append({"id": f"e-{prev_id}-{gate_final}", "source": prev_id, "target": gate_final})
    prev_id = gate_final

    # 9. End Node
    current_x += x_step
    end_id = "node-end"
    nodes.append({
        "id": end_id,
        "type": "end",
        "position": {"x": current_x, "y": y_center},
        "data": {
            "node_type": "end",
            "label": "Hoàn thành Quy trình",
            "config": {"require_summary": True, "export_ro_crate": True},
            "status": "idle",
        },
    })
    edges.append({"id": f"e-{prev_id}-{end_id}", "source": prev_id, "target": end_id})

    generated_workflow = {
        "id": wf_id,
        "name": f"AI Workflow: {obj_clean[:50]}",
        "description": f"Quy trình nghiên cứu do AI Workflow Architect thiết kế cho mục tiêu: '{obj_clean}' (Cấp độ: {execution_level}).",
        "is_preset": False,
        "generated_by_ai": True,
        "execution_level": execution_level,
        "nodes": nodes,
        "edges": edges,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Validate graph integrity
    validation = validate_workflow_graph(generated_workflow)
    generated_workflow["validation"] = validation

    return generated_workflow
