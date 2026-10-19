# 🔬 CLAUDE RESEARCH ALIGNMENT & ARCHITECTURAL GUIDELINES
> **Trạng thái:** Tài liệu đối chiếu ý tưởng (Ideation Reference) - Đứng cạnh `Target` và `Milestone` files.
> **Mục tiêu:** Định hướng cho Claude/AI hiểu rõ triết lý kiến trúc của PhD-Research-Lab khi so sánh với Anthropic Claude Science, giữ vững vai trò Control Plane, không tự xây lại hạ tầng đã chín muồi (ClearML, VS Code, Docker).

---

## 1. Tầm Nhìn Chiến Lược (Strategic Alignment)

PhD-Research-Lab không phải là một Wrapper Chatbot thông thường. Hệ thống chia sẻ **75% - 80% tư duy quy trình cốt lõi** với giải pháp nghiên cứu cao cấp nhất hiện tại là **Anthropic Claude Science (Claude Research Assistant)**, nhưng được tối ưu hóa theo mô hình **Hybrid IDE / Edge Computing** dành cho các kỹ sư Deep Learning chạy máy Local.

### Ma Trận Định Vị Tính Năng (Concept Mapping)

| Quy trình Nghiên cứu | Triết lý Claude Science (Anthropic) | Hiện thực hóa tại PhD-Research-Lab |
| :--- | :--- | :--- |
| **Lập kế hoạch & Giả thuyết** | Trình cấu trúc Planner Agent | **Tool 1 (Lit2Plan)** ➔ Tạo SOTA taxonomy, giả thuyết falsifiable và 6-month roadmap. |
| **Thiết kế thực nghiệm** | Code Generation trong Cloud Sandbox | **Tool 2 (Experimental Design)** ➔ Sinh mã nguồn toán học LaTeX và file xương cá `experiment_skeleton.py`. |
| **Bộ nhớ & Trôi bối cảnh** | State-space / Context Graph (Cloud) | **3-Tier Project Memory & Context Graph** ➔ Gom cụm Tier 1 (Raw logs) ➔ Tier 2 (Summarized Episodes via Local Model) ➔ Tier 3 (Locked Decisions). |
| **Kiểm soát tính tin cậy** | Bản hãng tự tối ưu cấu trúc Prompt | **Citation Guard & Red TBD Marks** ➔ Tự động triệt tiêu citation ảo, bắt buộc kết quả thực nghiệm phải trung thực dựa trên số liệu đo đạc thực tế. |
| **Chuỗi Phản biện chuyên sâu** | Iterative Critic-Writer Loop | **Deep Pipeline Section-by-Section** ➔ Phân rã bài báo thành các cấu trúc nhỏ: Write ➔ Review ➔ Revise (Bao vây và triệt tiêu lỗi logic). |

---

## 2. Điểm Khác Biệt & Lợi Thế Cốt Lõi (The Edge)

Khi phát triển code hoặc tư vấn tính năng mới cho dự án này, Claude **bắt buộc phải ghi nhớ** các lợi thế sinh tử sau của PhD-Research-Lab so với giải pháp của Anthropic:

1. **Kiểm soát chất lượng bằng "Section Briefs" (v3.1):** Cho phép con người can thiệp, gài kết quả thực nghiệm (`uploaded results`, `Code IDE runs`) và định hướng giọng văn cho từng chương mục trước khi AI viết. Đây là cơ chế kiểm soát (Steerability) thực tế hơn cách viết prompt tự do của bản hãng.
2. **Hạ tầng Hybrid (Linh hoạt chi phí):** Các tác vụ đọc hiểu nền, tóm tắt log, trích xuất BibTeX được đẩy cho **Local Models (Ollama / LM Studio)** để đạt mức chi phí bằng 0 (Zero API cost), để dành Cloud AI (Claude Sonnet/Opus) cho các tác vụ suy luận học thuật tối cao.
3. **Thực thi Phần cứng Nặng (Heavy GPU):** Khác với môi trường Cloud Sandbox giới hạn của hãng, dự án này giao tiếp trực tiếp với **Docker Sandbox (GPU Passthrough)** cục bộ, cho phép chạy các mô hình AI/Deep Learning lớn trực tiếp trên phần cứng của nghiên cứu sinh.

