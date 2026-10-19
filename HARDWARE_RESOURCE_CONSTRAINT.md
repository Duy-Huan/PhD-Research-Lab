# 📊 HARDWARE SPECIFICATION & RESOURCE MANAGEMENT POLICY
> **Cấu hình máy chủ mục tiêu:** i5-14400F | RTX 3060 12GB | 32GB RAM | 2.5TB SSD
> **Mục tiêu:** Ràng buộc tuyệt đối kiến trúc phân bổ tài nguyên để chạy song song huấn luyện AI (Sandbox) và suy luận mô hình ngôn ngữ (Local LLM) mà không gây sập nguồn, tràn VRAM hoặc đóng băng hệ điều hành.

---

## 1. Thông Số Vật Lý & Ngưỡng Giới Hạn Tối Đa (Hard Caps)

Hệ thống backend (`backend/sysinfo.py` và `backend/sandbox.py`) khi khởi chạy hoặc lập lịch tác vụ phải tuân thủ nghiêm ngặt các giới hạn trần sau:

| Tài nguyên phần cứng | Tổng dung lượng vật lý | Giới hạn trần an toàn (Safety Cap) | Phân bổ cho Docker Sandbox | Phân bổ cho Local AI Engine |
| :--- | :--- | :--- | :--- | :--- |
| **GPU VRAM (RTX 3060)**| **12.0 GB** | **11.0 GB** (Chừa 1GB cho hiển thị OS) | 100% (Khi Unload Local AI) | Tối đa **8.0 GB** (Bắt buộc dùng Quantized Q4_K_M) |
| **System RAM** | **32.0 GB** | **20.0 GB** (Chừa 12GB cho hệ thống) | **12.0 GB - 16.0 GB** | Tối đa **12.0 GB** (Nếu chạy LLM trên RAM) |
| **CPU Cores/Threads**  | **10C / 16T** | Giới hạn 85% CPU Load | Tối đa **6 Cores** (`--cpus="6"`) | Tối đa **4 Cores** (Thread threads pooling) |
| **Storage (NVMe SSD)** | **2.5 TB** | Giữ trống tối thiểu 50GB | Không giới hạn | Không giới hạn |

Ngoài ra hãy thêm cơ chế tự động check info hệ thống PC để đưa ra option tự động một cách thông minh, hoặc cho user config khi bắt đầu chạy hệ thống.
---

## 2. 03 Thuật Toán Điều Phối Bộ Nhớ Chiến Lược (Orchestration Algorithms)

Khi AI Agent chuẩn bị thực thi một mã lệnh tính toán trong file `backend/sandbox.py`, hệ thống phải áp dụng chuỗi logic điều phối tuần tự dưới đây:

### 🔄 Chiến lược A: Just-In-Time (JIT) VRAM Unload (Giải phóng bộ nhớ tức thời)
Áp dụng khi người dùng hoặc Agent kích hoạt lệnh chạy tác vụ huấn luyện nặng sử dụng GPU trong Docker Sandbox.
1. **Kiểm tra trạng thái:** Hệ thống quét xem Ollama hoặc LM Studio có đang chiếm dụng VRAM không.
2. **Kích hoạt lệnh Unload:** Gọi API ngầm để đẩy mô hình ra khỏi VRAM ngay lập tức:
   - *Đối với Ollama:* Gửi POST Request đến `/api/generate` với tham số `{"model": "tên_model", "keep_alive": 0}`.
   - *Đối với LM Studio:* Gọi lệnh CLI `lms unload --all` hoặc REST API tương đương.
3. **Thực thi:** Chờ 1.5 giây để VRAM hạ nhiệt về mức trống (< 2GB), sau đó mới kích hoạt lệnh `docker exec --gpus all` chạy Script thực nghiệm.

### 🔀 Chiến lược B: Hybrid Cloud Fallback (Định tuyến thông minh lên mây)
Áp dụng để duy trì sự hoạt động liên tục của Agent (Gõ bài báo, phản biện, fix lỗi code) ngay trong lúc GPU đang bận Train AI.
* **Luồng xử lý:** 
  ```text
  [Yêu cầu từ AI Agent] ──> Kiểm tra GPU Status (sysinfo.py)
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼ (GPU Nhàn rỗi < 30%)                  ▼ (GPU Đang bận Train / > 80%)
        [Chạy Local LLM bằng GPU]                [Cưỡng bức định tuyến lên Cloud API]
        (VRAM tiêu tốn: 7-8GB)                   (Tiêu tốn VRAM vật lý: 0 MB)
  ```

### 💻 Chiến lược C: CPU Offloading (Chạy mô hình nền bằng RAM)
Áp dụng trong trường hợp người dùng tắt mạng hoàn toàn (Offline mode) nhưng vẫn muốn Agent vừa soát lỗi bài viết, vừa chạy Train AI.
* **Cấu hình cưỡng bức:** Chuyển cấu hình của Ollama/LM Studio sang chế độ `GPU Layers = 0`. Mô hình 7B/14B sẽ được nạp trực tiếp vào **System RAM (DDR5)** và xử lý bằng các nhân của **i5-14400F**.
* Do máy có tới 32GB RAM, việc trích xuất 8GB cho LLM và 12GB cho Docker Sandbox vẫn nằm trong vùng an toàn tuyệt đối (Tổng = 20GB < Ngưỡng trần 28GB).

---

## 3. Chỉ Thị Cho Claude Khi Lập Trình Mã Nguồn (Execution Instructions)

1. **Bắt buộc đọc file này trước khi can thiệp vào File chạy:** Khi chỉnh sửa `backend/sandbox.py`, `backend/sysinfo.py` hoặc tạo mới bất kỳ Adapter nào liên quan đến tính toán, phải khai báo với người dùng: *"Tôi đã đọc file HARDWARE_RESOURCE_CONSTRAINT.md và đảm bảo hàm này tuân thủ định mức VRAM/RAM..."*
2. **Kiểm tra lỗi rò rỉ bộ nhớ (Memory Leak Protection):** Mọi tác vụ chạy ngầm của Agent (ví dụ: Local Critic Agent chạy async) phải có cơ chế ngắt thời gian chờ (`asyncio.timeout`) và dọn dẹp các biến con trỏ lớn sau khi kết thúc lượt chạy.
3. **Đặt bọc Lỗi (Graceful Degradation):** Khi Docker Container bị crash do lỗi phần cứng (ví dụ: mất kết nối GPU do driver quá nhiệt), hệ thống phải tự động bắt lỗi `ContainerError`, ghi nhận logs chi tiết vào `data/runs/<id>/stderr.log` và chuyển trạng thái Sandbox về chế độ chạy thuần CPU để cứu vãn tiến trình nghiên cứu mà không làm treo UI app.
