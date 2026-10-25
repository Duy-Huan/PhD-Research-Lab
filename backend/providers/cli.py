"""Provider connectors (v3.4 §3-5, §16-17, §23): one contract for every AI environment, first-party paths only.

    ProviderConnector            capabilities · health · connect · disconnect · start_session · send_message ·
                                 stream_message · cancel           (unsupported → "NOT_SUPPORTED", never faked)
      ├── CodexConnector         ChatGPT plan through the official OpenAI Codex CLI (`codex login` = ChatGPT sign-in)
      ├── ClaudeCodeConnector    Claude subscription through the official Claude Code CLI (`claude -p`)
      ├── AntigravityConnector   Google Antigravity: MCP client (IDE / app) + the official Antigravity CLI `agy -p`
      └── GeminiCliConnector     Google Gemini CLI (`gemini -p`) — kept for accounts that still use it

Policy (non-negotiable, v3.4 §0):
  • No credential ever passes through this app: each CLI signs in with its vendor's own browser flow and keeps its own
    token store. connect() only tells the researcher which official command to run (optionally opens a terminal for it).
  • No private endpoints, no cookie/session extraction, no user-agent impersonation, no quota circumvention.
  • Cost guard: unless <provider>_api_fallback is switched on, the CLI is started with every API-key variable of that
    vendor removed from its environment, so it can only use the subscription sign-in — the app never creates API
    billing implicitly. Codex signed in with an API key is refused for the same reason. Claude Code is never started
    with --bare (bare mode skips the subscription login and requires an API key).
  • Read-only by default: Codex runs with --sandbox read-only, Claude Code may only call the PhD-Lab research MCP read
    tools, Antigravity CLI runs with --sandbox (no approvals in headless mode → everything else is soft-denied).
  • v4.1 Secure CLI space (gateway/workspace.py): the process runs in its session workspace (never the app or project
    folder), with an allowlisted environment, a time limit, and its whole process tree is killed when the request ends
    early (cancel, timeout, client gone). context["profile"] selects review | assisted where the provider supports it.
"""
from __future__ import annotations

import json
import base64
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from backend.execution.tools import NO_WINDOW, cached, node_argv, run_cli, which
from backend.providers import events as E

HEALTH = ("CONNECTED", "DISCONNECTED", "AUTH_EXPIRED", "RATE_LIMITED", "UNAVAILABLE", "ERROR", "UNKNOWN")
NOT_SUPPORTED = "NOT_SUPPORTED"
CAPS = ("connect", "disconnect", "health", "capabilities", "send", "stream", "cancel", "mcp_client")
RATE_RE = re.compile(r"(?i)rate.?limit|429|quota|usage limit|weekly limit|daily limit|hit your .*limit|too many requests")
AUTH_RE = re.compile(r"(?i)authenticat|auth method|not logged in|login required|sign.?in|unauthori[sz]ed|401|expired")
READ_TOOLS = ("research_get_current_state", "research_search_memory", "research_get_hypothesis", "research_get_experiment",
              "research_get_evidence", "research_get_decisions", "research_get_failures", "research_get_context",
              "research_get_provenance")
_last_error: dict = {}
_procs: dict = {}
_lock = threading.Lock()


class ProviderError(Exception):
    """Safe-to-show provider failure (no secrets). `state` is one of HEALTH."""

    def __init__(self, msg: str, state: str = "ERROR"):
        super().__init__(msg)
        self.state = state


def classify_error(text: str) -> str:
    if RATE_RE.search(text or ""):
        return "RATE_LIMITED"
    if AUTH_RE.search(text or ""):
        return "AUTH_EXPIRED"
    return "ERROR"


def _gw() -> dict:
    from backend.core.config import load_config
    return load_config()["gateway"]


def kill_tree(proc) -> None:
    """Terminate a CLI process and every child it started (best effort, never raises)."""
    try:
        if proc.poll() is not None:
            return
        if sys.platform.startswith("win"):
            from backend.execution.processes import stop_descendants
            stop_descendants(proc)
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True,
                               creationflags=NO_WINDOW, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if proc.poll() is None:
                proc.kill()  # taskkill may be denied or unavailable; still terminate our own child promptly
        else:  # pragma: no cover - POSIX
            import signal
            if os.getpgid(proc.pid) == proc.pid:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
    except Exception:  # pragma: no cover
        pass


