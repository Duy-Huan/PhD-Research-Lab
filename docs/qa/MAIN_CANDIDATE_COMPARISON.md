# Measured main / candidate6.5.6 comparison

Decision: **NO-GO for QA promotion or release.** This comparison verifies a bounded software scope; it does not establish an entirely bug-free application.

Main: `6725975261fe6a4d8a5cb3e10208e31c3e24f0e2` (untrusted6.3.0 preview). Candidate application: `97845ee2d79cba43ff5a483a3462a64eed10bc0d` (6.5.6). Later classification/report updates preserve this candidate's application code. The frozen comparison uses198 identical test-source files, the same harness/dependency/build instrumentation and fixed evaluation policy. It runs serially on one host with Python3.12.15, Python3.11.17 compatibility probe, Node24.22.0, npm11.19.1 and the same recorded Chromium revision/binary. [Exact inputs, source hashes and overlays](evidence/comparison-6.5.6/preparation.json), [environment](evidence/comparison-6.5.6/environment.json), [commands and exit codes](evidence/comparison-6.5.6/execution.json).

Production inputs were unchanged before/after overlay and execution. Main is evaluated under the current common test toolchain; its original frontend package metadata is retained in preparation.json. This is not a pristine historical dependency installation. No passing cache substitutes execution. Tests requiring missing new APIs/modules produce ERROR/NOT_RUN; no test denominator is silently narrowed.

| Measurement | Main | Candidate6.5.6 |
|---|---|---|
| Confirmed unresolved P0/P1/P2 groups in this bounded inventory | 0 / 7 / 3 | 0 / 0 / 1 |
| Fixed critical software qualification denominator | 0/10 | 10/10 |
| Backend covered lines | 21808/24306 | 23833/26528 |
| Backend covered branches | 6649/8132 | 7120/8808 |
| Backend combined coverage | 87.73% | 87.6% |
| Frontend coverage | UNAVAILABLE: test collection errors; no numeric comparison | lines2445/3820=64%; branches2611/4125=63.29% |
| Browser journeys, real local app | 18PASS /9FAIL | 27PASS /0FAIL |
| AI-UAT | BLOCKED, exhausted unchanged3-cycle budget | BLOCKED, exhausted unchanged3-cycle budget |

Zero findings in a partial inventory does not establish zero P0/P1 defects. [Machine-readable comparison](evidence/comparison-6.5.6/comparison.json) and [defect registry](MAIN_CANDIDATE_DEFECTS.json) disclose exact identities and scope. Seven critical groups are software fixtures; three groups use real local browser/application execution. The10/10 result is not all-provider, scientific, accessibility-certification or entire-QA acceptance. Main's0/10 means none of these current-requirement groups qualified; some could not evaluate the older interface.

| Fixed critical group | Main | Candidate | Execution mode |
|---|---|---|---|
| context-pdf-completeness | FAIL | PASS | FIXTURED_SOFTWARE_REGRESSION |
| explicit-chat-history-budget | FAIL | PASS | FIXTURED_SOFTWARE_REGRESSION |
| remote-record-integrity | FAIL | PASS | FIXTURED_SOFTWARE_REGRESSION |
| cloud-local-resource-separation | BLOCKED | PASS | FIXTURED_SOFTWARE_REGRESSION |
| provider-isolation-fails-closed | FAIL | PASS | FIXTURED_SOFTWARE_REGRESSION |
| research-evidence-never-fabricated | FAIL | PASS | FIXTURED_SOFTWARE_REGRESSION |
| cli-settings-locale-persistence | FAIL | PASS | FIXTURED_SOFTWARE_REGRESSION |
| mobile-settings-actionability | FAIL | PASS | REAL_LOCAL_BROWSER |
| model-rules-and-language-persist | FAIL | PASS | REAL_LOCAL_BROWSER |
| actual-3d-webgl-and-navigation | FAIL | PASS | REAL_LOCAL_BROWSER |

## Defects, regressions and unexecuted work

The bounded confirmed main findings cover supported Python3.11 syntax, PDF context loss, fabricated replay metrics, invalid checksum acceptance, remote compute NameError, invented reference metadata, premature run completion, CLI settings/locale and accessibility naming. The candidate passes their unchanged named oracles. An additional P2, BUG-3D-LOCALE-001, remains OPEN: English3D retains Vietnamese HPC labels and agent descriptions. Identical source-review criteria confirm the hard-coded defect in both revisions; an actual candidate screenshot corroborates it. Its main runtime reproduction is NOT_RUN and its dedicated behavioral regression is NOT_IMPLEMENTED. This additional finding does not alter the10 declared harness groups or pretend those groups cover localization exhaustively. Newly confirmed product regressions in executed common cases: none observed; this is not an exhaustive absence claim. A Linux packaging fixture defect and CI install-order defect were repaired separately with real RED/GREEN/hosted evidence.

Remote compute NameError is reclassified as pre-existing using the actual main reproduction. A missing sidebar selector is not evidence of the later overlay-interception bug. Loader errors, unsupported newer features, unexecuted historical external tests, eight mandatory skips, all-provider/research/experiment-to-paper validation and the unavailable trusted live producer remain separate. Raw PASS counts are diagnostics, not a ranking of differently implemented source.

Both subjects retain mandatory typecheck/build results. Both also execute identical Vite-only diagnostic transpilation plus postbuild, then the browser tests run against fresh assets. A successful diagnostic transpilation never repairs a failed mandatory TypeScript/build gate. Actual WebGL2 context/camera pixel variation, light-button state and navigation are asserted; hardware GPU qualification and independent light-only pixel effects are not established. Visual evidence is same-agent reviewed, without controlled human-approved redesign baselines.

The comparison policy bundle was frozen at97845ee; subsequent evidence-backed issue reclassification changes accounting, not tests, application code, thresholds or the recorded inputs. The final current-source feature report separately covers that updated accounting.

## Additional local model observation

The explicit local `spark-x2.5-4b` endpoint answered three bounded128-token probes with exactREADY (1.890s/0.594s/0.641s). The original32-token probe FAIL is retained: all tokens were consumed by reasoning and no answer completed. Allocation was corrected; the oracle stayed unchanged. [Original](evidence/comparison-6.5.6/spark-probe-32-failed.json), [three actual responses](evidence/comparison-6.5.6/spark-probe-128.json). These direct connection samples do not qualify application chat streaming, AI-UAT, long-term stability, other providers or scientific workflows. No exhausted UAT task was restarted.

## Promotion

dev/qa/main remain at6725975. PR11 is the normal integration path; superseded PR7/9 and duplicate configuration PR8 are closed with branches/worktrees preserved. Two legacy workflow registrations are disabled; protected-main files and CD activation await qualified adoption. Main requires strictQA gate; other protection settings remain unchanged. Native dev auto-merge stays quarantined. No dev-to-qa merge or qa-to-main PR is created while mandatory coverage/live/UAT checks fail or are unavailable.
