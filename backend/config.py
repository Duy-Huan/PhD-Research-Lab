"""Configuration storage for the PhD Interactive Autonomous Research Lab.

Settings are persisted locally in data/config.json. Each API key is only ever sent to
its own provider's API endpoint.
"""
import json
import threading
from copy import deepcopy
from pathlib import Path

APP_VERSION = "1.2.0"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WORKSPACE = DATA_DIR / "workspace"
CONFIG_PATH = DATA_DIR / "config.json"
for _d in (DATA_DIR, WORKSPACE):
    _d.mkdir(parents=True, exist_ok=True)

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
    "custom":     {"label": "Custom (OpenAI-compatible)", "kind": "openai", "base_url": "",
                   "model": "", "key_url": "", "models": []},
}

# Agent registry. Engine value per agent: "cloud" (= default cloud provider), "local", or a provider id.
AGENTS = {
    "query_expansion": {"label": "Query Expansion (Tool 1)", "default": "local"},
    "lit2plan":        {"label": "Lit2Plan Architect (Tool 1)", "default": "cloud"},
    "experiment":      {"label": "Experimental Design (Tool 2)", "default": "cloud"},
    "pdf_parser":      {"label": "PDF Metadata Parser (Tool 3)", "default": "local"},
    "data_extractor":  {"label": "Data Extractor / Chat (Tool 3)", "default": "local"},
    "bib_extractor":   {"label": "3.1 BibTeX Extractor", "default": "local"},
    "author":          {"label": "3.2 Academic Author", "default": "cloud"},
    "reviewer":        {"label": "3.3 Peer Reviewer", "default": "cloud"},
    "editor":          {"label": "3.4 Revision Editor", "default": "cloud"},
    "masterclass":     {"label": "Masterclass Guide (Tool 4)", "default": "cloud"},
}

DEFAULTS = {
    "providers": {pid: {"api_key": "", "model": spec["model"], "base_url": ""} for pid, spec in PROVIDERS.items()},
    "default_cloud": "anthropic",
    "lmstudio_base_url": "http://localhost:1234/v1",
    "local_model": "",
    "references_dir": str(ROOT / "references"),
    "fallback_to_cloud": True,
    "agent_modes": {k: v["default"] for k, v in AGENTS.items()},
}

_lock = threading.Lock()


def _valid_mode(m: str) -> bool:
    return m in ("cloud", "local") or m in PROVIDERS


def load_config() -> dict:
    cfg = deepcopy(DEFAULTS)
    saved = {}
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text("utf-8"))
        except Exception:
            saved = {}
    for k in ("default_cloud", "lmstudio_base_url", "local_model", "references_dir", "fallback_to_cloud"):
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
    if cfg["default_cloud"] not in PROVIDERS:
        cfg["default_cloud"] = "anthropic"
    Path(cfg["references_dir"]).mkdir(parents=True, exist_ok=True)
    return cfg


def save_config(patch: dict) -> dict:
    with _lock:
        cfg = load_config()
        for k, v in patch.items():
            if k == "agent_modes" and isinstance(v, dict):
                cfg["agent_modes"].update({a: m for a, m in v.items() if a in AGENTS and _valid_mode(m)})
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
            elif k == "references_dir":
                p = Path(str(v).strip()).expanduser()
                p.mkdir(parents=True, exist_ok=True)
                cfg[k] = str(p.resolve())
            elif k in ("lmstudio_base_url", "local_model", "fallback_to_cloud"):
                cfg[k] = v
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), "utf-8")
        return cfg


def mask(key: str) -> str:
    return (key[:6] + "•" * 8 + key[-4:]) if len(key) > 12 else ("•" * 8 if key else "")


def public_config(cfg: dict) -> dict:
    out = deepcopy(cfg)
    for pid, p in out["providers"].items():
        p["has_key"] = bool(p.get("api_key"))
        p["api_key"] = mask(p.get("api_key", ""))
    out["provider_specs"] = PROVIDERS
    out["agents"] = AGENTS
    out["version"] = APP_VERSION
    return out


def refs_dir() -> Path:
    return Path(load_config()["references_dir"])
