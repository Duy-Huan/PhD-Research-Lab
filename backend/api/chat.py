"""The research chat (UI and CLI): conversations, turns, live events, approvals, attachments, artifacts, skills."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, File, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from backend.agent import artifacts, memory_modes, orchestrator, policy as POL, sessions as store
from backend.api.common import call, sse, stream

router = APIRouter()


# ------------------------------------------------------------------ conversations
@router.get("/api/chat/sessions")
async def sessions(q: str = "", archived: int = 0, limit: int = 200):
    return {"sessions": await call(store.list_sessions, "", "", q, bool(archived), max(1, min(500, limit)))}


@router.post("/api/chat/sessions")
async def create(body: dict = Body(default={})):
    return await call(store.create, str(body.get("title", "")), "global", "", "", body.get("settings") or {})


@router.get("/api/chat/sessions/{sid}")
async def get(sid: str):
    """The conversation + the sequence number to stream from + its memory proposals (with their current status)."""
    def run():
        from backend.memory import lifecycle
        s = store.get(sid)
        items = []
        for cid in s.get("memory") or []:
            try:
                c = lifecycle.get(cid)
            except Exception:
                continue
            p = c.get("payload") or {}
            items.append({"id": c["id"], "status": c["status"], "type": p.get("memory_type", c.get("kind", "")),
                          "text": p.get("text", ""), "message_ids": (p.get("source") or {}).get("message_ids", []),
                          "conflicts": len(c.get("conflicts_with") or []), "created": c.get("created", "")})
        return {**s, "last_seq": store._last_seq(sid), "memory_items": items}
    return await call(run)


@router.put("/api/chat/sessions/{sid}")
async def update(sid: str, body: dict = Body(...)):
    """{title?, archived?, settings? (provider, model, …), settings_reset?: [keys]}."""
    def run():
        if "title" in body:
            store.rename(sid, str(body["title"]))
        if "archived" in body:
            store.archive(sid, bool(body["archived"]))
        if "settings" in body or "settings_reset" in body:
            patch = POL.clean_settings(body.get("settings") or {})
            reset = [k for k in body.get("settings_reset") or [] if k in POL.KEYS]

            def fn(s):
                s["settings"].update(patch)
                for k in reset:
                    s["settings"].pop(k, None)
            store.update(sid, fn)
            store.emit(sid, "session.updated", field="settings")
        return store.get(sid)
    return await call(run)


@router.get("/api/chat/sessions/{sid}/effective")
async def effective(sid: str):
    """The settings this conversation really uses (model, reasoning, memory …) with where each value comes from, and
    notes for choices the provider cannot honour (e.g. a reasoning level it has no control for)."""
    def run():
        eff = POL.effective(store.get(sid))
        return {"effective": eff, "notes": POL.check_provider(eff)}
    return await call(run)


@router.delete("/api/chat/sessions/{sid}")
async def delete(sid: str, confirm: str = ""):
    return await call(store.delete, sid, confirm)


@router.post("/api/chat/sessions/{sid}/fork")
async def fork(sid: str, body: dict = Body(default={})):
    return await call(store.fork, sid, str(body.get("message_id", "")))


# ------------------------------------------------------------------ turns
@router.post("/api/chat/sessions/{sid}/turns")
async def turn(sid: str, request: Request, body: dict = Body(...)):
    """{text, overrides?: {provider, model, sources: ["att:…", "ref:…"], …}} — "/command" texts run a skill."""
    return await call(orchestrator.start, sid, str(body.get("text", "")), body.get("overrides") or {}, str(request.base_url),
                      str(body.get("replace_from", "")))


@router.post("/api/chat/sessions/{sid}/retry")
async def retry(sid: str, request: Request, body: dict = Body(default={})):
    return await call(orchestrator.retry, sid, str(request.base_url), body.get("overrides") or {})


@router.post("/api/chat/sessions/{sid}/turns/{tid}/cancel")
async def cancel(sid: str, tid: str):
    return await call(orchestrator.cancel, sid, tid)


@router.post("/api/chat/sessions/{sid}/turns/{tid}/launch")
async def launch(sid: str, tid: str, body: dict = Body(default={})):
    return await call(orchestrator.launch, sid, tid, body.get("context"))


@router.get("/api/chat/sessions/{sid}/turns/{tid}/context")
async def turn_context(sid: str, tid: str):
    """What the model was given for this turn (manifest of sources with trust labels) — the 'Advanced details'."""
    return await call(lambda: orchestrator._turn(store.get(sid), tid).get("manifest"))


@router.get("/api/chat/sessions/{sid}/events")
async def events(sid: str, after: int = 0):
    return {"events": await call(store.events, sid, max(0, after))}


@router.get("/api/chat/sessions/{sid}/stream")
async def events_stream(sid: str, request: Request, after: int = 0, timeout: float = 600):
    await call(store.get, sid)

    async def gen():
        last, end = max(0, after), asyncio.get_running_loop().time() + max(1.0, min(3600.0, timeout))
        while asyncio.get_running_loop().time() < end:
            for e in await run_in_threadpool(store.wait_events, sid, last, 1.0):
                last = e["seq"]
                yield sse(e)
            if await request.is_disconnected():
                return
        yield sse({"type": "stream.timeout", "seq": last})
    return stream(gen())


@router.post("/api/chat/sessions/{sid}/approvals/{aid}")
async def decide(sid: str, aid: str, body: dict = Body(...)):
    """The researcher's Accept / Reject of a proposal: {decision: approve | reject, edits?: {…}}."""
    return await call(orchestrator.decide, sid, aid, str(body.get("decision", "")), body.get("edits") or None)


