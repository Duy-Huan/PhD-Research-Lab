"""Supported research inventory and read-only retired-run history."""
import json
import re
from fastapi import APIRouter, HTTPException
from backend.api.common import call
from backend.research_engines import registry

router = APIRouter()


def public(value):
    from backend.core.telemetry import redact
    if isinstance(value, str): return redact(value)
    if isinstance(value, list): return [public(v) for v in value]
    if isinstance(value, dict):
        return {k: public(v) for k, v in value.items() if k.lower() not in ("token", "password", "api_key", "authorization")}
    return value


@router.get("/api/research-engines")
async def engines():
    def inventory():
        return [{"descriptor": registry.get(k).descriptor.model_dump(), "health": registry.get(k).health()} for k in registry.FACTORIES]
    return {"engines": await call(inventory)}


@router.get("/api/research-engines/jobs/{job_id}")
async def job(job_id: str):
    from backend.core.config import data_dir
    from backend.knowledge.research_store import safe_child
    if not re.fullmatch(r"ej-[0-9a-f]{20}", job_id): raise HTTPException(400, "Invalid historical job id")
    path = safe_child(data_dir(), "research-engines", "jobs", job_id + ".json")
    if not path.is_file(): raise HTTPException(404, "Historical job not found in current project")
    return public(json.loads(path.read_text("utf-8")))


@router.post("/api/research-engines/jobs/{job_id}/decisions")
@router.post("/api/research-engines/jobs/{job_id}/recover-admission")
@router.post("/api/research-engines/jobs/{job_id}/cancel")
async def retired_mutation(job_id: str):
    raise HTTPException(410, "External research runtime retired; historical receipts remain read-only. No provider action was executed.")
