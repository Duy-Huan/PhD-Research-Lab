"""Research memory as proposals: the context memory works in the background; what it wants to remember appears as a
proposal the researcher accepts or rejects. Pinned results are the durable outputs every conversation shares."""
from __future__ import annotations

from fastapi import APIRouter, Body

from backend.api.common import call

router = APIRouter()


@router.get("/api/memory/candidates")
async def candidates(status: str = "pending"):
    from backend.memory import lifecycle
    return {"candidates": await call(lifecycle.list_candidates, status)}


@router.post("/api/memory/candidates/{cid}/approve")
async def approve(cid: str, body: dict = Body(default={})):
    from backend.memory import lifecycle
    return await call(lifecycle.approve, cid, body.get("edits") or None)


@router.post("/api/memory/candidates/{cid}/reject")
async def reject(cid: str, body: dict = Body(default={})):
    from backend.memory import lifecycle
    return await call(lifecycle.reject, cid, str(body.get("reason", "")))


@router.put("/api/memory/sensitivity")
async def sensitivity(body: dict = Body(...)):
    """{id, level: PUBLIC | INTERNAL | SENSITIVE | RESTRICTED | ""} — RESTRICTED never leaves this computer."""
    from backend.providers.privacy import set_sensitivity
    return await call(set_sensitivity, str(body.get("id", "")), str(body.get("level", "")))


@router.get("/api/research")
async def research_state():
    """Decisions, hypotheses, experiments, failures (read-only; changes go through chat proposals)."""
    def run():
        from backend.memory import load, research
        r = research.load()
        return {"decisions": [d for d in load()["decisions"] if d.get("locked", True)], "hypotheses": r["hypotheses"],
                "experiments": r["experiments"], "failures": r.get("failures", [])}
    return await call(run)


@router.get("/api/pins")
async def pins_list(kind: str = "", status: str = ""):
    from backend.agent import pins
    return {"pins": await call(pins.list_pins, kind, status), "kinds": list(pins.KINDS), "statuses": list(pins.STATUS)}


@router.post("/api/pins")
async def pins_add(body: dict = Body(...)):
    from backend.agent import pins
    return await call(pins.add, str(body.get("kind") or "note"), str(body.get("title", "")), str(body.get("body", "")),
                      str(body.get("status") or "pinned"), body.get("provenance") or {})


@router.put("/api/pins/{pid}")
async def pins_update(pid: str, body: dict = Body(...)):
    from backend.agent import pins
    return await call(lambda: pins.update(pid, **{k: body[k] for k in ("kind", "title", "body", "status", "provenance") if k in body}))


@router.delete("/api/pins/{pid}")
async def pins_delete(pid: str):
    from backend.agent import pins
    return await call(pins.remove, pid)
