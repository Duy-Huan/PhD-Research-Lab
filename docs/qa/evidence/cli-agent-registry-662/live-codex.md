# Live acceptance: Codex as the PhD Lab agent (2026-10-28)

Owner request: use the owner's Codex (ChatGPT sign-in) as the agent and run the full flow to a paper.
Environment: Windows 11, codex-cli 0.163.0 signed in with ChatGPT, PhD Lab 6.6.2 from a disposable
`PHDLAB_DATA_DIR` (never the real `data/` or `projects/`), all four agent roles set to `cli:codex` in the UI,
Playwright browser with a disposable profile. Screenshots: `output/playwright/mcp/codex-demo-*.png` (local only).

## What worked live

- Chat with `cli:codex` answers through the isolated container (about 40 s per turn).
- After the fix in this change, Codex discovered and called registry tools over MCP
  (`phdlab_tools_search`, `phdlab_tools_describe`, `phdlab_tools_call`), created governed missions and stopped
  for human approval as designed.
- `mission.paper.discover` added 8 real papers (arXiv, Crossref) to the Topic library.
- `mission.code.implement` produced native run `RR-af6b7b95`; after approval Codex wrote `experiment.py`
  (605 lines, ECE self-checks, split digests, pinned requirements), `plot.py` and a README.
- With the new `process` permission granted in Settings, `sandbox_run_code` started the experiment in the
  project's own venv.

## Outcome

- Measured, artifact-verified results (run-3, 30 paired trainings, about 45 s CPU): label smoothing 0.1 raised
  mean test accuracy by 1.2-1.9 points at 10/30/100% data but raised top-label ECE by 0.10-0.13
  (CE 0.016-0.040 vs LS 0.121-0.168). Figure `run-3-figures/accuracy_ece.pdf`.
- A second PaperOrchestra mission, created by the researcher with an objective holding only the verified numbers
  (artifact `art-3860a2d7188dd1e2`), produced a complete English workshop draft (abstract, introduction, related
  work, method, experiments with table and figure, discussion, conclusion) whose numbers match the measurements.
  It has no citations (the writer received no library content), agent-style preambles leaked into sections,
  provenance and figure gates did not pass and no PDF was compiled (no LaTeX). Not submission-ready.

## Defects found and fixed in this change (FQC-CLI-AGENT-REGISTRY-662)

1. CLI agents (Codex, Claude Code) and Hermes in agent mode received only the read-only MCP allowlist: the
   `phdlab_tools_*` meta-tools were never granted, so Hermes' registry access was refused live as well.
2. A Topic chat received no tools at all (topic isolation removed the whole registry, not only project-scope tools).
3. Codex's own bubblewrap sandbox cannot start inside the PhD Lab container: every shell command failed with
   `bwrap: No permissions to create a new namespace`.
4. The agent-mode CLI workspace stayed read-only although the agent profile grants `workspace_write`.
5. The AI tools tab had no toggle for `process` or `reasoning`, so `sandbox_run_code` could never be granted.
6. Gate: two stale assertions (3D roster label, CI fixture without the new installers job).

## Open findings (not fixed in this change)

- `sandbox_run_code` blocks until the run ends; through the Codex container MCP proxy a long call returns
  HTTP 502 while the run continues. Long tools should return a job id and be polled.
- Tool descriptions do not state the host shell: Codex used POSIX `VAR=1 python ...` and `cmd.exe` failed.
- Dependency auto-install ignores pinned versions in `requirements.txt` (matplotlib 3.11.2 for a 3.9.2 pin,
  torch 2.6.0+cu124 for a 2.5.1+cpu pin) and two runs installed into the same venv concurrently.
- The project venv is created with `--system-site-packages` and inherits the interpreter's packages.
- Governed `experiment.run` only executes the built-in denoising protocol; agent-written research code can run
  only through `sandbox_run_code`, outside the protocol/approval chain.
- The agent cannot create or open a native code project; the owner must do it first.
- A discovery job that reaches its limit is marked failed when one provider is rate limited (OpenAlex 429).
- The Missions panel does not refresh when the agent creates a mission; a page reload is needed.
- A page reload drops the selected Topic, so the next chat is not Topic-bound.
- The agent has no registry tool to list the Topic library, so it cannot verify citations itself.
- `gateway.block_source_code` also blocks the agent from reading code it just wrote in its own project.
- Long data paths break Windows DLL loading (WinError 206); the app does not warn about them.
- Narrow drawer layout squeezes the Topic "Explore" button and the Missions header.
- A native coding run cannot edit an existing file: every run writes a new `experiments/<run>/` folder, so
  Codex's one-line fix (`RR-d4f1b600`) became a one-line file. Together with `gateway.block_source_code` the
  agent has no way to iterate on its own code. In this run the QA operator applied that exact line by hand
  (disclosed to the agent and here); the setting was left for the owner to decide.
- Positive: Codex's own self-checks caught a real defect in its code (float32 one-hot vs a 1e-12 tolerance)
  before any training, and its freeze -> separate approval -> run design held.
- The researcher approval file for this demo was written by the QA operator on the owner's explicit request
  and says so in `approved_by`; it is not an owner signature.
- Codex's generated `save_json` writes CRLF on Windows (text mode) and then compares the SHA-256 of that copy
  with the original approval file, so any LF approval fails verification. Run-3 with a CRLF approval passed
  `verify`; run-1 and run-3 produced identical metrics (deterministic).
- `paperorchestra.full_orchestration` writes from the objective text and paper ids only; experiment evidence
  is never passed to the section writer (`write_section(..., "", ...)`), and the agent cannot read
  `metrics.json` under `gateway.block_source_code`, so measured numbers reach the paper only if a human
  pastes them into the objective.
- With `cli:codex` as the research role, the section writer received agent-style context and returned
  approval plans in Vietnamese instead of LaTeX sections (artifact `art-1ce1fbc7cbeb6098`); the quality gates
  still reported citations and consistency as passed with zero citations. Gates must fail on empty or
  non-manuscript sections.
- After an abrupt backend stop, a sandbox job stays `running` forever and the Codex IPC proxy container is left
  running; neither is reconciled on the next start.
- The development host has no LaTeX, so the PDF step can only report that compilation is unavailable.

Test-harness note (not a product defect): moving the disposable data folder mid-session corrupted the copied
Codex home (`Operation not permitted` at start-up); a clean home with only `auth.json` fixed it.
