# 🧠 RESEARCH CONTEXT MEMORY ARCHITECTURE & FULL-FLOW SPECIFICATION
> **Triết lý thiết kế:** Tuyệt đối KHÔNG xây dựng một "chatbot có memory". Hệ thống phải được thiết kế như một **Research Operating System** sở hữu cấu trúc Context Memory phân tầng và chuỗi biên dịch ngữ cảnh đóng kín (Deterministic Context Compilation Pipeline).

---

## 1. SƠ ĐỒ TIẾN TRÌNH TOÀN DIỆN (FULL FLOW ARCHITECTURE)

```text
                 ┌───────────────────┐
                 │ Claude/GPT/Gemini │
                 └─────────┬─────────┘
                           │
                    Context Manager
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
[ Working Memory ]  [ Research Memory ] [ Knowledge Memory ]
 - Current Task      - Experiments       - Papers
 - Agent State       - Results           - Concepts
                     - Failures          - Methods
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                  [ Retrieval Engine ]
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ( Vector )     ( Graph )   ( Keyword )
                           │
                           ▼
                      [ Reranker ]
                           │
                           ▼
                  [ Context Compiler ]
                           │
                           ▼
                 ┌───────────────────┐
                 │ Claude/GPT/Gemini │
                 └───────────────────┘
```

---

## 2. QUY ĐỊNH PHÂN TẦNG LƯU TRỮ (STORAGE SCHEMAS)

Mã nguồn tại `backend/memory/` bắt buộc phải triển khai cấu trúc dữ liệu cô lập thành 3 phân vùng độc lập:

### Tầng 1: Working Memory (Bộ nhớ ngắn hạn)
- **Nhiệm vụ:** Lưu trữ trạng thái sống của phiên làm việc và chuỗi suy luận hiện tại của Agent.
- **Mã nguồn tương ứng:** `backend/memory/working.py`
- **Thành phần:** `current_task`, `agent_runtime_state`.

### Tầng 2: Research Memory (Bộ nhớ thực nghiệm - Tích hợp ClearML)
- **Nhiệm vụ:** Lưu vết tiến trình, kết quả và bài học rút ra từ thực nghiệm.
- **Mã nguồn tương ứng:** `backend/memory/research.py`
- **Thành phần:** `experiments_metadata`, `clearml_task_id`, `metrics_summary`, `validated_failures` (Nhật ký lỗi/Giả thuyết bị bác bỏ).

### Tầng 3: Knowledge Memory (Bộ nhớ tri thức học thuật vĩnh viễn)
- **Nhiệm vụ:** Kho lưu trữ tài liệu, lý thuyết và thư viện phương pháp nền tảng.
- **Mã nguồn tương ứng:** `backend/memory/knowledge.py`
- **Thành phần:** `papers_metadata` (BibTeX/PDF), `scientific_concepts`, `proven_methods` (Mã nguồn thuật toán chuẩn).

---

## 3. ĐẶC TẢ CHUỖI XỬ LÝ NGỮ CẢNH (RETRIEVAL & COMPILATION LAWS)

Khi một Agent gửi truy vấn, Module điều phối bối cảnh bắt buộc phải thực thi tuần tự theo chuỗi thuật toán sau:

### Bước 3.1: Kích hoạt Tri-Search (Tầng Tìm Kiếm Lai)
Hệ thống không được phụ thuộc vào một phương thức tìm kiếm đơn lẻ. Lớp `RetrievalEngine` phải gọi song song:
1. **Vector Index (Dense Retrieval):** Truy vấn độ tương đồng cosine (Cosine similarity) để bắt vết ngữ nghĩa văn bản.
2. **Graph Index (Relational Retrieval):** Truy vết các cạnh kết nối (Edges) giữa các Node giả thuyết, quyết định cấu trúc và kết quả thực nghiệm tương ứng để giữ nguyên tính logic của chuỗi nghiên cứu.
3. **Keyword Index (Sparse Retrieval):** Sử dụng BM25 để bắt chính xác các từ khóa cứng: Tên hàm, mã định danh `task_id` của ClearML, mã `git_sha`.

### Bước 3.2: Tái Sắp Xếp Trọng Số (Reranking)
- Toàn bộ kết quả thô từ bộ ba Tri-Search phải được đẩy qua một lớp Reranker nội bộ (Ưu tiên dùng model Reranker cục bộ siêu nhẹ như `bge-reranker` chạy bằng CPU/RAM).
- Loại bỏ các thông tin nhiễu, sắp xếp lại độ ưu tiên và chỉ giữ lại Top K tài liệu có điểm liên quan cao nhất đối với mục tiêu nghiên cứu hiện tại của tác vụ.

### Bước 3.3: Biên Dịch Ngữ Cảnh (Context Compilation)
- Mã nguồn tại `backend/memory/compiler.py` chịu trách nhiệm định hình cấu trúc thông tin cuối cùng.
- Cấm quăng dữ liệu thô dạng chuỗi lộn xộn vào prompt. Cấu trúc ngữ cảnh sau khi biên dịch phải được đóng gói chuẩn hóa dưới dạng Markdown cấu trúc:
  ```markdown
  [CONTEXT SYSTEM INJECTION]
  ### CURRENT WORKING STATE
  <Dữ liệu từ Working Memory>
  ### RELATED EXPERIMENT EVIDENCE (ClearML Pointer)
  <Dữ liệu từ Research Memory + ClearML Task ID Link>
  ### FOUNDATIONAL SCIENTIFIC KNOWLEDGE
  <Dữ liệu từ Knowledge Memory>
  ```
- File cấu trúc này sẽ được nhúng trực tiếp vào lượt gọi LLM kế tiếp, đảm bảo mô hình luôn nhận được thông tin có độ tinh khiết tri thức cao nhất.

Ngoài ra thuật toán nén context memory phải được thực hiện để tiết kiệm tài nguyên.
 4. AUTOMATED MEMORY COMPRESSION LAWS (QUY ĐỊNH NÉN BỘ NHỚ)

Mã nguồn tại `backend/memory/compressor.py` bắt buộc phải triển khai bộ ba thuật toán nén tự động nhằm bảo vệ tài nguyên máy Host:
1. **Token Watermark Monitor:** Kích hoạt ngầm (`asyncio`) quét `Working Memory`. Trigger lệnh nén ngay khi đạt ngưỡng High Watermark (16,000 tokens) và trả bộ nhớ ngắn hạn về mức Low Watermark (2,000 tokens) để giải phóng KV Cache cho RTX 3060.
2. **Hierarchical Reduce (Qwen Local):** Ép buộc băm nhỏ log hội thoại thô thành từng chunk 3,500 tokens. Gọi Qwen Local tóm tắt song song theo cấu trúc JSON/Markdown học thuật nghiêm ngặt trước khi dọn sạch (Purge) log cũ.
3. **Graph Entity Wiring:** Biến các bản nén văn bản thành các Node tri thức có liên kết logic trực tiếp với mã `task_id` của ClearML và mã giả thuyết khoa học.

