# 6.6.4 plan: remove the technical blockers on the way to scoped L3

Status: APPROVED scope (owner, 2026-10-28): phases A, A-QA and B all ship in 6.6.4 as one release. Estimate:
10-14 working days. Order: A-QA, A1, A2, A3, A6, A9, A4/A5/A7/A8/A10/A11, then B. Phase C (campaign) follows the release.

Scale: "L3" here is the research-autonomy scale in [RESEARCH_QUALITY_OBJECTIVES.md](RESEARCH_QUALITY_OBJECTIVES.md). It is not
the Missions/Harness L1–L4 execution policies in `backend/agent/autonomy.py`.

Baseline at v6.6.3 (`66b7311`):
- All 14 criteria RQ-01..RQ-14 are `NOT_RUN`; `achieved_level` is null.
- 6.6.4 removes the blockers and builds the measurement tooling. It does not claim L3.
- An L3 claim needs the qualification campaign in phase C, with measured evidence for every critical criterion.

## Findings this plan is based on

1. **Live Codex run, 2026-10-28** ([cli-agent-registry-662/live-codex.md](../docs/qa/evidence/cli-agent-registry-662/live-codex.md)).
   - Codex found real papers, wrote and self-checked code, measured results, and drafted a paper whose numbers match the measurements.
   - People still stepped in for ordinary steps: a hand-applied code fix, a QA-written approval, and a researcher-created writing mission.
   - The draft has no citations, agent preambles leak into the text, gates passed empty sections, and no PDF was produced.
2. **Playwright check of Harness Studio, 2026-10-28** (screenshots in `output/playwright/harness-team-663/`, local only).
   - **Team formation is keyword matching, not AI.** `auto_generate_team()` picks preset agents when words such as "paper", "code" or "train" appear.
   - **The architect fills a fixed template.** `generate_workflow_from_objective()` outputs the same 9-node graph for every goal.
   - **The canvas does not run agents.** `workflow_runtime._execute_single_node` only runs control flow, approvals, gates and benchmark tools. Running a generated workflow completed Start, and all 8 other nodes were `blocked`.
   - **`/api/harness/architect/team` is never called by the UI.**
   - **"Automated Agents" is a dead button** when Harness Studio is opened from the header. It only works inside the Missions panel.
   - **Vietnamese in English mode:** the 6 preset agents in the Team tab, and the architect's generated description and node names.
   - **Mission Teams sit behind flags that are off by default** (`research_os.enabled`, `team_enabled`, `multi_team_enabled`). `teams.propose()` splits a mission's existing tasks into worker/compute/verifier roles deterministically.
3. **L1–L4 Playwright coverage.**
   - `frontend/e2e/workflows.spec.ts` and `harness_ide.spec.ts` exist but are marked `needs_model: true` in `devtools/verification/uat_config.json`.
   - Routine CI therefore never runs them, so no L1–L4 flow is checked on any commit.

## Phase A: remove technical blockers (software, every item test-first)

Progress 2026-10-28:
- A1 is done locally (FQC-TOOL-JOBS-664). `phdlab_tools_call` waits at most 45 s, then `phdlab_tools_job` takes over.
- A5 is done locally (FQC-TOOL-SHELL-664). `sandbox_run_code` names cmd.exe or POSIX sh.
- A2 is done locally (FQC-AGENT-PROTOCOL-664). `experiment.propose_protocol` freezes agent code with a pinned environment;
  after approval it runs as `experiment.run` and is checked by `experiment.verify` (agent-code-recompute-v1).
- A3 is done locally (FQC-CODE-TOOLS-664). `code.create_project` / `code.open_project` and `code.apply_patch`
  (sha256-bound, git-committed or journalled) replace the new-folder-per-run limit.
