import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../../test/test-utils';
import { OfficeCanvas } from './OfficeCanvas';
import type { AgentOfficeViewModel } from '../../../shared/api/types';

describe('OfficeCanvas', () => {
  const dummyAgents: AgentOfficeViewModel[] = [
    {
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
      zone: 'podium',
      archetype: 'pi',
      personality: 'Leader',
      speechBubble: 'Leading the research seminar',
    },
    {
      agentId: 'faculty_lit',
      projectId: 'p-1',
      displayName: 'Dr. Feynman (Literature)',
      role: 'Literature Specialist',
      engine: 'feynman',
      presence: 'idle',
      activity: 'reading',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      zone: 'literature',
      archetype: 'feynman',
      personality: 'Curious',
      speechBubble: 'Analyzing research gap',
    },
  ];

  it('renders 3D Canvas with camera presets, lighting modes, and switches lighting', () => {
    const toggleSocialize = vi.fn();
    const selectObject = vi.fn();
    const selectAgent = vi.fn();

    renderWithProviders(
      <OfficeCanvas
        agents={dummyAgents}
        selectedAgentId="faculty_pi"
        selectedLabObject="library"
        topicTitle="Topological Quantum"
        paperCount={12}
        missionCount={4}
        socializeMode={true}
        onToggleSocialize={toggleSocialize}
        onSelectLabObject={selectObject}
        onSelectAgent={selectAgent}
      />
    );

    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument();

    // Click camera preset buttons
    const cameraButtons = screen.getAllByRole('button');
    expect(cameraButtons.length).toBeGreaterThan(5);

    // Click lighting buttons (Daylight, Night, Cyber, Biophilic Green)
    const daylightBtn = screen.getByTitle(/Ánh sáng Ban ngày|Daylight/i);
    fireEvent.click(daylightBtn);

    const nightBtn = screen.getByTitle(/Phòng Lab Đêm|Night Lab/i);
    fireEvent.click(nightBtn);

    const cyberBtn = screen.getByTitle(/Cyber Lab/i);
    fireEvent.click(cyberBtn);

    const greenBtn = screen.getByTitle(/Không gian (Phòng Lab Xanh|Xanh Tươi sáng)|Biophilic Green/i);
    fireEvent.click(greenBtn);

    // Toggle socialize mode button
    const socializeBtn = screen.getByTitle(/Agents đi lại/i);
    fireEvent.click(socializeBtn);
    expect(toggleSocialize).toHaveBeenCalled();
  });

  it('renders in full viewport mode cleanly', () => {
    renderWithProviders(
      <OfficeCanvas
        agents={dummyAgents}
        fullViewport={true}
        paperCount={5}
        missionCount={2}
      />
    );

    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument();
  });
});
