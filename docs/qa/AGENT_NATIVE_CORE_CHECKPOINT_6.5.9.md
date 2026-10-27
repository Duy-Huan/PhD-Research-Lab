# Agent-native research environment checkpoint ? 6.5.9

Local pre-publication snapshot for CI fixture repair1/3, source `b2b35a188e3eba19323c7c9eb51bf99b993c8f1018262787f974aff8baa47ac1`, stable. Baseline HEAD2a5ee141a1d06291eb65589045f0c5a35b711526. Actual latest publication/CI must be read from GitHub and shared.git/ci-observations/6.5.9-dev/receipt.json; no future remote result is presumed.

**Local software1199/1199PASS; release BLOCKED.** The current candidate retains the model-led conversation, context fidelity and native streaming fixes from6.5.8, plus measured runtime cleanup/source-identity corrections. It does not complete every requested architecture change or establish L3/L4.

## Actual repairs and one failed CI cycle

- BUG-CLI-RUNTIME-CLEANUP-001: three actual native probes left proxy containers. Parent/wrapper now share a fresh invocation owner and reuse exact owned-container/IPC-volume cleanup. Work/count/timeouts are bounded; failed cleanup cannot be reported as successful completion. Cancellation/consumer-close fallback retains diagnostics.
- BUG-VERIFY-EOL-001: three Apache license CRLF hashes produced different Windows/Linux fingerprints. Declared text now receives LF normalization; actual content changes still invalidate proof. Actual first6.5.9 CI artifacts all matched568d68f... across four environments. This validates that correction, not the failed run as a whole.
- BUG-TEST-RUNTIME-CACHE-001: first6.5.9 [CI40221840300](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40221840300) failed on all four backend jobs:970PASS/3ERROR each. The new Python protocol fixture inherited real executable discovery, colliding with cached missing-vendor health under gw:codex:None. This was a newly introduced test-infrastructure regression, not a reason to install/sign in Codex on hosted CI or skip tests. Fixture.binary now identifies sys.executable. A permanent absent-vendor/cached-health case reproduced the error before correction, then the affected suite43PASS. Real provider health still correctly reports UNAVAILABLE when its binary is absent.

The incomplete first local reproduction did not seed the unavailable cache and passed; it is retained but is not RED evidence. Correct RED9cases/1ERROR and GREEN43PASS are retained. Exactly one failed repair cycle is recorded under BUG-TEST-RUNTIME-CACHE-001, maximum3, without resetting the unrelated UAT ledger. No assertion/gate was weakened and no mandatory case was skipped.

## Complete current local execution

Command: `python scripts/verify.py --profile pr --component all --base origin/dev --out output/playwright/hermes-core-audit/runtime-cleanup-659-ci-repair-1`, pinned Python3.12.15 CI environment.

| Scope | Actual result |
|---|---|
| Backend software |974/974PASS,0FAIL/ERROR/SKIP;538.85seconds |
| Frontend unit assertions |194/194PASS |
| Real Playwright2D then3D |27/27 then1/1PASS |
| Owned process/browser boundaries |3/3PASS |
| Total selected software |1199/1199PASS;0FAIL/ERROR/SKIP/NOT_RUN/BLOCKED/UNVERIFIED |
| Node GitHub policy fixtures |48/48PASS separately |
| Types/build, syntax lint, pinned workflow syntax, contracts, discovery, protected files |PASS |
| Receipt validator / command wrapper |Observed exit0; source stable |

Static inventory127Python modules,42frontend unit files,6offlinePlaywright files is NOT_RUN inventory, not execution. Actual selected assertions above ran. Separate model/browser/live inventories remain unqualified at dev and are mandatory for QA/main. Browser cases include controlled fault fixtures; their count is not a production feature coverage percentage.

## Runtime and real provider evidence, with scope

The earlier frozen-source Docker experiment actually killed wrapperA, observed remaining resources, removed exact ownerA containers/volume while ownerB stayed running, then cleaned both. No inference or mocked Docker transport was used. Actual native Codex corrected smoke created no additional runtime resources relative to its captured baseline. Three prior probe-owned proxies and one verified unused app IPC volume were cleaned by exact ID/label only. No research data or agent/skills file was deleted.

The fixture correction changes no production code: a comparison of 301production/runtime source files against the previously tested source568d68f... found zero changed files. [Source comparison](evidence/cli-runtime-cleanup-6.5.9/ci-fixture-repair-r1/production-code-comparison.json) is a source comparison, not a new live run or final-source scientific qualification. [Actual Docker proof](evidence/cli-runtime-cleanup-6.5.9/actual-frozen-runtime.json) retains its own source identity. Host-crash recovery and every startup/cancel race are not qualified.

Actual official ChatGPT subscription inference through Codex0.163.0/gateway succeeded with API keys excluded; nonce/arithmetic responses and real usage events were retained. The exact CodexLive smoke and separate Spark LM Studio load/resource-gate/unload smoke also really passed in their recorded development scope. Exact model entitlements, all native MCP/tool paths and dashboard usage aggregation are not claimed. Spark resource verification used no inference or AI-UAT; its one-use UAT allowance is still unused.

## Coverage and release decision

Backend lines23949/26570 (90.14%); branches7156/8820 (81.13%); combined87.89%. Frontend lines65.97%, branches64.92%, functions51.39%. Desired100% production line/branch coverage is not achieved. Coverage is informational; every mandatory selected software regression must execute/PASS.

One environment, agent-selected research methods, evidence-backed learning: [persistent learning policy](../../agent/OPEN_ENDED_CAPABILITY_LEARNING.md), [implementation gap audit](../architecture/OPEN_ENDED_CAPABILITY_GAP_AUDIT.md). Full procedural learning (immutable skill revisions, evaluation/held-out transfer, activation and rollback) is DESIGN_RECORDED/runtimeNOT_RUN. ScopedL3/L4 remain NOT_DEMONSTRATED. No new Research Engine or compulsory six-step research script was built.

Feynman/OpenScience retirement with native replacements, one-paper-project migration and complete unified native/API/local provider configuration/usage/tool workflow remain pending/partial. Required exploratory UAT adapters are NOT_IMPLEMENTED and complete final-source live/provider/research/CLI/2D/3D/UAT evidence is missing. QA/main remain BLOCKED; no unqualified merge, tag or release. Original three UAT failures and exactly one unused600second/six-step Spark allowance remain intact.

[Current actual software report](evidence/local-verification/report.json), [preserved repair-cycle report](evidence/cli-runtime-cleanup-6.5.9/ci-fixture-repair-r1/final-software/report.json), [machine defect registry](AGENT_CORE_DEFECTS_6.5.9.json), [actual failed matrix](evidence/cli-runtime-cleanup-6.5.9/ci-fixture-repair-r1/first-run-matrix.json). Earlier local1198PASS and6.5.8/6.5.6 comparisons remain historical; they cannot substitute for this source's independent latest-HEAD CI or be compared by raw PASS totals.
