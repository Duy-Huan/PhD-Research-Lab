// PhD Research Lab v6.4.2 — Canonical TypeScript Contracts matching backend schemas

export interface Project {
  name: string;
  data_dir: string;
  references_dir?: string;
  created?: string;
  exists?: boolean;
  is_default?: boolean;
  active?: boolean;
  default?: boolean;
}

export interface UIConfig {
  language?: string;
  ai_language?: string;
  theme?: string;
  prose_font?: string;
  paper_explorer_v2?: boolean;
  discovery_inbox?: boolean;
  contextual_actions?: boolean;
  topic_scheduler_ui?: boolean;
  [key: string]: unknown;
}

export interface ProviderSpec {
  label: string;
  kind: string;
  base_url: string;
  model: string;
  key_url?: string;
  models: string[];
  local_gateway?: boolean;
  key_optional?: boolean;
}

export interface ProviderConfig {
  api_key?: string;
  has_key?: boolean;
  model: string;
  base_url?: string;
}

export interface AppConfig {
  hermes?: { enabled: boolean; model: string; deadline_s: number; max_iterations: number; max_tokens: number; free_only: boolean };
  project: Project;
  version: string;
  ui: UIConfig;
  default_cloud: string;
  fallback_to_cloud: boolean;
  lmstudio_base_url: string;
  local_model: string;
  ollama_base_url: string;
  ollama_model: string;
  latex_online: boolean;
  references_dir: string;
  providers: Record<string, ProviderConfig>;
  provider_specs: Record<string, ProviderSpec>;
  agents: Record<string, { label: string; label_en?: string; default: string }>;
  agent_modes: Record<string, string>;
  agent_models: Record<string, string>;
  search: {
    web_engine: string;
    n_results: number;
    mailto: string;
    read_pages: boolean;
    tavily_key?: string;
    has_tavily_key?: boolean;
    brave_key?: string;
    has_brave_key?: boolean;
    s2_key?: string;
    has_s2_key?: boolean;
    openalex_key?: string;
    has_openalex_key?: boolean;
    ieee_key?: string;
    has_ieee_key?: boolean;
    serpapi_key?: string;
    has_serpapi_key?: boolean;
    [key: string]: unknown;
  };
  runs: {
    auto_approve_risk: number;
    max_minutes: number;
    max_retries: number;
    auto_recover: boolean;
    web_search: boolean;
    slot_gpu: number;
    slot_cpu: number;
    slot_local_llm: number;
    slot_cli: number;
    slot_cloud: number;
  };
  research_providers: {
    coding_default: string;
    engine_mode: string;
    engine_priority: string[];
  };

