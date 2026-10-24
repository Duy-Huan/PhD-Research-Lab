# CI and browser dependency audit

Task date: 2026-10-25 (Asia/Saigon). These are observed prerequisites and results, not a guarantee every future hosted runner succeeds.

| Surface | Observed / installed | Limits |
|---|---|---|
| Python | Hash-locked clean installs on Windows Python3.11.17 and3.12.15; pip check / compile tests performed | Actual new Linux/Windows Actions run must be inspected separately |
| CI dependencies | requirements-ci.lock, pip --require-hashes; actual pip-audit over70 resolved dependencies found no known vulnerabilities | Local3.11 tomli C wheel was blocked by Windows AppControl; audit succeeded under existing3.14. Do not disable OS protection |
| Optuna / SQLAlchemy | SQLAlchemy2.1.6 C wheel hit local AppControl; official same-version pure-Python source build made the exact Optuna test pass | A focused pass does not recertify the full suite; no assumption hosted Windows has the same policy |
| Frontend | npm ci completed, zero audit findings at install; Node24 selected in CI; TypeScript/build and174 tests executed | Production coverage is below100% and strict gate fails |
| Browser | Playwright Chromium real headless Windows sessions; CI installs Chromium with Linux OS dependencies | Firefox/WebKit/device acceptance NOT RUN |
| Browser Use | Separate optional Python3.12 environment; browser-use0.13.11 locked; official APIs inspected and actual Spark calls attempted | Current3-cycle exploration budget exhausted; no completed AI-UAT acceptance |
| Workflows | Official Actions pinned to verified40-character SHAs; pinned actionlint passes | YAML validation is not evidence jobs passed on GitHub |
| Containers | Offline gates need no provider Docker image | Hosted runners do not inherit local CLI images, user subscriptions or LM Studio; contained CLI/live producer still needs provisioning |
| GitHub secrets/runners | Real API audit found zero Actions secrets and zero self-hosted runners | No separate Administration:read policy credential exists for the auto-merge protection audit; no copying local credentials into Actions |
| Optional live cases | ClearML server/SDK, OpenScience SDK, native Codex, local load/unload and privileged Windows symlinks are unqualified in the isolated offline matrix | Required skipped qualification is not PASS; no hidden opt-in or unsupported paid-provider fallback |

The new workflow's default token is restricted. The optional read-only AUTOMERGE_POLICY_READ_TOKEN is only for independent policy inspection. Write operations continue through the normal protected native merge path; no admin bypass. Actual human release approval and default-branch activation remain prerequisites.

Evidence files under docs/qa/evidence use a local .gitattributes rule disabling text conversion, so raw SHA256 attestations survive Windows/Linux checkout. Source identity separately normalizes declared text inputs to LF. Artifact integrity always compares exact saved bytes.

Actual GitHub run40136777730 on947d993: contract policy and dependency/security jobs passed. Browser dependencies installed, but Linux browser startup failed because isolated XDG_CACHE_HOME redirected binary lookup to an empty lease cache. quality.yml now sets an explicit workspace PLAYWRIGHT_BROWSERS_PATH for install and runtime. This is a configuration correction; current-source validation and a new GitHub run are required before claiming the browser job passed. Required AI-UAT correctly blocked on absent qualified evidence.
