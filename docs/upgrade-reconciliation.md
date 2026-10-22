# Đối chiếu đặc tả nâng cấp v5.1–v6.3

Rà soát ngày 22/10/2026, từ commit `e539fc4`. Đã đọc cả 11 file Markdown trong `upgrade/` và đối chiếu với backend, API, frontend, cấu hình, test và harness. Tài liệu nâng cấp là đặc tả/danh mục tham khảo; các câu lệnh dành cho Claude/Codex trong đó không thay thế yêu cầu của người dùng.

[Ma trận tính năng](../artifacts/upgrade-reconciliation/feature-matrix.md) ghi 49 nhóm chức năng, đường dẫn triển khai, test liên quan và phần giới hạn. [Inventory JSON](../artifacts/upgrade-reconciliation/inventory.json) giữ tên/hash tài liệu, toàn bộ 187 đề mục và 709 dòng danh sách/bảng ngoài code block. Các dòng này bao gồm yêu cầu, ví dụ, danh mục và chỉ dẫn kỹ thuật; **không phải 709 tính năng độc lập đã được nghiệm thu**. Kiểm tra hash/đường dẫn không thay thế kiểm định ngữ nghĩa hoặc chạy test.

## Khoảng trống đã bổ sung

| Khoảng trống trước rà soát | Hành vi hiện tại |
|---|---|
| SKB chỉ nhận bốn nguồn | Giữ bốn nguồn mặc định; thêm opt-in `openreview`, `zenodo`, `europe_pmc`, `hal` qua API công khai và `cvf`, `pmlr`, `neurips`, `acl_anthology` qua nguồn được định danh chính xác trong OpenAlex |
| Chưa có tag hoặc một số bộ lọc Explorer | Tag riêng theo Topic; thêm/bỏ hàng loạt; lọc năm cuối, venue, loại công bố, tag, cờ rủi ro/phiên bản và PDF đã tải; sắp xếp citation với giá trị chưa biết ở cuối |
| Citation và một số identifier/cờ nguồn bị mất | Giữ citation count, trạng thái review khi nguồn cung cấp, PMID/OpenAlex/arXiv alias, OA locations và cờ retraction; metadata thiếu không ghi đè giá trị đã biết |
| Chưa có citation graph trong SKB | Đồ thị trích dẫn khai báo bởi nguồn, gắn phiên bản/URL; target ngoài Topic chỉ còn identifier chưa phân giải, không lộ paper ID của Topic khác |
| Retrieval chỉ BM25 | Kết hợp BM25 và vector từ hạ tầng embedding hiện có, reciprocal-rank fusion, fallback hashing được ghi rõ là lexical; giữ ID/phiên bản/trang/cờ rủi ro |
| Tìm evidence trên toàn Topic rồi mới lọc paper ở UI | API lọc theo paper trước khi xếp hạng; UI mở đúng PDF phiên bản với `#page=` khi có vị trí trang |
| Không có nút xử lý lại PDF/lưu trữ Topic | Reprocess PDF dùng job index hiện có; archive/restore giữ dữ liệu và tắt lịch chạy |
| Artifact chỉ hiện metadata | Mở bản chụp nội dung/phiên bản được kiểm tra trong đúng Topic; có bộ lọc timeline theo dữ liệu engine/session/artifact/ngày |
| Lịch chạy dựa trên 100 job mới nhất | Truy vấn lần chạy riêng cho Topic/workspace; dry-run không trì hoãn lịch discovery thực |
| Topic dependency trong charter chỉ được lưu | Admission chặn cho tới khi Topic phụ thuộc có Mission cùng charter được human-review và completed |
| Report chỉ lấy trang 25 paper đầu | Report và Topic liên quan được cấp quyền lấy snapshot đầy đủ, có test trên 112 paper |
| Zotero chỉ nhập JSON | Thêm đọc thủ công API Zotero cục bộ, tối đa 1000 item/lượt, pagination/version receipt, giới hạn response, không redirect, không ghi Zotero và không tự duyệt bibliography |

