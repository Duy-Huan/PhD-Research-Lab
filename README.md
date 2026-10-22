# PhD Research Lab - v6.3.0-preview.1

**Upgrade reconciliation (v5.1–v6.3):** [feature audit and operating guide](docs/upgrade-reconciliation.md), [source-linked matrix](artifacts/upgrade-reconciliation/feature-matrix.md) and [executed validation](artifacts/upgrade-reconciliation/validation.md). Adds optional public scholarly source packs, paper tags/filters/citation graph, local hybrid evidence retrieval, read-only local Zotero sync, artifact navigation and fixes for scheduling, charter dependencies and complete Mission reports. The audit preserves explicit preview/external qualification gates.

**UI refinement:** bilingual interface labels, local JSON theme packages (including VS Code color imports), a project/conversation browser, persistent message pins and calendar dates. New Library uploads and downloads share a metadata-based PDF naming convention. See [UI usage and verification](docs/ui-refinement.md) and the [visual audit](docs/ui-refinement-audit.md). `node tests/frontend/run.js` enforces 100% lines, branches and functions across all first-party frontend JavaScript, including first-paint initialization.

A local research workspace with one project chat, a browser interface and a terminal client sharing the same FastAPI backend. Research and Reviewer agents use Markdown skills; a utility model handles background extraction and memory work.

**Supervised Research OS (opt-in):** `/monitor` adds immutable project charters, directed cross-topic report grants, scheduled missions, deadlines, aggregate budgets, explicit provider/billing controls, persisted quota cooldown and a final human review gate. Enable it in Mission Monitor; existing v5 missions retain their behavior. Run `python -B tools/research_harness.py --stage 6.0` for isolated acceptance. See [v6.0 release](docs/release-v6.0.md).

**Team harness (opt-in):** `/team` composes editable single/fixed/adaptive logical roles from registered capabilities, assigns exactly one owner per task and independent deterministic reviewers for scientific outputs. Durable handoffs, quota/recovery controls and bounded replan drafts use the same Mission worker. Benchmark with `python -B tools/research_harness.py --stage 6.2`; see [team architecture and limits](docs/architecture/v6.2_team_composition.md).

**Workstreams (opt-in):** `/workstreams` proposes subordinate team charters for independent branches, with shared mission limits, immutable evidence handoffs, receiving acknowledgments, version-checked canonical output references and PI dispute decisions. Simple work falls back to one team. `python -B tools/research_harness.py --stage 6.3` compares the same three local workflow families against a single adaptive team. See [v6.3 architecture and operations](docs/architecture/v6.3_multi_team_collaboration.md). All new autonomy flags default to false.

**Supervised Missions:** open Topics · SKB → Missions (`/mission`) to create a typed task DAG, review exact permissions/limits and approve its digest before execution. Deterministic capabilities bypass inference; comparisons require an explicitly selected engine and reasoning budget. Interrupted admissions pause for reconciliation. See [v5.4 release and API guide](docs/release-v5.4.md).

**Fixed experiments:** the Experiments drawer (`/experiment`) pre-registers an immutable generated-image denoising protocol, baseline, train/validation/test splits, seeds, MSE/PSNR and compute budgets. Approve the protocol, prepare a mission, then approve that exact execution plan. Native workers measure actual outputs; validation selects a candidate and held-out test is evaluated afterwards. See [v5.5 limits and reproduction](docs/release-v5.5.md).

**Scientific review:** Review Room (`/claims`) links immutable claim revisions to page quotes or measured artifacts, checks source identity and numerical provenance, and records human approval/rejection/retraction in an append-only audit chain. Manuscript exports include claim statuses. Checks certify neither semantic entailment nor novelty; publication still requires human scientific review. See [v5.6 verification matrix and operations](docs/release-v5.6.md).

## Topic knowledge and independent engine workspaces (preview)

