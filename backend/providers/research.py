"""Research providers: the parallel back-ends the orchestrator hands SCOPED tasks to (architecture: chatbox → primary
research orchestrator → shared context memory + research state → providers → reliability layer).

    category      id            what it does here
    research      phdlab        native literature, analysis and review through the selected model gateway
    research      app           the app's own model, agent "research" or "reviewer" (always available as fallback)
    coding        claude_code   Claude Code CLI · codex · gemini_cli · antigravity (subscription sign-in, own workspace)
    experiment    python        Python venv of the active code project on this PC (default execution)
    experiment    docker        Linux container — only for tasks that need Linux (needs_linux)
    experiment    tracking      native process journals, raw metrics and artifacts (no service)
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
OUT_EXT = {".md", ".txt", ".csv", ".json", ".bib", ".tex", ".pdf", ".png", ".svg", ".py", ".yaml", ".yml", ".sh", ".toml", ".ipynb", ".cfg", ".ini"}
CODING = ("claude_code", "codex", "gemini_cli", "antigravity")
CATALOG = {
    "phdlab": ("research", "PhD Lab Native Research"),
    "app": ("research", "Mô hình của ứng dụng (agent Research / Reviewer)"),
    "claude_code": ("coding", "Claude Code"),
    "codex": ("coding", "OpenAI Codex"),
    "gemini_cli": ("coding", "Gemini CLI"),
    "antigravity": ("coding", "Google Antigravity"),
    "python": ("experiment", "Native Python experiments"),
    "tracking": ("experiment", "Native experiment records"),
    "vscode": ("editor", "VS Code"),
    "docker": ("experiment", "Docker (Linux, chạy ngầm khi cần)"),
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
    if pid == 'tracking':
        return {'state':'READY','detail':'Project-owned run records, metrics, raw artifacts and code/data provenance; scientific verification is separate.'}
    if pid == 'vscode':
        from backend.execution.vscode import vscode_cli
        binary=vscode_cli()
        return {'state':'READY' if binary else 'UNAVAILABLE','detail':'Installed VS Code editor' if binary else 'VS Code is not installed or its CLI is unavailable'}
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
            if pid == "paperorchestra":
                from backend.research_engines.registry import get
                po_h = get(pid).health()
                h = {
                    "state": po_h["state"],
                    "detail": po_h.get("detail", ""),
                    "setup": po_h.get("setup", []),
                }
            elif pid in ("app", "phdlab"):
                h = {"state": "READY", "detail": "Native research adapter available; each task uses one configured model role. Model authentication/inference is verified separately."}
            elif pid in CODING:
                h = _coding_health(pid, fresh)
            else:
                h = _exec_health(pid, cfg)
        except Exception as e:  # a broken probe never breaks the registry
            h = {"state": "ERROR", "detail": f"{type(e).__name__}: {e}"[:200]}
        _health[pid] = (time.time(), h, fingerprint)
    cat, label = CATALOG[pid]
    return {"id": pid, "category": cat, "kind": "model" if pid in (*CODING, "app") else "embedded_engine" if pid in ("phdlab", "paperorchestra") else "native_tool", "label": label, "state": h["state"],
            "ready": h["state"] == "READY" or (pid in CODING and h["state"] == "UNKNOWN"),
            "detail": h.get("detail", ""), "setup": h.get("setup") or []}


def describe_all(fresh: bool = False) -> list:
    """Every provider, probed in parallel (CLI version / sign-in checks take seconds each)."""
    from concurrent.futures import ThreadPoolExecutor
    cfg = _cfg()
    names=[name for name in CATALOG if name not in (*CODING, "app")]
    with ThreadPoolExecutor(max_workers=len(names)) as ex:
        return list(ex.map(lambda p: describe(p, cfg, fresh), names))


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
def app_complete(agent: str, system: str, user: str, max_tokens: int = 6000, *, timeout_s: float = 900, cancelled=None) -> str:
    """One call to the app's model for the given agent (research | reviewer | utility)."""
    import asyncio

    from backend.providers.models import call_agent
    async def bounded():
        task=asyncio.create_task(call_agent(agent, system, user, max_tokens=max_tokens, temperature=0.3))
        deadline=time.monotonic()+timeout_s
        try:
            while not task.done():
                if cancelled and cancelled(): raise InterruptedError('Native model request cancelled')
                remaining=deadline-time.monotonic()
                if remaining<=0: raise TimeoutError('Native model request exceeded its task deadline')
                await asyncio.wait([task],timeout=min(.2,remaining))
            return await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
    r = asyncio.run(bounded())
    return (r.get("text") or "").strip()


