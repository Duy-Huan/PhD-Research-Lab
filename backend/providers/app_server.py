"""Opt-in Codex stdio RPC prototype. Process per request, native thread resume.

Only initialization failures permit exec fallback. A submitted turn is never replayed.
No persistent daemon until benchmarks demonstrate a benefit and grant renewal is designed.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time

from backend.providers import events as E


class StartupFailure(ValueError):
    pass


def model_catalog() -> list:
    """Explicit refresh only: catalog is not proof of account entitlement. No inference."""
    from backend.providers.cli import CONNECTORS, kill_tree
    from backend.providers.cli_space import open_session
    from backend.execution.tools import NO_WINDOW
    conn = CONNECTORS["codex"]
    cwd = open_session("codex", "catalog", "review")["cwd"]
    proc = subprocess.Popen(conn._prefix() + ["app-server", "--listen", "stdio://"], cwd=cwd, env=conn.env(),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW, start_new_session=os.name != "nt")
    timer = threading.Timer(20, lambda: kill_tree(proc))
    timer.daemon = True
    timer.start()
    try:
        for ident, method, params in [(1, "initialize", {"clientInfo": {"name": "phdlab", "version": "5.1"}}),
                                      (2, "model/list", {"limit": 100})]:
            proc.stdin.write(json.dumps({"id": ident, "method": method, "params": params}) + "\n")
            proc.stdin.flush()
            while True:
                line = proc.stdout.readline(1024 * 1024)
                if not line:
                    raise StartupFailure("Codex model catalog unavailable")
                obj = json.loads(line)
                if obj.get("id") != ident:
                    continue
                if obj.get("error"):
                    raise StartupFailure("Codex rejected model/list")
                if ident == 1:
                    proc.stdin.write('{"method":"initialized","params":{}}\n')
                    proc.stdin.flush()
                else:
                    return sorted({m["model"] for m in obj.get("result", {}).get("data", []) if m.get("model")})
                break
    finally:
        timer.cancel()
        kill_tree(proc)
        proc.wait(timeout=5)
        proc.stdin.close()
        proc.stdout.close()


def stream(conn, message: str, context: dict, extra: list):
    from backend.providers.cli import ProviderError, _procs, _lock, kill_tree, _drain, _gw
    from backend.execution.tools import NO_WINDOW
    from backend.providers import firewall
    from backend.core.config import load_config
    args = conn._prefix() + ["app-server", "--listen", "stdio://"] + extra
    ws = load_config()["codex"].get("windows_sandbox", "unelevated")
    if ws != "config":
        args += ["-c", f"windows.sandbox={ws}"]
    rid = context["request_id"]
    started = time.monotonic()
    try:
        proc = subprocess.Popen(args, cwd=context["cwd"], env=conn.env(), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                errors="replace", bufsize=1, creationflags=NO_WINDOW, start_new_session=os.name != "nt")
    except OSError as e:
        raise StartupFailure("app-server could not start") from e
    context.setdefault("_timings_ms", {})["cli_startup"] = round((time.monotonic() - started) * 1000, 2)
    with _lock:
        _procs[rid] = proc
    inbox = queue.Queue(maxsize=256)
    stop = threading.Event()
    errors = []
    context["_stderr"] = errors
    threading.Thread(target=_drain, args=(proc.stderr, errors), daemon=True).start()

    def reader():
        try:
            while not stop.is_set():
                line = proc.stdout.readline(1024 * 1024)
                if not line:
                    return
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                while not stop.is_set():
                    try:
                        inbox.put(obj, timeout=0.2)
                        break
                    except queue.Full:
                        continue
        except (OSError, ValueError):
            return
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = started + float(context.get("timeout_s") or _gw().get("provider_timeout_s", 600))
    submitted = False
    next_id = 0

    def send(method, params=None, notification=False):
        nonlocal next_id
        next_id += 1
        obj = {"method": method, "params": params or {}}
        if not notification:
            obj["id"] = next_id
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()
        return next_id

    def receive():
        while True:
            if getattr(proc, "_phd_cancelled", False) or (context.get("_cancel") and context["_cancel"].is_set()):
                raise InterruptedError("cancelled")
            if time.monotonic() >= deadline:
                raise TimeoutError("app-server time limit")
            try:
                obj = inbox.get(timeout=0.1)
            except queue.Empty:
                if proc.poll() is not None:
                    raise RuntimeError("app-server exited before turn completed")
                continue
            context["_timings_ms"].setdefault("first_cli_event", round((time.monotonic() - started) * 1000, 2))
            if "method" in obj and "id" in obj:
                # Tool approvals / requestUserInput require a UI bridge, never silently authorize.
                proc.stdin.write(json.dumps({"id": obj["id"], "error": {"code": -32601,
                                  "message": "Interactive requests are unavailable in the prototype"}}) + "\n")
                proc.stdin.flush()
                raise ProviderError("app-server requires an interactive approval; resume with codex exec")
            return obj

    def rpc(method, params):
        ident = send(method, params)
        while True:
            obj = receive()
            if obj.get("id") == ident:
                if obj.get("error"):
                    raise RuntimeError(str(obj["error"])[:300])
                return obj.get("result") or {}

    try:
        # Bound handshake separately; hung startup can safely fall back before any turn exists.
        full_deadline = deadline
        deadline = min(deadline, started + 20)
        rpc("initialize", {"clientInfo": {"name": "phdlab", "title": "PhD Research Lab", "version": "5.1"}})
        send("initialized", notification=True)
        params = {"cwd": context["cwd"], "approvalPolicy": "never",
                  "sandbox": "workspace-write" if context.get("profile") == "assisted" else "read-only"}
        if context.get("model"):
            params["model"] = context["model"]
        if context.get("resume_session"):
            result = rpc("thread/resume", {**params, "threadId": context["resume_session"]})
        else:
            result = rpc("thread/start", params)
        thread_id = result["thread"]["id"]
        deadline = full_deadline
        yield E.ev("request_started", provider="codex", request_id=rid, transport="app-server")
        yield E.ev("status", state="session", session_id=thread_id)
        turn = {"threadId": thread_id, "input": [{"type": "text", "text": message}]}
        if context.get("reasoning"):
            turn["effort"] = context["reasoning"]
        submitted = True  # includes ambiguous delivery; never fallback after this point
        send("turn/start", turn)
        while True:
            obj = receive()
            if obj.get("error"):
                raise ProviderError(str(obj["error"])[:300])
            method, p = obj.get("method"), obj.get("params") or {}
            if method == "item/agentMessage/delta":
                yield E.ev("text_delta", text=p.get("delta", ""))
            elif method in ("item/started", "item/completed"):
                item = p.get("item") or {}
                typ = item.get("type", "")
                if typ in ("commandExecution", "mcpToolCall", "fileChange"):
                    detail = str(item.get("command") or item.get("tool") or item.get("changes") or "")[:1000]
                    bad = firewall.violation(detail)
                    if bad:
                        raise ProviderError("firewall: app-server tool access refused")
                    yield E.ev("tool_call" if method.endswith("started") else "tool_result", name=typ, detail=detail)
            elif method == "turn/completed":
                status = (p.get("turn") or {}).get("status")
                if status == "interrupted":
                    yield E.ev("request_cancelled", provider="codex", request_id=rid)
                elif status != "completed":
                    raise ProviderError("Codex turn failed: " + str((p.get("turn") or {}).get("error") or status)[:300])
                else:
                    yield E.ev("request_completed", provider="codex", request_id=rid, exit_code=0)
                return
            elif method == "error" and not p.get("willRetry"):
                raise ProviderError(str(p.get("error") or "Codex error")[:300])
    except InterruptedError:
        yield E.ev("request_cancelled", provider="codex", request_id=rid)
    except Exception as e:
        if not submitted:
            raise StartupFailure("app-server initialization failed") from e
        raise ProviderError(str(e)[:500]) from e
    finally:
        stop.set()
        kill_tree(proc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        thread.join(timeout=1)
        with _lock:
            _procs.pop(rid, None)
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            try:
                pipe.close()
            except OSError:
                pass
