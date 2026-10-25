# CI recovery root causes and current6.5.6 decision

**NO-GO for protected promotion.** Deterministic CI is operational on integration PR11; current strict coverage/live/UAT qualification is incomplete. No failure is waived.

Actual pre-repair hosted run [40171931531](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40171931531), headb1dcf4b33179317d735238662d71c366c30b3513: policy, security/dependencies and real browserPASS. Backend matrices/frontend/UAT/Development gateFAIL. [Downloaded diagnostics](evidence/ci-stabilization-6.5.6/pr11-b1-diagnostics.json) distinguish assertions, skips, coverage and unavailable evidence. Post6.5.6 independent CI must be inspected against the exact latest pushed head.

| Root group | Classification | Evidence and disposition |
|---|---|---|
| Linux release packaging fixture | Introduced test specification defect | Index-only executable bit left the Linux worktree dirty; real packaging correctly rejected it. Original6tests:5PASS/1ERROR. Real chmod plus index fixes fixture, preserving all assertions and dirty-source rejection. POSIX6PASS/Windows6PASS; raw logs retained. |
| Windows3.11 missing run metrics | Existing application race | Waiter published done before collecting/persisting metrics. Deterministic delayed-collector test RED fails, then affected17PASS. Final status now follows persisted metadata; failed-run postprocessing still receives final status. Same reproducer FAIL on old main, PASS on candidate. |
| Missing remote context json import | Existing application defect, reclassified | Same unchanged case raises NameError on original main. Earlier provisional newly-introduced label is withdrawn; first known observed main6725975 is not an invented bisection result. Current candidate passes. |
| Policy dependency order | Introduced CI infrastructure defect, fixed | Earlier actual40154407248 discovery ran before installing httpx. New canonical targeted worker follows hash-locked installation; hosted40171931531 policyPASS confirms repair. |
| Backend coverage/completeness | Qualification gap | Same-suite candidate23833/26528lines,7120/8808branches,87.60% combined;8local mandatorySKIP. No threshold/exclusion change. |
| Frontend coverage | Qualification gap |174assertionsPASS, types/buildPASS; lines2445/3820=64%,branches2611/4125=63.29%,functions733/1467=49.96%,statements2574/4117=62.52%. Gate correctlyFAIL. |
| Verified AI-UAT | Unavailable qualification | Required current-source trusted exploration evidence missing. Canonical uat on both subjects returnsBLOCKED; TASK-UAT-LOCAL-ADAPTER remains exhausted3. Other personas/adapters and trusted research producer are incomplete. |
|3D locale consistency | Existing OPEN P2 | Same hard-coded Vietnamese system strings exist on main and candidate. Actual candidate English screenshot reproduces mixed language. Dedicated regression is NOT_IMPLEMENTED.27browser PASS does not erase this defect. |
| Native repair exercise | Real assisted partial acceptance | PR10 actually invokes Codex, fixes immutable-oracle fixture, targeted/feature verifies, supervisor pushes87703f7, new run40155743019 starts and completesFAIL. Initial Windows environment recovery needed operator help. Required-PASS/native dev merge are unachieved; no mergeSHA. |

The original old runs40148986328/40150782744 and full logs remain preserved. Duplicate matrix symptoms are grouped; no passing successful-job logs are supplied as repair authority. Current issue accounting has exceptions:[] and never filters tests or transforms unavailable results intoPASS.

## Actual GitHub cleanup

Two duplicate legacy workflow registrations394955699/395288466 are disabled_manually with readback; Quality Gates remains active and system Dependency Graph is retained. Old run/history evidence is preserved. Legacy files are removed in candidate history; protected main adoption/CD activation waits for qualified promotion.

PR7/9 closed only after their exact heads were proved ancestors of PR11. PR8 closed because its only weekly-root-pip configuration intent is fully represented by the new Dependabot config. Every branch/worktree/history remains. Queued main auto-merge was separately cancelled. Repository auto-merge stays quarantined.

Main now requires strict QA gate before merge (Actionsapp15368), with admin enforcement/no-force/no-delete/conversation/review settings unchanged. Release gate belongs to separate main-push CD, avoiding a circular pre-merge release requirement. [Before/after receipt](evidence/ci-stabilization-6.5.6/github-cleanup.json), [actual remote readback](evidence/comparison-6.5.6/github-state-before-publication.json).

The browser-control connection was unavailable; these are authenticated API operations/readbacks, not a claim of browser UI control. main/dev/qa history remains6725975. No protected merge, tag, release, deployment or successful auto-merge has occurred.

Hosted dependency/Chromium installation has executed successfully for passing policy/security/browser jobs. Actions secrets and self-hosted runner counts are both0. A hosted runner cannot use the owner's loopback LM Studio merely because that endpoint responds on the PC. Direct local Spark probes3/3 succeed with128tokens, retaining the original32-token reasoning-only FAIL; they do not provide trusted research/AI-UAT provenance or other-provider qualification.

[Same-suite comparison](MAIN_CANDIDATE_COMPARISON.md), [defect registry](MAIN_CANDIDATE_DEFECTS.json), [coverage priorities](COVERAGE_GAPS_6.5.6.json) and [readiness](RELEASE_READINESS.md) are the current handoff. Historical old reviewer/auto-merge/pending-application statements in earlier commits are superseded by these measured facts.
