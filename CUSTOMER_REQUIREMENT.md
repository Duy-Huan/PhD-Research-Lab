# 📑 ACADEMIC REQUIREMENTS & END-TO-END RESEARCH LIFECYCLE
> **Dự án:** PhD-Research-Lab (Control Plane OS)
> **Mục tiêu:** Bản đặc tả yêu cầu khách hàng (PRD) và kịch bản trải nghiệm người dùng tích hợp. Đây là tài liệu tối cao cấu trúc hành vi cho AI Agent khi thiết kế logic Frontend, Backend và thiết lập kịch bản kiểm thử toàn diện (Integration Testing).

---

## PART 1: 04 KỊCH BẢN TRẢI NGHIỆM ĐƠN LẺ (ACCEPTANCE CRITERIA)

### 🔬 Kịch Bản 1: Tự Động "Săn" Ý Tưởng Khoa Học (Literature SOTA to Hypothesis)
* **Bối cảnh:** Người dùng vừa tải về 20-30 file bài báo PDF mới nhất từ các hội nghị học thuật đỉnh cao (CVPR, NeurIPS, ICML) và cần tìm ra hướng đi mới mà không có thời gian đọc thủ công toàn bộ.
* **Luồng nghiệp vụ:**
  1. Người dùng kéo thả toàn bộ thư mục chứa các file PDF vào **Tool 1 (Lit2Plan)**.
  2. Hệ thống ngầm gọi `PyMuPDF` bóc tách text, dùng **Local Model (Ollama/LM Studio)** chạy bằng CPU/RAM để tự động trích xuất các bảng dữ liệu SOTA và phương pháp cốt lõi (Chi phí API = 0).
  3. Hệ thống tổng hợp dữ liệu cấu trúc này, chuyển vùng định tuyến lên **Cloud Claude API** để kích hoạt tư duy lập luận khoa học tối cao (Scientific Reasoning), tìm ra lỗ hổng nghiên cứu (Research Gaps).
* **Tiêu chuẩn nghiệm thu (Acceptance Criteria):**
  - Hệ thống tự động xuất ra một mã giả thuyết khoa học định danh dạng JSON ghim trực tiếp lên **Đồ thị tri thức (Context Graph)** (Ví dụ: `HYPE-006: Adaptive-Attention Mechanism`).

### 🐋 Kịch Bản 2: Tự Vá Lỗi Mã Nguồn Thực Nghiệm (Self-Healing Sandboxed Run)
* **Bối cảnh:** Người dùng nhấn nút chạy thử nghiệm mô hình Deep Learning trong môi trường Sandbox nhưng code bị crash giữa chừng do lỗi cú pháp toán học, lỗi ma trận PyTorch hoặc lỗi thư viện.
* **Luồng nghiệp vụ:**
  1. Người dùng nhấn nút **`[Execute Sandbox]`** từ giao diện PhD-Lab UI để chạy file `train.py`.
  2. Lớp hạ tầng tự động giải phóng VRAM (Unload Local LLM) để nhường trọn vẹn tài nguyên cho Docker Container thực thi script.
  3. Nếu mã nguồn bị lỗi và dừng đột ngột, `backend/sandbox.py` lập tức bắt lấy luồng thông báo lỗi thô (`stderr`).
  4. Hệ thống gọi AI Agent đọc log lỗi kết hợp với file code hiện tại, tự động lập luận viết ra một bản vá sửa lỗi (Bug fix patch).
* **Tiêu chuẩn nghiệm thu (Acceptance Criteria):**
  - Hệ thống tự động ra lệnh cho Docker Container tái khởi động và thực thi lại lượt chạy mới với bản vá đã sửa mà không cần con người can thiệp gõ lệnh thủ công.

### 🛡️ Kịch Bản 3: Truy Vết Ngược Nguồn Gốc Minh Chứng (Artifact Provenance Look-up)
* **Bối cảnh:** Người dùng chuẩn bị viết bài báo học thuật chuẩn ISI/Scopus nhưng trong máy có hàng trăm file ảnh đồ thị, file kết quả CSV chạy từ nhiều tuần trước và không thể nhớ file nào ứng với siêu tham số (Hyperparameters) nào.
* **Luồng nghiệp vụ:**
  1. Người dùng kéo thả một file ảnh đồ thị thực nghiệm cục bộ (Ví dụ: `loss_curve_final.png`) vào khung giám định của PhD-Lab UI.
  2. Bộ bóc tách của backend đọc các thẻ siêu dữ liệu ẩn (`PNG text chunk` được hệ thống tự động niêm phong qua thư viện `Pillow` tại thời điểm chạy sandbox xong).
  3. Hệ thống trích xuất ra mã `phd_clearml_task_id` chứa trong ảnh.
