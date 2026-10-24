import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { WorkstreamMonitor } from './WorkstreamMonitor';
import { useUIStore } from '../../shared/state/uiStore';
import { api, ApiError } from '../../shared/api/client';

describe('WorkstreamMonitor', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders prompt when no active topic selected', () => {
    useUIStore.getState().setActiveTopicId(null);
    renderWithProviders(<WorkstreamMonitor />);
    expect(
      screen.getByText(/Vui lòng chọn một Topic để xem phân luồng Workstreams/i)
    ).toBeInTheDocument();
  });

  it('renders workstreams and handles CAS output conflict', async () => {
    useUIStore.getState().setActiveTopicId('topic-ws');

    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/missions/mission-ws/workstreams')) {
        return {
          workstreams: [
            { id: 'ws-1', name: 'Literature Survey Stream', status: 'completed' },
            { id: 'ws-2', name: 'Experimental Stream', status: 'in_progress' },
          ],
          outputs: {
            'benchmark_table': {
              key: 'benchmark_table',
              revision: 1,
              source_task: 'task-eval',
              team_id: 'team-exp',
              note: 'Initial results',
            },
          },
          disputes: [],
        };
      }
      if (url.includes('/missions')) {
        return {
          missions: [
            {
              id: 'mission-ws',
              topic_id: 'topic-ws',
              status: 'running',
              payload: {
                spec: {
                  objective: 'Collaborative Multi-Stream Mission',
                  collaboration: {
                    workstreams: [
                      { id: 'ws-1', objective: 'Literature Survey Stream', lead_role: 'feynman' },
                    ],
                  },
                },
              },
            },
          ],
        };
      }
      return {};
    });

    // Mock 409 conflict on CAS output
    vi.spyOn(api, 'post').mockRejectedValueOnce(
      new ApiError(409, 'Conflict', 'CONFLICT', 'Output already updated')
    );

    renderWithProviders(<WorkstreamMonitor />);

    await waitFor(() => {
      expect(screen.getByText(/Literature Survey Stream/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Đăng ký Canonical Output \(Compare-and-Swap\)/i)
      ).toBeInTheDocument();
    });

    // Open CAS modal
    fireEvent.click(
      screen.getByText(/Đăng ký Canonical Output \(Compare-and-Swap\)/i)
    );

    const keyInput = screen.getByPlaceholderText(/research-report/i);
    fireEvent.change(keyInput, { target: { value: 'benchmark_table' } });

    // Submit CAS output
    const submitBtn = screen.getByText('Gửi CAS');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Xung đột phiên bản/i)).toBeInTheDocument();
    });
  });
});
