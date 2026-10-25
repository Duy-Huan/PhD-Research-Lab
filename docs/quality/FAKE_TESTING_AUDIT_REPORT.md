# Evidence integrity audit — 2026-10-25

Release acceptance remains **NO-GO**. See [measured results](../qa/RELEASE_READINESS.md) and [policy](ZERO_FAKE_TESTING_POLICY.md).

| Confirmed mechanism | Repair | Permanent oracle |
|---|---|---|
| Legacy harness returned fixed benchmark scores and default success without execution | Known tools without executors return blocked; unknown tools unsupported; metrics stay empty | `test_evidence_integrity_regressions` |
| Visual workflow synthesized token/confidence/citation/file counters and approved human gates | Control flow is distinguished from execution; unauthorized adapters block; explicit approval is required | `test_harness_workflow_ide`, integrity regressions |
| Reproducibility replay copied expected metrics into actual measurements | Integrity verification is separate from execution; no executable protocol means unverified, not passed | Integrity regressions, real Golden Thread |
| Library enrichment inferred invented authors, year, venue and Q1 rank from URLs | Missing metadata remains missing; imported ranking evidence is required | Integrity regressions |
| Deterministic workflow templates labeled AI-generated | `generated_by_ai=false`, explicit deterministic generation method | Updated v6.4 regressions |
| PNG export was a fixed grid; PDF export was a text placeholder, independent of data | SVG → svglib/ReportLab vector PDF → PDFium PNG; actual data changes the exported image | `test_figure_export_integrity` |
| Existing placeholder figure versions could still be exported or approved | Immutable originals preserved; PNG/PDF export, approval and paper attachment require regeneration | Legacy figure regression |
| Success was inferred while completion postprocessing was still writing | Terminal completion follows artifact, memory and retention writes; cancellation flag survives until worker exit | `test_intelligence_preservation`, orchestrator tests |

Visual inspection invalidated the earlier `golden-third` and `golden-final` paper exports despite their script status. Their original records remain local. The published `golden-verified` paper was regenerated after the renderer repair and visually inspected.

`tools/qa_harness.py audit` implements narrow AST rules for the confirmed hardcoded-metric, copied-replay and mock-in-live-test patterns. A clean result does not prove every source line free of fabricated behavior. Unit fixtures are allowed when labeled as such; they cannot certify a live provider or scientific claim.
