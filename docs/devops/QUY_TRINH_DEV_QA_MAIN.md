# Quy trình phát triển và phát hành

Chỉ phát triển, sửa code và thêm testcase trên nhánh `dev` hiện có. Không tạo nhánh feature/fix/backup khác. `qa` và `main` chỉ nhận mã qua PR bảo vệ. Quyền tự động merge cả hai bước đã được chủ repo cấp, nhưng chỉ có hiệu lực khi mọi gate bắt buộc thực sự đạt.

## Một chu trình làm việc

1. AI đọc `AGENTS.md`, `agent/AGENT.md`, `STATE.md`, `PLAN.md` và `agent/DEV_QA_MAIN.md`; giữ nguyên dữ liệu, worktree và thay đổi chưa commit. Tìm, chọn lọc và pin skill phù hợp trong `skills/`; xác định contract và testcase hành vi trước khi sửa.
2. Trong lúc sửa, chạy profile `quick` hoặc `targeted`. Harness nhóm lỗi trùng nguyên nhân; tối đa ba lượt gọi agent sửa cho một task/PR. Không đổi key hoặc reset ledger để lách giới hạn.
3. Cố định nguồn, chạy `python scripts/verify.py --profile pr --component all --base origin/dev --out output/playwright/<run-moi>`. Mọi regression phần mềm bắt buộc phải thực thi và PASS; SKIP/ERROR/NOT_RUN không được coi là PASS. Harness tự phát hiện testcase mới trong các package/spec được hỗ trợ; module Python không có case sẽ báo lỗi. Browser chạy 2D trước, rồi 3D.
4. Sau PASS, lưu báo cáo thực vào `docs/qa/evidence/local-verification/report.json`, commit đúng phạm vi trên `dev`, push bình thường. Hook kiểm tra nhánh, origin, nguồn hiện tại và báo cáo đầy đủ; GitHub chạy lại độc lập trên đúng SHA mới. Không dùng `--no-verify`, force push hoặc sửa báo cáo thành PASS.
5. Controller mở PR `dev → qa`. Ngoài regression, QA bắt buộc có evidence truy vấn provider thật, CLI, nghiên cứu/thí nghiệm/report/paper, AI-UAT đúng nguồn và review cần thiết. Thiếu dịch vụ, xác thực, bằng chứng hoặc adapter chưa hỗ trợ thì BLOCKED.
6. Chỉ khi tất cả gate đạt, controller yêu cầu GitHub native auto-merge vào QA. Nó kiểm tra đúng PR, HEAD, run, check-suite, toàn bộ job bắt buộc và branch protection. Sau khi quan sát merge thật, lưu SHA và chỉ đồng bộ lịch sử `dev` nếu cây nguồn không đổi.
7. Sau QA đủ điều kiện, tiếp tục PR `qa → main` với đầy đủ gate. GitHub tự merge theo quyền chủ repo đã cấp. Workflow CD riêng khi push `main` kiểm tra lại provenance QA/cây nguồn, build, đóng gói, checksum và tạo GitHub Release. Cài/cập nhật trên PC vẫn do chủ repo kiểm soát, có backup và rollback dữ liệu.

## Coverage và bằng chứng

Mục tiêu mong muốn là **100% coverage line/branch mã production**. Mốc trên 95% trước đây là ước tính/mốc cải thiện; coverage hiện chỉ báo cáo, chưa chặn CI. Báo rõ tử số, mẫu số, phạm vi và các nhánh chưa phủ; không loại mã khó test hay nới assertion để đạt con số. Regression bắt buộc vẫn phải thực thi/PASS 100%.

Ba testcase live được khai báo riêng chỉ được hoãn với trạng thái NOT_RUN ở dev; chúng vẫn bắt buộc tại QA/main. Test HTTP fixture/SDK offline không chứng minh inference thật. Kết quả model có vẻ hợp lý không phải kiểm chứng khoa học. Thí nghiệm cần dữ liệu thực thi, kết quả đo, khả năng tái lập và liên kết tới paper.

Ledger AI-UAT cũ giữ nguyên ba lỗi. Chủ repo cấp riêng đúng **một** lượt Spark X2.5 4B local, tối đa **600 giây/6 bước**. Quyền một lần nằm trong metadata Git bên ngoài mã PR, ràng buộc nguồn/HEAD, có ghi nhận sử dụng để chống chạy lại. Build hoặc dependency chưa sẵn sàng phải chặn trước khi tiêu thụ lượt này. Adapter hiện chỉ kiểm tra Settings và đổi VI → EN; không được tuyên bố đã khám phá toàn bộ ứng dụng.

## Khởi động và dừng tự động promotion

Sau khi code đã được kiểm thử đầy đủ, commit và working tree sạch:

```powershell
python scripts/promote.py register --authorize-native-main-merge --enable-repo-auto-merge
python scripts/promote.py once
python scripts/promote.py watch --apply
```

Ở terminal khác:

```powershell
python scripts/promote.py status
python scripts/promote.py stop
python scripts/promote.py resume
```

Không có `--apply` thì chỉ quan sát. Policy, khóa, trạng thái và SHA merge thực nằm trong shared `.git/auto-promotion/`, tồn tại qua session/restart. Controller thay đổi phải đăng ký lại quyền tin cậy; không reset lịch sử. AI sửa lỗi CI là thành phần riêng, xem `agent/CI_REPAIR_SUPERVISOR.md`. Không xóa bất kỳ file nào trong `agent/` hoặc `skills/` khi dọn repo.

Cấu hình và unit test không chứng minh pipeline remote đã PASS hoặc merge thành công. Trạng thái thực tế, link run/PR và blocker phải đọc từ `agent/STATE.md` cùng báo cáo QA hiện hành.
