# PhD Research Lab — engineering and QA continuation

## Start and resume

1. Read `agent/STATE.md`, `agent/PLAN.md` and `docs/quality/ZERO_FAKE_TESTING_POLICY.md`.
2. Run `git status --short`; preserve existing changes. Work on the recorded QA branch.
3. Read the latest run's machine-readable report and logs. An older report does not certify changed sources.
4. Select the first unfinished plan item, reproduce any failure, fix the cause and rerun affected checks. Record exact commands, source hashes, case counts, coverage and blockers in STATE.md.
5. Never reset, clean, stash, overwrite or commit unrelated user changes. Never run tests against real `data/` or `projects/`.
6. Never delete a file inside `skills/` or `agent/`, even when cleaning up. Preserve these continuation resources across versions and sessions.
7. User authorized versioned commits and pushes by stage on the task branch. Preserve unrelated dirty changes; never merge automatically. Native CLI forward actions must resolve installed local apps, not public websites.

## Test layers

- UNIT: deterministic tests with explicitly labeled mocks/faults; no live certification.
- INTEGRATION: actual application/storage/processes in a disposable profile.
- LIVE_PROVIDER: actual configured provider inference; binary detection or model listing alone is insufficient.
- REAL_E2E: browser/terminal → backend → actual provider/tools → persisted outputs.
- SCIENTIFIC: executed experiment, raw data, independent recomputation/replay and paper lineage. An LLM's answer is not an empirical measurement.

Run 2D browser journeys first, then 3D/WebGL, then native CLI chat/settings/locale. Preserve trace, screenshots, browser/network errors, request IDs and saved backend state. A WebGL fallback is not proof of 3D rendering.

## Commands (PowerShell, repository root)

```powershell
.venv/Scripts/python.exe tools/backend_quality_gate.py --profile full --i-understand-full-suite --output-dir output/playwright/<run>/backend
Push-Location frontend
npm ci
npx playwright install chromium
npm run typecheck
npm run test:coverage -- --reporter=json --outputFile=../output/playwright/<run>/frontend-tests.json
npm run build
# Start an isolated backend before browser tests; do not target a user's server.
$env:PHDLAB_E2E_URL='http://127.0.0.1:8771'
$env:PHDLAB_E2E_OUTPUT='../output/playwright/<run>/browser-2d'
npx playwright test --grep-invert '3D'
Pop-Location
```

Use `tools/playwright_server.py --help` for a disposable application server. The selected model must actually exist in LM Studio. Preferred user-authorized model: `spark-x2.5-4b`; Antigravity is the secondary authorized live path. Do not silently substitute another model/provider. Cloud providers without credentials remain BLOCKED. Bound request counts, tokens and deadlines.

## New feature regression contract

1. Add a stable requirement ID and expected behavior to the QA manifest before implementation.
2. Record API/CLI/2D/3D surfaces, locales, provider requirements, expected artifacts and failure conditions.
3. Add behavior-based tests for valid/invalid inputs, persistence, cancellation, errors and relevant approval boundaries.
4. Add graph fixtures to the existing workflow generator for new workflow nodes; preserve failing seeds. Generated inventories are UNVERIFIED until assertions execute.
5. Run affected tests first, then full regression. Run live E2E for changes to providers, prompts, context, streaming or artifact generation.
6. Evaluate coverage over all production sources; never narrow exclusions, copy expected metrics into actual results or weaken assertions to reach 100%.
7. Update evidence and STATE.md. CI must fail closed on missing evidence, skips in mandatory cases, failures and incomplete coverage.

## Skills

See `skills/SOURCES.json` for GitHub revisions and licenses. `playwright` supports browser investigation; `webapp-testing` supports local server/browser lifecycle; `security-best-practices` supports security review; `gh-fix-ci` is for inspecting an actual failing GitHub PR, not a prerequisite for local CI work. Installed skills are available for discovery on the next turn; instructions can be read directly now.

## Architecture

Preserve all features and public imports. When two supplied prompts conflict (delete old modules vs preserve compatibility shims), retain shims while consumers remain. Unify actual behavior only after call-graph inspection and baseline tests. Do not disable research engines globally merely to make tests green. No cosmetic refactor should precede evidence-integrity defects.
