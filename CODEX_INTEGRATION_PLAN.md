# CODEX INTEGRATION — plan & implementation notes (v3.2)

## Phase A findings (repository)
| Câu hỏi | Thực tế trong repo |
|---|---|
| Abstraction agent hiện có | Không có `AgentBackend`; agent = prompt + engine qua `llm.call_agent/stream_agent` (`config.AGENTS`). Co-coding agent riêng: `coder.py` + `/api/ide/agent` (giao thức ```file=``` / ```run```, self-debug). |
| Claude được gọi thế nào | `llm.anthropic_chat` / `_stream_anthropic` (HTTP Messages API, stream SSE), không có resume/cancel ngoài việc hủy request. Giữ nguyên 100 %. |
| Workspace | `sandbox.code_dir()` = `<project>/code`, kiểm tra đường dẫn bằng `ide_fs.safe`. |
| Lưu trạng thái | JSON theo project; Codex dùng `<project>/agent_runs/cx-*.json`. |
| Context Memory | Không tự ghi kết luận của agent. Codex chỉ cập nhật Working Memory (`set_agent_state("codex", …)`). |

## Cơ chế chọn: Codex CLI non-interactive
- Lựa chọn nhỏ nhất phù hợp backend Python: `codex exec --json --sandbox <mode> --skip-git-repo-check -` (prompt qua stdin), không cần Node SDK hay App Server.
- Đã đối chiếu tài liệu chính thức (Non-interactive mode): sandbox mặc định read-only; `--sandbox workspace-write` cho phép sửa; `--json` → JSONL (`thread.started{thread_id}`, `turn.started`, `item.started/item.completed{item}`, `turn.completed{usage}`, `turn.failed`, `error`); `codex exec resume <SESSION_ID>`; auth = `codex login` (gói ChatGPT) hoặc `CODEX_API_KEY` (tính phí API) — **hai cách tính phí khác nhau**.
- Không dùng `danger-full-access`. `--full-auto` đã ngừng hỗ trợ theo tài liệu.

## Ánh xạ vòng đời
`starting → running → completed | failed | cancelled` · `thread_id` từ `thread.started` · `final_message` từ `item.completed(agent_message)` · `usage` từ `turn.completed` · lỗi từ `turn.failed/error` · hủy = kill cây tiến trình · timeout = `codex.timeout_s`.

## Quyền & an toàn
- Workspace luôn là `code/` của project (không nhận path từ trình duyệt).
- Mặc định read-only; ghi chỉ khi request có `allow_write=true` và UI đã hỏi xác nhận; chế độ được lưu cùng run.
- Không commit/push/xóa: file thay đổi lấy từ `git status` trước/sau (nhãn *git-derived*), không tin lời agent.
- Không lưu credential Codex trong app/log; thông báo trạng thái đăng nhập được lọc chuỗi `sk-…`.

## Đã làm (v3.2)
`backend/integrations/agents.py` (CodexBackend, apply_event, persist), API `/api/codex/*`, Control Center → 🤖 Codex (chạy, theo dõi, hủy, Review in VS Code), cấu hình `codex.{enabled,binary,model,timeout_s}`, unit test mapping/trạng thái, test thật opt-in `PHDLAB_CODEX_LIVE=1`.

## Chưa làm / cần quyết định
1. Chưa kiểm chứng với CLI thật (chưa cài trên máy audit).
2. Chưa gom co-coding agent cũ và Codex dưới cùng một interface `AgentBackend` chung (đề xuất ở M5/M6 sau khi Codex được dùng thật).
3. Liên kết run Codex ↔ hypothesis/experiment: trường `link` đã có trong API, UI chưa hiển thị chọn liên kết.
