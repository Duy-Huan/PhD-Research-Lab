import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { DashboardView } from './DashboardView';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';

describe('DashboardView', () => {
  const mockDashboardData = {
    project: 'Physics-Informed Neural Operator',
    goal: 'Accelerate Navier-Stokes PDE solving by 100x using Fourier neural operators',
    outline_level: 3,
    outline_label: 'Drafting Methodology & Proofs',
    status: 'running',
    next_decision: 'Approve experiment hyperparameters for epoch 500',
    active_runs: [{ id: 'run-1', title: 'FNO Training Run #4' }],
    pending: [
      {
        kind: 'approval',
        id: 'pend-1',
        title: 'Merge Branch to Main Baseline',
        status: 'pending',
        text: 'Reviewer accepted validation loss decrease of 14%',
        session_id: 'sess-approval-1',
      },
    ],
    recent_runs: [
      {
        id: 'run-recent-1',
        title: 'Ablation Study on Grid Resolution',
        status: 'completed',
        provider: 'PyTorch/CUDA',
        done: 10,
        steps: 10,
      },
    ],
    pins: [
      {
        id: 'pin-1',
        title: 'Zero-shot generalization on Reynolds 10,000',
        status: 'verified',
        summary: 'Error below 2.4% across 5 benchmark seeds.',
      },
    ],
    resources: {
      cpu_percent: 42,
      ram_used_gb: 16,
      ram_total_gb: 64,
      active_slots: 2,
      max_slots: 4,
    },
    gpus: [
      {
        index: 0,
        name: 'NVIDIA RTX 4090',
        memory_used_mb: 8192,
        memory_total_mb: 24576,
        utilization: 88,
      },
    ],
    providers: [
      { id: 'openai', name: 'OpenAI GPT-4o', ready: true },
      { id: 'anthropic', name: 'Claude 3.5 Sonnet', ready: true },
      { id: 'ollama', name: 'Local Ollama (DeepSeek-R1)', ready: false },
    ],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders dashboard with complete KPI metrics, GPU status, pending approvals, and providers', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(mockDashboardData);
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});

    renderWithProviders(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByText(/Trung tâm Điều hành Nghiên cứu/i)).toBeInTheDocument();
      expect(screen.getByText(/Physics-Informed Neural Operator/i)).toBeInTheDocument();
      expect(screen.getByText(/Cấp 3 \/ 5/i)).toBeInTheDocument();
      expect(screen.getByText(/NVIDIA RTX 4090/i)).toBeInTheDocument();
      expect(screen.getByText(/Merge Branch to Main Baseline/i)).toBeInTheDocument();
      expect(screen.getByText(/Ablation Study on Grid Resolution/i)).toBeInTheDocument();
      expect(screen.getByText(/Zero-shot generalization on Reynolds 10,000/i)).toBeInTheDocument();
      expect(screen.getByText(/OpenAI GPT-4o/i)).toBeInTheDocument();
    });

    // Test Unload VRAM action
    const unloadBtn = screen.getByTitle(/Giải phóng các mô hình cục bộ/i);
    fireEvent.click(unloadBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/models/unload', { engine: 'all', force: true });

    // Test Navigation actions
    const office3dBtn = screen.getByText(/Phòng Lab 3D/i);
    fireEvent.click(office3dBtn);
    expect(useUIStore.getState().mainView).toBe('office3d');
    expect(useUIStore.getState().officeFullscreen).toBe(true);

    const openOutlineBtn = screen.getByText(/Mở Đề cương 5 cấp/i);
    fireEvent.click(openOutlineBtn);
    expect(useUIStore.getState().drawerKind).toBe('outline');

    const openMissionsBtn = screen.getByText(/Mở Nhiệm vụ/i);
    fireEvent.click(openMissionsBtn);
    expect(useUIStore.getState().drawerKind).toBe('missions');

    // Test Refresh and Back to Chat
    const refreshBtn = screen.getByText(/Làm mới/i);
    fireEvent.click(refreshBtn);

    const backChatBtn = screen.getByText(/Quay lại Hội thoại/i);
    fireEvent.click(backChatBtn);
    expect(useUIStore.getState().mainView).toBe('chat');

    const reviewPendingBtn = screen.getByText(/Xem & Duyệt/i);
    fireEvent.click(reviewPendingBtn);
    expect(useUIStore.getState().activeSessionId).toBe('sess-approval-1');
    expect(useUIStore.getState().mainView).toBe('chat');
  });

  it('handles unload VRAM error gracefully', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(mockDashboardData);
    vi.spyOn(api, 'post').mockRejectedValue(new Error('CUDA out of memory error'));
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

    renderWithProviders(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByText(/Trung tâm Điều hành Nghiên cứu/i)).toBeInTheDocument();
    });

    const unloadBtn = screen.getByTitle(/Giải phóng các mô hình cục bộ/i);
    fireEvent.click(unloadBtn);

    // 6.6.3 QA: the failure is shown on the page, not in a browser alert.
    expect(await screen.findByRole('alert')).toHaveTextContent(/Không thể giải phóng VRAM: CUDA out of memory error/);
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it('renders CPU-only fallback and empty states gracefully', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      project: 'Empty Lab',
      goal: '',
      outline_level: 0,
      outline_label: '',
      status: 'idle',
      pending: [],
      recent_runs: [],
      pins: [],
      gpus: [],
      providers: [],
    });

    renderWithProviders(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByText(/Chế độ CPU \/ Cloud API/i)).toBeInTheDocument();
      expect(screen.getByText(/Tất cả đề xuất và thực thi đều đã được xử lý/i)).toBeInTheDocument();
      expect(screen.getByText(/Chưa có tiến trình chạy nền nào/i)).toBeInTheDocument();
      expect(screen.getByText(/Chưa có kết quả ghim nào/i)).toBeInTheDocument();
    });
  });
});