  /** Opaque historical configuration; active settings never write this section. */
  readonly opencode?: {
    enabled: boolean;
    base_url: string;
    allow_metered_api: boolean;
    timeout_s: number;
    workspace_mode: string;
  };
  memory: {
    keep_recent_turns: number;
    auto_summarize: boolean;
    interval_s: number;
    high_watermark_tokens: number;
    low_watermark_tokens: number;
    chunk_tokens: number;
    min_keep_messages: number;
    parallel_summaries: number;
    summary_timeout_s: number;
    context_budget_tokens: number;
    embed_engine: string;
    embed_model: string;
    rerank_url: string;
    rerank_model: string;
  };
  resources: {
    enforce_caps: boolean;
    require_unload: boolean;
    vram_free_target_mb: number;
    unload_wait_s: number;
    unload_timeout_s: number;
    gpu_temp_limit_c: number;
    cpu_fallback_on_gpu_fault: boolean;
    gpu_busy_util_pct: number;
    sandbox_memory_gb: number;
    sandbox_cpus: number;
    local_ai_vram_gb: number;
    local_ai_threads: number;
    auto_unload_for_gpu: boolean;
  };
  lifecycle: {
    enabled: boolean;
    unload_on_exit: boolean;
    local_background: string;
    local_interactive: string;
    cli: string;
    mcp: string;
    cloud: string;
    cloud_preconnect?: boolean;
    local_idle_min: number;
    cli_idle_min: number;
    mcp_idle_min: number;
    cloud_idle_min: number;
    unload_grace_s: number;
    respect_manual_loads: boolean;
    single_model_vram: boolean;
  };
  /** Historical migration metadata only. */
  readonly clearml?: {
    enabled: boolean;
    auto_record: boolean;
    project: string;
    server_enabled: boolean;
    web_url: string;
  };
  workspace: {
    vscode_path: string;
  };
  routing: {
    online_check: boolean;
    chains: Record<string, string[]>;
    provider_headers?: Record<string, unknown>;
    capability_aware: boolean;
    verified_local_tasks: string[];
    verified_fallbacks: Record<string, string[]>;
  };
  gateway: {
    enabled: boolean;
    allow_internal: boolean;
    allow_sensitive: boolean;
    block_source_code: boolean;
    claude_code_oauth_token?: string;  // always masked by the backend
    has_claude_code_oauth_token?: boolean;
    context_budget_tokens: number;
    provider_timeout_s: number;
    codex_app_server: boolean;
    cli_models: Record<string, string[]>;
    codex_enabled: boolean;
    claude_code_enabled: boolean;
    gemini_cli_enabled: boolean;
    antigravity_enabled: boolean;
    cli_profile: string;
  };
  mcp: {
    enabled: boolean;
    expose_research: boolean;
    allow_writes: boolean;
    expose_sandbox: boolean;
    token?: string;
    has_token?: boolean;
    rate_limit_per_min: number;
    audit: boolean;
  };
  mcp_agent: {
    enabled: boolean;
    url: string;
    token?: string;
    has_token?: boolean;
    tool: string;
    models: string[];
    timeout_s: number;
  };
  aiws: {
    history_budget_tokens?: number;
    enabled: boolean;
    operating_mode: string;
    provider: string;
    model: string;
    reasoning: string;
    context_mode: string;
    memory_mode: string;
    auto_memory_types: string[];
    mcp_auto: boolean;
    mcp_tools: string[];
    security_profile: string;
    keep_history: boolean;
    summaries: boolean;
    collect_artifacts: boolean;
    context_budget_tokens: number;
    max_turn_s: number;
  };
  research_os: {
    enabled: boolean;
    team_enabled: boolean;
    multi_team_enabled: boolean;
  };
  ranking: {
    auto: boolean;
    core_source: string;
    watch_downloads: boolean;
    refresh_days: number;
  };
}

export interface Topic {
  id: string;
  title: string;
  name?: string;
  description: string;
  objectives?: string;
  keywords?: string[];
  synonyms?: string[];
  exclusions?: string[];
  sources?: string[];
  min_year?: number;
  cadence?: 'off' | 'manual' | 'daily' | 'weekly';
  enabled?: boolean;
  metadata_limit?: number;
  pdf_limit?: number;
  created: string;
  updated: string;
  status?: string;
  archived?: boolean;
}

export interface ChatApproval {
  id: string;
  turn_id?: string;
  kind: 'tool' | 'action' | 'apply_artifact' | string;
  name: string;
  args?: Record<string, any>;
  payload?: Record<string, any>;
  status: 'pending' | 'approved' | 'executed' | 'rejected' | 'failed' | 'denied' | 'cancelled';
  reason?: string;
  decided_by?: string;
  created?: number;
  result?: Record<string, any>;
}

export interface ChatMemoryItem {
  id: string;
  status: 'pending' | 'duplicate' | 'approved' | 'rejected' | string;
  type: string;
  text: string;
  message_ids?: string[];
  conflicts?: number;
  created?: string;
}

export interface ChatArtifact {
  id: string;
  turn_id?: string;
  path: string;
  status: 'collected' | 'applied' | 'rejected' | string;
  created?: number;
}

export interface ChatNote {
  id: string;
  message_id: string;
  quote?: string;
  prefix?: string;
  suffix?: string;
  text?: string;
  status?: 'open' | 'resolved';
  created?: number;
  point?: { chart: number; series: string; x: string | number; y: string | number; label?: string };
}

export interface ChatTurn {
  manifest?: { sources?: Array<{ id: string; truncated?: boolean }>; omitted?: Array<{ id: string; reason?: string }> };
  history_manifest?: { omitted_messages?: string[]; truncated_messages?: string[]; budget_tokens?: number };
  error?: string;
  id: string;
  status: 'running' | 'queued' | 'waiting_approval' | 'awaiting_launch' | 'completed' | 'failed' | 'cancelled';
  created?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  text?: string;
  ts?: number;
  created?: number;
  status?: string;
  model?: string;
  provider?: string;
  turn_id?: string;
  run_id?: string;
  pinned?: boolean;
  sources?: string[];
  citations?: Array<{ key?: string; title?: string; url?: string }>;
  attachments?: Array<{ id: string; name: string; size?: number; path?: string }>;
  proposals?: Array<{ id: string; kind: string; payload: Record<string, unknown>; status?: string }>;
  error?: string;
}

