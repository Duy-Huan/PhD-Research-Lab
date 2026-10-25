ACTIVE OWNER POLICY (2026-10-25): All source edits, repairs and testcase additions ONLY on the existing dev branch; creating any other development/backup branch is forbidden. Native automatic dev -> qa -> main is explicitly authorized ONLY after every mandatory local/GitHub/software/live/research/AI-UAT gate actually passes. Desired production line/branch coverage100%; >95% was an estimate, coverage stays informational/nonblocking. Every mandatory regression must execute/PASS100%. Original UAT three-failure ledger stays intact; exactly ONE separately authorized Spark X2.5 4B local attempt may run, maximum600seconds/six steps. Do not bypass protection or invent evidence.

# Active CI/CD standard: dev -> qa -> main

Owner-authorized migration in 6.5.7 replaces feature-to-dev PR development. Only three principal remote branches are retained after verified retirement. Preserve local worktrees and unique history.

| Stage | Trigger | Mandatory checks | Promotion |
|---|---|---|---|
| Local dev | Before normal push | Full software regression, static validation, frontend build and deterministic 2D/3D browser | Guarded normal push to dev |
| GitHub dev | push dev | Policy, Python 3.11/3.12 Windows/Linux software regression, frontend types/tests/build, security, browser | Development gate |
| QA | PR dev -> qa | Development gate + matching-source real live research/provider qualification + AI-UAT | QA gate; trusted native auto-merge may be enabled only after qualification |
| Main acceptance | PR qa -> main | Same mandatory QA criteria | Owner-authorized native auto-merge only after all mandatory gates pass |
| Delivery | push main | Qualified QA PR provenance, matching tested tree, build/package/checksum | GitHub Release; PC update remains controlled |

Coverage has no percentage threshold at any stage. Every selected mandatory regression must execute/PASS; reported coverage scope/denominators cannot be hidden. The only deferred dev test IDs are the three declared live-provider tests in devtools/verification/layers.py, explicitly NOT_RUN and required at QA/main. Official SDK offline regressions remain mandatory software tests.

quality.yml contains CI only. release.yml contains main-push CD. The old duplicate workflow registrations are disabled and historical runs retained. Privileged automerge controller loads protected main code only; new candidate controller code is not active on main before qualified adoption. Required QA/main protection is strict GitHub Actions QA gate (app15368), enforced for admins, with no force push/delete. Dev uses local-before-push guards plus independent push CI; its former required-PR rule must be migrated only after local proof, with API readback.

The local supervisor is an explicit trusted tool, not built-in GitHub AI. See CI_REPAIR_SUPERVISOR.md for registration, exact-head checks, state and three-attempt bounds. No credentials or CI logs can grant themselves repair authority. Repo auto-merge, registration and actual successful merge are separate facts; report measured status in STATE.md.

Existing 6.5.6 same-suite comparison and old-policy failures remain in docs/qa/evidence/. TASK-UAT-LOCAL-ADAPTER has exhausted its three-attempt budget; do not reset it. Missing current-source live/AI-UAT qualification blocks QA/main even if dev is green. No baseline exceptions are granted.
