# Báo cáo audit và kiểm chứng PhD-Research-Lab — 24/10/2026

CLI/tool follow-up: user-reported connectivity failures were reproduced with real vendor binaries. See [the repair report](cli-connectivity-report.md); the earlier local-model results do not qualify CLI connectivity or OpenScience/OpenCode native inference.

**Kết luận: NO-GO cho yêu cầu production thương mại với 100% coverage toàn dự án.** Bốn lựa chọn L1–L4 đã được triển khai và chạy thật với LM Studio `qwen/qwen3.5-9b`. Các kiểm thử đã chạy chứng minh được một phạm vi kỹ thuật cụ thể; chúng chưa chứng minh mọi tính năng, mọi nhánh của dự án hoặc khả năng tự chủ khoa học L3/L4.

Số liệu cuối cùng và danh sách test nằm trong [audit-summary.json](../../artifacts/autonomy-qa/audit-summary.json). [Chiến lược kiểm thử](autonomy-test-strategy.md), [ma trận yêu cầu](autonomy-workflow-matrix.csv), [nhật ký phát triển](../architecture/autonomy-workflows.md) và log thô cho phép kiểm tra lại kết luận. Không có commit/push/deploy nào được thực hiện trong công việc này. HEAD chuyển từ `9003be4` sang `0914d53` do một thay đổi bên ngoài thêm `AUTORESEARCHAI.pdf`; file đó được giữ nguyên. Các thay đổi hiện tại chưa commit và có fingerprint source riêng.

## Cách sử dụng và phạm vi đã phát triển

Chọn Topic, mở **Missions → Workflows L1–L4**, chọn nguồn, mục tiêu và model local. Tạo draft, đọc **Plan and results**, nhập ghi chú rồi duyệt chính xác kế hoạch. Có thể tạo nhiều workflow; scheduler phục vụ tối đa bốn workflow độc lập, mỗi workflow một task tại một thời điểm. CPU/local LLM vẫn tuân thủ slot hiện có, vì vậy bốn workflow không đồng nghĩa bốn lượt suy luận GPU cùng lúc.

| Lựa chọn | Cách tương tác | Điểm dừng |
|---|---|---|
| L1 | AI hỗ trợ kiểm tra/tổng hợp nguồn trong phạm vi hẹp | Người dùng chấp nhận hoặc từ chối từng câu trả lời |
| L2 | AI thực thi các capability trong kế hoạch đã duyệt | Người dùng xác nhận từng kết quả trước bước tiếp theo |
| L3 thử nghiệm | Tự điều phối DAG đã duyệt, người dùng xử lý ngoại lệ | Chờ human review cuối |
| L4 thử nghiệm | Tự đóng workflow kỹ thuật trong capability giới hạn | Chỉ đóng sau kiểm tra artifact; thí nghiệm cần tái lập độc lập; review khoa học vẫn pending |

Một workflow tổng hợp nguồn không có thí nghiệm được ghi rõ là không có thí nghiệm. L4 có thí nghiệm cần hai snapshot protocol cùng digest được duyệt riêng, với nonce riêng; không tự duyệt protocol. Lỗi/timeout không tự phát lại tác vụ chưa chắc chắn về hiệu ứng. CLI có thể dùng cùng API và cùng digest qua `phdlab api`; xem [CLI.md](../CLI.md).