export interface ChatProject {
  id: string;
  name: string;
  instructions?: string;
  created: number;
}

export interface ChatSession {
  id: string;
  title: string;
  created: number;
  updated: number;
  status?: string;
  archived?: boolean;
  pinned?: boolean;
  chat_project?: string;
  topic_id?: string;
  provider?: string;
  pending_approvals?: number;
  last?: string;
  settings?: {
    provider?: string;
    model?: string;
    reasoning?: string;
    [key: string]: unknown;
  };
  messages?: ChatMessage[];
  turns?: ChatTurn[];
  approvals?: ChatApproval[];
  memory_items?: ChatMemoryItem[];
  artifacts?: ChatArtifact[];
  notes?: ChatNote[];
  last_seq?: number;
  memory?: string[];
  run_id?: string;
}

export interface SkillItem {
  name: string;
  aliases?: string[];
  alias?: string;
  title?: string;
  title_en?: string;
  description?: string;
  description_en?: string;
  category?: string;
  provider?: string;
  mode?: 'chat' | 'run' | 'ui';
  origin?: 'builtin' | 'user' | 'project' | 'plugin';
  plugin?: string;
  risk?: number;
}

export interface ModelProviderItem {
  provider_id?: string;
  readiness?: Record<string, string>;
  model_catalog?: { origin: string; models: string[]; verified: boolean; queried_at?: number };
  runtime?: { state?: string; detail?: string };
  billing?: string;
  setup?: string[];

  id: string;
  label: string;
  name?: string;
  selected?: string;
  transport: 'router' | 'local' | 'api' | 'cli' | string;
  state: string;
  available: boolean;
  detail?: string;
  models: string[];
  reasoning: string[];
}

export interface ModelsResponse {
  agents: Record<string, { engine: string; model: string; label: string; [key: string]: unknown }>;
  agent_catalog: Record<string, {
    provider_id?: string;
    engine: string;
    mode: string;
    label: string;
    models: string[];
    selected: string;
  }>;
  providers: ModelProviderItem[];
  default: string | { provider?: string; model?: string };
  cloud: Record<string, { label: string; models: string[] }>;
}

export interface ModelItem {
  id: string;
  name: string;
  provider: string;
  available: boolean;
  level?: string;
  context_window?: number;
}

export interface OSSettings {
  enabled: boolean;
  team_enabled: boolean;
  multi_team_enabled: boolean;
  experimental: boolean;
  max_parallel_tasks: 1;
}

export interface MissionTask {
  id: string;
  capability?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'interrupted' | 'blocked';
  payload: {
    spec: {
      id: string;
      capability: string;
      depends_on?: string[];
      preferred_engine?: string;
      fallback_engines?: string[];
      args?: Record<string, unknown>;
      arguments?: Record<string, unknown>;
    };
    attempts: number;
    result_digest?: string;
    human_review?: { accept: boolean; note: string };
    result?: {
      status?: string;
      engine?: string;
      output?: unknown;
      error?: string;
      artifacts?: Array<{ index?: number; type?: string; title?: string; path?: string; sha256?: string }>;
      limitations?: string[];
    };
    execution_record?: {
      attempt_key: string;
      elapsed_seconds: number;
      outcome: string;
      provider_usage: unknown;
      verification_status: string;
    };
  };
}

export interface Mission {
  id: string;
  topic_id: string;
  status: 'draft' | 'queued' | 'running' | 'paused' | 'awaiting_review' | 'awaiting_step_review' | 'completed' | 'failed' | 'cancelled' | 'interrupted';
  payload: {
    spec: {
      topic_id: string;
      objective: string;
      autonomy?: { level: 'L1' | 'L2' | 'L3' | 'L4'; max_output_tokens: number };
      permissions: string[];
      tasks: Array<{
        id: string;
        capability: string;
        depends_on?: string[];
        preferred_engine?: string;
        fallback_engines?: string[];
        args?: Record<string, unknown>;
      }>;
      limits?: {
        max_seconds: number;
        max_reasoning_calls: number;
      };
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
    };
    plan_digest?: string;
    approval?: {
      plan_digest: string;
      expires?: string;
      note?: string;
    };
    blocking_reason?: string;
    active_seconds: number;
    reasoning_calls: number;
    started_at?: string;
  };
  tasks: MissionTask[];
  created: string;
  updated: string;
}

