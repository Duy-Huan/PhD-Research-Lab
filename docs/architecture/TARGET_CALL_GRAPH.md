# Actual context and provider call graph

This describes the implemented path; it does not claim the entire requested target architecture is complete.

```mermaid
flowchart TD
    API[api/chat: chat turn endpoint] --> Start[orchestrator.start]
    Start --> Run[orchestrator.run / _dispatch]
    Run --> Context[ContextBuilder.build]
    Context --> Project[project_context sources and pins]
    Context --> Corpus[knowledge evidence / selected papers]
    Context --> Memory[memory engine / compiler / LOD]
    Run --> App[orchestrator._app]
    Run --> CLI[orchestrator._cli]
    App --> Models[providers.models: agent runtime and streaming]
    CLI --> Prepare[gateway.prepare / provider_context]
    Prepare --> Send[gateway.send / CLI connector subprocess]
    Models --> Complete[orchestrator._complete]
    Send --> Complete
    Complete --> Persist[artifact / proposal / memory / retention writes]
    Persist --> Terminal[terminal turn state and SSE events]
```

`ContextBuilder.build(session, question, effective)` owns the existing deterministic module-context implementation. `context.compile` and `build_unified_context_packet` are aliases to that callable. It collects trust-labeled sources, budgets/deduplicates context and emits a manifest; default raw recency dumps from unrelated conversations were removed. Explicit folder sharing remains available.

The app path uses `_history` for the current session and `providers.models.agent_runtime` for the configured engine/model. The CLI path uses `gateway.prepare`, the provider context packet/compiler and `gateway.send`; adapter events feed the orchestrator. Terminal completion follows all postprocessing writes. Failed gateway partial text cannot become completed.

Actual CPU mission/protocol execution remains in `execution/` and native research engines; visual graph catalog nodes without executable adapters block rather than fabricate outputs. Knowledge owns corpus/provenance, memory owns conversational/working state, but legacy cross-domain adapters remain.

Remaining consolidation: absorb specialized `intelligence/context_gateway.py` and `knowledge/research_context.py` policies into a shared implementation without losing role/topic/privacy semantics; migrate overlapping memory evidence/research lookup with compatibility shims; unify smart router and policy implementations; qualify every research engine path. A facade alone is not evidence that these are done.
