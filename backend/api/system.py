"""System: version, settings, models (picker + local engines), research providers, dashboard, the UI ⇄ CLI event bus."""
from __future__ import annotations

import asyncio
from asyncio import wait_for

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from backend.api.common import call, sse, stream
from backend.core import bus
from backend.core.config import APP_VERSION, AGENTS, PROVIDERS, ROOT, load_config, public_config, save_config

router = APIRouter()


@router.get("/api/version")
def version():
    return {"version": APP_VERSION, "root": str(ROOT)}


@router.get("/api/config")
def get_config():
    return public_config(load_config())


@router.post("/api/config")
def set_config(body: dict = Body(...)):
    out = public_config(save_config(body))
    bus.publish("config.updated", keys=",".join(sorted(body))[:200])
    return out


# ------------------------------------------------------------------ models
@router.post("/api/models/cli/codex")
async def codex_catalog():
    from backend.providers.app_server import model_catalog
    models = await call(model_catalog)
    cfg = load_config()
    save_config({"gateway": {"cli_models": {**cfg["gateway"].get("cli_models", {}), "codex": models}}})
    return {"models": models, "entitlement_verified": False}


@router.get("/api/models")
async def models():
    """The chat's model picker: the agents (what engine/model each one uses now) and every selectable provider id."""
    from backend.providers import registry
    from backend.providers.models import agent_runtime
    cfg = load_config()
    agents = await run_in_threadpool(lambda: {a: agent_runtime(cfg, a) | {"label": AGENTS[a]["label"]} for a in AGENTS})
    provs = await run_in_threadpool(registry.registry)
    from backend.providers.models import resolve_engine
    catalog = {}
    for agent in AGENTS:
        engine = resolve_engine(cfg, agent)
        provider = next((p for p in provs if p["id"] in ("app:" + engine, "cli:" + engine)), None)
        choices = (cfg.get("mcp_agent") or {}).get("models", []) if engine == "mcp" else (provider or {}).get("capabilities", {}).get("models", [])
        catalog[agent] = {"engine": engine, "mode": cfg["agent_modes"][agent], "label": (provider or {}).get("label", engine),
                          "models": list(dict.fromkeys([m for m in [*choices, cfg.get("agent_models", {}).get(agent)] if m])),
                          "selected": cfg.get("agent_models", {}).get(agent, "")}
    return {"agents": agents, "agent_catalog": catalog, "providers": [{k: p[k] for k in ("id", "label", "transport", "state", "available", "detail")}
                                            | {"models": p["capabilities"]["models"],
                                               "reasoning": p["capabilities"]["reasoning_controls"]} for p in provs],
            "default": cfg["aiws"]["provider"], "cloud": {k: {"label": v["label"], "models": v["models"]}
                                                          for k, v in PROVIDERS.items()}}


@router.post("/api/models/test")
async def test_model(body: dict = Body(...)):
    from backend.providers.models import LLMError, _stream_engine, default_model_for
    pid = str(body.get("provider", "")).removeprefix("app:")
    if pid not in (*PROVIDERS, "local", "ollama"):
        raise HTTPException(400, "Unknown provider")
    cfg = load_config()
    model = str(body.get("model") or "").strip() or None
    async def collect():
        return [part async for part in _stream_engine(cfg, pid, "Reply with the single word: OK",
                                                     [{"role": "user", "content": "ping"}], 256, None, model)]
    try:
        parts = await wait_for(collect(), timeout=60)
    except asyncio.TimeoutError as e:
        raise HTTPException(504, "Provider connection test timed out after 60 seconds.") from e
    text = "".join(parts).strip()
    if not text:
        raise LLMError("The provider returned an empty stream. Check the base URL, selected model and provider logs.")
    return {"ok": True, "provider": pid, "transport": "stream", "model": model or default_model_for(cfg, pid) or "(auto)",
            "reply": text[:80]}


@router.post("/api/models/list")
async def provider_models(body: dict = Body(...)):
    from backend.providers.models import list_provider_models
    return {"models": await list_provider_models(load_config(), str(body.get("provider", "")))}


@router.get("/api/models/local")
async def local_status():
    """LM Studio / Ollama: reachable, available models, what is in VRAM now."""
    from backend.providers import lifecycle as LC
    from backend.providers import local as local_ai
    cfg = load_config()
    lm, ol = await asyncio.gather(local_ai.lmstudio_status(cfg["lmstudio_base_url"]), local_ai.ollama_status(cfg["ollama_base_url"]))
    return {"lmstudio": lm, "ollama": ol, "selected": {"local": cfg.get("local_model", ""), "ollama": cfg.get("ollama_model", "")},
            "lifecycle": await LC.status()}


