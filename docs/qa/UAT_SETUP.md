# Reproduce the local browser environment

Use the governance worktree recorded in agent/STATE.md. Install application/CI dependencies from requirements-ci.lock, frontend dependencies with npm ci, and build the frontend. No project data or credentials should be copied into test state.

PowerShell from repository root, with Python3.12 available:

```powershell
py -3.12 -m venv output/playwright/browser-uat-env
& output/playwright/browser-uat-env/Scripts/python.exe -m pip install --require-hashes -r requirements-uat.lock
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'output/playwright/browser-binaries'
Push-Location frontend
npm ci
npx --no-install playwright install chromium
npm run build
Pop-Location
python scripts/verify.py --profile feature --base origin/dev
```

Linux uses python3.12 -m venv and output/playwright/browser-uat-env/bin/python instead. CI installs Chromium with --with-deps on Linux. Browser Use is optional for routine regression; Playwright remains authoritative without an LLM.

Before exploration read agent/UAT.md and the persistent repair ledger. The current TASK-UAT-LOCAL-ADAPTER is already exhausted; the following is an interface example for a genuinely new, independently authorized feature task, not permission to restart the exhausted group:

```powershell
python scripts/verify.py --profile uat --uat-journey settings-language --repair-key TASK-<new-feature-id>
```

LM Studio must already expose the explicitly authorized spark-x2.5-4b model at127.0.0.1:1234/v1. There is no paid/cloud or alternative-model fallback. The adapter owns the test server, browser profile, data/config/cache and local CDP lease. It excludes personal browser/account state and inherited provider/GitHub keys. Unsupported journeys block before inference. The next valid exploration requires the stable task's budget to permit it; never choose a new key to evade the prior group limit.

Reports are under output/playwright/verification/<run>. Preserve the full raw evidence locally. Commit only reviewed, secret-free artifacts. A model's own success text or an inventory entry never qualifies acceptance; raw browser confirmation and required independent review must agree. See UAT_ACCEPTANCE_REPORT.md and the CI user guide for current blockers.

Keep PLAYWRIGHT_BROWSERS_PATH identical when installing and running browsers. On Linux, export PLAYWRIGHT_BROWSERS_PATH="$PWD/output/playwright/browser-binaries" before install/verification. Only executable binaries are shared: profiles and app/config caches remain lease-specific. This prevents XDG_CACHE_HOME isolation from redirecting Playwright away from its installed Chromium. See the [official binary management documentation](https://playwright.dev/docs/browsers#managing-browser-binaries).
