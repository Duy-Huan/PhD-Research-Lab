"""Coding-agent backends (v3.2) — PhD_Research_Lab_Codex_Integration_Upgrade_Prompt.md.

    AgentBackend
      ├── built-in co-coding agent (coder.py + /api/ide/agent, any LLM incl. Claude) — unchanged, still the default
      └── CodexBackend   OpenAI Codex CLI in non-interactive mode: `codex exec --json --sandbox <mode> -`

Verified against the official non-interactive docs (developers.openai.com/codex/noninteractive → learn.chatgpt.com):
  • `codex exec` defaults to a read-only sandbox; `--sandbox workspace-write` allows edits; `--json` turns stdout into
    JSON Lines events (thread.started{thread_id}, turn.started, item.started/item.completed{item}, turn.completed{usage},
    turn.failed, error); `-` reads the prompt from stdin; `codex exec resume <SESSION_ID>` continues a session.
  • Auth: saved `codex login` credentials (ChatGPT plan) or CODEX_API_KEY (API billing) — this app never stores either.
Policy here: the workspace is ALWAYS the project's code/ folder; default sandbox read-only; workspace-write only when the
request carries allow_write=true (the UI asks the researcher); danger-full-access is never used. Non-interactive mode
cannot ask for approvals, so the permission mode is fixed before the run and recorded with it.
Changed files are taken from `git status` before/after (labelled "git-derived"), not from the agent's claims.
"""
from __future__ import annotations

import json
import re
import secrets
import subprocess
import sys
from pathlib import Path
import threading
import time
from collections import deque

from ..config import data_dir, load_config
from .base import NO_WINDOW, IntegrationError, IntegrationStatus, cached, run_cli, which

SANDBOX_MODES = ("read-only", "workspace-write")
RUNS: dict = {}
_lock = threading.Lock()
ID_RE = re.compile(r"^cx-[0-9a-f]{10}$")


def _runs_dir():
    d = data_dir() / "agent_runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


