"""Lazy adapter registration. Core dispatch depends on the research-engine port."""
from backend.research_engines.contracts import EngineFailure

FACTORIES = {
    "phdlab": ("backend.research_engines.phdlab", "PhDLabEngine"),
    "paperorchestra": ("backend.research_engines.paperorchestra.engine", "PaperOrchestraEngine"),
}


def get(engine_id: str):
    from importlib import import_module
    if engine_id not in FACTORIES:
        raise EngineFailure("Unknown research engine", "capability")
    module, name = FACTORIES[engine_id]
    return getattr(import_module(module), name)()


def plan(mode: str, capability: str, preferred: str = "phdlab") -> list[str]:
    """Native by default; explicit supported runtimes remain explicit, never renamed."""
    if mode in ("auto", "phdlab", "app", "native"):
        candidate = preferred if mode == "auto" else "phdlab"
        if candidate == "app": candidate = "phdlab"
        if candidate not in FACTORIES:
            raise EngineFailure("Requested research engine is retired or unsupported", "capability")
        return [candidate]
    if mode in FACTORIES: return [mode]
    raise EngineFailure("Requested research engine is retired or unsupported", "capability")
