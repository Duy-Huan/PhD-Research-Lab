"""Configuration storage for the PhD Interactive Autonomous Research Lab.

Global settings (API keys, providers, agent engines) are persisted in data/config.json.
Each research PROJECT has its own data folder (workspace, chats, library, outputs) and its
own references folder, so one installation can switch between several research projects.
Each API key is only ever sent to its own provider's API endpoint.
"""
from __future__ import annotations

import json
import os
import re
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path

APP_VERSION = "6.4.2"

ROOT = Path(__file__).resolve().parents[2]
# PHDLAB_DATA_DIR (v3.2) moves ALL user data elsewhere — used by the test suite so it never touches the real data/.
_DATA_OVERRIDE = os.environ.get("PHDLAB_DATA_DIR", "").strip()
GLOBAL_DIR = Path(_DATA_OVERRIDE).resolve() if _DATA_OVERRIDE else ROOT / "data"   # global config + the "Default project"
CONFIG_PATH = GLOBAL_DIR / "config.json"
PROJECTS_ROOT = GLOBAL_DIR / "projects" if _DATA_OVERRIDE else ROOT / "projects"    # default parent folder for new projects
DEFAULT_REFS = GLOBAL_DIR / "references"
META_NAME = "project_meta.json"
GLOBAL_DIR.mkdir(parents=True, exist_ok=True)

