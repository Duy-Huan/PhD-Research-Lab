import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderWithProviders } from '../../../test/test-utils';
import { OfficeScene, type LabLightingMode } from './OfficeScene';
import type { AgentOfficeViewModel } from '../../../shared/api/types';

describe('OfficeScene', () => {
  const dummyAgents: AgentOfficeViewModel[] = [
    {
      agentId: 'a-1',
      projectId: 'p-1',
      displayName: 'Agent 1',
      role: 'PI',
      engine: 'auto',
      presence: 'running',
      activity: 'reviewing',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'pi',
    },
    {
      agentId: 'a-2',
      projectId: 'p-1',
      displayName: 'Agent 2',
      role: 'Code',
      engine: 'opencode',
      presence: 'idle',
      activity: 'writing',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'opencode',
    },
    {
      agentId: 'a-3',
      projectId: 'p-1',
      displayName: 'Agent 3',
      role: 'Reviewer',
      engine: 'claude',
      presence: 'idle',
      activity: 'reviewing',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'reviewer',
    },
    {
      agentId: 'a-4',
      projectId: 'p-1',
      displayName: 'Agent 4',
      role: 'Lit',
      engine: 'feynman',
      presence: 'idle',
      activity: 'reading',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'feynman',
    },
    {
      agentId: 'a-5',
      projectId: 'p-1',
      displayName: 'Agent 5',
      role: 'Figure',
      engine: 'auto',
      presence: 'idle',
      activity: 'reporting',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'figure_fellow',
    },
    {
      agentId: 'a-6',
      projectId: 'p-1',
      displayName: 'Agent 6',
      role: 'Science',
      engine: 'openscience',
      presence: 'idle',
      activity: 'executing',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'openscience',
    },
    // Extra agents for station grid wrapping
    {
      agentId: 'a-7',
      projectId: 'p-1',
      displayName: 'Agent 7',
      role: 'Worker',
      engine: 'auto',
      presence: 'queued',
      activity: 'searching',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'pi',
    },
    {
      agentId: 'a-8',
      projectId: 'p-1',
      displayName: 'Agent 8',
      role: 'Worker 8',
      engine: 'auto',
      presence: 'idle',
      activity: 'none',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'pi',
    },
    {
      agentId: 'a-9',
      projectId: 'p-1',
      displayName: 'Agent 9',
      role: 'Worker 9',
      engine: 'auto',
      presence: 'idle',
      activity: 'none',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'pi',
    },
    {
      agentId: 'a-10',
      projectId: 'p-1',
      displayName: 'Agent 10',
      role: 'Worker 10',
      engine: 'auto',
      presence: 'idle',
      activity: 'none',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'pi',
    },
  ];

  it('renders scene under all 4 lighting modes without crashing', () => {
    const modes: LabLightingMode[] = ['biophilic_green', 'daylight', 'night_lab', 'cyber_science'];

    for (const lightingMode of modes) {
      const { unmount } = renderWithProviders(
        <OfficeScene
          agents={dummyAgents}
          selectedAgentId="a-1"
          selectedLabObject="outline"
          lightingMode={lightingMode}
          topicTitle="Quantum Optics"
          paperCount={8}
          missionCount={3}
          socializeMode={true}
          onSelectAgent={vi.fn()}
          onSelectLabObject={vi.fn()}
        />
      );
      unmount();
    }
  });
});
