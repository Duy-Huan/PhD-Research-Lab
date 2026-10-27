"""Tool specification, structured errors and semantic versions for the native tool capability system.

A ToolSpec describes WHAT a tool does and WHAT it needs (schemas, permissions, budgets); it never grants anything.
Authority always comes from a runtime Grant (backend.tools.runtime).
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.tools import schema as S

KINDS = ("native", "python", "cli", "mcp", "container")
PERMISSIONS = ("read", "workspace_write", "network", "compute", "process", "reasoning")
ID = r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){0,3}$"
SEMVER = re.compile(r"^(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})$")


def parse_version(v: str) -> tuple[int, int, int]:
    m = SEMVER.match(v or "")
    if not m:
        raise ValueError(f"Invalid semantic version: {v!r}")
    return tuple(int(x) for x in m.groups())


def satisfies(version: str, constraint: str) -> bool:
    """Constraint forms: "" / "*" (any), "1.2.3" (exact), "^1.2" / "^1.2.3" (same major, >=), ">=1.2.0"."""
    c = (constraint or "*").strip()
    if c == "*":
        return True
    have = parse_version(version)
    if c.startswith(">="):
        return have >= parse_version(c[2:].strip())
    if c.startswith("^"):
        parts = c[1:].strip().split(".")
        want = parse_version(".".join(parts + ["0"] * (3 - len(parts))))
        return have[0] == want[0] and have >= want
    return have == parse_version(c)


class ToolError(Exception):
    """A structured, agent-readable failure. `retryable` means repeating the SAME call may succeed (timeouts,
    transient unavailability); a validation or permission error is never retryable without changing the call."""

    CODES = ("not_found", "invalid_input", "invalid_output", "permission_denied", "budget_exceeded", "unavailable",
             "timeout", "cancelled", "execution_failed", "incompatible_version", "invalid_spec")

    def __init__(self, code: str, message: str, *, retryable: bool = False, hint: str = "", details: dict | None = None):
        if code not in self.CODES:
            raise ValueError(f"Unknown tool error code {code}")
        super().__init__(message)
        self.code, self.message, self.retryable, self.hint = code, message[:2000], retryable, hint[:500]
        self.details = details or {}

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "retryable": self.retryable, "hint": self.hint,
                "details": self.details}


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout_s: float = Field(default=60, gt=0, le=86400)
    max_output_bytes: int = Field(default=256_000, ge=1, le=64_000_000)
    memory_mb: int = Field(default=1024, ge=16, le=262_144)
    cpus: float = Field(default=1.0, gt=0, le=256)


class ToolSpec(BaseModel):
    """Versioned, schema-validated tool description. `execution` is adapter-specific and validated by the adapter."""
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=ID, max_length=120)
    version: str = "1.0.0"
    title: str = Field(default="", max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    kind: Literal["native", "python", "cli", "mcp", "container"]
    capabilities: list[str] = Field(default_factory=list, max_length=40)
    input_schema: dict = Field(default_factory=lambda: {"type": "object"})
    output_schema: dict = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    mutates: bool = False
    idempotent: bool = True
    max_retries: int = Field(default=0, ge=0, le=3)
    budget: Budget = Field(default_factory=Budget)
    execution: dict = Field(default_factory=dict)
    requires_app: str = ""
    deprecated: str = ""
    source: str = "builtin"
    examples: list[dict] = Field(default_factory=list, max_length=20)

    @field_validator("version")
    @classmethod
    def _version(cls, v):
        parse_version(v)
        return v

    @field_validator("permissions")
    @classmethod
    def _permissions(cls, v):
        bad = [p for p in v if p not in PERMISSIONS]
        if bad:
            raise ValueError(f"Unknown permissions {bad}; allowed {list(PERMISSIONS)}")
        return sorted(set(v))

    @field_validator("capabilities")
    @classmethod
    def _caps(cls, v):
        return sorted({c.strip().lower()[:60] for c in v if c.strip()})

    @field_validator("input_schema", "output_schema")
    @classmethod
    def _schemas(cls, v):
        errors = S.schema_errors(v) if v else []
        if errors:
            raise ValueError("; ".join(errors[:5]))
        return v

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def digest(self) -> str:
        """Content hash binding provenance records to the exact specification that ran."""
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True, default=str).encode()).hexdigest()

    def summary(self, available: dict | None = None) -> dict:
        """Compact entry for discovery listings; full schemas are loaded only by describe (lazy specification)."""
        out = {"id": self.id, "version": self.version, "kind": self.kind, "title": self.title or self.id,
               "description": self.description.split("\n", 1)[0][:240], "capabilities": self.capabilities,
               "permissions": self.permissions, "mutates": self.mutates}
        if self.deprecated:
            out["deprecated"] = self.deprecated
        if available is not None:
            out["available"] = available
        return out
