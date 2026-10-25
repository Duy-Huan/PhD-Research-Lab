# Branch migration checkpoint

The initial local origin/main cache was `70aabbb`; the actual remote main was `6725975261fe6a4d8a5cb3e10208e31c3e24f0e2`. Read-only GitHub audit found three branches, six closed PRs, no open PRs, no protections/rulesets, no Actions secrets and no self-hosted runners. PR #6 was closed without merging. Main's newer five commits were merge commits; its merge into the governance worktree completed cleanly.

| Before | After | Preserved SHA / action |
|---|---|---|
| main | main | 6725975261fe6a4d8a5cb3e10208e31c3e24f0e2 unchanged remotely |
| qa/full-harness-20261024 | feature/full-harness-20261024 | Native GitHub rename, 3ba0e1e6549d625c36e0a7632c74f7732faf0b85 preserved |
| absent | dev | Created from remote main SHA |
| absent | qa | Created from remote main SHA |
| feature/v3.2-research-os | Same | Unmerged/local history retained |
| current QA hardening branch | feature/development-governance in separate worktree | Earlier tested hardening plus clean main merge; ongoing governance/UAT work |

Before mutations, binary diff, status, ref inventory and 107 changed/untracked files were copied to `output/playwright/full-20261024/governance-audit/snapshot-before-normalization/` in the original workspace. Local backup refs use `backup/pre-governance-20261025/`. These contain private working-state material and are deliberately not published wholesale.

After the remote rename, the stale remote-tracking `origin/qa/full-harness-20261024` prevented fetching canonical origin/qa. Only that backed-up cache ref was removed; the renamed remote branch and source commits were retained. No unmerged source branch, working file, research data or protected agent/skill file was deleted.

The original workspace still contains application/cloud/security/intelligence work for 6.4.5. Governance lives in `D:/git-repo/PhD-Research-Lab-worktrees/development-governance` with version 6.5.0. Do not reset either worktree. Commit, push, CI execution and actual auto-merge status must be read from the latest acceptance report; branch creation does not certify the pending code.
