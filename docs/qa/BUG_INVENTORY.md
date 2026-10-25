# Confirmed defect inventory — 2026-10-25

Machine-readable source: [defects.json](defects.json). Duplicate viewport findings are grouped under their shared cause; test-infrastructure mistakes are recorded separately.

| ID | Severity | Reproduction / actual result | Status | Regression |
|---|---|---|---|---|
| BUG-UI-001 | P1 | 375px: Open sidebar → Settings; navigation remains on top and intercepts Back to Workspace | LOCAL FIX VERIFIED in6.5.1; pending CI/merge | UI-MOBILE-SETTINGS-001 |
| BUG-UI-002 | P2 | Workspace/Settings: language, zoom and tools-panel names fail label-content-name-mismatch | LOCAL FIX VERIFIED in6.5.1; pending CI/merge | UI-ACCESSIBLE-NAMES-001 |

No P0 was confirmed by this limited campaign. This does not prove absence of undiscovered P0 defects. Both current confirmed defects block this requested quality baseline until fixed and independently checked.

## Infrastructure findings

Historical confirmed repairs retained in governance evidence: Linux Chromium binary lookup, Windows SQLite fixture cleanup, nested unit-package discovery, and missing/staging-sensitive source-attestation inputs. Actual RED/GREEN evidence is under evidence/governance; these repairs do not prove application research correctness.

The first two UI reconnaissance scripts used incorrect mobile sidebar selectors; those runs are incomplete infrastructure failures, not product defects. The corrected third run completed eight scans with no script errors. Its accessibility violations remain real findings. No expected assertions were relaxed.

## Next repair order

1. Restore mobile Settings usability, preserving desktop navigation.
2. Align accessible control names with visible text in both EN and VI.
3. Add permanent browser regressions to the canonical selector, retain RED/GREEN and update this registry after matching-source verification.
4. Complete global coverage and mandatory live evidence; these are qualification gaps, not fabricated application bugs.

## Controlled UI repair update

See UI_STABILIZATION_REPORT.md and evidence/ui-stabilization-6.5.1/manifest.json. Same test source: functional RED1PASS/4FAIL, GREEN5PASS/0FAIL/0SKIP. Both fixes remain open for independent CI and integration; no protected merge occurred. Sixteen EN/VI viewport/surface scans passed automated checks in GREEN. This is not full visual/screen-reader certification.
