# Rà soát workflow frontend — 2026-10-22

Ứng dụng tiếp tục ở `6.3.0-preview.1`. Đợt này sửa trải nghiệm sử dụng và kết nối nguồn model; không nâng mức nghiệm thu khoa học của harness 6.x.

## Thay đổi đã thực hiện

| Workflow | Vấn đề / quyết định | Kết quả và kiểm chứng |
|---|---|---|
| Gán model cho Research, Reviewer, Utility | Model các hãng bị trộn; đổi nguồn vẫn giữ model cũ | Danh sách theo từng nguồn. Đổi nguồn xóa override cũ trong một lần lưu. Kiểm tra cả API, local, MCP và lỗi lưu |
| Cloud mặc định / Claude ưu tiên | Alias có thể đổi hãng khi đổi cloud hoặc thêm key | Theo dõi hãng thực tế; chỉ bỏ model khi hãng thực tế thay đổi. Giữ model Anthropic khi đổi cloud khác |
| LM Studio / Ollama | Agent cần chọn được model đang có trên máy | Probe danh sách local cập nhật các dropdown agent. Model riêng vẫn nhập được qua Custom model |
| Tài nguyên và chi phí | Local có thể chuyển sang cloud theo cấu hình nhưng thiếu nút điều khiển | Thêm tùy chọn tắt fallback cloud ngay trong Models & agents; Auto vẫn dùng routing/capability policy hiện có |
| API / gateway riêng | URL tùy chỉnh khó tiếp cận; refresh mất Custom model; lỗi lưu làm mất key đang nhập | URL riêng trong hàng provider, refresh giữ lựa chọn và Custom model, lưu thất bại giữ key để thử lại |
| Agent MCP | MCP tool server thông thường không tự cung cấp model | Adapter tool suy luận được cấu hình rõ: endpoint, token, tên tool, catalog model; kiểm tra schema trước khi gọi. Xem [hợp đồng](MODEL_RESOURCES.md) |
| OpenScience / Feynman | Lối vào sâu; Feynman chỉ trả lệnh sao chép | Mục riêng trên thanh bên. Windows mở terminal tương tác riêng; OpenScience dùng native `web`, Feynman dùng REPL. Có nút mở cùng workspace trong cửa sổ VS Code mới |
| Đồng bộ engine | Cần giữ rõ thao tác mở engine và nhập kết quả | Nút Sync Now / View changes / Relink giữ nguyên scope Topic và lịch sử artifact. Mở engine không gửi research prompt |
| Màn hình nhỏ | Bảng cấu hình gây cuộn ngang, select dài khó thao tác | Agent chuyển thành thẻ dọc có nhãn nguồn/model; bảng API cuộn trong vùng riêng; đường dẫn và lệnh dài tự xuống dòng |
| Bàn phím / hộp thoại | Focus thoát ra nền; thay modal có thể giữ listener cũ | Tab/Shift Tab giới hạn trong dialog, Escape đóng, ưu tiên ô nhập và trả focus về nút mở; modal thay thế không bị callback cũ đóng nhầm |
| Thao tác nghiên cứu | Có thể bấm lặp khi request chưa xong | Vô hiệu hóa nút đang xử lý và bật lại sau kết quả/lỗi |
| Ngôn ngữ | Alias từ điển ghi đè Library thành Paper; mô tả agent / VRAM / fallback còn tiếng Việt trong UI Anh | Giữ bản dịch chuẩn có sẵn, bổ sung bản dịch và nhãn mới. Không dịch nội dung nghiên cứu của người dùng |
| Dự án / hội thoại / ghim / ngày | Bảo toàn workflow hiện có | Regression JS và Edge: nhóm chat theo dự án, pin/unpin, lịch, đổi dự án, composer và giao diện mobile |
| Library / SKB / nguồn / bằng chứng | Bảo toàn upload, đặt tên PDF và tuyển chọn tài liệu | Regression backend/JS; Edge kiểm tra panel, bộ lọc, tags, citations, archive/restore và bố cục mobile. Không gọi nguồn học thuật thật trong QA |
| Viết bài / xuất / ghi chú / phản biện | Bảo toàn thao tác đi qua chat và duyệt kết quả | Bộ regression frontend kiểm tra viết/compile, export, ghi chú, review, đề xuất và lỗi; Edge kiểm tra panel viết bài và VS Code |
| Mission / team / workstream / thí nghiệm | Giữ các bước duyệt và preview gate | Bộ regression backend và frontend hiện có; không tự bật các cờ Research OS hoặc chạy tác vụ model thật |

## Cách dùng

1. Khởi động lại PhD Lab để nạp backend mới, rồi tải lại trang.
2. **Cài đặt → Mô hình & agent**: chọn nguồn trước, sau đó chọn model tương ứng. Chọn **Tự động** trong picker của chat để sử dụng cấu hình từng agent này. Provider cố định trong chat sẽ ưu tiên lựa chọn của cuộc hội thoại.
3. Với local, chạy LM Studio/Ollama trước khi mở cài đặt. Catalog từ tài khoản API được tải bằng **↻ Models**; catalog gợi ý không chứng minh quyền truy cập hoặc quota.
4. Với MCP, mở **Cấu hình agent suy luận MCP**, nhập thông tin server và bật adapter, rồi chọn nguồn MCP cho agent. Server cần đúng [hợp đồng suy luận](MODEL_RESOURCES.md).
5. Chọn Topic, mở **OpenScience · Feynman** trên thanh bên, tạo/liên kết workspace. **Open … ↗** mở engine độc lập; **Mở trong VS Code** mở thư mục trong editor riêng; **Sync Now** đưa các file đã lưu vào cầu nối artifact.

## Bằng chứng và giới hạn

Kết quả đo cuối cùng, log, LCOV và ảnh chụp ở [artifacts/workflow-ux](../artifacts/workflow-ux/verification.md). Toàn bộ JavaScript first-party đều được tính coverage; không bỏ script hoặc thêm chỉ thị bỏ qua coverage.

Kiểm tra launch dùng subprocess giả lập để kiểm chứng argv, cwd, chống bấm lặp và cách ly key. Đã probe help CLI thật; không gửi suy luận có phí, mở terminal native tương tác hoặc khẳng định đăng nhập/quota trong QA trình duyệt. Windows mở cửa sổ trên **máy chạy server**, không phải máy khách truy cập từ xa. Ngoài Windows, Feynman tiếp tục trả lệnh terminal để chạy thủ công.

MCP hiện hỗ trợ HTTP JSON/SSE và tool suy luận theo hợp đồng; không hỗ trợ trực tiếp mọi server stdio hoặc server chỉ có tools dữ liệu. Nội dung trả về được nhận sau khi tool hoàn tất. Stop/ngân sách thời gian hủy request phía PhD Lab; việc server MCP thực sự dừng compute cần được xác nhận tại server đó. Adapter không tự fallback sang API trả phí.

Native engines dùng đăng nhập và cấu hình riêng, không tự nhận API key PhD Lab. Quan sát workspace vẫn chỉ bao gồm file đã lưu; không đọc được private reasoning hoặc toàn bộ native session. Các kết quả harness đã lưu trước đây vẫn thuộc đúng source snapshot của chúng, không được đổi nhãn thành nghiệm thu UI mới.
