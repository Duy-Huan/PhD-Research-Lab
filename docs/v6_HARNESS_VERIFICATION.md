# Kiểm chứng harness từ v6.0 tới v6.3

Lệnh kiểm chứng tổng hợp:

```powershell
.venv/Scripts/python -B tools/verify_v6_harness.py --historical
```

Lệnh chạy test hợp đồng trước, sau đó chạy từng stage trong process/dữ liệu riêng và kiểm lại bằng chứng xuất ra bằng bộ verifier độc lập. Không đổi branch/checkout hiện tại, không đọc hoặc sửa project nghiên cứu thật. Bằng chứng ở [bảng kết quả](../artifacts/harness-verification/verification.md), [summary có từng test](../artifacts/harness-verification/summary.json) và thư mục `current/`, `historical/` bên cạnh.

## Hai cấp kiểm chứng

| Phạm vi | Mục đích | Mốc |
|---|---|---|
| Stage trên mã hiện tại | Xác minh hành vi của từng mốc vẫn hoạt động sau các nâng cấp | 6.0, 6.2, 6.3; application version vẫn là 6.3.0-preview.1 |
| Mã tại commit phát hành gốc | Xuất chính xác mã Git vào thư mục tạm rồi chạy harness gốc | 6.0: `312e9b0`; 6.2: `40e1173`; 6.3: `459fc13` |

Các commit lịch sử chạy với Python/dependency **đang cài trên máy này**; không tái tạo toàn bộ môi trường dependency lịch sử. Không sửa mã cũ để làm test đạt. Các chênh lệch định dạng bằng chứng được ghi rõ trong summary.

Không có đặc tả/release commit/stage riêng cho **v6.1** trong repo. Phần này là lớp tương thích role, ownership, task envelope và verifier trên Mission worker, được kiểm tra bằng `test_teams`. Không tạo số liệu benchmark hay một nhãn release v6.1 giả.

## Nội dung kiểm tra

- **6.0:** charter/lifecycle, đúng plan digest và quyền, lịch/deadline, ngân sách tổng, pause/review, không fallback API trả phí, cooldown khi quota lỗi, cách ly Topic, citation không có bằng chứng giữ `unverifiable`.
- **6.1/6.2:** team tối thiểu, single/fixed/adaptive, owner/verifier khác nhau, quyền không vượt Mission, DAG/handoff, giới hạn replan và trừ budget đã dùng, provider thiếu thì pause, kết quả tự nhận cải thiện vẫn chưa verified.
- **6.3:** partition hữu ích và single-team fallback, work order/receipt đúng scope và digest, lỗi engine không giả hoàn tất team khác, quota/storage preflight, canonical output phát hiện xung đột, dispute chặn review và human resolution không tự duyệt claim.
- **Tái lập:** chạy CPU fixture hai lần cho từng chế độ. Verifier đọc raw arrays trong ZIP, tính lại MSE, PSNR, trung bình theo seed, gain/CI và held-out metrics; kiểm tra cùng dữ liệu baseline/variant, không dùng test để chọn candidate, các lần chạy độc lập có cùng raw measurement hashes.
- **Provenance:** checksum/size của artifact, request và log tồn tại, code worker đúng SHA, audit chain gốc liên tục. Các stage hiện tại xuất cả raw control-plane snapshots để rehash role envelope, work order, source result và receipt sau khi thư mục tạm đã bị dọn.
- **Adversarial:** sửa artifact nhưng ZIP CRC vẫn hợp lệ; sửa metric rồi cập nhật checksum; dựng gain/held-out metric 999; đổi receipt receiver/audit payload; thiếu workflow, trùng Mission, task thất bại hoặc source digest sai đều phải bị từ chối. Verifier dùng điều kiện lỗi rõ ràng, vẫn chạy kiểm tra dưới `python -O`.

Test restart bổ sung tạo **hai process Python khác nhau**: process đầu dừng bằng `os._exit(23)` sau khi admission đã commit và một marker đã ghi; process sau dùng cùng DB, gọi recovery và tiếp tục checkpoint an toàn. Kiểm tra admission chưa rõ kết quả vẫn `interrupted`, marker chỉ có một lần, task đã commit không chạy lại, handoff đã publish được ack đúng một lần. PID, exit code và counters đo được được lưu trong case tương ứng ở `summary.json`. Đây là kiểm thử abrupt application exit trên SQLite, không mô phỏng mất điện hoặc lỗi phần cứng storage.

## Phát hiện và khắc phục trong harness

Harness trước đây chỉ ghi application version nên dễ nhầm stage 6.0 trên code mới với release 6.0 gốc. Bản hiện tại ghi thêm `stage`, schema và feature flags. ZIP giữ raw control-plane, role handoff và collaboration snapshots để verifier có thể kiểm lại digest ngoài runtime. Tool tổng hợp đặt trạng thái `running`, `passed=false` ngay khi bắt đầu, tránh dùng lại summary thành công của lần chạy trước nếu lần mới thất bại.

Các bundle **gốc** của 6.0/6.2 không có embedded source manifest hoặc Mission report files trong ZIP; có thể xác nhận mã qua Git export, raw CPU measurements và audit, nhưng không thể kiểm độc lập file report đã bị dọn. Bundle gốc 6.3 có source manifest/artifact nhưng thiếu raw handoff snapshots. Kết quả lịch sử vì vậy được ghi **PASS with export limits**, không đánh đồng với mức bằng chứng hiện tại. Những thiếu sót này đã được bổ sung trong harness hiện tại mà không sửa lịch sử Git.

## Chạy từng phần

```powershell
# Chỉ ba stage hiện tại cùng các test hợp đồng
.venv/Scripts/python -B tools/verify_v6_harness.py

# Kiểm lại bundle đã lưu, không chạy thí nghiệm
.venv/Scripts/python -B tools/verify_v6_harness.py --verify-only artifacts/harness-verification/current/v63 --stage 6.3

# Test riêng các trường hợp giả mạo và restart thực
.venv/Scripts/python -B tools/run_tests.py test_harness_verification

# Entry point từng stage cũ vẫn dùng được
.venv/Scripts/python -B tools/research_harness.py --stage 6.0 --output artifacts/manual-v60
.venv/Scripts/python -B tools/research_harness.py --stage 6.2 --output artifacts/manual-v62
.venv/Scripts/python -B tools/research_harness.py --stage 6.3 --output artifacts/manual-v63
```

Các test/harness ở đây chạy tuần tự trên CPU và dùng literature/workspace fixture. Kết quả không chứng minh hiệu quả nghiên cứu khoa học, model productivity, quota/billing live, khả năng Docker containment, tải GPU thật hoặc phục hồi private native sessions. Những cổng nghiệm thu đó vẫn mở; Research OS/teams/workstreams tiếp tục opt-in preview. Xem [handoff](v6_UPGRADE_HANDOFF.md) và [phạm vi hệ thống](upgrade-reconciliation.md).
