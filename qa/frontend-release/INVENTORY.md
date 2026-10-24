# Frontend Component & State Inventory — PhD Research Lab OS

## 1. Screens & Main Stage Views (`activeTab`)
| View / Component | File | State Source | Critical UI Actions | Endpoints Called |
|---|---|---|---|---|
| Chat Center | `src/features/chat/ChatCenter.tsx` | `uiStore.activeSessionId` | Send prompt, stop generation, switch model, reasoning effort, slash autocomplete | `GET/POST /api/chat`, `POST /api/chat/sessions`, `DELETE /api/chat/sessions/{id}` |
| Agent Status & 3D Lab | `src/features/agent-status/AgentStatusView.tsx` | `uiStore.officeFullscreen`, `selectedLabObject` | Filter agents, inspect agent, toggle 3D camera presets, switch lighting, click 3D stations | `GET /api/config`, `GET /api/papers`, `GET /api/library`, `GET /api/research/topics` |
| Workstream Monitor | `src/features/workstreams/WorkstreamMonitor.tsx` | `uiStore.activeTopicId` | Filter workstream partitions, pause/resume execution, view dependency edges | `GET /api/workstreams`, `POST /api/workstreams/{id}/pause`, `POST /api/workstreams/{id}/resume` |
| Missions & DAG | `src/features/missions/MissionLiveWorkspace.tsx` | `uiStore.activeTopicId` | Generate mission DAG, inspect task nodes, approve/reject mission execution | `GET/POST /api/missions`, `POST /api/missions/{id}/approve`, `POST /api/missions/{id}/reject` |
| Evidence & Ledger | `src/features/evidence/EvidenceReview.tsx` | `uiStore.activeTopicId` | Verify cryptographic hash, resolve finding disputes, approve evidence artifact | `GET /api/evidence`, `POST /api/evidence/{id}/resolve` |
| Review & Canonical | `src/features/review/ReviewView.tsx` | `uiStore.activeTopicId` | Approve peer review, save canonical output revision, handle 409 conflict | `GET/POST /api/review`, `POST /api/canonical/output` |
| Research Topics | `src/features/research-topics/TopicView.tsx` | `uiStore.activeTopicId` | Create research topic, switch active topic, view linked missions/papers | `GET/POST /api/research/topics` |
| Library & Papers | `src/features/library/LibraryPanel.tsx` | `uiStore.project` | Search references, upload PDF, view full metadata modal, in-app PDF preview, open external tab | `GET /api/library`, `GET /api/papers`, `GET /api/library/file/{name}`, `POST /api/library/upload` |
| OpenCode Studio | `src/features/opencode/OpenCodePanel.tsx` | `uiStore.project` | Parallel code cores, file explorer, diff editor, execute script | `GET/POST /api/code/run`, `GET /api/code/files` |
| Intelligence Hub | `src/features/intelligence/IntelligenceHubPanel.tsx` | `uiStore.project` | Semantic memory search, knowledge graph visualization, prune cache | `GET /api/memory`, `POST /api/memory/query` |
| Figure Studio | `src/features/figures/FigureStudioPanel.tsx` | `uiStore.project` | Generate scientific figures, prompt modifier, export SVG/PNG | `GET/POST /api/figures` |
| Dashboard & Metrics | `src/features/dashboard/DashboardView.tsx` | `uiStore.project` | View token usage, cost analytics, model health, system resource stats | `GET /api/metrics`, `GET /api/status` |
| Outline & Papers | `src/features/workspace-tools/OutlinePaperCodePanels.tsx` | `uiStore.project` | Outline generator, LaTeX editor, code workspace tabs | `GET /api/outline`, `POST /api/outline/save` |

## 2. Shell & Persistent Navigation
| Component | File | Responsibilities | Critical Interactions |
|---|---|---|---|
| AppShell | `src/shell/AppShell.tsx` | Core layout container, sidebar-stage-drawer orchestration, zoom/scale shortcuts | Zoom scale handler (Ctrl++/Ctrl+-/Ctrl+0), keyboard navigation |
| Header | `src/shell/Header.tsx` | Top breadcrumbs, active topic/project indicator, notification bell, settings button, language toggle, theme toggle | Project switch trigger, settings trigger, drawer toggle |
| Sidebar | `src/shell/Sidebar.tsx` | Pinned conversations, recent sessions, folder groups, new chat button, session context menu (pin, rename, delete, archive) | Create chat, pin/unpin session, context menu actions without duplication |
| ContextualDrawer | `src/shell/ContextualDrawer.tsx` | Right-side contextual drawer for quick tool inspections | Toggle open/close, switch active inspector tab |

## 3. Modals & Overlays
| Modal | File | Purpose |
|---|---|---|
| SettingsModal | `src/features/settings/SettingsModal.tsx` | Language selection (VI/EN), AI provider assignment, Model selector filtered by vendor, Subscription option, Autonomy rules |
| ProjectSwitcher | `src/features/projects/ProjectSwitcher.tsx` | Switch active research project, create project with custom `data_dir` and `references_dir` |
| LibraryPaperModal | `src/features/library/LibraryPanel.tsx` | Full paper metadata popup, KaTeX markdown abstract, BibTeX snippet, in-app embedded PDF viewer, open in new tab |

## 4. State & Infrastructure
- `src/shared/state/uiStore.ts`: Central Zustand store controlling project, topic, session, activeTab, drawer, office 3D mode, scale, language.
- `src/shared/api/client.ts`: Unified HTTP client supporting GET, POST, PUT, DELETE with error normalization and Bearer token / CSRF support.
- `src/shared/events/eventAdapter.ts`: SSE event multiplexer connecting to `/api/events/live`.
- `src/shared/i18n/index.ts`: React-i18next bilingual configuration for English (`en`) and Vietnamese (`vi`).
- `src/shared/ui/MarkdownRenderer.tsx`: Secure Markdown rendering with KaTeX math equation support and syntax-highlighted code blocks with copy button.
