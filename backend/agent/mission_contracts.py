"""Typed control-plane contracts. Data from a model cannot enlarge these permissions."""
from typing import Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class Limits(Contract):
    max_tasks: int = Field(default=12, ge=1, le=24)
    max_seconds: int = Field(default=600, ge=1, le=3600)
    max_attempts: int = Field(default=2, ge=1, le=3)
    max_reasoning_calls: int = Field(default=1, ge=0, le=3)
    max_depth: int = Field(default=2, ge=0, le=3)
    max_hops: int = Field(default=12, ge=1, le=24)
    max_artifact_mb: int = Field(default=32, ge=1, le=128)


class Task(Contract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    capability: str = Field(max_length=80)
    args: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, max_length=24)
    preferred_engine: Literal["deterministic", "feynman", "openscience", "app"] = "deterministic"
    fallback_engines: list[Literal["feynman", "openscience", "app"]] = Field(default_factory=list, max_length=2)


class MissionControl(Contract):
    charter_id: str = ""
    charter_digest: str = ""
    hypothesis_id: str = Field(default="",max_length=200)
    exclusions: list[str] = Field(default_factory=list,max_length=20)
    success_criteria: list[str] = Field(min_length=1,max_length=20)
    allowed_engines: list[Literal["deterministic","feynman","openscience","app"]] = Field(default_factory=lambda:["deterministic"],min_length=1,max_length=4)
    app_backend: str = Field(default="ollama",max_length=80)
    app_model: str = Field(default="",max_length=200)
    allow_api_billing: bool = False
    not_before: datetime|None = None
    end_date: datetime
    max_wall_seconds: int = Field(default=3600,ge=1,le=86400)
    priority: int = Field(default=0,ge=0,le=10)
    review_required: Literal[True] = True
    predecessor_id: str = ""

    @model_validator(mode="after")
    def dates(self):
        if self.end_date.tzinfo is None or (self.not_before and self.not_before.tzinfo is None):raise ValueError("Mission dates require an explicit timezone")
        if self.not_before and self.not_before>=self.end_date:raise ValueError("Schedule must precede mission end date")
        return self


class MissionSpec(Contract):
    topic_id: str
    objective: str = Field(min_length=1, max_length=8000)
    questions: list[str] = Field(default_factory=list, max_length=20)
    inputs: list[str] = Field(default_factory=list, max_length=30)
    expected_artifacts: list[str] = Field(default_factory=list, max_length=20)
    permissions: list[Literal["network", "workspace_write", "reasoning", "compute"]] = Field(default_factory=list)
    limits: Limits = Field(default_factory=Limits)
    stop_conditions: list[str] = Field(default_factory=lambda: ["budget_exceeded", "failed_dependency"])
    routing_mode: Literal["manual", "assisted"] = "manual"
    owner: str = Field(default="researcher", min_length=1, max_length=100)
    parent_mission_id: str = ""
    control: MissionControl|None = None
    tasks: list[Task] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def dag(self):
        ids = {t.id for t in self.tasks}
        if len(ids) != len(self.tasks) or len(ids) > self.limits.max_tasks or len(ids) > self.limits.max_hops:
            raise ValueError("Duplicate task IDs or task/hop budget exceeded")
        pending = {t.id: set(t.depends_on) for t in self.tasks}
        if any(d not in ids for deps in pending.values() for d in deps):
            raise ValueError("Unknown task dependency")
        done = set()
        while pending:
            ready = {k for k, deps in pending.items() if deps <= done}
            if not ready:
                raise ValueError("Task dependency cycle")
            done |= ready
            pending = {k:v for k,v in pending.items() if k not in ready}
        return self


class EvidenceRef(Contract):
    source_id: str
    topic_id: str
    kind: Literal["paper", "evidence", "artifact", "experiment", "mission"]
    sha256: str = ""
    trust: Literal["untrusted", "measurement", "human_reviewed"] = "untrusted"


class ArtifactManifest(Contract):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(ge=0)
    scientific_review: Literal["pending"] = "pending"


class ToolCall(Contract):
    mission_id: str
    task_id: str
    idempotency_key: str
    capability: str
    args: dict


class ExecutionResult(Contract):
    status: Literal["completed", "failed", "unavailable", "interrupted"]
    output: dict = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    artifacts: list[ArtifactManifest] = Field(default_factory=list)
    engine: str = "deterministic"
    limitations: list[str] = Field(default_factory=list)
