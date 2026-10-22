# UI refinement audit — 2026-10-22

Baseline: `459fc13`, real application seeded by `tools/demo_server.py`, Edge at 1440 × 900. Screenshot: `artifacts/ui-refinement/before.png`.

The existing sidebar, central chat composer, routes and right contextual drawer are retained. No framework or animation dependency is added.

| Priority | Finding | Change |
| --- | --- | --- |
| P0 | Research drawers contain English literals in Vietnamese mode | Explicit translations of interface labels; user text and scientific identifiers stay intact |
| P0 | PDF upload can overwrite an identically named file; downloads use opaque names | One metadata and content based filename convention, original-name provenance, duplicate detection |
| P1 | Project creation is buried in a menu | Project browser in the existing right drawer, grouped conversations and explicit create action |
| P1 | Research-result pin is confused with message pin | Separate persistent message pin, accessible pinned-message browser |
| P1 | Chat history uses rolling 24-hour intervals | Calendar-day separators, localized full dates and month groups |
| P1 | Only light/dark/system themes | Local, data-only theme packages with install/select/remove and VS Code color import |
| P2 | Faint labels, cramped controls and abrupt transitions | Refine semantic tokens, focus, spacing, contrast and reduced-motion behavior |

Baseline regression passes 99 frontend tests. Baseline measured coverage is 97.06% lines, 93.81% branches, 89.98% functions. The existing strict runner reports 299 uncovered line/branch entries; the upgrade must retain the full first-party JavaScript scope.

Validation: use real-browser before/after captures, language and theme checks, drawer/modal interactions, small-screen overflow and keyboard focus; Node/jsdom regression and V8 line/branch/function coverage; backend tests for project scope, pins and PDF ingestion.

## Completed review

The baseline and matching `after.png` use a 1440 × 900 Edge window (1416 × 808 captured content on this Windows host). Additional checks emulate a 390 × 844 mobile viewport and a 1440 × 900 English desktop viewport.

The final browser review found and corrected:

- Input focus outlines overridden by base input styles.
- Narrow settings tabs shrinking into vertically wrapped words.
- Mobile header buttons competing with the conversation title.
- User-message timestamps appearing beside rather than below their bubble.
- A literal `null` from a conditional native `append()` in the run footer.
- Theme selection not updating the Settings dropdown after clicking a theme card.
- Browser-native English file-picker text in the Vietnamese theme installation flow.
- Slow provider probes delaying the settings controls below their status list.

The layout still uses the original sidebar, main chat and contextual drawer. Custom theme packages are data-only. User text, scientific identifiers, source records and JSON contract keys are preserved. Existing curated Library filenames remain stable; new uploads, direct-directory imports and downloads use the shared convention.

All 14 first-party JavaScript files, including the extracted first-paint script, are in the strict coverage gate. Final logs, screenshots and browser assertions are recorded in [the validation report](../artifacts/ui-refinement/validation.md).
