# Real Chromium QA & Playwright E2E Regression Report — 2026-10-24

**Test Target**: PhD Research Lab (Full Stack: React 19 Frontend + FastAPI Backend)  
**Testing Framework**: `@playwright/test` + Real Chromium (Engine Revision 1248)  
**Accessibility Engine**: `@axe-core/playwright` (WCAG 2.0, 2.1, 2.2 AA)  
**Inference Engine**: Real LM Studio (`qwen/qwen3.5-9b` on `127.0.0.1:1234`)  
**Backend QA Profile**: `127.0.0.1:8768` (Isolated storage `output/playwright/20261024-live/state`)  
**Frontend QA Profile**: `127.0.0.1:5174/dist/react.html`  
**Regression Status**: **24/24 PASSED (100% Pass Rate across all 5 specs in 1.9m)**

---

## 1. Executive Summary & Test Results Matrix

| Spec File | Tests | Status | Execution Time | Core Scope Covered |
| :--- | :---: | :---: | :---: | :--- |
| `frontend/e2e/harness_ide.spec.ts` | 1 | **PASSED** | 3.9s | Visual Harness IDE: 7 Template Library, Dynamic Team Builder, Node Inspector, AI Architect DAG generation |
| `frontend/e2e/journeys.spec.ts` | 5 | **PASSED** | 22.7s | Real Qwen chat, SSE streaming, message pinning, project memory persistence, cancellation recovery, project isolation, Axe WCAG 2.2 accessibility scan |
| `frontend/e2e/navigation.spec.ts` | 13 | **PASSED** | 18.2s | Studio navigation, main stage views, 3D lab transition, responsive mobile & tablet viewports (1440px, 768px, 390px, 360px) |
| `frontend/e2e/tools.spec.ts` | 3 | **PASSED** | 35.6s | Fail-closed harness execution without fake metrics, Decision Ledger UI & hash chain audit, real Codex CLI execution |
| `frontend/e2e/workflows.spec.ts` | 2 | **PASSED** | 27.7s | Autonomous Missions L1–L4 with real local model inference, CPU benchmark reproduction, draft cancellation & validation |
| **Total Full Regression Suite** | **24** | **PASSED (24/24)** | **1.9m** | **Comprehensive end-to-end real browser verification** |

---

## 2. Autonomous Defect Repairs & Confirmations

### Defect 1: Cascading Failure & Blocked State in Workflow Runtime
* **Symptom**: In multi-step harness workflows, when an upstream benchmark node failed or was blocked due to missing external adapters, downstream tasks still executed or reported inconsistent metrics.
* **Root Cause**: `workflow_runtime.py` and `harness.py` lacked explicit parent dependency (`in_edges_map`) blocked-state propagation.
* **Fix**: Added dependency graph traversal before node execution. If any parent node fails or is blocked, downstream nodes fail closed with `status: "blocked"`, `passed: false`, and empty metrics (`{}`). Overall workflow report returns `status: "blocked"`, `passed: false`.
* **Verification**: Verified in `tools.spec.ts:3:1` (`harness run does not invent evaluation metrics when adapters are unavailable`).

### Defect 2: Missing Topic Ledger Event Route & Empty Hash Chain
* **Symptom**: Navigating to Decision Ledger for a freshly created topic returned 404 or an empty cryptographic hash chain.
* **Root Cause**: `backend/api/research.py` only had `/audit` endpoint; `/topics/{tid}/ledger` was unmapped. Furthermore, `save_topic` in `research_store.py` did not record the initial `topic_created` event.
* **Fix**: Registered `/topics/{tid}/ledger` route and automatically appended `topic_created` event on topic creation.
* **Verification**: Verified in `tools.spec.ts:17:1` (`ledger UI renders actual ledger events and verified API status`).

### Defect 3: Retained Topic Title on Project Switching
* **Symptom**: Switching between projects in `ProjectSwitcher` retained the old topic title in the header `#topic-btn`.
* **Root Cause**: `uiStore.ts` `setProject` function switched `activeProject` without resetting `activeTopic` and `activeTopicId`.
* **Fix**: Updated `uiStore.ts` to reset `activeTopic: null` and `activeTopicId: null` when the project directory changes.
* **Verification**: Verified in `journeys.spec.ts:74:1` (`project create, rename, delete cancellation and switch isolate topics`).

### Defect 4: Accessibility Obscuration in Settings Modal (WCAG 2.2 SC 2.5.8 Target Size)
* **Symptom**: Axe accessibility check flagged a target-size violation on the language switcher buttons (VI / ENG) in the Settings modal header.
* **Root Cause**: `#floating-drawer-toggle` had `position: absolute; top: 14px; right: 0px` which overlapped the rightmost 24px of `.settings-studio-header` when the right drawer was closed.
* **Fix**: Adjusted `.settings-studio-header` padding to `padding: '14px 110px 14px 24px'` to provide safe spacing away from the floating toggle, and added explicit `aria-label` attributes to scale and cloud selects.
* **Verification**: Verified with `AxeBuilder` with tags `['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']` with **0 critical or serious violations** in `journeys.spec.ts:109:1`.

### Defect 5: Misleading "Server stopped" Banner & Stale Process Handling in `run.bat`
* **Symptom**: When running `run.bat` while a server was already running on port 8765, `start.py` opened the browser and exited with code 0, but `run.bat` displayed a false-alarm banner: `Server stopped. If you saw an [ERROR] above, copy this whole window text and send it for help.`
* **Fix**:
  1. Updated `start.py` to support `--restart` (`-r`) and `--stop` (`-s`), with automated PID termination (`kill_process_on_port`).
  2. Updated `run.bat` to check `%ERRORLEVEL%`: exits cleanly on code 0 without displaying the error box.
  3. Added convenient 1-click utility scripts: `restart.bat` and `stop.bat`.

---

## 3. Real Browser Traceability Evidence

* Playwright Trace: `output/playwright/regression/results/*/trace.zip`
* Full Accessibility Scans: `output/playwright/regression/results/*axe-*.json`
* Video Recordings: `output/playwright/regression/results/*/*.webm`
* Screenshots: `output/playwright/regression/results/*/*.png`

---

## 4. Release Decision

* **Regression Pass Rate**: **100% (24/24)**
* **Accessibility**: **Compliant (0 critical/serious WCAG AA violations)**
* **Fail-Closed Safety**: **Verified across all adapters and runtime nodes**
* **Local Inference Integration**: **Verified with real LM Studio and Codex CLI**
