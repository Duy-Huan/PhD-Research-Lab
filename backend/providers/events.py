"""Provider stream normalisation (v3.4 §14): ProviderEvent (vendor JSONL) → InternalEvent → SSE → UI.

InternalEvent types: request_started, text_delta, tool_call, tool_result, status, error, request_completed,
request_cancelled. The UI and the rest of the backend only ever see these; vendor formats stay inside this module.

Vendor formats (verified against the official docs, see docs/integrations/provider-architecture.md):
  codex   `codex exec --json`            thread.started{thread_id} · item.started/item.completed{item{type,text,command}}
                                          · turn.completed{usage} · turn.failed / error
  claude  `claude -p --output-format stream-json --verbose --include-partial-messages`
          system{subtype:init,session_id} · stream_event{event.delta.text_delta} · assistant{message.content[]}
          · user{tool_result} · result{subtype,is_error,result,session_id,usage,total_cost_usd} · system{subtype:api_retry}
  agy     `agy -p --output-format stream-json` (Antigravity CLI)
          {event:init,conversation_id} · {event:step_update, step_update{text_delta, step_type, tool_info}}
          · {event:result, result{status, response, error, usage}}
  gemini  `gemini -p --output-format stream-json` (Gemini CLI)   init · message · tool_use · tool_result · error · result
Unknown events are reported as `status` with the raw type only (never dropped silently, never guessed).
"""
from __future__ import annotations

import time

TYPES = ("request_started", "text_delta", "tool_call", "tool_result", "status", "error", "request_completed",
         "request_cancelled")


def ev(type_: str, **data) -> dict:
    if type_ not in TYPES:
        raise ValueError(f"unknown internal event {type_}")
    return {"type": type_, "ts": round(time.time(), 3), **{k: v for k, v in data.items() if v not in (None, "")}}


def _clip(v, n: int = 2000):
    s = v if isinstance(v, str) else str(v)
    return s[:n]


def _args(v) -> str:
    """Tool arguments as text — what the firewall audits (paths a CLI agent wants to touch)."""
    if not v:
        return ""
    import json
    return _clip(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False), 2000)


def codex(e: dict) -> list:
    t = e.get("type", "")
    item = e.get("item") or {}
    if t == "thread.started":
        return [ev("status", state="session", session_id=e.get("thread_id", ""))]
    if t == "item.completed" and item.get("type") == "agent_message":
        return [ev("text_delta", text=item.get("text", ""), final=True)]
    if t == "item.started" and item.get("type") in ("command_execution", "mcp_tool_call"):
        return [ev("tool_call", name=item.get("type"),
                   detail=_clip(item.get("command") or item.get("tool") or "", 300) + " " + _args(item.get("arguments")))]
    if t == "item.completed" and item.get("type") in ("command_execution", "mcp_tool_call"):
        return [ev("tool_result", name=item.get("type"), status=item.get("status", ""))]
    if t == "turn.completed":
        return [ev("status", state="usage", usage=e.get("usage") or {})]
    if t in ("turn.failed", "error"):
        err = e.get("error")
        return [ev("error", message=_clip(e.get("message") or (err.get("message") if isinstance(err, dict) else err) or t, 500))]
    return [ev("status", state="event", raw_type=t)] if t else []


def claude(e: dict) -> list:
    t = e.get("type", "")
    if t == "system":
        st = e.get("subtype", "")
        if st == "init":
            return [ev("status", state="session", session_id=e.get("session_id", ""), model=e.get("model", ""))]
        if st == "api_retry":
            return [ev("status", state="retry", attempt=e.get("attempt"), error=e.get("error", ""))]
        return [ev("status", state="system", raw_type=st)]
    if t == "stream_event":
        d = (e.get("event") or {}).get("delta") or {}
        if d.get("type") == "text_delta":
            return [ev("text_delta", text=d.get("text", ""))]
        return []
    if t == "assistant":
        out = []
        for b in (e.get("message") or {}).get("content") or []:
            if b.get("type") == "tool_use":
                out.append(ev("tool_call", name=b.get("name", ""), call_id=b.get("id", ""), detail=_args(b.get("input"))))
        return out
    if t == "user":
        out = []
        for b in (e.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                out.append(ev("tool_result", call_id=b.get("tool_use_id", ""), is_error=bool(b.get("is_error"))))
        return out
    if t == "result":
        if e.get("is_error") or (e.get("subtype") not in (None, "success")):
            return [ev("error", message=_clip(e.get("result") or e.get("subtype") or "error", 500))]
        return [ev("status", state="result", final_text=e.get("result", ""), usage=e.get("usage") or {},
                   session_id=e.get("session_id", ""))]
    return [ev("status", state="event", raw_type=t)] if t else []


def agy(e: dict) -> list:
    t = e.get("event", "")
    if t == "init":
        return [ev("status", state="session", session_id=e.get("conversation_id", ""))]
    if t == "step_update":
        s = e.get("step_update") or {}
        if s.get("text_delta"):
            return [ev("text_delta", text=s["text_delta"])]
        if s.get("step_type") == "tool":
            ti = s.get("tool_info") or {}
            if s.get("state") == "DONE":
                return [ev("tool_result", name=s.get("tool_name", ""), is_error=bool(ti.get("error")))]
            return [ev("tool_call", name=s.get("tool_name", ""), detail=_args(ti.get("args") or ti.get("input")))]
        return []
    if t == "result":
        r = e.get("result") or {}
        if r.get("status") != "SUCCESS":
            err = r.get("error")
            return [ev("error", message=_clip((err.get("message") if isinstance(err, dict) else err) or r.get("status", "ERROR"), 500))]
        return [ev("status", state="result", final_text=r.get("response", ""), usage=r.get("usage") or {},
                   session_id=r.get("conversation_id", ""))]
    return [ev("status", state="event", raw_type=t)] if t else []


def gemini(e: dict) -> list:
    t = e.get("type", "")
    if t == "init":
        return [ev("status", state="session", session_id=e.get("session_id", ""), model=e.get("model", ""))]
    if t == "message":
        if e.get("role") in (None, "assistant", "model"):
            txt = e.get("content") if isinstance(e.get("content"), str) else e.get("text", "")
            return [ev("text_delta", text=txt or "")] if txt else []
        return []
    if t == "tool_use":
        return [ev("tool_call", name=e.get("tool_name") or e.get("name", ""), detail=_args(e.get("parameters") or e.get("args")))]
    if t == "tool_result":
        return [ev("tool_result", name=e.get("tool_name") or e.get("name", ""), status=e.get("status", ""))]
    if t == "error":
        return [ev("error", message=_clip(e.get("message") or "error", 500))]
    if t == "result":
        if e.get("status") not in (None, "success"):
            return [ev("error", message=_clip(e.get("error") or e.get("status"), 500))]
        return [ev("status", state="result", final_text=e.get("response", ""), usage=e.get("stats") or {})]
    return [ev("status", state="event", raw_type=t)] if t else []


NORMALIZERS = {"codex": codex, "claude": claude, "agy": agy, "gemini": gemini}
