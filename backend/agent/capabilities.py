"""Versioned whitelisted capabilities, layered over existing registries (not a shell/plugin runtime)."""
from typing import Literal
from pydantic import Field
from backend.agent.mission_contracts import Contract, Task
from backend.execution.protocol_contracts import ProtocolRef


class Capability(Contract):
    id: str
    version: str = "1.0"
    description: str
    deterministic: bool
    permissions: list[str]
    compatible_engines: list[str]
    input_schema: dict
    output_schema: dict = Field(default_factory=lambda: {"type":"object"})
    estimated_cost: str = "local I/O; no LLM"


class Discover(Contract):
    limit: int = Field(default=10, ge=1, le=100)


class PaperIDs(Contract):
    paper_ids: list[str] = Field(default_factory=list, max_length=100)
    from_task: str = ""
    limit: int = Field(default=2, ge=1, le=25)


class Compare(PaperIDs):
    question: str = Field(default="Compare the selected evidence with explicit uncertainties", max_length=4000)


class Sync(Contract):
    workspace_id: str


class Report(Contract):
    title: str = Field(default="Mission evidence report", max_length=200)


class Verify(Contract):
    from_task:str=""
    run_id:str=""


class FigureAction(Contract):
    figure_id: str = ""
    title: str = Field(default="Scientific Figure", max_length=300)
    experiment_id: str = ""
    from_task: str = ""
    preset: str = "ieee-single-column"
    plot_kind: str = "line"
    dot_source: str = ""
    waveform: dict = Field(default_factory=dict)


class OpenCodeTaskArgs(Contract):
    goal: str = Field(default="Implement and verify baseline module", max_length=8000)
    workspace_id: str = ""
    from_task: str = ""


INPUTS = {"paper.discover": Discover, "paper.download": PaperIDs, "paper.inspect": PaperIDs,
          "paper.compare": Compare, "workspace.sync": Sync, "mission.report": Report,"experiment.run":ProtocolRef}
INPUTS.update({"experiment.verify":Verify,"artifact.verify":Verify})
INPUTS.update({
    "figure.create_2d": FigureAction,
    "figure.create_comparison": FigureAction,
    "figure.render_diagram": FigureAction,
    "figure.render_waveform": FigureAction,
    "figure.create_3d": FigureAction,
    "figure.validate": FigureAction,
    "figure.export": FigureAction,
    "figure.regenerate": FigureAction,
    "opencode.implement": OpenCodeTaskArgs,
})
META = {
    "experiment.verify": ("Independently check raw experiment artifacts",True,[],["deterministic"]),
    "artifact.verify": ("Check artifact hashes without certifying scientific interpretation",True,[],["deterministic"]),
    "experiment.run": ("Run an approved immutable CPU/Docker protocol",True,["compute","workspace_write"],["deterministic"]),
    "paper.discover": ("Discover topic metadata", True, ["network", "workspace_write"], ["deterministic"]),
    "paper.download": ("Resolve/download bounded OA PDFs", True, ["network", "workspace_write"], ["deterministic"]),
    "paper.inspect": ("Inspect scoped metadata and source versions", True, [], ["deterministic"]),
    "paper.compare": ("Synthesize selected source evidence", False, ["reasoning", "network", "workspace_write"], ["feynman", "openscience", "opencode", "app"]),
    "workspace.sync": ("Reconcile native workspace files", True, ["workspace_write"], ["deterministic"]),
    "mission.report": ("Write evidence manifest and pending-review report", True, ["workspace_write"], ["deterministic"]),
    "figure.create_2d": ("Create deterministic 2D publication plot from verified source data", True, ["workspace_write"], ["deterministic"]),
    "figure.create_comparison": ("Create multi-panel scientific image comparison plate", True, ["workspace_write"], ["deterministic"]),
    "figure.render_diagram": ("Render deterministic Graphviz/DOT architecture or DAG diagram", True, ["workspace_write"], ["deterministic"]),
    "figure.render_waveform": ("Render deterministic WaveDrom digital timing diagram", True, ["workspace_write"], ["deterministic"]),
    "figure.create_3d": ("Render deterministic 3D scientific surface/mesh projection", True, ["workspace_write"], ["deterministic"]),
    "figure.validate": ("Verify figure numerical integrity and data hash against source", True, [], ["deterministic"]),
    "figure.export": ("Export verified figure artifact in SVG/PNG/PDF formats", True, ["workspace_write"], ["deterministic"]),
    "figure.regenerate": ("Regenerate immutable figure version from FigureSpec and source data", True, ["workspace_write"], ["deterministic"]),
    "opencode.implement": ("Delegate scoped repository analysis, code edit, or test execution to OpenCode", False, ["reasoning", "workspace_write"], ["opencode", "app"]),
}


def catalog() -> list:
    return [Capability(id=k, description=v[0], deterministic=v[1], permissions=v[2], compatible_engines=v[3],
                       input_schema=INPUTS[k].model_json_schema(), estimated_cost="Explicit provider usage; bounded calls" if not v[1] else "local I/O; no LLM").model_dump() for k,v in META.items()]


def validate_task(task: Task):
    if task.capability not in INPUTS:
        raise ValueError("Unknown or disabled capability: " + task.capability)
    INPUTS[task.capability].model_validate(task.args)
    meta = META[task.capability]
    if meta[1] and (task.preferred_engine != "deterministic" or task.fallback_engines):
        raise ValueError("Deterministic capabilities cannot invoke inference engines")
    if not meta[1] and task.preferred_engine not in meta[3]:
        raise ValueError("Choose an explicit compatible reasoning engine")


def route(task: Task) -> dict:
    validate_task(task)
    if META[task.capability][1]:
        return {"engine":"deterministic", "why":"Typed deterministic operation bypasses every LLM provider"}
    from backend.research_engines import registry
    unavailable = []
    for engine in [task.preferred_engine, *task.fallback_engines]:
        if engine == "app":
            return {"engine":"app", "why":"Explicit configured application provider", "fallback_from":unavailable}
        adapter = registry.get(engine)
        if "literature" in adapter.descriptor.capabilities and adapter.health().get("ready"):
            return {"engine":engine, "why":"Existing adapter advertises literature capability and is ready", "fallback_from":unavailable}
        unavailable.append(engine)
    raise ValueError("Requested engines unavailable; no implicit fallback: " + ", ".join(unavailable))


def skill_manifest(name: str) -> dict:
    from backend.agent import skills
    skill = skills.get(name)
    return {"id":skill["name"], "version":"legacy-1", "description":skill["description"],
            "kind":"declarative_procedure", "input_schema":{"type":"object","properties":{"question":{"type":"string"}}},
            "output_schema":{"type":"object"}, "requirements":["explicit mission plan"],
            "compatible_engines":[skill["provider"]], "permissions_are_granted":False,
            "estimated_cost":"provider dependent", "deterministic":False, "origin":skill["origin"]}