Open **Topics · SKB**, create a Topic, then **Open Topic**. The existing chat remains central. The drawer contains a discovery inbox, local paper search with filters/pagination, version/page evidence, OA download jobs, explicit reference curation, native engine folders and a provenance timeline. `/find`, `/topic`, `/workspace`, `/sync`, `/artifacts` and `/jobs` open deterministic controls without model inference. Selected paper/artifact chips enter chat only when you send an AI request.

Topic discovery reuses OpenAlex/arXiv/Semantic Scholar and adds Crossref; Unpaywall uses the contact email in Research providers when configured. Scientific papers live in a separate SQLite corpus and content-addressed PDF store. Importing the old library is explicit and leaves it intact. Downloads do not approve bibliography entries or scientific claims. L4 requires your attestation note. Zotero/CSL JSON import is read-only, and BibTeX exports accepted records only.

Link OpenScience or Feynman folders to a Topic and **Sync Now** after independent work, including work while PhD Lab was closed. File hashes, versions, text excerpts and tombstones are recorded without executing files. Large checkpoints remain metadata-only. OpenScience offers its verified native browser command; Feynman provides the terminal command for interactive use. External sessions/private reasoning remain unobservable through this file bridge. Optional Docling and Optuna adapters do not install dependencies or start research automatically.

This is an incremental preview, not completion of every optional plugin/source in the upgrade catalogs. See [setup, recovery and limitations](docs/v5.3/01_OPERATIONS.md), [the implementation audit](docs/v5.3/00_AUDIT_AND_GAP_ANALYSIS.md) and [acceptance evidence](docs/v5.3/02_ACCEPTANCE.md).

## Start

On Windows, install Python 3.10+ and run `setup.bat`, then `run.bat`. Open the address printed by the launcher (normally `http://127.0.0.1:8765`).

For manual setup:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python start.py
```

VS Code, Git, Ollama/LM Studio, Docker, LaTeX and ClearML are optional integrations. Their availability is shown in Settings. Docker is used for work that requires Linux; normal Python experiments prefer the project's environment.

## Research workflow

1. Create or open a research project. Build its outline from keywords to topic, direction, method and proposal, or attach an existing PDF, Word or Markdown file.
2. Ask a question or type `/` to select a skill such as `/lit`, `/plan`, `/code`, `/run`, `/write`, `/review` or `/verify`.
3. Review proposals and choose Accept or Reject. Code changes, compute and changes to research state follow backend approval rules.
4. Open a code project in VS Code for experiments. Sync results back into the project; background runs keep their steps, events, measured metrics and recovery proposals.
5. Use the dashboard to track current work, pending decisions and pinned results. Review manuscripts in the separate review view.

Context and memory are shared between conversations. Imported papers, external text and provider output retain their source/trust labels. A pin or a citation does not automatically count as verified evidence.

## OpenScience research engine (opt-in preview)

OpenScience runs alongside Feynman through its official Python runtime SDK. Settings exposes Auto, Feynman Only, OpenScience Only and bounded Collaborative modes; `/science` delegates an approved task without copying native scientific skills. The adapter preserves native receipts, streaming cursors, decisions and hash-verified artifacts. It is disabled by default. See the [audit, setup and acceptance guide](docs/openscience-integration.md) and [architecture decision](docs/adr/2026-10-21-openscience.md). Live runtime protocol checks passed on 2.0.152; scientific model workflows and ClearML handoff remain separate acceptance gates.

## Chat tools: charts, figures, notes and export

Answers render Markdown, KaTeX math and three kinds of figures the agents can produce: ```` ```chart ```` (an interactive line / bar / scatter / area plot with error bars, a data table and PNG/SVG download), ```` ```svg ```` (sanitised diagrams) and ```` ```mermaid ```` (flowcharts, loaded on demand from `frontend/vendor/`). The composer's chart button asks the agent for one of them.

Select a passage of an answer and press **Note** (or click a point of a chart) to pin a note to exactly that place. Notes are highlighted and numbered in the answer, listed in the **Notes** panel of the conversation, can be resolved, edited or deleted, and **Send notes to AI** puts all open notes into the next message.