# Cloud AI providers. kind = "anthropic" (native Messages API) or "openai" (OpenAI-compatible
# /chat/completions). Default models are suggestions only - use "List models" in the UI to pick
# exactly what your account can access.
PROVIDERS = {
    "anthropic":  {"label": "Anthropic Claude", "kind": "anthropic", "base_url": "https://api.anthropic.com/v1",
                   "model": "claude-sonnet-5-5", "key_url": "https://console.anthropic.com/settings/keys",
                   "models": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"]},
    "openai":     {"label": "OpenAI ChatGPT", "kind": "openai", "base_url": "https://api.openai.com/v1",
                   "model": "gpt-5", "key_url": "https://platform.openai.com/api-keys",
                   "models": ["gpt-5", "gpt-5-mini", "gpt-4.1", "o3"]},
    "gemini":     {"label": "Google Gemini", "kind": "openai",
                   "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                   "model": "gemini-2.5-pro", "key_url": "https://aistudio.google.com/apikey",
                   "models": ["gemini-2.5-pro", "gemini-2.5-flash"]},
    "xai":        {"label": "xAI Grok", "kind": "openai", "base_url": "https://api.x.ai/v1",
                   "model": "grok-4", "key_url": "https://console.x.ai", "models": ["grok-4"]},
    "deepseek":   {"label": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com/v1",
                   "model": "deepseek-chat", "key_url": "https://platform.deepseek.com/api_keys",
                   "models": ["deepseek-chat", "deepseek-reasoner"]},
    "mistral":    {"label": "Mistral AI", "kind": "openai", "base_url": "https://api.mistral.ai/v1",
                   "model": "mistral-large-latest", "key_url": "https://console.mistral.ai/api-keys",
                   "models": ["mistral-large-latest", "mistral-medium-latest", "codestral-latest"]},
    "qwen":       {"label": "Alibaba Qwen (DashScope)", "kind": "openai",
                   "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                   "model": "qwen-max", "key_url": "https://bailian.console.alibabacloud.com/",
                   "models": ["qwen-max", "qwen-plus", "qwen-turbo"]},
    "moonshot":   {"label": "Moonshot Kimi", "kind": "openai", "base_url": "https://api.moonshot.ai/v1",
                   "model": "moonshot-v1-128k", "key_url": "https://platform.moonshot.ai/console/api-keys",
                   "models": ["moonshot-v1-128k"]},
    "cohere":     {"label": "Cohere", "kind": "openai", "base_url": "https://api.cohere.ai/compatibility/v1",
                   "model": "command-a-03-2025", "key_url": "https://dashboard.cohere.com/api-keys",
                   "models": ["command-a-03-2025"]},
    "perplexity": {"label": "Perplexity", "kind": "openai", "base_url": "https://api.perplexity.ai",
                   "model": "sonar-pro", "key_url": "https://www.perplexity.ai/settings/api",
                   "models": ["sonar-pro", "sonar-reasoning-pro", "sonar"]},
    "groq":       {"label": "Groq", "kind": "openai", "base_url": "https://api.groq.com/openai/v1",
                   "model": "llama-3.3-70b-versatile", "key_url": "https://console.groq.com/keys",
                   "models": ["llama-3.3-70b-versatile"]},
    "openrouter": {"label": "OpenRouter (multi-vendor)", "kind": "openai", "base_url": "https://openrouter.ai/api/v1",
                   "model": "openai/gpt-5", "key_url": "https://openrouter.ai/keys", "models": []},
    "together":   {"label": "Together AI", "kind": "openai", "base_url": "https://api.together.xyz/v1",
                   "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "key_url": "https://api.together.ai/settings/api-keys",
                   "models": []},
    # v3.2 LLM gateway (LLM_UPDATE_PROMPT.md). Local gateways keep their own keys in plaintext: never put your main
    # paid OpenAI/Anthropic keys into them — give them only their own gateway token.
    "deepinfra":  {"label": "DeepInfra", "kind": "openai", "base_url": "https://api.deepinfra.com/v1/openai",
                   "model": "meta-llama/Llama-3.3-70B-Instruct", "key_url": "https://deepinfra.com/dash/api_keys",
                   "models": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct"]},
    "ninerouter": {"label": "9Router (local gateway)", "kind": "openai", "base_url": "http://localhost:20128/v1",
                   "model": "", "key_url": "", "models": [], "local_gateway": True, "key_optional": True},
    "omniroute":  {"label": "OmniRoute (local proxy)", "kind": "openai", "base_url": "http://localhost:20130/v1",
                   "model": "", "key_url": "", "models": [], "local_gateway": True, "key_optional": True},
    "custom":     {"label": "Custom (OpenAI-compatible)", "kind": "openai", "base_url": "",
                   "model": "", "key_url": "", "models": []},
}

# Agents (v5): two agents do the research work, one utility model runs background chores. Engine value per agent:
# "auto" (smart router: local → cloud chain), "cloud" (= default cloud provider), "claude" (Anthropic when it has a key),
# "local", "ollama" or a provider id. What an agent does is decided by the SKILL it runs (backend/agent/skills/*.md),
# not by a separate agent per tool.
AGENTS = {
    "assistant": {"label": "Trợ lý chat — hội thoại thường ngày, độc lập với agent nghiên cứu", "default": "auto"},
    "research": {"label": "Research agent — điều phối, nghiên cứu, thiết kế, code, viết bài", "default": "auto"},
    "reviewer": {"label": "Reviewer agent — phản biện, kiểm chứng claim / evidence", "default": "claude"},
    "utility":  {"label": "Tiện ích chạy nền — tóm tắt bộ nhớ, trích xuất PDF/BibTeX, truy vấn tìm kiếm", "default": "auto"},
}
# v1–v4 agent names → the v5 agent that now does their job (old call sites and saved settings keep working)
AGENT_ALIASES = {
    **{a: "research" for a in ("lit2plan", "experiment", "author", "editor", "masterclass", "coder", "context_agent",
                               "results_analyst", "workflow_planner", "hpo_strategist", "ai_workspace", "data_extractor",
                               "chat_lit2plan", "chat_experiment", "chat_paper", "chat_masterclass")},
    **{a: "reviewer" for a in ("critic", "ext_reviewer", "ext_meta", "ext_fixer", "chat_review")},
    **{a: "utility" for a in ("summarizer", "pdf_parser", "bib_extractor", "query_expansion", "web_query")},
}


def agent_key(name: str) -> str:
    """The v5 agent behind any agent name (unknown names are research work)."""
    return name if name in AGENTS else AGENT_ALIASES.get(name, "research")


# v4.1 model lifecycle: agents whose calls are BACKGROUND tasks (no researcher waiting on a stream). Their local models
# follow lifecycle.local_background (default: load → task → unload); everything else follows lifecycle.local_interactive.
BACKGROUND_AGENTS = frozenset({"utility", "summarizer", "critic", "pdf_parser", "bib_extractor", "query_expansion",
                               "web_query", "workflow_planner", "hpo_strategist"})

# v3.2: task kind of every agent for the "auto" engine mode (backend/llm_router.py)
AGENT_TASK_KIND = {
    "assistant": "reasoning", "research": "reasoning", "reviewer": "reasoning", "utility": "extract",
    "data_extractor": "extract", "query_expansion": "extract", "web_query": "extract", "coder": "code",
    "lit2plan": "reasoning", "experiment": "reasoning", "author": "writing", "reviewer": "reasoning", "editor": "writing",
    "context_agent": "reasoning", "results_analyst": "reasoning", "masterclass": "writing",
}

SEARCH_DEFAULTS = {
    "web_engine": "duckduckgo",   # duckduckgo (free, no key) | tavily | brave
    "tavily_key": "", "brave_key": "", "openalex_key": "", "ieee_key": "", "serpapi_key": "",
    "s2_key": "",                 # Semantic Scholar API key (optional, higher rate limit)
    "mailto": "",                 # e-mail for the OpenAlex "polite pool" (optional, faster)
    "n_results": 8,               # results per search
    "read_pages": True,           # read the text of the top web pages (more accurate, slower)
}
SEARCH_KEYS = ("tavily_key", "brave_key", "s2_key", "openalex_key", "ieee_key", "serpapi_key")

DEFAULTS = {
    "providers": {pid: {"api_key": "", "model": spec["model"], "base_url": ""} for pid, spec in PROVIDERS.items()},
    "default_cloud": "anthropic",
    "lmstudio_base_url": "http://localhost:1234/v1",
    "local_model": "",
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "",
    "agent_models": {},      # v3: per-agent model override {agent: model id} for the engine selected for that agent
    "references_dir": str(DEFAULT_REFS),  # legacy (v1.0-1.5): becomes the Default project's references
    "projects": [],          # registered project data folders
    "active_project": "",    # data folder of the active project ("" = Default project in data/)
    "fallback_to_cloud": True,
    "agent_modes": {k: v["default"] for k, v in AGENTS.items()},
    "search": dict(SEARCH_DEFAULTS),
    "latex_online": False,   # v2.7: allow compiling the preview with the public LaTeX-on-HTTP service (sends the paper)
    "memory": {"keep_recent_turns": 12, "auto_summarize": True, "interval_s": 180,
               # v3.2 Context Memory v2 (CONTEXT_MEMORY.md): token watermarks of the compressor, chunk size of the
               # hierarchical reduce, retrieval/compiler settings
               "high_watermark_tokens": 16000, "low_watermark_tokens": 2000, "chunk_tokens": 3500, "min_keep_messages": 2,
               "parallel_summaries": 2, "summary_timeout_s": 240, "context_budget_tokens": 3500,
               "embed_engine": "auto", "embed_model": "nomic-embed-text", "rerank_url": "", "rerank_model": ""},
    # v3.2 hardware resource governor (HARDWARE_RESOURCE_CONSTRAINT.md); 0 = derived from the scanned machine
    "resources": {"enforce_caps": True, "require_unload": True, "vram_free_target_mb": 2048, "unload_wait_s": 1.5,
                  "unload_timeout_s": 20, "gpu_temp_limit_c": 83, "cpu_fallback_on_gpu_fault": True, "gpu_busy_util_pct": 80,
                  "sandbox_memory_gb": 0, "sandbox_cpus": 0, "local_ai_vram_gb": 0, "local_ai_threads": 0,
                  # v4.1: free VRAM automatically (idle local models only — never one that is answering) when a GPU
                  # training run is started; off = the v3.2 rule (the run is refused until the researcher unloads)
                  "auto_unload_for_gpu": False},
    # v4.1 model lifecycle (backend/model_lifecycle.py). One vocabulary for every engine class:
    #   unload_after_task  load → task → unload (after unload_grace_s, so a burst of calls does not thrash VRAM)
    #   keep_loaded        keep it until the researcher unloads it
    #   idle_unload        keep it while in use, release after <class>_idle_min minutes without a task
    # local = LM Studio / Ollama models in VRAM; cli = native CLI sessions (Codex / Claude Code / Gemini / agy — the
    # process itself always exits after a request); mcp = the Docker sandbox container used by MCP tools and agent runs;
    # cloud = the pooled HTTPS connections to cloud APIs.
    "lifecycle": {"enabled": True, "unload_on_exit": True, "local_background": "unload_after_task", "local_interactive": "idle_unload",
                  "cli": "idle_unload", "mcp": "idle_unload", "cloud": "idle_unload",
                  "local_idle_min": 10, "cli_idle_min": 30, "mcp_idle_min": 15, "cloud_idle_min": 5,
                  "unload_grace_s": 15, "respect_manual_loads": True, "single_model_vram": True},
    # ClearML offline recording (SDK only, no server): auto_record records every finished run as an offline session in
    # <project>/clearml that can be imported into a ClearML Server later.
    "clearml": {"enabled": True, "auto_record": True, "project": "PhD Research Lab", "server_enabled": False,
                "web_url": "http://localhost:8080"},
    # windows_sandbox: Codex needs a Windows sandbox backend to run shell commands; "unelevated" (restricted token, no
    # admin rights), "elevated" (stronger, needs a one-time admin setup) or "config" (use ~/.codex/config.toml as is)
    "codex": {"enabled": True, "binary": "", "sandbox": "read-only", "model": "", "timeout_s": 1800, "windows_sandbox": "unelevated"},
    "workspace": {"vscode_path": ""},
    "routing": {"online_check": True, "chains": {}, "provider_headers": {},
                "capability_aware": True, "verified_local_tasks": ["extract", "summarize", "context", "live_critic"],
                "verified_fallbacks": {}},
    "provenance": {"enabled": True, "csv_header": True},
    # v3.4 Context Gateway (provider-independent research context for ChatGPT / Claude Code / Gemini & Antigravity).
    # Sensitivity: PUBLIC always leaves, INTERNAL per allow_internal, SENSITIVE only with allow_sensitive, RESTRICTED never.
    # *_api_fallback False = the CLI connectors run with API-key variables removed, so a subscription sign-in is used
    # and no API billing is ever created implicitly (cost guard).
    "gateway": {"enabled": True, "allow_internal": True, "allow_sensitive": False, "block_source_code": True,
                "context_budget_tokens": 6000, "provider_timeout_s": 600, "codex_app_server": False, "cli_models": {},
                "codex_enabled": True, "claude_code_enabled": True, "gemini_cli_enabled": True, "antigravity_enabled": True,
                "codex_api_fallback": False, "claude_code_api_fallback": False, "antigravity_api_fallback": False,
                "gemini_cli_api_fallback": False,
                "claude_binary": "", "gemini_binary": "",
                # v4.1 Secure CLI gateway: every CLI request runs in its own session workspace under cli_space_dir
                # (empty = <data>/cli-space), never in the project or the app folder. cli_profile: review (read-only) |
                # assisted (the session workspace is writable). A profile the provider cannot enforce is refused
                # unless the researcher accepts the weaker isolation for that request.
                "cli_space_dir": "", "cli_profile": "review", "cli_retention_days": 14, "cli_max_sessions": 300},
    # v3.4 MCP gateway (POST /mcp, localhost only). token: when set, every MCP request needs "Authorization: Bearer <token>".
    # Research write tools only create review CANDIDATES (never permanent memory) unless the researcher approves them.
    "mcp": {"enabled": True, "expose_research": True, "allow_writes": True, "expose_sandbox": True, "token": "",
            "rate_limit_per_min": 240, "audit": True},
    # v4.2 AI workspace (universal chat, context firewall, hybrid control) — the GLOBAL defaults; module_defaults
    # {module: {key: value}} override them per module, a session overrides those, a turn can override once.
    # operating_mode: automation | manual. context_mode: none | selected | relevant | expanded.
    # memory_mode: off | manual | suggest | auto (restricted: only auto_memory_types are saved without review).
    # mcp_tools: the session allowlist ([] = every read-only research tool); mcp_auto: the orchestrator proposes tools.
    "aiws": {"enabled": True, "operating_mode": "automation", "provider": "app:auto", "model": "", "reasoning": "auto",
             "context_mode": "relevant", "memory_mode": "suggest", "auto_memory_types": ["open_question"],
             "mcp_auto": True, "mcp_tools": [], "security_profile": "review", "keep_history": True, "summaries": True,
             "collect_artifacts": True, "context_budget_tokens": 6000, "module_defaults": {}, "max_turn_s": 900},
}
# v5 research runs (backend/agent/runs.py) and research providers (backend/providers/research.py)
DEFAULTS["runs"] = {
    "auto_approve_risk": 1,    # runs up to this risk start without asking (0 read, 1 writes inside the project);
                               # code / experiments (risk 2) always wait for the researcher
    "max_minutes": 120.0,      # default active-time budget of one run
    "max_retries": 1,          # automatic recovery attempts (e.g. CUDA OOM → batch size ½) before asking
    "auto_recover": True,
    "web_search": True,        # /lit on the app model first retrieves real papers (OpenAlex, Semantic Scholar, arXiv)
    # hardware guard slots (execution/guard.py) — can only be lowered; gpu is never more than 1
    "slot_gpu": 1, "slot_cpu": 1, "slot_local_llm": 1, "slot_cli": 2, "slot_cloud": 3,
}
DEFAULTS["research_providers"] = {
    "feynman_enabled": True,
    "feynman_share_app_key": False,   # let Feynman use the app's Anthropic / OpenAI key (billed to that API account)
    "feynman_timeout_s": 1800,
    "coding_default": "claude_code",  # claude_code | codex | gemini_cli | antigravity | app
    "engine_mode": "auto", "engine_priority": ["feynman", "openscience", "opencode"],
}
DEFAULTS["openscience"] = {
    "enabled": False, "base_url": "http://127.0.0.1:4096", "token": "", "timeout_s": 600,
    "request_timeout_s": 3.0, "max_artifact_mb": 64, "max_artifacts": 32, "allow_execution": False,
    "policy_confirmed": False, "qualified_tasks": [], "model_provider": "", "model_id": "",
}
DEFAULTS["opencode"] = {
    "enabled": True, "base_url": "http://127.0.0.1:4097", "allow_metered_api": False,
    "timeout_s": 600, "workspace_mode": "topic_isolated",
}
# v5.1 interface language (UI strings) and AI response language
DEFAULTS["ui"] = {"language": "vi", "ai_language": "auto", "prose_font": "sans", "paper_explorer_v2": True, "discovery_inbox": True,
                  "contextual_actions": True, "topic_scheduler_ui": True}
DEFAULTS["mcp_agent"] = {"enabled": False, "url": "http://127.0.0.1:8766/mcp", "token": "",
                         "tool": "research", "models": [], "timeout_s": 120}
DEFAULTS["research_os"] = {"enabled":False,"team_enabled":False,"multi_team_enabled":False}
# v5.1 automatic venue ranking: CORE conference ranks are downloaded (refreshed after refresh_days); SCImago journal
# exports cannot be fetched automatically (bot protection), so a scimagojr*.csv saved in Downloads is imported by itself.
DEFAULTS["ranking"] = {"auto": True, "core_source": "ICORE2026", "watch_downloads": True, "refresh_days": 30}
SECTIONS_V32 = ("runs", "research_providers", "memory", "resources", "clearml", "codex", "workspace", "routing", "provenance",
                "gateway", "mcp", "lifecycle", "aiws", "ui", "ranking", "openscience", "opencode", "research_os", "mcp_agent")
LIFECYCLE_POLICIES = ("unload_after_task", "keep_loaded", "idle_unload")
SECRET_FIELDS = {"mcp": ("token",), "openscience": ("token",), "mcp_agent": ("token",)}
CHOICES = {("research_providers", "coding_default"): ("claude_code", "codex", "gemini_cli", "antigravity", "app"),
           ("research_providers", "engine_mode"): ("auto", "feynman", "openscience", "opencode", "collaborative", "phdlab"),
           ("codex", "sandbox"): ("read-only", "workspace-write"),
           ("codex", "windows_sandbox"): ("unelevated", "elevated", "config"),
           ("memory", "embed_engine"): ("auto", "ollama", "hashing"), ("gateway", "cli_profile"): ("review", "assisted"),
           ("aiws", "operating_mode"): ("automation", "manual"), ("aiws", "context_mode"): ("none", "selected", "relevant", "expanded"),
           ("aiws", "memory_mode"): ("off", "manual", "suggest", "auto"), ("aiws", "security_profile"): ("review", "assisted"),
           ("aiws", "reasoning"): ("auto", "off", "low", "medium", "high"),
           ("ui", "language"): ("vi", "en"), ("ui", "ai_language"): ("auto", "vi", "en", "bilingual"),
           ("ui", "prose_font"): (
               "sans", "serif", "source-serif", "latex", "merriweather", "lora",
               "garamond", "times", "charter", "inter", "roboto", "mono", "fira"
           ),
           **{("lifecycle", k): LIFECYCLE_POLICIES for k in ("local_background", "local_interactive", "cli", "mcp", "cloud")}}

_lock = threading.Lock()


CLI_PROVIDERS = ("codex", "claude_code", "gemini_cli", "antigravity", "chatgpt_sub")


def _valid_mode(m: str) -> bool:
    if not isinstance(m, str):
        return False
    clean = m.removeprefix("cli:").removeprefix("app:")
    return clean in ("cloud", "local", "claude", "ollama", "auto", "mcp", *CLI_PROVIDERS) or clean in PROVIDERS


def _coerce(default, val):
    """Value converted to the type of its default (bad values keep the default)."""
    try:
        if isinstance(default, bool):
            return val if isinstance(val, bool) else str(val).strip().lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            return max(0, int(float(val)))
        if isinstance(default, float):
            return max(0.0, float(val))
        if isinstance(default, dict):
            return dict(val) if isinstance(val, dict) else default
        if isinstance(default, list):
            return list(val) if isinstance(val, list) else default
        return str(val if val is not None else "").strip()[:2000]
    except (TypeError, ValueError):
        return default


def _merge_section(sec: str, target: dict, patch: dict, masked_ok: bool) -> None:
    """Update one v3.2 config section with known keys only; masked secrets ('••') leave the stored value unchanged."""
    for f, val in (patch or {}).items():
        if f not in DEFAULTS[sec]:
            continue
        if f in SECRET_FIELDS.get(sec, ()) and masked_ok and isinstance(val, str) and "•" in val:
            continue
        v = _coerce(DEFAULTS[sec][f], val)
        allowed = CHOICES.get((sec, f))
        if allowed and v not in allowed:
            v = DEFAULTS[sec][f]
        target[f] = v
    if sec == "mcp_agent":
        from backend.providers.mcp_agent import endpoint
        if target["url"] or target["enabled"]:
            endpoint(target["url"])
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", target["tool"]):
            raise ValueError("MCP inference tool must have a valid name")
        if len(target["models"]) > 500 or any(not isinstance(m, str) or not m.strip() or len(m) > 256 for m in target["models"]):
            raise ValueError("MCP catalog must contain at most 500 nonempty model IDs")
        target["models"] = list(dict.fromkeys(m.strip() for m in target["models"]))
        target["timeout_s"] = max(5, min(600, target["timeout_s"]))


def load_config() -> dict:
    cfg = deepcopy(DEFAULTS)
    saved = {}
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text("utf-8"))
            if not isinstance(saved, dict):
                raise ValueError("configuration must be an object")
        except ValueError:
            from backend.memory.store import quarantine
            quarantine(CONFIG_PATH)
            saved = {}
        except OSError:
            saved = {}
    for k in ("default_cloud", "lmstudio_base_url", "local_model", "ollama_base_url", "ollama_model",
              "references_dir", "fallback_to_cloud", "projects", "active_project", "latex_online"):
        if k in saved:
            cfg[k] = saved[k]
    for pid, p in (saved.get("providers") or {}).items():
        if pid in PROVIDERS and isinstance(p, dict):
            cfg["providers"][pid].update({f: str(p.get(f, "")) for f in ("api_key", "model", "base_url") if f in p})
    # migrate v1.0/v1.1 settings
    if saved.get("anthropic_api_key") and not cfg["providers"]["anthropic"]["api_key"]:
        cfg["providers"]["anthropic"]["api_key"] = saved["anthropic_api_key"]
    if saved.get("claude_model") and "providers" not in saved:
        cfg["providers"]["anthropic"]["model"] = saved["claude_model"]
    cfg["agent_modes"].update({a: m for a, m in (saved.get("agent_modes") or {}).items()
                               if a in AGENTS and _valid_mode(m)})
    for sec in SECTIONS_V32:
        if isinstance(saved.get(sec), dict):
            try:
                _merge_section(sec, cfg[sec], saved[sec], masked_ok=False)
            except ValueError:
                if sec != "mcp_agent":
                    raise
                cfg[sec] = deepcopy(DEFAULTS[sec])  # malformed manual config disables this optional adapter
    cfg["agent_models"].update({a: str(m) for a, m in (saved.get("agent_models") or {}).items() if a in AGENTS and m})
    cfg["search"].update({k: v for k, v in (saved.get("search") or {}).items() if k in SEARCH_DEFAULTS})
    if cfg["default_cloud"] not in PROVIDERS:
        cfg["default_cloud"] = "anthropic"
    if not (GLOBAL_DIR / META_NAME).exists():  # first run / upgrade: describe the legacy data/ folder as a project
        _ensure_project(GLOBAL_DIR, "Default project", cfg.get("references_dir") or str(DEFAULT_REFS))
    proj = active_project(cfg)
    cfg["references_dir"] = proj["references_dir"]  # what the UI shows/edits = the active project's folder
    return cfg


def _write_config(cfg: dict) -> None:
    """Replace settings atomically so interrupted writes cannot truncate credentials or project settings."""
    from backend.memory.store import replace_retry
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2), "utf-8")
    replace_retry(tmp, CONFIG_PATH)


