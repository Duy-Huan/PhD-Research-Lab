# Backend Contracts & Telemetry Protocol

**System:** PhD Research Lab  
**Backend:** FastAPI 0.150.0 / Starlette 1.9.0 / Pydantic v2  
**Audited Routes:** 198 paths across 14 routers  
**Date:** 2026-10-23

---

## 1. Multiplexed Event Bus & SSE Transport

The backend provides two primary Server-Sent Events (SSE) streaming channels:

### 1.1 Global Application Event Bus: `GET /api/events/stream`
- **Controller:** `backend.core.bus`
- **Headers:** `Last-Event-Id: <seq>` (supports resumption from monotonic sequence number)
- **Event Schema:**
  ```json
  {
    "seq": 104,
    "ts": 1729700000.123,
    "type": "api.mutation | aiws.update | run.status | outline.updated | config.saved | research.mission",
    "client": "ui | cli | \"\"",
    "mission_id": "optional string",
    "session_id": "optional string",
    "run_id": "optional string"
  }
  ```
- **Lifecycle & Bus Invariants:**
  - Emitted whenever any POST/PUT/PATCH/DELETE completes under `/api/`.
  - In-memory ring buffer (per process); gaps trigger authoritative snapshot reconciliation.

### 1.2 Session Chat Stream: `GET /api/chat/sessions/{sid}/stream`
- **Controller:** `backend.api.chat:events_stream`
- **Headers:** `Last-Event-Id: <sid>:<seq>`
- **Event Types:**
  - `chunk`: incremental markdown text fragment (`{ "type": "chunk", "text": "..." }`)
  - `activity`: agent step or tool notice (`{ "type": "activity", "label": "..." }`)
  - `tool`: tool invocation (`{ "type": "tool", "name": "...", "status": "running|done" }`)
  - `approval`: requires human approval (`{ "type": "approval", "id": "...", "kind": "..." }`)
  - `done`: turn complete (`{ "type": "done" }`)
  - `stream.timeout`: periodic keep-alive (`{ "type": "stream.timeout", "seq": 12 }`)

### 1.3 Run Stream: `GET /api/runs/{rid}/stream`
- **Controller:** `backend.api.runs:runs_stream`
- Emits background research run logs, step transitions, and completion states.

---

## 2. Research OS & Mission Contracts

Defined in `backend/agent/mission_contracts.py` & `backend/api/research.py`:

### 2.1 OS Settings Contract: `GET /api/research/os-settings`
```typescript
export interface OSSettings {
  enabled: boolean;
  team_enabled: boolean;
  multi_team_enabled: boolean;
  experimental: boolean;
  max_parallel_tasks: 1; // Strict serial scheduler invariant
}
```

### 2.2 Mission Spec & Plan Review Contract
```typescript
export interface MissionSpec {
  topic_id: string;
  objective: string;
  permissions: Array<"network" | "workspace_write" | "reasoning" | "compute">;
  tasks: Array<{
    id: string;
    capability: string;
    depends_on?: string[];
    preferred_engine?: string;
    fallback_engines?: string[];
    arguments?: Record<string, unknown>;
  }>;
  control?: {
    priority?: number;
    end_date: string;
    allowed_engines: string[];
    allow_api_billing?: boolean;
    app_backend?: string;
    app_model?: string;
    charter_id?: string;
    charter_digest?: string;
    success_criteria?: string[];
  };
  collaboration?: {
    rationale: string;
    workstreams: Array<{
      id: string;
      objective: string;
      task_ids: string[];
      lead_role: string;
    }>;
  };
}
```

### 2.3 Mission Approval & Digest Verification
- `POST /api/research/topics/{tid}/missions/{mid}/approve`
  ```typescript
  export interface MissionApprovalRequest {
    plan_digest: string; // Must match server sha256 digest of spec exactly
    note: string;
    expires_minutes?: number; // default 60
  }
  ```
- If the plan was edited, `plan_digest` changes. Approving an outdated digest returns `400 Digest Mismatch`, preventing stale execution.

### 2.4 Workstreams & Canonical Output Compare-And-Swap (CAS)
- `POST /api/research/topics/{tid}/missions/{mid}/outputs`
  ```typescript
  export interface CanonicalOutputCASRequest {
    team_id: string;
    key: string;
    source_task: string;
    artifact_index: number;
    expected_revision: number; // Must be actual current revision, NOT hardcoded 0
    note: string;
  }
  ```
- **Error Condition:** Returns `409 Conflict` if the output key was mutated concurrently. Frontend prompts user with fresh revision diff and requires confirmation.

---

## 3. Normalized 3D Agent Office View Model

The 3D office and 2D status monitors consume a single canonical view model adapted from live mission events and snapshots:

```typescript
export type AgentPresence =
  | 'queued'
  | 'running'
  | 'idle'
  | 'awaiting_approval'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'rate_limited'
  | 'disconnected'
  | 'unknown';

export type AgentActivity =
  | 'reading'
  | 'writing'
  | 'executing'
  | 'searching'
  | 'training'
  | 'reviewing'
  | 'reporting'
  | 'none'
  | 'unknown';

export interface AgentOfficeViewModel {
  agentId: string;
  sessionId?: string;
  missionId?: string;
  taskId?: string;
  projectId: string;
  topicId?: string;
  teamId?: string;
  displayName: string;
  role: string;
  engine: string;
  presence: AgentPresence;
  activity: AgentActivity;
  lastObservedAt: string;
  sourceEventId?: string;
  canInspect: boolean;
  canPause: boolean;
  canResume: boolean;
  hasApprovalRequest: boolean;
}
```

**Truthful Presentation Invariant:**
- Only ONE agent can be `running` at any moment in production, because `max_parallel_tasks: 1`.
- Any task without an admitted active attempt is `queued` or `idle`.
- External sync sessions (OpenScience/Feynman) are labeled `last synced`, never animated as typing.
- All credential keys and private chain-of-thought tokens are stripped at backend and client boundaries.