class CodexBackend:
    name = "codex"
    label = "OpenAI Codex CLI"

    def __init__(self, cfg: dict | None = None):
        self.cfg = (cfg or load_config())["codex"]

    def binary(self) -> str | None:
        b = (self.cfg.get("binary") or "").strip()
        return b if b and re.search(r"codex", b, re.I) else which("codex")

    def argv(self) -> list:
        """Command prefix. On Windows npm installs a codex.cmd shim; arguments passed through a batch file are re-parsed by
        cmd.exe, so the shim's own target is used instead: node <npm>/node_modules/@openai/codex/bin/codex.js."""
        b = self.binary()
        if not b:
            return []
        p = Path(b)
        if p.suffix.lower() in (".cmd", ".bat", ".ps1", "") and sys.platform.startswith("win"):
            js = p.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            node = p.parent / "node.exe" if (p.parent / "node.exe").is_file() else which("node")
            if js.is_file() and node:
                return [str(node), str(js)]
        return [b]

    def _probe(self) -> dict:
        pre = self.argv()
        if not pre:
            return {"bin": None}
        b = " ".join(pre)
        code, out = run_cli(pre + ["--version"], 20)
        lc, lout = run_cli(pre + ["login", "status"], 20)
        return {"bin": b, "ok": code == 0, "version": out.strip().splitlines()[-1] if out.strip() else "",
                "auth": "logged in" if lc == 0 else ("unknown" if lc in (124, 126, 127) else "not logged in"),
                "auth_detail": re.sub(r"(sk-[A-Za-z0-9_-]{4})[A-Za-z0-9_-]+", r"\1…", lout.strip())[-160:]}

    def status(self) -> IntegrationStatus:
        setup = ["npm install -g @openai/codex   (Node.js 18+)", "codex login   (ChatGPT plan)  — or set CODEX_API_KEY for API billing",
                 "Control Center → Integrations → enable Codex"]
        if not self.cfg.get("enabled"):
            return IntegrationStatus("codex", self.label, "disabled", "Disabled in the configuration.", setup=setup)
        p = cached("codex", 60, self._probe)
        if not p["bin"]:
            return IntegrationStatus("codex", self.label, "unavailable", "The `codex` CLI was not found on PATH.", setup=setup)
        if not p["ok"]:
            return IntegrationStatus("codex", self.label, "error", "`codex --version` failed", setup=setup)
        if p["auth"] == "not logged in":
            return IntegrationStatus("codex", self.label, "unconfigured", "Authentication required: run `codex login`.",
                                     version=p["version"], setup=setup)
        return IntegrationStatus("codex", self.label, "available", f"auth: {p['auth']}", version=p["version"],
                                 capabilities=["start_run", "stream_events", "cancel_run", "resume_run", "status"],
                                 extra={"sandbox_modes": list(SANDBOX_MODES), "default_sandbox": self.cfg.get("sandbox", "read-only")})

    # ---- runs
    def start_run(self, prompt: str, allow_write: bool = False, model: str = "", resume_thread: str = "",
                  link: dict | None = None) -> dict:
        st = self.status()
        if not st.ok:
            raise IntegrationError(f"Codex is {st.state}: {st.detail}")
        prompt = (prompt or "").strip()
        if not prompt:
            raise IntegrationError("Describe the coding task")
        from ..sandbox import code_dir
        mode = "workspace-write" if allow_write else "read-only"  # never danger-full-access
        mdl = ["-m", (model or self.cfg["model"])[:80]] if (model or self.cfg.get("model")) else []
        ws = self.cfg.get("windows_sandbox") or "unelevated"
        if sys.platform.startswith("win") and ws != "config":  # without a Windows sandbox backend every shell command is blocked
            mdl += ["-c", f"windows.sandbox={ws}"]
        if resume_thread:  # `codex exec resume` has no --sandbox flag: the policy is passed as a config override
            if not re.fullmatch(r"[\w-]{6,80}", resume_thread):
                raise IntegrationError("Invalid session id")
            args = self.argv() + ["exec", "resume", "--json", "-c", f"sandbox_mode={mode}", "--skip-git-repo-check"] + mdl + [resume_thread, "-"]
        else:
            args = self.argv() + ["exec", "--json", "--sandbox", mode, "--skip-git-repo-check", "-C", str(code_dir())] + mdl + ["-"]
        rid = "cx-" + secrets.token_hex(5)
        from .. import gitops
        before = _git_snapshot(gitops)
        run = {"id": rid, "provider": "codex", "status": "starting", "permission_mode": mode, "prompt": prompt[:4000],
               "workspace": str(code_dir()), "git_before": before.get("head", {}), "started": time.time(), "ended": None,
               "thread_id": resume_thread or "", "final_message": "", "usage": {}, "errors": [], "events": deque(maxlen=400),
               "changed_files": [], "changed_files_source": "git-derived", "link": link or {}, "proc": None, "cancelled": False}
        try:
            from ..gateway.connectors import CodexConnector
            from ..gateway.workspace import minimal_env  # v4.1: allowlisted env — other vendors' keys and secrets stay out
            proc = subprocess.Popen(args, cwd=str(code_dir()), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=NO_WINDOW,
                                    env=minimal_env(set(CodexConnector.api_env)))
        except OSError as e:
            raise IntegrationError(f"Could not start codex: {e}")
        run["proc"], run["status"] = proc, "running"
        with _lock:
            RUNS[rid] = run
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except OSError:
            pass
        threading.Thread(target=self._pump, args=(run, before), daemon=True).start()
        threading.Thread(target=_drain_stderr, args=(run,), daemon=True).start()
        timeout = int(self.cfg.get("timeout_s") or 1800)
        watchdog = threading.Timer(timeout, lambda: run["status"] == "running" and self.cancel_run(rid, reason=f"time limit {timeout} s"))
        watchdog.daemon = True  # never keeps the app (or a test process) alive
        watchdog.start()
        run["watchdog"] = watchdog
        _persist(run)
        return public(run)

    def _pump(self, run: dict, before: dict):
        proc = run["proc"]
        for line in iter(proc.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                run["events"].append({"type": "text", "text": line[:500]})
                continue
            apply_event(run, ev)
        proc.wait()
        from .. import gitops
        after = _git_snapshot(gitops)
        run["git_after"] = after.get("head", {})
        # git-derived: files that became dirty during the run, and everything uncommitted afterwards
        run["changed_files"] = sorted(set(after.get("files", [])) - set(before.get("files", [])))
        run["dirty_after"] = sorted(after.get("files", []))
        run["exit_code"] = proc.returncode
        run["ended"] = time.time()
        if run.get("watchdog"):
            run["watchdog"].cancel()
        if run["cancelled"]:
            run["status"] = "cancelled"
        elif run["status"] in ("running", "starting"):
            run["status"] = "completed" if proc.returncode == 0 and not run["errors"] else "failed"
        _persist(run)
        try:
            from ..memory.working import set_agent_state
            set_agent_state("codex", run["status"], f"{run['id']}: {run['prompt'][:120]}")
        except Exception:
            pass

    def cancel_run(self, rid: str, reason: str = "cancelled by the researcher") -> dict:
        run = RUNS.get(rid)
        if not run or run["status"] not in ("running", "starting"):
            raise IntegrationError("Run is not active")
        run["cancelled"] = True
        run["errors"].append(reason)
        p = run["proc"]
        try:
            if p and p.poll() is None:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, creationflags=NO_WINDOW) \
                    if sys.platform.startswith("win") else p.terminate()
        except Exception:
            pass
        return public(run)