def save_config(patch: dict) -> dict:
    with _lock:
        cfg = load_config()
        def source(a):
            mode = cfg["agent_modes"][a]
            return ("anthropic" if cfg["providers"]["anthropic"].get("api_key") else cfg["default_cloud"]) if mode == "claude" else cfg["default_cloud"] if mode == "cloud" else mode
        previous_sources = {a: source(a) for a in AGENTS}
        for k, v in sorted(patch.items(), key=lambda item: item[0] != "agent_modes"):
            if k == "agent_modes" and isinstance(v, dict):
                for a, m in v.items():
                    if a in AGENTS and _valid_mode(m) and cfg["agent_modes"].get(a) != m:
                        cfg["agent_modes"][a] = m
                        cfg["agent_models"].pop(a, None)
            elif k == "providers" and isinstance(v, dict):
                for pid, p in v.items():
                    if pid not in PROVIDERS or not isinstance(p, dict):
                        continue
                    for f in ("model", "base_url"):
                        if f in p:
                            cfg["providers"][pid][f] = str(p[f]).strip()
                    key = p.get("api_key")
                    if isinstance(key, str) and "•" not in key:  # masked value = unchanged
                        cfg["providers"][pid]["api_key"] = key.strip()
            elif k == "default_cloud":
                if v in PROVIDERS:
                    cfg[k] = v
            elif k == "references_dir":  # belongs to the active project
                proj = active_project(cfg)
                info = _ensure_project(proj["data_dir"], None, str(v).strip() or None, update_refs=True)
                cfg[k] = info["references_dir"]
            elif k in ("lmstudio_base_url", "local_model", "fallback_to_cloud", "ollama_base_url", "ollama_model"):
                cfg[k] = v
            elif k == "agent_models" and isinstance(v, dict):
                for a, m in v.items():
                    if a in AGENTS:
                        if m:
                            cfg["agent_models"][a] = str(m).strip()
                        else:
                            cfg["agent_models"].pop(a, None)
            elif k == "latex_online":
                cfg[k] = bool(v)
            elif k in SECTIONS_V32 and isinstance(v, dict):
                previous_identity = tuple(cfg[k].get(f) for f in ("base_url", "model_provider", "model_id")) if k == "openscience" else None
                _merge_section(k, cfg[k], v, masked_ok=True)
                if k == "openscience":
                    from backend.research_engines.openscience import Settings
                    if previous_identity != tuple(cfg[k].get(f) for f in ("base_url", "model_provider", "model_id")):
                        cfg[k]["qualified_tasks"] = []
                    cfg[k] = Settings.model_validate(cfg[k]).model_dump()
                if k == "memory":
                    for f in ("keep_recent_turns", "interval_s", "high_watermark_tokens", "chunk_tokens"):
                        cfg["memory"][f] = max(1, cfg["memory"][f])
            elif k == "search" and isinstance(v, dict):
                sc = cfg["search"]
                for f, val in v.items():
                    if f in SEARCH_KEYS:
                        if isinstance(val, str) and "•" not in val:  # masked value = unchanged
                            sc[f] = val.strip()
                    elif f == "web_engine":
                        sc[f] = val if val in ("duckduckgo", "tavily", "brave") else "duckduckgo"
                    elif f == "n_results":
                        try:
                            sc[f] = max(1, min(30, int(val)))
                        except (TypeError, ValueError):
                            pass
                    elif f == "read_pages":
                        sc[f] = bool(val)
                    elif f == "mailto":
                        sc[f] = str(val).strip()[:120]
        for a in AGENTS:
            if previous_sources[a] != source(a) and a not in (patch.get("agent_models") or {}):
                cfg["agent_models"].pop(a, None)
        _write_config(cfg)
        return cfg


