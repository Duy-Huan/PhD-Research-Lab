"""Shared helpers of the HTTP API: error mapping, SSE encoding, streamed agent jobs."""
from __future__ import annotations

import json

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

SSE = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _user_errors() -> tuple:
    from backend.agent import AIWSError
    from backend.execution.code_projects import CodeProjectError
    from backend.execution.sandbox import SandboxError
    from backend.knowledge.attachments import AttachmentError
    from backend.paper.review import ReviewError
    return (AIWSError, CodeProjectError, SandboxError, AttachmentError, ReviewError, ValueError, KeyError, FileNotFoundError)


async def call(fn, *a, **k):
    """Run a blocking service call in the thread pool; user errors become HTTP 400 with their message."""
    from backend.execution.code_projects import NoCodeProject
    try:
        return await run_in_threadpool(fn, *a, **k)
    except NoCodeProject:
        raise
    except HTTPException:
        raise
    except _user_errors() as e:
        raise HTTPException(400, str(e).strip("'\""))


def sse(obj) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False, default=str)}\n\n"


def stream(gen) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream", headers=SSE)


def sse_job(agent: str, system: str, user: str, finalize, max_tokens: int = 8000, temperature: float = 0.3,
            start: dict | None = None) -> StreamingResponse:
    """Stream one agent call as Server-Sent Events: start → delta… → done (finalize(meta) result) | error.
    If the client disconnects, the generator (and the upstream model request) is cancelled and nothing is saved."""
    from backend.providers.models import LLMError, stream_agent

    async def gen():
        try:
            yield sse({"type": "start", **(start or {})})
            meta = {}
            async for kind, val in stream_agent(agent, system, [{"role": "user", "content": user}],
                                                max_tokens=max_tokens, temperature=temperature):
                if kind == "delta":
                    yield sse({"type": "delta", "text": val})
                else:
                    meta = val
            if not meta.get("text", "").strip():
                raise LLMError("The model returned an empty answer.")
            out = await run_in_threadpool(finalize, meta)
            yield sse({"type": "done", "engine": meta["engine"], "note": meta["note"], **out})
        except LLMError as e:
            yield sse({"type": "error", "detail": str(e)})
        except HTTPException as e:
            yield sse({"type": "error", "detail": str(e.detail)})
        except Exception as e:  # never leave the client hanging
            yield sse({"type": "error", "detail": f"{type(e).__name__}: {e}"})
    return stream(gen())
