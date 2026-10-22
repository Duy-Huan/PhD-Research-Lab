"""Versioned application boundary, independent of vendor implementations."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class EngineTask(Contract):
    operation_id: str = Field(pattern=r"^RR-[0-9a-f]{8}:S[0-9]+$")
    attempt: int = Field(default=1, ge=1)
    project_id: str
    workflow_id: str
    step_id: str
    question: str = Field(min_length=1, max_length=60000)
    context: str = Field(default="", max_length=200000)
    capability: Literal["literature", "analysis", "prototype", "review"] = "literature"
    native_workflow: str = ""
    output_dir: Path
    approved: bool = False
    time_limit_s: float = Field(default=600, gt=0, le=7200)
    hypothesis_id: str = ""
    experiment_id: str = ""


class EngineEvent(Contract):
    engine: str
    type: Literal["status", "text_delta", "tool", "artifact", "decision", "usage"]
    sequence: int | None = None
    data: dict = Field(default_factory=dict)


class EngineResult(Contract):
    engine: str
    text: str
    artifact_refs: list[dict] = Field(default_factory=list)
    native_session_id: str = ""
    native_run_id: str = ""
    provenance: dict = Field(default_factory=dict)


class EngineDescriptor(Contract):
    id: str
    capabilities: list[str]
    transport: str
    token_streaming: bool
    native_sessions: bool
    skills_owner: Literal["engine"] = "engine"


class EngineFailure(RuntimeError):
    def __init__(self, message: str, kind: str = "execution", *, job_id: str = "", pending: list | None = None):
        from backend.core.telemetry import redact
        super().__init__(redact(message)[:700])
        self.kind, self.job_id, self.pending = kind, job_id, pending or []


class ResearchEngine(Protocol):
    descriptor: EngineDescriptor

    def health(self) -> dict: ...

    def execute(self, task: EngineTask, emit: Callable[[EngineEvent], None], cancelled: Callable[[], bool]) -> EngineResult: ...
