# Memory integrity report

The confirmed context poisoning bug imported an unrelated chat's numeric answer into a new conversation. Default context now excludes that conversation unless explicitly shared/selected; the current session history resolves follow-up references. Unit and real browser regressions exercise this behavior.

Temporal retrieval previously called the moving clock separately for each record's sort key. Equal stored timestamps could acquire different ages and reorder evidence between provider requests. It now orders stored instants directly, normalizes timezone offsets and uses record ID for ties; unknown timestamps sort last. A regression checks equal instants and reversed inputs without sampling the clock.

The Golden Thread demonstrates source PDF provenance, project pins and selected/retrieved memory in one context manifest. This is a fixture-specific result. Complete migration of evidence/research lookup from `memory/` into canonical `knowledge/` stores, all role/session boundaries, privacy classes and durable multi-client behavior remains open. No memory files were deleted or global research engines disabled for a green suite.
