# Harness team on models from the list: live Codex runs (6.6.4 A9)

Date: 2026-10-29. Disposable data folder `D:/qa663` (QA server on port 8791), a new project per run.
Model: `cli:codex`, signed in with the owner's ChatGPT plan, as the owner asked for live tests.
Driver: the QA server's own HTTP API, using only these routes: `/api/harness/team/propose`, `/api/harness/compile`,
mission approve and step review.

The QA operator approved the mission plan and the checkpoint in this disposable project, and both approvals say so in
their notes. This is a stand-in for the researcher's review; it is not an owner signature.

## 1. Team proposal (`live-propose.json`)

`cli:codex` as the architect received the objective, the model list with availability, and the tool catalog. Its
answer came back in 61.6 s:

| Agent | Role | Model it chose | Registry tools |
|---|---|---|---|
| literature | Literature reviewer | app:local | 12 |
| experiment | Protocol designer and experiment operator | cli:codex | 17 |
| verifier | Independent experiment verifier | cli:claude_code | 10 |
| writer | Evidence-grounded manuscript author | app:ollama | 18 |

The app validated every tool id and model. Codex placed the verifier on a different model from the experimenter.

**Finding, fixed:** Codex chose `app:local` and `app:ollama` because the model list showed them as available while
their registry state was only `UNKNOWN`. The model list now probes local engines, with a 5 s timeout cached for 30 s.
On the next listing, LM Studio showed `READY (LM Studio: nvidia/nemotron-3-nano-4b)` and Ollama showed
`UNREACHABLE (Ollama has no model …)`.
Test: `test_a_local_engine_counts_as_available_only_when_it_answers`.

## 2. Canvas → mission, run 1 (`live-run1-final.json`)

The canvas was Start → agent task (role `researcher` on `cli:codex`) → approval node → End. It compiled to the L3
mission `agent.task` → `review.checkpoint` → `mission.report`.

1. The plan was approved.
2. The Codex agent task completed in about 61 s.
3. The mission stopped in `awaiting_step_review` at the checkpoint.
4. After the review it went to `awaiting_review`; the final L3 review stays with the researcher.

**Findings, both fixed:**
- Codex said `library.search` was not among its tools. A CLI agent's grant held only the read MCP tools, so
  `phdlab_tools_call` could not reach the registry tools the team had given it. The grant now carries the agent's
  registry tools, which run under the owner's agent profile.
- The session's instruction files (`AGENTS.md`, `CLAUDE.md`, `FIREWALL.md`, `GEMINI.md`) were returned as the agent's
  outputs. `research._collect` now leaves them out at the session root. The same fix applies to delegate tools and
  coding runs.

Test: `test_a_cli_agent_grant_carries_its_registry_tools_and_session_files_are_not_outputs`.

## 3. Canvas → mission, run 2 with the fixes (`live-run2-*`)

The same canvas, on a new project:

- **Agent task:** completed in about 61 s.
- **Library check:** Codex called `library.search` through the registry (job `tj-5320ab757296963b6268`) and reported
  that the topic library is empty.
- **Output:** the only returned output was its own `design.md` (`live-run2-design.md`). It contains one narrow,
  testable hypothesis, the conditions and procedure, the metric and decision rule, and the explicit statement
  "design only; no experiment or protocol has been run or approved here".
- **Mission:** checkpoint, then review, then `awaiting_review`.

## Not shown by these runs

- **Full research run:** a run through an approved protocol, verification and a paper. That is the phase C campaign.
- **Claude Code:** not run as a team agent here. It is listed and available.
- **Text encoding:** the stored answers use UTF-8 correctly, for example `I’ll` stored as `U+2019`. A terminal that
  shows `I�ll` is a console display artefact.
