import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { IntelligenceHubPanel } from './IntelligenceHubPanel';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('IntelligenceHubPanel', () => {
  const mockMissions = [
    {
      id: 'mission-alpha',
      payload: {
        spec: {
          objective: 'Benchmark Diffusion Super-Resolution',
        },
      },
    },
  ];

  const mockArtifacts = [
    {
      artifact_id: 'urap-art-001',
      artifact_type: 'experiment_result',
      verification: { status: 'auto_screened' },
      content: { sha256: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08' },
      producer: { runtime_id: 'phdlab-core' },
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopicId('topic-1');
  });

  it('renders prompt when no topic is selected', () => {
    useUIStore.getState().setActiveTopicId(null);
    renderWithProviders(<IntelligenceHubPanel />);
    expect(screen.getByText(/Vui lòng chọn một Topic/i)).toBeInTheDocument();
  });

  it('navigates through all 4 tabs and executes intelligence actions', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/missions') && !url.includes('/trace')) {
        return { missions: mockMissions };
      }
      if (url.includes('/artifacts-urap')) {
        return { items: mockArtifacts, count: 1 };
      }
      if (url.includes('/lineage')) {
        return {
          nodes: [{ id: 'n1', label: 'Raw Dataset' }, { id: 'n2', label: 'Trained Weights' }],
          edges: [{ from: 'n1', to: 'n2' }],
        };
      }
      if (url.includes('/trace')) {
        return {
          trace_id: 'trace-xyz-789',
          mission_status: 'completed',
          task_spans: [{ id: 'span-1' }],
          trace_events: [
            {
              id: 'tr-ev-1',
              seq: 1,
              event_type: 'task_dispatched',
              span_id: 'span-1',
              payload: { worker: 'Agent-Analyst' },
            },
          ],
          routing_decisions: [],
        };
      }
      return {};
    });

    const postSpy = vi.spyOn(api, 'post').mockImplementation(async (url: string) => {
      if (url.includes('/verify-integrity')) {
        return {
          valid: true,
          artifact_id: 'urap-art-001',
          detail: 'SHA-256 matched bit-for-bit',
          stale_downstream: [],
        };
      }
      if (url.includes('/context-pack')) {
        return {
          context_pack_id: 'cpack-01',
          role_focus: 'literature_reviewer',
          budget: { token_estimate: 2100, max_tokens: 3500 },
          retrieval: { injection_attempts_blocked: 2 },
          constraints: { prohibited_actions: ['modify_filesystem'] },
        };
      }
      if (url.includes('/route-preview')) {
        return {
          selected_engine: 'deterministic',
          status: 'ok',
          llm_calls: 0,
          metered_api_fallback: 'disabled',
          rationale: 'Deterministic algorithm matched for paper discovery.',
        };
      }
      if (url.includes('/reproducibility-export')) {
        return {
          export_id: 'repro-pack-001',
          bundle_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
          files: ['ro-crate-metadata.json', 'requirements.lock', 'checksums.sha256'],
        };
      }
      if (url.includes('/reproducibility-replay')) {
        return {
          passed: true,
          status: 'verified_exact',
          verified_file_count: 3,
          tolerance: '1e-6',
        };
      }
      if (url.includes('/report-manifest')) {
        return {
          markdown: '# Unified Research Technical Report\n\n- Verified Claims: 4\n- Figures: 2',
        };
      }
      return {};
    });

    renderWithProviders(<IntelligenceHubPanel />);

    // TAB 1: URAP
    await waitFor(() => {
      expect(screen.getByText(/Research Intelligence Hub/i)).toBeInTheDocument();
      expect(screen.getByText(/urap-art-001/i)).toBeInTheDocument();
      expect(screen.getByText(/AUTO_SCREENED/i)).toBeInTheDocument();
      expect(screen.getByText(/Lineage Graph/i)).toBeInTheDocument();
    });

    // Test verify SHA-256 button
    const verifyShaBtn = screen.getByText(/Kiểm định SHA-256 trên đĩa/i);
    fireEvent.click(verifyShaBtn);
    await waitFor(() => {
      expect(screen.getByText(/SHA-256 matched bit-for-bit/i)).toBeInTheDocument();
    });

    // Test sample artifact button
    const sampleArtBtn = screen.getByText(/\+ Ghi nhận Artifact mẫu/i);
    fireEvent.click(sampleArtBtn);
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/research/topics/topic-1/artifacts-urap',
        expect.anything()
      );
    });

    // TAB 2: Mission Trace
    const traceTabBtn = screen.getByText(/Mission Trace/i);
    fireEvent.click(traceTabBtn);
    await waitFor(() => {
      expect(screen.getByText(/trace-xyz-789/i)).toBeInTheDocument();
      expect(screen.getByText(/task_dispatched/i)).toBeInTheDocument();
    });

    // TAB 3: Context & Smart Router
    const contextTabBtn = screen.getByText(/Context & Smart Router/i);
    fireEvent.click(contextTabBtn);

    const makePackBtn = screen.getByText(/Tạo Context Pack/i);
    fireEvent.click(makePackBtn);
    await waitFor(() => {
      expect(screen.getByText(/Prompt Injections bị chặn/i)).toBeInTheDocument();
      expect(screen.getByText(/modify_filesystem/i)).toBeInTheDocument();
    });

    const routeCheckBtn = screen.getByText(/Kiểm tra Định tuyến/i);
    fireEvent.click(routeCheckBtn);
    await waitFor(() => {
      expect(screen.getByText(/Deterministic algorithm matched/i)).toBeInTheDocument();
    });

    // TAB 4: RO-Crate & Report
    const reproTabBtn = screen.getByText(/RO-Crate & Report/i);
    fireEvent.click(reproTabBtn);

    const exportBtn = screen.getByText(/Đóng gói RO-Crate \(\.zip\)/i);
    fireEvent.click(exportBtn);
    await waitFor(() => {
      expect(screen.getByText(/repro-pack-001/i)).toBeInTheDocument();
      expect(screen.getAllByText(/ro-crate-metadata\.json/i).length).toBeGreaterThanOrEqual(1);
    });

    const replayBtn = screen.getByText(/Chạy Kiểm định Replay Độc lập/i);
    fireEvent.click(replayBtn);
    await waitFor(() => {
      expect(screen.getByText(/VERIFIED_EXACT/i)).toBeInTheDocument();
    });

    const reportBtn = screen.getByText(/Kết xuất Báo cáo Tổng hợp/i);
    fireEvent.click(reportBtn);
    await waitFor(() => {
      expect(screen.getByText(/Unified Research Technical Report/i)).toBeInTheDocument();
    });
  });
});