def _artifact_files(folder: Path) -> list[Path]:
    from backend.knowledge.research_store import safe_child
    root=safe_child(folder);files=[];visited=0;started=time.monotonic()
    for directory,children,names in os.walk(root,followlinks=False):
        children[:]=sorted(name for name in children if not name.startswith('.') and name not in ('node_modules','__pycache__'))
        for name in children:
            safe_child(root,str((Path(directory)/name).relative_to(root)))
        for name in sorted(names):
            visited+=1
            if visited>10000 or time.monotonic()-started>20:
                raise ProviderUnavailable('Coding artifact inventory exceeded its explicit scan budget; files remain in the provider workspace')
            candidate=Path(directory)/name
            if name.startswith('.') or candidate.suffix.lower() not in OUT_EXT:continue
            candidate=safe_child(root,str(candidate.relative_to(root)))
            if candidate.is_file():files.append(candidate)
            if len(files)>200:
                raise ProviderUnavailable('Coding artifact inventory exceeds200files; originals are preserved, no silent truncation')
    return files


def _snapshot(d: Path) -> dict:
    return {str(f):f.stat().st_mtime_ns for f in _artifact_files(d)}


def _collect(cwd: Path, before: dict, outdir: Path) -> list:
    from backend.core.config import data_dir
    from backend.knowledge.research_store import safe_child
    try:outdir=safe_child(data_dir(),str(outdir.absolute().relative_to(data_dir().resolve())))
    except ValueError as error:raise ProviderUnavailable('Coding artifacts must remain in this paper project') from error
    pending=[];total=0
    for source in _artifact_files(cwd):
        stat=source.stat()
        if before.get(str(source))==stat.st_mtime_ns:continue
        total+=stat.st_size
        if stat.st_size>32*1024*1024 or total>64*1024*1024:
            raise ProviderUnavailable('Coding artifact byte budget exceeded; original files are preserved in the provider workspace')
        target=safe_child(outdir,str(source.relative_to(cwd)))
        pending.append((source,target,stat))
    files=[]
    for source,target,stat in pending:
        target.parent.mkdir(parents=True,exist_ok=True)
        # Provider termination precedes collection. Detect concurrent user edits as well.
        current=source.stat()
        if (current.st_size,current.st_mtime_ns)!=(stat.st_size,stat.st_mtime_ns):
            raise ProviderUnavailable('Coding output changed during collection; inspect preserved originals')
        shutil.copyfile(source,target)
        files.append(str(target.relative_to(outdir)).replace('\\','/'))
    return files


def run_coding(task_id: str, pid: str, prompt: str, context_text: str, outdir: Path, cancelled=None) -> dict:
    """An explicitly selected coding provider through the existing durable gateway."""
    from backend.providers import cli_space as W, gateway as G
    from backend.providers.cli import ProviderError
    from backend.providers.privacy import sanitize
    from backend.agent.mcp_policy import grant_for_cli, revoke
    if pid not in CODING:
        raise ProviderUnavailable(f"{pid} is not a coding provider")
    if cancelled and cancelled():
        raise ProviderUnavailable('Coding task cancelled before gateway preparation; no provider was invoked')
    profile = "assisted" if W.isolation(pid, "assisted")["supported"] else "review"
    request=None;grant=None
    try:
        iso=W.check_profile(pid,profile)
        safe_context,_=sanitize(context_text or '')
        request=G.prepare('Read ./PROJECT_CONTEXT.md and ./FIREWALL.md first.\n\n'+prompt,pid,
                          profile=profile,module_context=safe_context,memory=False)
        sid=request['session_id']
        session=W.open_session(pid,sid,profile,iso)
        cwd=Path(session['cwd'])
        (cwd/'PROJECT_CONTEXT.md').write_text(safe_context,'utf-8')
        before=_snapshot(cwd)
        grant=grant_for_cli('run:'+task_id)
        G.send(request['id'],base_url=grant['mcp_url'].removesuffix('/mcp'),
               mcp={'token':grant['mcp_token'],'tools':grant['mcp_tools']})
        deadline=time.monotonic()+600
        while True:
            actual=G.get(request['id'])
            if actual['status'] not in ('ready','starting','running'):break
            if cancelled and cancelled():
                G.cancel(request['id'])
                raise ProviderUnavailable('Coding task cancelled; partial output retained in its gateway request')
            if time.monotonic()>=deadline:
                G.cancel(request['id'])
                raise ProviderUnavailable('Coding task exceeded its deadline; inspect its gateway request before retrying')
            time.sleep(.05)
        if actual['status']!='completed':
            raise ProviderUnavailable('; '.join(actual.get('errors') or []) or 'Coding provider did not complete')
        return {'text':actual['answer'],'files':_collect(cwd,before,outdir),'workspace':str(cwd),
                'gateway_request_id':request['id'],'notes':[]}
    except (ProviderError,G.GatewayError,W.WorkspaceError) as error:
        raise ProviderUnavailable(str(error)) from error
    finally:
        if grant:revoke(grant['mcp_token'])


def needs_linux(text: str) -> bool:
    """A task explicitly asks for Linux (apt, bash scripts, Linux-only packages) → run it in Docker."""
    return bool(re.search(r"(?i)\b(apt(-get)?\s+install|bash\s+\S+\.sh|needs?[_ ]linux|\.sh\b|/usr/bin|ubuntu|debian)\b",
                          text or ""))
