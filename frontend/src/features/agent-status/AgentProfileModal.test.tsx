import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { AgentProfileModal } from './AgentProfileModal';
import { useUIStore } from '../../shared/state/uiStore';
import type { AgentOfficeViewModel } from '../../shared/api/types';

describe('AgentProfileModal', () => {
  const dummyAgent: AgentOfficeViewModel = {
    agentId: 'faculty_pi_orchestrator',
    projectId: 'p-1',
    displayName: 'Prof. AI Orchestrator (PI)',
    role: 'Principal Investigator',
    engine: 'claude',
    presence: 'idle',
    activity: 'reading',
    lastObservedAt: '2026-10-24T00:00:00Z',
    canInspect: true,
    canPause: false,
    canResume: false,
    hasApprovalRequest: false,
    archetype: 'pi',
    personality: 'Điềm tĩnh, chiến lược',
    speechBubble: 'Sẵn sàng thảo luận Đề cương',
  };

  beforeEach(() => {
    const s = useUIStore.getState();
    s.setLanguage('vi');
    s.resetAgentProfile('faculty_pi_orchestrator');
  });

  it('renders nothing when isOpen is false', () => {
    const onClose = vi.fn();
    const { container } = renderWithProviders(
      <AgentProfileModal agent={dummyAgent} isOpen={false} onClose={onClose} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders modal dialog with agent details and form controls when open', () => {
    const onClose = vi.fn();
    renderWithProviders(
      <AgentProfileModal agent={dummyAgent} isOpen={true} onClose={onClose} />
    );

    expect(
      screen.getByText(/Hồ sơ Cá nhân & Đặt tên riêng cho AI Agent/i)
    ).toBeInTheDocument();
    expect(screen.getAllByText('Prof. AI Orchestrator (PI)').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText(/Tên riêng theo sở thích của bạn/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Chức danh \/ Vai trò hiển thị/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Tính cách & Phong cách nghiên cứu/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Câu thoại \/ Lời chào 3D mặc định/i)).toBeInTheDocument();
  });

  it('allows user to customize name, role, greeting, coat color and saves to store', () => {
    const onClose = vi.fn();
    renderWithProviders(
      <AgentProfileModal agent={dummyAgent} isOpen={true} onClose={onClose} />
    );

    // Enter custom name
    const nameInput = screen.getByLabelText(/Tên riêng theo sở thích của bạn/i);
    fireEvent.change(nameInput, { target: { value: 'GS. Minh Trí' } });

    // Enter custom title
    const titleInput = screen.getByLabelText(/Chức danh \/ Vai trò hiển thị/i);
    fireEvent.change(titleInput, { target: { value: 'Giáo sư Cố vấn Cấp cao' } });

    // Enter custom greeting
    const greetingInput = screen.getByLabelText(/Câu thoại \/ Lời chào 3D mặc định/i);
    fireEvent.change(greetingInput, { target: { value: 'Chào bạn! Hôm nay cần tôi hỗ trợ gì?' } });

    // Pick Emerald Tech color swatch
    const emeraldSwatch = screen.getByTitle('Xanh Ngọc Công nghệ');
    fireEvent.click(emeraldSwatch);

    // Save profile
    const saveBtn = screen.getByRole('button', { name: /Lưu Hồ sơ/i });
    fireEvent.click(saveBtn);

    expect(onClose).toHaveBeenCalled();

    // Verify stored state
    const saved = useUIStore.getState().agentProfiles['faculty_pi_orchestrator'];
    expect(saved).toBeDefined();
    expect(saved?.customName).toBe('GS. Minh Trí');
    expect(saved?.customTitle).toBe('Giáo sư Cố vấn Cấp cao');
    expect(saved?.customGreeting).toBe('Chào bạn! Hôm nay cần tôi hỗ trợ gì?');
    expect(saved?.customColor).toBe('#065f46');
  });

  it('allows resetting profile to original system defaults', () => {
    // Pre-populate custom profile
    useUIStore.getState().updateAgentProfile('faculty_pi_orchestrator', {
      customName: 'Custom Name',
      customColor: '#7f1d1d',
    });

    const onClose = vi.fn();
    renderWithProviders(
      <AgentProfileModal agent={dummyAgent} isOpen={true} onClose={onClose} />
    );

    // Reset button should be visible
    const resetBtn = screen.getByRole('button', { name: /Khôi phục mặc định/i });
    fireEvent.click(resetBtn);

    const profile = useUIStore.getState().agentProfiles['faculty_pi_orchestrator'];
    expect(profile).toBeUndefined();
  });
});