@router.post("/api/models/unload")
async def unload_models(body: dict = Body(default={})):
    """Unload local models from VRAM: {engine: all | local | ollama, model?, force?}."""
    from backend.providers import lifecycle as LC
    eng = str(body.get("engine") or "all")
    if eng == "all":
        return await LC.unload_all_local(bool(body.get("force")))
    if eng not in ("ollama", "local"):
        raise HTTPException(400, "engine must be ollama, local (LM Studio) or all")
    return await LC.unload(eng, str(body.get("model") or ""), bool(body.get("force")))


# ------------------------------------------------------------------ research providers
@router.get("/api/providers")
async def providers(fresh: int = 0):
    from backend.providers.research import describe_all
    return {"providers": await run_in_threadpool(describe_all, bool(fresh))}


VENDOR_LOGIN_URLS = {
    "codex": "https://chatgpt.com",
    "chatgpt": "https://chatgpt.com",
    "chatgpt_sub": "https://chatgpt.com",
    "claude_code": "https://claude.ai/login",
    "claude": "https://claude.ai/login",
    "antigravity": "https://antigravity.google",
    "gemini_cli": "https://gemini.google.com",
    "gemini": "https://gemini.google.com",
    "openai": "https://platform.openai.com/login",
    "anthropic": "https://console.anthropic.com/login",
    "feynman": "https://feynman.ai",
    "openscience": "https://openscience.org",
    "opencode": "http://127.0.0.1:4097",
    "lmstudio": "http://127.0.0.1:1234",
    "ollama": "http://127.0.0.1:11434",
    "deepseek": "https://chat.deepseek.com",
}


@router.get("/api/providers/{pid}/auth-status")
async def provider_auth_status(pid: str):
    """Check whether a CLI/Subscription provider is signed in and ready on this computer."""
    from backend.providers.cli import CONNECTORS
    clean_pid = pid.removeprefix("cli:").removeprefix("app:")
    web_url = VENDOR_LOGIN_URLS.get(clean_pid) or VENDOR_LOGIN_URLS.get(pid, "https://chatgpt.com")
    if clean_pid not in CONNECTORS:
        return {
            "provider": pid,
            "state": "UNKNOWN",
            "ready": False,
            "detail": "No CLI connector registered",
            "web_url": web_url,
        }
    conn = CONNECTORS[clean_pid]
    h = await run_in_threadpool(conn.health, True)
    return {
        "provider": pid,
        "state": h.get("state", "UNKNOWN"),
        "ready": h.get("state") == "CONNECTED",
        "detail": h.get("detail", ""),
        "login_cmd": conn.login_cmd,
        "web_url": web_url,
        "setup": h.get("setup", []),
    }


@router.post("/api/providers/{pid}/connect")
async def provider_connect(pid: str, body: dict | None = None):
    """CLI providers sign in with the vendor's own flow; PhD Lab opens a terminal and/or forwards to the vendor's app/web."""
    import sys
    import subprocess
    import webbrowser
    from backend.providers.cli import CONNECTORS

    payload = body if isinstance(body, dict) else {}
    clean_pid = pid.removeprefix("cli:").removeprefix("app:")
    mode = str(payload.get("mode") or "both").lower()  # terminal, web, or both
    open_web = bool(payload.get("open_web")) or mode in ("web", "both", "app")
    web_url = VENDOR_LOGIN_URLS.get(clean_pid) or VENDOR_LOGIN_URLS.get(pid, "https://chatgpt.com")

    # Forward to app/web browser if requested or mode includes web
    opened_web = False
    if open_web and web_url:
        try:
            webbrowser.open(web_url)
            opened_web = True
        except Exception:
            pass

    if clean_pid == "feynman":
        launched = False
        if sys.platform.startswith("win") and mode in ("terminal", "both"):
            subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k", "feynman model login"])
            launched = True
        return {
            "provider": pid,
            "command": "feynman model login",
            "launched": launched,
            "web_url": web_url,
            "opened_web": opened_web,
        }

    if clean_pid not in CONNECTORS:
        if clean_pid in VENDOR_LOGIN_URLS or pid in VENDOR_LOGIN_URLS:
            return {
                "provider": pid,
                "command": "",
                "launched": False,
                "web_url": web_url,
                "opened_web": opened_web,
                "detail": f"Forwarded to {clean_pid} web portal for authentication.",
            }
        raise HTTPException(400, f"{pid} has no sign-in flow")

    conn = CONNECTORS[clean_pid]
    res = await call(conn.connect, mode in ("terminal", "both"))
    res["web_url"] = web_url
    res["opened_web"] = opened_web
    return res


