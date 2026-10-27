# Enforced GitHub branch protection

The repository API returned HTTP 200 for all three protections on 2026-10-25 (Asia/Saigon task date). Before the change there were no protections or rulesets. Repository admin permission was available. Auto-merge was initially false and subsequently enabled by the owner; read-back confirmed true.

| Branch | Required Actions context | Up to date | Approving PR reviews | Admin enforcement |
|---|---|---|---|---|
| dev | Development gate | Required | 0; PR still mandatory | Enabled |
| qa | QA gate | Required | 0; PR still mandatory | Enabled |
| main | Release gate | Required | 1 | Enabled |

All require conversation resolution and disallow force pushes/deletions. Required contexts are pinned to GitHub Actions app ID 15368. The production environment requires Duy-Huan review. No bypass was used. These settings intentionally block merges while contexts are missing or failing; configuring them is not proof a workflow passed.

Main's reviewer must be someone other than its PR author. This is GitHub's review rule; do not create a fake approval or disable the rule when working solo. The owner can review an appropriately authored promotion PR, or add a trusted reviewer. Never auto-merge main.

Read-only audits are safe to repeat. When modifying protection later, compare the full returned policy first; do not overwrite a stronger existing setting with a weaker template. See [GitHub protected-branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

The branch-protection read endpoint requires Administration:read, which the normal workflow GITHUB_TOKEN cannot request. The protected-main handler accepts an optional separate `AUTOMERGE_POLICY_READ_TOKEN` with only the repository permission needed to read policy; it never uses that credential for merging. No such secret was present in the real audit, and none has been copied from the developer machine. Missing/unreadable policy returns BLOCKED with no write. This is an additional activation prerequisite, not permission to weaken the protection check. See [official GitHub endpoint permissions](https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection).
