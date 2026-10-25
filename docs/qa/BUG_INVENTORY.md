# Current measured defect inventory ? 6.5.9

Local snapshot before6.5.9 publication. Source `568d68f5c218f4ccdfa941de160621e79e5a6794309ffaaf14b68d179e76b3c3`, stable. Baseline HEADb3080ab0f89715b207c7e2004d84968954eef5e5. Actual publication and independent CI must be matched by exact latest GitHub HEAD; durable remote receipts are in shared.git/ci-observations/6.5.9-dev/. This local report does not presume a future GitHub result.

Two additional confirmed P2 groups were repaired locally: CLI runtime resource leak and Windows/Linux license source-fingerprint mismatch. [Machine-readable reproduction, evidence and regression IDs](AGENT_CORE_DEFECTS_6.5.9.json). Independent latest-HEAD GitHub qualification is separate from this local snapshot. This is a scoped inventory, not proof of zero remaining defects across the repository.

No baseline exception or test waiver was approved. The older3Dlocale defect was fixed/verified in6.5.7. Older unresolved observations and previous main/candidate evidence remain in [historical inventory](history/20261026-before-659/BUG_INVENTORY.md) and KNOWN_ISSUES_BASELINE.json; do not reset history or treat stale old OPEN labels as a fresh reproduction. Missing new UAT adapters and research evidence are explicit qualification blockers.
