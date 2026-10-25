# CI recovery root causes — 2026-10-25

Decision: **NO-GO for merge or release.** The inspected CI is correctly refusing incomplete qualification. Not all red jobs are broken test infrastructure.

## Preserved source and actual runs

The original four worktrees are retained. Their HEADs/status are in [worktrees.json](evidence/ci-recovery-2026-10-25/worktrees.json). Binary HEAD/index patches and untracked copies remain private under the original workspace's `output/playwright/ci-recovery/preserved/`. Recovery started from clean dev `6725975261fe6a4d8a5cb3e10208e31c3e24f0e2`, then explicitly merged published UI/governance dependency `c737d133a193d0737f9bf3c42bfc0bbfe9cca993`. Unpublished `71e5332` automation is parked, not silently discarded or activated.

Downloaded actual job logs and bounded artifact archives for [governance run40148986328](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40148986328) at `1a7e494` and [UI run40150782744](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40150782744) at `c737d13`. Full raw downloads remain in the original ignored output; selected raw reports, job metadata and SHA256 manifest are checked in under [evidence](evidence/ci-recovery-2026-10-25/manifest.json). Reports identify observed revisions; they do not certify the recovery candidate.

## Grouped diagnoses

| Group | Actual evidence | Classification and action |
| --- | --- | --- |
| Python3.11 clean dev | `compileall` fails at `backend/paper/export.py:379`, f-string backslash | Proven existing compatibility defect at6725975; syntax repair already in published governance dependency. Do not blame current hosted dependency installation. |
| Four backend matrix jobs | Each854 run:849 PASS,5 SKIP,0 assertion failures/errors; combined coverage87.32–87.72% on c737d13 | Coverage qualification gap plus unavailable live/optional infrastructure. Installation, pip check and compilation steps succeeded. Preserve100% requirement and incomplete-case blocking. |
| Frontend |174 assertions PASS; lines2439/3799=64.20%,branches2595/4095=63.36%,functions731/1454=50.27%,statements2568/4094=62.72% | Whole-source coverage gap. Typecheck/build succeeded in the artifact; test gate exits nonzero for unmet thresholds. No confirmed assertion regression in this run. |
| AI-UAT | `Required AI-UAT evidence is missing`; current selection NOT_RUN; additional adapters NOT_IMPLEMENTED | Missing execution/evidence producer and exhausted local adapter repair budget. Correctly BLOCKED, not a false test pass. No paid model calls or mock replacement. |
| Development gate | All upstream `failure` values were rewritten BLOCKED | Introduced reporting defect in bd71705. Reproduced functional RED and fixed to retain FAIL plus raw upstream results. Blocking behavior remains intact. |
| Baseline policy identity | Initial local baseline addition was omitted from source input hashing | Caught before publication by functional RED; baseline file now invalidates source evidence. |
| Browser/policy/security | Actual successful checks on inspected runs | Earlier Playwright binary lookup fix is present and actual hosted browser check succeeds. These checks alone do not qualify live/scientific workflows. |

No new test specification defect is confirmed by these runs. Earlier local latency318.167ms under a300ms assertion remains an unresolved observation in `defects.json`; isolated passes do not erase that failure. First affected revisions are observations, not an invented bisection result.

## Controlled repair and accounting

Permanent tests preserve failed/missing/skipped/cancelled distinctions; only complete required success may PASS. Machine-readable [known issues](KNOWN_ISSUES_BASELINE.json) bind exact baseline SHA, owners, reproduction, evidence hashes and remediation plans. Policy validates that accounting and rejects all exceptions because none is explicitly approved. It does not suppress any test or lower a threshold. Changes to baseline policy invalidate source identity.

Targeted actual local execution:39 PASS,0 SKIP in [final-targeted-green.json](evidence/ci-recovery-2026-10-25/final-targeted-green.json). The aggregate functional RED had4 PASS/1 FAIL; baseline identity RED had4 PASS/1 FAIL. The initial missing-module baseline RED is separately retained and is not represented as a behavioral reproduction. Node controller20 fixture tests PASS; they are not live merge proof. Candidate full feature and independent CI results must be read from the recovery handoff before claiming completion.

## Containment and remaining blockers

Repository auto-merge is disabled by verified API readback. PR8 still retained a queued main auto-merge after that setting changed; its native auto-merge request was separately disabled and verified, without changing its source/base/open state. Existing dev/qa/main protection rules were read and preserved. Actual main requires `Release gate`, strict checks/admin enforcement/no force/deletion; its current reviewer count is0, which differs from older handoffs. No reviewer requirement was silently claimed or changed.

Feature/dev auto-merge remains quarantined. No qa/main merge, release or tag occurred. AI Repair Supervisor integration, successful real auto-merge, and a green end-to-end promotion exercise remain NOT RUN/BLOCKED. Next priority: complete auditable live producers/adapters and missing integrations; add meaningful whole-source tests; integrate preserved app work; rerun frozen candidate mandatory gates. Do not substitute a coverage waiver for these tasks.
