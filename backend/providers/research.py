"""Research providers: the parallel back-ends the orchestrator hands SCOPED tasks to (architecture: chatbox → primary
research orchestrator → shared context memory + research state → providers → reliability layer).

    category      id            what it does here
    research      feynman       Feynman CLI workflows (lit, deepresearch, compare, review, summarize, draft, recipe)
    research      app           the app's own model, agent "research" or "reviewer" (always available as fallback)
    coding        claude_code   Claude Code CLI · codex · gemini_cli · antigravity (subscription sign-in, own workspace)
    experiment    python        Python venv of the active code project on this PC (default execution)
    experiment    docker        Linux container — only for tasks that need Linux (needs_linux)
    experiment    clearml       offline experiment tracking of every run (no server)
    publication   latex         LaTeX → PDF (tectonic / latexmk / pdflatex)
    publication   paperorchestra PaperOrchestra Multi-Agent Research Writing Engine

PhD-Lab owns the research state; a provider only receives one task with its scope, inputs and limits, runs in its own
session workspace (never the project folder) and returns text + files. Nothing a provider writes changes the project
until the researcher accepts it. A provider that is not set up is reported honestly (NOT_CONFIGURED + the command that
fixes it) and the task falls back to the app's own model with a visible note — never silently.
"""
from __future__ import annotations

import re
import os
import json
import hashlib
import shutil
import subprocess
import threading
import time
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
FEYNMAN_WORKFLOWS = ("lit", "deepresearch", "compare", "review", "summarize", "draft", "recipe", "audit")
OUT_EXT = {".md", ".txt", ".csv", ".json", ".bib", ".tex", ".pdf", ".png", ".svg", ".py", ".yaml", ".yml"}
CODING = ("claude_code", "codex", "gemini_cli", "antigravity")
CATALOG = {
    "feynman": ("research", "Feynman (AI research agent)"),
    "openscience": ("research", "OpenScience (external research runtime)"),
    "phdlab": ("research", "PhD Lab Native (Toàn bộ Agent nội bộ của PhD Lab)"),
    "app": ("research", "Mô hình của ứng dụng (agent Research / Reviewer)"),
    "claude_code": ("coding", "Claude Code"),
    "codex": ("coding", "OpenAI Codex"),
    "gemini_cli": ("coding", "Gemini CLI"),
    "antigravity": ("coding", "Google Antigravity"),
    "opencode": ("coding", "OpenCode Sandbox Thực nghiệm"),
    "python": ("experiment", "Python venv (máy này)"),
    "docker": ("experiment", "Docker (Linux, chạy ngầm khi cần)"),
    "clearml": ("experiment", "ClearML (offline tracking)"),
    "latex": ("publication", "LaTeX → PDF"),
    "paperorchestra": ("publication", "PaperOrchestra (Multi-Agent Research Writing Engine)"),
}
_health: dict = {}


class ProviderUnavailable(Exception):
    pass


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text or "").replace("\r", "")


def _cfg() -> dict:
    from backend.core.config import load_config
    return load_config()


def _rp(cfg: dict | None = None) -> dict:
    return (cfg or _cfg()).get("research_providers") or {}


# ------------------------------------------------------------------ health
def _feynman_health(cfg: dict) -> dict:
    from backend.execution.tools import run_cli, which
    if _rp(cfg).get("feynman_enabled") is False:
        return {"state": "DISABLED", "detail": "tắt trong Cài đặt → Providers"}
    b = which("feynman")
    if not b:
        return {"state": "UNAVAILABLE", "detail": "không tìm thấy lệnh `feynman`",
                "setup": ["irm https://feynman.is/install.ps1 | iex"]}
    code, out = run_cli([b, "status"], 40)
    text = strip_ansi(out)
    m = re.search(r"Model valid:\s*(\w+)", text)
    model = re.search(r"Model:\s*(.+)", text)
    if m and m.group(1).lower() == "yes":
        return {"state": "READY", "detail": f"model {model.group(1).strip() if model else '?'}", "bin": b}
    if _shared_key(cfg):
        return {"state": "READY", "detail": "dùng API key của ứng dụng (đã cho phép trong Cài đặt)", "bin": b}
    return {"state": "NOT_CONFIGURED", "bin": b,
            "detail": "Feynman chưa có model (Model valid: no)",
            "setup": ["feynman model login", "hoặc bật 'Cho Feynman dùng API key của ứng dụng' trong Cài đặt"]}


