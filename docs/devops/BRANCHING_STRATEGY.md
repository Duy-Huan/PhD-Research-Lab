# Branching strategy

Permanent branches: main (stable), dev (integration), qa (release validation). Work moves `feature/* -> dev -> qa -> main`. Short-lived fix/docs/chore branches may target dev through the same PR gates, but automatic merging is intentionally restricted to trusted feature/* PRs.

Start new work from fetched dev. Preserve existing task branches and unpushed commits. Merge current dev into a task branch without rewriting history; use a separate worktree when another task has dirty work. No force-push, reset-hard, unmerged branch deletion or main/qa auto-merge. After a successful native squash dev merge, verify GitHub's merge SHA is on dev before any disposable-worktree cleanup. Never remove protected skills/agent files.

Promotion fixes go back through dev, then qa; do not leave qa-only fixes that disappear in the next promotion. Main needs human release authorization and matching QA evidence. See [branch protection](BRANCH_PROTECTION.md), [migration](BRANCH_MIGRATION_REPORT.md) and the [user guide](CI_CD_USER_GUIDE.vi.md).