export interface WorkstreamView {
  messages: Array<{
    id: string;
    source_workstream?: string;
    target_workstream?: string;
    source_task?: string;
    target_task?: string;
    task_id?: string;
    evidence_hash?: string;
    digest?: string;
    created: string;
  }>;
  receipts: Array<{
    id?: string;
    message_id?: string;
    handoff_id?: string;
    receiver_team?: string;
    received_by?: string;
    at?: string;
    created?: string;
  }>;
  disputes: Array<{
    id: string;
    status: 'open' | 'resolved';
    revision: number;
    payload: {
      reason: string;
      claim_ids?: string[];
      source_workstream?: string;
      resolution_note?: string;
    };
  }>;
  canonical_outputs: Record<string, {
    key: string;
    team_id: string;
    source_task: string;
    artifact_index: number;
    revision: number;
    updated: string;
  }>;
  usage: Array<{
    team_id: string;
    tasks_completed?: number;
    reasoning_calls?: number;
    active_seconds: number;
  }>;
}

export interface Claim {
  id: string;
  topic_id: string;
  status: 'draft' | 'proposed' | 'checked' | 'supported' | 'contested' | 'accepted' | 'rejected';
  payload: {
    kind: string;
    text: string;
    limitations?: string[];
  };
  evidence: Array<{
    id: string;
    payload: {
      source_type?: string;
      source_id: string;
      quote?: string;
      excerpt?: string;
      locator?: string;
      provenance?: {
        paper_id?: string;
        version_id?: string;
        page?: number;
      };
    };
  }>;
  checks: Array<{
    outcome?: string;
    status?: string;
    details?: unknown;
  }>;
}

export interface LibraryPaper {
  id?: string;
  key?: string;
  file?: string;
  filename?: string;
  title: string;
  authors: string[];
  year: number | string;
  doi?: string;
  arxiv_id?: string;
  venue?: string;
  abstract?: string;
  source_url?: string;
  url?: string;
  pdf_url?: string;
  pdf_available?: boolean;
  metadata_only?: boolean;
  include?: boolean;
  level?: number;
  state?: string;
  tags?: string[];
  rank?: {
    rank?: string;
    tier?: string;
    source?: string;
  };
  journal_ranking?: {
    status?: string;
    quartile?: string;
    sjr?: number;
    h_index?: number;
    core_rank?: string;
    acronym?: string;
    conference?: string;
    source?: string;
    year?: number | string;
  };
  ranking?: {
    venue?: string;
    tier?: string;
  };
}

export interface LibraryResponse {
  references?: LibraryPaper[];
  papers?: LibraryPaper[];
  added?: number;
  dir?: string;
  pdf_backend?: string;
}

// ── v6.4.0 Figure Studio Contracts ─────────────────────────────────────────

export interface FigurePreset {
  id: string;
  label: string;
  width_in: number;
  height_in: number;
  font_size_pt: number;
  dpi: number;
  palette: string;
  venue_note: string;
}

export interface FigureVerificationReport {
  figure_artifact_id: string;
  version: number;
  source_data_artifact_ids: string[];
  tests: Record<string, string>;
  warnings: string[];
  errors: string[];
  overall_status: 'passed' | 'needs_review' | 'failed' | 'illustrative_only';
  validator_version: string;
  checked_at: string;
}

export interface FigureRecord {
  id: string;
  topic_id: string;
  mission_id?: string;
  title: string;
  category: 'plot_2d' | 'comparison_plate' | 'diagram' | 'waveform' | 'surface_3d';
  current_version: number;
  selected_version: number;
  status: string;
  spec: Record<string, any>;
  provenance: {
    renderer_used: string;
    renderer_version: string;
    spec_sha256: string;
    script_sha256: string;
    data_sha256: string;
    camera_state?: Record<string, number>;
    exports: Record<string, { path: string; sha256: string; bytes: number; mime: string }>;
    warnings: string[];
    scientific_review: string;
    created_at: string;
  };
  verification: FigureVerificationReport;
  svg_preview: string;
  versions?: Array<{
    version: number;
    spec_sha256: string;
    script_sha256: string;
    data_sha256: string;
    created: string;
  }>;
  created: string;
  updated: string;
}

