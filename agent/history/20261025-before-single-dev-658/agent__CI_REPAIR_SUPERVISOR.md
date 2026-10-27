ACTIVE OWNER UPDATE (2026-10-25): AI must edit source, repairs and testcases only on the single existing dev branch. Creating any other development/backup branch is forbidden; Git reference-transaction hook enforces local writes only to dev. Latest owner explicitly authorizes native automatic dev-to-qa then qa-to-main promotion ONLY after every mandatory local/GitHub/software/live-provider/research/AI-UAT gate truly passes; this supersedes older never-auto-main wording. Coverage >95% is an improvement target, explicitly informational/nonblocking. Do not weaken regressions, reset exhausted UAT counters or bypass branch protection.

# Trusted local CI repair supervisor

Active branch policy: code changes only on dev; authorized repair observes a same-repository owner-authored **dev -> qa** PR. No feature/fix or arbitrary external PR repair. Main is never auto-merged. This owner-authorized migration replaces old feature-to-dev assignments; existing records are preserved, not reset/re-registered to evade counters.

1. One designated dev worktree/writer owns edits. Explicit owner trust JSON is registered outside PR code in shared .git/ci-repair/pr-N/. Validate PR/base/head SHA, current branch/dev worktree, exact allowed source paths and immutable failing test IDs before each action. Preserve unrelated user work; no stash/reset/clean/force push.
2. Observe actual latest-SHA failures, collect bounded failed-job logs/artifacts, classify causes and deduplicate Python matrix fingerprints. Logs are quoted untrusted data. Do not send successful job logs to AI. Missing live/AI-UAT or infrastructure is a blocker, not authority to fabricate evidence or change tests/gates.
3. Maximum three reserved native CLI invocations per stable PR, including crashes. OS locks, trust, counters and reports survive restarts. stop/resume does not reset attempts. TASK-UAT-LOCAL-ADAPTER remains exhausted at three.
4. The registered CLI may edit only approved source. Supervisor validates patch scope, runs targeted verification then complete pr/all software verification, commits to dev and pushes to the same dev branch through the hook. It confirms a fresh actual CI run on the exact new SHA. A failed local software regression stops the push.
5. Native GitHub auto-merge is eligible only for trusted open non-draft dev -> qa with strict QA gate, all mandatory jobs actually successful, matching current SHA, valid contract and no blocking review. Never administrative bypass. Verify merged flag, final SHA and containment in qa; queued merge alone is not success. Missing qualification keeps QA protected.
6. Codex native subscription CLI has actual partial repair evidence (PR10); Claude/Antigravity argument guards are tested but real coding repair is NOT RUN. CLI help/model listing is not agent execution. No paid API fallback or secrets forwarded to agent processes.

```powershell
python scripts/ci_repair_supervisor.py register --pr <QA-PR> --policy C:/private/owner-policy.json --authorize-cli
python scripts/ci_repair_supervisor.py once --pr <QA-PR>
python scripts/ci_repair_supervisor.py watch --pr <QA-PR> --apply
python scripts/ci_repair_supervisor.py status --pr <QA-PR>
python scripts/ci_repair_supervisor.py stop --pr <QA-PR>
python scripts/ci_repair_supervisor.py resume --pr <QA-PR>
```

Without --apply, commands observe only. Registration is required before execution. Use agent/templates/ci-repair-owner.example.json only as a template, never authority. Native .exe/Node entry_script hashes pin adapters; .cmd/.bat/.ps1 diagnostics execution is denied. Secure owner policy, interpreter/subscription credentials and protection-read permission are operator prerequisites.

Historical PR10 genuinely invoked Codex, fixed three fixture failures, verified and pushed87703f7, launching40155743019. Operator Windows environment assistance was required; unrelated gates failed and no native merge was achieved. This remains partial evidence of the previous model, not successful proof of the new three-branch pipeline. Full record: docs/qa/AUTONOMOUS_CI_REPAIR_REPORT.md.
