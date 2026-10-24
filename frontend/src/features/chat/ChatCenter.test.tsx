import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { ChatCenter } from './ChatCenter';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('ChatCenter', () => {
  const mockSession = {
    id: 's-123',
    title: 'Active Research Session',
    chat_project: 'proj-1',
    messages: [
      { id: 'm-1', role: 'user', text: 'Hello AI Assistant' },
      { id: 'm-2', role: 'assistant', text: 'Hello researcher, how can I assist today?' },
    ],
    approvals: [
      {
        id: 'appr-1',
        name: 'run_simulation',
        reason: 'Run finite element simulation with 50,000 steps',
        status: 'pending',
      },
    ],
    memory_items: [
      {
        id: 'mem-1',
        type: 'fact',
        text: 'Critical turbulence transitions at Re=2300',
        status: 'pending',
      },
    ],
    turns: [],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    const s = useUIStore.getState();
    s.setLanguage('vi');
    s.setActiveSessionId('s-123');
    s.setActiveTopicId('topic-1');
  });

  it('fetches session and renders conversation messages, approvals and memory', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/chat/sessions/s-123')) {
        return mockSession;
      }
      if (url.includes('/api/chat/projects')) {
        return {
          projects: [{ id: 'proj-1', name: 'Fluid Turbulence Research', icon: 'folder' }],
        };
      }
      return {};
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});

    renderWithProviders(<ChatCenter />);

    await waitFor(() => {
      expect(screen.getByText('Hello AI Assistant')).toBeInTheDocument();
      expect(screen.getByText('Hello researcher, how can I assist today?')).toBeInTheDocument();
      expect(screen.getByText(/Run finite element simulation/i)).toBeInTheDocument();
      expect(screen.getByText(/Critical turbulence transitions at Re=2300/i)).toBeInTheDocument();
    });

    // Test sending a turn message via Composer
    const textarea = screen.getByPlaceholderText(/Hỏi bất kỳ điều gì hoặc gõ \//i);
    fireEvent.change(textarea, { target: { value: 'Compute Fourier transform' } });

    const sendBtn = screen.getByTitle(/Gửi/i);
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/chat/sessions/s-123/turns',
        expect.objectContaining({ text: 'Compute Fourier transform' })
      );
    });

    // Test accept proposal
    const acceptBtn = screen.getByText('Phê duyệt');
    fireEvent.click(acceptBtn);
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/chat/sessions/s-123/approvals/appr-1', {
        decision: 'approve',
      });
    });

    // Test memory decision
    const approveMemBtn = screen.getByText('Lưu');
    fireEvent.click(approveMemBtn);
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/memory/candidates/mem-1/approve', {});
    });
  });

  it('creates new session when sending without an active session id', async () => {
    useUIStore.getState().setActiveSessionId(null);

    const postSpy = vi.spyOn(api, 'post').mockImplementation(async (url: string) => {
      if (url === '/api/chat/sessions') {
        return { id: 's-created-999', title: 'New Auto Session' };
      }
      if (url.includes('/turns')) {
        return { id: 'turn-1', status: 'completed' };
      }
      return {};
    });

    vi.spyOn(api, 'get').mockResolvedValue({ projects: [] });

    renderWithProviders(<ChatCenter />);

    const textarea = screen.getByPlaceholderText(/Hỏi bất kỳ điều gì hoặc gõ \//i);
    fireEvent.change(textarea, { target: { value: 'Explore wave equation' } });

    const sendBtn = screen.getByTitle(/Gửi/i);
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/chat/sessions',
        expect.objectContaining({ title: 'Explore wave equation' })
      );
      expect(useUIStore.getState().activeSessionId).toBe('s-created-999');
    });
  });
});
