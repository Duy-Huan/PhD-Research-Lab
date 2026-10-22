"""Lazy adapter registration. Core dispatch depends on the research-engine port."""
from backend.research_engines.contracts import EngineFailure

FACTORIES = {"feynman": ("backend.research_engines.feynman", "FeynmanEngine"),
             "openscience": ("backend.research_engines.openscience", "OpenScienceEngine")}


def get(engine_id: str):
    from importlib import import_module
    if engine_id not in FACTORIES:
        raise EngineFailure("Unknown research engine", "capability")
    module, name = FACTORIES[engine_id]
    return getattr(import_module(module), name)()


def plan(mode: str, capability: str, preferred: str = "feynman") -> list[str]:
    from backend.core.config import load_config
    cfg = load_config()
    if mode == "collaborative":
        return ["openscience", "feynman"] if capability in ("analysis", "prototype") else ["feynman", "openscience"]
    if mode in FACTORIES:
        return [mode]
    if mode != "auto":
        raise EngineFailure("Unknown research engine mode", "capability")
    if preferred == "openscience":  # explicit /science delegation never silently changes engine
        return ["openscience"]
    settings = cfg.get("openscience") or {}
    qualified = capability in settings.get("qualified_tasks", []) and bool(settings.get("model_provider") and settings.get("model_id"))
    for candidate in cfg["research_providers"].get("engine_priority", ["feynman", "openscience"]):
        if candidate not in FACTORIES:
            continue
        engine = get(candidate)
        if capability not in engine.descriptor.capabilities:
            continue
        if candidate == "openscience" and not qualified:
            continue
        if candidate == "openscience" and capability in ("analysis", "prototype") and not settings.get("allow_execution"):
            continue
        if engine.health().get("ready"):
            return [candidate]
    return [preferred]  # existing fail-closed preflight presents a provider decision