def mask(key: str) -> str:
    return (key[:6] + "•" * 8 + key[-4:]) if len(key) > 12 else ("•" * 8 if key else "")


def public_config(cfg: dict) -> dict:
    out = deepcopy(cfg)
    for pid, p in out["providers"].items():
        p["has_key"] = bool(p.get("api_key"))
        p["api_key"] = mask(p.get("api_key", ""))
    for f in SEARCH_KEYS:
        out["search"]["has_" + f] = bool(out["search"].get(f))
        out["search"][f] = mask(out["search"].get(f, ""))
    for sec, fields in SECRET_FIELDS.items():
        for f in fields:
            out[sec]["has_" + f] = bool(out[sec].get(f))
            out[sec][f] = mask(out[sec].get(f, ""))
    out["provider_specs"] = PROVIDERS
    out["agents"] = AGENTS
    out["version"] = APP_VERSION
    out["project"] = active_project(cfg)
    return out


# ============================================================== research projects
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve(p) -> Path:
    return Path(str(p)).expanduser().resolve()


def _read_meta(d: Path) -> dict:
    try:
        return json.loads((d / META_NAME).read_text("utf-8"))
    except Exception:
        return {}


def _refs_abs(d: Path, meta: dict) -> Path:
    r = Path(meta.get("references_dir") or "references").expanduser()
    return (r if r.is_absolute() else d / r).resolve()


