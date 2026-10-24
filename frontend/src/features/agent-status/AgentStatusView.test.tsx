import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { AgentStatusView } from './AgentStatusView';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('AgentStatusView', () => {
  const mockConfig = {
    projects: [{ name: 'Default', data_dir: '/path/data' }],
    active_project: { name: 'Default', data_dir: '/path/data' },
    agent_modes: {
      assistant: 'cloud:google',
      research: 'claude_code',
      reviewer: 'codex',
      utility: 'antigravity',
    },
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    const s = useUIStore.getState();
    s.setLanguage('vi');
    s.setProject({ name: 'Default', data_dir: '/path/data' });
    s.setOfficeFullscreen(false);
    s.setOfficeChatOpen(true);
    s.setSelectedLabObject(null);
    s.setAgentStatusView('office3d');

    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/config')) {
        return mockConfig;
      }
      if (url.includes('/api/papers') || url.includes('/api/library')) {
        return {
          papers: [{ id: 'p1', title: 'Paper 1' }],
          references: [{ id: 'p1', title: 'Paper 1' }],
        };
      }
      if (url.includes('/api/research/topics')) {
        return { missions: [] };
      }
      return {};
    });

    vi.spyOn(api, 'post').mockResolvedValue({ id: 'sess-new' } as any);
  });

  it('renders top command bar and 3D quick action pills', async () => {
    renderWithProviders(<AgentStatusView />);

    await waitFor(() => {
      expect(screen.getAllByText(/PhD Research Lab/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Library \(1\)/i)).toBeInTheDocument();
    });
  });

  it('allows clicking 3D object buttons to open corresponding workflow in dock', async () => {
    renderWithProviders(<AgentStatusView />);

    // Click Outline button
    const outlineBtn = screen.getByText('Outline');
    fireEvent.click(outlineBtn);

    expect(useUIStore.getState().selectedLabObject).toBe('outline');
    expect(useUIStore.getState().officeChatOpen).toBe(true);

    // Click HPC button
    const hpcBtn = screen.getByTitle('HPC Server & OpenCode');
    fireEvent.click(hpcBtn);
    expect(useUIStore.getState().selectedLabObject).toBe('hpc_opencode');

    // Click Review button
    const reviewBtn = screen.getByTitle('Peer Review Roundtable');
    fireEvent.click(reviewBtn);
    expect(useUIStore.getState().selectedLabObject).toBe('roundtable_review');

    // Click Figures button
    const figureBtn = screen.getByTitle('Figure Hologram Table');
    fireEvent.click(figureBtn);
    expect(useUIStore.getState().selectedLabObject).toBe('figure_studio');
  });

  it('switches between office3d, list matrix (2D), and live timeline views', async () => {
    renderWithProviders(<AgentStatusView />);

    // Switch to 2D List Matrix
    const listBtn = screen.getByTitle('2D Matrix');
    fireEvent.click(listBtn);
    expect(useUIStore.getState().agentStatusView).toBe('list');
    await waitFor(() => {
      expect(screen.getByText(/Ma trận Trạng thái/i)).toBeInTheDocument();
    });

    // Switch to Timeline
    const timelineBtn = screen.getByTitle('Event Log');
    fireEvent.click(timelineBtn);
    expect(useUIStore.getState().agentStatusView).toBe('timeline');
    await waitFor(() => {
      expect(screen.getByText(/Nhật ký Hoạt động của các AI Agents/i)).toBeInTheDocument();
    });

    // Switch back to 3D Office
    const office3dBtn = screen.getByTitle('3D Lab');
    fireEvent.click(office3dBtn);
    expect(useUIStore.getState().agentStatusView).toBe('office3d');
  });

  it('toggles roster, fullscreen, and direct agent interaction in dock', async () => {
    renderWithProviders(<AgentStatusView />);

    // Roster is initially open
    await waitFor(() => {
      expect(screen.getByText(/Nhân sự AI trong Lab/i)).toBeInTheDocument();
    });

    // Toggle Roster off
    const rosterBtn = screen.getByTitle(/Danh sách Agents/i);
    fireEvent.click(rosterBtn);
    expect(screen.queryByText(/Nhân sự AI trong Lab/i)).not.toBeInTheDocument();

    // Toggle Roster back on
    fireEvent.click(rosterBtn);
    expect(screen.getByText(/Nhân sự AI trong Lab/i)).toBeInTheDocument();

    // Toggle Fullscreen
    const fullscreenBtn = screen.getByTitle(/Toàn màn hình/i);
    fireEvent.click(fullscreenBtn);
    expect(useUIStore.getState().officeFullscreen).toBe(true);

    // Switch dock to direct agent chat
    const agentTabBtn = screen.getByText(/Trò chuyện Agent/i);
    fireEvent.click(agentTabBtn);
    await waitFor(() => {
      expect(screen.getByText(/Hỏi Trạng thái/i)).toBeInTheDocument();
    });

    // Click a preset agent question
    const askStatusBtn = screen.getByText(/Hỏi Trạng thái/i);
    fireEvent.click(askStatusBtn);
  });

  it('allows customizing an agent personal profile and reflects custom name in lab', async () => {
    renderWithProviders(<AgentStatusView />);

    await waitFor(() => {
      expect(screen.getByText(/Nhân sự AI trong Lab/i)).toBeInTheDocument();
    });

    // Find custom profile buttons in floating roster
    const customizeBtns = screen.getAllByTitle(/Tùy biến hồ sơ & Đặt tên/i);
    expect(customizeBtns.length).toBeGreaterThanOrEqual(1);

    // Click customize for first agent
    fireEvent.click(customizeBtns[0]);

    // Modal should be open
    await waitFor(() => {
      expect(screen.getByText(/Hồ sơ Cá nhân & Đặt tên riêng cho AI Agent/i)).toBeInTheDocument();
    });

    // Enter custom name
    const nameInput = screen.getByLabelText(/Tên riêng theo sở thích của bạn/i);
    fireEvent.change(nameInput, { target: { value: 'GS. Stephen Hawking' } });

    // Save
    const saveBtn = screen.getByRole('button', { name: /Lưu Hồ sơ/i });
    fireEvent.click(saveBtn);

    // Verify custom name appears in the roster
    await waitFor(() => {
      expect(screen.getAllByText('GS. Stephen Hawking').length).toBeGreaterThanOrEqual(1);
    });
  });
});
