# 6.5.7 current software verification

Owner policy: AI develops/commits only on dev; full local software regression before dev push; dev -> qa -> main promotion. Coverage is informational. Actual live/provider/research/AI-UAT is mandatory at QA/main.

Canonical command: python scripts/verify.py --profile pr --component all --base origin/dev --out output/playwright/regression-policy-657/pr-all-stable

Result: **1127PASS,0FAIL/ERROR/SKIP/NOT_RUN/BLOCKED/UNVERIFIED**. Backend921/921; frontend176/176; Playwright27/27; real owned-process/browser capability boundaries3/3. The browser suite includes labeled controlled harness fault cases, not27 distinct production features. Node policy tests42/42 separately PASS; frontend typecheck/build PASS; dependency audit PASS and high-severity/high-confidence Bandit PASS. Coverage remains87.62%combined backend (23841/26528lines,7121/8808branches); frontend64.02%lines/63.32%branches/50.00%functions/62.54%statements. No percentage threshold or baseline exception is used.

Source digest: 8cd61b8559a2abbfd87c7ac80ce2234b852d73bb47f92d8f59bcd3efc431dab5. Source was stable; full raw report includes file digests/environment/commands. Report's pre-commit HEAD5415743 identifies integration history; the eventual dev publication commit must be verified independently on GitHub. No cached passing result was reused. An earlier attempt was cancelled after root instruction cleanup changed source; it remains incomplete, not PASS.

Exactly three live-provider IDs remain explicitly NOT_RUN in the separate deferred list, required at QA/main. Offline ClearML and actual official OpenScience SDK socket regressions were provisioned and run, not hidden as live deferrals. The SDK archive is pinned and hash-verified; see official-sdk-provenance.json. These results are software verification, not live model or scientific certification.

Installed local guard rejects dirty/unverified normal pushes and non-dev source development; actual negative dry-run evidence is retained. Source reports/receipts are local trusted-client enforcement, not an unbypassable server control. No --no-verify/force push/admin bypass is permitted.

EN/VI3D labels/roles have actual unit RED/GREEN and the real Playwright WebGL journey now asserts English system labels and absence of the old Vietnamese hint. No intentional redesign. QA/main remain BLOCKED pending current-source trusted live/research/AI-UAT evidence; TASK-UAT-LOCAL-ADAPTER exhausted3 must not retry or reset. No release or zero-bug claim.

Evidence: docs/qa/evidence/dev-qa-main-6.5.7/. Historical main/candidate6.5.6 same-suite evidence remains unchanged and used its then-current policy; do not compare raw PASS totals between different suites.
