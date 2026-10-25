# Regression prevention

The operational contract is [agent/AGENT.md](../../agent/AGENT.md). Add requirement IDs, behavior oracles, error/persistence/cancellation cases and relevant live journeys with each feature. Generated cases require executed assertions and a failing seed must be retained.

`tools/qa_harness.py` inventories API operations, workflows, node types, providers and source hashes; generates valid/dangling-edge graph cases; checks confirmed fake-success patterns; and rejects incomplete release evidence. It does not automatically infer correctness of arbitrary new features.

`tools/backend_quality_gate.py --require-complete` fails on failures, errors, skips, changed production sources during the run or incomplete production line/branch coverage. Whole-source frontend coverage uses 100% thresholds for lines, statements, functions and branches. The current results fail these thresholds; the gate has not been weakened.

`.github/workflows/full-harness-regression.yml` runs integrity checks, protected-file checks, generated cases, backend Windows/Linux and frontend coverage/build. Hosted CI has no automatic access to the local model or subscription CLIs. Local live evidence and scientific review remain separate release requirements. Remote configuration alone is not a passed CI run.

`tools/protect_agent_resources.py` rejects deletions and renames out of `skills/` and `agent/` in the staged diff or every commit of a CI range, including files introduced and deleted within that range. These directories must never be pruned during cleanup.
