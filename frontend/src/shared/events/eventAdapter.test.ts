import { describe, it, expect } from 'vitest';
import {
  mapMissionsToAgentViewModels,
  buildUniversityLabRoster,
} from './eventAdapter';
import type { Mission, OpenCodeSession } from '../api/types';

describe('eventAdapter', () => {
  it('localizes permanent faculty while preserving supplied live-agent context', () => {
    const live = { agentId: 'user-agent', displayName: 'Tên riêng của người dùng' } as any;
    const english = buildUniversityLabRoster([live], 'p', undefined, undefined, 'en');
    expect(english[0]).toBe(live);
    for (const agent of english.slice(1)) {
      expect([agent.role, agent.personality, agent.speechBubble].join(' ')).not.toMatch(/[À-ỹ]/);
    }
    const vietnamese = buildUniversityLabRoster([], 'p', undefined, undefined, 'vi');
    expect(vietnamese.find(a => a.agentId === 'faculty_pi_orchestrator')?.personality).toContain('Điềm tĩnh');
  });
  it('maps missions with various task statuses and capabilities to agent view models', () => {
    const mockMissions: Mission[] = [
      {
        id: 'm-1',
        topic_id: 't-1',
        status: 'running',
        created: '2026-10-24T00:00:00Z',
        updated: '2026-10-24T00:00:00Z',
        tasks: [
          {
            id: 'task-code',
            status: 'running',
            payload: {
              attempts: 1,
              spec: { id: 'code-gen', capability: 'code.execute', preferred_engine: 'opencode' },
            },
          },
          {
            id: 'task-paper',
            status: 'completed',
            payload: {
              attempts: 1,
              spec: { id: 'paper-search', capability: 'paper.inspect', preferred_engine: 'feynman' },
            },
          },
          {
            id: 'task-verify',
            status: 'running',
            payload: {
              attempts: 1,
              spec: { id: 'verify-claim', capability: 'verify.claim', preferred_engine: 'reviewer' },
            },
          },
          {
            id: 'task-exp',
            status: 'running',
            payload: {
              attempts: 1,
              spec: { id: 'run-exp', capability: 'experiment.run', preferred_engine: 'openscience' },
            },
          },
          {
            id: 'task-fig',
            status: 'running',
            payload: {
              attempts: 1,
              spec: { id: 'plot-fig', capability: 'figure.plot', preferred_engine: 'auto' },
            },
          },
          {
            id: 'task-pending',
            status: 'pending',
            payload: {
              attempts: 0,
              spec: { id: 'pending-task', capability: 'search', preferred_engine: 'auto' },
            },
          },
          {
            id: 'task-failed',
            status: 'failed',
            payload: {
              attempts: 2,
              spec: { id: 'failed-task', capability: 'compute', preferred_engine: 'opencode' },
            },
          },
          {
            id: 'task-paused',
            status: 'interrupted',
            payload: {
              attempts: 1,
              spec: { id: 'paused-task', capability: 'compute', preferred_engine: 'opencode' },
            },
          },
          {
            id: 'task-blocked',
            status: 'blocked',
            payload: {
              attempts: 1,
              spec: { id: 'blocked-task', capability: 'pi.orchestrate', preferred_engine: 'pi' },
            },
          },
        ],
        payload: {
          blocking_reason: 'Awaiting human authorization',
          spec: { topic_id: 't-1', objective: 'Test mission', permissions: [], tasks: [] },
          active_seconds: 0,
          reasoning_calls: 0,
        },
      },
    ];

    const result = mapMissionsToAgentViewModels(mockMissions, 'proj-1', 't-1');
    expect(result.length).toBe(9);

    const codeAgent = result.find((a) => a.agentId === 'm-1_task-code');
    expect(codeAgent?.presence).toBe('awaiting_approval');
    expect(codeAgent?.zone).toBe('compute');

    const paperAgent = result.find((a) => a.agentId === 'm-1_task-paper');
    expect(paperAgent?.zone).toBe('literature');
    expect(paperAgent?.archetype).toBe('feynman');

    const verifyAgent = result.find((a) => a.agentId === 'm-1_task-verify');
    expect(verifyAgent?.zone).toBe('review');
    expect(verifyAgent?.archetype).toBe('reviewer');

    const expAgent = result.find((a) => a.agentId === 'm-1_task-exp');
    expect(expAgent?.zone).toBe('lab_bench');
    expect(expAgent?.archetype).toBe('openscience');

    const figAgent = result.find((a) => a.agentId === 'm-1_task-fig');
    expect(figAgent?.archetype).toBe('figure_fellow');
  });

  it('maps OpenCode parallel core sessions across all lifecycle states', () => {
    const mockSessions: any[] = [
      { id: 's-run', topic_id: 't-1', status: 'running', created: '2026-10-24T00:00:00Z', updated: '2026-10-24T00:00:00Z' },
      { id: 's-appr', topic_id: 't-1', status: 'awaiting_approval', created: '2026-10-24T00:00:00Z', updated: '2026-10-24T00:00:00Z' },
      { id: 's-rate', topic_id: 't-1', status: 'blocked_by_quota', created: '2026-10-24T00:00:00Z', updated: '2026-10-24T00:00:00Z' },
      { id: 's-done', topic_id: 't-1', status: 'completed', created: '2026-10-24T00:00:00Z', updated: '2026-10-24T00:00:00Z' },
      { id: 's-fail', topic_id: 't-1', status: 'failed', created: '2026-10-24T00:00:00Z', updated: '2026-10-24T00:00:00Z' },
      { id: 's-pause', topic_id: 't-1', status: 'paused', created: '2026-10-24T00:00:00Z', updated: '2026-10-24T00:00:00Z' },
    ];

    const result = mapMissionsToAgentViewModels([], 'proj-1', 't-1', mockSessions);
    expect(result).toHaveLength(6);

    expect(result.find((a) => a.agentId === 'opencode_s-run')?.presence).toBe('running');
    expect(result.find((a) => a.agentId === 'opencode_s-appr')?.presence).toBe('awaiting_approval');
    expect(result.find((a) => a.agentId === 'opencode_s-rate')?.presence).toBe('rate_limited');
    expect(result.find((a) => a.agentId === 'opencode_s-done')?.presence).toBe('completed');
    expect(result.find((a) => a.agentId === 'opencode_s-fail')?.presence).toBe('failed');
    expect(result.find((a) => a.agentId === 'opencode_s-pause')?.presence).toBe('paused');
  });

  it('builds full University Lab Roster including core faculty and live agents', () => {
    const liveAgents = mapMissionsToAgentViewModels([], 'proj-1', 't-1', [
      { id: 'live-worker', topic_id: 't-1', status: 'running', created: '2026-10-24T00:00:00Z', updated: '2026-10-24T00:00:00Z' },
    ] as any);

    const roster = buildUniversityLabRoster(liveAgents, 'proj-1', 't-1', {
      assistant: 'cloud:google',
      research: 'claude_code',
      reviewer: 'codex',
      utility: 'antigravity',
    });

    expect(roster.length).toBe(7); // 1 live agent + 6 core faculty
    expect(roster[0].agentId).toBe('opencode_live-worker');
    expect(roster.some((a) => a.agentId === 'faculty_pi_orchestrator')).toBe(true);

    const emptyRoster = buildUniversityLabRoster([], 'proj-1');
    expect(emptyRoster).toHaveLength(6);
  });
});