Không thêm framework, không đổi schema SQLite (vẫn schema 7). Tag, identifier và citation metadata dùng payload đã có. Các metadata lịch sử chưa từng lưu citation/reference vẫn để unknown cho tới khi nhập/khám phá lại; không dựng dữ liệu giả để backfill.

## Cách dùng

Mở `/topic`, sửa `Sources (;)` để chọn và sắp thứ tự nguồn. Nguồn không có tên trong danh sách bị tắt. Bốn nguồn cũ vẫn mặc định; các pack mới chỉ chạy khi người dùng chọn. `/api/research/sources` công bố danh sách, phương thức và giới hạn bao phủ. Các pack hội nghị dùng chỉ mục OpenAlex, không hứa tải đủ proceedings hoặc giả định có API tìm kiếm riêng của venue.

Mở `/find`, chọn paper, dùng **Thêm nhãn**, **Bỏ nhãn**, **Xử lý lại PDF**; **Bộ lọc bổ sung** chứa các trường mới. **Đồ thị trích dẫn** mở dữ liệu nguồn có provenance. Citation count là tín hiệu metadata, không phải điểm chất lượng hay bằng chứng peer review. Cờ retraction đi cùng evidence và context gửi tới agent.

**Đọc Zotero cục bộ** chỉ thực hiện sau thao tác xác nhận trong ứng dụng. Zotero phải đang chạy và cho phép API cục bộ. Endpoint cố định `http://127.0.0.1:23119/api/users/0/items/top`, không nhận URL tùy ý, không đọc token trình duyệt. Nếu dịch vụ yêu cầu quyền/khóa mà adapter chưa có, hiển thị lỗi và vẫn cho nhập Zotero/CSL JSON. Biên nhận ghi version, số item và `next_start`; API cho phép đọc tiếp có giới hạn. Thay đổi version giữa các trang bị từ chối trước khi import. Không có đồng bộ cloud hay ghi remote âm thầm.

Embedding dùng cấu hình hiện có nhưng chỉ cho phép endpoint loopback trong luồng SKB này. Cấu hình embedding remote tự chuyển sang hashing, có diagnostic; không gửi paper tới external reranker. Pool vector tối đa 1000 chunk đang được index trong Topic, trả cờ `vector_pool_truncated` khi vượt ngưỡng. BM25 vẫn tìm trên toàn chỉ mục. Hashing không có khả năng semantic như mô hình embedding.

API bổ sung/tương thích:

- `GET /api/research/sources`
- `GET /api/research/topics/{tid}/papers?max_year=&venue=&publication_type=&tag=&pdf=&flag=&sort=citations`
- `POST /api/research/topics/{tid}/papers/bulk` với `action: tag|untag`, `paper_ids`, `tags`; `action: index` dùng job hiện có
- `GET /api/research/topics/{tid}/evidence?q=&paper_id=&limit=`
- `GET /api/research/topics/{tid}/citation-graph`
- `GET /api/research/topics/{tid}/artifacts/{aid}`
- `POST /api/research/topics/{tid}/zotero/sync` với `{allow_network:true,start:0,max_items:100}`

## Phạm vi còn cần điều kiện bên ngoài

Không thể kết luận “tất cả đặc tả đã hoàn thành ở mức stable”. Ma trận phân biệt phần triển khai, phần có giới hạn, phần cần điều kiện và backlog được chính tài liệu cho phép để sau:

