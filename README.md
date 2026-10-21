# PhD Research Lab - v5.0.0

A local research workspace with one project chat, a browser interface and a terminal client sharing the same FastAPI backend. Research and Reviewer agents use Markdown skills; a utility model handles background extraction and memory work.

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

## Literature, web search and library

Open the Library search panel, enter a topic and select academic papers, web pages or both. Results combine OpenAlex, arXiv, Semantic Scholar, IEEE discovery and the selected web engine. Each source can fail independently; errors and setup requirements are reported with the remaining results.

Configure search in **Settings → Research providers**:

| Service | Configuration |
|---|---|
| Web search | DuckDuckGo, or your Tavily/Brave API key |
| IEEE Xplore | Your IEEE API key for metadata search; otherwise indexed IEEE web discovery |
| Google Scholar | Your SerpAPI key; the panel also offers a direct Scholar search link |
| OpenAlex / Semantic Scholar | Optional API keys for the service/account's available access |
| Journal ranking | Import a SCImago CSV and specify its ranking year |

Save a result directly into the library. Open-access PDFs are downloaded when available; a metadata-only entry is retained when a PDF is unavailable. Search results are deduplicated by DOI or normalized title; library saves recognize an existing DOI or source URL. The library preserves citation metadata and can export BibTeX.

Journal indicators include their source and date/year. SJR and Q1–Q4 are shown only when an imported ranking record matches the journal; OpenAlex citation indicators are displayed separately. Preprints and conference papers do not receive an invented journal quartile. Venue-level indicators are not an assessment of an individual paper's correctness.

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
| `workspace/` | Conversations, outline, proposed artifacts and durable research runs |
| `memory/` | Research state, evidence, retrieval records and raw-page snapshots |
| `code/<name>/` | Separate code projects with their own execution environment |
| `runs/` | Experiment jobs, logs, figures and measured metrics |
| `clearml/` | Optional offline ClearML sessions |

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
.venv\Scripts\python -B tools/backend_regression.py
npm ci --prefix tests/frontend
node tests/frontend/run.js
```

The backend harness isolates all test data and writes logs, JSON/XML/HTML coverage and an exact line-and-branch gate to `artifacts/backend-regression/`. It fails if tests fail, coverage is incomplete, or backend/test sources change during the run. The existing subprocess exclusion for `backend/execution/clearml_worker.py` is explicit in `.coveragerc`.

Windows process-cancellation regressions require permission to terminate the subprocess trees they create. Symlink tests require Developer Mode/admin. Live ClearML, Codex and LM Studio tests are opt-in and are reported as skipped unless configured; mocked integration tests do not establish that a real account is connected. Consult the dated status report for measured results, rather than historical coverage claims.
