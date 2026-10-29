import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { CustomHarnessStudio } from './CustomHarnessStudio';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';

describe('CustomHarnessStudio', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockTools = [
    {
      id: 'lm_evaluation_harness',
      name: 'LM-Evaluation-Harness (EleutherAI)',
      category: 'benchmark',
      icon: 'Gauge',
      description: 'Chuẩn mở đánh giá mô hình ngôn ngữ lớn (MMLU, GSM8K).',
      description_en: 'Open standard evaluation harness for LLMs.',
      default_params: { tasks: 'gsm8k,mmlu', min_pass_score: 0.75 },
      available_metrics: ['acc', 'acc_norm'],
      docs_url: 'https://github.com/EleutherAI/lm-evaluation-harness',
    },
    {
      id: 'inspect_ai',
      name: 'Inspect AI (UK AI Safety Institute)',
      category: 'agent_eval',
      icon: 'ShieldCheck',
      description: 'Framework đánh giá tự động đa bước cho AI Agents.',
      description_en: 'Multi-step automated evaluation framework.',
      default_params: { eval_suite: 'agent_reasoning', min_pass_rate: 0.8 },
      available_metrics: ['pass_at_1', 'safety_score'],
      docs_url: 'https://github.com/UKGovernmentBEIS/inspect_ai',
    },
  ];

  const mockWorkflows = [
    {
      id: 'hw-preset-llm-eval',
      name: 'Quy trình Đánh giá Năng lực Mô hình (LM-Eval + Safety)',
      description: 'Tích hợp LM-Evaluation-Harness và Inspect AI',
      is_preset: true,
      nodes: [
        {
          id: 'node-1',
          type: 'harnessNode',
          position: { x: 50, y: 50 },
          data: {
            label: 'LM Evaluation Benchmark',
            tool: 'lm_evaluation_harness',
            category: 'benchmark',
            params: { tasks: 'gsm8k,mmlu' },
            status: 'idle',
          },
        },
      ],
      edges: [],
    },
  ];

  it('renders studio, loads tools catalog and displays workflow nodes', async () => {
    vi.spyOn(api, 'get').mockImplementation((url: string) => {
      if (url.includes('/api/harness/tools')) {
        return Promise.resolve({ tools: mockTools });
      }
      if (url.includes('/api/harness/workflows')) {
        return Promise.resolve({ workflows: mockWorkflows });
      }
      return Promise.resolve({});
    });

    renderWithProviders(<CustomHarnessStudio />);

    await waitFor(() => {
      expect(screen.getByText(/Harness Studio & Thiết kế Quy trình/i)).toBeInTheDocument();
      expect(screen.getByText(/LM-Evaluation-Harness/i)).toBeInTheDocument();
      expect(screen.getByText(/Inspect AI/i)).toBeInTheDocument();
    });

    // Check action buttons
    expect(screen.getByRole('button', { name: /Chạy Harness/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Lưu/i })).toBeInTheDocument();
  });

  it('displays blocked execution without inventing benchmark measurements', async () => {
    vi.spyOn(api, 'get').mockImplementation((url: string) => {
      if (url.includes('/api/harness/tools')) {
        return Promise.resolve({ tools: mockTools });
      }
      if (url.includes('/api/harness/workflows')) {
        return Promise.resolve({ workflows: mockWorkflows });
      }
      return Promise.resolve({});
    });

    const execSpy = vi.spyOn(api, 'post').mockResolvedValue({
      execution_id: 'exec-test-123',
      workflow_id: 'hw-preset-llm-eval',
      workflow_name: 'Quy trình Đánh giá Năng lực Mô hình',
      status: 'blocked',
      passed: false,
      total_duration_s: 1.25,
      nodes_count: 1,
      node_results: {
        'node-1': {
          node_id: 'node-1',
          label: 'LM Evaluation Benchmark',
          tool_id: 'lm_evaluation_harness',
          tool_name: 'LM-Evaluation-Harness',
          status: 'blocked',
          passed: false,
          duration_s: 0.45,
          metrics: {},
          summary: 'No executable benchmark adapter is configured; no evaluation ran.',
          execution_mode: 'NOT_EXECUTED',
          timestamp: '2026-10-24T12:00:00Z',
        },
      },
      created_at: '2026-10-24T12:00:00Z',
    });

    renderWithProviders(<CustomHarnessStudio />);

    await waitFor(() => {
      expect(screen.getByText(/LM Evaluation Benchmark/i)).toBeInTheDocument();
    });

    const runBtn = screen.getByRole('button', { name: /Chạy Harness/i });
    fireEvent.click(runBtn);

    await waitFor(() => {
      expect(execSpy).toHaveBeenCalledWith(
        '/api/harness/execute',
        expect.objectContaining({
          workflow: expect.any(Object),
        })
      );
      expect(screen.getByText(/Báo cáo Thực thi Harness:/i)).toBeInTheDocument();
      expect(screen.getByText(/no evaluation ran/i)).toBeInTheDocument();
      expect(screen.queryByText(/84.0%/i)).not.toBeInTheDocument();
    });
  });

  it('allows switching to automated agent flow', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ tools: [], workflows: [] });
    const switchSpy = vi.fn();

    renderWithProviders(<CustomHarnessStudio onSwitchToAutomated={switchSpy} />);

    await waitFor(() => {
      expect(screen.getByText(/Quy trình Tự động/i)).toBeInTheDocument();
    });

    const autoBtn = screen.getByRole('button', { name: /Quy trình Tự động/i });
    fireEvent.click(autoBtn);
    expect(switchSpy).toHaveBeenCalled();
  });

  // agent/PLAN_6.6.4_L3.md A-QA, found by frontend/e2e/harness_levels.spec.ts.
  it('has no mode switch when there is no automated view to switch to', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ tools: [], workflows: [] });
    renderWithProviders(<CustomHarnessStudio />);
    await screen.findByRole('button', { name: /Chạy Harness/i });
    expect(screen.queryByRole('button', { name: /Quy trình Tự động/i })).not.toBeInTheDocument();
  });

  it('shows English agent names and descriptions in the English interface', async () => {
    useUIStore.getState().setLanguage('en');
    vi.spyOn(api, 'get').mockImplementation((url: string) => Promise.resolve(url.includes('/api/harness/agents') ? { agents: [{
      id: 'agent-literature-specialist', name: 'Chuyên viên Tổng quan Văn hiến (Literature Specialist)', name_en: 'Literature Specialist',
      role: 'literature', purpose: 'Tìm kiếm tài liệu học thuật', purpose_en: 'Searches scholarly literature',
      system_prompt: 'x', provider: 'auto', skills: [], mcp_tools: [], memory_scope: 'project', permissions: [],
      max_tokens: 1, timeout_seconds: 1, max_retries: 0 }] } : { tools: [], workflows: [] }));
    renderWithProviders(<CustomHarnessStudio />);
    fireEvent.click(await screen.findByTitle('Build the agent team'));
    expect(await screen.findByText('Literature Specialist')).toBeInTheDocument();
    expect(screen.getByText('Searches scholarly literature')).toBeInTheDocument();
    expect(screen.queryByText(/Chuyên viên/)).not.toBeInTheDocument();
    useUIStore.getState().setLanguage('vi');
  });
});
