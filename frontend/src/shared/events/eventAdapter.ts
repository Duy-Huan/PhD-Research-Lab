import type {
  Mission,
  OpenCodeSession,
  AgentOfficeViewModel,
  AgentPresence,
  AgentActivity,
} from '../api/types';

function inferZone(role: string, engine: string): AgentOfficeViewModel['zone'] {
  const r = (role || '').toLowerCase();
  const e = (engine || '').toLowerCase();
  if (e === 'opencode' || r.includes('code') || r.includes('implement') || r.includes('compute')) {
    return 'compute';
  }
  if (r.includes('paper') || r.includes('lit') || r.includes('inspect') || e === 'feynman') {
    return 'literature';
  }
  if (r.includes('verify') || r.includes('validate') || r.includes('review') || r.includes('claim')) {
    return 'review';
  }
  if (r.includes('experiment') || r.includes('protocol') || r.includes('figure')) {
    return 'lab_bench';
  }
  if (r.includes('orchestrat') || r.includes('plan') || r.includes('pi')) {
    return 'podium';
  }
  return 'lab_bench';
}

// Old producer IDs below are read-only historical aliases, never active runtime choices.
function inferArchetype(role: string, engine: string): AgentOfficeViewModel['archetype'] {
  const r = (role || '').toLowerCase();
  const e = (engine || '').toLowerCase();
  if (e === 'opencode' || r.includes('code') || r.includes('implement')) return 'opencode';
  if (e === 'feynman' || r.includes('paper') || r.includes('lit')) return 'literature';
  if (e === 'openscience' || r.includes('protocol') || r.includes('experiment')) return 'experiment';
  if (r.includes('review') || r.includes('verify') || r.includes('claim')) return 'reviewer';
  if (r.includes('figure') || r.includes('latex')) return 'figure_fellow';
  return 'pi';
}

export function mapMissionsToAgentViewModels(
  missions: Mission[],
  projectId: string,
  topicId?: string,
  opencodeSessions: OpenCodeSession[] = []
): AgentOfficeViewModel[] {
  const models: AgentOfficeViewModel[] = [];

  for (const m of missions) {
    if (topicId && m.topic_id !== topicId) continue;

    for (const t of m.tasks) {
      const spec = t.payload.spec;
      const engine = t.payload.result?.engine || spec.preferred_engine || 'deterministic';
      const role = spec.capability || 'researcher';
      const displayName = `${spec.id} (${engine})`;

      let presence: AgentPresence = 'idle';
      let activity: AgentActivity = 'none';

      if (t.status === 'running') {
        presence = 'running';
        if (spec.capability.includes('paper') || spec.capability.includes('inspect')) {
          activity = 'reading';
        } else if (spec.capability.includes('code') || spec.capability.includes('opencode')) {
          activity = 'writing';
        } else if (spec.capability.includes('verify') || spec.capability.includes('validate')) {
          activity = 'reviewing';
        } else if (spec.capability.includes('experiment')) {
          activity = 'executing';
        } else if (spec.capability.includes('figure') || spec.capability.includes('report')) {
          activity = 'reporting';
        } else {
          activity = 'searching';
        }
      } else if (t.status === 'pending') {
        presence = m.status === 'running' || m.status === 'queued' ? 'queued' : 'idle';
      } else if (t.status === 'completed') {
        presence = 'completed';
      } else if (t.status === 'failed') {
        presence = 'failed';
      } else if (t.status === 'interrupted' || t.status === 'blocked') {
        presence = 'paused';
      }

      if (m.payload.blocking_reason) {
        presence = 'awaiting_approval';
      }

      models.push({
        agentId: `${m.id}_${t.id}`,
        missionId: m.id,
        taskId: t.id,
        projectId,
        topicId: m.topic_id,
        displayName,
        role,
        engine,
        presence,
        activity,
        lastObservedAt: m.updated || m.created,
        canInspect: true,
        canPause: presence === 'running',
        canResume: presence === 'paused',
        hasApprovalRequest: presence === 'awaiting_approval',
        zone: inferZone(role, engine),
        archetype: inferArchetype(role, engine),
        personality: 'Autonomous Mission Task Specialist',
        skillCommand: '/status',
        speechBubble:
          presence === 'running'
            ? `Executing ${spec.capability}…`
            : presence === 'awaiting_approval'
            ? 'Waiting for PI approval…'
            : undefined,
      });
    }
  }

  // Historical producer IDs/status remain visible, never advertised as live processes.
  for (const s of opencodeSessions) {
    if (topicId && s.topic_id !== topicId) continue;

    const presence: AgentPresence = s.status === 'completed' ? 'completed' : s.status === 'failed' ? 'failed' : 'unknown';
    const activity: AgentActivity = 'none';

    models.push({
      agentId: `opencode_${s.id}`,
      sessionId: s.id,
      missionId: s.mission_id || undefined,
      taskId: s.task_id || s.id,
      projectId,
      topicId: s.topic_id,
      displayName: `${s.id} (OpenCode history: ${s.status})`,
      role: s.payload?.spec?.goal?.slice(0, 40) || 'opencode.implement',
      engine: 'opencode',
      presence,
      activity,
      lastObservedAt: s.updated || s.created,
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      zone: 'compute',
      archetype: 'opencode',
      personality: 'Historical software execution record (read only)',
    });
  }

  return models;
}

/**
 * Add configured roles as idle stations. Configuration is not execution telemetry.
 */
export function buildUniversityLabRoster(
  liveAgents: AgentOfficeViewModel[],
  projectId: string,
  topicId?: string,
  agentModes?: Record<string, string>,
  language: 'vi' | 'en' = 'en',
  configuredAgents?: Record<string, {label: string}>
): AgentOfficeViewModel[] {
  const roles = configuredAgents ? Object.keys(configuredAgents) : Object.keys(agentModes || {});
  const names: Record<string, [string,string]> = {
    assistant: ['Trợ lý chat','Chat assistant'], research: ['Agent nghiên cứu','Research agent'],
    reviewer: ['Agent phản biện','Reviewer agent'], utility: ['Agent tiện ích','Utility agent'],
  };
  const stations = roles.map(role => ({
    agentId: `configured_${role}`, projectId, topicId,
    displayName: names[role]?.[language === 'vi' ? 0 : 1] || configuredAgents?.[role]?.label || role,
    role, engine: agentModes?.[role] || 'auto', presence: 'idle' as const, activity: 'none' as const,
    lastObservedAt: '', canInspect: true, canPause: false, canResume: false, hasApprovalRequest: false,
    zone: inferZone(role, ''), archetype: inferArchetype(role, ''),
    personality: language === 'vi' ? 'Vai trò đã cấu hình; chưa có quan sát thực thi' : 'Configured role; no execution observation',
  }));
  return [...stations, ...liveAgents];
}