Any answer, or the whole conversation, exports to **PDF, Word (.docx), LaTeX (.tex / .zip with figures), Markdown or HTML**. PDF is printed by the Edge/Chrome already installed (headless); without one the browser's print dialog opens. Every export is also kept in `workspace/exports/` of the project.

## Interface language

**Settings → Appearance & language** switches the interface between Tiếng Việt and English; the agents answer in the same language unless you write in another one. The answer font can be Sans-serif (Segoe UI, recommended for Vietnamese) or Serif (Cambria). Developers: UI strings are wrapped in `PL.t("…")`; `node tools/i18n_wrap.js --check` reports strings without an English entry in `frontend/assets/i18n-en.js`.

## Skill plugins from GitHub

**Settings → Plugin (GitHub)** installs skills from any public repository URL (`https://github.com/owner/repo`, optionally `/tree/<branch>/<folder>`). A snapshot of one commit is stored in `data/plugins/<id>/`; nothing in it is executed. Folders with a `SKILL.md` (Agent Skills format) and PhD Lab skill files in `skills/` become `/` commands. Each project switches plugins and single skills on or off (`<project>/plugins.json`); a plugin skill never replaces a built-in command (a clash is renamed `<plugin>-<name>`). Update re-downloads the branch; removal moves the folder to `data/plugins/_trash/`.

## AI-Scientist-v2 for paper writing

The **Write paper** panel installs [SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) as a plugin. Its prompts are read from the repository source and used with your own models (its GPU tree search and API clients are not run): `/ais-idea` (grant-style ideation), `/ais-review` (NeurIPS review form, scores and Accept/Reject), `/ais-write` (section write-up) and **Write full manuscript** — the ICML or ICBINB LaTeX template filled from the outline, MEASURED and pinned results, project figures and the library bibliography. Citations missing from `references.bib` are removed, the manuscript can be compiled to PDF when TeX is installed, and it always contains a Disclosure paragraph, as the AI Scientist Source Code License requires for machine-generated papers.

## Paper review: revision guide

After the reviewers, the area chair and the issue list, the **Revision guide** tab writes detailed instructions for the authors: a plan ordered by severity, step-by-step fixes for every issue, example revised passages, "done when" criteria, the experiments still needed and a pre-submission checklist. Without a model answer, an automatic guide is built from the issues and proposed fixes. The guide, report, proposed fixes and response letter export as Markdown, PDF, Word or LaTeX. Typing the target venue looks up its CORE rank / SCImago quartile and presets the reviewers' bar.

## Literature, web search and library

Open the Library search panel, enter a topic and select academic papers, web pages or both. Results combine OpenAlex, arXiv, Semantic Scholar, IEEE discovery and the selected web engine. Each source can fail independently; errors and setup requirements are reported with the remaining results.

Configure search in **Settings → Research providers**:

| Service | Configuration |
|---|---|
| Web search | DuckDuckGo, or your Tavily/Brave API key |
| IEEE Xplore | Your IEEE API key for metadata search; otherwise indexed IEEE web discovery |
| Google Scholar | Your SerpAPI key; the panel also offers a direct Scholar search link |
| OpenAlex / Semantic Scholar | Optional API keys for the service/account's available access |
| Venue ranking | Automatic: CORE conference ranks are downloaded and refreshed; a `scimagojr*.csv` saved in Downloads is imported by itself (or import it manually with its year) |

Save a result directly into the library. Open-access PDFs are downloaded when available; a metadata-only entry is retained when a PDF is unavailable. Search results are deduplicated by DOI or normalized title; library saves recognize an existing DOI or source URL. The library preserves citation metadata and can export BibTeX.

Journal indicators include their source and date/year. SJR and Q1–Q4 are shown only when an imported ranking record matches the journal; OpenAlex citation indicators are displayed separately. Conference papers get their CORE rank (A*, A, B, C) when the venue's full title or acronym matches the CORE export exactly; preprints and conference papers never receive an invented journal quartile. **Check rankings** in the Library ranks every saved document from the local data. SCImago blocks automated downloads, so its table is fetched once through your browser (Settings → Research providers → Download SCImago table) and then imported automatically. Venue-level indicators are not an assessment of an individual paper's correctness.