def _drain(stream, out: list) -> None:
    try:
        for line in iter(stream.readline, ""):
            if line.strip():
                from backend.core.telemetry import redact
                out.append(redact(line.strip())[:300])
                del out[:-128]
    except (ValueError, OSError):  # pipe closed when the request ended
        pass


class ProviderConnector:
    provider_id = ""
    label = ""
    vendor = ""
    path = ""            # the officially supported integration path, shown in the UI
    api_env: tuple = ()  # vendor API-key variables removed by the cost guard
    supports_resume = False  # native session resume (used by the cli lifecycle policy)

    def enabled(self) -> bool:
        return bool(_gw().get(f"{self.provider_id}_enabled", True))

    def api_fallback(self) -> bool:
        return bool(_gw().get(f"{self.provider_id}_api_fallback", False))

    def capabilities(self) -> dict:
        return {c: NOT_SUPPORTED for c in CAPS} | {"health": True, "capabilities": True}

    def health(self, fresh: bool = False) -> dict:
        return {"provider": self.provider_id, "state": "UNKNOWN", "detail": ""}

    def connect(self, launch: bool = False) -> dict:
        raise ProviderError(NOT_SUPPORTED)

    def stream_message(self, message: str, context: dict):
        raise ProviderError(f"{self.label}: {NOT_SUPPORTED}", "ERROR")

    def cancel(self, request_id: str) -> dict:
        return {"provider": self.provider_id, "cancelled": False, "detail": NOT_SUPPORTED}

