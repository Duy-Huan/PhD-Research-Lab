# CI/CD condition review — 2026-10-27

Status: corrected source passed complete local verification on source fd1e9964dd4fce07bd20477dcd968d0a82a68a7b56c2f2c920f136b4b6d7e6c5. Actual protected promotion of the corrected source is not yet verified. Candidate remains unreleased6.5.12; native core6.6.xx is the next campaign.

## Observed failure

Both exact-head Quality Gates runs on5c71068e88a98249d5c9cb142519a24112415d5e succeeded: [dev40381520620](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40381520620) and [PR40381529763](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40381529763). All eight actual backend artifacts contain1022/1022PASS, zero failures/errors/skips. All three cleanup/latency target cases PASS in every artifact. These are8176case executions of1022unique cases, not8176distinct behaviors or scientific tests. Full artifacts and hashes are retained under local native-clean-state/successful-backend-artifacts/; the measured summary is successful-backend-summary.json.

[PR14](https://github.com/Duy-Huan/PhD-Research-Lab/pull/14) was CLEAN, open, unmerged and qualified. The supervisor's enablePullRequestAutoMerge mutation returned the actual UNPROCESSABLE error: `Pull request Pull request is in clean status`. The exact response is retained in docs/qa/evidence/native-clean-state-6.5.12/actual-github-rejection.json. Old red runs remain historical failures; no test was rerun unchanged to erase them.

`automerge.cjs::assess` requires CLEAN, while `promotion.py::ensure_native` and the optional hosted `automerge.cjs::run` previously called an API that rejects CLEAN. The old unit oracle merely asserted that API was called and did not model its real rejection. [Official GitHub CLI source](https://github.com/cli/cli/blob/trunk/pkg/cmd/pr/merge/merge.go#L546) also distinguishes immediately mergeable PRs from queued auto-merge.

## Preserved conditions

| Boundary | Required condition and implementation |
|---|---|
| Local publication | Existingdev only, clean worktree, authorized origin, stable source-bound complete pr/all receipt; installed development_guard/branch_policy hooks |
| Independent CI | Exact latest matching-head PR Quality Gates workflow/run/repository, not an older successful or unrelated skipped check suite; promotion.execution/latest_run and automerge.qualifiedErrors |
| Mandatory software | .github/required-ci-jobs.json: policy; four Linux/Windows Python3.11/3.12 backend jobs; frontend types/tests/build; dependency/security; real offline browser; Development gate; QA gate |
| Aggregation | quality.yml Development gate needs all software jobs; QA gate needs Development gate, with failures/skips/missing jobs rejected |
| Target protection | Strict QA gate from GitHub Actions app15368; enforced for admins; force-push/delete disabled; no protection changed by this correction |
| PR identity | Same repository/owner, forwarddev->qa or explicitly authorizedqa->main, open/non-draft, valid contract, no blocking review, source contains current target |
| Final mutation | Fresh same head/target SHA/ref and ready CLEAN state; normal native mergePullRequest with expectedHeadOid; no admin/force option or alternate bypass |
| Completion | Subsequent actual merged flag/SHA, target containment, identical tested/merged tree and same-tree dev fast-forward; a requested merge is not success |
| CD | Main-push release.yml independently validates current protected main, actualqa->main PR, exact successful QA PR run/check suite/tested tree; builds source/web archives, validates checksums and publishes matching tag |

Readback confirms repo merge commits enabled, linear-history requirement disabled, required review count0, and the strict/admin-enforced QA gates remain enabled on both targets. No new manual release approval is needed under the existing owner policy. Live-provider/research/AI-UAT qualification stays separately NOT_RUN/BLOCKED until actually executed; it is not software/scientific PASS by inference. Coverage remains measured/informational, not100% achieved.

## Correction and evidence

The existing local and optional hosted controllers now request the normal protected native merge for a fully qualified CLEAN PR, locking expectedHeadOid. Fresh target changes, draft/closed or no-longer-ready state block before mutation. Every existing failed/skipped-job, wrong suite/app/SHA, protection, review, fork and branch-order assertion remains.

Actual TDD: the7case Python policy suite produced RED1ERROR/6PASS from a controlled reproduction of the retained real GitHub rejection, then GREEN7PASS. Controlled Node policy/release tests:49/49PASS, zero skips. These mocked API fixtures prove code policy behavior; they do not prove an actual GitHub merge. The full local and independent CI outcomes for the corrected source must be recorded before publication/completion.

Active guides were reconciled with the owner policy: removed obsolete live-as-software-prerequisite and manual-main wording; replaced the incompatible auto-merge-API-only rule with normal head-locked protected native merge. No software test/gate, source proof, protection, review, repair history or UAT budget was relaxed. Pinned gh-fix-ci/github-actions-hardening skills in skills/SOURCES.json were reused after GitHub search/review; no duplicate framework or new credential was added.

Original three failed CI observations and the owner-granted additional cycle remain in agent/repair-ledgers/ledger.json. The5c software CI success is recorded separately from the native promotion rejection. The latest owner instruction explicitly requests checking/fixing CI/CD conditions; no counter reset or native AI repair invocation occurred.

## Current-source local qualification

Quick1239/1239, feature1274/1274 and pr/all1274/1274 PASS, source stable, zero FAIL/ERROR/SKIP/NOT_RUN/BLOCKED. Controlled Node49/49PASS. Backend1022, frontend217, real-local boundary6,2D28 and WebGL3D1. Python23693/26679lines and7118/8958branches, combined86.46%; frontend2523/3818lines and2754/4218branches. Coverage100% is not achieved. Two live-provider cases remain NOT_RUN. Exact fresh GitHub CI, actual protected PR merges/main containment and matching main CD are required next; the existing5c CI success is not reused for changed code.


## CD provenance consistency correction6.5.13

Actual protected PR14/15 merged and6.5.12 tag targets main73e35da. Initial CD40429712059 rejected PR provenance8seconds after merge; later API returns matching PR15 and same-source recovery40430420830 passed and published. Delayed association indexing is an inference: failed-time response body was not logged. The new bounded qualifier permits6reads with1/2/4/8/16-second waits, rechecks current protected main each attempt and preserves every QA/source/tree condition. Permanent absence or changed/unprotected main fails closed. Controlled offline18release tests plus other policy suites total52PASS; not live/scientific proof. Exactly one extra owner-authorized CD correction candidate, all original ledgers retained. New independent CI and actual automatic release are still required.
