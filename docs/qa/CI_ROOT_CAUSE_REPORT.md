# Actual GitHub CI recovery6.5.11

Candidate6.5.11 on existing `dev`, parent `3f60a77c54ada9f1197c901019a119ad5d4ddebf`, source `dd01c60ac488bd91da7dd0cfaf880893d88232e6c1444cebca1b8d265571886c`. Actual stable local complete software gate PASS. Fresh exact-head GitHub CI is still required; no future PASS is presumed.

Owner explicitly confirmed on2026-10-26: complete software regression is mandatory across dev -> qa -> main; live-provider/research/AI-UAT qualification runs separately, and coverage is informational. Optional qualification never becomes live/scientific PASS merely because software CI passes.

Original exact-head [Quality Gates run40331308169](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40331308169) on3f60a77 failed all four backend jobs; frontend, real browser, workflow policy and dependency/security jobs passed. Direct web inspection confirmed the failures. Browser raw logs require sign-in; the existing authenticated Git credential API supplied actual logs/artifacts without exposing credentials.

Confirmed root1: `psutil` was imported by the new real process-containment regression but was absent from requirements-dev/CI lock. The development interpreter already had it, masking the clean-runner failure. Added explicit psutil>=7.2.2 and regenerated the universal hash lock with --no-upgrade. No existing tests were removed or skipped.

Confirmed root2: orchestration fixtures used real Python protocol subprocesses but the model registry also consulted the physical Docker/vendor runtime. The development machine had the runtime; hosted runners did not. The test context now explicitly supplies simulated runtime readiness only while running that controlled peer. A new regression first failed with absent host runtime, then passed after the fixture correction; outside that fixture the production registry still refuses unavailable isolation. Production readiness and original assertions are unchanged. The same root accounts for five failures/errors across complete matrix reports.

Unresolved historical incident: Ubuntu/Python3.11 exited withSIGSEGV/-11 before a complete report. No native stack was captured in that old run. It did not reproduce in three local non-root Python3.11.17 Linux full executions; do not claim its original cause was proven fixed. PYTHONFAULTHANDLER1 is now enabled in CI so a recurrence records actual stacks. Two initial diagnostic environment failures (missing Chromium and a noexec tmpfs affecting Git hooks) were retained, then corrected in the disposable diagnostic setup. Production tests/hooks were not weakened. Final Linux preflight36/36PASS and full1017/1017PASS, no skip.

Policy change was explicitly authorized by the owner, independently of these backend repairs: mandatory Quality Gates retains complete backend/frontend/browser/static/security checks; QA aggregates Development gate; live/AI-UAT jobs are removed from that prerequisite graph and the evidence publisher is manual-dispatch only. Its evidence validators and UAT budgets remain intact. Policy RED2FAIL and GREEN37PASS are retained, along with current full local regression. Protected branch checks/admin enforcement are unchanged.

Current autonomous correction cycle1; no blind rerun of the unchanged old source, no status forgery, assertion weakening, coverage cutoff, force push, administrative bypass or paid AI call.
