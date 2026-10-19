# 📑 PHD-RESEARCH-LAB CORE CAPABILITIES VERIFICATION CHECKLIST
> **Vai trò:** Chief QA Engineer + System Integration Auditor.
> **Mục tiêu:** Cung cấp bộ quy tắc và danh sách hạng mục kiểm tra tối cao để Claude quét, đối chiếu và xác minh tính toàn vẹn của toàn bộ mã nguồn (`backend/`, `frontend/`, `data/`) trước khi đóng gói hoặc nghiệm thu.

---

## 1. NGUYÊN TẮC KIỂM TRA MÃ NGUỒN (AUDIT GUARDRAILS)
Khi được yêu cầu chạy checklist này, Claude bắt buộc phải:
- Không được suy đoán. Mọi xác minh phải dựa trên sự tồn tại thực tế của hàm, route, hoặc component trong file.
- Ghi rõ trạng thái của từng mục:  (Đã hoàn thiện) |  (Chưa có / Thiếu hụt) | ⚠️ (Có lỗi tiềm ẩn / Cần refactor).
- Nếu phát hiện lỗi hoặc thiếu hụt, xuất ra chính xác đường dẫn file và gợi ý đoạn code sửa đổi trực tiếp.

---

## 2. DANH SÁCH KIỂM TRA CHI TIẾT TỪNG MODULE (THE CHECKLIST)

### 📊 MODULE 1: HẠ TẦNG VÀ QUẢN LÝ TÀI NGUYÊN VẬT LÝ (HARDWARE & SYSTEM)
*Đối chiếu trực tiếp với quy định tại `HARDWARE_RESOURCE_CONSTRAINT.md`*
- [ ] **Sysinfo Monitor:** Hàm đọc thông số GPU (VRAM/Temp), CPU, RAM, Disk có hoạt động theo chu kỳ 2 giây? Có sử dụng pure-python (`sysinfo.py`) để tránh Smart App Control prompt?
- [ ] **JIT VRAM Unload Loop:** Có tồn tại hàm tự động gửi lệnh giải phóng VRAM tới Ollama (`keep_alive: 0`) và LM Studio trước khi khởi chạy Sandbox huấn luyện nặng?
- [ ] **Docker Sandbox Limits:** Logic khởi chạy container có áp các cờ giới hạn cứng: RAM (12G-16G), CPU (6 cores), và passthrough GPU (`--gpus all`)?
- [ ] **Graceful Degradation:** Khi GPU dính lỗi hoặc quá nhiệt, hệ thống có bắt lỗi và tự động hạ cấp sang chế độ chạy thuần CPU (CPU Fallback) thay vì làm treo UI?

### 💻 MODULE 2: KHÔNG GIAN LÀM VIỆC VÀ ĐIỀU PHỐI (WORKSPACE & ORCHESTRATION)
- [ ] **VS Code Native Deep Link:** Frontend và Backend đã bóc tách Monaco Editor dở dang chưa? Có nút sinh URI `vscode://vscode-remote/...` mở trực tiếp Dev Container trên VS Code Desktop?
- [ ] **ClearML Cloud/Local Target Switch:** Tab Compute đã có thanh gạt chuyển vùng linh hoạt từ Local Docker sang Remote Cluster thông qua `ClearMLAdapter`?
- [ ] **Jupyter Session Link:** Có nút khởi chạy và lấy token an toàn trỏ thẳng trình duyệt sang Jupyter Server chạy ngầm trong container?
- [ ] **Native Git/GitHub Integration:** Mã nguồn có lưu đúng metadata (`git_commit_sha`, `repository_url`, GitHub token bảo mật ẩn trong `config.json`) thay vì tự xây hệ thống quản lý git riêng?