Theo [bài báo tham khảo](https://arxiv.org/html/2605.23204v1), L4 là mục tiêu phân tích chưa đạt, và một pipeline dài vẫn có thể chỉ thuộc L2 nếu còn cần con người xác minh khoa học thường xuyên. Vì vậy tên các option ở đây biểu thị **policy thực thi**, không phải chứng nhận năng lực khoa học. Novelty, validity và impact chưa được kiểm chứng bằng nghiên cứu thực tế.

## Kết quả thực đo

| Hạng mục | Kết quả | Bằng chứng |
|---|---|---|
| Backend regression đầy đủ, gồm các thư mục test con | 739 test: 732 pass, 7 skip, 0 failure/error; bổ sung một positive case L4 pass trên cùng source production | [full report](../../artifacts/autonomy-qa/final-backend/report.json), [bổ sung](../../artifacts/autonomy-qa/supplemental/report.json) |
| Frontend React | 161 test pass; typecheck và production build pass | [kết quả từng test](../../artifacts/autonomy-qa/frontend-results.json) |
| Policy/scheduler mới | 100% line và branch trong module autonomy và workflow_worker | [Coverage full + bổ sung, cùng source](../../artifacts/autonomy-qa/release-combined-coverage.json) |
| UI/plan builder mới | 100% line, branch, statement và function cho AutonomyPanel và autonomyPlan | [coverage frontend](../../artifacts/autonomy-qa/frontend-coverage-summary.json) |
| Live bốn workflow × ba vòng | 12 workflow hoàn tất và thêm một hành trình UI; **26 request inference thật**; có CPU subprocess và tái lập độc lập; response model được kiểm tra là Qwen đã chọn | [report](../../artifacts/autonomy-qa/final-live/report.json), raw ZIP và snapshots cùng thư mục |
| Real browser | UI tạo draft → duyệt → review hai bước → completed; desktop 1440px và mobile 375px; không lỗi request/runtime | [browser report](../../artifacts/autonomy-qa/final-live/browser-report.json), screenshots cùng thư mục |
| Legacy live integration | Lần đầu: 71 test, 2 failure, 1 error, 1 skip. Ba test lỗi pass khi chạy riêng. Lần chạy lại đầy đủ: 70 pass, 1 skip | [lần đầu](../../artifacts/autonomy-qa/legacy-live/report.json), [chạy riêng](../../artifacts/autonomy-qa/legacy-diagnosis/report.json), [chạy lại đầy đủ](../../artifacts/autonomy-qa/legacy-live-repeat/report.json) |
| Harness nghiên cứu cũ | v6.0: 4 workflow; v6.2: 12; v6.3: 8. Kiểm tra lại export v6.3 đạt: 20 trial, 480 raw sample, 151 audit event, 10 handoff/receipt | [v6.0](../../artifacts/autonomy-qa/research-v60/harness.json), [v6.2](../../artifacts/autonomy-qa/research-v62/harness.json), [v6.3](../../artifacts/autonomy-qa/research-v63/harness.json) |
| Stress | 16 worker × 3 vòng, 15 phase pass; 1.440 HTTP request, 2.400 SSE delivery, 9.600 gateway event, 960 concurrent state write, 48 subprocess; không HTTP error hoặc process leak | [stress.json](../../artifacts/autonomy-qa/stress.json) |
| Dependency audit | pip-audit và npm audit không ghi nhận advisory sau khi vá | [scan summary](../../artifacts/autonomy-qa/static/summary.json) |

Stress là tải I/O có provider giả lập và số vòng hữu hạn; inference Qwen thật được kiểm tra riêng. Nó chưa phải bằng chứng cho soak nhiều ngày hoặc chất lượng nghiên cứu thực tế. Quyết định human trong harness là input thử nghiệm mô phỏng, không phải phản biện khoa học của người dùng. Reviewer dùng chung model không tạo ra ground truth độc lập.

## Lỗi đã sửa và quan sát còn mở

- Qwen 3.5 có thể tiêu hết token vào reasoning và trả content rỗng. Đã tái hiện thật, thêm test lỗi trước khi sửa, dùng hard thinking switch và từ chối câu trả lời rỗng. L4 cũng từ chối kết quả bị truncation.
- Worker cũ chặn các Mission độc lập khi chờ một lượt inference. Scheduler mới có giới hạn bốn workflow, giữ project scope và không lặp admission; CPU bận được chờ trước admission.
- L4 closure từng mở transaction lồng nhau gây khóa SQLite trong lần phát triển đầu. Đã sửa bằng kiểm tra snapshot đang có; các lượt fail được giữ trong `live-initial` và `live`.
- Backend/live quality gate cũ có điều kiện luôn PASS và các khẳng định compliance/fault không được suy ra từ từng bằng chứng. Đã thay bằng báo cáo theo test và giữ các gate thiếu bằng chứng ở BLOCKED/FAIL.
- Sửa source manifest của harness cũ còn tham chiếu `frontend/index.html` sau migration React.
- Kiểm tra screenshot phát hiện panel mobile bị che dù document không overflow. Đã sửa panel toàn màn hình và bổ sung oracle hình học; bỏ tải Google Fonts bắt buộc để UI hoạt động offline bằng font hệ thống.
- Vá dependency có advisory ở pypdf/certifi; thêm parser defusedxml và regression cho entity trong XML arXiv. SQLAlchemy được cài lại Python thuần cùng phiên bản để chạy được trên Windows hiện tại.
- Form Mission cũ gửi ngân sách 4 lượt suy luận dù API chỉ cho tối đa 3. Regression mới tái hiện sai lệch trước khi sửa; form nay gửi 3. Preflight launcher đã kiểm tra dependency/module mới; `start.py --check` và 10 test entrypoint đều pass.
- **Còn mở:** nguyên nhân ba lỗi gián đoạn ở lượt legacy live đầu chưa được xác định. Việc chạy lại pass không xóa lịch sử lỗi hoặc chứng minh ổn định tuyệt đối.

## Vì sao chưa được công nhận đạt 100%

Coverage backend là **90,36% line** (22.091/24.447), **81,69% branch** (6.715/8.220); vẫn thiếu 2.356 dòng và 1.505 nhánh. Frontend là **65,36% line**, **66,32% branch**, **52,69% function**, với startup, settings, 3D và các công cụ khác còn khoảng trống. Phần mới đạt 100% không đồng nghĩa toàn dự án đạt 100%. Đã bỏ omission ClearML worker và đưa toàn bộ production TS/TSX vào inventory; không loại code khó test để tăng phần trăm. Frontend coverage đo TS/TSX; CSS được kiểm tra bằng ảnh và hình học, chưa có chứng nhận mọi biến thể giao diện. Các entrypoint subprocess và phần bị exclude chuẩn vẫn được liệt kê trong coverage report.

Các test skip gồm quyền tạo symlink Windows, ClearML online, live Codex, SDK OpenScience tùy chọn và model lifecycle cần opt-in riêng. Matrix CI Windows/Linux được cấu hình nhưng chưa có bằng chứng chạy Linux trong phiên này. [Inventory OpenAPI](../../artifacts/autonomy-qa/api-journey-inventory.csv) liệt kê **296 operation**, không tự đánh dấu chúng đều đạt chỉ vì một suite pass. [Khoảng trống coverage](../../artifacts/autonomy-qa/coverage-gaps.json) cho biết module cần bổ sung kiểm thử.

Ruff còn nợ lint; Bandit còn finding cần phân tích theo ngữ cảnh. Các SHA1 bị đánh mức high đang dùng cho ID/cache/hash embedding, không phải digest phê duyệt hay checksum bằng chứng; các digest bảo vệ bằng chứng dùng SHA256. Các finding `/tmp` liên quan container, và SQL động trong retrieval chỉ ghép placeholder, giá trị được bind. Đây là triage theo source, chưa phải đánh giá ASVS độc lập hoàn chỉnh. Không tuyên bố ISO/ASVS certification hoặc production-ready tuyệt đối.

**Điều kiện để đổi quyết định release:** xử lý/giải thích được flake live; hoàn thành các hành trình/API/CLI/external integration bắt buộc; thực thi platform/hardware/manual gates; đạt 100% line/branch/function coverage theo phạm vi đã thống nhất; và có đánh giá khoa học độc lập nếu muốn dùng nhãn L3/L4 theo nghĩa của bài báo. Chỉ số coverage không thay thế các điều kiện còn lại.
