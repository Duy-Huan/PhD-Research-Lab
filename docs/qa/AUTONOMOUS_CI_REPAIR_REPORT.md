# Actual CI repair acceptance - 2026-10-25

**PARTIAL / NO-GO for merge or release.** A real CLI repair, local verification, commit/push and exact-head CI rerun occurred. Successful all-required-checks/native merge acceptance has not occurred.

| Stage | Actual evidence | Result |
| --- | --- | --- |
| Controlled PR | PR10, feature/ci-repair-controlled-exercise, initialfc21484 then app-fixture repairceff505 | Real non-draft dev PR; immutable arithmetic tests deliberately3FAIL |
| GitHub failure and blocking | run40154407248 atceff505; completed backend job assertion artifacts; PR API mergeable_state blocked | Actual failed mandatory jobs observed while matrix still running; overall run later CANCELLED by subsequent push, never reported completedFAIL/PASS |
| Detection/assignment | Owner policy in shared Git metadata; exactPR/branch/SHA/worktree; onlyqa/fixtures/ci_repair/arithmetic.py writable | Real local supervisor; diagnostics from failed jobs/artifacts; matrix failure fingerprints; no external PR execution |
| Coding agent | Codex6.1-sol/high, workspace sandbox, thread01a170e7-cb1c-7280-b971-d616b2c24a06 | Actual CLI turn completed; reproduced3failures and removed erroneous+1; no test/assertion edits |
| Scope interruption | Missing Windows standard env generated literal%SystemDrive% cache; guard blocked | Supervising AI archived its generated cache and adopted reviewed existing patch, counter remained1. This is not human review or a fully unattended first trial |
| Local checks | Canonical targeted3PASS; complete feature report preserved | Actual evaluated tests;8optional/unavailable skips remain unqualified for strict gates |
| Correction push |87703f74963ff40527edde35f19567219eec22c2 | Supervisor committed/pushed one fixture file to same branch; immutable test SHA2567aea8260c7e96a67e8a779931a1f5447e90a82b19e5604426762e3d962fb8ade unchanged |
| Fresh CI | run40155743019, exacthead87703f7 | Real fresh run completedFAIL; fixture failures repaired, broader strict coverage/live/AI-UAT and old policy-install defect remain blocking |
| Native auto-merge | PR remains unmerged/blocked; repository auto-merge quarantined | NOT RUN / NOT ELIGIBLE; no final merge SHA; noqa/main history modified |

Links: [controlledPR](https://github.com/Duy-Huan/PhD-Research-Lab/pull/10), [observed old run](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40154407248), [fresh exact-head run](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40155743019).

Reviewed raw reports, invocation/extracted actual CLI events, state, job metadata, archive hashes and immutable test results are in evidence/ci-supervisor-6.5.5. Full failed-job/artifact archives and original CLI stream remain in shared.git/ci-repair/pr-10; no credential is published. CLI input359315 tokens includes306304cached; output1488. No savings percentage/cost is inferred.

The canonical supervisor is development infrastructure, not Research Agent Harness. It reserves max3invocations before execution; missing/corrupt state cannot reset quota. It preserves user/unknown edits, forbids tests/gates/policy changes by the assigned agent, uses native/pinned npm CLI entrypoints without shell interpolation, verifies exact-head mandatory jobs and only requests GitHub-native dev auto-merge. Completed merge must be independently observed and included in dev. Claude/Antigravity repair execution is NOT RUN; unit argv guards are not live qualification.

Separate confirmed new pipeline defect: real policy job usedunittest discovery before hash-locked dependency installation, importing unrelated package initializers and failing missinghttpx. Candidate6.5.5 installs first and invokes precise canonical worker modules. Same final workflow tests:3FAIL/1PASS against previous YAML, then43targeted regression checks PASS; Nodepolicy42PASS separately. Candidate CI is pull_request-only; main qualified CD is separate, source/tree/tag/asset-bound. No unqualified release/tag is created.

Legacy GitHub registrations394955699 and395288466 were disabled with verified readback, while QualityGates395459438 remains active. Old run history is retained. Candidate history removes legacyfiles; protectedmain still contains its old file until a qualified promotion. Source main/dev/qa remains6725975 and preview is explicitly untrusted.

Remaining blockers:100% production coverage unmet; mandatory live/SDK cases skipped/unavailable; current-source all-provider/research qualification absent; AI-UAT adapter budget exhausted3 and other adapters incomplete; trusted live producer unavailable. These do not become exceptions or fakePASS. Fresh candidate independent CI, same-suite main comparison, protected dev/qa qualification and eventual qa?main PR remain conditional on actual results. No approval or zero-bug claim is fabricated.
