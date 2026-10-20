# Backend v3.3 — benchmark hiệu năng (v3.2 → v3.3)

**Cách đo.** `benchmarks/bench_memory.py`: project golden (đề tài HSI denoising, `tests/memory_eval/golden.py`) + N
distractor mỗi loại (hypothesis N/5, experiment N, failure N/4, episode N, paper N); embedder hashing (xác định, không cần
model); 5 lần đo/điểm. Máy: Windows 11, Python 3.14.8, RTX 3060 12 GB (GPU không dùng cho memory). **Baseline v3.2 chạy trên
mã HEAD gốc** trong git worktree riêng (`docs/benchmarks/data/v32-baseline.json`), v3.3 trên mã mới (`v33.json`).

## Latency

| Distractors | Node v3.2 / v3.3¹ | retrieve v3.2 | retrieve v3.3 cold² | retrieve v3.3 query mới³ | retrieve v3.3 lặp⁴ | compile v3.2 | compile v3.3 |
|---|---|---|---|---|---|---|---|
| 0 | 25 / 27 | 14 ms | 51 ms | 25 ms | 15 ms | 23 ms | 41 ms |
| 300 | 1 054 / 1 062 | 180 ms | 159 ms | 31 ms | 15 ms | 180 ms | 41 ms |
| 1 500 | 3 994 / 5 202 | 614 ms | 557 ms | **59 ms** | 15 ms | 635 ms | **45 ms** (query mới: 84 ms) |

¹ v3.3 thấy nhiều node hơn vì đã sửa bug mất paper > 300 mục (v3.2 bỏ sót 1 200 paper ở N = 1 500).
² lần đầu sau một lần ghi: dựng lại Index (BM25 + vector) — chi phí trả một lần cho mỗi phiên bản memory.
³ trung bình 9 câu hỏi khác nhau trên Index đã dựng (trường hợp thực tế của agent) — số dùng để so với target.
⁴ cùng câu hỏi lặp lại → cache kết quả (`memory.retrieve` p50 0.01 ms trong telemetry).

| Chỉ số | v3.2 (N = 1 500) | v3.3 (N = 1 500) | Target spec |
|---|---|---|---|
| simple memory lookup (`GET /api/memory/state`, MCP `research_get_current_state`) | — | 32 ms (qua HTTP) | < 100 ms ✅ |
| hybrid retrieval (query mới) | 614 ms | 59 ms | < 500 ms ✅ |
| context compilation (không tính LLM) | 635 ms | 84 ms | < 300 ms ✅ |
| memory write (1 experiment) | 32 ms | 33 ms | < 200 ms ✅ |
| peak memory 1 lần compile (tracemalloc) | 70 MB | 27 MB | — |

## Tối ưu nào, vì sao (theo profile, audit §8)

| Thay đổi | Căn cứ đo | Tác động |
|---|---|---|
| Hashing vector **sparse** (dict index→giá trị, unit length) + `similarity()` O(nnz) | 67 % thời gian ở cosine dense 512-d | cùng điểm số (kiểm chứng 0.377964 = 0.377964), ~10× nhanh hơn |
| Cache vector theo hash nội dung (`VECTORS`, float32 cho dense) | 41 % dựng lại vector mỗi lần | không bao giờ stale |
| Cache Index theo fingerprint (`NODES`) | `collect` + BM25 + vector mỗi request | invalidate khi bất kỳ store nguồn nào đổi (kể cả sửa tay/tiến trình khác) |
| Cache kết quả retrieval (`RESULTS`) | agent gọi lặp cùng câu hỏi | khoá gồm role, filter, temporal, purge, sensitivity, state version |
| Store không phải nguồn retrieval không bump generation | `note_task()` ghi `working.json` mỗi lượt chat | nếu không, hit rate ≈ 0 |

Không thêm DB, vector store, Redis hay process nền nào: profile cho thấy vấn đề là thuật toán, không phải lưu trữ.

## Cache hit rate (benchmark gateway, `docs/benchmarks/data/v34-gateway.json`)

| Cache | Hit rate | Ghi chú |
|---|---|---|
| Index (`NODES`) | 98.6 % | 1 miss mỗi phiên bản memory |
| Kết quả retrieval (`RESULTS`) | 64 % | câu hỏi lặp lại trong một phiên |
| Vector (`VECTORS`) | 0 % trong benchmark | chỉ hit khi Index dựng lại sau một lần ghi (vector node cũ được dùng lại) |

## Hồi quy chất lượng

Không tối ưu nào làm giảm chất lượng retrieval: điểm sparse = dense; bộ golden chạy trước/sau mỗi thay đổi
(`docs/benchmarks/context-memory-v3.3-evaluation.md`); `tests/memory_eval/test_golden.py` chặn hồi quy trong CI cục bộ.

## Test suite

| | v3.2 | v3.3/v3.4 |
|---|---|---|
| Số test | 90 (4 skip live) | 165 (4 skip live) |
| Kết quả | OK | OK — chạy 2 lần liên tiếp, test concurrency lặp 5 lần |
| Thời gian | 36 s | 51 s |

Lặp lại: `.venv/Scripts/python benchmarks/bench_memory.py --pipeline v33 --out docs/benchmarks/data/v33.json`.