- CI on Windows found a CLI chat race (text written just before a turn ends was dropped); fixed in `02d0517`.
- A6 part 1 is done locally (FQC-PAPER-EVIDENCE-664): writer evidence (library + verified runs), no template prose,
  preamble stripping, manuscript gate, `library.search` / `library.passages`. Part 2, a bundled LaTeX engine for the
  PDF, is done locally (FQC-LATEX-BUNDLE-664): Tectonic 0.17.0, SHA-256 pinned, in <install>/tools of the .exe and
  .deb; CI installer smoke runs it. A live PDF compile on the owner's machine needs the owner's permission to run the
  downloaded binary (the session's permission check blocked it); its first compile needs internet.
- A9 is done locally (FQC-HARNESS-TEAM-664): AI-proposed team bound to the model list, canvas → governed mission
  (agent.task, review.checkpoint), Team tab UI, HARNESS-LEVELS-004 in CI. Live Codex runs (2026-10-29) proposed a
  4-agent team and ran an agent task to a checkpoint; three findings fixed (local engines shown available unprobed,
  registry tools missing from CLI grants, session files returned as outputs). Owner decision still open: default of
  research_os.team_enabled (off).
- A12 is done locally (FQC-TOOL-LISTING-664): /api/tools built the index 59 times per listing (1.29 s); now once (about
  0.02 s). A10 (FQC-LONG-PATHS-664): the system scan and startup warn about long Windows data paths. A11
  (FQC-LINE-ENDINGS-664): approvals are canonical-JSON digests over frozen bytes since A2; regression tests show a
  line-ending conversion of the working copy keeps the approved run, and a converted frozen or result file is refused.
- A7 is done locally (FQC-DISCOVERY-PARTIAL-664): a rate-limited provider no longer fails a discovery step that found
  papers; the step is partial and names the provider. A8 (FQC-MISSIONS-LIVE-664): mission changes are published on
  the bus (agent-created missions appear live), the selected Topic survives a reload, the Missions header wraps in a
  narrow drawer (missions_live.spec.ts in the offline CI run).
- A4 is done locally (FQC-DEPS-PINS-664): a failed pinned install is never replaced by an unpinned one, +cpu/+cuNNN pins
  use the PyTorch index, one install per environment at a time (lock), new code projects do not inherit site-packages.
  Phase A is complete locally; phase B (qualification tooling) is next.
- CI on Linux (13000d6) found the narrow-drawer squeeze the live run reported: the sidebar's header icons shrank below the
  20 px tap target at 1024 px. They now keep their size and have accessible names; the Topic "Explore" button is
  translated (it was Vietnamese in English mode) and no longer wraps.
- Phase B: B2 is done locally (FQC-INTERVENTIONS-664): intervention ledger by category and decision ownership, with a
  record route for interventions the app cannot see. B5 (FQC-QUALIFICATION-664): per-criterion scoring from measured
  campaign evidence; the objectives file changes only through it. B1 (frozen case suite) waits for the owner's domain;
  B3 (FQC-FAULTS-664): 5 automated planted faults, each caught by its detector; 4 faults are campaign-only and never
  counted. B4 (FQC-CONTINUITY-664): snapshot/compare across real restarts, duplicate-run and leakage checks. Phase B
  is complete except B1, which needs the owner's domain and budget.
- B1 is done locally (FQC-SUITE-664): devtools/qualification/cpu-ml-v1, frozen (suite-digest.txt), 4 cases with fixed
  generated data (held-out sets for the open cases), budgets and stopping rules; campaign_template feeds B5.
  Phase B is complete locally.
- CI on f1b2607 (repair 1): the suite digest file was written with CRLF on Windows and committed as LF; its `.sha256`
  suffix is not line-ending-normalised by the source fingerprint, so the local receipt and CI hashed different bytes.
  The file is now suite-digest.txt (normalised), written with LF.

| ID | Change | Criteria |
|---|---|---|
| A1 | Long tools return a job id and are polled (`sandbox_run_code`, experiments, discovery): no 502 through the CLI container proxy | RQ-10, RQ-07 |
| A2 | Governed execution of agent-written code: `experiment.run` accepts an agent protocol (code digest + pinned environment), frozen, approved, then `experiment.verify`, instead of only the built-in denoising protocol | RQ-04, RQ-05, RQ-08 |
| A3 | The agent can create/open its native code project and edit existing files as versioned patches (no new folder per run) | RQ-04, RQ-06 |
| A4 | Dependency installs honour pins, venv without `--system-site-packages`, one install per venv at a time | RQ-05 |
| A5 | Tool descriptions state the host OS and shell | RQ-10 |
| A6 | Library tools for the agent (list Topic library, fetch paper text). PaperOrchestra receives library and experiment evidence. Strip agent preambles. Gates reject empty or non-manuscript sections. Compile LaTeX to PDF (bundled engine) | RQ-03, RQ-12 |
| A7 | Discovery keeps partial results when one provider is rate limited (429) | RQ-03 |
| A8 | Missions panel refreshes live. The selected Topic survives a reload. Narrow-drawer layout fixes | RQ-07 |
| A9 | Harness: compile the canvas into a governed `MissionSpec` so agent and research nodes run through the mission runtime. The agent proposes the team (roles, tools, prompts), validated by `teams.validate`. Each team agent is bound to a model from the app's current model list (Settings → Models & AI connections, including `cli:codex` and `cli:claude_code`), never a hidden or hardcoded model; an unavailable model is shown as such, never silently swapped. Fix the dead button and the English-mode texts. Decide the default of the team flags (owner) | RQ-14, RQ-13, RQ-10 |
| A10 | Warn about long Windows data paths (WinError 206) | — |
| A11 | Approval digests normalise line endings (CRLF vs LF) | RQ-08 |
| A12 | `/api/tools` takes about 1 s per call (the other AI tools requests take about 5 ms): cache or index the registry listing, invalidated when a tool changes. Found by the 6.6.4 gate | RQ-10 |

## Phase A-QA: Playwright for the four L1–L4 flows in CI/CD (owner request 2026-10-28)

Progress 2026-10-28: items 1, 2 and 4 are done locally (FQC-AUTONOMY-QA-664, evidence `docs/qa/evidence/autonomy-qa-664/`).
Five defects the specs found are fixed. Item 3, the live model part with Codex, comes with A9.

Split each flow into a deterministic part that runs on every CI run and a model part that runs in live qualification. Nothing is skipped and nothing is faked.

1. **New `frontend/e2e/autonomy_levels.spec.ts`, `needs_model: false`, in the routine `pr` and offline CI.** One test per level, through the real UI (Missions → Workflows L1–L4) and the real backend, using deterministic capabilities only:
   - **L1:** draft → `paper.inspect` → accept each answer. A forbidden capability is rejected.
   - **L2:** approved tool execution with per-result review. Reject and accept both change state.
   - **L3:** approved DAG runs. Final human review and exception handling are required. Cancel and retry behave.
   - **L4:** bounded technical closure with `experiment.run` (CPU protocol) → independent `experiment.verify` → `mission.report`. Scientific review stays pending.
   - Each level also checks that an invalid draft does not launch a task and that the result evidence links resolve.
2. **New `frontend/e2e/harness_levels.spec.ts`, `needs_model: false`.** Harness Studio at L2/L3/L4: generate, load, validate and run.
   - Until A9 lands, it asserts the honest `blocked` state.
   - After A9, it asserts that the canvas compiles to a mission and that control-flow, approval and gate nodes behave.
   - It also runs the uiAudit rules on the Team and Architect tabs, which would have caught the English-mode defects.
3. **The model parts stay `needs_model: true`.**
   - `workflows.spec.ts` (local inference in L1–L4) and the A9 agent-team run go into the owner-run live qualification suite.
   - Their evidence is published through `research-live.yml`, because GitHub runners have no model.
4. **CI wiring.**
   - Add both new specs to `uat_config.json` journeys with `needs_model: false` so `--offline-all` selects them.
   - Keep them inside the 900 s per-invocation browser budget, splitting into their own invocation like `2d-audit` if needed.
   - Extend `tests/test_dynamic_discovery.py` so CI fails if they are not selected.

## Phase B: qualification tooling (measurement, not claims)

| ID | Change | Criteria |
|---|---|---|
| B1 | Frozen case suite in one declared computational domain: guided and open-ended cases, held-out questions, fixed data, model/provider versions, budgets and stopping rules chosen before running | RQ-13, RQ-01 |
| B2 | Intervention ledger: who decided each hypothesis, branch, rejection, replan and stop, kept separate from authorization, routine verification, rescue and exception handling | RQ-14 |
| B3 | Fault injection set: omitted method component, wrong metric, leakage, stale/contradictory memory, poisoned source or skill, provider failure, interrupted run, unsupported conclusion | RQ-08, RQ-07 |
| B4 | Long-work continuity: N turns and M process restarts per case without lost requirements, duplicate experiments or cross-project leakage | RQ-07 |
| B5 | Per-criterion scoring with evidence links. `research-quality-objectives.json` changes only from measured results | all |

## Phase C: qualification campaign (after A and B, owner-approved budget)

- Run the frozen suite with a real agent (Codex and/or Claude Code CLI), every attempt recorded, denominators reported.
- Include null and negative results.
- Keep scientific review and publication as human steps.
- Claim scoped L3 only if every critical criterion qualifies.

## Owner decisions

- 2026-10-28: Harness team agents use models from the current model list. Codex and Claude both have quota; **use
  Codex (`cli:codex`, ChatGPT sign-in) for the live tests** of the agent team and the L1–L4 model parts.
  Claude Code stays available in the list as an alternative.

- 2026-10-29: domain = small CPU-scale ML (calibration / robustness of small classifiers); campaign budget = 4 cases
  (2 guided, 2 open-ended), 40 turns and 2 restarts per case, about 2 hours per case, Codex; `research_os.team_enabled`
  stays off by default (opt-in in Missions). Phase A order followed as proposed.

Still open: none for 6.6.4. Phase C (the campaign itself) runs after the release.

## Release rules

Development happens on `dev`. A full local gate and the CI checks must pass, with no skipped tests. The CI time limits are 1.5× since 6.6.3. Promotion goes through protected PRs, and the release must ship a .exe and a .deb.
