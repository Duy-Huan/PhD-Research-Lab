# 🤖 CLAUDE EXECUTION PROMPT: ADVANCED FEATURES IMPLEMENTATION
> **Vai trò:** Senior ML Platform Engineer + Architecture Guardrail.
> **Mục tiêu:** Chỉ thị tối cao hướng dẫn Claude/AI code bổ sung 4 tính năng nâng cao (Compute Orchestration, Domain Connectors, Provenance, Local Critic) vào cấu trúc source code hiện tại của dự án `PhD-Research-Lab` (v3.1.0) không phá vỡ core.

---

## 1. NGUYÊN TẮC CODE BẮT BUỘC (CODING GUARDRAILS)
1. **Không Chạm Vào Thô (Hands Off Core):** Tuyệt đối không sửa đổi cấu trúc logic nghiên cứu lõi (`backend/paper.py`, `backend/prompts.py`) khi chưa có thiết kế Adapter.
2. **Kế Thừa Thư Mục Hiện Tại:** 
   - Code backend mới phải nằm trong `backend/` và đăng ký route tại `backend/api_v31.py` hoặc tạo `backend/api_v32.py`.
   - File cấu hình hoặc lưu trữ thực thi mới phải nằm trong cấu trúc `data/workspace/` hoặc `data/results/`.
3. **Mô hình Trả về Khép kín:** Mọi hàm xử lý phải bọc trong `try-except` nghiêm ngặt, ghi log rõ ràng ra console để phục vụ debug cục bộ.

---

## 2. CHỈ THỊ IMPLEMENT CHI TIẾT THEO TỪNG TÍNH NĂNG

### 🚀 TÁC VỤ 1: CHUYỂN DỊCH HẠ TẦNG COMPUTING CỤ CỤC BỘ ➔ REMOTE (COMPUTE ORCHESTRATION)
- **Tập tin cần can thiệp:** Tạo mới `backend/clearml_adapter.py` và cập nhật bổ sung vào `backend/sandbox.py`.
- **Yêu cầu kỹ thuật:**
  - Thiết kế `ClearMLAdapter` kế thừa từ một interface trừu tượng (`ComputeBackend`).
  - Viết hàm `submit_remote_job(script_path: str, parameters: dict)` để đẩy mã nguồn dưới dạng `Task` vào hàng đợi (Queue) của ClearML thay vì chạy lệnh `docker exec` trực tiếp trên máy local khi người dùng bật chế độ `Remote`.
  - Giữ nguyên luồng chạy cũ làm Fallback (chạy local docker) nếu không kết nối được tới ClearML Server.

### 🧬 TÁC VỤ 2: XÂY DỰNG BỘ ĐIỀU PHỐI DỮ LIỆU CHUYÊN NGÀNH (DATA CONNECTOR REGISTRY)
- **Tập tin cần can thiệp:** Tạo mới thư mục `backend/connectors/` và file `backend/connectors/registry.py`.
- **Yêu cầu kỹ thuật:**
  - Viết lớp `DataConnectorRegistry` tự động quét (scan) toàn bộ file `.py` nằm trong thư mục `backend/connectors/`.
  - Định nghĩa một Base Class `BaseConnector` với hàm trừu tượng `fetch_data(query: str) -> dict`.
  - Viết sẵn 2 plugin mẫu: `huggingface_connector.py` (tải dataset) và `kaggle_connector.py` để làm mẫu cho AI Agent tự động gọi kỹ năng cào dữ liệu thô khi người dùng ra lệnh trong Data Chat.

### 📊 TÁC VỤ 3: ĐÓNG GÓI MINH CHỨNG SỐ LIỆU (ARTIFACT PROVENANCE INJECTION)
- **Tập tin cần can thiệp:** Cập nhật `backend/sandbox.py` (Hàm sau khi chạy code xong và sinh ra kết quả).
- **Yêu cầu kỹ thuật:**
  - Khi một task chạy trong sandbox kết thúc và xuất ra tệp tin hình ảnh (PNG/JPG) hoặc bảng biểu (CSV) trong thư mục `data/runs/<id>/figures/`.
  - Viết thêm hàm `inject_provenance_metadata(file_path: str, run_id: str, git_sha: str)`. 
  - Đối với file ảnh, sử dụng thư viện `Pillow` (PIL) để ghi thông tin nguồn gốc vào thẻ `Exif` hoặc `PNG text chunk`. Đối với CSV, chèn một dòng comment `# Provenance: run_id={id}, git_sha={sha}` ở ngay dòng đầu tiên của file để sau này Tool 3 (Writer) có thể truy vết ngược nguồn gốc tạo ra số liệu đó.

### 🧠 TÁC VỤ 4: THIẾT LẬP AGENT PHẢN BIỆN CHẠY NGẦM THỜI GIAN THỰC (LOCAL CRITIC AGENT)
- **Tập tin cần can thiệp:** Cập nhật `backend/llm.py` và `backend/api_v31.py`.
- **Yêu cầu kỹ thuật:**
  - Thiết kế một cơ chế chạy bất đồng bộ (`asyncio.create_task`). Khi Cloud Model (Claude) đang stream bài viết bài báo (Introduction/Methodology) về frontend.
  - Một hàm ngầm `run_local_critic(text_chunk: str)` sẽ được gọi liên tục, đẩy dữ liệu thô sang mô hình Local (qua cổng Ollama/LM Studio của máy người dùng).
  - Nhiệm vụ của Local Critic: Quét lỗi cú pháp LaTeX (thiếu dấu `$`, sai cấu trúc `\begin{}`), kiểm tra xem các mã trích dẫn `\cite{key}` sinh ra có nằm trong file `references.bib` cục bộ không. Nếu phát hiện lỗi, trả về một mảng JSON cảnh báo để Frontend hiển thị live badge màu đỏ ngay bên cạnh đoạn text đang stream.

---

## 3. QUY TRÌNH RA LỆNH CHO CLAUDEkhi CODE (PROMPT WORKFLOW)

Khi người dùng gõ: `"Claude hãy thực hiện Tác vụ X trong file CLAUDE_DEVELOPMENT_PROMPT.md"`, bạn phải thực hiện đúng 3 bước:

1. **Analysis Stage:** Đọc file mã nguồn hiện tại cần can thiệp trong repo (`PhD-Research-Lab`), xuất ra phân tích cấu trúc hàm hiện tại dưới dạng Markdown table.
2. **Drafting Stage:** Viết mã nguồn bổ sung chuẩn xác, giải thích rõ các tham số đầu vào/đầu ra và cách bọc lỗi để không làm hỏng app.
3. **Integration Stage:** Cung cấp chỉ dẫn chính xác (File path, dòng cần chèn hoặc thay thế) hoặc viết toàn bộ file mới để người dùng copy-paste trực tiếp vào repo.