def apply_event(run: dict, ev: dict) -> None:
    """Map one Codex JSONL event onto the run record (unknown events are kept verbatim, truncated)."""
    t = ev.get("type", "")
    item = ev.get("item") or {}
    if t == "thread.started":
        run["thread_id"] = ev.get("thread_id", run["thread_id"])
    elif t == "turn.completed":
        run["usage"] = ev.get("usage") or {}
    elif t in ("turn.failed", "error"):
        err = ev.get("error")
        msg = ev.get("message") or (err.get("message") if isinstance(err, dict) else err)
        run["errors"].append(str(msg or t)[:500])
        run["status"] = "failed"
    elif t == "item.completed" and item.get("type") == "agent_message":
        run["final_message"] = item.get("text", "")
    compact = {"type": t}
    if item:
        compact["item"] = {k: (str(v)[:400] if isinstance(v, str) else v) for k, v in item.items() if k in ("id", "type", "status", "command", "text", "exit_code")}
    run["events"].append(compact)


def _drain_stderr(run: dict):
    for line in iter(run["proc"].stderr.readline, ""):
        if line.strip():
            run["events"].append({"type": "stderr", "text": line.strip()[:300]})


def _git_snapshot(gitops) -> dict:
    try:
        st = gitops.status()
        return {"head": gitops.head_info(), "files": [f["path"] for f in st.get("files", [])],
                "modified": [f["path"] for f in st.get("files", []) if f.get("status") in ("modified", "added", "deleted", "renamed")]}
    except Exception:
        return {}


def public(run: dict) -> dict:
    out = {k: v for k, v in run.items() if k not in ("proc", "events", "watchdog")}
    out["events"] = list(run["events"])[-200:]
    return out


def _persist(run: dict) -> None:
    try:
        (_runs_dir() / f"{run['id']}.json").write_text(json.dumps(public(run), indent=1, default=str), "utf-8")
    except OSError:
        pass


def get_run(rid: str) -> dict:
    if not ID_RE.match(rid or ""):
        raise IntegrationError("Invalid run id")
    if rid in RUNS:
        return public(RUNS[rid])
    f = _runs_dir() / f"{rid}.json"
    if not f.exists():
        raise IntegrationError("Run not found")
    try:
        return json.loads(f.read_text("utf-8"))
    except (OSError, ValueError):
        raise IntegrationError("The run record is damaged (interrupted write)")


def list_runs(limit: int = 30) -> list:
    out = []
    for f in sorted(_runs_dir().glob("cx-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        try:
            d = json.loads(f.read_text("utf-8"))
            out.append({k: d.get(k) for k in ("id", "status", "permission_mode", "prompt", "started", "ended", "thread_id", "changed_files")})
        except (OSError, ValueError):
            continue
    return out
