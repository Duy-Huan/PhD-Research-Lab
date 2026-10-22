"""Explicit MCP inference-tool binding; MCP tool servers are not implicitly models.

Supported tool input: system, messages, model, max_tokens, temperature (JSON).
Only the named, schema-compatible tool is called. No tool discovery auto-execution,
credential forwarding, redirects or fallback to another paid provider.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

import httpx

LIMIT = 2 * 1024 * 1024
FIELDS = {"system", "messages", "model", "max_tokens", "temperature"}


def endpoint(value: str) -> str:
    u = urlsplit(value)
    if u.port == 0 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("MCP URL must not contain whitespace or an invalid port")
    if u.username or u.password or u.fragment or u.query or not u.hostname:
        raise ValueError("MCP URL must have a host and no credentials, query or fragment")
    if u.scheme != "https" and not (u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1")):
        raise ValueError("MCP requires HTTPS, or HTTP on loopback")
    return value


async def _complete(cfg: dict, system: str, messages: list, model: str | None,
                   max_tokens: int, temperature: float) -> str:
    from backend.providers.models import LLMError
    settings = cfg.get("mcp_agent") or {}
    if not settings.get("enabled"):
        raise LLMError("MCP inference agent is disabled; configure its endpoint and inference tool in Settings")
    try:
        url = endpoint(settings.get("url", ""))
    except ValueError as e:
        raise LLMError(str(e)) from e
    tool = settings.get("tool", "")
    headers = {"Accept": "application/json, text/event-stream"}
    if settings.get("token"):
        headers["Authorization"] = "Bearer " + settings["token"]
    timeout = max(5, min(600, int(settings.get("timeout_s") or 120)))
    seq = 0
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        async def request(method, params, notify=False):
            nonlocal seq
            seq += 1
            payload = {"jsonrpc": "2.0", "method": method, "params": params}
            if not notify:
                payload["id"] = seq
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code not in (200, 202, 204):
                    raise LLMError(f"MCP request failed (HTTP {response.status_code}); verify endpoint and authentication")
                if session := response.headers.get("mcp-session-id"):
                    headers["Mcp-Session-Id"] = session
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > LIMIT:
                        raise LLMError("MCP response exceeded 2 MiB")
                    if not notify and "text/event-stream" in response.headers.get("content-type", ""):
                        # Stop after our correlated reply; long-lived SSE need not close.
                        for event in bytes(raw).replace(b"\r\n", b"\n").split(b"\n\n")[:-1]:
                            event = event.decode("utf-8")
                            data = "\n".join(line[5:].lstrip() for line in event.splitlines() if line.startswith("data:"))
                            if data:
                                result = json.loads(data)
                                if result.get("id") == seq:
                                    return unpack(result, seq)
                if notify:
                    return {}
                return unpack(json.loads(raw), seq)

        def unpack(result, rid):
            if not isinstance(result, dict) or result.get("id") != rid or "error" in result:
                raise LLMError("MCP returned an error or an uncorrelated response")
            value = result.get("result")
            if not isinstance(value, dict):
                raise LLMError("MCP result must be an object")
            return value

        try:
            init = await request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                                 "clientInfo": {"name": "phdlab-inference", "version": "1"}})
            version = init.get("protocolVersion")
            if version not in ("2024-11-05", "2025-03-26", "2025-06-18"):
                raise LLMError("Unsupported MCP protocol version")
            headers["MCP-Protocol-Version"] = version
            await request("notifications/initialized", {}, notify=True)
            catalog, cursor, seen, found = {}, None, set(), None
            for _ in range(10):
                catalog = await request("tools/list", {"cursor": cursor} if cursor else {})
                found = next((t for t in catalog.get("tools", []) if t.get("name") == tool), None)
                if found:
                    break
                cursor = catalog.get("nextCursor")
                if not cursor or cursor in seen:
                    break
                seen.add(cursor)
            schema = (found or {}).get("inputSchema") or {}
            properties = schema.get("properties") or {}
            if not found or schema.get("type") != "object" or not {"system", "messages"} <= properties.keys() or \
                    properties["system"].get("type") != "string" or properties["messages"].get("type") != "array" or \
                    not set(schema.get("required") or []) <= FIELDS:
                raise LLMError("Selected MCP tool is not a compatible inference tool (requires system and messages inputs)")
            args = {"system": system, "messages": messages, "model": model or "",
                    "max_tokens": max_tokens, "temperature": temperature}
            if model and "model" not in properties:
                raise LLMError("Selected MCP tool cannot accept a model override")
            result = await request("tools/call", {"name": tool, "arguments": {k: v for k, v in args.items() if k in properties}})
            if result.get("isError"):
                raise LLMError("MCP inference tool reported failure; inspect its server logs")
            text = "\n".join(c["text"] for c in result.get("content", []) if c.get("type") == "text" and isinstance(c.get("text"), str))
            if not text.strip():
                raise LLMError("MCP inference tool returned no text")
            return text
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as e:
            # Never include URL tokens, request arguments or response bodies in public errors.
            raise LLMError("MCP transport/protocol failed; verify the configured server and inference tool") from e


async def complete(cfg: dict, system: str, messages: list, model: str | None,
                   max_tokens: int, temperature: float) -> str:
    import asyncio
    from backend.providers.models import LLMError
    timeout = max(5, min(600, int((cfg.get("mcp_agent") or {}).get("timeout_s") or 120)))
    try:
        async with asyncio.timeout(timeout):
            return await _complete(cfg, system, messages, model, max_tokens, temperature)
    except TimeoutError as e:
        raise LLMError("MCP inference exceeded its time budget") from e
