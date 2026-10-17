"""Configuration storage for the PhD Interactive Autonomous Research Lab.

Global settings (API keys, providers, agent engines) are persisted in data/config.json.
Each research PROJECT has its own data folder (workspace, chats, library, outputs) and its
own references folder, so one installation can switch between several research projects.
Each API key is only ever sent to its own provider's API endpoint.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path

APP_VERSION = "2.6.2"

ROOT = Path(__file__).resolve().parent.parent
GLOBAL_DIR = ROOT / "data"                 # global config + the "Default project" (backward compatible)
CONFIG_PATH = GLOBAL_DIR / "config.json"
PROJECTS_ROOT = ROOT / "projects"          # default parent folder for new projects
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
    "chat_lit2plan":   {"label": "💬 Chat · Tool 1 Lit2Plan", "default": "cloud"},
    "chat_experiment": {"label": "💬 Chat · Tool 2 Experiment", "default": "cloud"},
    "chat_paper":      {"label": "💬 Chat · Tool 3 Paper", "default": "cloud"},
    "chat_masterclass": {"label": "💬 Chat · Tool 4 Masterclass", "default": "cloud"},
    # v2.5 external paper review flow — Claude preferred ("claude" = Anthropic if it has a key, else the default cloud)
    "ext_reviewer":    {"label": "📝 Review · Reviewers R1-R3", "default": "claude"},
    "ext_meta":        {"label": "📝 Review · Area Chair / Editor", "default": "claude"},
    "ext_fixer":       {"label": "📝 Review · Quick-fix editor", "default": "claude"},
    "chat_review":     {"label": "💬 Chat · Paper Review", "default": "claude"},
    # v2.6 internet search
    "web_query":       {"label": "🌐 Search query planner", "default": "cloud"},
}

SEARCH_DEFAULTS = {
    "web_engine": "duckduckgo",   # duckduckgo (free, no key) | tavily | brave
    "tavily_key": "", "brave_key": "",
    "s2_key": "",                 # Semantic Scholar API key (optional, higher rate limit)
    "mailto": "",                 # e-mail for the OpenAlex "polite pool" (optional, faster)
    "n_results": 8,               # results per search
    "read_pages": True,           # read the text of the top web pages (more accurate, slower)
}
SEARCH_KEYS = ("tavily_key", "brave_key", "s2_key")

DEFAULTS = {
    "providers": {pid: {"api_key": "", "model": spec["model"], "base_url": ""} for pid, spec in PROVIDERS.items()},
    "default_cloud": "anthropic",
    "lmstudio_base_url": "http://localhost:1234/v1",
    "local_model": "",
    "references_dir": str(ROOT / "references"),  # legacy (v1.0-1.5): becomes the Default project's references
    "projects": [],          # registered project data folders
    "active_project": "",    # data folder of the active project ("" = Default project in data/)
    "fallback_to_cloud": True,
    "chat_restore": True,  # reopen the last chat session on start
    "output_lang": "ui",   # Tools 1/2/4 output language: ui | en | vi
    "agent_modes": {k: v["default"] for k, v in AGENTS.items()},
    "search": dict(SEARCH_DEFAULTS),
}

_lock = threading.Lock()


def _valid_mode(m: str) -> bool:
    return m in ("cloud", "local", "claude") or m in PROVIDERS


def load_config() -> dict:
    cfg = deepcopy(DEFAULTS)
    saved = {}
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text("utf-8"))
        except Exception:
            saved = {}
    for k in ("default_cloud", "lmstudio_base_url", "local_model", "references_dir", "fallback_to_cloud", "chat_restore",
              "projects", "active_project", "output_lang"):
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
    cfg["search"].update({k: v for k, v in (saved.get("search") or {}).items() if k in SEARCH_DEFAULTS})
    if cfg["default_cloud"] not in PROVIDERS:
        cfg["default_cloud"] = "anthropic"
    if not (GLOBAL_DIR / META_NAME).exists():  # first run / upgrade: describe the legacy data/ folder as a project
        _ensure_project(GLOBAL_DIR, "Default project", cfg.get("references_dir") or str(ROOT / "references"))
    proj = active_project(cfg)
    cfg["references_dir"] = proj["references_dir"]  # what the UI shows/edits = the active project's folder
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
            elif k == "references_dir":  # belongs to the active project
                proj = active_project(cfg)
                info = _ensure_project(proj["data_dir"], None, str(v).strip() or None, update_refs=True)
                cfg[k] = info["references_dir"]
            elif k in ("lmstudio_base_url", "local_model", "fallback_to_cloud"):
                cfg[k] = v
            elif k == "chat_restore":
                cfg[k] = bool(v)
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
                            sc[f] = max(3, min(20, int(val)))
                        except (TypeError, ValueError):
                            pass
                    elif f == "read_pages":
                        sc[f] = bool(val)
                    elif f == "mailto":
                        sc[f] = str(val).strip()[:120]
            elif k == "output_lang":
                cfg[k] = v if v in ("ui", "en", "vi") else "ui"
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), "utf-8")
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
    if changed:
        (d / META_NAME).write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")
    refs = _refs_abs(d, meta)
    refs.mkdir(parents=True, exist_ok=True)
    return {"name": meta["name"], "data_dir": str(d), "references_dir": str(refs), "created": meta["created"]}


def project_info(data_dir) -> dict:
    d = _resolve(data_dir)
    meta = _read_meta(d)
    return {"name": meta.get("name") or d.name, "data_dir": str(d), "references_dir": str(_refs_abs(d, meta)),
            "created": meta.get("created"), "exists": d.exists(), "is_default": d == GLOBAL_DIR.resolve()}


def active_project(cfg: dict | None = None) -> dict:
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
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), "utf-8")


def _register(data_dir: str, activate: bool) -> None:
    with _lock:
        cfg = load_config()
        d = str(_resolve(data_dir))
        if d != str(GLOBAL_DIR.resolve()) and d not in [str(_resolve(p)) for p in cfg.get("projects", [])]:
            cfg.setdefault("projects", []).append(d)
        if activate:
            cfg["active_project"] = "" if d == str(GLOBAL_DIR.resolve()) else d
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), "utf-8")


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
