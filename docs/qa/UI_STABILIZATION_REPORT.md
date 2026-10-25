# UI stabilization candidate 6.5.1

Status: verified locally for the stated regressions; independent required CI and integration remain pending. No zero-bug or release certification.

The baseline found two product defects: mobile Settings remained underneath the navigation overlay, and visible control text was missing from accessible names. A controlled pointer-action reproduction confirmed the first issue; axe found the second on the running application. These were not mocked pages.

AppShell now closes mobile navigation when the Settings main view opens, preserving desktop navigation. Header accessible names include the current language, percentage and visible tools-panel label; the floating menu includes its visible Vietnamese label too. UI appearance is unchanged.

| Requirement | Actual test | Result |
|---|---|---|
| UI-MOBILE-SETTINGS-001 | Open mobile sidebar -> Settings -> verify navigation hidden -> click Back -> chat input visible, at375/768px | Functional RED fails both; GREEN passes both |
| UI-DESKTOP-SETTINGS-001 | Open Settings at1280px, sidebar remains available, Back returns to chat | PASS before/after |
| UI-ACCESSIBLE-NAMES-001 | Running Workspace and Settings, EN/VI,375/768/1280/1920px; WCAG tags and document overflow | Functional RED fails both locale cases; GREEN passes both |

Same test-source SHA256 in functional RED/GREEN: `4f1c5ac3ee8087d66ff86acf1fe688cc2ec66580e7209d5d8d628e23967bcd62`. Raw results, screenshot/trace attachments, command logs and source identities are retained in evidence/ui-stabilization-6.5.1. RED:1PASS/4FAIL; GREEN:5PASS/0FAIL/0SKIP. The five cases include sixteen accessibility scans. Required assertions were retained; no axe rule exclusion was added.

The first candidate run also exposed a mobile bootstrap helper requiring a hidden desktop New chat button. The new mobile tests now wait for connection and the rendered chat input, then execute the actual navigation behavior. Corrected tests were rerun against the original AppShell/Header sources to preserve functional RED, followed by the same tests against the fix. The additional Vietnamese floating-menu name failure was repaired within the same defect group. BUG-UI-001-002 repair ledger retains one failed repair and success; the exhausted AI-UAT key is unchanged. No model calls were made.

The new browser suite is part of the canonical deterministic smoke list, so future browser CI executes these checks without AI. Existing @axe-core/playwright is reused; no second test framework is introduced. The current JSON contract validator supports Python symbols only; this report traces actual Playwright IDs explicitly and does not invent Python/full-project contract coverage.

This branch was created from actual origin/dev, then merged the pending governance dependency so the canonical verifier is available. It must not be merged around that dependency's failing quality gates. Version6.5.1 is a candidate, not a published release.

Limitations: automated axe scans do not cover all WCAG criteria, screen-reader behavior, visual correctness or every application route. Captured screenshots are review evidence; no visual golden baseline has been automatically approved. Full coverage, live provider/research workflow proof, protected CI and release reviews remain required.
