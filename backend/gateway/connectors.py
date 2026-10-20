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
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from ..integrations.base import NO_WINDOW, cached, run_cli, which
from . import events as E

HEALTH = ("CONNECTED", "DISCONNECTED", "AUTH_EXPIRED", "RATE_LIMITED", "UNAVAILABLE", "ERROR", "UNKNOWN")
NOT_SUPPORTED = "NOT_SUPPORTED"
CAPS = ("connect", "disconnect", "health", "capabilities", "send", "stream", "cancel", "mcp_client")
RATE_RE = re.compile(r"(?i)rate.?limit|429|quota|usage limit|too many requests")
AUTH_RE = re.compile(r"(?i)authenticat|not logged in|login required|sign.?in|unauthori[sz]ed|401|expired")
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
    from ..config import load_config
    return load_config()["gateway"]


def _drain(stream, out: list) -> None:
    try:
        for line in iter(stream.readline, ""):
            if line.strip():
                out.append(line.strip()[:300])
    except (ValueError, OSError):  # pipe closed when the request ended
        pass


class ProviderConnector:
    provider_id = ""
    label = ""
    vendor = ""
    path = ""            # the officially supported integration path, shown in the UI
    api_env: tuple = ()  # vendor API-key variables removed by the cost guard

    def enabled(self) -> bool:
        return bool(_gw().get(f"{self.provider_id}_enabled", True))

    def api_fallback(self) -> bool:
        return bool(_gw().get(f"{self.provider_id}_api_fallback", False))

    def capabilities(self) -> dict:
        return {c: NOT_SUPPORTED for c in CAPS} | {"health": True, "capabilities": True}

    def health(self) -> dict:
        return {"provider": self.provider_id, "state": "UNKNOWN", "detail": ""}

    def connect(self, launch: bool = False) -> dict:
        raise ProviderError(NOT_SUPPORTED)

    def disconnect(self, revoke: bool = False) -> dict:
        from ..config import save_config
        save_config({"gateway": {f"{self.provider_id}_enabled": False}})
        return {"provider": self.provider_id, "state": "DISCONNECTED",
                "detail": "PhD-Lab will no longer use this provider. Its own sign-in is unchanged (sign out in the vendor's app/CLI)."}

    def start_session(self, context: dict) -> dict:
        return {"provider": self.provider_id, "session_id": "", "note": "sessions are created on the first message"}

    def send_message(self, message: str, context: dict) -> dict:
        text, final, usage, session, errors = [], "", {}, "", []
        for e in self.stream_message(message, context):
            if e["type"] == "text_delta":
                text.append(e.get("text", ""))
                if e.get("final"):
                    final = e.get("text", "")
            elif e["type"] == "status" and e.get("state") == "result":
                final, usage = e.get("final_text", final), e.get("usage", usage)
            elif e["type"] == "status" and e.get("state") == "session":
                session = e.get("session_id", session)
            elif e["type"] == "error":
                errors.append(e.get("message", ""))
        return {"provider": self.provider_id, "text": final or "".join(text), "usage": usage, "session_id": session, "errors": errors}

    def stream_message(self, message: str, context: dict):
        raise ProviderError(f"{self.label}: {NOT_SUPPORTED}", "ERROR")

    def cancel(self, request_id: str) -> dict:
        return {"provider": self.provider_id, "cancelled": False, "detail": NOT_SUPPORTED}

    def mcp_registration(self, base_url: str, token: str = "") -> dict:
        return {"provider": self.provider_id, "supported": False}


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
        """Cost guard: the API-key variables of EVERY AI vendor are removed (an agent could otherwise spend another
        vendor's key through a shell command); the provider's own ones stay only with <provider>_api_fallback."""
        env = dict(os.environ)
        keep = set(self.api_env) if self.api_fallback() else set()
        for k in ALL_API_ENV - keep:
            env.pop(k, None)
        env["NO_COLOR"] = "1"
        return env

    def _probe(self) -> dict:
        b = self.binary()
        if not b:
            return {"bin": None}
        code, out = run_cli([b, "--version"], 20)
        return {"bin": b, "ok": code == 0, "version": (out.strip().splitlines() or [""])[-1][:80]}

    def auth_state(self, probe: dict) -> tuple[str, str]:
        """(state, detail) — CLIs without a status command are UNKNOWN until the first request proves the sign-in."""
        return "UNKNOWN", "signed-in state is verified by the first request"

    def health(self) -> dict:
        base = {"provider": self.provider_id, "label": self.label, "path": self.path,
                "billing": "API key (fallback enabled)" if self.api_fallback() else "subscription sign-in only (API keys removed)",
                "api_fallback": self.api_fallback()}
        if not self.enabled():
            return {**base, "state": "DISCONNECTED", "detail": "disabled in PhD-Lab (gateway settings)"}
        p = cached(f"gw:{self.provider_id}:{self.binary()}", 60, self._probe)
        if not p.get("bin"):
            return {**base, "state": "UNAVAILABLE", "detail": f"`{self.binaries[0]}` CLI not found on PATH", "setup": self.setup()}
        if not p.get("ok"):
            return {**base, "state": "ERROR", "detail": f"`{self.binaries[0]} --version` failed", "setup": self.setup()}
        state, detail = self.auth_state(p)
        last = _last_error.get(self.provider_id)
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
        if launch and sys.platform.startswith("win") and self.binary():
            subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k", self.login_cmd], creationflags=NO_WINDOW)
            out["launched"] = True
        _last_error.pop(self.provider_id, None)
        from ..config import save_config
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
        args = self.argv(context)
        from ..sandbox import code_dir
        try:
            proc = subprocess.Popen(args, cwd=str(code_dir()), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1, env=self.env(), creationflags=NO_WINDOW)
        except OSError as e:
            raise ProviderError(f"Could not start {self.binaries[0]}: {e}", "UNAVAILABLE")
        with _lock:
            _procs[rid] = proc
        err_lines: list = []
        threading.Thread(target=_drain, args=(proc.stderr, err_lines), daemon=True).start()
        yield E.ev("request_started", provider=self.provider_id, request_id=rid)
        try:
            try:
                proc.stdin.write(self.stdin_payload(message, context))
                proc.stdin.close()
            except OSError:
                pass
            norm = E.NORMALIZERS[self.normalizer]
            errored = False
            for line in iter(proc.stdout.readline, ""):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except ValueError:
                    yield E.ev("text_delta", text=line + "\n")
                    continue
                for e in norm(raw) if isinstance(raw, dict) else []:
                    if e["type"] == "error":
                        errored = True
                        st = classify_error(e.get("message", ""))
                        if st != "ERROR":
                            _last_error[self.provider_id] = (st, e.get("message", "")[:200])
                    yield e
            proc.wait()
            cancelled = getattr(proc, "_phd_cancelled", False)
            if cancelled:
                yield E.ev("request_cancelled", provider=self.provider_id, request_id=rid)
                return
            if proc.returncode != 0 and not errored:
                msg = " | ".join(err_lines[-3:]) or f"exit code {proc.returncode}"
                st = classify_error(msg)
                if st != "ERROR":
                    _last_error[self.provider_id] = (st, msg[:200])
                yield E.ev("error", message=msg[:500], state=st)
            elif not errored:
                _last_error.pop(self.provider_id, None)
            yield E.ev("request_completed", provider=self.provider_id, request_id=rid, exit_code=proc.returncode)
        finally:
            with _lock:
                _procs.pop(rid, None)
            for f in (proc.stdout, proc.stderr):
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
        try:
            if sys.platform.startswith("win"):
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, creationflags=NO_WINDOW)
            else:
                p.terminate()
        except Exception:
            pass
        return {"provider": self.provider_id, "cancelled": True}


