# Agent-native core and runtime reliability ? 6.5.9

Local snapshot before6.5.9 publication. Source `568d68f5c218f4ccdfa941de160621e79e5a6794309ffaaf14b68d179e76b3c3`, stable. Baseline HEADb3080ab0f89715b207c7e2004d84968954eef5e5. Actual publication and independent CI must be matched by exact latest GitHub HEAD; durable remote receipts are in shared.git/ci-observations/6.5.9-dev/. This local report does not presume a future GitHub result.

**Local software PASS; release BLOCKED.** This extends the [6.5.8 core checkpoint](AGENT_NATIVE_CORE_CHECKPOINT_6.5.8.md), with two actual defects discovered beyond passing smoke assertions.

## Measured corrections

- BUG-CLI-RUNTIME-CLEANUP-001 / P2: native turn shutdown could kill the runtime wrapper before its Docker finally cleanup. Three actual successful probes left proxy containers running. Parent and wrapper now share a fresh invocation owner and reuse exact-label/container/IPC-volume cleanup. Resource count and operation timeouts bound work; cleanup failure produces an error/nonzero completion. Consumer-close fallback retains diagnostics. Other invocations are not cleanup targets.
- BUG-VERIFY-EOL-001 / P2 infrastructure: actual6.5.8 Windows/Linux artifact fingerprints differed only in three Apache license files with CRLF versusLF. Declared license text now receives the existing LF normalization. Genuine content changes still invalidate proof, and staging does not change identity.

Preserved functional RED/GREEN: eight cleanup behavior cases plus affected connectivity/workspace suite42PASS; source identity5PASS after real RED. The initial targeted attempt failed from fixture-owned sticky error state; test cleanup was corrected without weakening assertions. All raw failed records remain. A first6.5.9 full run was deliberately ABORTED before the source-identity correction and is notPASS.

## Actual local execution

`python scripts/verify.py --profile pr --component all --base origin/dev --out output/playwright/hermes-core-audit/runtime-cleanup-659-final` using the pinned Python3.12.15 CI environment.

| Scope | Executed result |
|---|---|
| Backend software |973/973PASS,0fail/error/skip,530.18seconds |
| Frontend unit assertions |194/194PASS |
| Actual Playwright2D then3D |27/27 then1/1PASS |
| Owned browser/process boundaries |3/3PASS |
| Total selected software cases |1198/1198PASS,0FAIL/ERROR/SKIP/NOT_RUN/BLOCKED/UNVERIFIED |
| Node GitHub policy fixtures |48/48PASS separately |
| Types/build, contract policy, pinned workflow syntax, syntax lint, discovery, protected files |PASS |
| Source-bound receipt validator |Observed exit0; no source change since full run |

Unlike the preceding redirected shell run, this full command's wrapper also returned0. Browser counts include controlled fault fixtures, not28 independent production features. This is software regression, not full live/scientific acceptance.

## Actual runtime and provider evidence

The frozen-source Docker experiment ran two separate real runtimes with no model inference or mocked transport. Forced termination of wrapperA left real containers. Parent cleanup removed A's containers and volume while B still had its two running containers and volume. Both were then actually cleaned; source remained stable. [Raw frozen proof](evidence/cli-runtime-cleanup-6.5.9/actual-frozen-runtime.json).

The corrected real Codex smoke also passed and created no additional container/volume relative to its recorded baseline. Earlier actual subscription nonce/arithmetic probes and the exact CodexLive case used official ChatGPT sign-in with API keys excluded; they do not establish every native tool path or scientific quality. A separate actual Spark LM Studio test loaded/gated/unloaded the model and observed VRAM4947->1843MB; no inference or AI-UAT was used. Those development receipts are under output/playwright/hermes-core-audit/, with their own source identities; they cannot be relabeled as complete final-source QA evidence.

Three known probe-owned proxy containers and a separately verified unused app IPC volume were cleaned only after exact ID/label/ownership checks. No research data or agent/skills file was deleted. Application-host crash recovery and every startup/cancellation race remain unqualified; this repair does not claim universal leak freedom.

## Coverage and release limits

Backend lines 23949/26570 (90.14%); branches 7151/8820 (81.08%); combined 87.88%. Frontend lines65.97%, branches64.92%, functions51.39%. Desired100% production line/branch coverage is not achieved; coverage remains informational, not a waived failing test.

Full open-ended capability learning is DESIGN_RECORDED/runtimeNOT_RUN. Reuse existing candidates/skills/memory/experiments, then qualify immutable revisions, evaluations, held-out transfer, scoped activation and rollback. No new Research Engine or compulsory six-stage scientific method was added. ScopedL3/L4 remain NOT_DEMONSTRATED.

Active Feynman/OpenScience retirement, one-project/one-paper migration and complete unified provider configuration/usage/tool workflow remain pending/partial. Preserve all research/harness/data functions. New required exploratory UAT adapters are NOT_IMPLEMENTED; complete matching-source provider/research/CLI/2D/3D/AI-UAT evidence is missing. QA/main therefore stay BLOCKED, not automatically merged. The original three UAT failures and exactly one unused600second/six-step Spark allowance are preserved.

Published6.5.8 [GitHub run40218073963](https://github.com/Duy-Huan/PhD-Research-Lab/actions/runs/40218073963) actually succeeded, with964/964 and0skip on all four Windows/Linux Python3.11/3.12 jobs. The dev push emitted no exact required `QA gate` context; out-of-phase skips are not QA success. That run does not qualify changed6.5.9 source. New independent CI must prove latestHEAD and identical corrected fingerprints on all matrix environments.

Raw evidence: [current local report](evidence/local-verification/report.json), [preserved final software](evidence/cli-runtime-cleanup-6.5.9/final-software/report.json), [defect registry](AGENT_CORE_DEFECTS_6.5.9.json), [receipt validation](evidence/cli-runtime-cleanup-6.5.9/final-software/receipt-validation.json). Historical five-report snapshots are preserved under history/20261026-before-659/.
