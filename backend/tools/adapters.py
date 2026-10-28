"""Execution adapters behind the unified tool runtime: native, python, cli, mcp and container.

Every adapter has the same contract:
    probe(spec)                -> {"available": bool, "reason": str}   (cheap runtime availability detection)
    execute(spec, args, ctx)   -> dict                                 (raises ToolError on any failure)

`ctx` (runtime.ExecContext) carries the per-job working directory, deadline, cancellation event, output bound and an
`observe(kind, text)` callback that streams observations while the tool runs. Process-based adapters start tools with an
allowlisted environment (no provider/GitHub credentials), `python -I`, no shell, a private working directory and kill
the whole owned process tree on timeout/cancel. Containers run without network unless the spec declares the `network`
permission. These are defense-in-depth controls, not a certified OS sandbox.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from backend.tools.spec import ToolError, ToolSpec

ENV_ALLOW = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "LANG", "LC_ALL", "TZ")


def tool_env(ctx, extra: dict | None = None) -> dict:
    env = {k: os.environ[k] for k in ENV_ALLOW if k in os.environ}
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PHDLAB_TOOL_WORKDIR=str(ctx.workdir),
               HOME=str(ctx.workdir), USERPROFILE=str(ctx.workdir))
    env.update(extra or {})
    return env


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        import psutil
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except Exception:
        try:
            proc.kill()
        except OSError:
            pass


def run_process(argv: list, ctx, *, stdin: bytes = b"", env: dict | None = None, cwd: Path | None = None) -> dict:
    """Run an owned process with deadline/cancel/output bounds; stderr lines are streamed as observations."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=str(cwd or ctx.workdir), env=env if env is not None else tool_env(ctx),
                                creationflags=flags)
    except FileNotFoundError as e:
        raise ToolError("unavailable", f"Executable not found: {argv[0]}", hint="Install the tool or choose another") from e
    except OSError as e:
        raise ToolError("execution_failed", f"Could not start process: {type(e).__name__}") from e
    out, err, overflow = bytearray(), bytearray(), {"hit": False}

    def pump_out():
        for chunk in iter(lambda: proc.stdout.read(65536), b""):
            if len(out) + len(chunk) > ctx.max_output_bytes:
                overflow["hit"] = True
                _kill_tree(proc)
                return
            out.extend(chunk)

    def pump_err():
        for line in iter(proc.stderr.readline, b""):
            if len(err) < 64_000:
                err.extend(line)
            ctx.observe("stderr", line.decode("utf-8", "replace").rstrip()[:2000])

    readers = [threading.Thread(target=pump_out, daemon=True), threading.Thread(target=pump_err, daemon=True)]
    for r in readers:
        r.start()
    try:
        if stdin:
            proc.stdin.write(stdin)
        proc.stdin.close()
    except OSError:
        pass
    reason = ""
    while proc.poll() is None:
        if ctx.cancelled.is_set():
            reason = "cancelled"
        elif time.monotonic() >= ctx.deadline:
            reason = "timeout"
        if reason:
            _kill_tree(proc)
            break
        time.sleep(0.02)
    proc.wait(timeout=30)
    for r in readers:
        r.join(timeout=5)
    for pipe in (proc.stdout, proc.stderr):
        try:
            pipe.close()
        except OSError:
            pass
    if reason == "cancelled":
        raise ToolError("cancelled", "Tool execution was cancelled")
    if reason == "timeout":
        raise ToolError("timeout", "Tool exceeded its time budget", retryable=True,
                        hint="Retry with a smaller input or ask for a larger budget")
    if overflow["hit"]:
        raise ToolError("budget_exceeded", f"Tool output exceeded {ctx.max_output_bytes} bytes",
                        hint="Request less output (filter, paginate or summarize inside the tool)")
    return {"exit_code": proc.returncode, "stdout": bytes(out).decode("utf-8", "replace"),
            "stderr": bytes(err).decode("utf-8", "replace")[-8000:]}


def _json_result(raw: str, spec: ToolSpec) -> dict:
    try:
        value = json.loads(raw)
    except ValueError as e:
        raise ToolError("invalid_output", f"{spec.ref} did not print a JSON object on stdout") from e
    if not isinstance(value, dict):
        raise ToolError("invalid_output", f"{spec.ref} must print a JSON object")
    return value


