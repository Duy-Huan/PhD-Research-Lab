import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { Canvas } from '@react-three/fiber';
import { renderWithProviders } from '../../../test/test-utils';
import { AgentAvatar } from './AgentAvatar';
import type { AgentOfficeViewModel } from '../../../shared/api/types';

describe('AgentAvatar', () => {
  it('renders 3D agent avatar without throwing', () => {
    const dummyAgent: AgentOfficeViewModel = {
      agentId: 'faculty_pi',
      projectId: 'p-1',
      displayName: 'Prof. AI Orchestrator (PI)',
      role: 'Principal Investigator',
      engine: 'cloud:google',
      presence: 'running',
      activity: 'reviewing',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'pi',
      speechBubble: 'Leading the research seminar',
    };

    expect(() => {
      renderWithProviders(
        <Canvas>
          <AgentAvatar
            agent={dummyAgent}
            index={0}
            position={[0, 0, 0]}
            isSelected={true}
            socializeMode={true}
          />
        </Canvas>
      );
    }).not.toThrow();
  });

  it('renders 3D agent avatar with custom personal profile attributes', () => {
    const customAgent: AgentOfficeViewModel = {
      agentId: 'faculty_pi',
      projectId: 'p-1',
      displayName: 'GS. Minh Trí',
      role: 'Principal Investigator',
      engine: 'cloud:google',
      presence: 'idle',
      activity: 'reading',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      archetype: 'pi',
      customName: 'GS. Minh Trí',
      customColor: '#065f46',
      customGreeting: 'Chào ngày mới!',
    };

    expect(() => {
      renderWithProviders(
        <Canvas>
          <AgentAvatar
            agent={customAgent}
            index={0}
            position={[0, 0, 0]}
            isSelected={true}
            socializeMode={true}
          />
        </Canvas>
      );
    }).not.toThrow();
  });
});
