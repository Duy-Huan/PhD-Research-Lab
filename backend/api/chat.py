"""The research chat (UI and CLI): conversations, turns, live events, approvals, attachments, artifacts, skills."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends, File, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from backend.agent import artifacts, memory_modes, orchestrator, policy as POL, sessions as store
from backend.api.common import call, sse, stream

async def bind_project():
    from backend.core.config import data_dir, project_scope
    with project_scope(data_dir()):
        yield


router = APIRouter(dependencies=[Depends(bind_project)])


# ------------------------------------------------------------------ conversations
@router.get("/api/chat/projects")
async def chat_projects():
    return {"projects": await call(store.chat_projects)}


@router.post("/api/chat/projects")
async def chat_project_create(body: dict = Body(...)):
    return await call(store.create_chat_project, body.get("name", ""), body.get("instructions", ""))


@router.put("/api/chat/projects/{gid}")
async def chat_project_update(gid: str, body: dict = Body(...)):
    return await call(store.update_chat_project, gid, body.get("name"), body.get("instructions"))


@router.delete("/api/chat/projects/{gid}")
async def chat_project_delete(gid: str):
    return await call(store.delete_chat_project, gid)


@router.get("/api/chat/sessions")
async def sessions(q: str = "", archived: int = 0, limit: int = 200):
    return {"sessions": await call(store.list_sessions, "", "", q, bool(archived), max(1, min(500, limit)))}


@router.post("/api/chat/sessions")
async def create(body: dict = Body(default={})):
    def run():
        tid = str(body.get("topic_id") or "")
        gid = body.get("chat_project") or ""
        if gid and not any(g["id"] == gid for g in store.chat_projects()):
            raise ValueError("Chat project not found in this research project")
        if tid:
            from backend.knowledge.research_store import get_topic
            get_topic(tid)
        s = store.create(str(body.get("title", "")), "global", "", "", body.get("settings") or {})
        if gid:
            store.organize(s["id"], chat_project=gid)
            s = store.get(s["id"])
        if tid:
            store.update(s["id"], lambda x: x.update(topic_id=tid))
            return store.get(s["id"])
        return s
    result = await call(run)
    if 'settings' in body or 'settings_reset' in body:
        from backend.providers.connections import session_selected
        session_selected(result)
    return result


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
        if "pinned" in body or "chat_project" in body:
            store.organize(sid, body.get("pinned"), body.get("chat_project"))
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
    result = await call(run)
    if 'settings' in body or 'settings_reset' in body:
        from backend.providers.connections import session_selected
        session_selected(result)
    return result


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


@router.put("/api/chat/sessions/{sid}/messages/{mid}/pin")
async def pin_message(sid: str, mid: str, body: dict = Body(...)):
    return await call(store.pin_message, sid, mid, body.get("pinned"))


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


@router.post("/api/chat/sessions/{sid}/cancel")
async def cancel_session_turns(sid: str):
    def _cancel():
        s = store.get(sid)
        cancelled = []
        for t in s.get("turns", []):
            if t.get("status") in ("running", "queued"):
                try:
                    orchestrator.cancel(sid, t["id"])
                    cancelled.append(t["id"])
                except Exception:
                    pass
        return {"cancelled": cancelled}
    return await call(_cancel)


@router.post("/api/chat/sessions/{sid}/turns/{tid}/launch")
async def launch(sid: str, tid: str, body: dict = Body(default={})):
    return await call(orchestrator.launch, sid, tid, body.get("context"))


@router.post("/api/chat/sessions/{sid}/console")
async def open_console(sid: str, request: Request):
    """Continue this conversation in the phdlab terminal chat (a new cmd window on Windows). The port is the one the
    server socket listens on, never a request header."""
    from backend.providers import native
    port = (request.scope.get("server") or ("", 8765))[1]
    return await call(native.open_chat_console, sid, port)


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
    resume = request.headers.get("last-event-id", "")
    if resume.startswith(sid + ":"):
        try:
            after = max(after, int(resume.rsplit(":", 1)[1]))
        except ValueError:
            pass

    async def gen():
        last, end = max(0, after), asyncio.get_running_loop().time() + max(1.0, min(3600.0, timeout))
        measured = set()
        while asyncio.get_running_loop().time() < end:
            for e in await run_in_threadpool(store.wait_events, sid, last, 1.0):
                last = e["seq"]
                if e["type"] == "message.delta" and e["turn_id"] not in measured:
                    import time
                    from backend.core.telemetry import record
                    measured.add(e["turn_id"])
                    record({"ts": time.time(), "operation": "chat.sse_delivery", "session_id": sid,
                            "latency_ms": round(max(0, time.time() - e["ts"]) * 1000, 2), "ok": True})
                yield "id: " + e["id"] + "\n" + sse(e)
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


@router.get("/api/chat/attachments/{att_id}/file")
async def attachment_file(att_id: str):
    """Inline file for image previews, thumbnails and documents."""
    import mimetypes
    from backend.knowledge import attachments as AT
    p = await call(AT.get_file_path, att_id)
    meta = await call(AT.get_meta, att_id)
    mt = meta.get("media_type") or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return FileResponse(p, media_type=mt, filename=meta.get("name") or p.name, content_disposition_type="inline")


@router.get("/api/chat/attachments/{att_id}")
async def attachment_meta(att_id: str):
    """Metadata of an attachment."""
    from backend.knowledge import attachments as AT
    return await call(AT.get_meta, att_id)


@router.post("/api/chat/attachments/{att_id}/analyze")
async def attachment_analyze(att_id: str, body: dict = Body(default={})):
    """Vision and image analysis tool endpoint."""
    from backend.knowledge import attachments as AT
    return await call(AT.analyze_image_attachment, att_id, str(body.get("focus", "")))


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


# ------------------------------------------------------------------ notes pinned to points of an answer
@router.get("/api/chat/sessions/{sid}/notes")
async def notes_list(sid: str):
    return {"notes": await call(lambda: store.get(sid).get("notes") or [])}


@router.post("/api/chat/sessions/{sid}/notes")
async def notes_add(sid: str, body: dict = Body(...)):
    """A note on a passage (quote + prefix/suffix anchor) or on a chart point ({chart, series, x, y}) of a message."""
    return await call(store.add_note, sid, body)


@router.put("/api/chat/sessions/{sid}/notes/{nid}")
async def notes_update(sid: str, nid: str, body: dict = Body(...)):
    return await call(store.update_note, sid, nid, body)


@router.delete("/api/chat/sessions/{sid}/notes/{nid}")
async def notes_delete(sid: str, nid: str):
    return await call(store.delete_note, sid, nid)


# ------------------------------------------------------------------ skills ("/" commands)
@router.get("/api/skills")
async def skills_list():
    from backend.agent import skills
    from backend.agent.ui_actions import catalog
    return {"skills": await call(skills.catalog), "actions": catalog(), "errors": await call(skills.errors)}


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
