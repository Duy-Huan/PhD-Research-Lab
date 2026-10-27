"""Provider failover for model-driven agent loops (owner-approved option 2, 2026-10-27).

An owner-configured, ordered pool of DIFFERENT providers, one account each (e.g. Claude Code CLI -> Codex CLI ->
Gemini API key -> local spark). When the active provider reports quota/rate-limit exhaustion, the same agent loop
continues on the next provider with the identical conversation, jobs and provenance. Rules:

  * different providers only: a provider may appear once, so the pool cannot rotate several accounts of one service;
  * Antigravity cannot be a member: its terms forbid third-party software driving it (use it interactively as an MCP
    client of PhD Lab instead);
  * only an error classified as quota/rate-limit switches providers; any other failure is returned to the loop as is;
  * an exhausted provider rests for `cooldown_s` before it may be used again;
  * every model call is attributed (provider, model, outcome) so mixed-model results stay transparent;
  * when every member is exhausted the call raises ToolError(unavailable) -- the run ends BLOCKED, never "completed".
"""
from __future__ import annotations

import re
import time
from typing import Callable

from backend.tools.spec import ToolError

QUOTA = re.compile(r"(?i)usage limit|quota|rate[ -]?limit|too many requests|\b429\b|resource[_ ]exhausted|"
                   r"insufficient[_ ]quota|weekly limit|limit reached|hit your .{0,20}limit|credit balance is too low")
FORBIDDEN = {"cli:antigravity": "Antigravity terms forbid third-party software driving it; use it as an MCP client instead"}
REST: dict[str, float] = {}  # provider -> monotonic time until which it is known to be exhausted (shared across runs)


def normalize(members: list) -> list[dict]:
    out, seen = [], set()
    for m in members or []:
        m = {"provider": m} if isinstance(m, str) else dict(m)
        pid = str(m.get("provider", "")).strip()
        if not re.fullmatch(r"(app|cli):[a-z_]{2,40}", pid):
            raise ValueError(f"Invalid pool provider {pid!r} (use app:<id> or cli:<id>)")
        if pid in FORBIDDEN:
            raise ValueError(FORBIDDEN[pid])
        if pid in seen:
            raise ValueError(f"{pid} appears twice: the pool rotates between providers, never between accounts")
        seen.add(pid)
        out.append({"provider": pid, "model": str(m.get("model") or "")[:120]})
    return out


def is_quota(error: BaseException) -> bool:
    return bool(QUOTA.search(str(error)))


class ProviderPool:
    def __init__(self, members: list, call: Callable[[dict, str, list], str], *, cooldown_s: float = 3600,
                 clock: Callable[[], float] = time.monotonic, rest_until: dict | None = None):
        self.members = normalize(members)
        if not self.members:
            raise ValueError("A provider pool needs at least one provider")
        self.call, self.cooldown_s, self.clock = call, cooldown_s, clock
        self.rest_until = REST if rest_until is None else rest_until
        self.active = 0
        self.history: list[dict] = []

    def available(self) -> list[dict]:
        now = self.clock()
        return [m for m in self.members if self.rest_until.get(m["provider"], 0) <= now]

    def current(self) -> dict:
        return self.members[self.active]

    def complete(self, system: str, messages: list) -> str:
        """Model call for agent_loop.run: fail over on quota exhaustion, propagate every other error."""
        for _ in range(len(self.members)):
            member = self.members[self.active]
            if self.rest_until.get(member["provider"], 0) > self.clock():
                self.active = (self.active + 1) % len(self.members)
                continue
            started = self.clock()
            try:
                reply = self.call(member, system, messages)
            except Exception as e:
                if not is_quota(e):
                    self.history.append({**member, "outcome": "error", "error": str(e)[:300]})
                    raise
                self.rest_until[member["provider"]] = self.clock() + self.cooldown_s
                self.history.append({**member, "outcome": "quota", "error": str(e)[:300]})
                self.active = (self.active + 1) % len(self.members)
                continue
            self.history.append({**member, "outcome": "ok", "seconds": round(self.clock() - started, 2)})
            return reply
        raise ToolError("unavailable", "Every provider in the pool is exhausted (quota/rate limit)",
                        hint="Wait for a provider's quota to reset, or continue interactively (e.g. Antigravity as MCP client)")

    def summary(self) -> dict:
        used = [h for h in self.history if h["outcome"] == "ok"]
        return {"members": self.members, "calls": self.history,
                "providers_used": sorted({h["provider"] for h in used}), "mixed_models": len({(h["provider"], h["model"]) for h in used}) > 1}


def default_call(cfg: dict, max_tokens: int = 6000) -> Callable[[dict, str, list], str]:
    """Call one member through the application's existing provider paths (installed CLIs via the project gateway,
    app engines/cloud providers via their configured credentials). Nothing new is authenticated here."""
    import asyncio
    from backend.providers import models

    def call(member: dict, system: str, messages: list) -> str:
        kind, pid = member["provider"].split(":", 1)
        model = member["model"] or None

        async def run():
            if kind == "cli":
                return "".join([c async for c in models._stream_cli(cfg, pid, system, messages, model)])
            if pid in ("local", "ollama"):
                return await models.local_chat(cfg, system, messages, max_tokens, 0.2, pid, model, "interactive")
            return await models.cloud_chat(cfg, pid, system, messages, max_tokens, 0.2, model)
        return models.strip_think(asyncio.run(run()))
    return call
