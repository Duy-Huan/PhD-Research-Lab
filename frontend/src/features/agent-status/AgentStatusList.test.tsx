import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { AgentStatusList } from './AgentStatusList';
import type { AgentOfficeViewModel } from '../../shared/api/types';

describe('AgentStatusList', () => {
  it('renders agents roster and handles agent click', () => {
    const onSelect = vi.fn();
    const mockAgents: AgentOfficeViewModel[] = [
      {
        agentId: 'agent-1',
        projectId: 'p-1',
        displayName: 'Prof. AI Orchestrator',
        role: 'Principal Investigator',
        engine: 'cloud:google',
        presence: 'running',
        activity: 'reviewing',
        lastObservedAt: '2026-10-24T00:00:00Z',
        canInspect: true,
        canPause: true,
        canResume: false,
        hasApprovalRequest: false,
      },
      {
        agentId: 'agent-2',
        projectId: 'p-1',
        displayName: 'OpenCode Sandbox',
        role: 'Sandbox Engineer',
        engine: 'opencode',
        presence: 'awaiting_approval',
        activity: 'executing',
        lastObservedAt: '2026-10-24T00:00:00Z',
        canInspect: true,
        canPause: false,
        canResume: false,
        hasApprovalRequest: true,
      },
      {
        agentId: 'agent-3',
        projectId: 'p-1',
        displayName: 'Reviewer Node',
        role: 'Peer Review',
        engine: 'claude',
        presence: 'failed',
        activity: 'reviewing',
        lastObservedAt: '2026-10-24T00:00:00Z',
        canInspect: true,
        canPause: false,
        canResume: false,
        hasApprovalRequest: false,
      },
    ];

    renderWithProviders(<AgentStatusList agents={mockAgents} onSelectAgent={onSelect} />);

    expect(screen.getByText('Prof. AI Orchestrator')).toBeInTheDocument();
    expect(screen.getByText('OpenCode Sandbox')).toBeInTheDocument();
    expect(screen.getByText('Reviewer Node')).toBeInTheDocument();
    expect(screen.getByText('AWAITING_APPROVAL')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Prof. AI Orchestrator'));
    expect(onSelect).toHaveBeenCalledWith(mockAgents[0]);
  });

  it('triggers onEditProfile when edit button is clicked', () => {
    const onEditProfile = vi.fn();
    const mockAgent: AgentOfficeViewModel = {
      agentId: 'agent-1',
      projectId: 'p-1',
      displayName: 'Prof. AI Orchestrator',
      role: 'Principal Investigator',
      engine: 'cloud:google',
      presence: 'running',
      activity: 'reviewing',
      lastObservedAt: '2026-10-24T00:00:00Z',
      canInspect: true,
      canPause: true,
      canResume: false,
      hasApprovalRequest: false,
    };

    renderWithProviders(<AgentStatusList agents={[mockAgent]} onEditProfile={onEditProfile} />);

    const editBtn = screen.getByTitle('Chỉnh sửa hồ sơ & Đặt tên');
    fireEvent.click(editBtn);
    expect(onEditProfile).toHaveBeenCalledWith(mockAgent);
  });
});