def _ensure_project(data_dir, name: str | None = None, references_dir: str | None = None,
                    update_refs: bool = False) -> dict:
    """Create/complete a project folder (data_dir/workspace, references, project_meta.json)."""
    d = _resolve(data_dir)
    (d / "workspace").mkdir(parents=True, exist_ok=True)
    meta = _read_meta(d)
    changed = not meta
    if name and name.strip():
        meta["name"], changed = name.strip()[:80], True
    meta.setdefault("name", d.name)
    meta.setdefault("created", _now())
    if references_dir and (update_refs or "references_dir" not in meta):
        r = _resolve(references_dir)
        try:  # store relative when inside the project, so the folder can be moved/copied as a whole
            meta["references_dir"] = str(r.relative_to(d))
        except ValueError:
            meta["references_dir"] = str(r)
        changed = True
    meta.setdefault("references_dir", "references")
    # Older default installations kept PDFs beside data/. Copy before switching the pointer; never overwrite a
    # different file or delete the original. Custom reference folders remain explicitly configurable.
    legacy = (ROOT / "references").resolve()
    if not _DATA_OVERRIDE and _refs_abs(d, meta) == legacy:
        from shutil import copy2
        target = d / "references"
        target.mkdir(parents=True, exist_ok=True)
        for source in legacy.iterdir() if legacy.is_dir() else []:
            if not source.is_file():
                continue
            dest = target / source.name
            if dest.exists() and dest.read_bytes() != source.read_bytes():
                raise ValueError(f"Library migration conflict: {dest}. Original files have been preserved.")
            if not dest.exists():
                copy2(source, dest)
        meta["references_dir"], changed = "references", True
    if changed:
        (d / META_NAME).write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")
    refs = _refs_abs(d, meta)
    refs.mkdir(parents=True, exist_ok=True)
    return {"name": meta["name"], "data_dir": str(d), "references_dir": str(refs), "created": meta["created"]}


