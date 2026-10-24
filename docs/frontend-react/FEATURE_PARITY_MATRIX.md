# Feature Parity Matrix — PhD Research Lab React Migration

**Version:** 6.3.0-preview.1 → React Modernization  
**Status:** M0 Baseline Defined

| Legacy Screen / Surface | Old File / Function | React Component Target | API Endpoint / Source of Truth | Verification Test | Parity Status |
|---|---|---|---|---|---|
| **App Shell & Layout** | `index.html`, `layout.js`, `app.css` | `src/shell/AppShell.tsx`, `Sidebar.tsx`, `Header.tsx` | Local state + `GET /api/config` | `test:e2e` / `AppShell.test.tsx` | Planned M1 |
| **Project Switcher & Modal** | `main.js:projectMenu`, `newProject` | `src/features/projects/ProjectSwitcher.tsx` | `GET /api/projects`, `POST /api/projects/activate` | `pins-projects.test.js` / Unit | Planned M1 |
| **Chat Center & Messages** | `chat.js:open`, `renderMessage` | `src/features/chat/ChatCenter.tsx`, `MessageList.tsx` | `GET /api/chat/sessions/{sid}`, `POST .../turns` | `chat.test.js` / RTL | Planned M2 |
| **Streaming & Reconnect** | `core.js:stream`, `chat.js:stream` | `src/shared/events/useSessionStream.ts` | `GET /api/chat/sessions/{sid}/stream` (SSE) | `streaming.test.ts` | Planned M2 |
| **Sticky Composer & Slash** | `chat.js:renderComposer`, `slashMenu` | `src/features/chat/Composer.tsx`, `SlashMenu.tsx` | `GET /api/skills`, `POST /api/chat/sessions` | `chat.test.js` | Planned M2 |
| **Contextual Drawer Base** | `panels.js:open`, `close`, `layout-grip` | `src/shell/ContextualDrawer.tsx` | `Zustand` UI store + resize listener | `panels.test.js` | Planned M3 |
| **Topic Selector & Inbox** | `research.js:renderTopics`, `renderCorpus` | `src/features/research-topics/TopicView.tsx` | `GET /api/research/topics`, `.../papers` | `research-workspace.test.js` | Planned M3 |
| **Curated Library & PDF** | `panels.js:library`, `tools.js` | `src/features/library/LibraryPanel.tsx` | `GET /api/library`, `POST /api/library/upload` | `v51.test.js` | Planned M3 |
| **Paper Writer & LaTeX** | `panels.js:paper`, `review.js` | `src/features/paper/PaperPanel.tsx` | `GET /api/paper/sections`, `POST .../compile` | `panels.test.js` | Planned M4 |
| **Code & VS Code Bridge** | `panels.js:code` | `src/features/code/CodePanel.tsx` | `GET /api/code/projects`, `POST .../vscode` | `panels.test.js` | Planned M4 |
| **Dashboard & Resources** | `dashboard.js` | `src/features/dashboard/DashboardView.tsx` | `GET /api/dashboard`, `GET /api/models` | `dashboard.test.js` | Planned M4 |
| **Settings & Providers** | `settings.js` | `src/features/settings/SettingsModal.tsx` | `GET /api/config`, `PUT /api/config` | `settings.test.js` | Planned M4 |
| **Mission Builder (Form+DAG)** | `research.js:renderMissions` | `src/features/missions/MissionBuilder.tsx` | `POST /api/research/topics/{tid}/missions` | `test_missions.py` + Vitest | Planned M4 (Remediates F07) |
| **Mission DAG Visualizer** | (None — was raw JSON) | `src/features/missions/MissionDAG.tsx` (React Flow) | `GET /api/research/topics/{tid}/missions` | Vitest + RTL | Planned M4 (Remediates F04) |
| **Mission Task Inspector** | (None — was raw JSON) | `src/features/missions/TaskInspector.tsx` | `GET .../missions/{mid}` | Vitest + RTL | Planned M4 (Remediates F06) |
| **Team Monitor & Roles** | `research.js:renderTeams` | `src/features/team/TeamMonitor.tsx` | `GET .../team`, `POST .../replan` | `test_teams.py` | Planned M4 |
| **Workstream Monitor & Swimlanes** | `research.js:renderWorkstreams` | `src/features/workstreams/WorkstreamMonitor.tsx` | `GET .../workstreams`, `POST .../handoffs` | `test_workstreams.py` | Planned M4 (Remediates F02, F05) |
| **Canonical Output CAS** | `research.js:375` (broken) | `src/features/workstreams/CanonicalOutputModal.tsx` | `POST .../outputs` (dynamic `expected_revision`) | Vitest CAS conflict test | Planned M4 (Remediates F03) |
| **Scientific Evidence & Claims** | `research.js:renderClaims` | `src/features/evidence/EvidenceReview.tsx` | `GET .../claims`, `POST .../claims/{cid}/decision` | `research-controls.test.js` | Planned M4 |
| **AI Agent Status: 2D List** | (New unified view) | `src/features/agent-status/AgentStatusList.tsx` | `GET /api/research/os-settings`, missions snapshot | Vitest | Planned M4 (Remediates F08) |
| **AI Agent Status: Timeline** | (New unified view) | `src/features/agent-status/AgentTimeline.tsx` | Event bus `/api/events/stream` | Vitest | Planned M4 |
| **AI Agent Status: 3D Office** | (New optional view) | `src/features/agent-office-3d/OfficeCanvas.tsx` | Normalized `AgentOfficeViewModel` (read-only) | R3F test / 2D fallback | Planned M5/M6 (Lazy loaded) |
| **Provider Telemetry & Quota** | (None) | `src/features/providers/ProviderUsageCard.tsx` | Measured tokens or "Not reported" | Vitest | Planned M4 (Remediates F09) |