def _shared_key(cfg: dict) -> dict:
    """{ENV: key} when the researcher allowed Feynman to use the app's Anthropic / OpenAI key (cost: their API account)."""
    if not _rp(cfg).get("feynman_share_app_key"):
        return {}
    p = cfg.get("providers") or {}
    out = {}
    if (p.get("anthropic") or {}).get("api_key"):
        out["ANTHROPIC_API_KEY"] = p["anthropic"]["api_key"]
    if (p.get("openai") or {}).get("api_key"):
        out["OPENAI_API_KEY"] = p["openai"]["api_key"]
    return out


def _coding_health(pid: str, fresh: bool = False) -> dict:
    from backend.providers.cli import CONNECTORS
    h = CONNECTORS[pid].health(fresh=fresh)
    st = {"CONNECTED": "READY"}.get(h.get("state"), h.get("state") or "UNKNOWN")
    if st == "UNAVAILABLE":
        st = "UNAVAILABLE"
    return {"state": st, "detail": h.get("detail", ""), "setup": h.get("setup") or []}


def _exec_health(pid: str, cfg: dict) -> dict:
    if pid == "python":
        return {"state": "READY", "detail": "venv riêng của từng code project (mặc định)"}
    if pid == "docker":
        from backend.execution.sandbox import docker_exe, docker_running
        if not docker_exe():
            return {"state": "UNAVAILABLE", "detail": "Docker chưa cài — chỉ cần khi tác vụ yêu cầu Linux"}
        return {"state": "READY" if docker_running() else "STOPPED",
                "detail": "chỉ dùng khi tác vụ cần Linux" + ("" if docker_running() else " · Docker Desktop đang tắt")}
    if pid == "clearml":
        import importlib.util
        if not (cfg.get("clearml") or {}).get("enabled"):
            return {"state": "DISABLED", "detail": "tắt trong cấu hình"}
        if importlib.util.find_spec("clearml") is None:
            return {"state": "UNAVAILABLE", "detail": "chưa cài gói clearml — run vẫn được lưu đầy đủ trong dự án",
                    "setup": ["pip install clearml"]}
        return {"state": "READY", "detail": "ghi offline mỗi run vào <dự án>/clearml (không cần server)"}
    from backend.paper.latex import engines
    e = engines()
    found = [k for k, v in e.items() if v]
    return {"state": "READY" if found else "UNAVAILABLE",
            "detail": ", ".join(found) if found else "chưa cài TeX (tectonic / MiKTeX / TeX Live)",
            "setup": [] if found else ["winget install tectonic-typesetting.tectonic"]}


def describe(pid: str, cfg: dict | None = None, fresh: bool = False) -> dict:
    if pid not in CATALOG:
        raise ProviderUnavailable(f"Unknown research provider '{pid}'")
    cfg = cfg or _cfg()
    fingerprint = hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()
    hit = _health.get(pid)
    if hit and len(hit) > 2 and hit[2] == fingerprint and not fresh and time.time() - hit[0] < 60:
        h = hit[1]
    else:
        try:
            if pid == "feynman":
                h = _feynman_health(cfg)
            elif pid == "openscience":
                from backend.research_engines.registry import get
                h = get(pid).health()
            elif pid == "opencode":
                from backend.research_engines.registry import get
                oc_h = get(pid).health()
                h = {
                    "state": "READY" if oc_h.get("ready") else "UNAVAILABLE",
                    "detail": oc_h.get("detail") or ("OpenCode runtime sẵn sàng" if oc_h.get("ready") else "Chưa cài đặt OpenCode CLI"),
                    "setup": ["npm install -g opencode-ai"] if not oc_h.get("installed") else [],
                }
            elif pid == "paperorchestra":
                from backend.research_engines.registry import get
                po_h = get(pid).health()
                h = {
                    "state": po_h["state"],
                    "detail": po_h.get("detail", ""),
                    "setup": po_h.get("setup", []),
                }
            elif pid in ("app", "phdlab"):
                h = {"state": "READY", "detail": "PhD Lab Native Multi-Agent OS (chạy toàn bộ hội đồng Agent nội bộ)"}
            elif pid in CODING:
                h = _coding_health(pid, fresh)
            else:
                h = _exec_health(pid, cfg)
        except Exception as e:  # a broken probe never breaks the registry
            h = {"state": "ERROR", "detail": f"{type(e).__name__}: {e}"[:200]}
        _health[pid] = (time.time(), h, fingerprint)
    cat, label = CATALOG[pid]
    return {"id": pid, "category": cat, "label": label, "state": h["state"],
            "ready": h["state"] == "READY" or (pid in CODING and h["state"] == "UNKNOWN"),
            "detail": h.get("detail", ""), "setup": h.get("setup") or []}