_migration_lock = threading.RLock()


def project_info(data_dir) -> dict:
    d = _resolve(data_dir)
    meta = _read_meta(d)
    if not _DATA_OVERRIDE and _refs_abs(d, meta) == (ROOT / "references").resolve():
        with _migration_lock:
            meta = _read_meta(d)
            if _refs_abs(d, meta) == (ROOT / "references").resolve():
                _ensure_project(d)
                meta = _read_meta(d)
    return {"name": meta.get("name") or d.name, "data_dir": str(d), "references_dir": str(_refs_abs(d, meta)),
            "created": meta.get("created"), "exists": d.exists(), "is_default": d == GLOBAL_DIR.resolve()}


_project_context = ContextVar("phdlab_project", default=None)


@contextmanager
def project_scope(project_dir):
    """Bind a background task and its child threads to the project that started it."""
    token = _project_context.set(str(Path(project_dir).resolve()))
    try:
        yield
    finally:
        _project_context.reset(token)


def active_project(cfg: dict | None = None) -> dict:
    scoped = _project_context.get()
    if scoped is not None:
        return project_info(scoped)
    cfg = cfg if cfg is not None else load_config()
    dd = cfg.get("active_project") or ""
    d = _resolve(dd) if dd else GLOBAL_DIR.resolve()
    if not d.exists():
        d = GLOBAL_DIR.resolve()
    if not (d / META_NAME).exists():
        _ensure_project(d)
    return project_info(d)


