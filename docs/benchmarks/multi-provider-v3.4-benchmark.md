# Multi-provider v3.4 — benchmark

`benchmarks/bench_gateway.py` qua HTTP stack thật (TestClient → `/mcp`, `/api/gateway/*`), project golden + N distractor,
hashing embedder. CLI vendor được thay bằng `tests/providers/fake_cli.py` ⇒ số "stream start-up" là **overhead của
PhD-Lab** (spawn tiến trình, stdin, parse JSONL); first-token latency của model thật phụ thuộc vendor và **không** được đo
ở đây. Dữ liệu: `docs/benchmarks/data/v34-gateway.json`.

## MCP tool latency (median ms, 4 lần ấm sau 1 lần lạnh)

| Tool | N = 0 | N = 300 | N = 1 500 | Target |
|---|---|---|---|---|
| research_get_current_state | 32 | 30 | 32 | < 200 ✅ |
| research_search_memory | 47 | 48 | 48 | ✅ |
| research_get_experiment | 35 | 39 | 66 | ✅ |
| research_get_evidence | 42 | 42 | 42 | ✅ |
| research_get_failures | 42 | 44 | 52 | ✅ |
| research_get_decisions | 25 | 26 | 28 | ✅ |
| research_get_context | 67 | 65 | 72 | ✅ |
| research_get_provenance | 29 | 35 | 47 | ✅ |
| research_record_observation | 27 | 27 | 27 | ✅ |

p50 / p95 toàn bộ `mcp.tool` (telemetry, N = 1 500): 37 / 77 ms. Phần lớn là chi phí HTTP + JSON + sensitivity check.

## Context Gateway

| Bước | N = 0 | N = 300 | N = 1 500 | Target |
|---|---|---|---|---|
| prepare (state + retrieval + compile + sanitize + persist + audit) | 59 ms | 74 ms | 110 ms | retrieval < 500, compile < 300 ✅ |
| stream start-up đến event đầu (overhead PhD-Lab) | 11 ms | 11 ms | 11 ms | — |
| round-trip với fake provider | `gateway.request` p50 53 ms | | | — |
| auth overhead | 0 (CLI dùng credential cache của vendor; health probe cache 60 s) | | | — |

## Cache

Index 98.6 % hit, retrieval result 64 %, `memory.compile` cache-hit 40 % (compile luôn chạy, retrieval bên trong hit).
Ghi candidate qua MCP **không** làm mất cache (candidates không phải nguồn retrieval) — đúng thiết kế.

## Không đo / cần đo với provider thật

First-token latency, throughput, hành vi rate limit của từng vendor cần chạy với CLI thật đã đăng nhập. Trên máy audit:
`codex` 0.163.0 có và health thật = `CONNECTED (signed in with ChatGPT)`; `claude`, `agy`, `gemini` không có trên PATH.
Chưa gửi request thật nào tới vendor (sẽ gửi dữ liệu nghiên cứu ra ngoài và dùng quota — cần researcher đồng ý).
