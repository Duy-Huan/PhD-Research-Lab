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


class NativeCodeTaskArgs(Contract):
    goal: str = Field(default="", max_length=8000)
    run_id: str = ""
    from_task: str = ""


class PaperWritingAction(Contract):
    question: str = Field(default="", max_length=10000)
    section: str = Field(default="", max_length=80)
    from_task: str = ""
    paper_ids: list[str] = Field(default_factory=list, max_length=50)
    figure_id: str = ""
    style: str = "IEEE"
    venue: str = ""


class AgentTaskArgs(Contract):
    """v6.6.4 (A9): one bounded sub-task for a team agent, run on the model the team bound it to."""
    agent: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    model: str = Field(min_length=1, max_length=120)
    instructions: str = Field(min_length=1, max_length=20000)
    tools: list[str] = Field(default_factory=list, max_length=30)  # registry tools the team gave this agent
    from_task: str = ""


class Checkpoint(Contract):
    title: str = Field(default="Review the results so far", min_length=1, max_length=300)


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
    "code.implement": NativeCodeTaskArgs,
    "paperorchestra.outline": PaperWritingAction,
    "paperorchestra.section_write": PaperWritingAction,
    "paperorchestra.refine": PaperWritingAction,
    "paperorchestra.cite_verify": PaperWritingAction,
    "paperorchestra.figure_integrate": PaperWritingAction,
    "paperorchestra.full_orchestration": PaperWritingAction,
    "agent.task": AgentTaskArgs,
    "review.checkpoint": Checkpoint,
})
META = {
    "experiment.verify": ("Independently check raw experiment artifacts",True,[],["deterministic"]),
    "artifact.verify": ("Check artifact hashes without certifying scientific interpretation",True,[],["deterministic"]),
    "experiment.run": ("Run an approved immutable CPU/Docker protocol",True,["compute","workspace_write"],["deterministic"]),
    "paper.discover": ("Discover topic metadata", True, ["network", "workspace_write"], ["deterministic"]),
    "paper.download": ("Resolve/download bounded OA PDFs", True, ["network", "workspace_write"], ["deterministic"]),
    "paper.inspect": ("Inspect scoped metadata and source versions", True, [], ["deterministic"]),
    "paper.compare": ("Synthesize selected source evidence", False, ["reasoning", "network", "workspace_write"], ["phdlab", "app"]),
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
    "code.implement": ("Create or inspect a native coding run; writes require its existing approval and completion requires actual files", True, ["workspace_write"], ["deterministic"]),
    "paperorchestra.outline": ("Generate structured paper outline, bullet points and citation hints", False, ["reasoning", "workspace_write"], ["paperorchestra", "app"]),
    "paperorchestra.section_write": ("Draft publication-ready LaTeX body section grounded in evidence", False, ["reasoning", "workspace_write"], ["paperorchestra", "app"]),
    "paperorchestra.refine": ("Refine and format LaTeX manuscript for target venue", False, ["reasoning", "workspace_write"], ["paperorchestra", "app"]),
    "paperorchestra.cite_verify": ("Verify in-text citations against project library and topic corpus", False, ["workspace_write"], ["paperorchestra", "app"]),
    "paperorchestra.figure_integrate": ("Integrate verified scientific figure artifacts into LaTeX manuscript", False, ["workspace_write"], ["paperorchestra", "app"]),
    "paperorchestra.full_orchestration": ("Multi-agent research-to-paper writing orchestration with quality gates", False, ["reasoning", "workspace_write"], ["paperorchestra", "app"]),
    "review.checkpoint": ("Pause until the researcher reviews the results so far (a Harness approval node)", True, [], ["deterministic"]),
    "agent.task": ("Run one bounded sub-task with a team agent on the model bound to it from the model list (no substitution)", False, ["reasoning", "workspace_write"], ["agent"]),
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
    if task.preferred_engine == "agent":
        from backend.agent import team_agents
        model = team_agents.check_model(task.args.get("model", ""))
        return {"engine": "agent", "model": model["id"], "why": "The team bound this agent to this model; no other model is tried"}
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
