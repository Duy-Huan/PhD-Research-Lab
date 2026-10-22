"""External engine receipts and live decisions, separate from model/provider APIs."""
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from backend.api.common import call
from backend.research_engines import registry
from backend.research_engines.openscience import inspect_job, decide, recover_admission, cancel_job

router = APIRouter()


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=200)
    reply: Literal["once", "reject"] = "reject"
    answers: list[Annotated[list[Annotated[str, Field(max_length=4000)]], Field(max_length=50)]] | None = Field(default=None, max_length=20)


def public(value, _token=None):
    from backend.core.telemetry import redact
    if _token is None:
        from backend.core.config import load_config
        _token = load_config().get("openscience", {}).get("token", "")
    if isinstance(value, str):
        return redact(value).replace(_token, "[REDACTED]") if _token else redact(value)
    if isinstance(value, dict):
        return {k: public(v, _token) for k, v in value.items()}
    if isinstance(value, list):
        return [public(v, _token) for v in value]
    return value


@router.get("/api/research-engines")
async def engines():
    def inventory():
        return [{"descriptor": registry.get(k).descriptor.model_dump(), "health": registry.get(k).health()} for k in registry.FACTORIES]
    return {"engines": await call(inventory)}


@router.get("/api/research-engines/jobs/{job_id}")
async def job(job_id: str):
    return public(await call(inspect_job, job_id))


@router.post("/api/research-engines/jobs/{job_id}/decisions")
async def decision(job_id: str, body: Decision):
    return public(await call(decide, job_id, body.request_id, reply=body.reply, answers=body.answers))


@router.post("/api/research-engines/jobs/{job_id}/recover-admission")
async def recover(job_id: str):
    return await call(recover_admission, job_id)


@router.post("/api/research-engines/jobs/{job_id}/cancel")
async def cancel(job_id: str):
    return await call(cancel_job, job_id)
