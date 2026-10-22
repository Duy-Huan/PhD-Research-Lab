"""PhD Research Lab — AI research operating system (FastAPI server; the UI and the `phdlab` CLI are its two clients).

Run:  python start.py          (or: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765)
"""
import asyncio
import os
import re
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.api import ROUTERS
from backend.core.bus import MutationMiddleware
from backend.core.config import APP_VERSION, ROOT, load_config
from backend.execution.code_projects import NoCodeProject
from backend.providers.models import LLMError

FRONTEND = ROOT / "frontend"


@asynccontextmanager
async def lifespan(_app):
    """Start: memory summariser + model lifecycle reaper, and every research run that was working resumes from its last
    committed step (durable execution). Stop: experiment jobs are stopped and local models leave VRAM."""
    from backend.agent import runs
    from backend.memory import worker
    from backend.providers.lifecycle import reaper
    stop = asyncio.Event()
    task = asyncio.create_task(worker(stop))
    reap = asyncio.create_task(reaper(stop))
    from backend.knowledge.research_jobs import worker as research_worker
    research_task = asyncio.create_task(research_worker(stop))
    try:
        await asyncio.to_thread(runs.recover_all)
    except Exception:  # a damaged run file must never keep the app from starting
        pass
    asyncio.get_running_loop().run_in_executor(None, _warm)
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        research_task.cancel()
        await asyncio.gather(research_task, return_exceptions=True)
        await _shutdown()
        try:
            await asyncio.wait_for(reap, timeout=3)
        except BaseException:
            reap.cancel()


def _warm() -> None:
    """Probe the CLI providers once in the background, so the model picker opens instantly; refresh venue rankings."""
    try:
        from backend.providers import registry, research
        registry.registry()
        research.describe_all()
    except Exception:
        pass
    try:
        from backend.knowledge import ranking
        ranking.auto_refresh(load_config())
    except Exception:  # offline start: the previous ranking data stays in use
        pass


async def _shutdown() -> None:
    from backend.execution.sandbox import stop_all
    from backend.providers import lifecycle as LC
    try:
        await asyncio.to_thread(stop_all, "shutdown")
    except Exception:
        pass
    if (load_config().get("lifecycle") or {}).get("unload_on_exit", True):
        try:  # the researcher's rule: closing the app frees the GPU
            await asyncio.wait_for(LC.unload_all_local(force=True), timeout=20)
        except BaseException:
            pass


app = FastAPI(title="PhD Research Lab", version=APP_VERSION, lifespan=lifespan)


@app.exception_handler(LLMError)
async def llm_error_handler(_, exc: LLMError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(NoCodeProject)
async def no_code_project_handler(_, exc: NoCodeProject):
    """Experiment actions need an open code project (the UI and the CLI then offer to create / open one)."""
    return JSONResponse(status_code=409, content={"detail": str(exc), "code": "NO_CODE_PROJECT"})


def _page() -> Response:
    """The page links its assets with ?v=<version> so a browser never mixes files from two versions."""
    html = (FRONTEND / "index.html").read_text("utf-8")
    html = re.sub(r'((?:src|href)="/assets/[\w./-]+)"', lambda m: f'{m.group(1)}?v={APP_VERSION}"', html)
    return Response(html, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/", include_in_schema=False)
def index():
    return _page()


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(FRONTEND / "img" / "favicon-32.png", media_type="image/png")


class _NoStaleUI:
    """Pure ASGI (does not buffer SSE streams): UI files are always revalidated, so an upgrade shows up immediately."""
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/assets/"):
            return await self.inner(scope, receive, send)

        async def snd(msg):
            if msg["type"] == "http.response.start":
                hs = [(k, v) for k, v in msg.get("headers", []) if k.lower() != b"cache-control"]
                msg = {**msg, "headers": hs + [(b"cache-control", b"no-cache, must-revalidate")]}
            await send(msg)
        return await self.inner(scope, receive, snd)


class _LocalHostOnly:
    """The API runs commands and holds API keys, so it answers only requests whose Host is this computer (blocks DNS
    rebinding) and refuses cross-origin writes. Pure ASGI (keeps SSE streaming). Extra names: PHDLAB_ALLOWED_HOSTS."""
    ALLOWED = {"localhost", "127.0.0.1", "::1", "testserver"} | {h.strip().lower() for h in os.environ.get(
        "PHDLAB_ALLOWED_HOSTS", "").split(",") if h.strip()}

    def __init__(self, inner):
        self.inner = inner

    @staticmethod
    def host_of(scope) -> str:
        raw = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"host"), "").strip().lower()
        if raw.startswith("["):  # [::1]:8765
            return raw[1:raw.find("]")] if "]" in raw else raw
        return raw.rsplit(":", 1)[0] if raw.count(":") == 1 else raw

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and self.host_of(scope) not in self.ALLOWED:
            await send({"type": "http.response.start", "status": 421, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"Misdirected request: PhD Research Lab only answers on localhost."})
            return
        if scope["type"] == "http" and scope.get("method") in ("POST", "PUT", "PATCH", "DELETE"):
            origin = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"origin"), "")
            if origin:
                try:
                    parsed = urlsplit(origin)
                    valid = (parsed.scheme in ("http", "https") and parsed.hostname in self.ALLOWED
                             and parsed.username is None and parsed.password is None and not parsed.path
                             and not parsed.query and not parsed.fragment)
                except ValueError:
                    valid = False
                if not valid:
                    await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"text/plain")]})
                    await send({"type": "http.response.body", "body": b"Origin not allowed"})
                    return
        return await self.inner(scope, receive, send)


for _r in ROUTERS:
    app.include_router(_r)
app.mount("/assets", StaticFiles(directory=str(FRONTEND / "assets")), name="assets")
app.mount("/vendor", StaticFiles(directory=str(FRONTEND / "vendor")), name="vendor")  # offline UI libraries
app.mount("/img", StaticFiles(directory=str(FRONTEND / "img")), name="img")
app.add_middleware(MutationMiddleware)  # UI ⇄ CLI: successful API mutations are published on /api/events
app.add_middleware(_NoStaleUI)
app.add_middleware(_LocalHostOnly)