// ── v6.4.1 OpenCode Contracts ──────────────────────────────────────────────

export interface OpenCodeStatus {
  engine: string;
  ready: boolean;
  state: string;
  server_reachable: boolean;
  base_url: string;
  loopback_only: boolean;
  auth_mode: string;
  metered_api_allowed: boolean;
  opencode_zen_enabled: boolean;
  provider_priority: string[];
  capabilities: string[];
  detail: string;
  installed: boolean;
  version: string;
}

export interface OpenCodeSession {
  id: string;
  topic_id: string;
  mission_id: string;
  task_id: string;
  workspace_id: string;
  native_session_id: string;
  status: 'running' | 'awaiting_approval' | 'paused' | 'blocked_by_quota' | 'reconciled_with_gap' | 'completed' | 'cancelled' | 'failed';
  payload: {
    spec: {
      goal: string;
      usage_policy: string;
      allow_metered_api: boolean;
      allowed_capabilities: string[];
    };
    workspace_path: string;
    blocking_reason?: string;
    sync_gap?: boolean;
    sync_gap_note?: string;
    artifacts?: Array<{ id: string; path: string; sha256: string; bytes: number; version: number }>;
  };
  events: Array<{
    id: string;
    seq: number;
    event_type: string;
    fingerprint: string;
    payload: Record<string, unknown>;
    created: string;
  }>;
  approvals: Array<{
    id: string;
    action: string;
    risk: string;
    status: 'pending' | 'approved' | 'rejected';
    payload: {
      action: string;
      scope: string;
      risk: string;
      decision?: string;
      note?: string;
    };
    created: string;
  }>;
  created: string;
  updated: string;
}

// ── v6.4.2 Unified Research Intelligence Contracts ─────────────────────────

export interface URAPArtifact {
  schema_version: string;
  artifact_id: string;
  artifact_type: string;
  project_id: string;
  topic_id: string;
  mission_id: string;
  task_id: string;
  producer: {
    runtime_id: string;
    runtime_version: string;
    session_id: string;
    agent_id: string;
  };
  content: {
    uri: string;
    media_type: string;
    byte_size: number;
    sha256: string;
    hash_algorithm: string;
  };
  lineage: {
    input_artifact_ids: string[];
    experiment_id: string;
    code_revision: string | null;
  };
  verification: {
    status: 'unverified' | 'auto_screened' | 'user_verified' | 'rejected' | 'superseded' | 'stale';
    verifier_task_id: string | null;
    evidence_artifact_ids: string[];
  };
  metadata: Record<string, unknown>;
  created_at: string;
}

// ── 3D Agent Office View Model ─────────────────────────────────────────────

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

export interface AgentCustomProfile {
  agentId: string;
  customName?: string;
  customTitle?: string;
  customBio?: string;
  customColor?: string;
  customGreeting?: string;
  updatedAt?: string;
}

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
  zone?: 'podium' | 'literature' | 'compute' | 'lab_bench' | 'review' | 'lounge';
  archetype?: 'pi' | 'literature' | 'experiment' | 'opencode' | 'reviewer' | 'figure_fellow';
  personality?: string;
  skillCommand?: string;
  speechBubble?: string;
  customName?: string;
  customTitle?: string;
  customBio?: string;
  customColor?: string;
  customGreeting?: string;
}

export interface LatexEnginesInfo {
  available: string[];
  paths: Record<string, string>;
  online: boolean;
  default: string;
  platform: string;
}

export interface PaperSection {
  id: string;
  title: string;
  text: string;
  state: string;
  versions: number;
}

export interface PaperProject {
  title: string;
  authors: string;
  style: string;
  venue: string;
  sections: PaperSection[];
  pdf: boolean;
}

export interface CompilePaperResponse {
  ok: boolean;
  engine: string;
  layout: string;
  seconds: number;
  pdf_mtime?: number | null;
  report?: {
    figures?: number;
    tables?: number;
    cites?: number;
    sections?: number;
    [key: string]: unknown;
  };
  notes?: string[];
  errors?: Array<{
    message: string;
    line?: number | null;
    context?: string;
    section?: string;
    section_title?: string;
  }>;
  undefined_citations?: string[];
  undefined_refs?: string[];
  overfull?: number;
  pages?: number | null;
  missing_files?: string[];
}

export interface HarnessToolSpec {
  id: string;
  name: string;
  category: string;
  icon: string;
  description: string;
  description_en: string;
  default_params: Record<string, unknown>;
  available_metrics: string[];
  docs_url: string;
}