# ------------------------------------------------------------------ native (built-in application functions)
class Native:
    """Built-in tools only: user/agent manifests can never declare kind=native (enforced by the registry)."""

    @staticmethod
    def probe(spec):
        ex = spec.execution
        if "mcp_tool" in ex:
            from backend.core.config import load_config
            m = load_config().get("mcp") or {}
            if not m.get("enabled", True):
                return {"available": False, "reason": "MCP tools are disabled in Settings (mcp.enabled)"}
            if spec.capabilities and "sandbox" in spec.capabilities and not m.get("expose_sandbox", True):
                return {"available": False, "reason": "Sandbox tools are disabled (mcp.expose_sandbox)"}
            return {"available": True, "reason": ""}
        if "probe" in ex:  # application-defined availability check (e.g. a CLI delegate's sign-in)
            import importlib
            module, _, name = ex["probe"].partition(":")
            if not module.startswith("backend."):
                return {"available": False, "reason": "Native probes must live in the backend package"}
            return getattr(importlib.import_module(module), name)(spec)
        if "callable" in ex:
            return {"available": True, "reason": ""}
        return {"available": False, "reason": "Native tool has no handler"}

    @staticmethod
    def execute(spec, args, ctx):
        ex = spec.execution
        if "mcp_tool" in ex:
            from backend.providers.mcp_server import call_tool
            try:
                res = call_tool(ex["mcp_tool"], args, {"name": "phdlab-tool-runtime", "session": ctx.principal})
            except PermissionError as e:
                raise ToolError("permission_denied", str(e)) from e
            except (ValueError, KeyError, TypeError) as e:
                raise ToolError("invalid_input", f"{type(e).__name__}: {e}"[:500]) from e
            text = "\n".join(c.get("text", "") for c in res.get("content") or [] if c.get("type") == "text")
            if res.get("isError"):
                raise ToolError("execution_failed", text[:1000] or "Tool reported an error")
            out = {"text": text[:ctx.max_output_bytes]}
            if isinstance(res.get("structuredContent"), dict):
                out["structured"] = res["structuredContent"]
            return out
        import importlib
        module, _, name = ex["callable"].partition(":")
        if not module.startswith("backend."):
            raise ToolError("invalid_spec", "Native callables must live in the backend package")
        fn = getattr(importlib.import_module(module), name)
        result = fn(args, ctx, spec) if ex.get("pass_spec") else fn(args, ctx)
        if not isinstance(result, dict):
            raise ToolError("invalid_output", f"{spec.ref} returned {type(result).__name__}, expected an object")
        return result


# ------------------------------------------------------------------ python (manifest-directory script)
class Python:
    """execution = {"entry": "tool.py"}: run `python -I <entry>` with the JSON arguments on stdin; the script prints one
    JSON object on stdout. stderr lines stream as observations."""

    @staticmethod
    def _entry(spec) -> Path:
        home = Path(spec.execution.get("home", ""))
        entry = (home / spec.execution.get("entry", "")).resolve()
        if not home.is_dir() or not entry.is_relative_to(home.resolve()) or entry.suffix != ".py":
            raise ToolError("invalid_spec", "Python tool entry must be a .py file inside its tool directory")
        return entry

    @classmethod
    def probe(cls, spec):
        try:
            return {"available": cls._entry(spec).is_file(), "reason": "" if cls._entry(spec).is_file() else "entry file missing"}
        except ToolError as e:
            return {"available": False, "reason": e.message}

    @classmethod
    def execute(cls, spec, args, ctx):
        entry = cls._entry(spec)
        python = spec.execution.get("python") or sys.executable
        r = run_process([python, "-I", str(entry)], ctx, stdin=json.dumps(args).encode())
        if r["exit_code"] != 0:
            raise ToolError("execution_failed", f"{spec.ref} exited with code {r['exit_code']}",
                            details={"stderr_tail": r["stderr"][-2000:]})
        return _json_result(r["stdout"], spec)