@router.post("/api/providers/{pid}/launch")
async def provider_launch(pid: str, body: dict | None = None):
    """Direct shortcut to launch or navigate to an app provider (web app, desktop app, or CLI terminal)."""
    import webbrowser
    import subprocess
    import sys
    payload = body if isinstance(body, dict) else {}
    clean_pid = pid.removeprefix("cli:").removeprefix("app:")
    web_url = VENDOR_LOGIN_URLS.get(clean_pid) or VENDOR_LOGIN_URLS.get(pid, "https://chatgpt.com")
    
    if clean_pid == "opencode":
        try:
            from backend.research_engines import opencode as OC
            OC.ensure_server_running()
        except Exception:
            pass

    opened_web = False
    try:
        webbrowser.open(web_url)
        opened_web = True
    except Exception:
        pass

    terminal_launched = False
    if clean_pid in ("feynman", "claude_code", "codex", "gemini_cli", "antigravity") and payload.get("terminal"):
        from backend.providers.cli import CONNECTORS
        if clean_pid in CONNECTORS:
            await call(CONNECTORS[clean_pid].connect, True)
            terminal_launched = True

    return {
        "ok": True,
        "provider": pid,
        "clean_id": clean_pid,
        "url": web_url,
        "opened_web": opened_web,
        "terminal_launched": terminal_launched,
        "message": f"Opened {clean_pid} app navigator directly.",
    }


@router.post("/api/providers/{pid}/sync")
async def provider_sync(pid: str):
    """Synchronize files, outputs, and artifacts from an app provider workspace back into PhD Lab."""
    from backend.knowledge import research_store as S
    from backend.research_engines import workspaces as W
    from backend.agent import decision_ledger as L

    clean_pid = pid.removeprefix("cli:").removeprefix("app:")
    synced_workspaces = []
    total_changed = 0
    total_observed = 0

    with S.db() as c:
        topics = c.execute("SELECT id FROM topics ORDER BY updated DESC LIMIT 5").fetchall()

    for trow in topics:
        tid = trow[0]
        ws_list = W.list_workspaces(tid)
        matching = [w for w in ws_list if w.get("engine") == clean_pid]
        if not matching and clean_pid in ("claude_code", "codex", "antigravity", "gemini_cli", "python"):
            matching = [w for w in ws_list if w.get("engine") in ("opencode", "feynman", "openscience")]
        
        for w in matching:
            wid = w["id"]
            report = W.sync(wid)
            synced_workspaces.append({"workspace_id": wid, "topic_id": tid, "engine": w.get("engine"), "report": report})
            total_changed += int(report.get("changed", 0))
            total_observed += int(report.get("observed", 0))
            
            with S.db() as c:
                L.append(
                    c,
                    tid,
                    f"sync-{clean_pid}",
                    "provider.workspace_synced",
                    {"provider": clean_pid, "workspace_id": wid, "changed": report.get("changed", 0)},
                )

    if not synced_workspaces and topics:
        tid = topics[0][0]
        ws_list = W.list_workspaces(tid)
        for w in ws_list[:2]:
            wid = w["id"]
            report = W.sync(wid)
            synced_workspaces.append({"workspace_id": wid, "topic_id": tid, "engine": w.get("engine"), "report": report})
            total_changed += int(report.get("changed", 0))
            total_observed += int(report.get("observed", 0))

    return {
        "ok": True,
        "provider": pid,
        "clean_id": clean_pid,
        "synced_at": S.now(),
        "workspaces_synced": len(synced_workspaces),
        "total_changed": total_changed,
        "total_observed": total_observed,
        "details": synced_workspaces,
    }


# ------------------------------------------------------------------ dashboard + events
@router.get("/api/dashboard")
async def dashboard(advanced: int = 0):
    from backend.agent.dashboard import status
    return await call(status, bool(advanced))