# ------------------------------------------------------------------ CLI-backed connectors
class CLIConnector(ProviderConnector):
    binaries: tuple = ()
    binary_key = ""
    normalizer = ""
    login_cmd = ""

    def binary(self) -> str | None:
        b = (_gw().get(self.binary_key) or "").strip() if self.binary_key else ""
        if b and Path(b).name.lower().split(".")[0] in self.binaries:
            return b
        return which(*self.binaries)

    def env(self) -> dict:
        """v4.1: an allowlisted environment (workspace.minimal_env) — credentials, cloud keys and unrelated variables
        never reach the CLI. Cost guard: the provider's own API-key variables pass only with <provider>_api_fallback."""
        from backend.providers.cli_space import minimal_env
        return minimal_env(set(self.api_env) if self.api_fallback() else set())

    def _probe(self) -> dict:
        b = self.binary()
        if not b:
            return {"bin": None}
        code, out = run_cli([b, "--version"], 20)
        return {"bin": b, "ok": code == 0, "version": (out.strip().splitlines() or [""])[-1][:80]}

    def auth_state(self, probe: dict) -> tuple[str, str]:
        """(state, detail) — CLIs without a status command are UNKNOWN until the first request proves the sign-in."""
        return "UNKNOWN", "signed-in state is verified by the first request"

    def health(self, fresh: bool = False) -> dict:
        base = {"provider": self.provider_id, "label": self.label, "path": self.path,
                "billing": "API key (fallback enabled)" if self.api_fallback() else "subscription sign-in only (API keys removed)",
                "api_fallback": self.api_fallback()}
        if not self.enabled():
            return {**base, "state": "DISCONNECTED", "detail": "disabled in PhD-Lab (gateway settings)"}
        key = f"gw:{self.provider_id}:{self.binary()}"
        if fresh:
            from backend.execution.tools import _cache
            _cache.pop(key, None)
        p = cached(key, 300, self._probe)
        if not p.get("bin"):
            return {**base, "state": "UNAVAILABLE", "detail": f"`{self.binaries[0]}` CLI not found on PATH", "setup": self.setup()}
        if not p.get("ok"):
            return {**base, "state": "ERROR", "detail": f"`{self.binaries[0]} --version` failed", "setup": self.setup()}
        state, detail = self.auth_state(p)
        last = _last_error.get(self.provider_id)
        if fresh and state == "CONNECTED" and last and last[0] == "AUTH_EXPIRED":
            _last_error.pop(self.provider_id, None)
            last = None
        if last and state in ("CONNECTED", "UNKNOWN"):
            state, detail = last
        return {**base, "state": state, "detail": detail, "version": p.get("version", ""), "setup": self.setup()}

    def setup(self) -> list:
        return []

    def capabilities(self) -> dict:
        return {**super().capabilities(), "connect": True, "disconnect": True, "send": True, "stream": True, "cancel": True,
                "mcp_client": True}

    def connect(self, launch: bool = False) -> dict:
        out = {"provider": self.provider_id, "action": "sign_in_with_vendor", "command": self.login_cmd,
               "detail": "Sign in through the vendor's own browser flow. PhD-Lab never sees your password or tokens."}
        if launch and sys.platform.startswith("win"):
            bin_path = self.binary()
            if bin_path:
                parts = [bin_path, *self.login_cmd.split()[1:]]
                command = "& " + " ".join("'" + part.replace("'", "''") + "'" for part in parts)
            else:
                command = f"Write-Host '--- PhD Research Lab: {self.label} CLI ---' -ForegroundColor Cyan; {self.login_cmd}"
            encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
            subprocess.Popen(["powershell.exe", "-NoLogo", "-NoExit", "-EncodedCommand", encoded],
                             creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            out["launched"] = True
        _last_error.pop(self.provider_id, None)
        from backend.core.config import save_config
        save_config({"gateway": {f"{self.provider_id}_enabled": True}})
        return out

    def argv(self, context: dict) -> list:
        raise NotImplementedError

    def stdin_payload(self, message: str, context: dict) -> str:
        return message

    def stream_message(self, message: str, context: dict):
        h = self.health()
        if h["state"] in ("DISCONNECTED", "UNAVAILABLE", "ERROR"):
            raise ProviderError(f"{self.label} is {h['state']}: {h['detail']}", h["state"])
        rid = context.get("request_id") or "req-" + secrets.token_hex(6)
        context.setdefault("request_id", rid)
        if context.get("_cancel") and context["_cancel"].is_set():
            yield E.ev("request_cancelled", provider=self.provider_id, request_id=rid)
            return
        from backend.providers import cli_space as W
        profile = context.get("profile") or "review"
        if not context.get("cwd"):  # never the project / app folder: an ad-hoc session workspace instead
            try:
                iso = W.check_profile(self.provider_id, profile, bool(context.get("allow_weaker")))
            except W.WorkspaceError as e:
                raise ProviderError(str(e), "ERROR")
            context["cwd"] = W.open_session(self.provider_id, "adhoc-" + re.sub(r"[^\w-]", "-", rid)[-24:], profile, iso)["cwd"]
        cwd = Path(context["cwd"]).resolve()
        if not cwd.is_dir() or cwd.name != "workspace" or cwd.parent.parent.parent.parent != W.root():
            raise ProviderError("CLI working directory is not a PhD-Lab session workspace", "ERROR")
        from backend.providers import firewall
        mcp = {"url": context["mcp_url"], "token": context.get("mcp_token", "")} if context.get("mcp_url") else None
        extra = firewall.prepare_workspace(self.provider_id, cwd, mcp)["argv"]
        if self.provider_id == "codex" and _gw().get("codex_app_server", False):
            from backend.providers.app_server import stream, StartupFailure
            try:
                yield from stream(self, message, context, extra)
                return
            except StartupFailure:
                # No turn was submitted. Once submitted, recovery must never replay the prompt automatically.
                yield E.ev("status", state="transport_fallback", transport="codex-exec")
        context["_extra_argv"] = extra
        args = self.argv(context)
        if not context.get("_extra_argv_consumed") and self.provider_id != "codex":
            args = (args[:-1] + extra + ["-"]) if args and args[-1] == "-" else args + extra
        launch = time.perf_counter()
        try:
            proc = subprocess.Popen(args, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1, env=self.env(), creationflags=NO_WINDOW,
                                    start_new_session=os.name != "nt")
        except OSError as e:
            raise ProviderError(f"Could not start {self.binaries[0]}: {e}", "UNAVAILABLE")
        with _lock:
            _procs[rid] = proc
        context.setdefault("_timings_ms", {})["cli_startup"] = round((time.perf_counter() - launch) * 1000, 2)
        if context.get("_cancel") and context["_cancel"].is_set():
            proc._phd_cancelled = True
            kill_tree(proc)
        err_lines: list = []
        context["_stderr"] = err_lines
        threading.Thread(target=_drain, args=(proc.stderr, err_lines), daemon=True).start()
        limit = float(context.get("timeout_s") or _gw().get("provider_timeout_s", 600) or 600)

        def _timeout():
            proc._phd_timeout = True
            kill_tree(proc)
        watchdog = threading.Timer(limit, _timeout)
        watchdog.daemon = True
        watchdog.start()
        try:  # everything after the launch is inside try/finally: a client that leaves early never orphans the CLI
            yield E.ev("request_started", provider=self.provider_id, request_id=rid)
            try:
                proc.stdin.write(self.stdin_payload(message, context))
                proc.stdin.close()
            except OSError:
                pass
            norm = E.NORMALIZERS[self.normalizer]
            errored = False
            emitted_text = False
            turn_finished = False
            for line in iter(proc.stdout.readline, ""):
                line = line.strip()
                if not line:
                    continue
                context["_timings_ms"].setdefault("first_cli_event", round((time.perf_counter() - launch) * 1000, 2))
                try:
                    raw = json.loads(line)
                except ValueError:
                    yield E.ev("text_delta", text=line + "\n")
                    continue
                events_batch = norm(raw) if isinstance(raw, dict) else []
                # Check for terminal events from normalizer or raw event payloads
                if isinstance(raw, dict):
                    raw_type = raw.get("type") or raw.get("event") or ""
                    if raw_type in ("turn.completed", "turn.failed", "result") or (raw_type == "item.completed" and raw.get("item", {}).get("type") == "agent_message" and self.provider_id == "codex"):
                        # Terminal status signal received
                        turn_finished = True
                for e in events_batch:
                    if e["type"] == "text_delta" and e.get("text"):
                        emitted_text = True
                    if e["type"] == "status" and e.get("state") == "result" and e.get("final_text") and not emitted_text:
                        emitted_text = True
                        yield E.ev("text_delta", text=e["final_text"], final=True)
                    if e["type"] == "status" and e.get("state") in ("usage", "result"):
                        turn_finished = True
                    bad = firewall.violation(f"{e.get('name', '')} {e.get('detail', '')}") if e["type"] == "tool_call" else ""
                    if bad:  # layer 5: the agent named the app's source / a secret → stop it now (fail closed)
                        kill_tree(proc)
                        yield E.ev("error", message=f"firewall: {self.label} tried to access {bad} — stopped", state="ERROR")
                        yield E.ev("request_completed", provider=self.provider_id, request_id=rid, exit_code=-1)
                        return
                    if e["type"] == "error":
                        errored = True
                        st = classify_error(e.get("message", ""))
                        e["state"] = st
                        if st != "ERROR":
                            _last_error[self.provider_id] = (st, e.get("message", "")[:200])
                    yield e
                if turn_finished:
                    # CLI has emitted the final answer and usage/turn-complete event. Break out immediately
                    # so lingering child processes/handles on Windows do not block the turn for 15-35s.
                    break
            try:
                proc.wait(timeout=0.3 if turn_finished else 5.0)
            except subprocess.TimeoutExpired:
                if proc.poll() is None:
                    kill_tree(proc)
            if getattr(proc, "_phd_timeout", False):
                yield E.ev("error", message=f"{self.label} did not finish within {int(limit)} s — stopped (time limit)",
                           state="ERROR")
                yield E.ev("request_completed", provider=self.provider_id, request_id=rid, exit_code=proc.returncode)
                return
            cancelled = getattr(proc, "_phd_cancelled", False)
            if cancelled:
                yield E.ev("request_cancelled", provider=self.provider_id, request_id=rid)
                return
            if not turn_finished and proc.returncode != 0 and not errored:
                msg = " | ".join(err_lines[-3:]) or f"exit code {proc.returncode}"
                st = classify_error(msg)
                if st != "ERROR":
                    _last_error[self.provider_id] = (st, msg[:200])
                yield E.ev("error", message=msg[:500], state=st)
            elif not errored and not emitted_text:
                yield E.ev("error", message=f"{self.label} returned no answer. Check CLI sign-in, model access and logs.", state="ERROR")
            elif not errored:
                _last_error.pop(self.provider_id, None)
            yield E.ev("request_completed", provider=self.provider_id, request_id=rid, exit_code=0 if turn_finished and not errored else proc.returncode)
        finally:
            watchdog.cancel()
            if proc.poll() is None:
                kill_tree(proc)  # consumer gone / exception: no orphaned CLI or child process stays behind
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
            with _lock:
                _procs.pop(rid, None)
            for f in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    f.close()
                except Exception:
                    pass
            if context.get("_tmpfile"):
                try:
                    os.remove(context.pop("_tmpfile"))
                except OSError:
                    pass

    def cancel(self, request_id: str) -> dict:
        with _lock:
            p = _procs.get(request_id)
        if not p or p.poll() is not None:
            return {"provider": self.provider_id, "cancelled": False, "detail": "request is not running"}
        p._phd_cancelled = True
        kill_tree(p)
        return {"provider": self.provider_id, "cancelled": True}


class CodexConnector(CLIConnector):
    provider_id, label, vendor = "codex", "ChatGPT (OpenAI Codex CLI)", "OpenAI"
    path = "Codex CLI signed in with a ChatGPT plan (`codex login`)"
    binaries, normalizer, login_cmd = ("codex",), "codex", "codex login"
    api_env = ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY")
    supports_resume = True

    def binary(self):
        from backend.core.config import load_config
        b = ((load_config().get("codex") or {}).get("binary") or "").strip()
        return b if b and re.search(r"codex", b, re.I) else which("codex")

    def _prefix(self) -> list:
        return node_argv(self.binary(), "@openai/codex/bin/codex.js")

    def _probe(self) -> dict:
        pre = self._prefix()
        if not pre:
            return {"bin": None}
        code, out = run_cli(pre + ["--version"], 20)
        lc, lout = run_cli(pre + ["login", "status"], 20)
        return {"bin": " ".join(pre), "ok": code == 0, "version": (out.strip().splitlines() or [""])[-1][:80], "login_code": lc,
                "login": lout.strip()[-200:]}

    def auth_state(self, p: dict) -> tuple[str, str]:
        if p.get("login_code") != 0:
            return "AUTH_EXPIRED" if p.get("login_code") not in (124, 126, 127) else "UNKNOWN", "run `codex login` (ChatGPT sign-in)"
        if re.search(r"(?i)api key", p.get("login", "")) and not self.api_fallback():
            return "ERROR", "Codex is signed in with an API key (API billing). Sign in with ChatGPT (`codex login`) or enable codex_api_fallback."
        return "CONNECTED", "signed in" + (" with ChatGPT" if re.search(r"(?i)chatgpt", p.get("login", "")) else "")

    def setup(self) -> list:
        return ["npm install -g @openai/codex", "codex login   (choose 'Sign in with ChatGPT')"]

    def argv(self, context: dict) -> list:
        mode = "workspace-write" if context.get("profile") == "assisted" else "read-only"
        resume_id = context.get("resume_session") if (context.get("resume_session") and re.fullmatch(r"[\w-]{6,80}", str(context["resume_session"]))) else ""
        if resume_id:
            args = self._prefix() + ["exec", "resume", "--json", "-c", f"sandbox_mode={mode}", "--skip-git-repo-check"]
        else:
            args = self._prefix() + ["exec", "--json", "--sandbox", mode, "--skip-git-repo-check"]
        if sys.platform.startswith("win"):
            from backend.core.config import load_config
            ws = load_config()["codex"].get("windows_sandbox") or "unelevated"
            if ws != "config":
                args += ["-c", f"windows.sandbox={ws}"]
        model = str(context.get("model") or "").strip()[:80]
        # Filter out API-only model default 'gpt-5' when using ChatGPT sign-in to prevent 400 errors
        if model and model.lower() not in ("gpt-5", "default", "auto", "none"):
            args += ["-m", model]
        if context.get("reasoning") in ("low", "medium", "high"):  # v4.2: Codex config key model_reasoning_effort
            args += ["-c", f"model_reasoning_effort={context['reasoning']}"]
        if context.get("_extra_argv"):
            args += list(context["_extra_argv"])
            context["_extra_argv_consumed"] = True
        if resume_id:
            args.append(resume_id)
        return args + ["-"]

class ClaudeCodeConnector(CLIConnector):
    provider_id, label, vendor = "claude_code", "Claude (Claude Code CLI)", "Anthropic"
    path = "Claude Code CLI signed in with a Claude subscription (`claude`, then /login)"
    binaries, binary_key, normalizer, login_cmd = ("claude",), "claude_binary", "claude", "claude"
    api_env = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
               "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
    supports_resume = True
    WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

    def binary(self) -> str | None:
        found = super().binary()
        if found:
            return found
        # The official native installer uses ~/.local/bin; a running desktop app may have an older PATH.
        native = Path.home() / ".local" / "bin" / ("claude.exe" if sys.platform.startswith("win") else "claude")
        return str(native) if native.is_file() else None

    def _probe(self) -> dict:
        p = super()._probe()
        if not p.get("ok"):
            return p
        code, output = run_cli(node_argv(self.binary(), "@anthropic-ai/claude-code/cli.js") + ["auth", "status", "--json"], 20)
        try:
            auth = json.loads(output)
            if isinstance(auth, dict) and isinstance(auth.get("loggedIn"), bool):
                # The status may include an email / organization. Retain only the fields needed by the health check.
                p["auth"] = {k: auth.get(k) for k in ("loggedIn", "authMethod", "apiProvider")}
                p["auth_code"] = code
        except ValueError:
            pass  # older CLI versions have no auth status command: report UNKNOWN until the first request
        return p

    def auth_state(self, probe: dict) -> tuple[str, str]:
        auth = probe.get("auth")
        if not auth:
            return super().auth_state(probe)
        if not auth["loggedIn"]:
            return "AUTH_EXPIRED", "run `claude auth login` (Claude subscription sign-in)"
        method = auth.get("authMethod")
        if method in ("api_key", "api_key_helper", "third_party") and not self.api_fallback():
            return "ERROR", "Claude Code uses API billing. Sign in with a Claude subscription or enable claude_code_api_fallback."
        if probe.get("auth_code") == 0 and (method in ("claude.ai", "oauth_token") or self.api_fallback()):
            return "CONNECTED", "sign-in configured (model access is verified by the first request)"
        return super().auth_state(probe)

    def setup(self) -> list:
        return ["Install Claude Code (https://code.claude.com/docs)", "run `claude` once and sign in with your Claude account (/login)"]

    def argv(self, context: dict) -> list:
        args = [self.binary(), "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages"]
        if context.get("mcp_url"):
            cfg = {"mcpServers": {"phd-research-lab": {"type": "http", "url": context["mcp_url"]}}}
            if context.get("mcp_token"):
                cfg["mcpServers"]["phd-research-lab"]["headers"] = {"Authorization": f"Bearer {context['mcp_token']}"}
            f = Path(tempfile.gettempdir()) / f"phdlab-mcp-{secrets.token_hex(4)}.json"
            f.write_text(json.dumps(cfg), "utf-8")
            context["_tmpfile"] = str(f)  # removed when the request ends
            tools = context["mcp_tools"] if "mcp_tools" in context else READ_TOOLS  # v4.2: the session's MCP allowlist
            args += ["--mcp-config", str(f), "--allowedTools", ",".join(f"mcp__phd-research-lab__{t}" for t in tools)]
        if context.get("profile") == "assisted":  # writes only inside the session workspace (permission rules)
            args += ["--permission-mode", "acceptEdits", "--disallowedTools", "Bash"]
        else:  # review: no shell, no file writes
            args += ["--disallowedTools", ",".join(("Bash",) + self.WRITE_TOOLS)]
        if context.get("resume_session") and re.fullmatch(r"[\w-]{6,80}", context["resume_session"]):
            args += ["--resume", context["resume_session"]]
        if context.get("model"):
            args += ["--model", str(context["model"])[:80]]
        return args

class AntigravityConnector(CLIConnector):
    provider_id, label, vendor = "antigravity", "Google Antigravity (MCP + agy CLI)", "Google"
    path = "Antigravity IDE/app as MCP client (mcp_config.json) and the Antigravity CLI `agy -p` (Google sign-in)"
    binaries, normalizer, login_cmd = ("agy",), "agy", "agy"
    supports_resume = True
    api_env = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_APPLICATION_CREDENTIALS")

    def config_path(self) -> Path:
        return Path.home() / ".gemini" / "config" / "mcp_config.json"

    def mcp_registered(self) -> bool:
        try:
            d = json.loads(self.config_path().read_text("utf-8"))
            return "phd-research-lab" in (d.get("mcpServers") or {})
        except (OSError, ValueError):
            return False

    def health(self, fresh: bool = False) -> dict:
        h = super().health(fresh)
        h["mcp_registered"] = self.mcp_registered()
        if h["state"] == "UNAVAILABLE" and h["mcp_registered"]:
            h.update(state="CONNECTED", detail="MCP client path configured (agy CLI not installed: headless send not available)")
        return h

    def capabilities(self) -> dict:
        c = super().capabilities()
        if not cached(f"gw:{self.provider_id}:{self.binary()}", 60, self._probe).get("bin"):
            c.update(send=NOT_SUPPORTED, stream=NOT_SUPPORTED, cancel=NOT_SUPPORTED)
        return c

    def setup(self) -> list:
        return ["Install Google Antigravity (https://antigravity.google)", "sign in with your Google account (run `agy` once)",
                "register the PhD-Lab MCP server (Gateway → Antigravity → Register MCP)"]

    def argv(self, context: dict) -> list:
        args = [self.binary(), "--output-format", "stream-json", "--input-format", "stream-json", "--sandbox", "--print="]
        if context.get("model"):
            args += ["--model", str(context["model"])[:80]]
        if context.get("resume_session") and re.fullmatch(r"[\w-]{6,80}", context["resume_session"]):
            args += ["--conversation", context["resume_session"]]
        return args

    def stdin_payload(self, message: str, context: dict) -> str:
        return json.dumps({"event": "user", "message": {"content": message}}) + "\n"

class GeminiCliConnector(CLIConnector):
    provider_id, label, vendor = "gemini_cli", "Gemini CLI", "Google"
    path = "Gemini CLI signed in with a Google account (being replaced by the Antigravity CLI for some account types)"
    binaries, binary_key, normalizer, login_cmd = ("gemini",), "gemini_binary", "gemini", "gemini"
    api_env = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_APPLICATION_CREDENTIALS")
    supports_resume = True

    def _probe(self) -> dict:
        probe = super()._probe()
        home = Path(os.environ.get("GEMINI_CLI_HOME") or Path.home())
        try:
            settings = json.loads((home / ".gemini" / "settings.json").read_text("utf-8"))
            method = settings.get("security", {}).get("auth", {}).get("selectedType")
        except (OSError, ValueError, AttributeError):
            method = None
        probe['auth_configured'] = bool(method)
        return probe

    def auth_state(self, probe: dict) -> tuple[str, str]:
        if probe.get('auth_configured') is False and not self.api_fallback():
            return "AUTH_EXPIRED", "Gemini CLI has no configured sign-in method. Run `gemini` and choose Login with Google."
        return super().auth_state(probe)

    def setup(self) -> list:
        return ["npm install -g @google/gemini-cli", "run `gemini` once and choose 'Login with Google'"]

    def argv(self, context: dict) -> list:
        args = [self.binary(), "-p", "Answer the research question at the end of the input, using the research context it contains.",
                "--output-format", "stream-json"]
        if context.get("model"):
            args += ["--model", str(context["model"])[:80]]
        if context.get("resume_session") and re.fullmatch(r"[\w-]{6,80}", context["resume_session"]):
            args += ["--resume", context["resume_session"]]
        return args

ALL_API_ENV = set(CodexConnector.api_env) | set(ClaudeCodeConnector.api_env) | set(AntigravityConnector.api_env)     | set(GeminiCliConnector.api_env)
CONNECTORS = {c.provider_id: c for c in (CodexConnector(), ClaudeCodeConnector(), AntigravityConnector(), GeminiCliConnector())}


def get(pid: str) -> ProviderConnector:
    if pid not in CONNECTORS:
        raise ProviderError(f"Unknown provider '{pid}' (known: {', '.join(CONNECTORS)})")
    return CONNECTORS[pid]