export type WorkflowNodeType =
  | 'start'
  | 'end'
  | 'agent_task'
  | 'multi_agent_team'
  | 'research_engine'
  | 'tool_skill'
  | 'mcp_tool'
  | 'input'
  | 'output'
  | 'condition'
  | 'parallel_branch'
  | 'join'
  | 'bounded_loop'
  | 'human_approval'
  | 'evaluation_gate'
  | 'artifact_transformation'
  | 'memory_read'
  | 'memory_write'
  | 'error_handler'
  | 'checkpoint'
  | 'harnessNode';

export interface WorkflowNodePort {
  id: string;
  name: string;
  type: 'control' | 'data' | 'artifact' | 'boolean';
  direction: 'input' | 'output';
  required?: boolean;
  description?: string;
}

export interface WorkflowNodeMetadata {
  type: WorkflowNodeType;
  label: string;
  label_en: string;
  category: 'flow' | 'agent' | 'engine' | 'tool' | 'data' | 'governance' | 'benchmark';
  icon: string;
  description: string;
  description_en: string;
  inputs: WorkflowNodePort[];
  outputs: WorkflowNodePort[];
  default_config: Record<string, unknown>;
  config_schema: Record<string, unknown>;
}

export interface AgentProfile {
  id: string;
  name: string;
  role: string;
  purpose: string;
  system_prompt: string;
  provider: string;
  model?: string;
  reasoning_effort?: string;
  skills: string[];
  mcp_tools: string[];
  memory_scope: string;
  permissions: string[];
  max_tokens: number;
  timeout_seconds: number;
  max_retries: number;
  fallback_provider?: string;
}

export interface WorkflowValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  node_count: number;
  edge_count: number;
}

export interface HarnessNodeData {
  label: string;
  tool?: string;
  node_type?: WorkflowNodeType;
  category?: string;
  params?: Record<string, unknown>;
  config?: Record<string, unknown>;
  description?: string;
  input_artifact_ids?: string[];
  output_artifact_ids?: string[];
  checkpoint_id?: string;
  status?: 'idle' | 'running' | 'completed' | 'failed' | 'skipped' | 'waiting_approval' | 'paused';
  result?: {
    passed?: boolean;
    duration_s?: number;
    metrics?: Record<string, unknown>;
    summary?: string;
    output?: unknown;
    error?: string;
  };
  [key: string]: unknown;
}

export interface CustomHarnessWorkflow {
  id: string;
  name: string;
  name_en?: string;
  description: string;
  description_en?: string;
  topic_id?: string;
  category?: string;
  badge?: string;
  is_preset?: boolean;
  generated_by_ai?: boolean;
  execution_level?: 'L2' | 'L3' | 'L4' | string;
  nodes: Array<{
    id: string;
    type?: string;
    position: { x: number; y: number };
    data: HarnessNodeData;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    sourceHandle?: string;
    targetHandle?: string;
    label?: string;
  }>;
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowExecutionState {
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  status: 'pending' | 'running' | 'paused' | 'waiting_approval' | 'completed' | 'failed' | 'cancelled' | 'blocked';
  execution_level: string;
  step_mode: boolean;
  current_node_id?: string | null;
  node_statuses: Array<{
    node_id: string;
    label: string;
    node_type: string;
    status: 'idle' | 'running' | 'completed' | 'failed' | 'skipped' | 'waiting_approval' | 'blocked';
    started_at?: string;
    completed_at?: string;
    duration_s?: number;
    output?: unknown;
    error?: string;
    feedback?: string;
    summary?: string;
  }>;
  total_duration_s: number;
  checkpoints: Array<Record<string, unknown>>;
  artifacts_produced: string[];
  logs: Array<{
    timestamp: string;
    level: string;
    node_id?: string;
    message: string;
  }>;
  started_at: string;
  completed_at?: string;
}

export interface HarnessExecutionReport {
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  status: 'completed' | 'failed' | 'partial';
  passed: boolean;
  total_duration_s: number;
  nodes_count: number;
  node_results: Record<
    string,
    {
      node_id: string;
      label: string;
      tool_id: string;
      tool_name: string;
      status: string;
      passed: boolean;
      duration_s: number;
      metrics: Record<string, unknown>;
      summary: string;
      timestamp: string;
    }
  >;
  created_at: string;
}
