# M0 — Baseline Repository and Architecture Audit

**Target:** `Duy-Huan/PhD-Research-Lab`  
**Audited Baseline Version:** `v6.3.0-preview.1`  
**Date:** 2026-10-23  
**Status:** COMPLETE (M0 Baseline Frozen)  
**Rule:** DO NOT COMMIT TO GIT (per explicit user instruction)

---

## 1. Executive Summary & Verification Findings

An exhaustive source audit of `Duy-Huan/PhD-Research-Lab` was conducted directly against the local checkout:

1. **Current Runtime & Language Stack:**
   - **Backend:** Python 3.14.8 running FastAPI on localhost (`127.0.0.1:8765`), ASGI with `MutationMiddleware`, `_NoStaleUI`, and `_LocalHostOnly` DNS-rebinding protection.
   - **Frontend:** Vanilla JavaScript (ES6+), DOM builder `PL.h`, global namespace `window.PL`, fetch wrappers in `core.js`, hash router in `main.js`, layout/panels in `panels.js`, chat in `chat.js`, research harness in `research.js`.
   - **Node.js Environment:** Node v24.22.0, npm 11.19.1.
   - **Automated Tests:** 29 core Python tests in `tests/test_missions.py`, `tests/test_teams.py`, `tests/test_workstreams.py` pass in 17.6s; 150 frontend jsdom tests in `tests/frontend/` pass in 9.9s; Research Harness v6.3 verification script (`tools/verify_v6_harness.py --stage 6.3`) passes 100% of checks (8 missions, 8 task artifacts, 20 trials, 480 raw samples, 151 audit events, 10 handoffs, 10 receipts).

2. **v6.4.x Implementation Status (Truthful Verification):**
   - **v6.4.0 Figure Studio:** Spec in `upgrade/`, NOT implemented in backend. Must be feature-gated and honestly reported as "Not yet implemented in backend".
   - **v6.4.1 OpenCode Parallel Core:** Spec in `upgrade/`, NOT implemented in backend.
   - **v6.4.2 Unified Research Intelligence & 3D Agent Office:** Spec in `upgrade/`, frontend migration target.
   - **Worker Concurrency:** Strictly `max_parallel_tasks: 1` in `backend/api/research.py:43` and `backend/agent/missions.py`. Multi-team and workstreams are logical roles scheduled over a serial execution worker. UI must never animate multiple concurrent typing agents.

3. **Critical Audit Gaps Identified (F01–F10 Closure Targets):**
   - **F01 (Live State Loop):** `research.js` did not subscribe to `PL.bus` for mission/team/workstream updates; required manual user click on "Refresh". Fixed via unified SSE / bus subscription.
   - **F02 (Lifecycle Coverage):** Missing UI visibility for dispute creation, findings, handoff auto-acknowledgments.
   - **F03 (Canonical Output CAS Bug):** Line 375 of `research.js` hardcodes `expected_revision: 0`, breaking outputs when revision advances. Fixed with dynamic revision tracking and 409 conflict handling.
   - **F04 (Mission DAG):** Only raw JSON `<pre>` blocks existed. Needs React Flow visual DAG with accessible table fallback.
   - **F05 (N+1 Query in Workstreams):** Lines 367–369 loop over all missions making sequential `PL.get(url + "/workstreams")` requests. Fixed via lazy on-demand inspection and pagination.
   - **F06 (Scientific Data Navigation):** Raw JSON dump replaced with structured evidence/claim/artifact cards.
   - **F07 (Composition UX):** Replaced raw JSON textareas with typed, constraint-aware form builders and an expert-mode JSON toggle.
   - **F08 (Serial Scheduling):** Real `max_parallel_tasks: 1` surfaced truthfully in Agent Status.
   - **F09 (Provider Telemetry):** `provider_usage` is `None` in backend; UI must render "Not reported / Unavailable" rather than fabricating zero tokens or fake costs.
   - **F10 (Slash Commands):** Connected slash commands (`/mission`, `/team`, `/workstreams`, `/claims`, etc.) directly to typed draft proposals in chat.

---

## 2. Inventory of Frontend Assets & Build Pipeline

