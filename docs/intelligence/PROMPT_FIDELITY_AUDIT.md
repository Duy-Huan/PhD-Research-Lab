# Prompt fidelity audit

The application prompt now explicitly permits calculation and ordinary reasoning while prohibiting fabricated empirical results. The prior instruction to answer only from recorded context suppressed valid arithmetic. User requests for no tools now prevent automatic memory/search proposals.

The current session history takes precedence for references to the previous answer. Default project context no longer dumps unrelated recent conversations; explicit folder sharing, selected sources, retrieved memory and project pins remain available. The real multi-turn regression verifies 17×23 then twice the previous answer, rather than an unrelated 42.

`ContextBuilder.build` is the canonical deterministic module-context compiler; `compile` and `build_unified_context_packet` are compatibility aliases to the same callable. Specialized research/provider adapters still exist, so complete system-wide context consolidation is not claimed.

The [native/wrapped comparison](NATIVE_VS_WRAPPED_BENCHMARK.md) records its prompt differences. Wrapped model identifier and token usage are not authoritatively exposed by the current HTTP API and remain unknown. No hidden model substitution was intentionally configured; unknown identity is not proof of equality.
