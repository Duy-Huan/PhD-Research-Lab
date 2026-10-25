# CI/CD architecture

The portable entrypoint is `python scripts/verify.py`. Development orchestration lives in `devtools/verification/`; application research execution stays in backend research/runtime modules. They reuse existing unittest, Playwright and evidence producers without importing the development orchestrator into the application.

`quality.yml` replaces two overlapping legacy workflows. It runs on every PR into dev/qa/main and protected-branch pushes, without path filters that could leave required checks pending. Concurrency cancels superseded runs; cancelled/missing dependencies never satisfy aggregate gates.

| Job | Evidence / dependency |
|---|---|
| policy | Reviewed feature contracts, executable traceability, RED/GREEN artifacts, protected resources, pinned actionlint and auto-merge policy tests |
| backend | Windows/Linux × Python 3.11/3.12, hash-locked install, pip check, compileall, full offline regression and strict 100% line/branch coverage |
| frontend | Node 24/npm ci, dependency audit, TypeScript, whole-source 100% coverage across lines/branches/functions/statements, build |
| security | Hash-locked Python dependency audit and high-confidence/high-severity Bandit checks |
| browser | Fresh Chromium with Linux browser dependencies; actual disposable app smoke/fault/isolation tests; no LLM needed |
| Development gate | All required development dependencies must report success |
| live qualification / QA gate | Exact-source actual provider/browser/CLI/scientific evidence; absence blocks promotion |
| production / Release gate | Successful QA plus human environment approval and protected main PR review |

AI exploration is risk-aware and remains outside routine paid/cloud execution. Hosted runners do not carry local LM Studio or CLI subscription logins. Public forks must never get self-hosted runners, local profiles or production credentials. A trusted live path needs explicit provisioning and matching-source evidence; its implementation and execution status are tracked in the UAT acceptance report.

All action references are pinned to commit SHAs verified against official repositories. Tokens default to contents:read or no permissions; checkout does not persist credentials. The privileged auto-merge workflow checks out protected main only, reads API metadata/checks and never executes PR code or artifacts. It can request only a normal native squash merge into dev with expected head OID; GitHub protection remains authoritative.

CI uses `requirements-ci.lock` with hashes and `frontend/package-lock.json`. Optional UAT uses its own lock and Python 3.12 environment. Dependency caches accelerate installation; no cached passing test result substitutes for a new required gate. No app/container image from a developer machine is assumed available on GitHub. Offline jobs require no provider Docker image; isolated live CLI tests need their own pinned images and authenticated trusted runner.

The branch-protection read endpoint requires Administration:read, which the normal workflow GITHUB_TOKEN cannot request. The protected-main handler accepts an optional separate `AUTOMERGE_POLICY_READ_TOKEN` with only the repository permission needed to read policy; it never uses that credential for merging. No such secret was present in the real audit, and none has been copied from the developer machine. Missing/unreadable policy returns BLOCKED with no write. This is an additional activation prerequisite, not permission to weaken the protection check. See [official GitHub endpoint permissions](https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection).