# ------------------------------------------------------------------ cli (installed executable, no shell)
class Cli:
    """execution = {"binary": "name", "args": ["--in", "{path}"], "output": "text"|"json", "ok_exit_codes": [0]}.
    Placeholders are substituted per argument (never through a shell); a substituted value may not start with "-",
    so arguments cannot smuggle extra options."""

    @staticmethod
    def resolve(spec) -> str | None:
        b = spec.execution.get("binary", "")
        if not b:
            return None
        p = Path(b)
        if p.is_absolute():
            return str(p) if p.is_file() else None
        return shutil.which(b)

    @classmethod
    def probe(cls, spec):
        found = cls.resolve(spec)
        return {"available": bool(found), "reason": "" if found else f"{spec.execution.get('binary')} is not installed"}

    @staticmethod
    def argv(template: list, args: dict) -> list:
        import re

        def fill(match):
            name = match.group(1)
            if name not in args:
                raise ToolError("invalid_input", f"Missing argument {name!r} required by the command template")
            given = args[name]
            text = given if isinstance(given, str) else json.dumps(given)
            if text.startswith("-"):
                raise ToolError("invalid_input", f"Argument {name} may not start with '-'")
            return text
        return [re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", fill, str(part)) for part in template]

    @classmethod
    def execute(cls, spec, args, ctx):
        binary = cls.resolve(spec)
        if not binary:
            raise ToolError("unavailable", f"{spec.execution.get('binary')} is not installed",
                            hint="Search for an alternative tool")
        r = run_process([binary, *cls.argv(spec.execution.get("args") or [], args)], ctx)
        if r["exit_code"] not in (spec.execution.get("ok_exit_codes") or [0]):
            raise ToolError("execution_failed", f"{spec.ref} exited with code {r['exit_code']}",
                            details={"stderr_tail": r["stderr"][-2000:], "stdout_tail": r["stdout"][-2000:]})
        if spec.execution.get("output") == "json":
            return _json_result(r["stdout"], spec)
        return {"exit_code": r["exit_code"], "stdout": r["stdout"], "stderr": r["stderr"]}


# ------------------------------------------------------------------ mcp (external MCP server tool)
class Mcp:
    """execution = {"url": "https://host/mcp" | loopback http, "tool": "remote_name"}. No credentials are stored in a
    manifest. Application-only keys (stripped from manifests/snapshots by the registry): `stdio` names an owned local
    server process, `auth` names an application token provider, `guard` names an argument/result policy."""

    @staticmethod
    def _url(spec) -> str:
        from backend.providers.mcp_agent import endpoint
        try:
            return endpoint(spec.execution.get("url", ""))
        except ValueError as e:
            raise ToolError("invalid_spec", str(e)) from e

    @classmethod
    def probe(cls, spec):
        if spec.execution.get("stdio") or spec.execution.get("auth"):
            from backend.tools import google_mcp
            return google_mcp.probe(spec)
        try:
            cls._url(spec)
        except ToolError as e:
            return {"available": False, "reason": e.message}
        return {"available": True, "reason": "configured (reachability is checked on call)"}

    @classmethod
    def execute(cls, spec, args, ctx):
        timeout = max(1.0, ctx.deadline - time.monotonic())
        ex = spec.execution
        if ex.get("stdio"):  # application-defined local server (e.g. Google Colab bridge); never from a manifest
            from backend.tools import google_mcp
            session = google_mcp.stdio_server(ex["stdio"])
            call = lambda tool, arguments: session.request("tools/call", {"name": tool, "arguments": arguments}, timeout)
            result = cls._guarded(spec, args, call)
        else:
            headers = {}
            if ex.get("auth"):
                from backend.tools import google_mcp
                headers = google_mcp.auth_headers(ex["auth"], cls._url(spec))
            with McpSession(cls._url(spec), timeout, headers) as s:
                call = lambda tool, arguments: s.request("tools/call", {"name": tool, "arguments": arguments})
                result = cls._guarded(spec, args, call)
        return cls._unpack(result, ctx, spec)

    @staticmethod
    def _guarded(spec, args, call):
        if spec.execution.get("guard"):
            from backend.tools import google_mcp
            return google_mcp.guarded_call(spec, args, call)
        return call(spec.execution.get("tool", spec.id), args)

    @staticmethod
    def _unpack(result, ctx, spec):
        text = "\n".join(c.get("text", "") for c in result.get("content") or [] if c.get("type") == "text")
        if result.get("isError"):
            raise ToolError("execution_failed", text[:1000] or "Remote MCP tool reported an error")
        out = {"text": text[:ctx.max_output_bytes]}
        if isinstance(result.get("structuredContent"), dict):
            out["structured"] = result["structuredContent"]
        return out


class McpSession:
    """Minimal synchronous streamable-HTTP JSON-RPC client (initialize -> requests); bounded response size."""
    LIMIT = 4 * 1024 * 1024

    def __init__(self, url: str, timeout: float, headers: dict | None = None):
        import httpx
        self.url, self.seq = url, 0
        self.headers = {"Accept": "application/json, text/event-stream", **(headers or {})}
        self.client = httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False)

    def __enter__(self):
        try:
            init = self.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                               "clientInfo": {"name": "phdlab-tool-runtime", "version": "1"}})
            if init.get("protocolVersion") not in ("2024-11-05", "2025-03-26", "2025-06-18"):
                raise ToolError("incompatible_version", "Unsupported MCP protocol version")
            self.headers["MCP-Protocol-Version"] = init["protocolVersion"]
            self.request("notifications/initialized", {}, notify=True)
        except BaseException:
            self.client.close()
            raise
        return self

    def __exit__(self, *exc):
        self.client.close()

    def request(self, method: str, params: dict, notify: bool = False) -> dict:
        import httpx
        self.seq += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            payload["id"] = self.seq
        try:
            r = self.client.post(self.url, headers=self.headers, json=payload)
        except httpx.TimeoutException as e:
            raise ToolError("timeout", "MCP server did not answer in time", retryable=True) from e
        except httpx.HTTPError as e:
            raise ToolError("unavailable", "MCP server is unreachable", retryable=True) from e
        if r.status_code not in (200, 202, 204):
            raise ToolError("unavailable" if r.status_code >= 500 else "execution_failed",
                            f"MCP request failed (HTTP {r.status_code})", retryable=r.status_code >= 500)
        if len(r.content) > self.LIMIT:
            raise ToolError("budget_exceeded", "MCP response exceeded 4 MiB")
        if sid := r.headers.get("mcp-session-id"):
            self.headers["Mcp-Session-Id"] = sid
        if notify:
            return {}
        try:
            if "text/event-stream" in r.headers.get("content-type", ""):
                events = [json.loads(data) for ev in r.text.replace("\r\n", "\n").split("\n\n")
                          if (data := "\n".join(l[5:].lstrip() for l in ev.splitlines() if l.startswith("data:")))]
                msg = next((e for e in events if isinstance(e, dict) and e.get("id") == self.seq), None)
            else:
                msg = json.loads(r.text)
        except ValueError as e:
            raise ToolError("invalid_output", "MCP server returned malformed JSON-RPC") from e
        if not isinstance(msg, dict) or msg.get("id") != self.seq:
            raise ToolError("invalid_output", "MCP returned an uncorrelated response")
        if "error" in msg:
            raise ToolError("execution_failed", f"MCP error: {str((msg['error'] or {}).get('message', ''))[:300]}")
        if not isinstance(msg.get("result"), dict):
            raise ToolError("invalid_output", "MCP result must be an object")
        return msg["result"]

    def list_tools(self, pages: int = 10) -> list:
        tools, cursor, seen = [], None, set()
        for _ in range(pages):
            page = self.request("tools/list", {"cursor": cursor} if cursor else {})
            tools += [t for t in page.get("tools") or [] if isinstance(t, dict)]
            cursor = page.get("nextCursor")
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
        return tools


