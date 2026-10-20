# Context Memory v3.3 — đánh giá chất lượng

## Phương pháp

- **Corpus golden** (`tests/memory_eval/golden.py`): project "HSI denoising on CAVE under 12 GB VRAM" — 3 hypothesis
  (supported / testing / refuted), 5 experiment có git/ClearML/dataset/environment, 2 failure, 2 decision, 1 claim +
  1 evidence (v3.3), 6 paper (3 liên quan, 3 nhiễu), 3 episode — cộng N distractor (CIFAR ablation, NaN loss, paper về
  molecule…), N ∈ {0, 300, 1 500}.
- **Ba bộ task**, mỗi task có record bắt buộc phải tìm thấy và fact phải còn nguyên trong context đã biên dịch:
  - `TASKS` (dev, 9 task — 8 task của spec §20 + câu hỏi SwinIR): **đã dùng để tinh chỉnh** trọng số → số lạc quan.
  - `HELD_OUT` (8 task): viết sau khi tinh chỉnh; *đã bị xem một lần* để tìm lỗi hệ thống (dẫn tới stemming + gate
    centrality) → không còn sạch hoàn toàn.
  - `HELD_OUT_2` (6 task): viết **trước** hai sửa đổi cuối, chạy đúng một lần → **con số trung thực nhất**.
- Metric: recall@5/@10, precision@5, MRR (retrieval); `ids_in_context` (record đúng có trong text gửi LLM),
  `fact_fidelity` (fact nguyên văn còn trong text — evidence fidelity), `context_tokens`, `efficiency` = (ids + facts)
  trên 1 000 token (context efficiency). Temporal correctness và failure recall có test riêng (`tests/test_memory_v33.py`).

## Kết quả ở N = 1 500 distractor (~4–5k node)

| Bộ | Phiên bản | recall@5 | recall@10 | MRR | ids_in_context | fact_fidelity | context tokens | efficiency |
|---|---|---|---|---|---|---|---|---|
| dev | v3.2 | 0.47 | 0.64 | 0.49 | 0.79 | 0.89 | 2 821 | 0.60 |
| dev | v3.3 | **0.94** | 0.97 | **0.86** | 1.00 | 1.00 | 1 195 | 1.75 |
| held-out | v3.2 | 0.58 | 0.58 | 0.50 | 0.79 | 0.88 | 2 836 | 0.59 |
| held-out | v3.3 | **0.92** | 1.00 | **0.76** | 1.00 | 1.00 | 1 172 | 1.77 |
| **held-out-2 (sạch)** | v3.2 | 0.83 | 0.83 | 0.64 | 0.83 | 0.67 | 2 954 | 0.54 |
| **held-out-2 (sạch)** | v3.3 | **1.00** | 1.00 | **0.89** | 1.00 | 0.83 | 1 311 | 1.41 |

Held-out-2 tìm ra một lỗ hổng fidelity: `environment` của experiment ("RTX 3060 12GB, torch 2.4, batch 4") không bao giờ
được render, nên fact "batch 4" (K004) mất trong **cả** v3.2 và v3.3. Đã sửa sau lần chạy (render `env` trong refs);
sau sửa held-out-2 fact_fidelity = 1.00 (`v33-after-env-fix.json`) — con số này *không* tính là held-out vì đã biết lỗi.

Tiến trình held-out (để minh bạch về rủi ro overfit): lần đo đầu sau tinh chỉnh dev, held-out ở N = 1 500 chỉ đạt
recall@5 0.67 / MRR 0.58 — cải thiện thật nhưng khiêm tốn. Hai sửa đổi tổng quát (stemming nhẹ; centrality chỉ cộng đầy đủ
cho câu hỏi planning) nâng lên 0.92 / 0.76 và đo được trên held-out-2 sạch.

## Theo năng lực spec §19

| Năng lực | Bằng chứng |
|---|---|
| Retrieval recall | bảng trên; v3.2 mất hoàn toàn paper ở thư viện lớn (bug `limit=300`) |
| Precision | precision@5 thấp (0.27–0.38) vì mỗi task chỉ có 1–4 record đúng; 5 vị trí luôn chứa thêm bản ghi liên quan nhưng không nằm trong đáp án — đo đúng nhưng không phản ánh nhiễu. Nhiễu thực được đo qua context tokens / efficiency |
| Evidence fidelity | fact_fidelity 1.00 (dev, held-out); 0.83 → 1.00 (held-out-2, xem trên) |
| Temporal correctness | `test_temporal_current_penalises_refuted_but_history_keeps_it`, `test_superseded_decision_leaves_state_but_is_kept`, tie-break theo thứ tự ghi |
| Failure recall | T002/T006/H002 + `test_failure_memory_is_found_when_planning` (failure có cấu trúc lên top 5 khi lập kế hoạch) |
| Context efficiency | ×2.6–2.9; context nhỏ hơn 55–58 % với nhiều record đúng hơn |
| Decision support | gián tiếp: câu hỏi planning (T007, T009, K004) đưa đủ hypothesis + failure + baseline + ràng buộc phần cứng vào context; test acceptance §25 kiểm tra quyết định ghi lại được khôi phục ở phiên sau. Không đo chất lượng *quyết định* của LLM (cần đánh giá với model thật — xem giới hạn) |

## Giới hạn của đánh giá

- Một corpus tổng hợp, nhỏ, do cùng người viết engine thiết kế; distractor khác chủ đề nên dễ hơn nhiễu cùng chủ đề.
- Embedder hashing (lexical). Với Ollama embedding thật, vector ranking sẽ khác — cần chạy lại bộ golden.
- Không có đánh giá end-to-end chất lượng câu trả lời của LLM (decision support trực tiếp).
- `precision@k` không phù hợp với task có ít đáp án; nên bổ sung nDCG với nhãn mức độ liên quan.

Lặp lại: `.venv/Scripts/python benchmarks/bench_memory.py --pipeline v33`; cổng hồi quy: `tests/memory_eval/test_golden.py`.