---

## 3. Nguyên Tắc Kiến Trúc Chuyển Dịch (Migration Principles)
*Áp dụng khi refactor hoặc viết module mới cho `backend/` và `frontend/`*

Tuyệt đối tuân thủ mô hình **Research Control Plane / Control Center**. PhD-Research-Lab giữ vai trò quản lý Tri thức khoa học, ý tưởng, giả thuyết, và kết luận. Dự án **KHÔNG** đóng vai trò thực thi hạ tầng thô.

```text
               [ PhD Research Lab (Control Plane) ]
            (Ý tưởng, Giả thuyết, Tri thức, Quyết định)
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Coding IDE     │  │Experiment/MLOps  │  │ Container Run    │
│  (VS Code Native)│  │(ClearML Backend) │  │ (Docker Cục Bộ)  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Quy tắc Phân Định Trách Nhiệm (Separation of Concerns)

*   **Không tự xây lại:** Không cố gắng viết thêm code cho Text Editor (Đã có VS Code tiếp quản), không viết thêm UI biểu đồ Loss/Accuracy (Đã có ClearML Web UI hiển thị ở `localhost:8080`), không tự viết script quản lý container phức tạp (Ủy nhiệm cho Docker/Dev Containers).
*   **Thiết kế tầng Abstraction Layer:** Tất cả mã nguồn kết nối hạ tầng phải nằm sau các Interface trừu tượng (như `WorkspaceAdapter`, `ExperimentBackend`). Hệ thống gọi các lớp này dưới dạng các Adapter (ví dụ: `ClearMLAdapter`), cho phép hoán đổi backend sau này mà không chạm vào lõi nghiên cứu (Research Core).

---

## 4. Đồng Bộ Dữ Liệu: Tri Thức Khoa Học ↔ Hạ Tầng MLOps

Khi thiết kế hoặc can thiệp vào bộ nhớ hệ thống (`backend/memory.py` hoặc `context_graph.py`), quy định lưu trữ thông tin được phân định như sau:

*   **ClearML (Hạ tầng thô) lưu trữ:** Toàn bộ bảng chạy thực nghiệm, các thông số Hyperparameters, Logs hệ thống (stdout/stderr), biểu đồ độ chính xác và tệp tin Model Checkpoint đồ sộ.
*   **PhD Context Memory (Trí tuệ nhân tạo) lưu trữ:** Chỉ ghi nhận **`task_id`** của ClearML làm con trỏ (Pointer), đi kèm là diễn giải khoa học của Agent: *Tại sao chạy task này? Hiện tượng bất thường quan sát được là gì? Kết quả đo đạc này chứng minh hay bác bỏ giả thuyết khoa học nào?*

---

## 5. Chỉ Thị Cho Claude Khi Viết Code (Instructions for AI Development)

1. **Đọc kỹ cấu trúc hiện tại trước khi sửa đổi:** Không phá vỡ cấu trúc thư mục của bản v3.1.0 (`backend/app.py`, `backend/sandbox.py`, `backend/memory.py`).
2. **Ưu tiên tích hợp qua API & Deep Links:** Thay vì viết code vẽ lại log Terminal lên UI của app, hãy thiết kế các nút hành động sinh Deep Link (ví dụ: mở link trực tiếp dẫn tới Task trên ClearML Local Web UI, hoặc gọi URI dạng `vscode://` để mở IDE Native).
3. **Giữ vững tính thực dụng học thuật:** Mọi module viết ra phải phục vụ mục tiêu tối thượng là xuất bản bài báo khoa học chất lượng cao (hỗ trợ export cấu trúc `latex.zip` deterministic, biên dịch PDF native).