* **Tiêu chuẩn nghiệm thu (Acceptance Criteria):**
  - Hệ thống thực hiện lệnh gọi API sang **ClearML Local Server** (`localhost:8080`) để kéo ngược và hiển thị trực quan lên màn hình: Mã nguồn chính xác lúc chạy, phiên bản Git Commit, cấu hình siêu tham số (`Hyperparameters`), và biểu đồ tiêu hao phần cứng tại đúng thời điểm sinh ra bức ảnh đó.

### 📝 Kịch Bản 4: Phản Biện Và Soát Lỗi Bản Thảo Thần Tốc (Live Critic Loop)
* **Bối cảnh:** Người dùng sử dụng AI để viết chương Phương pháp nghiên cứu (Methodology Section) bằng ngôn ngữ LaTeX và cần đảm bảo tuyệt đối không có lỗi cú pháp hoặc lỗi trích dẫn ảo (Hallucination) lọt qua mắt ban biên tập tạp chí.
* **Luồng nghiệp vụ:**
  1. Người dùng bật **Tool 3 (Paper Writer)**, điền yêu cầu và nhấn nút sinh văn bản dựa trên kết quả thực nghiệm.
  2. Do GPU vật lý đang bận, hệ thống tự động định tuyến yêu cầu lên **Cloud Claude API** để stream bài viết học thuật về màn hình.
  3. Đồng thời, một tiến trình nền chạy bất đồng bộ (`asyncio`) gọi **Local Model** chạy bằng CPU/RAM hoạt động song song như một kính lúp soi lỗi.
* **Tiêu chuẩn nghiệm thu (Acceptance Criteria):**
  - Local Critic liên tục quét chuỗi text đang stream về: Kiểm tra lỗi cú pháp LaTeX (Thiếu dấu `$`, sai cấu trúc `\begin{}`) và đối chiếu các mã trích dẫn `\cite{key}` với file dữ liệu `references.bib` cục bộ của người dùng. Nếu phát hiện sai sót, lập tức bắn **Badge cảnh báo màu đỏ** live trực tiếp lên UI tại đúng vị trí dòng lỗi.

---

## PART 2: CHU KỲ SỐNG NGHIÊN CỨU TOÀN DIỆN (THE FULL FLOW LIFECYCLE)

Khi các kịch bản đơn lẻ xâu chuỗi lại với nhau, hệ thống bắt buộc phải duy trì luồng chuyển dịch trạng thái (State Transitions) liền mạch như sau:

```text
 [Giai đoạn 1: Khởi động] ➔ Đọc 30 PDFs ➔ Sinh Giả thuyết HYPE-005 (Lit2Plan)
            │
            ▼
 [Giai đoạn 2: Lập mã]   ➔ Bấm [Open in VS Code] ➔ Code train_medical.py trong Container
            │
            ▼
 [Giai đoạn 3: Thực thi] ➔ Bấm [Execute Sandbox] ➔ JIT Unload VRAM ➔ 100% GPU cày DL
            │
            ▼
 [Giai đoạn 4: Viết lách] ➔ Stream bài báo (Cloud) ➔ Local Critic check lỗi LaTeX bằng CPU
            │
            ▼
 [Giai đoạn 5: Xuất bản] ➔ Đồ thị loss.png tự nhúng Metadata ➔ Đồng bộ ClearML ➔ Ra gói latex.zip
```

### 📈 GIAI ĐOẠN 1: TỪ VĂN BẢN SOTA ĐẾN KHỞI TẠO Ý TƯỞNG (09:00 AM)
*   **Hành động của User:** Kéo thả thư mục chứa 30 file PDF nghiên cứu mới nhất từ hội nghị NeurIPS vào **Tool 1 (Lit2Plan)** trên UI.
*   **Hệ thống xử lý:** Thực thi trọn vẹn nghiệp vụ của **Kịch bản 1**.
*   **Trạng thái hệ thống (State):** Sinh mã giả thuyết **`HYPE-005: Saturated-Loss Optimization`**, tạo một Node mới trên **Context Graph** và lưu vào **Context Memory Tier 3**.

