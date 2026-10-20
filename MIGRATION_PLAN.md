# MIGRATION PLAN — PhD Research Lab → Research OS

> Thứ tự ưu tiên thiết kế theo yêu cầu: (1) Target + Codex + LLM gateway + development tasks → (2) Context Memory →
> (3) milestones → (4) checklist → (5) alignment Claude Science → (6) phần cứng → (7) customer flows.
> Context Memory được xem là quan trọng nhất về giá trị nên được triển khai sớm ngay sau nền móng.

## Nguyên tắc
- Không xóa implementation cũ trước khi implementation mới được kiểm chứng và người dùng duyệt.
- Mỗi bước có test (`python -m unittest discover -s tests`) và tiêu chí nghiệm thu đo được.
- Tích hợp chưa có trên máy → báo trạng thái thật, không giả lập.

## Trạng thái milestone

| Milestone | Nội dung | Trạng thái | Ghi chú |
|---|---|---|---|
| M1 | Audit & kiến trúc | ✅ Done (v3.2) | `ARCHITECTURE_AUDIT.md`, `ARCHITECTURE.md`, file này, `INTEGRATION_STATUS.md`. |
| M2 | Integration layer | ✅ Phần nền (v3.2) | `backend/integrations/` (status, workspace, experiment, agents), config + mask secret, contract tests. |
| CM | Context Memory v2 | ✅ v3.2 | page-store, LOD tree, tri-search + RRF + reranker, compiler, compressor watermark. |
| HW | Resource governor | ✅ v3.2 | policy, caps, JIT unload, thermal guard, CPU fallback, GPU-busy routing. |
| M3 | VS Code + Git + Docker + Jupyter | ✅ v3.2 (Jupyter chưa kiểm chứng thật) | Monaco IDE đã gỡ; VS Code + extension Codex là nơi viết code; tab Workspace & Runs; Dev Container, Environment Manager, git SHA vào run. |
| M4 | ClearML | ✅ offline mode (v3.2) · 🟡 server mode chưa kiểm chứng | `pip install clearml` (setup.bat / nút trong UI) đủ để ghi mọi run thành phiên ClearML offline; server + import: test opt-in `PHDLAB_CLEARML_LIVE=1`. |
| M5 | Deep Learning workflow | ⏳ | Experiment spec có cấu trúc (seed, dataset version), baseline training example. |
| M6 | Research Control Center | 🟡 Tab mới (v3.2) | Dashboard, timeline, workspace, integrations, provenance. Chưa redesign toàn bộ điều hướng. |
| M7 | Model serving | ⏳ | Chỉ abstraction + tài liệu; không cài Kubernetes. vLLM/BentoML khi có use case. |
| M8 | E2E validation | ⏳ | Cần Docker daemon chạy + ClearML để kiểm chứng chuỗi đầy đủ. |
| CX | Codex backend | 🟡 Adapter (v3.2), **chưa kiểm chứng** | `codex` CLI chưa cài trên máy audit. Xem `CODEX_INTEGRATION_PLAN.md`. |
| LLM | Gateway đa provider | ✅ v3.2 | DeepInfra, 9Router, OmniRoute + chế độ `auto`; header 9Router là tùy chọn, chưa kiểm chứng. |

## Các bước tiếp theo đề xuất (cần người dùng quyết định)
1. Bật Docker Desktop, chạy `python -m unittest` + kiểm thử tay một run GPU để xác nhận JIT unload & caps.
2. Cài ClearML server (docker compose chính thức) + `pip install clearml`, cấu hình trong Control Center → chạy test opt-in.
3. ~~Gỡ Monaco IDE~~ — đã làm (v3.2). Quy tắc VRAM: run GPU bị chặn khi LLM local còn trong VRAM, unload thủ công.
4. Cài Codex CLI (`npm i -g @openai/codex`), `codex login`, chạy smoke test opt-in.
5. M5: chuẩn hóa experiment spec + ví dụ baseline.

## Rollback
Mọi thay đổi v3.2 là bổ sung. Dữ liệu cũ (`memory/project_state.json`, `context_graph.json`, runs) giữ nguyên định dạng;
file mới (`memory/research.json`, `memory/pages/`, `memory/working.json`, `memory/embeddings.json`) có thể xóa an toàn để quay về v3.1.
Tắt từng tính năng: `memory.v2_pipeline=false`, `resources.require_unload=false`, `resources.enforce_caps=false`,
`critic.enabled=false`, `provenance.enabled=false`.
