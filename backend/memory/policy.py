"""Context policies (v3.3 §6-7): per-role section budgets, scoring weights and explicit token budgeting.

A policy answers two questions for the compiler and the retrieval engine:
    1. how is the memory budget split over the sections (state / working / research / evidence / knowledge)?
    2. how much does each scoring dimension count for this role (relevance, evidence strength, centrality, recency, …)?

Shares are relative weights (normalised to 1); unused budget of a section flows to the next one in SECTION_ORDER.
The research state section is never starved: it gets `state_floor` of the memory budget before anything else.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

SECTION_ORDER = ("state", "research", "evidence", "working", "knowledge")

# relevance, importance, recency, confidence, evidence_strength, research_centrality, failure_prevention, task_fit
BASE_WEIGHTS = {"relevance": 1.0, "importance": 0.35, "recency": 0.25, "confidence": 0.2, "evidence_strength": 0.3,
                "research_centrality": 0.35, "failure_prevention": 0.25, "task_fit": 0.3, "low_confidence": 0.3}


@dataclass(frozen=True)
class RolePolicy:
    role: str
    label: str
    shares: dict
    weights: dict = field(default_factory=dict)
    type_fit: dict = field(default_factory=dict)   # node type → task fit in [0, 1]
    state_floor: float = 0.12

    def weight(self, dim: str) -> float:
        return self.weights.get(dim, BASE_WEIGHTS[dim])

    def to_dict(self) -> dict:
        return asdict(self)


def _w(**kw) -> dict:
    return {**BASE_WEIGHTS, **kw}


POLICIES = {
    "literature": RolePolicy("literature", "Literature Agent",
                             {"knowledge": 0.40, "evidence": 0.30, "research": 0.20, "working": 0.10},
                             _w(evidence_strength=0.45, failure_prevention=0.1, recency=0.1),
                             {"paper": 1.0, "claim": 0.9, "concept": 0.8, "method": 0.7, "evidence": 0.6, "hypothesis": 0.5}),
    "experiment_designer": RolePolicy("experiment_designer", "Experiment Designer",
                                      {"research": 0.45, "evidence": 0.25, "knowledge": 0.15, "working": 0.15},
                                      _w(failure_prevention=0.6, research_centrality=0.5, evidence_strength=0.35),
                                      {"experiment": 1.0, "failure": 1.0, "hypothesis": 0.9, "constraint": 0.9, "decision": 0.8,
                                       "evidence": 0.7, "metric": 0.7, "method": 0.6, "paper": 0.5}, state_floor=0.15),
    "coder": RolePolicy("coder", "Coding Agent",
                        {"working": 0.35, "research": 0.35, "knowledge": 0.15, "evidence": 0.15},
                        _w(recency=0.45, failure_prevention=0.5, task_fit=0.4),
                        {"failure": 1.0, "experiment": 0.9, "method": 0.9, "episode": 0.8, "note": 0.7, "constraint": 0.8,
                         "decision": 0.6}),
    "reviewer": RolePolicy("reviewer", "Paper Reviewer",
                           {"evidence": 0.40, "research": 0.30, "knowledge": 0.20, "working": 0.10},
                           _w(evidence_strength=0.6, confidence=0.4, low_confidence=0.5),
                           {"evidence": 1.0, "claim": 1.0, "experiment": 0.9, "metric": 0.9, "paper": 0.8, "failure": 0.6,
                            "decision": 0.6}),
    "writer": RolePolicy("writer", "Paper Writer",
                         {"evidence": 0.30, "knowledge": 0.30, "research": 0.30, "working": 0.10},
                         _w(evidence_strength=0.5, confidence=0.35),
                         {"claim": 1.0, "evidence": 0.9, "paper": 0.9, "experiment": 0.8, "metric": 0.8, "decision": 0.6}),
    "director": RolePolicy("director", "Research Director",
                           {"research": 0.40, "evidence": 0.25, "working": 0.20, "knowledge": 0.15},
                           _w(research_centrality=0.6, importance=0.5, recency=0.35),
                           {"hypothesis": 1.0, "decision": 1.0, "objective": 1.0, "experiment": 0.8, "failure": 0.8,
                            "claim": 0.7, "constraint": 0.8}, state_floor=0.18),
    "default": RolePolicy("default", "General",
                          {"research": 0.35, "working": 0.30, "knowledge": 0.20, "evidence": 0.15}, _w(), {}),
}
ROLE_ALIASES = {"literature_agent": "literature", "experiment": "experiment_designer", "designer": "experiment_designer",
                "coding": "coder", "code": "coder", "coding_agent": "coder", "paper_reviewer": "reviewer", "review": "reviewer",
                "paper_writer": "writer", "author": "writer", "research_director": "director", "general": "default"}
# app tools / agents → role (backward compatible: agent_block(tool, …) picks the role from the tool)
TOOL_ROLE = {"lit2plan": "literature", "search": "literature", "references": "literature", "library": "literature",
             "experiment": "experiment_designer", "ide": "coder", "coder": "coder", "codex": "coder",
             "reviewer": "reviewer", "review": "reviewer", "review_ext": "reviewer", "critic": "reviewer",
             "author": "writer", "editor": "writer", "paper": "writer", "masterclass": "writer",
             "context": "director", "context_agent": "director", "data": "default", "results": "reviewer",
             "results_analyst": "reviewer"}


def resolve_role(role: str = "", tool: str = "") -> str:
    r = (role or "").strip().lower()
    r = ROLE_ALIASES.get(r, r)
    if r in POLICIES:
        return r
    return TOOL_ROLE.get((tool or "").strip().lower(), "default")


def get(role: str = "", tool: str = "") -> RolePolicy:
    return POLICIES[resolve_role(role, tool)]


@dataclass
class Budget:
    """Explicit token budget of one compilation (§7). memory_budget is what the compiler may spend on memory."""
    max_tokens: int = 3500
    reserved_tokens: int = 0       # e.g. the model's answer, when the caller compiles against a full context window
    system_tokens: int = 0         # system prompt already spent by the caller
    task_tokens: int = 0           # the user's request / task text
    safety_margin: float = 0.05    # token estimates are chars/4 — keep a margin
    sections: dict = field(default_factory=dict)

    @property
    def memory_budget(self) -> int:
        free = self.max_tokens - self.reserved_tokens - self.system_tokens - self.task_tokens
        return max(200, int(free * (1 - self.safety_margin)))

    def split(self, policy: RolePolicy) -> dict:
        total = self.memory_budget
        state = int(total * policy.state_floor)
        rest = total - state
        norm = sum(policy.shares.values()) or 1.0
        self.sections = {"state": state, **{k: int(rest * v / norm) for k, v in policy.shares.items()}}
        return self.sections

    def to_dict(self) -> dict:
        return {"max_tokens": self.max_tokens, "reserved_tokens": self.reserved_tokens, "system_tokens": self.system_tokens,
                "task_tokens": self.task_tokens, "safety_margin": self.safety_margin, "memory_budget": self.memory_budget,
                "sections": dict(self.sections)}
