# CI recovery and known issues6.5.11

Candidate6.5.11 on existing `dev`, parent `3f60a77c54ada9f1197c901019a119ad5d4ddebf`, source `dd01c60ac488bd91da7dd0cfaf880893d88232e6c1444cebca1b8d265571886c`. Actual stable local complete software gate PASS. Fresh exact-head GitHub CI is still required; no future PASS is presumed.

CI-DEP-001: explicit process-test dependency missing on hosted runners; corrected in dev/CI lock.

CI-FIXTURE-001: controlled CLI protocol fixture accidentally depended on real host runtime installation; corrected in fixture context, with new absent-runtime regression and production fail-closed assertion unchanged.

CI-NATIVE-CRASH-001: historical Ubuntu3.11 SIGSEGV cause remains UNKNOWN/NOT_REPRODUCED locally. New fault-handler instrumentation and actual fresh CI are required; no existing failure is reclassified as PASS.

Original native/UI/integrity fixes and the Hermes deferred-tool-discovery limitation remain recorded in NATIVE_CONSOLIDATION_DEFECTS.json and prior reports. The native tool reliability observation is an optional model qualification finding under the new owner policy, not a software regression waiver. Scientific quality/L3/L4 remain unproven.

[Detailed CI diagnosis](CI_ROOT_CAUSE_REPORT.md). Test retirement ledger is unchanged by this recovery: no old software case was removed or skipped to get PASS.
