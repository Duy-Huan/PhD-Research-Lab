OWNER POLICY2026-10-26 (latest explicit chat answer): for ALL dev -> qa -> main stages, every mandatory SOFTWARE REGRESSION must execute/PASS100%. Coverage is informational. Live-provider, research and AI-UAT qualification run separately by explicit operator invocation and are NOT commit/merge prerequisites. Their FAIL/BLOCKED/NOT_RUN outcomes remain visible and must never be called live/scientific PASS. Preserve protected native forward merges, trust, security/data/API regressions and all UAT budgets. This supersedes every older instruction requiring live/AI-UAT evidence for QA/main.

# Operator guide: single dev -> protected qa -> protected main

All AI source edits, repairs, test additions and commits use the existing dev branch only. Do not create any other branch. Preserve every worktree, dirty user change, research dataset and file in skills/ or agent/. One writer at a time. Older guides are retained in agent/history/; this owner policy supersedes historical feature branches and manual-main requirements.

## Install and develop

Use Python3.11/3.12 and Node24. Read AGENTS.md, AGENT.md, STATE.md, PLAN.md and ZERO_FAKE_TESTING_POLICY.md. Review/pin suitable GitHub skills before a new feature, then write a reviewed Feature Quality Contract and meaningful behavioral tests.

```powershell
git status --short
git branch --show-current
python -m pip install --require-hashes -r requirements-ci.lock
$env:NO_PROXY = 'localhost,127.0.0.1,::1'
python scripts/development_guard.py install
Push-Location frontend
npm ci
npx --no-install playwright install chromium
Pop-Location
python scripts/verify.py --profile quick
```

The reference-transaction hook denies local head creation/update except dev; pre-commit requires dev. These are installed-client controls, not an OS security boundary. Never disable hooks or use --no-verify. Test fixtures own disposable PHDLAB_DATA_DIR; native provider launches use installed CLI apps with authorized project-contained roots.

## Verify, commit and push dev

Freeze source and execute the complete software gate. Dynamic packaged-Python/TypeScript/Playwright discovery incorporates new tests; an empty packaged Python test module fails. Browser execution uses separate2D then3D invocations, not filename-order assumptions.

```powershell
python scripts/verify.py --profile pr --component all --base origin/dev --out output/playwright/<fresh-run>
# Only after actual PASS with stable source:
Copy-Item output/playwright/<fresh-run>/report.json docs/qa/evidence/local-verification/report.json
python scripts/check_local_verification.py
git add <reviewed-task-files>
git commit -m "<reviewed scope>"
git push origin dev
```

Create the local-verification directory first if absent. Preserve raw execution logs, case outcomes, source hash and real RED/GREEN records. Pre-push requires a clean dev HEAD, authorized origin and current-source complete local report; GitHub independently repeats regression on the new SHA. Any source edit invalidates prior verification. Coverage is informational: desired production line/branch100%, >95% was only an estimate. Report real numerators/denominators and all uncovered paths. Every selected mandatory software regression must execute/PASS100%, zero FAIL/ERROR/SKIP/BLOCKED/NOT_RUN. Explicit live-provider IDs remain a separate NOT_RUN inventory until actually invoked; no live result is required by commit/merge CI at any stage.

## Genuine live and AI acceptance

Actual provider inference, research experiment/report/paper lineage and AI-UAT plus independent review are separate operator qualification; they do not block software promotion. Real deterministic CLI/2D/3D regression remains mandatory in software CI. Missing infrastructure/credentials/unsupported journeys are BLOCKED, not waiver/PASS. Offline SDK/HTTP fixtures are software tests, never scientific evidence.

TASK-UAT-LOCAL-ADAPTER retains its original three failed attempts. Owner chat on2026-10-25 separately permits exactly ONE Spark X2.5 4B local attempt, at most600seconds/six steps. scripts/verify.py --profile uat --uat-journey settings-language --uat-model spark-x2.5-4b --uat-steps 6 --uat-deadline 600 --uat-owner-authorization <external-grant> consumes a source/HEAD-bound one-use grant in shared .git/uat-authorizations/. See UAT.md. A failed extra run stops the loop; no reset, rename or extra fallback. Package only actual passing current-source UAT; review stays PENDING until genuinely reviewed.

For real evidence transport, build the validated exact-head bundle outside source, including genuine required UAT under uat/. Run python scripts/upload_live_evidence.py --help for required inputs. Owner-only dispatch publishes existing validated bytes; it neither executes models nor makes a scientific claim. The optional research-live publisher is workflow_dispatch-only; no registration push run is emitted. A new pending/failed dispatch blocks reuse of an older successful dispatch.

## Native automatic promotion

Latest owner explicitly authorizes both dev -> qa and qa -> main automatically after ALL mandatory SOFTWARE gates pass. Local controller reuses existing Quality Gates and native GitHub auto-merge, never direct/admin merge. It pins trusted code outside PR code, checks current local source proof, exact PR/head/run/check-suite, all mandatory job success, strict target protection, reviews and tested/merged tree equality. A merged flag or skipped required context alone never qualifies QA.

```powershell
python scripts/promote.py register --authorize-native-main-merge --enable-repo-auto-merge
python scripts/promote.py once
python scripts/promote.py watch --apply
# In another terminal:
python scripts/promote.py status
python scripts/promote.py stop
python scripts/promote.py resume
```

Register only clean fully verified dev. Observation without --apply does not mutate GitHub. Policy/state/locks/STOP persist under shared .git/auto-promotion/ and survive sessions. Changed trusted code requires owner-authorized re-registration; history/counters remain. The watcher creates only forward PRs, requests native auto-merge only after qualification, records actual merged SHA/containment, then fast-forwards/pushes dev only across the observed identical-source merge. Different source or dirty work blocks synchronization. Never edit qa/main or force-push. Main-push release.yml separately rechecks exact genuine QA PR run and tested tree, builds, hashes and publishes a GitHub Release. PC installation/data backup/rollback remains controlled by the owner.

The optional hosted automerge controller stays off unless explicitly configured and adopted on protected main. Local-first promotion needs no hosted Administration secret. AI repair is separate: see CI_REPAIR_SUPERVISOR.md. Native merge success, AI invocation and a published release require separate real evidence; configuration/unit fixtures do not prove them.

## Owner completion rule (2026-10-26)

Owner design constraints (2026-10-27): read the complete [Native AI Research Environment checklist](NATIVE_AI_RESEARCH_ENVIRONMENT.md) before core, prompt, orchestration, context, memory, tool, provider or runtime design/changes. Maintain item-level status, source and actual evidence, including the seven required reports. CI/CD is first; the native core campaign targets 6.6.xx. Requirements or software PASS do not certify real scientific execution or L3/L4.

For every coding task, the AI agent must inspect the actual repository on GitHub **in a browser**: the exact commit, relevant Actions run and forward promotion PRs. A CLI/API receipt supplements this browser inspection. Local PASS, a push, an open PR or an auto-merge request is not completion. Continue the authorized protected automatic `dev -> qa -> main` flow; verify both PRs are actually merged, record their URLs and merge SHAs, and prove the task commit is contained in current `main`. Where delivery is in scope, also verify the exact main release SHA. Never report the coding task complete before this evidence exists. If mandatory gates fail or a repair budget is exhausted, retain an explicit incomplete/blocker handoff with actual evidence; do not bypass protection or manufacture success. This rule does not turn software CI into live-provider or scientific L3/L4 qualification.