### 🧠 MODULE 3: BỘ NHỚ NGỮ CẢNH VÀ QUẢN LÝ TRI THỨC (CONTEXT & MEMORY)
- [ ] **3-Tier Memory Architecture:**
    - *Tier 1:* Lưu logs hội thoại và sandbox thô gần nhất.
    - *Tier 2:* Có tiến trình chạy ngầm gọi Local Model tự động gom cụm Tier 1 thành các tóm tắt phân đoạn (Episodes) khi vượt ngưỡng 24k tokens?
    - *Tier 3:* Lưu trữ biệt lập các bất biến: Mục tiêu, Giả thuyết, Locked Decisions, Best Metrics.
- [ ] **Context Graph Connection:** Các Node trên đồ thị tri thức (Hypotheses, Decisions) có chứa thuộc tính liên kết con trỏ trực tiếp với `task_id` của ClearML?
- [ ] **Context Decision Agent:** Có Agent tiếp nhận câu lệnh tự nhiên của người dùng để thực thi các tác vụ hàng loạt: Ghim (Pin) làm bối cảnh bắt buộc hoặc Thanh trừng (Purge) node tri thức lỗi thời?

### 🔬 MODULE 4: PIPELINE VIẾT BÀI BÁO VÀ PHẢN BIỆN (RESEARCH & PAPER WRITER)
- [ ] **Section-by-Section Deep Pipeline:** Logic sinh bài báo có chạy theo chu trình khép kín: Viết (Author) ➔ Đánh giá/Chấm điểm (Reviewer) ➔ Sửa đổi (Editor) cho từng chương mục, thay vì sinh cả bài một lúc gây tràn context window?
- [ ] **Section Briefs & Result Injection:** Hệ thống có tiếp nhận cấu hình chi tiết cho từng section (yêu cầu cấu trúc, giọng văn, kết quả đính kèm như ảnh, CSV) trước khi gọi LLM?
- [ ] **Citation Guard & Verification:** Có cơ chế tự động quét, đối chiếu trích dẫn `\cite{}` với file `references.bib` cục bộ, tự bôi đỏ lỗi `[CITATION NEEDED]` hoặc `[TBD]` đối với số liệu thiếu minh chứng?
- [ ] **Local Critic Engine:** Có tác vụ bất đồng bộ (`asyncio`) sử dụng Local Model chạy ngầm để quét và cảnh báo trực tiếp lỗi cú pháp LaTeX hoặc lỗi logic toán học ngay khi Cloud Model đang stream chữ về UI?
- [ ] **Deterministic LaTeX Compile:** Có tự động tìm kiếm các bộ biên dịch nội bộ (TeX Live, Tectonic...) để render PDF Preview chính xác, phân tách log lỗi tương ứng với từng chương mục?

### 🧬 MODULE 5: KẾT NỐI DỮ LIỆU VÀ MINH CHỨNG (DATA CONNECTORS & PROVENANCE)
- [ ] **DataConnectorRegistry Scanner:** Lớp quản lý có tự động quét và nạp các plugin kỹ năng cào dữ liệu chuyên ngành (HuggingFace, Kaggle, ChEBI...) nằm trong thư mục `backend/connectors/`?
- [ ] **Artifact Provenance Injection:** Sau khi Sandbox xuất ra đồ thị (PNG) hoặc bảng số liệu (CSV), hệ thống có tự động nhúng (inject) Metadata định danh (`run_id`, `git_sha`, `task_id`) vào thẳng file kết quả để phục vụ truy vết ngược sau này?

---

## 3. QUY TRÌNH BAO VÂY LỖI KHI XỬ LÝ (VERIFICATION WORKFLOW)
Khi người dùng kích hoạt: `"Claude chạy Checklist xác minh file backend/X.py"`, hãy thực thi theo cấu trúc:
1. **Scope Deficit:** Liệt kê các tính năng trong checklist thuộc file đó đang bị thiếu hụt hoặc chưa tối ưu phần cứng.
2. **Security & Performance Audit:** Kiểm tra rò rỉ bộ nhớ (Memory leak) hoặc tranh chấp VRAM trong file code hiện tại.
3. **Refactor Blueprint:** Cung cấp đoạn mã nguồn sửa đổi hoàn chỉnh, được bọc trong các khối an toàn bảo vệ phần cứng.
