# CI/CD sau chuẩn hóa phục hồi

Cập nhật 6.5.6: GitHub đã đổi required check của `main` sang `QA gate`, giữ strict và các bảo vệ khác; receipt trước/sau nằm trong `docs/qa/evidence/ci-stabilization-6.5.6/github-cleanup.json`. Hai workflow trùng cũ đã bị vô hiệu hóa, PR #7/#9 được đóng vì toàn bộ lịch sử đã nằm trong PR tích hợp #11. Branch/worktree và log cũ được giữ. Đây chưa phải promotion thành công: nguồn mới vẫn phải qua đầy đủ coverage, regression và AI-UAT; chưa có merge/tag/release.

Preview6.3.0 trên main/dev/qa không được coi là baseline đáng tin cậy. Code hiện tại được tích hợp từ các worktree đã bảo toàn; evidence phải gắn đúng source/commit đang kiểm tra. Đây là thiết kế và candidate chưa release, không phải chứng nhận zero-bug/IEEE.

## CI — pull request

`quality.yml` chạy cho PR vào dev/qa/main và dispatch phục vụ chẩn đoán. Không deploy hoặc publish release trong workflow PR. Python3.11/3.12 trên Ubuntu/Windows, frontend types/whole-source coverage/build, dependency/security, browser thật, contract/policy và AI-UAT evidence vẫn được giữ. Không nới100% threshold, không coi SKIP/NOT_RUN là PASS.

Job policy cài dependency hash-lock trước test worker; không dùng filename-filtered discovery vì Python vẫn import các package test khác. Critical policy/repair/workflow cases chạy qua worker hiện có; Node policy và actionlint kiểm tra riêng. Development gate giữ FAIL của upstream thay vì đổi thành BLOCKED. QA gate yêu cầu Development và matching-source live qualification cho promotion qa/main.

## AI Auto-Repair — local development infrastructure

Supervisor riêng polling CI, chỉ chạy khi có local trust policy cho đúng owner/PR/branch/SHA/worktree. CLI được ủy quyền sửa source trong phạm vi, deterministic harness kiểm thử rồi supervisor commit/push. Tối đa3 invocation và persistent state. Không chạy tùy ý từ log/webhook/PR bên ngoài. [Hướng dẫn vận hành](CI_REPAIR_SUPERVISOR.vi.md).

Native GitHub auto-merge chỉ dành cho PR đủ điều kiện vào dev. Không tự promote qa/main. Gate đỏ hoặc thiếu live evidence tiếp tục chặn; việc bật flag repository không tự tạo vòng AI repair hay chứng minh PR đã merge.

## CD — qualified main push

`release.yml` chỉ chạy sau push vào main hoặc dispatch đúng protected main SHA. Release gate đòi commit là kết quả qa→main đã merge, Development/QA checks đúng app và head thành công, merged Git tree trùng source QA đã kiểm thử. PR code không chạy với release write token. Build cài hash-lock, kiểm tra Python/TypeScript và build web; packager tạo source/web ZIP và checksum. Publish kiểm tra lại provenance/tag/asset hash, không ghi đè asset khác nội dung và không dời tag.

Đây là GitHub Release cho ứng dụng local-first; không triển khai ứng dụng lên cloud. Native main promotion do chủ repo kiểm soát. Trước áp dụng CI/CD split phải đồng bộ required check của main từ pre-merge `Release gate` sang `QA gate`, giữ strict/admin/no-force/no-delete; nếu chưa đổi, main tiếp tục bị chặn thay vì bypass. Đọc report cuối để biết cấu hình nào đã thực sự được áp dụng.

## Controlled deployment trên PC

Chủ máy tự chọn thời điểm cập nhật. Dừng ứng dụng, backup đầy đủ data/projects/config và ghi phiên bản hiện tại; kiểm tra checksum release trước giải nén. Cài vào thư mục phiên bản mới, trỏ `PHDLAB_DATA_DIR` về dữ liệu được cấp phép, chạy smoke/regression phù hợp trước chuyển sử dụng. Giữ nguyên thư mục bản trước và backup để rollback. Không tự xóa/migrate dữ liệu hoặc thay bản đang chạy. Source/web ZIP không phải Windows installer tự chứa mọi runtime hay chứng nhận tất cả provider/Docker đã sẵn sàng.

Hiện không có deployment tự động, main merge, tag hoặc GitHub Release được chứng nhận. Thiếu provider credentials/live infrastructure, AI-UAT exhausted budget và coverage chưa100% vẫn là blocker; CD config không biến chúng thành PASS.