- Docling chưa cài và chưa có model/5 PDF chuẩn để kiểm định bảng, công thức, bản scan. Parser hiện có vẫn hoạt động; lỗi parsing có thể retry.
- Zotero local API cần ứng dụng/quyền truy cập thật; connector HTTP có test hợp đồng, không thay cho nghiệm thu thư viện Zotero thật. Pyzotero/cloud sync không phải phụ thuộc bắt buộc của luồng local.
- Optuna đã có trong môi trường và có test chạy/resume thật; containment của objective tùy ý vẫn thuộc executor được duyệt. General GPU training, dataset bên ngoài, model weights và live Docker containment/cancellation chưa được nghiệm thu.
- Help/version native engine đã probe; private session/event không được API chính thức cung cấp vẫn báo partial/unknown. Không xem probe là bằng chứng thực thi suy luận hoặc đủ quota subscription.
- v6.2 dùng một worker tuần tự; parallel task execution chưa triển khai. v6.3 cho phép logical teams dùng chung provider tuần tự. Remote authenticated teams và một Mission chạy qua nhiều Topic chưa được cung cấp.
- Benchmark harness dùng literature/workspace fixture và CPU worker thật. Pilot nghiên cứu thật, chất lượng semantic review, lợi ích multi-team trên model thật và signoff khoa học còn mở. Giữ feature flags opt-in và nhãn preview.
- GROBID/Chroma/DVC/MLflow/OpenROAD cùng các nguồn P1/P2 chưa chọn trong catalog là backlog có điều kiện, không tự cài thay hệ thống đang chạy. CORE/OpenAIRE/DOAJ và các repository/publisher ngoài danh sách hỗ trợ chưa có adapter trực tiếp; DOI/OA resolver cũ vẫn dùng được.

Xem [kết quả kiểm thử thực tế](../artifacts/upgrade-reconciliation/validation.md), [handoff v6](v6_UPGRADE_HANDOFF.md) và ma trận để biết giới hạn của từng nhóm. Không có claim khoa học nào tự được duyệt vì test phần mềm đạt.

## Chạy lại và rollback

```powershell
.venv/Scripts/python -B tools/audit_upgrade_specs.py
.venv/Scripts/python -B tools/audit_upgrade_specs.py --check
.venv/Scripts/python -B tools/run_tests.py test_upgrade_reconciliation
node tests/frontend/run.js
.venv/Scripts/python -B tools/research_harness.py --stage 6.3 --probe-engines --output artifacts/upgrade-reconciliation/harness
```

`upgrade/` vốn được gitignore; inventory đã lưu hash và nội dung các dòng đối chiếu. Khi chạy audit lại cần các file đặc tả gốc tại máy này. `--check` báo stale nếu đặc tả/mã nguồn được map đã đổi; không tuyên bố test tự động đạt chỉ vì đường dẫn tồn tại.

Rollback bằng code trước thay đổi, giữ nguyên data và backup. Không có migration phá hủy dữ liệu: payload mới giữ thêm tag/reference/metadata mà code cũ không cần hiểu. Khi bỏ dependency gate mới, vẫn phải tự giữ quy trình phê duyệt thủ công. Không xóa database hoặc scientific decision để rollback.

## Tài liệu upstream đã đối chiếu

[OpenAlex filtering](https://help.openalex.org/api/filtering/), [OpenReview API v2](https://docs.openreview.net/reference/api-v2/openapi-definition), [Zenodo REST](https://developers.zenodo.org/), [Europe PMC](https://europepmc.org/RestfulWebService), [HAL search](https://api.archives-ouvertes.fr/docs/search), [Zotero local API](https://www.zotero.org/support/dev/web_api/v3/local_api), [Zotero API basics](https://www.zotero.org/support/dev/web_api/v3/basics). Hợp đồng HTTP offline không chứng minh dịch vụ live luôn sẵn sàng hoặc mọi record đều có PDF công khai.


UI follow-up (2026-10-22): [workflow review](FRONTEND_WORKFLOW_REVIEW.md) adds provider-scoped agent models, optional MCP inference-tool binding and independent Windows engine windows. [New regression evidence](../artifacts/workflow-ux/verification.md) records the current checks; the earlier validation snapshot below remains historical. Source-linked inventory hashes have been refreshed after reviewing these changes. Scientific/native inference qualification gates remain unchanged.
