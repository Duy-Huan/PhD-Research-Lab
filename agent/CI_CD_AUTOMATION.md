# Current CI/CD standard — candidate6.5.5

This replaces the parked71e5332 automatic qa/main promotion design. Never automatically modify qa/main, bypass protection, weaken100% gates or claim unexecuted acceptance.

- `quality.yml`: pull_request only, build/static/tests/coverage/security/browser/evidence; Development gate for dev and QA gate for qa/main. No release publishing or production approval job in PR CI. Rerun an existing PR run instead of a diagnostic dispatch overwriting required status contexts.
- `scripts/verify.py`: canonical shared local/CI verification. `feature` is pre-push development verification; `pr/full` retains strict coverage/completeness. Real provider/research/AI-UAT qualification remains separate and mandatory where required.
- `scripts/ci_repair_supervisor.py`: local owner-authorized failure polling/CLI assignment, exact PR/head/worktree, immutable tests/gates, three-invocation persistent budget. See CI_REPAIR_SUPERVISOR.md.
- Native GitHub auto-merge: only eligible trusted feature/fix PRs into dev, only after genuine current required checks and mandatory jobs. Observe and record actual merge SHA. Repository quarantine is not automatically lifted by a passing unit fixture.
- QA: owner-controlled dev→qa PR, full regression plus authorized live/AI-UAT evidence. Only qualified QA may open qa→main. Main promotion stays manual/protected.
- `release.yml`: after qualified main push, verify native qa→main provenance and tested tree, build/package/checksum and publish GitHub Release. PC installation is user-controlled with data backup/rollback; no cloud deployment or automatic data migration.

Legacy workflow files are removed in candidate history, duplicate old GitHub workflow registrations are disabled with readback, and run/evidence history is retained. Main required context migration (`Release gate`→`QA gate`) must be recorded as an actual settings change before declaring the split fully adopted. Protected history cannot be rewritten just to remove the old default-branch files early.

Comparison methodology: docs/qa/COMPARISON_PROTOCOL.md. Same test bundle/environment/policy; fixed critical denominator; old/new/unclassified/unexecuted results separated. Absolute PASS totals from different suites do not rank branches. Current release remains NO-GO until all mandatory criteria really pass.
