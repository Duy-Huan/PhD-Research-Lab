"""Pre-built, customizable scientific research workflow templates for PhD Research Lab.

Implements the 7 required standard scientific research workflows:
1. Idea to Hypothesis
2. Literature Review
3. Hypothesis to Experiment
4. Deep Learning Research
5. Paper Reproduction
6. Research to Paper
7. Full Autonomous Research (L4)
"""
from __future__ import annotations

from typing import Any


RESEARCH_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "tpl-idea-to-hypothesis",
        "name": "Ý tưởng đến Giả thuyết Khoa học (Idea to Hypothesis)",
        "name_en": "Idea to Hypothesis Formulation",
        "category": "ideation",
        "badge": "L2/L3",
        "description": "Phát triển ý tưởng sơ khởi thành giả thuyết khoa học có thể kiểm chứng: Rà soát tổng quan, phân tích khoảng trống (gap analysis), tranh luận phản biện và phê duyệt.",
        "description_en": "Evolve early research intuition into falsifiable scientific hypotheses via literature review, gap analysis, multi-agent debate, and human gate.",
        "is_preset": True,
        "nodes": [
            {
                "id": "node-start",
                "type": "start",
                "position": {"x": 50, "y": 150},
                "data": {
                    "node_type": "start",
                    "label": "Ý tưởng Sơ khởi",
                    "config": {"objective": "Khám phá kỹ thuật nén mô hình Transformer thời gian thực"},
                    "status": "idle",
                },
            },
            {
                "id": "node-lit-review",
                "type": "research_engine",
                "position": {"x": 300, "y": 150},
                "data": {
                    "node_type": "research_engine",
                    "label": "Rà soát Tài liệu (Native research)",
                    "config": {"engine": "phdlab", "action": "synthesize_literature", "params": {"query": "Transformer model compression real-time"}},
                    "status": "idle",
                },
            },
            {
                "id": "node-gap-analysis",
                "type": "agent_task",
                "position": {"x": 560, "y": 150},
                "data": {
                    "node_type": "agent_task",
                    "label": "Phân tích Khoảng trống (Gap)",
                    "config": {
                        "agent_role": "literature",
                        "prompt": "Đối chiếu các công trình đã công bố, xác định 3 khoảng trống nghiên cứu chính và hạn chế hiện tại.",
                        "provider": "auto",
                    },
                    "status": "idle",
                },
            },
            {
                "id": "node-team-debate",
                "type": "multi_agent_team",
                "position": {"x": 820, "y": 150},
                "data": {
                    "node_type": "multi_agent_team",
                    "label": "Tranh biện Đa Agent (Lead vs Reviewer)",
                    "config": {
                        "team_name": "Hypothesis Formulation Team",
                        "coordination_mode": "adaptive",
                        "max_rounds": 2,
                    },
                    "status": "idle",
                },
            },
            {
                "id": "node-approval",
                "type": "human_approval",
                "position": {"x": 1080, "y": 150},
                "data": {
                    "node_type": "human_approval",
                    "label": "Chuyên gia Phê duyệt Giả thuyết",
                    "config": {"checkpoint_title": "Xác nhận giả thuyết HYPE-001 trước khi thiết kế thí nghiệm"},
                    "status": "idle",
                },
            },
            {
                "id": "node-mem-write",
                "type": "memory_write",
                "position": {"x": 1340, "y": 150},
                "data": {
                    "node_type": "memory_write",
                    "label": "Ghi Giả thuyết vào Sổ cái",
                    "config": {"kind": "hypothesis", "text": "Structured Hypothesis HYPE-001"},
                    "status": "idle",
                },
            },
            {
                "id": "node-end",
                "type": "end",
                "position": {"x": 1580, "y": 150},
                "data": {
                    "node_type": "end",
                    "label": "Hoàn tất Giả thuyết",
                    "config": {"require_summary": True},
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "node-start", "target": "node-lit-review"},
            {"id": "e2", "source": "node-lit-review", "target": "node-gap-analysis"},
            {"id": "e3", "source": "node-gap-analysis", "target": "node-team-debate"},
            {"id": "e4", "source": "node-team-debate", "target": "node-approval"},
            {"id": "e5", "source": "node-approval", "target": "node-mem-write"},
            {"id": "e6", "source": "node-mem-write", "target": "node-end"},
        ],
    },
    {
        "id": "tpl-literature-review",
        "name": "Tổng quan Tài liệu Học thuật Toàn diện (Literature Review)",
        "name_en": "Comprehensive Literature Review & Evidence Synthesis",
        "category": "literature",
        "badge": "L2/L3",
        "description": "Thu thập tự động từ OpenAlex/arXiv, sàng lọc bài báo, trích xuất bằng chứng định lượng và lập cây phả hệ học thuật.",
        "description_en": "Automated paper retrieval from OpenAlex/arXiv, relevance screening, evidence extraction, and taxonomy mapping.",
        "is_preset": True,
        "nodes": [
            {
                "id": "node-start",
                "type": "start",
                "position": {"x": 50, "y": 180},
                "data": {
                    "node_type": "start",
                    "label": "Từ khóa & Chủ đề",
                    "config": {"objective": "Literature mapping on Vision Transformers in Medical Imaging"},
                    "status": "idle",
                },
            },
            {
                "id": "node-fork",
                "type": "parallel_branch",
                "position": {"x": 280, "y": 180},
                "data": {
                    "node_type": "parallel_branch",
                    "label": "Tìm kiếm Song song",
                    "config": {"max_concurrency": 2},
                    "status": "idle",
                },
            },
            {
                "id": "node-mcp-arxiv",
                "type": "mcp_tool",
                "position": {"x": 520, "y": 80},
                "data": {
                    "node_type": "mcp_tool",
                    "label": "Tìm kiếm arXiv / OpenAlex",
                    "config": {"tool_name": "web_search", "args": {"query": "Medical Vision Transformers 2024-2026", "kind": "papers"}},
                    "status": "idle",
                },
            },
            {
                "id": "node-native-literature",
                "type": "research_engine",
                "position": {"x": 520, "y": 280},
                "data": {
                    "node_type": "research_engine",
                    "label": "Truy vấn Thư viện Native research",
                    "config": {"engine": "phdlab", "action": "search_papers", "params": {"n": 10}},
                    "status": "idle",
                },
            },
            {
                "id": "node-join",
                "type": "join",
                "position": {"x": 780, "y": 180},
                "data": {
                    "node_type": "join",
                    "label": "Hội tụ Danh mục Bài báo",
                    "config": {"join_strategy": "wait_all"},
                    "status": "idle",
                },
            },
            {
                "id": "node-synthesis",
                "type": "agent_task",
                "position": {"x": 1020, "y": 180},
                "data": {
                    "node_type": "agent_task",
                    "label": "Trích xuất & Tổng hợp Bằng chứng",
                    "config": {
                        "agent_role": "reviewer",
                        "prompt": "Phân loại các phương pháp theo ma trận so sánh, trích dẫn chuẩn DOI và đánh giá mức độ tin cậy.",
                    },
                    "status": "idle",
                },
            },
            {
                "id": "node-output",
                "type": "output",
                "position": {"x": 1280, "y": 180},
                "data": {
                    "node_type": "output",
                    "label": "Báo cáo Tổng quan (Literature_Review.md)",
                    "config": {"target_filename": "Literature_Review.md", "format": "markdown"},
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "node-start", "target": "node-fork"},
            {"id": "e2", "source": "node-fork", "target": "node-mcp-arxiv"},
            {"id": "e3", "source": "node-fork", "target": "node-native-literature"},
            {"id": "e4", "source": "node-mcp-arxiv", "target": "node-join"},
            {"id": "e5", "source": "node-native-literature", "target": "node-join"},
            {"id": "e6", "source": "node-join", "target": "node-synthesis"},
            {"id": "e7", "source": "node-synthesis", "target": "node-output"},
        ],
    },
    {
        "id": "tpl-hypothesis-to-experiment",
        "name": "Giả thuyết đến Thiết kế & Chạy Thí nghiệm (Hypothesis to Experiment)",
        "name_en": "Hypothesis to Experiment Design & Execution",
        "category": "experiment",
        "badge": "L3",
        "description": "Chuyển hóa giả thuyết thành quy trình thí nghiệm chính xác: Thiết lập đối chứng, tạo kịch bản, chạy thử nghiệm sandbox và thu thập metrics.",
        "description_en": "Translate hypothesis into rigorous experimental design: baseline selection, protocol generation, sandbox run, and metric collection.",
        "is_preset": True,
        "nodes": [
            {
                "id": "node-start",
                "type": "start",
                "position": {"x": 50, "y": 150},
                "data": {
                    "node_type": "start",
                    "label": "Giả thuyết Đầu vào",
                    "config": {"objective": "Kiểm nghiệm giả thuyết HYPE-001 về tốc độ suy luận"},
                    "status": "idle",
                },
            },
            {
                "id": "node-protocol",
                "type": "agent_task",
                "position": {"x": 280, "y": 150},
                "data": {
                    "node_type": "agent_task",
                    "label": "Thiết kế Đề cương Thí nghiệm (Protocol)",
                    "config": {
                        "agent_role": "researcher",
                        "prompt": "Xây dựng giao thức kiểm thử: Biến độc lập, biến phụ thuộc, nhóm đối chứng và seed ngẫu nhiên.",
                    },
                    "status": "idle",
                },
            },
            {
                "id": "node-approval",
                "type": "human_approval",
                "position": {"x": 520, "y": 150},
                "data": {
                    "node_type": "human_approval",
                    "label": "Duyệt Giao thức & Tài nguyên GPU",
                    "config": {"checkpoint_title": "Chấp thuận phân bổ tài nguyên tính toán cho thí nghiệm"},
                    "status": "idle",
                },
            },
            {
                "id": "node-codegen",
                "type": "tool_skill",
                "position": {"x": 760, "y": 150},
                "data": {
                    "node_type": "tool_skill",
                    "label": "Tạo Mã Thí nghiệm (Native Code)",
                    "config": {"skill": "code", "input_arg": "Implement the approved research objective in the active code project"},
                    "status": "idle",
                },
            },
            {
                "id": "node-sandbox",
                "type": "mcp_tool",
                "position": {"x": 1000, "y": 150},
                "data": {
                    "node_type": "mcp_tool",
                    "label": "Chạy Thực thi Sandbox Docker",
                    "config": {"tool_name": "sandbox_run_code", "args": {"command": "python train.py --epochs 5 --eval"}},
                    "status": "idle",
                },
            },
            {
                "id": "node-eval-gate",
                "type": "evaluation_gate",
                "position": {"x": 1240, "y": 150},
                "data": {
                    "node_type": "evaluation_gate",
                    "label": "Kiểm định Metrics & Tái lập",
                    "config": {"metric_key": "accuracy", "min_threshold": 0.85},
                    "status": "idle",
                },
            },
            {
                "id": "node-end",
                "type": "end",
                "position": {"x": 1480, "y": 150},
                "data": {
                    "node_type": "end",
                    "label": "Kết thúc Thí nghiệm",
                    "config": {"export_ro_crate": True},
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "node-start", "target": "node-protocol"},
            {"id": "e2", "source": "node-protocol", "target": "node-approval"},
            {"id": "e3", "source": "node-approval", "target": "node-codegen"},
            {"id": "e4", "source": "node-codegen", "target": "node-sandbox"},
            {"id": "e5", "source": "node-sandbox", "target": "node-eval-gate"},
            {"id": "e6", "source": "node-eval-gate", "target": "node-end"},
        ],
    },
    {
        "id": "tpl-deep-learning-research",
        "name": "Nghiên cứu Học Sâu & Tối ưu Siêu tham số (Deep Learning Research)",
        "name_en": "Deep Learning Experimentation & Iterative Tuning",
        "category": "experiment",
        "badge": "L3/L4",
        "description": "Vòng lặp tự động huấn luyện, đánh giá mất mát (loss curve), rẽ nhánh điều kiện và tinh chỉnh mô hình học sâu có giới hạn.",
        "description_en": "Automated training loop, loss evaluation, conditional branching, and bounded hyperparameter tuning.",
        "is_preset": True,
        "nodes": [
            {
                "id": "node-start",
                "type": "start",
                "position": {"x": 50, "y": 160},
                "data": {
                    "node_type": "start",
                    "label": "Mô hình & Siêu tham số",
                    "config": {"objective": "Tune learning rate and batch size for Vision Transformer"},
                    "status": "idle",
                },
            },
            {
                "id": "node-loop",
                "type": "bounded_loop",
                "position": {"x": 280, "y": 160},
                "data": {
                    "node_type": "bounded_loop",
                    "label": "Vòng lặp Huấn luyện (Tối đa 4 vòng)",
                    "config": {"max_iterations": 4, "stop_condition": "metrics.val_loss <= 0.25"},
                    "status": "idle",
                },
            },
            {
                "id": "node-train",
                "type": "mcp_tool",
                "position": {"x": 540, "y": 160},
                "data": {
                    "node_type": "mcp_tool",
                    "label": "Chạy Huấn luyện Model (Sandbox GPU)",
                    "config": {"tool_name": "sandbox_run_code", "args": {"command": "python train_loop.py"}},
                    "status": "idle",
                },
            },
            {
                "id": "node-condition",
                "type": "condition",
                "position": {"x": 780, "y": 160},
                "data": {
                    "node_type": "condition",
                    "label": "Hội tụ: Val Loss <= 0.25?",
                    "config": {"expression": "metrics.val_loss <= 0.25", "variable": "metrics.val_loss", "operator": "<=", "threshold": 0.25},
                    "status": "idle",
                },
            },
            {
                "id": "node-tune",
                "type": "agent_task",
                "position": {"x": 780, "y": 320},
                "data": {
                    "node_type": "agent_task",
                    "label": "Điều chỉnh Siêu tham số (Optuna Agent)",
                    "config": {"agent_role": "coder", "prompt": "Phân tích learning rate curve và đề xuất LR mới theo Cosine Annealing."},
                    "status": "idle",
                },
            },
            {
                "id": "node-checkpoint",
                "type": "checkpoint",
                "position": {"x": 1040, "y": 160},
                "data": {
                    "node_type": "checkpoint",
                    "label": "Lưu Trọng số Mô hình & Checkpoint",
                    "config": {"save_artifacts": True, "tag": "best_model_weights"},
                    "status": "idle",
                },
            },
            {
                "id": "node-end",
                "type": "end",
                "position": {"x": 1280, "y": 160},
                "data": {
                    "node_type": "end",
                    "label": "Hoàn tất Huấn luyện",
                    "config": {"export_ro_crate": True},
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "node-start", "target": "node-loop"},
            {"id": "e2", "source": "node-loop", "target": "node-train"},
            {"id": "e3", "source": "node-train", "target": "node-condition"},
            {"id": "e4", "source": "node-condition", "target": "node-checkpoint"},
            {"id": "e5", "source": "node-condition", "target": "node-tune"},
            {"id": "e6", "source": "node-tune", "target": "node-loop"},
            {"id": "e7", "source": "node-checkpoint", "target": "node-end"},
        ],
    },
    {
        "id": "tpl-paper-reproduction",
        "name": "Tái lập Kết quả Bài báo Khoa học (Paper Reproduction)",
        "name_en": "Scientific Paper Reproduction & Benchmark Audit",
        "category": "reproducibility",
        "badge": "L3",
        "description": "Nhập tệp PDF, trích xuất phương pháp, clone repository GitHub, chạy benchmark kiểm định và báo cáo sai số so với công bố gốc.",
        "description_en": "Ingest PDF, extract methods, clone repo, run benchmark suite, and audit reproducibility discrepancies against claims.",
        "is_preset": True,
        "nodes": [
            {
                "id": "node-start",
                "type": "start",
                "position": {"x": 50, "y": 150},
                "data": {
                    "node_type": "start",
                    "label": "Bài báo Mục tiêu (PDF/DOI)",
                    "config": {"objective": "Reproduce baseline results from Target Paper"},
                    "status": "idle",
                },
            },
            {
                "id": "node-extract",
                "type": "agent_task",
                "position": {"x": 280, "y": 150},
                "data": {
                    "node_type": "agent_task",
                    "label": "Trích xuất Phương pháp & Môi trường",
                    "config": {"agent_role": "literature", "prompt": "Liệt kê chi tiết siêu tham số, phiên bản thư viện, phần cứng và tập dữ liệu."},
                    "status": "idle",
                },
            },
            {
                "id": "node-swe",
                "type": "harnessNode",
                "position": {"x": 520, "y": 150},
                "data": {
                    "node_type": "harnessNode",
                    "label": "Thiết lập Môi trường & Test Suite",
                    "tool": "swe_bench",
                    "category": "code_benchmark",
                    "params": {"verify_tests": True, "min_pass_rate": 0.80},
                    "status": "idle",
                },
            },
            {
                "id": "node-repro-gate",
                "type": "evaluation_gate",
                "position": {"x": 760, "y": 150},
                "data": {
                    "node_type": "evaluation_gate",
                    "label": "Đánh giá Sai số Tái lập (Delta <= 5%)",
                    "config": {"metric_key": "reproducibility_score", "min_threshold": 0.95},
                    "status": "idle",
                },
            },
            {
                "id": "node-approval",
                "type": "human_approval",
                "position": {"x": 1000, "y": 150},
                "data": {
                    "node_type": "human_approval",
                    "label": "Xác nhận của Nhà nghiên cứu",
                    "config": {"checkpoint_title": "Duyệt báo cáo đối soát độ tin cậy tái lập"},
                    "status": "idle",
                },
            },
            {
                "id": "node-end",
                "type": "end",
                "position": {"x": 1240, "y": 150},
                "data": {
                    "node_type": "end",
                    "label": "Báo cáo Tái lập Sẵn sàng",
                    "config": {"require_summary": True},
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "node-start", "target": "node-extract"},
            {"id": "e2", "source": "node-extract", "target": "node-swe"},
            {"id": "e3", "source": "node-swe", "target": "node-repro-gate"},
            {"id": "e4", "source": "node-repro-gate", "target": "node-approval"},
            {"id": "e5", "source": "node-approval", "target": "node-end"},
        ],
    },
    {
        "id": "tpl-research-to-paper",
        "name": "Nghiên cứu đến Bài báo Hoàn chỉnh (Research to Paper)",
        "name_en": "Evidence-to-Paper Synthesis (PaperOrchestra)",
        "category": "writing",
        "badge": "L3/L4",
        "description": "Tích hợp động cơ PaperOrchestra: Lập dàn ý 5 cấp, soạn thảo từng phần học thuật, biên dịch LaTeX, phản biện độc lập và duyệt nộp bài.",
        "description_en": "Integrate PaperOrchestra engine: 5-level outline, section drafting, LaTeX compilation, peer review, and submission approval.",
        "is_preset": True,
        "nodes": [
            {
                "id": "node-start",
                "type": "start",
                "position": {"x": 50, "y": 150},
                "data": {
                    "node_type": "start",
                    "label": "Minh chứng & Kết quả Thực nghiệm",
                    "config": {"objective": "Viết bài báo khoa học chuẩn IEEE/ACM từ các kết quả đo lường"},
                    "status": "idle",
                },
            },
            {
                "id": "node-outline",
                "type": "tool_skill",
                "position": {"x": 280, "y": 150},
                "data": {
                    "node_type": "tool_skill",
                    "label": "Đề cương 5 Cấp (/outline)",
                    "config": {"skill": "outline", "input_arg": "5-level hierarchical outline"},
                    "status": "idle",
                },
            },
            {
                "id": "node-orchestra",
                "type": "research_engine",
                "position": {"x": 520, "y": 150},
                "data": {
                    "node_type": "research_engine",
                    "label": "Động cơ PaperOrchestra",
                    "config": {
                        "engine": "paperorchestra",
                        "action": "synthesize_paper",
                        "backend_mode": "skill",
                        "params": {"target_venue": "NeurIPS/ICLR", "citation_check": True},
                    },
                    "status": "idle",
                },
            },
            {
                "id": "node-latex",
                "type": "artifact_transformation",
                "position": {"x": 760, "y": 150},
                "data": {
                    "node_type": "artifact_transformation",
                    "label": "Biên dịch LaTeX sang PDF",
                    "config": {"transform_type": "compile_pdf", "target_path": "paper.pdf"},
                    "status": "idle",
                },
            },
            {
                "id": "node-review-gate",
                "type": "agent_task",
                "position": {"x": 1000, "y": 150},
                "data": {
                    "node_type": "agent_task",
                    "label": "Phản biện Độc lập (Peer Review)",
                    "config": {
                        "agent_role": "reviewer",
                        "prompt": "Đánh giá theo 4 tiêu chí ICLR: Tính mới, tính đúng đắn kỹ thuật, độ rõ ràng và mức độ ảnh hưởng.",
                    },
                    "status": "idle",
                },
            },
            {
                "id": "node-approval",
                "type": "human_approval",
                "position": {"x": 1240, "y": 150},
                "data": {
                    "node_type": "human_approval",
                    "label": "Chuyên gia Phê duyệt Nộp bài",
                    "config": {"checkpoint_title": "Quyết định cuối cùng của tác giả trước khi nộp hội nghị"},
                    "status": "idle",
                },
            },
            {
                "id": "node-output",
                "type": "output",
                "position": {"x": 1480, "y": 150},
                "data": {
                    "node_type": "output",
                    "label": "Gói Hồ sơ Bài báo (paper.zip)",
                    "config": {"target_filename": "final_manuscript.zip", "format": "zip"},
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "node-start", "target": "node-outline"},
            {"id": "e2", "source": "node-outline", "target": "node-orchestra"},
            {"id": "e3", "source": "node-orchestra", "target": "node-latex"},
            {"id": "e4", "source": "node-latex", "target": "node-review-gate"},
            {"id": "e5", "source": "node-review-gate", "target": "node-approval"},
            {"id": "e6", "source": "node-approval", "target": "node-output"},
        ],
    },
    {
        "id": "tpl-autonomous-research",
        "name": "Nghiên cứu Tự chủ Khép kín L4 (Full Autonomous Research)",
        "name_en": "End-to-End Autonomous Research Pipeline (L4)",
        "category": "autonomous",
        "badge": "L4 Autonomous",
        "description": "Chu trình nghiên cứu tự chủ toàn diện: Khảo sát văn hiến -> Đề xuất giả thuyết -> Lập trình thử nghiệm -> Kiểm định lặp có chặn -> Viết bài báo -> Ký số minh chứng.",
        "description_en": "Complete closed-loop autonomous research: literature survey -> hypothesis -> experimentation -> bounded iteration -> writeup -> cryptographic audit.",
        "is_preset": True,
        "nodes": [
            {
                "id": "node-start",
                "type": "start",
                "position": {"x": 50, "y": 180},
                "data": {
                    "node_type": "start",
                    "label": "Mục tiêu Nghiên cứu Cấp cao (L4)",
                    "config": {"objective": "Autonomous discovery of low-power attention mechanisms"},
                    "status": "idle",
                },
            },
            {
                "id": "node-team-formation",
                "type": "multi_agent_team",
                "position": {"x": 280, "y": 180},
                "data": {
                    "node_type": "multi_agent_team",
                    "label": "Đội ngũ Nghiên cứu Tự chủ",
                    "config": {
                        "team_name": "Autonomous Laboratory Team",
                        "coordination_mode": "adaptive",
                        "max_rounds": 3,
                    },
                    "status": "idle",
                },
            },
            {
                "id": "node-loop",
                "type": "bounded_loop",
                "position": {"x": 540, "y": 180},
                "data": {
                    "node_type": "bounded_loop",
                    "label": "Vòng lặp Nghiên cứu L4 (Max 3 lần)",
                    "config": {"max_iterations": 3, "stop_condition": "metrics.reproducibility >= 0.95"},
                    "status": "idle",
                },
            },
            {
                "id": "node-fork-exp",
                "type": "parallel_branch",
                "position": {"x": 780, "y": 180},
                "data": {
                    "node_type": "parallel_branch",
                    "label": "Triển khai Thí nghiệm Song song",
                    "config": {"max_concurrency": 2},
                    "status": "idle",
                },
            },
            {
                "id": "node-native-code",
                "type": "tool_skill",
                "position": {"x": 1020, "y": 80},
                "data": {
                    "node_type": "tool_skill",
                    "label": "Lập trình Thực nghiệm (Native Code)",
                    "config": {"skill": "code", "input_arg": "Implement the approved research objective in the active code project"},
                    "status": "idle",
                },
            },
            {
                "id": "node-native-experiment",
                "type": "research_engine",
                "position": {"x": 1020, "y": 280},
                "data": {
                    "node_type": "research_engine",
                    "label": "Đối chiếu Bằng chứng (Native research)",
                    "config": {"engine": "phdlab", "action": "synthesize_literature"},
                    "status": "idle",
                },
            },
            {
                "id": "node-join-exp",
                "type": "join",
                "position": {"x": 1260, "y": 180},
                "data": {
                    "node_type": "join",
                    "label": "Hội tụ Kết quả & Minh chứng",
                    "config": {"join_strategy": "wait_all"},
                    "status": "idle",
                },
            },
            {
                "id": "node-eval",
                "type": "evaluation_gate",
                "position": {"x": 1480, "y": 180},
                "data": {
                    "node_type": "evaluation_gate",
                    "label": "Kiểm định Độc lập & Sổ cái",
                    "config": {"verify_sha256": True, "min_threshold": 0.90},
                    "status": "idle",
                },
            },
            {
                "id": "node-paper",
                "type": "research_engine",
                "position": {"x": 1700, "y": 180},
                "data": {
                    "node_type": "research_engine",
                    "label": "Biên soạn Bài báo (PaperOrchestra)",
                    "config": {"engine": "paperorchestra", "action": "synthesize_paper", "backend_mode": "skill"},
                    "status": "idle",
                },
            },
            {
                "id": "node-human-final",
                "type": "human_approval",
                "position": {"x": 1940, "y": 180},
                "data": {
                    "node_type": "human_approval",
                    "label": "Phê duyệt Xuất bản Cuối cùng",
                    "config": {"checkpoint_title": "Duyệt công bố bài báo và toàn bộ minh chứng L4"},
                    "status": "idle",
                },
            },
            {
                "id": "node-end",
                "type": "end",
                "position": {"x": 2180, "y": 180},
                "data": {
                    "node_type": "end",
                    "label": "Hoàn thành Dự án Nghiên cứu",
                    "config": {"export_ro_crate": True},
                    "status": "idle",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "node-start", "target": "node-team-formation"},
            {"id": "e2", "source": "node-team-formation", "target": "node-loop"},
            {"id": "e3", "source": "node-loop", "target": "node-fork-exp"},
            {"id": "e4", "source": "node-fork-exp", "target": "node-native-code"},
            {"id": "e5", "source": "node-fork-exp", "target": "node-native-experiment"},
            {"id": "e6", "source": "node-native-code", "target": "node-join-exp"},
            {"id": "e7", "source": "node-native-experiment", "target": "node-join-exp"},
            {"id": "e8", "source": "node-join-exp", "target": "node-eval"},
            {"id": "e9", "source": "node-eval", "target": "node-paper"},
            {"id": "e10", "source": "node-paper", "target": "node-human-final"},
            {"id": "e11", "source": "node-human-final", "target": "node-end"},
        ],
    },
]


def list_templates() -> list[dict[str, Any]]:
    """Return all available scientific research workflow templates."""
    return RESEARCH_TEMPLATES


def get_template(template_id: str) -> dict[str, Any] | None:
    """Retrieve template by id."""
    for t in RESEARCH_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None
