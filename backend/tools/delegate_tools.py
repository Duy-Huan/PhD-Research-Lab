"""CLI coding agents as delegate tools (v6.6.2): `delegate.codex`, `delegate.claude_code`.

An agent hands a bounded coding sub-task to a CLI agent the researcher installed and signed in to. The call reuses the
existing durable gateway path (research.run_coding): isolated session workspace, scoped short-lived MCP grant, the
gateway request record, and only files actually written are returned (copied into the project under
delegations/<job>). Antigravity and Gemini CLI are excluded: their terms forbid third-party software driving them.
"""
from __future__ import annotations

from backend.tools.spec import ToolError, ToolSpec

DELEGATES = {"codex": "OpenAI Codex CLI (ChatGPT plan sign-in)", "claude_code": "Claude Code CLI"}
PREFIX = "delegate."


def specs() -> list[ToolSpec]:
    return [ToolSpec(
        id=PREFIX + pid, version="1.0.0", kind="native", source="builtin",
        description=f"Delegate a coding sub-task to {label}; returns its answer and the files it actually wrote",
        capabilities=["delegate", "code", "agent", pid], permissions=["compute", "workspace_write"],
        mutates=True, idempotent=False, budget={"timeout_s": 1800},
        input_schema={"type": "object", "required": ["task"], "properties": {
            "task": {"type": "string", "minLength": 1, "maxLength": 20000},
            "context": {"type": "string", "maxLength": 40000}}},
        execution={"callable": "backend.tools.delegate_tools:run", "probe": "backend.tools.delegate_tools:probe",
                   "pass_spec": True})
        for pid, label in DELEGATES.items()]


def _health(pid: str) -> dict:
    from backend.providers import cli
    return cli.get(pid).health()


def probe(spec) -> dict:
    pid = spec.id[len(PREFIX):]
    h = _health(pid)
    ready = h.get("state") in ("CONNECTED", "READY")
    return {"available": ready, "reason": "" if ready else f"{pid}: {h.get('state')} - {h.get('detail', '')}"[:300]}


def run(args: dict, ctx, spec) -> dict:
    from backend.core.config import data_dir
    from backend.providers import research
    pid = spec.id[len(PREFIX):]
    if pid not in DELEGATES:
        raise ToolError("permission_denied", f"{pid} cannot be driven by PhD Lab")
    rel = f"delegations/{ctx.job_id}"
    try:
        out = research.run_coding("delegate:" + ctx.job_id, pid, str(args["task"]), str(args.get("context") or ""),
                                  data_dir() / rel, cancelled=ctx.cancelled.is_set)
    except research.ProviderUnavailable as e:
        raise ToolError("unavailable", str(e)[:600], retryable=False,
                        hint="Check the CLI sign-in in Settings, or choose another tool") from e
    return {"answer": out["text"], "files": out["files"], "output_dir": rel,
            "gateway_request_id": out["gateway_request_id"], "provider": pid}