### 💻 GIAI ĐOẠN 2: THIẾT LẬP MÔI TRƯỜNG VÀ ĐỒNG CHÈN MÃ NGUỒN (09:30 AM)
*   **Hành động của User:** Nhấp chọn Node `HYPE-005` và nhấn nút **`[🚀 Open Project in VS Code]`**.
*   **Hệ thống xử lý:** 
    - `WorkspaceAdapter` tự động sinh file `Dockerfile` và `devcontainer.json` giới hạn cứng phần cứng vật lý (6 Cores CPU, 16GB RAM) để bảo vệ máy Host.
    - Kích hoạt Deep Link `vscode://` mở app VS Code Native kết nối vào container.
*   **Trạng thái hệ thống (State):** User hoàn thiện file code huấn luyện `train_medical.py`. Hệ thống tự động chụp lại trạng thái mã nguồn và ghim mã commit **`git_sha: #a3f2b1`** vào metadata dự án.

### 🚀 GIAI ĐOẠN 3: ĐIỀU PHỐI VRAM VÀ CHẠY THỰC NGHIỆM ĐÓNG KÍN (10:15 AM)
*   **Hành động của User:** Quay lại UI của PhD-Lab và nhấn nút **`[🔥 Run Experiment via Sandbox]`**.
*   **Hệ thống xử lý:** 
    - Kích hoạt thuật toán **JIT VRAM Unload** giải phóng mô hình Ollama ra khỏi card RTX 3060 (Đưa VRAM về trạng thái an toàn < 1GB).
    - Khởi chạy Docker Sandbox chiếm dụng 100% tài nguyên GPU vật lý để train mô hình.
    - Thực thi cơ chế tự vá lỗi của **Kịch bản 2** nếu phát hiện lỗi tại luồng `stderr`.
*   **Trạng thái hệ thống (State):** Thực nghiệm kết thúc. Một tệp đồ thị kết quả `loss_curve.png` được sinh ra trong thư mục outputs.

### 📝 GIAI ĐOẠN 4: HYBRID WRITING VÀ GIÁM SÁT KÉP (11:00 AM)
*   **Hành động của User:** Chuyển sang **Tool 3 (Paper Writer)**, chọn viết chương *Methodology* dựa trên kết quả của `HYPE-005`.
*   **Hệ thống xử lý:** 
    - Định tuyến yêu cầu sinh văn bản lên **Cloud Claude API** để giải phóng áp lực VRAM cho GPU vật lý.
    - Kích hoạt **Local Critic Engine** (Chạy bằng CPU/RAM) thực thi nghiệp vụ của **Kịch bản 4** để soi lỗi cú pháp LaTeX và đối chiếu tệp `references.bib` cục bộ.
*   **Trạng thái hệ thống (State):** Bản thảo được chỉnh sửa trực tiếp, đồng bộ hóa và lưu trữ vào Context Memory Tier 2.

### 🛡️ GIAI ĐOẠN 5: NIÊM PHONG MINH CHỨNG VÀ XUẤT BẢN THÀNH PHẨM (12:00 PM)
*   **Hành động của User:** Nhấn nút **`[🔒 Finalize & Export Paper]`**.
*   **Hệ thống xử lý:**
    - Kích hoạt nghiệp vụ của **Kịch bản 3**: Nhúng (Inject) thông tin `run_id`, `git_sha`, và `clearml_task_id` vào siêu dữ liệu ẩn của ảnh `loss_curve.png`.
    - Đóng gói toàn bộ cấu trúc mã nguồn, tài liệu, file bib thành file **`latex.zip`** chuẩn tương thích Overleaf.
    - Thiết lập đường dẫn liên kết sâu trỏ thẳng sang giao diện Web UI cục bộ của **ClearML Server (`localhost:8080`)** để lưu trữ logs phần cứng thô vĩnh viễn.
*   **Trạng thái cuối cùng (Final Target State):** Bản ghi tri thức tối cao được khóa lại trong Context Memory: *"Giả thuyết HYPE-005 thành công với Accuracy đạt 94.2%. Minh chứng số liệu đã được niêm phong an toàn tại cấu trúc ảnh. Chiến dịch nghiên cứu hoàn tất."*
