import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { OpenCodePanel } from './OpenCodePanel';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('OpenCodePanel', () => {
  const mockStatus = {
    state: 'ready',
    active_sessions: 1,
    base_url: 'http://127.0.0.1:4097',
    detail: 'OpenCode Loopback v6.4.1 Active',
    metered_api_allowed: false,
    provider_priority: ['Local Ollama', 'LM Studio', 'Anthropic Free Tier'],
  };

  const mockSession = {
    id: 'oc-sess-1',
    topic_id: 'topic-1',
    status: 'running',
    created: '2026-10-24T00:00:00Z',
    payload: {
      spec: {
        goal: 'Benchmark LLM runtime parallel with bounded memory',
      },
      blocking_reason: 'Waiting for filesystem mutation approval',
    },
    approvals: [
      {
        id: 'appr-99',
        risk: 'high',
        action: 'write_file',
        payload: { scope: 'opencode_prj/tests/test_hpc.py' },
        status: 'pending',
      },
    ],
    events: [
      {
        id: 'ev-1',
        seq: 1,
        event_type: 'agent_start',
        fingerprint: 'sha256-abcdef0123456789',
        payload: { agent: 'hpc_coder', status: 'initialized' },
      },
      {
        id: 'ev-2',
        seq: 2,
        event_type: 'code_generated',
        fingerprint: 'sha256-9876543210fedcba',
        payload: { files_modified: ['opencode_prj/src/core.py'] },
      },
    ],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopicId('topic-1');
  });

  it('renders prompt when no topic selected', () => {
    useUIStore.getState().setActiveTopicId(null);
    renderWithProviders(<OpenCodePanel />);
    expect(screen.getByText(/Vui lòng chọn một Topic/i)).toBeInTheDocument();
  });

  it('renders OpenCode telemetry, handles workspace init, form submit, and approvals', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/opencode/status')) {
        return mockStatus;
      }
      if (url.includes('/opencode/sessions')) {
        return { sessions: [mockSession] };
      }
      return {};
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});

    renderWithProviders(<OpenCodePanel />);

    await waitFor(() => {
      expect(screen.getByText(/OpenCode Parallel Core Runtime/i)).toBeInTheDocument();
      expect(screen.getByText(/Loopback Only/i)).toBeInTheDocument();
      expect(screen.getByText(/Benchmark LLM runtime parallel/i)).toBeInTheDocument();
      expect(screen.getByText(/Waiting for filesystem mutation approval/i)).toBeInTheDocument();
      expect(screen.getByText(/Yêu cầu phê duyệt hành động rủi ro/i)).toBeInTheDocument();
      expect(screen.getByText(/Luồng sự kiện đã khử trùng lặp SHA-256/i)).toBeInTheDocument();
    });

    // Test Workspace Init
    const initWorkspaceBtn = screen.getByText(/Khởi tạo opencode_prj/i);
    fireEvent.click(initWorkspaceBtn);
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/research/topics/topic-1/opencode/workspace',
        { enable_bridge_plugin: true }
      );
    });

    // Test Form Submit (Launch bounded session)
    const goalTextarea = screen.getByPlaceholderText(/Nhập mục tiêu kỹ thuật/i);
    fireEvent.change(goalTextarea, { target: { value: 'Write PDE unit test' } });

    const launchBtn = screen.getByText(/Khởi chạy Phiên OpenCode/i);
    fireEvent.click(launchBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/research/topics/topic-1/opencode/sessions',
        expect.objectContaining({
          goal: 'Write PDE unit test',
        })
      );
    });

    // Test Reconcile button
    const reconcileBtn = screen.getByTitle(/Đồng bộ trạng thái & artifact/i);
    fireEvent.click(reconcileBtn);
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/research/topics/topic-1/opencode/sessions/oc-sess-1/reconcile', {
        simulate_gap: false,
      });
    });

    // Test Cancel session button
    const cancelBtn = screen.getByText(/Huỷ/i);
    fireEvent.click(cancelBtn);
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/research/topics/topic-1/opencode/sessions/oc-sess-1/cancel');
    });

    // Test Approve approval button
    const approveBtn = screen.getByText(/Chấp thuận/i);
    fireEvent.click(approveBtn);
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/research/topics/topic-1/opencode/sessions/oc-sess-1/approvals/appr-99',
        expect.objectContaining({ decision: 'approve' })
      );
    });
  });
});