# ------------------------------------------------------------------ attachments (sent with a message as sources att:<id>)
@router.post("/api/chat/attachments")
async def attach(file: UploadFile = File(...)):
    """Any file: PDF, Word, PowerPoint, Excel, notebooks, text/code, images. PDFs can also go to the library."""
    from backend.knowledge import attachments as AT
    return await call(AT.add_upload, file.filename or "file", await file.read())


# ------------------------------------------------------------------ artifacts (files a provider proposed)
@router.get("/api/chat/sessions/{sid}/artifacts/{aid}")
async def artifact(sid: str, aid: str):
    return await call(lambda: artifacts.preview(store.get(sid), aid))


@router.get("/api/chat/sessions/{sid}/artifacts/{aid}/diff")
async def artifact_diff(sid: str, aid: str, target: str = ""):
    return await call(lambda: artifacts.diff(store.get(sid), aid, target))


@router.get("/api/chat/sessions/{sid}/artifacts/{aid}/download")
async def artifact_download(sid: str, aid: str):
    a, data = await call(lambda: (artifacts.get(store.get(sid), aid), artifacts.content(store.get(sid), aid)))
    return Response(data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{a["path"].rsplit("/", 1)[-1]}"'})


@router.post("/api/chat/sessions/{sid}/artifacts/{aid}/apply")
async def artifact_apply(sid: str, aid: str, body: dict = Body(...)):
    return await call(artifacts.apply, sid, aid, str(body.get("target", "")), str(body.get("expected_sha", "")))


@router.post("/api/chat/sessions/{sid}/artifacts/{aid}/reject")
async def artifact_reject(sid: str, aid: str, body: dict = Body(default={})):
    return await call(artifacts.reject, sid, aid, str(body.get("reason", "")))


@router.post("/api/chat/sessions/{sid}/memory")
async def remember(sid: str, body: dict = Body(...)):
    """'Ghi nhớ' on a message: a memory proposal (or saved directly with save=true)."""
    return await call(lambda: memory_modes.manual(store.get(sid), str(body.get("message_id", "")), str(body.get("type", "")),
                                                  str(body.get("content", "")), str(body.get("title", "")),
                                                  bool(body.get("save"))))


# ------------------------------------------------------------------ skills ("/" commands)
@router.get("/api/skills")
async def skills_list():
    from backend.agent import skills
    return {"skills": await call(skills.catalog), "errors": await call(skills.errors)}


@router.get("/api/skills/{name}")
async def skill_get(name: str):
    from backend.agent import skills
    return await call(skills.get, name)


@router.post("/api/skills")
async def skill_save(body: dict = Body(...)):
    """Create / replace one of the researcher's skills: {text: "---\\nname: …\\n---\\n…", scope: project | user}."""
    from backend.agent import skills
    return await call(skills.save_user, str(body.get("text", "")), str(body.get("scope") or "project"))


@router.delete("/api/skills/{name}")
async def skill_delete(name: str):
    from backend.agent import skills
    return await call(skills.delete_user, name)