## Models and research providers

Set provider URLs, keys and models in **Settings → Models & agents**. Use the model list and connection test to verify the actual selected endpoint. The chat contains a model picker; provider setup stays in Settings.

API models, LM Studio and Ollama use their configured transports. Codex, Claude Code, Gemini CLI, Antigravity and Feynman use their own installed tools and sign-in flows. An installed CLI can still need authentication or model configuration; the app reports that state. Optional LaTeX and experiment providers are also probed separately.

Local model lifecycle settings control load/unload behavior. Closing the app stops its experiment jobs and, when the configured shutdown policy is enabled, unloads local models.

## Data and upgrades

Global settings live in `data/config.json`; each research project has its own data folder. New projects default to `projects/<name>/` unless another folder is selected. Set `PHDLAB_DATA_DIR` before startup to relocate global data and the default project.

| Project path | Contents |
|---|---|
| `references/` | Library PDFs inside the project's data directory |
| `library.json` | Bibliographic metadata, saved search results and ranking provenance |
| `workspace/` | Conversations (with their notes), outline, proposed artifacts, durable research runs, `exports/`, `paper_ais/` |
| `plugins.json` | Plugins and plugin skills switched on for this project |
| `memory/` | Research state, evidence, retrieval records and raw-page snapshots |
| `code/<name>/` | Separate code projects with their own execution environment |
| `runs/` | Experiment jobs, logs, figures and measured metrics |
| `clearml/` | Optional offline ClearML sessions |

Installed GitHub plugins (`data/plugins/<id>/`) and venue-ranking data (`data/plugins/ranking/`) are shared by every project.

For the default project, PDFs therefore live in `data/references/`. An older root `references/` folder is copied before its default-project pointer is switched; conflicting files stop migration and originals remain intact. Explicit custom reference folders remain supported.

Old curated concepts/methods in `memory/knowledge.json` are imported idempotently into approved project notes. Their complete original records remain attached to the imported notes and the source file is preserved. Existing data should be backed up before upgrading across major versions; legacy endpoints and the former tabbed UI have been replaced by the new API/UI structure.

## Terminal client

Keep the backend running, then launch `phdlab.bat` on Windows or `./phdlab` on Linux/macOS. Without arguments it opens the research chat. The terminal and browser use the same conversations, approvals, runs and project state.

```powershell
.\phdlab.bat
.\phdlab.bat ask "/lit token pruning for edge transformers"
.\phdlab.bat status
.\phdlab.bat providers
.\phdlab.bat runs list
.\phdlab.bat commands
```

See [the CLI guide](docs/CLI.md) and [the current status report](docs/STATUS_2026-10-21.md).

## Development and verification

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -B tools/run_tests.py
.venv\Scripts\python -B tools/backend_regression.py --include-workers --include-entrypoints
npm ci --prefix tests/frontend
node tests/frontend/run.js
```

The backend harness isolates all test data and writes logs, JSON/XML/HTML coverage and an exact line-and-branch gate to `artifacts/backend-regression/`. It fails if tests fail, coverage is incomplete, or application/test sources change during the run. The flags above include the standalone ClearML worker, launcher and stdio bridge. The [full validation report](docs/validation-2026-10-21.md) separates regression success, strict coverage without exclusions, stress evidence and justified integration skips; it does not claim 100% application coverage.

Windows process-cancellation regressions require permission to terminate the subprocess trees they create. Symlink tests require Developer Mode/admin. Live ClearML, Codex and LM Studio tests are opt-in and are reported as skipped unless configured; mocked integration tests do not establish that a real account is connected. Consult the dated status report for measured results, rather than historical coverage claims.

Cloud runtime optimization, capability-aware failover, searchable provider/model settings, terminal chat launcher and the attended remote-compute/ClearML MVP are documented in [the v5.1 runtime audit](docs/cloud-runtime-v51.md), including benchmark evidence and unfinished integrations. Run `chat.bat` once to enter terminal chat; subsequent questions need no `phdlab` prefix.