def describe_all(fresh: bool = False) -> list:
    """Every provider, probed in parallel (CLI version / sign-in checks take seconds each)."""
    from concurrent.futures import ThreadPoolExecutor
    cfg = _cfg()
    with ThreadPoolExecutor(max_workers=len(CATALOG)) as ex:
        return list(ex.map(lambda p: describe(p, cfg, fresh), CATALOG))


def pick(preferred: str, category: str = "research") -> tuple[str, str]:
    """(provider id, note) for a task: the preferred provider when READY, else the app model with the reason."""
    want = preferred
    if preferred == "coding":
        want = _rp().get("coding_default") or "claude_code"
    if want in ("app", "phdlab") or want not in CATALOG:
        return want if want in CATALOG else "app", ""
    d = describe(want)
    if d["ready"]:
        return want, ""
    return "app", f"{d['label']}: {d['state']} — {d['detail']} → dùng mô hình của ứng dụng"


# ------------------------------------------------------------------ running tasks
def app_complete(agent: str, system: str, user: str, max_tokens: int = 6000) -> str:
    """One call to the app's model for the given agent (research | reviewer | utility)."""
    import asyncio

    from backend.providers.models import call_agent
    r = asyncio.run(call_agent(agent, system, user, max_tokens=max_tokens, temperature=0.3))
    return (r.get("text") or "").strip()


def _snapshot(d: Path) -> dict:
    return {str(f): f.stat().st_mtime_ns for f in d.rglob("*") if f.is_file()}


def _collect(cwd: Path, before: dict, outdir: Path) -> list:
    outdir.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(cwd.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in OUT_EXT or before.get(str(f)) == f.stat().st_mtime_ns:
            continue
        rel = f.relative_to(cwd)
        dst = outdir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst)
        files.append(str(rel).replace("\\", "/"))
    return files[:200]