class CodexConnector(CLIConnector):
    provider_id, label, vendor = "codex", "ChatGPT (OpenAI Codex CLI)", "OpenAI"
    path = "Codex CLI signed in with a ChatGPT plan (`codex login`)"
    binaries, normalizer, login_cmd = ("codex",), "codex", "codex login"
    api_env = ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY")

    def binary(self):
        from ..integrations.agents import CodexBackend
        return CodexBackend().binary()

    def _prefix(self) -> list:
        from ..integrations.agents import CodexBackend
        return CodexBackend().argv()

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
        args = self._prefix() + ["exec", "--json", "--sandbox", "read-only", "--skip-git-repo-check"]
        if sys.platform.startswith("win"):
            from ..config import load_config
            ws = load_config()["codex"].get("windows_sandbox") or "unelevated"
            if ws != "config":
                args += ["-c", f"windows.sandbox={ws}"]
        if context.get("resume_session") and re.fullmatch(r"[\w-]{6,80}", context["resume_session"]):
            args = self._prefix() + ["exec", "resume", "--json", "-c", "sandbox_mode=read-only", "--skip-git-repo-check",
                                     context["resume_session"]]
        if context.get("model"):
            args += ["-m", str(context["model"])[:80]]
        return args + ["-"]

    def mcp_registration(self, base_url: str, token: str = "") -> dict:
        bridge = str(Path(__file__).resolve().parents[2] / "mcp_stdio_bridge.py").replace("\\", "/")
        env = f'env = {{ PHDLAB_MCP_URL = "{base_url}/mcp"' + (', PHDLAB_MCP_TOKEN = "<token>"' if token else "") + " }"
        return {"provider": self.provider_id, "supported": True, "file": "~/.codex/config.toml",
                "snippet": f'[mcp_servers.phd-research-lab]\ncommand = "python"\nargs = ["{bridge}"]\n{env}\n'}