```
frontend/
├── index.html                   (FastAPI entrypoint, versioned link injection)
├── assets/
│   ├── app.css                  (CSS variables: --bg, --panel, --side, --ink, etc.)
│   ├── appearance-init.js       (Theme & font bootstrap)
│   ├── chat.js                  (Chat composer, streaming, history, slash menu)
│   ├── core.js                  (PL global, DOM h(), fetch API, event bus, markdown)
│   ├── dashboard.js             (Dashboard view, system resources, VRAM)
│   ├── i18n.js, i18n-en.js      (Localization en/vi)
│   ├── layout.js                (Resizable split panes, keyboard handling)
│   ├── main.js                  (App boot, project switcher, hash routing)
│   ├── panels.js                (Side drawer for library, outline, paper, code)
│   ├── research.js              (Topics, corpus, missions, workstreams, protocols, claims)
│   ├── review.js                (Paper review interface)
│   ├── settings.js              (Settings modal, providers, models, appearance)
│   ├── themes.js                (VS Code & custom theme imports)
│   ├── tools.js                 (Charts, exports, notes, figure helpers)
│   └── ui-locales.js            (Translation dictionary)
├── img/                         (Logos, favicons)
└── vendor/                      (Offline libraries: marked, DOMPurify, highlight.js, KaTeX, mermaid)
```

**FastAPI Serving Contract in `backend/app.py`:**
- `app.mount("/assets", StaticFiles(directory="frontend/assets"))`
- `app.mount("/vendor", StaticFiles(directory="frontend/vendor"))`
- `app.mount("/img", StaticFiles(directory="frontend/img"))`
- `_page()` reads `frontend/index.html` and injects `?v={APP_VERSION}` into asset links.
- `start.py` requires all existing frontend asset files in `REQUIRED_FILES`. **Invariance rule:** Existing assets must remain intact or bridged to pass `python start.py --check`.

---

## 3. Full API Route & Capabilities Map

FastAPI exposes **198 endpoint paths across 14 APIRouters**:
1. `system.router` — `/api/config`, `/api/models`, `/api/providers`, `/api/dashboard`, `/api/events`, `/api/events/stream`
2. `projects.router` — `/api/projects`, `/api/outline`, `/api/projects/activate`, `/api/projects/conversations`
3. `chat.router` — `/api/chat/sessions`, `/api/chat/sessions/{sid}`, `/api/chat/sessions/{sid}/stream`, `/api/chat/sessions/{sid}/approvals/{aid}`
4. `runs.router` — `/api/runs`, `/api/runs/{rid}/stream`, `/api/runs/{rid}/cancel`, `/api/runs/{rid}/retry`
5. `memory.router` — `/api/memory/proposals`, `/api/memory/proposals/{pid}/accept`, `/api/memory/pins`
6. `code.router` — `/api/code/projects`, `/api/code/vscode`, `/api/code/experiments`
7. `library.router` — `/api/library`, `/api/library/upload`, `/api/library/{id}/bibtex`
8. `paper.router` — `/api/paper/sections`, `/api/paper/compile`, `/api/paper/export`
9. `review.router` — `/api/review/sessions`, `/api/review/venues`
10. `mcp.router` — `/api/mcp/servers`, `/api/mcp/tools`
11. `plugins.router` — `/api/plugins`, `/api/plugins/install`
12. `compute.router` — `/api/compute/resources`, `/api/compute/gpus`
13. `research_engines.router` — `/api/research-engines/status`
14. `research.router` (77 routes) — Topics, Missions, Charters, Teams, Workstreams, Handoffs, Canonical Outputs, Disputes, Protocols, Claims, Citations, Audit.

---

## 4. Security & Isolation Boundaries

- `_LocalHostOnly` Middleware: Enforces `Host: localhost / 127.0.0.1 / ::1 / testserver`. Rejects external DNS rebinding. Enforces origin checks on all mutating methods (`POST`, `PUT`, `PATCH`, `DELETE`).
- `Vite Dev Proxy`: When developing with Vite on `localhost:5173`, the proxy forwards to `127.0.0.1:8765` with `Host: 127.0.0.1` and `Origin: http://127.0.0.1:8765`, preserving security gates.
- No Credentials in Telemetry: API keys and CLI credentials are never transmitted in telemetry or event streams.

---

## 5. Rollback Route & Dual-Serving Strategy

- Production build placed in `frontend/dist/`.
- If `frontend/dist/index.html` exists and `?legacy=1` is not set, FastAPI serves the compiled React app.
- If `?legacy=1` is provided or if `frontend/dist/` is removed, FastAPI seamlessly serves the original `frontend/index.html`.
- Zero user data risk: user data in `data/` and `projects/` is completely preserved.
