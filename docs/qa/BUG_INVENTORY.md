# Current defect inventory:6.5.6

Authoritative paired triage: [MAIN_CANDIDATE_DEFECTS.json](MAIN_CANDIDATE_DEFECTS.json). Existing accounting: [KNOWN_ISSUES_BASELINE.json](KNOWN_ISSUES_BASELINE.json) and [historical UI findings](defects.json). No baseline exception is approved or applied.

| Scope | P0 | P1 | P2 | Qualification |
|---|---:|---:|---:|---|
| Main, minimum confirmed groups |0|7|3|Partial inventory; includes shared source-confirmed3D locale defect |
| Candidate, unresolved groups in same inventory |0|0|1|Partial inventory; not zero-bug certification |

The shared3D localization finding uses identical source-review criteria on both revisions; candidate browser reproduction is retained. Main's runtime localization reproduction is NOT_RUN. It is additional to the10 fixed software groups, not an invented failed automated case.

**OPEN BUG-3D-LOCALE-001 / P2 / release-blocking for the owner's requested clean UI baseline.** Set UI English, open3D, select HPC Rack, inspect its label and PI role card. Expected English system labels; actual Vietnamese text is hard-coded in OfficeScene.tsx and eventAdapter.ts. Root cause: locale-sensitive defaults bypass localization. [Source review](evidence/comparison-6.5.6/locale-source-review.json), [actual screenshot](evidence/comparison-6.5.6/candidate/visual/3d-3d-real.png). Owner: recovery frontend/SDET. Repair status OPEN; planned regression UI-3D-LOCALE-001 is NOT_IMPLEMENTED. Next: behavior-based EN/VI regression, smallest localization repair, targeted/feature/full evidence. No intentional redesign is approved.

Local verified repairs include premature experiment completion (deterministic delayed collector RED then17PASS affected tests), Linux executable packaging fixture (original6tests:1ERROR; corrected6PASS on POSIX and6PASS Windows), remote compute NameError, context completeness, CLI settings parity, evidence authenticity and accessibility naming. Their original failures remain retained. Source-confirmed fixes are not protected merges.

The remote NameError existed on main; the former newly-introduced classification is withdrawn. Missing newer APIs/modules, selector mismatches and loader errors are separate from proven product regressions. In particular a missing Open sidebar selector cannot reproduce the later overlay-interception root cause. No new product regression is observed in executed common cases; unknown/unexecuted scope remains.

Coverage deficits, unavailable provider/SDK infrastructure, exhausted AI-UAT and missing trusted research evidence are qualification blockers. Earlier latency318.167ms under a300ms assertion remains an unresolved load/instrumentation observation; later isolated passes do not erase it or establish its cause.