def run_feynman(task_id: str, workflow: str, prompt: str, context_text: str, outdir: Path, cancelled=None,
                timeout_s: float = 0) -> dict:
    """One Feynman task in its own session workspace. Returns {text, files}. Raises ProviderUnavailable."""
    from backend.providers import cli_space as W
    from backend.providers.cli import kill_tree
    from backend.execution.tools import NO_WINDOW
    cfg = _cfg()
    h = describe("feynman", cfg, fresh=True)
    if not h["ready"]:
        raise ProviderUnavailable(f"Feynman: {h['state']} — {h['detail']}")
    if workflow and workflow not in FEYNMAN_WORKFLOWS:
        raise ProviderUnavailable(f"Feynman workflow '{workflow}' is not allowed here")
    sess = W.open_session("feynman", re.sub(r"[^\w.-]", "-", task_id)[:60], "assisted",
                          W.check_profile("feynman", "assisted", allow_weaker=True))
    cwd = Path(sess["cwd"])
    (cwd / "PROJECT_CONTEXT.md").write_text(context_text or "(no project context)", "utf-8")
    from backend.providers.firewall import prepare_workspace
    prepare_workspace("feynman", cwd)
    before = _snapshot(cwd)
    from backend.execution.tools import node_argv, which
    pre = node_argv(which("feynman"), "@companion-ai/feynman/bin/feynman.js")
    topic = (prompt or "").strip()[:6000]
    argv = pre + ([workflow, topic] if workflow else ["--prompt", "Read ./PROJECT_CONTEXT.md first.\n\n" + topic])
    env = W.minimal_env() | {"NO_COLOR": "1", "FEYNMAN_TELEMETRY": "off"} | _shared_key(cfg)
    proc = subprocess.Popen(argv, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace", env=env, creationflags=NO_WINDOW,
                            start_new_session=os.name != "nt")
    from collections import deque
    from backend.core.telemetry import redact
    out = deque(maxlen=2048)
    def drain():
        try:
            for line in iter(proc.stdout.readline, ""):
                out.append(redact(line)[:4000])
        except (OSError, ValueError):
            pass
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    limit = timeout_s or float(_rp(cfg).get("feynman_timeout_s") or 1800)
    end = time.time() + limit
    try:
        while proc.poll() is None:
            if (cancelled and cancelled()) or time.time() > end:
                raise ProviderUnavailable("Feynman stopped: " + ("cancelled" if cancelled and cancelled() else f"time limit {int(limit)} s"))
            time.sleep(0.3)
        reader.join(5)
        text = strip_ansi("".join(out)).strip()
        if proc.returncode != 0:
            raise ProviderUnavailable(f"Feynman exit {proc.returncode}: {text[-600:]}")
        return {"text": text, "files": _collect(cwd, before, outdir), "workspace": str(cwd)}
    except Exception:
        kill_tree(proc)
        reader.join(5)
        files = _collect(cwd, before, outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "interrupted.json").write_text(json.dumps({"task_id": task_id, "workflow": workflow,
            "workspace": str(cwd), "files": files, "status": "interrupted", "native_resume_verified": False}), "utf-8")
        (outdir / "partial-output.txt").write_text(strip_ansi("".join(out)), "utf-8")
        raise
    finally:
        kill_tree(proc)
        reader.join(5)
        proc.stdout.close()


def run_coding(task_id: str, pid: str, prompt: str, context_text: str, outdir: Path, cancelled=None) -> dict:
    """A coding task on a CLI provider (assisted profile: writes only inside its own session workspace)."""
    from backend.providers import cli_space as W
    from backend.providers.cli import CONNECTORS, ProviderError
    if pid not in CODING:
        raise ProviderUnavailable(f"{pid} is not a coding provider")
    profile = "assisted" if W.isolation(pid, "assisted")["supported"] else "review"
    try:
        iso = W.check_profile(pid, profile, allow_weaker=True)
    except W.WorkspaceError as e:
        raise ProviderUnavailable(str(e))
    sess = W.open_session(pid, re.sub(r"[^\w.-]", "-", task_id)[:60], profile, iso)
    cwd = Path(sess["cwd"])
    (cwd / "PROJECT_CONTEXT.md").write_text(context_text or "", "utf-8")
    before = _snapshot(cwd)
    text, errors = [], []
    from backend.agent.mcp_policy import grant_for_cli, revoke
    ctx = {"cwd": str(cwd), "profile": profile, "allow_weaker": True, **grant_for_cli(f"run:{task_id}")}
    try:
        for e in CONNECTORS[pid].stream_message("Read ./PROJECT_CONTEXT.md and ./FIREWALL.md first.\n\n" + prompt, ctx):
            if cancelled and cancelled():
                break
            if e["type"] == "text_delta":
                text.append(e.get("text", ""))
            elif e["type"] == "error":
                errors.append(e.get("message", ""))
    except ProviderError as e:
        raise ProviderUnavailable(str(e))
    finally:
        revoke(ctx["mcp_token"])
    if errors and not text:
        raise ProviderUnavailable("; ".join(errors)[:600])
    return {"text": "".join(text).strip(), "files": _collect(cwd, before, outdir), "workspace": str(cwd),
            "notes": errors[:3]}


def needs_linux(text: str) -> bool:
    """A task explicitly asks for Linux (apt, bash scripts, Linux-only packages) → run it in Docker."""
    return bool(re.search(r"(?i)\b(apt(-get)?\s+install|bash\s+\S+\.sh|needs?[_ ]linux|\.sh\b|/usr/bin|ubuntu|debian)\b",
                          text or ""))
