# Quy trình chuẩn: dev → qa → main

Chính sách chủ repo ngày 25/10/2026 thay thế quy trình feature/fix → dev trước đây. Ba nhánh chính là `dev`, `qa`, `main`. **Mọi AI chỉ sửa mã và commit trên `dev`.** Một AI giữ quyền ghi tại một thời điểm; AI khác chỉ đọc cho đến khi được bàn giao. Không xóa worktree hay thay đổi chưa commit của người dùng.

## Thiết lập một lần trên mỗi clone

```powershell
git status --short
git branch --show-current
# Chỉ tiếp tục trong worktree dev sạch hoặc chứa thay đổi đúng task.
python -m pip install --require-hashes -r requirements-ci.lock
python scripts/install_ci_sdk.py --out output/playwright/ci-sdk
$env:PYTHONPATH = (Resolve-Path output/playwright/ci-sdk).Path
$env:NO_PROXY = 'localhost,127.0.0.1,::1'
python scripts/development_guard.py install
Push-Location frontend
npm ci
npx --no-install playwright install chromium
Pop-Location
```

Dùng Python 3.11/3.12. SDK được tải từ commit chính thức và kiểm tra SHA-256; thư mục output phải mới. Test SDK chạy offline/socket nội bộ, không phải bằng chứng truy vấn AI thật. Hook dùng interpreter đã đăng ký; cập nhật lại `install` nếu môi trường Python đổi.

## Mỗi lần phát triển

1. Đọc `AGENTS.md`, `agent/AGENT.md`, `STATE.md`, `PLAN.md`. Xác nhận branch chính xác là `dev`; tìm skill phù hợp trên GitHub, review/pin vào `skills/`, viết Feature Quality Contract và testcase trước khi sửa.
2. Chạy `quick`/`targeted` khi sửa. Trước push phải chạy toàn bộ software gate:

```powershell
python scripts/verify.py --profile pr --component all --base origin/dev --out output/playwright/<run-moi>
```

3. Tất cả regression bắt buộc phải thực thi và PASS. FAIL/ERROR/SKIP/BLOCKED/NOT_RUN trong bộ software đều chặn. Coverage được báo cáo với phạm vi và mẫu số, **không có ngưỡng phần trăm**. Ba live-provider test được khai báo riêng trong `layers.py` chỉ hoãn ở dev, vẫn ghi NOT_RUN và bắt buộc tại QA/main.
4. Lưu bằng chứng, đồng bộ version, commit đúng thay đổi task trên `dev`, rồi `git push origin dev`. Pre-commit chặn branch khác. Pre-push kiểm tra branch, origin, HEAD hiện tại, working tree sạch và báo cáo đầy đủ khớp hash nguồn. Không dùng `--no-verify`, force push hay chỉnh báo cáo thành PASS. Hook là kiểm soát trên client đã cài, không phải cơ chế GitHub không thể vô hiệu hóa.
5. GitHub chạy Quality Gates trên đúng SHA của dev. Đọc kết quả thật; có lỗi thì phân loại, sửa nguyên nhân trên dev và chạy lại local trước push. Tối đa ba lần gọi AI sửa cho một task/PR, không reset bộ đếm.

## Đưa qua QA và main

- Tạo PR `dev → qa`. CI chạy lại regression phần mềm, đồng thời bắt buộc evidence provider thật, research/CLI/2D/3D và AI-UAT đúng nguồn/SHA. Dịch vụ chưa có hoặc evidence thiếu thì QA BLOCKED. Có thể dùng native auto-merge cho PR QA tin cậy sau khi mọi gate đạt và branch protection còn hiệu lực.
- Chỉ khi QA đủ điều kiện mới tạo PR `qa → main`. Không tự merge main. Không vượt branch protection, không lấy kết quả cũ hoặc mock để hợp thức hóa release.
- CD nằm trong workflow riêng khi push main: kiểm tra provenance QA, build/đóng gói/checksum và GitHub Release. Cài lên PC do người dùng kiểm soát, có backup/rollback dữ liệu.

Hiện `TASK-UAT-LOCAL-ADAPTER` đã hết ba lần sửa; không gọi lại model hoặc đổi key để lách. Dev xanh không đồng nghĩa QA/release đạt hay ứng dụng không có bug. Xem trạng thái thực tế mới nhất trong `STATE.md`.

## Dọn repo

Chỉ giữ ba nhánh remote chính sau khi xác minh mã đã tích hợp, không còn PR cần dùng, SHA không đổi và backup Git bundle đã kiểm tra. Không xóa worktree, dữ liệu nghiên cứu hay bất kỳ file nào trong `skills/` và `agent/`. Giữ log/bằng chứng lịch sử; không sửa FAIL cũ thành PASS theo chính sách mới.
