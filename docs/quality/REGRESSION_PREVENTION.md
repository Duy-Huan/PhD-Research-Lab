# Regression prevention

Active owner policy: AI develops only on dev, complete local software regression before push, dev -> qa -> main promotion. See agent/AGENT.md and agent/DEV_QA_MAIN.md. Coverage is collected across production sources and reported with denominators; it has no minimum pass threshold.

Add requirement IDs, behavioral acceptance tests and genuine RED/GREEN records with each feature. Generated inventories are NOT_RUN until assertions execute. Never weaken assertions, exclude failing code or silently skip mandatory regression. --require-complete rejects failed/error/skipped/unverified/empty selected software suites and unstable source.

quality.yml is the sole Quality Gates CI definition: dev push software checks, qa/main promotion PR software plus actual live/provider/research/AI-UAT. release.yml handles qualified main-push CD separately. Hosted CI has no automatic access to local models/subscription CLIs; unavailable evidence blocks QA/main. Three explicitly declared live IDs are deferred from dev with NOT_RUN records, not fake PASS; SDK offline socket tests remain selected.

tools/protect_agent_resources.py rejects deletion or rename-out of skills/ and agent/ across the entire commit range. Preserve raw failures, known-issue accounting, worktrees, source hashes and exact-head independent CI. Configuration and unit policy fixtures do not prove a real remote run or scientific claim.