def list_projects() -> list:
    cfg = load_config()
    paths = [str(GLOBAL_DIR.resolve())] + [p for p in cfg.get("projects", []) if p]
    seen, out = set(), []
    active = active_project(cfg)["data_dir"]
    for p in paths:
        r = str(_resolve(p))
        if r in seen:
            continue
        seen.add(r)
        info = project_info(r)
        info["active"] = r == active
        out.append(info)
    return out


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", name, flags=re.UNICODE).strip().replace(" ", "-")
    return s[:60] or "project"


def create_project(name: str, data_dir: str | None = None, references_dir: str | None = None) -> dict:
    """New project folder (default: <app>/projects/<name>). Existing folders are opened, not overwritten."""
    if not name or not name.strip():
        raise ValueError("Project name is required")
    d = _resolve(data_dir) if data_dir and data_dir.strip() else PROJECTS_ROOT / _slug(name)
    if d.exists() and (d / META_NAME).exists() and not data_dir:
        i = 2
        while (PROJECTS_ROOT / f"{_slug(name)}-{i}").exists():
            i += 1
        d = PROJECTS_ROOT / f"{_slug(name)}-{i}"
    info = _ensure_project(d, name, references_dir, update_refs=bool(references_dir))
    _register(info["data_dir"], activate=True)
    return info


