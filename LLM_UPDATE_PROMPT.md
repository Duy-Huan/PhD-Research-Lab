# 🌐 LLM GATEWAY UPGRADE & MULTI-PROVIDER ROUTING SPECIFICATION
> **Vai trò:** Senior Cloud Infrastructure & Network Security Engineer.
> **Mục tiêu:** Chỉ thị tối cao hướng dẫn Claude/AI Agent tái cấu trúc và mở rộng toàn bộ module `backend/llm/` nhằm tích hợp 9Router, OmniRoute, OpenRouter, DeepInfra, Groq. Bắt buộc tuân thủ rào dán bảo mật và định tuyến chi phí tối ưu (Hybrid Cost-Efficiency Layer).

---

## 1. MA TRẬN KẾT NỐI NHÀ CUNG CẤP (PROVIDER INTEGRATION MATRIX)

Bộ điều phối `LLMRouter` bắt buộc phải bao bọc (wrap) cấu trúc API chuẩn OpenAI cho tất cả các nhà cung cấp sau thông qua một Interface trừu tượng duy nhất (`BaseLLMProvider`):

| Nhà cung cấp API | Base URL Endpoint | Phương thức xác thực (Auth) | Mục tiêu tác vụ trong Hệ thống |
| :--- | :--- | :--- | :--- |
| **9Router (Local Gateway)** | `http://localhost:20128/v1` | `NINE_ROUTER_API_KEY` (Plaintext) | Các tác vụ Agent chạy tự động (Free Models: Kiro, Vertex) |
| **OmniRoute (Proxy)** | `http://localhost:20130/v1` | `OMNI_ROUTE_TOKEN` | Load-balance các tài khoản phụ và hạn ngạch Free-tier |
| **OpenRouter** | `https://openrouter.ai` | `OPEN_ROUTER_API_KEY` | Gọi DeepSeek V4 Pro, Qwen-Coder siêu rẻ khi mô hình Local quá tải |
| **DeepInfra** | `https://deepinfra.com`| `DEEPINFRA_TOKEN` | Gọi các dòng mô hình mã nguồn mở Llama-3.3-70B/Qwen với chi phí tiệm cận 0 |
| **Groq API** | `https://groq.com` | `GROQ_API_KEY` | Tác vụ Live Critic (Cần tốc độ sinh chữ cực cao >200 tokens/s) |
| **Ollama (Cục bộ)** | `http://localhost:11434/v1` | Không yêu cầu | Chạy Qwen Local 7B-9B mặc định khi chạy ngoại tuyến (Offline) |

---

## 2. RÀO DÁN BẢO MẬT & QUẢN LÝ KHÓA (SECURITY & PLAIN_TEXT PROTECTION)

> ⚠️ **CẢNH BÁO KIỂM TOÁN 2026:** Do 9Router/OmniRoute phiên bản cục bộ lưu trữ khóa (API Keys) và Tokens dưới dạng văn bản thô (Plaintext) trong file cấu hình SQLite/JSON nội bộ và thỉnh thoảng tắt xác thực TLS nhằm tối ưu tốc độ proxy, hệ thống phải tuân thủ nghiêm ngặt quy tắc bảo mật sau:

1. **Cô lập Khóa Tuyệt đối (Key Isolation):** 
   - Nghiêm cấm hành vi ghi đè hoặc đẩy các API Key tài khoản chính chứa thẻ tín dụng thật (như khóa OpenAI/Anthropic chính) vào Dashboard của 9Router/OmniRoute.
   - Các API Key chính của Cloud bắt buộc phải được băm (hash) hoặc lưu trữ độc lập trong file môi trường `.env` của hệ thống Host (`data/config.json`), bọc qua lớp `SecureConfigManager` của app PhD-Lab.
2. **Sanitization Headers:** 
   - Khi chuyển hướng (forward) request từ PhD-Lab sang 9Router/OmniRoute, hệ thống phải tự động lọc bỏ (strip) toàn bộ các header nhạy cảm liên quan đến danh tính thực tế của người dùng, ngoại trừ token định danh cục bộ của cổng proxy đó.

---

## 3. THUẬT TOÁN ĐỊNH TUYẾT & BẢO VỆ PHẦN CỨNG (ROUTING & HARDWARE LAWS)

Mã nguồn tại `backend/llm/router.py` phải thực thi đúng logic cây quyết định (Decision Tree) sau cho mỗi lượt gọi truy vấn từ các Tool:

```text
[Yêu cầu từ Agent Tool] ──> Kiểm tra Trạng thái Mạng (Internet Online?)
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼ (ONLINE)                                        ▼ (OFFLINE)
Kiểm tra Loại Tác vụ (Task Kind)                      [Cưỡng bức chạy Qwen Local]
     │                                                (Load vào RTX 3060 VRAM)
     ├─► Live Critic (Cần Tốc độ) ──► Chạy Groq API (Llama-3-8b via LPU)
     ├─► Thống kê SOTA (Context)  ──► Chạy 9Router / OmniRoute (Gemini Flash Free Cache)
     └─► Vá lỗi Code (Cấu trúc)   ──► Chạy OpenRouter / DeepInfra (DeepSeek V4)
```

### Quy tắc Inject Header Tối ưu hóa Token (9Router/OmniRoute Specifics)
Khi định tuyến qua 9Router hoặc OmniRoute, hệ thống bắt buộc phải chèn thêm các tùy biến header đặc quyền nhằm tối ưu hóa bộ nhớ:
- `X-9Router-Skills: rtk`: Kích hoạt bộ lọc rút gọn khoảng trắng và nén logs thô (Tiết kiệm 30% Input Token).
- `X-9Router-Skills: caveman`: Ép mô hình phản hồi vắn tắt, loại bỏ các câu chào hỏi thừa thãi (Tiết kiệm 50% Output Token cho tác vụ hệ thống).

---

## 4. QUY TRÌNH RA LỆNH CHO CLAUDE (EXECUTION WORKFLOW)

Khi người dùng ra lệnh: `"Claude hãy thực hiện cập nhật API Router dựa trên file LLM_UPDATE_PROMPT.md"`, bạn phải:
1. **Phân tích File Hiện tại:** Đọc cấu trúc file `backend/llm.py` hiện tại, lập bảng Markdown đối chiếu các hàm kết nối cũ.
2. **Thiết kế Lớp Hợp nhất (Adapter Pattern):** Viết mã nguồn Python triển khai cấu trúc `SmartMultiRouter` bọc toàn bộ 6 nhà cung cấp trên, bọc chặt các khối lệnh `try-except` và cơ chế Fallback tuần tự nếu Endpoint Free bị sập hoặc hết Quota.
3. **Chỉ dẫn Tích hợp:** Xuất mã nguồn sạch, chỉ rõ file path và cách đăng ký biến môi trường an toàn trong `data/config.json`.