# ------------------------------------------------------------------ container (Docker, isolated)
class Container:
    """execution = {"image": "python:3.12-slim", "command": ["python", "-c", "..."]}: JSON args on stdin, one JSON
    object on stdout. --network none unless the spec has the `network` permission; read-only root filesystem; the
    per-job working directory is the only writable mount; memory/CPU limits from the spec budget. Images are never
    pulled implicitly."""

    @staticmethod
    def probe(spec):
        from backend.execution import sandbox
        if not sandbox.docker_exe():
            return {"available": False, "reason": "Docker CLI is not installed"}
        if not sandbox.docker_running():
            return {"available": False, "reason": "Docker engine is not running"}
        image = spec.execution.get("image", "")
        if not image or not sandbox.image_present(image):
            return {"available": False, "reason": f"Image {image or '?'} is not present locally (no implicit pull)"}
        return {"available": True, "reason": ""}

    @classmethod
    def execute(cls, spec, args, ctx):
        from backend.execution import sandbox
        state = cls.probe(spec)
        if not state["available"]:
            raise ToolError("unavailable", state["reason"], hint="Use a non-container tool or prepare the image")
        b = spec.budget
        argv = [sandbox.docker_exe(), "run", "--rm", "-i", "--read-only", "--tmpfs", "/tmp:rw,size=256m",
                "--security-opt", "no-new-privileges", "--cap-drop", "ALL", "--pids-limit", "256",
                f"--memory={b.memory_mb}m", f"--cpus={b.cpus}", "-v", f"{ctx.workdir}:/work", "-w", "/work",
                "--name", f"phdlab-tool-{ctx.job_id}"]
        if spec.execution.get("home"):  # application-set only (registry strips it from manifests): tool code, read-only
            argv += ["-v", f"{spec.execution['home']}:/tool:ro"]
        if "network" not in spec.permissions:
            argv += ["--network", "none"]
        argv += [spec.execution["image"], *[str(c) for c in spec.execution.get("command") or []]]
        try:
            r = run_process(argv, ctx, stdin=json.dumps(args).encode())
        finally:
            sandbox.docker(["rm", "-f", f"phdlab-tool-{ctx.job_id}"], timeout=30)
        if r["exit_code"] != 0:
            raise ToolError("execution_failed", f"{spec.ref} container exited with code {r['exit_code']}",
                            details={"stderr_tail": r["stderr"][-2000:]})
        return _json_result(r["stdout"], spec)


ADAPTERS = {"native": Native, "python": Python, "cli": Cli, "mcp": Mcp, "container": Container}
