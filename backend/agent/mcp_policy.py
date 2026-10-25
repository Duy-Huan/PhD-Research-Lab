"""Per-session MCP policy (Firewall spec §6.4, M6): which research tools a session may use, who selects them, and
an enforcement point the model cannot talk its way around.

  allowlist   session setting `mcp_tools`: [] = every READ tool (default), ["-"] = no tools, or explicit names.
              Write / sandbox tools are only usable when listed explicitly AND each call is approved.
  auto        `mcp_auto` (automation mode): the orchestrator proposes read tools from the question (deterministic
              rules below) — proposals are filtered by the allowlist and the approval rule; manual mode never
              auto-selects.
  grants      every CLI turn and every CLI step of a research run gets an EPHEMERAL MCP token bound to the allowed
              tools (Claude Code: --mcp-config; Codex: -c mcp_servers…; Gemini / Antigravity: workspace settings —
              providers/firewall.py); /mcp lists and executes only those tools for that token. Tool names asked for
              in a prompt or a paper can never widen a grant: grants come from stored settings only.
"""
from __future__ import annotations

import re
import secrets
import threading
import time

_grants: dict = {}
_lock = threading.Lock()
RISK = {"read": 0, "write": 1}
SANDBOX_RISK = {"sandbox_run_code": 2, "sandbox_manage_files": 2, "sandbox_get_metrics": 0}
ID_PAT = {"research_get_hypothesis": r"HYPE-\d{3,6}", "research_get_experiment": r"EXP-\d{3,6}",
          "research_get_provenance": r"(?:HYPE|EXP|FAIL|CLM|EVID)-\d{3,6}"}
RULES = (  # (tool, pattern, args builder) — first matching rules win, at most 3 tools per turn
    ("research_get_experiment", None, "id"),
    ("research_get_hypothesis", None, "id"),
    ("research_get_failures", r"(?i)\b(fail|failure|oom|crash|diverg|nan)\w*|lỗi|thất bại", "query"),
    ("research_get_decisions", r"(?i)\bdecision|decided|chose|quyết định", "none"),
    ("research_get_evidence", r"(?i)\bevidence|claim|support|refut|bằng chứng|chứng cứ", "query"),
    ("research_analyze_image", r"(?i)\b(image|picture|figure|plot|chart|diagram|photo|screenshot|đồ thị|hình ảnh|ảnh|sơ đồ)\b", "image"),
    ("web_search", r"(?i)internet|\bweb\b|google|trên mạng|mới nhất|gần đây|latest|recent|news|tin tức", "query"),
)


def catalog() -> list:
    from backend.providers.mcp_tools import TOOLS
    from backend.providers.mcp_server import TOOLS as SB
    out = [{"name": t["name"], "group": t["group"], "risk": RISK[t["group"]], "description": t["description"],
            "mutates": t["group"] == "write"} for t in TOOLS]
    out += [{"name": t["name"], "group": "sandbox", "risk": SANDBOX_RISK.get(t["name"], 2), "description": t["description"],
             "mutates": t["name"] != "sandbox_get_metrics"} for t in SB]
    return out


def _by_name() -> dict:
    return {t["name"]: t for t in catalog()}


def allowed(settings_value: list) -> list:
    """Effective allowlist from the session setting, minus tools switched off in the MCP configuration."""
    from backend.core.config import load_config
    m = load_config()["mcp"]
    cat = catalog()
    if settings_value == ["-"]:
        names = []
    elif not settings_value:
        names = [t["name"] for t in cat if t["group"] == "read"]
    else:
        names = [n for n in settings_value if n != "-"]
    off = set()
    if not m.get("enabled", True):
        off = {t["name"] for t in cat}
    if not m.get("expose_research", True):
        off |= {t["name"] for t in cat if t["group"] in ("read", "write")}
    if not m.get("allow_writes", True):
        off |= {t["name"] for t in cat if t["group"] == "write"}
    if not m.get("expose_sandbox", True):
        off |= {t["name"] for t in cat if t["group"] == "sandbox"}
    return [n for n in names if n not in off]


def propose(question: str, allow: list) -> list:
    """Deterministic auto-selection of READ tools for a question (filtered by the allowlist)."""
    q = question or ""
    if re.search(r"(?i)\b(?:do not|don't|never)\s+use\s+(?:any\s+)?tools?\b|\bno tools\b|không\s+(?:dùng|sử dụng)\s+công cụ", q):
        return []
    out = []
    for tool, pat, kind in RULES:
        if tool not in allow:
            continue
        if kind == "id":
            m = re.search(ID_PAT[tool], q)
            if m:
                out.append({"tool": tool, "args": {"id": m.group(0)}, "reason": f"the question names {m.group(0)}"})
        elif kind == "image" and re.search(pat, q):
            m = re.search(r"\batt:([a-f0-9]{12})\b|\b([a-f0-9]{12})\b", q)
            att_id = (m.group(1) or m.group(2)) if m else ""
            if att_id:
                out.append({"tool": tool, "args": {"attachment_id": att_id, "focus": q[:200]}, "reason": f"the question refers to image {att_id}"})
        elif re.search(pat, q):
            args = {"query": q[:280 if tool == "web_search" else 500]} if kind == "query" else {}
            out.append({"tool": tool, "args": args, "reason": "keywords in the question"})
    if not out and q.strip() and "research_search_memory" in allow:
        out.append({"tool": "research_search_memory", "args": {"query": q[:500], "k": 8}, "reason": "general research question"})
    return out[:3]


def risk(tool: str) -> int:
    t = _by_name().get(tool)
    return t["risk"] if t else 3


def execute(tool: str, args: dict, session_id: str = "") -> dict:
    from backend.providers.mcp_server import call_tool
    res = call_tool(tool, args or {}, {"name": "phdlab-ai-workspace", "session": session_id})
    text = "\n".join(c.get("text", "") for c in res.get("content") or [] if c.get("type") == "text")
    return {"text": text[:20000], "structured": res.get("structuredContent")}


# ------------------------------------------------------------------ ephemeral grants
def grant_for_cli(key: str, ttl_s: int = 3600) -> dict:
    """An MCP grant for a CLI agent outside a chat session (research-run steps): every READ tool, nothing else."""
    import os
    tools = [t["name"] for t in catalog() if t["group"] == "read"]
    base = (os.environ.get("PHDLAB_URL") or "http://127.0.0.1:8765").rstrip("/")
    return {"mcp_url": base + "/mcp", "mcp_token": issue(key, tools, ttl_s), "mcp_tools": tools}


def issue(session_id: str, tools: list, ttl_s: int = 1800) -> str:
    from backend.core.config import data_dir
    tok = "phg_" + secrets.token_urlsafe(24)
    with _lock:
        now = time.time()
        for k in [k for k, g in _grants.items() if g["expires"] < now]:
            _grants.pop(k)
        _grants[tok] = {"session_id": session_id, "tools": sorted(set(tools)), "expires": now + ttl_s,
                        "project": str(data_dir().resolve())}
    return tok


def lookup(token: str) -> dict | None:
    from backend.core.config import data_dir
    with _lock:
        g = _grants.get(token or "")
    if g and g["expires"] >= time.time() and g.get('project') == str(data_dir().resolve()):
        return g
    return None


def revoke(token: str) -> None:
    with _lock:
        _grants.pop(token or "", None)