@router.get("/api/events")
def events(after: int = 0, limit: int = 500):
    return bus.since(max(0, after), max(1, min(2000, limit)))


@router.get("/api/events/stream")
async def events_stream(request: Request, after: int = -1, timeout: float = 3600):
    async def gen():
        last = bus.last() if after < 0 else after
        end = asyncio.get_running_loop().time() + max(1.0, min(86400.0, timeout))
        yield sse({"type": "hello", "seq": last})
        while asyncio.get_running_loop().time() < end:
            for e in await run_in_threadpool(bus.wait, last, 1.0):
                last = e["seq"]
                yield sse(e)
            if await request.is_disconnected():
                return
    return stream(gen())


# ------------------------------------------------------------------ filesystem & folder picker
@router.post("/api/system/pick-folder")
async def pick_folder(body: dict | None = None):
    """Open native host OS directory picker dialog (Tkinter/Windows Explorer) and return chosen path."""
    payload = body if isinstance(body, dict) else {}
    initial_dir = str(payload.get("initial_dir") or "").strip()
    title = str(payload.get("title") or "Chọn thư mục nghiên cứu").strip()

    def run():
        import os
        import subprocess
        import sys

        script = """
import sys, os
try:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    init_dir = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else ""
    title = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else "Select Folder"
    p = filedialog.askdirectory(initialdir=init_dir or None, title=title)
    root.destroy()
    if p:
        print(os.path.normpath(p))
    else:
        print("")
except Exception:
    print("")
"""
        try:
            proc = subprocess.run(
                [sys.executable, "-c", script, initial_dir, title],
                capture_output=True,
                text=True,
                timeout=120,
            )
            path = proc.stdout.strip()
            return {"path": path, "canceled": not bool(path), "ok": True}
        except Exception as e:
            return {"path": "", "canceled": True, "ok": False, "error": str(e)}

    return await run_in_threadpool(run)


@router.get("/api/system/fs-browse")
async def fs_browse(path: str = ""):
    """Browse host filesystem directories, list drives, shortcuts, and subdirectories."""
    def run():
        import os
        import string
        from pathlib import Path
        from backend.core.config import ROOT, data_dir

        drives: list[str] = []
        if os.name == "nt":
            for letter in string.ascii_uppercase:
                d = f"{letter}:\\"
                if os.path.exists(d):
                    drives.append(d)
        else:
            drives = ["/"]

        home = Path.home()
        shortcuts = [
            {"name": "Home", "path": str(home)},
            {"name": "Desktop", "path": str(home / "Desktop") if (home / "Desktop").exists() else ""},
            {"name": "Documents", "path": str(home / "Documents") if (home / "Documents").exists() else ""},
            {"name": "Downloads", "path": str(home / "Downloads") if (home / "Downloads").exists() else ""},
            {"name": "Workspace Lab", "path": str(ROOT)},
        ]
        try:
            active_data = str(data_dir().resolve())
            shortcuts.append({"name": "Active Project", "path": active_data})
        except Exception:
            pass
        shortcuts = [s for s in shortcuts if s["path"] and os.path.isdir(s["path"])]

        # Target directory
        raw_path = path.strip() if path else ""
        if raw_path:
            cur = Path(raw_path).resolve()
            if not cur.exists() or not cur.is_dir():
                cur = ROOT
        else:
            cur = ROOT

        entries = []
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    if entry.is_dir() and not entry.name.startswith("$") and entry.name not in (
                        "System Volume Information", "Recovery", "$Recycle.Bin"
                    ):
                        entries.append({
                            "name": entry.name,
                            "path": str(Path(entry.path).resolve()),
                            "hidden": entry.name.startswith("."),
                        })
        except (PermissionError, OSError):
            pass

        entries.sort(key=lambda x: (x["hidden"], x["name"].lower()))
        parent = str(cur.parent) if cur.parent != cur else None

        return {
            "current": str(cur),
            "parent": parent,
            "drives": drives,
            "shortcuts": shortcuts,
            "directories": entries,
        }

    return await run_in_threadpool(run)


@router.post("/api/system/fs-mkdir")
async def fs_mkdir(body: dict = Body(...)):
    """Create a new directory on host computer."""
    def run():
        from pathlib import Path
        path_str = str(body.get("path") or "").strip()
        if not path_str:
            raise HTTPException(400, "Path is required")
        p = Path(path_str).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "path": str(p)}

    return await run_in_threadpool(run)