class ClaudeCodeConnector(CLIConnector):
    provider_id, label, vendor = "claude_code", "Claude (Claude Code CLI)", "Anthropic"
    path = "Claude Code CLI signed in with a Claude subscription (`claude`, then /login)"
    binaries, binary_key, normalizer, login_cmd = ("claude",), "claude_binary", "claude", "claude"
    api_env = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
               "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")

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
            args += ["--mcp-config", str(f), "--allowedTools", ",".join(f"mcp__phd-research-lab__{t}" for t in READ_TOOLS)]
        if context.get("resume_session") and re.fullmatch(r"[\w-]{6,80}", context["resume_session"]):
            args += ["--resume", context["resume_session"]]
        if context.get("model"):
            args += ["--model", str(context["model"])[:80]]
        return args

    def mcp_registration(self, base_url: str, token: str = "") -> dict:
        hdr = ' --header "Authorization: Bearer <token>"' if token else ""
        return {"provider": self.provider_id, "supported": True,
                "command": f"claude mcp add --transport http phd-research-lab {base_url}/mcp{hdr}"}


class AntigravityConnector(CLIConnector):
    provider_id, label, vendor = "antigravity", "Google Antigravity (MCP + agy CLI)", "Google"
    path = "Antigravity IDE/app as MCP client (mcp_config.json) and the Antigravity CLI `agy -p` (Google sign-in)"
    binaries, normalizer, login_cmd = ("agy",), "agy", "agy"
    api_env = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_APPLICATION_CREDENTIALS")

    def config_path(self) -> Path:
        return Path.home() / ".gemini" / "config" / "mcp_config.json"

    def mcp_registered(self) -> bool:
        try:
            d = json.loads(self.config_path().read_text("utf-8"))
            return "phd-research-lab" in (d.get("mcpServers") or {})
        except (OSError, ValueError):
            return False

    def health(self) -> dict:
        h = super().health()
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
        args = [self.binary(), "-p", "--output-format", "stream-json", "--input-format", "stream-json", "--sandbox"]
        if context.get("model"):
            args += ["--model", str(context["model"])[:80]]
        if context.get("resume_session") and re.fullmatch(r"[\w-]{6,80}", context["resume_session"]):
            args += ["--conversation", context["resume_session"]]
        return args

    def stdin_payload(self, message: str, context: dict) -> str:
        return json.dumps({"event": "user", "message": {"content": message}}) + "\n"

    def mcp_registration(self, base_url: str, token: str = "") -> dict:
        entry = {"serverUrl": f"{base_url}/mcp"}
        if token:
            entry["headers"] = {"Authorization": "Bearer <token>"}
        return {"provider": self.provider_id, "supported": True, "file": str(self.config_path()),
                "workspace_file": ".agents/mcp_config.json", "snippet": {"mcpServers": {"phd-research-lab": entry}}}

    def register_mcp(self, base_url: str, token: str = "") -> dict:
        """Explicit researcher action: merge our server into ~/.gemini/config/mcp_config.json (a .bak copy is kept)."""
        p = self.config_path()
        d = {}
        if p.exists():
            try:
                d = json.loads(p.read_text("utf-8"))
            except ValueError:
                raise ProviderError(f"{p} is not valid JSON — fix or remove it first")
            p.with_suffix(".json.bak").write_text(p.read_text("utf-8"), "utf-8")
        entry = {"serverUrl": f"{base_url}/mcp"}
        if token:
            entry["headers"] = {"Authorization": f"Bearer {token}"}
        d.setdefault("mcpServers", {})["phd-research-lab"] = entry
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, indent=2), "utf-8")
        return {"provider": self.provider_id, "registered": True, "file": str(p)}


