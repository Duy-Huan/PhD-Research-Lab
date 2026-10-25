# JSON and API contract audit

The current OpenAPI document was compared with the actual task base `d3c1dc6d2268413c3826d8ce49fe3af55495d11d`: **318/318 operations, zero removed/added operations, zero structural operation changes and zero changed schemas**. Two provider-launch descriptions changed to explain native apps. [Machine comparison](../qa/evidence/2026-10-25/api-task-parity.json).

The older checked-in snapshot has 274 operations and already differs from the task base. Its 44 additional operations, optional bodies and schema differences are reported separately in [historical comparison](../qa/evidence/2026-10-25/api-parity.json). It was not overwritten to manufacture parity.

Static OpenAPI parity does not establish all runtime JSON or SSE semantics. Existing API and streaming tests plus selected real browser/CLI paths cover their assertions only. Evidence records use strict modes/statuses, require execution/artifacts for live/scientific claims, and reject mocked live success. Malformed JSON, partial provider output, unsupported actions and fallback provenance still require provider-specific qualification.