def open_project(data_dir: str) -> dict:
    """Register (and activate) an existing project folder, e.g. one copied from another computer."""
    d = _resolve(data_dir)
    if not d.exists():
        raise FileNotFoundError(f"Folder not found: {d}")
    info = _ensure_project(d)
    _register(info["data_dir"], activate=True)
    return info


def activate_project(data_dir: str) -> dict:
    d = _resolve(data_dir)
    if not d.exists():
        raise FileNotFoundError(f"Folder not found: {d}")
    _ensure_project(d)
    _register(str(d), activate=True)
    return project_info(d)


def rename_project(data_dir: str, name: str) -> dict:
    return _ensure_project(data_dir, name)


def forget_project(data_dir: str) -> None:
    """Remove from the list only - files on disk are never deleted."""
    d = str(_resolve(data_dir))
    if d == str(GLOBAL_DIR.resolve()):
        raise ValueError("The Default project cannot be removed from the list")
    with _lock:
        cfg = load_config()
        cfg["projects"] = [p for p in cfg.get("projects", []) if str(_resolve(p)) != d]
        if cfg.get("active_project") and str(_resolve(cfg["active_project"])) == d:
            cfg["active_project"] = ""
        _write_config(cfg)


def _register(data_dir: str, activate: bool) -> None:
    with _lock:
        cfg = load_config()
        d = str(_resolve(data_dir))
        if d != str(GLOBAL_DIR.resolve()) and d not in [str(_resolve(p)) for p in cfg.get("projects", [])]:
            cfg.setdefault("projects", []).append(d)
        if activate:
            cfg["active_project"] = "" if d == str(GLOBAL_DIR.resolve()) else d
        _write_config(cfg)


# ---- paths of the ACTIVE project (resolved on every call, so switching takes effect immediately)
def data_dir() -> Path:
    return Path(active_project()["data_dir"])


def workspace() -> Path:
    w = data_dir() / "workspace"
    w.mkdir(parents=True, exist_ok=True)
    return w


def refs_dir() -> Path:
    r = Path(active_project()["references_dir"])
    r.mkdir(parents=True, exist_ok=True)
    return r
