# Qualification suite cpu-ml-v1 (frozen)

Owner decision, 2026-10-29: small CPU-scale ML, 4 cases (2 guided, 2 open-ended), 40 turns and 2 restarts per case,
about 2 hours per case, Codex (`cli:codex`). Scope and rules: `agent/PLAN_6.6.4_L3.md` phases B and C.

| File | Purpose |
|---|---|
| `suite.json` | Cases, questions, datasets (generator arguments and sha256), budget, stopping rules, measured criteria |
| `suite-digest.txt` | sha256 of the canonical JSON; `devtools.qualification.suite.load()` refuses a changed suite |
| `generate_data.py` | Recreates every dataset byte for byte and checks its sha256 (`python generate_data.py <out_dir>`) |

Never edit a frozen suite: copy it to a new version (for example `cpu-ml-v2`) and freeze that. Held-out datasets go to
the case verifier only, never into the agent's project. `campaign_template()` starts the campaign record that
`backend.agent.qualification.score()` reads; with nothing measured every criterion is NOT_RUN.
