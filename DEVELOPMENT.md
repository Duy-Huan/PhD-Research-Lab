# DEVELOPMENT — PhD Research Lab v3.2

## Run
```bash
python start.py                 # checks files/version, installs requirements, serves http://127.0.0.1:8765
python start.py --check         # installation check only
```
The API answers only requests whose `Host` is `localhost`, `127.0.0.1` or `[::1]` (DNS-rebinding protection). Add more
names with `PHDLAB_ALLOWED_HOSTS="lab.local"`.

## Tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```
- Standard library only (no pytest needed). Every test module imports `tests/_env.py` first, which sets
  `PHDLAB_DATA_DIR` to a temporary folder — the real `data/` is never touched.
- `tests/test_sandbox_e2e.py` runs a real job in the local sandbox (creates a venv the first time, ~15 s).
- Live integrations are opt-in: `PHDLAB_CLEARML_LIVE=1`, `PHDLAB_CODEX_LIVE=1` (`tests/test_live_integrations.py`),
  `PHDLAB_LMSTUDIO_LIVE=1` (+ `PHDLAB_LMSTUDIO_MODEL`, loads and unloads a real model — `tests/test_vram_gate.py`).

## Layout (v3.2 additions)
| Path | Role |
|---|---|
| `backend/memory/` | Context Memory: legacy tiers (`__init__`), `working`, `research`, `knowledge`, `pages` (raw page-store), `lod` (TREEFRAG-style tree), `embeddings`, `retrieval`, `compiler`, `compressor` |
| `backend/integrations/` | `base` (IntegrationStatus contract), `workspace` (VS Code, Dev Containers, Environment Manager, Jupyter), `experiment` (ExperimentBackend, LocalRunsBackend, ClearMLAdapter), `agents` (CodexBackend) |
| `backend/resources.py` | hardware policy, caps, JIT VRAM unload, thermal guard, GPU-fault classification |
| `backend/llm_router.py` | SmartMultiRouter for engine mode `auto` |
| `backend/critic.py` | live critic (rules + optional LLM) |
| `backend/provenance.py` | artifact sealing + inspection |
| `backend/connectors/` | DataConnectorRegistry + plugins (`*_connector.py`) |
| `backend/api_v32.py` | all v3.2 routes |
| `frontend/app/control.js` | 🧭 Control Center tab |
| `frontend/app/workspace.js` | 💻 Workspace & Runs tab (replaces the Monaco Code IDE) |

## Configuration keys (data/config.json — gitignored; secrets masked in the UI)
```jsonc
{
  "memory": {"v2_pipeline": true, "high_watermark_tokens": 16000, "low_watermark_tokens": 2000, "chunk_tokens": 3500,
             "min_keep_messages": 2, "parallel_summaries": 2, "summary_timeout_s": 240, "context_budget_tokens": 3500,
             "embed_engine": "auto", "embed_model": "nomic-embed-text", "rerank_url": "", "rerank_model": ""},
  "resources": {"enforce_caps": true, "require_unload": true, "vram_free_target_mb": 2048, "unload_wait_s": 1.5,
                "gpu_temp_limit_c": 83, "cpu_fallback_on_gpu_fault": true, "gpu_busy_util_pct": 80,
                "sandbox_memory_gb": 0, "sandbox_cpus": 0, "local_ai_vram_gb": 0, "local_ai_threads": 0},   // 0 = derived
  "clearml": {"enabled": false, "api_host": "http://localhost:8008", "web_host": "http://localhost:8080",
              "files_host": "http://localhost:8081", "access_key": "<from ClearML UI>", "secret_key": "<from ClearML UI>",
              "project": "PhD Research Lab", "queue": "default"},
  "codex": {"enabled": false, "binary": "", "sandbox": "read-only", "model": "", "timeout_s": 1800},
  "routing": {"online_check": true, "chains": {"live_critic": ["groq", "ollama", "@cloud"]},
              "provider_headers": {"ninerouter": {"X-9Router-Skills": "rtk"}}},
  "critic": {"enabled": true, "llm": true, "interval_chars": 700},
  "provenance": {"enabled": true, "csv_header": true},
  "agent_modes": {"critic": "auto"}
}
```
Engine mode `auto` routes by task kind (`config.AGENT_TASK_KIND`); `@cloud` = default cloud provider, `@claude` = Anthropic.

## Conventions
- Vendor SDKs/CLIs are imported/called only inside `backend/integrations/*`; adapters report `disabled | unconfigured |
  unavailable | available | error` and never claim success without a real probe.
- Long-term memory has one writer (`memory/compressor.py`) plus explicit researcher actions; raw pages are write-once.
- New modules stay Python ≥ 3.9 compatible and pure-Python (Windows Smart App Control friendly).