class GeminiCliConnector(CLIConnector):
    provider_id, label, vendor = "gemini_cli", "Gemini CLI", "Google"
    path = "Gemini CLI signed in with a Google account (being replaced by the Antigravity CLI for some account types)"
    binaries, binary_key, normalizer, login_cmd = ("gemini",), "gemini_binary", "gemini", "gemini"
    api_env = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_APPLICATION_CREDENTIALS")

    def setup(self) -> list:
        return ["npm install -g @google/gemini-cli", "run `gemini` once and choose 'Login with Google'"]

    def argv(self, context: dict) -> list:
        args = [self.binary(), "-p", "Answer the research question at the end of the input, using the research context it contains.",
                "--output-format", "stream-json"]
        if context.get("model"):
            args += ["--model", str(context["model"])[:80]]
        return args

    def mcp_registration(self, base_url: str, token: str = "") -> dict:
        entry = {"httpUrl": f"{base_url}/mcp"}
        if token:
            entry["headers"] = {"Authorization": "Bearer <token>"}
        return {"provider": self.provider_id, "supported": True, "file": "~/.gemini/settings.json",
                "snippet": {"mcpServers": {"phd-research-lab": entry}}}


ALL_API_ENV = set(CodexConnector.api_env) | set(ClaudeCodeConnector.api_env) | set(AntigravityConnector.api_env)     | set(GeminiCliConnector.api_env)
CONNECTORS = {c.provider_id: c for c in (CodexConnector(), ClaudeCodeConnector(), AntigravityConnector(), GeminiCliConnector())}


def get(pid: str) -> ProviderConnector:
    if pid not in CONNECTORS:
        raise ProviderError(f"Unknown provider '{pid}' (known: {', '.join(CONNECTORS)})")
    return CONNECTORS[pid]


def chatgpt_web_note() -> dict:
    """ChatGPT (web/desktop) custom MCP connectors are called from OpenAI's servers, so they need a PUBLIC HTTPS endpoint.
    PhD-Lab binds to 127.0.0.1 and does not open tunnels; this path is documented, not automated."""
    return {"provider": "chatgpt_web", "supported": False,
            "detail": "ChatGPT developer-mode connectors require a public HTTPS /mcp endpoint. PhD-Lab is local-only by design; "
                      "use the Codex CLI path (ChatGPT plan) instead, or expose /mcp yourself through a tunnel WITH an MCP token "
                      "(see docs/integrations/chatgpt.md)."}
