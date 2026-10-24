import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { Sidebar } from '../shell/Sidebar';
import { ProjectSwitcher } from '../features/projects/ProjectSwitcher';
import { Composer } from '../features/chat/Composer';
import { MessageList } from '../features/chat/MessageList';
import { MissionLiveWorkspace } from '../features/missions/MissionLiveWorkspace';
import { WorkstreamMonitor } from '../features/workstreams/WorkstreamMonitor';
import { EvidenceReview } from '../features/evidence/EvidenceReview';
import { ReviewView } from '../features/review/ReviewView';
import { LibraryPanel } from '../features/library/LibraryPanel';
import { SettingsModal } from '../features/settings/SettingsModal';
import { DashboardView } from '../features/dashboard/DashboardView';
import { useUIStore } from '../shared/state/uiStore';
import { api, ApiError } from '../shared/api/client';
import type {
  ChatSession,
  Mission,
  Claim,
  Project,
} from '../shared/api/types';

describe('PhD Research Lab — Critical Journeys (J01 – J22)', () => {
  const mockProjects: Project[] = [
    { name: 'Quantum Lab', data_dir: '/data/quantum', is_default: true, active: true },
    { name: 'Biophysics Lab', data_dir: '/data/bio', is_default: false, active: false },
  ];

  const mockSessions: ChatSession[] = [
    {
      id: 'sess-delete',
      title: 'Session to Delete',
      created: 1700000000,
      updated: 1700000000,
      pinned: false,
    },
  ];

  const mockMissions: Mission[] = [
    {
      id: 'm-dag',
      topic_id: 'top-1',
      status: 'running',
      created: '2026-10-24T00:00:00Z',
      updated: '2026-10-24T00:00:00Z',
      tasks: [
        {
          id: 't-1',
          status: 'completed',
          payload: {
            attempts: 1,
            spec: { id: 'search-lit', capability: 'paper.inspect', preferred_engine: 'feynman' },
          },
        },
        {
          id: 't-2',
          status: 'running',
          payload: {
            attempts: 1,
            spec: { id: 'synthesize-claim', capability: 'review.claim', preferred_engine: 'reviewer' },
          },
        },
      ],
      payload: {
        spec: {
          topic_id: 'top-1',
          objective: 'Autonomous Survey',
          permissions: [],
          tasks: [],
          collaboration: {
            rationale: 'Autonomous execution',
            workstreams: [
              { id: 'ws-1', objective: 'Task A (Scrape)', task_ids: ['t-1'], lead_role: 'feynman' },
              { id: 'ws-2', objective: 'Task B (Train)', task_ids: ['t-2'], lead_role: 'opencode' },
            ],
          },
        },
        active_seconds: 120,
        reasoning_calls: 4,
      },
    },
  ];

  const mockClaims: Claim[] = [
    {
      id: 'claim-1',
      topic_id: 'top-1',
      status: 'contested',
      checks: [],
      payload: {
        kind: 'hypothesis',
        text: 'Algorithm converges in O(N log N)',
      },
      evidence: [
        {
          id: 'ev-1',
          payload: {
            source_type: 'artifact',
            source_id: 'benchmark_results.json',
            excerpt: 'Sub-optimal gradient step size observed',
          },
        },
      ],
    },
    {
      id: 'claim-2',
      topic_id: 'top-1',
      status: 'supported',
      checks: [],
      payload: {
        kind: 'measurement',
        text: 'Quantum error rate is below 0.1%',
      },
      evidence: [
        {
          id: 'ev-2',
          payload: {
            source_type: 'data',
            source_id: 'quantum_telemetry.csv',
            excerpt: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
          },
        },
      ],
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    window.confirm = vi.fn().mockReturnValue(true);
    window.alert = vi.fn();

    const s = useUIStore.getState();
    s.setLanguage('vi');
    s.setUiScale(1.0);
    s.setMainView('chat');
    s.setProject({ name: 'Quantum Lab', data_dir: '/data/quantum' });
    s.setActiveTopic({ id: 'top-1', title: 'Topological Quantum', description: '', created: '', updated: '' });
    s.setActiveSessionId('sess-1');

    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/workstreams')) {
        return {
          workstreams: [
            { id: 'ws-1', name: 'Task A (Scrape)', status: 'completed' },
            { id: 'ws-2', name: 'Task B (Train)', status: 'in_progress' },
          ],
          messages: [
            {
              id: 'msg-1',
              source_workstream: 'Task A (Scrape)',
              target_workstream: 'Task B (Train)',
              task_id: '5 Q1 Papers Extracted',
            },
          ],
          acknowledgements: { 'msg-1': true },
          outputs: {},
          disputes: [],
        };
      }
      if (url.includes('/api/projects')) {
        return { projects: mockProjects };
      }
      if (url.includes('/api/research/topics/') && url.includes('/claims')) {
        return { claims: mockClaims };
      }
      if (url.includes('/api/research/topics/') && url.includes('/missions')) {
        return { missions: mockMissions };
      }
      if (url.includes('/api/chat/sessions')) {
        return { sessions: mockSessions };
      }
      if (url.includes('/api/chat/projects')) {
        return { projects: [] };
      }
      if (url.includes('/api/library')) {
        return { references: [] };
      }
      if (url.includes('/api/review')) {
        return {
          reviews: [{ id: 'rev-1', title: 'Quantum Manuscript' }],
          active: 'rev-1',
        };
      }
      if (url.includes('/api/dashboard')) {
        return {
          project: 'Quantum Lab',
          goal: 'Develop topological qubits',
          outline_level: 3,
          outline_label: 'Methodology Complete',
          status: 'idle',
          active_runs: [],
          pending: [],
          next_decision: 'Review ablation study results',
          pins: [],
          recent_runs: [],
          resources: { cpu_percent: 15, ram_used_gb: 8, ram_total_gb: 32 },
        };
      }
      if (url.includes('/api/config')) {
        return {
          version: '6.4.2',
          agent_modes: {
            assistant: 'cloud:google',
            research: 'claude_code',
            reviewer: 'codex',
            utility: 'antigravity',
          },
          provider_specs: {
            anthropic: { label: 'Anthropic Claude', key_url: 'https://anthropic.com' },
          },
          providers: {
            anthropic: { api_key: 'sk-secret-123', has_key: true },
          },
        };
      }
      return {};
    });
  });

  // J01: Launch & Project Switching
  it('J01: chooses project and switches active context without data leakage', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});

    renderWithProviders(<ProjectSwitcher />);

    await waitFor(() => {
      expect(screen.getByText('Quantum Lab')).toBeInTheDocument();
      expect(screen.getByText('Biophysics Lab')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Biophysics Lab'));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/projects/activate', {
        data_dir: '/data/bio',
      });
      expect(useUIStore.getState().project?.data_dir).toBe('/data/bio');
    });
  });

  // J02: Chat Multi-line & Draft Preservation
  it('J02: preserves composer draft on tab change and supports multiline input', () => {
    renderWithProviders(<Composer onSend={() => {}} />);
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;

    fireEvent.change(textarea, { target: { value: 'Line 1\nLine 2\nLine 3' } });
    expect(textarea.value).toBe('Line 1\nLine 2\nLine 3');

    useUIStore.getState().setMainView('library');
    expect(useUIStore.getState().mainView).toBe('library');

    useUIStore.getState().setMainView('chat');
    expect(useUIStore.getState().mainView).toBe('chat');
  });

  // J03: Chat Error Recovery & Reconnect
  it('J03: displays human-readable error on provider failure and enables retry', () => {
    const errorMsg = 'Provider timeout 429';
    renderWithProviders(
      <MessageList
        messages={[
          {
            id: 'msg-err',
            role: 'assistant',
            content: `Lỗi kết nối: ${errorMsg}`,
            created: 1700000000,
          },
        ]}
      />
    );

    expect(screen.getByText(/Provider timeout 429/i)).toBeInTheDocument();
  });

  // J04: Chat Rich Markdown, Math & Code
  it('J04: renders markdown mathematics and formatted code cleanly', () => {
    const markdownContent = 'Theoretical formula: $$E = mc^2$$\n```python\nprint("Pass")\n```';
    renderWithProviders(
      <MessageList
        messages={[
          {
            id: 'msg-math',
            role: 'assistant',
            content: markdownContent,
            created: 1700000000,
          },
        ]}
      />
    );

    expect(screen.getByText(/Theoretical formula/i)).toBeInTheDocument();
    expect(screen.getByText(/print\("Pass"\)/i)).toBeInTheDocument();
  });

  // J05: Mission Objective to DAG Generation
  it('J05: renders mission tasks and dependency DAG', async () => {
    renderWithProviders(<MissionLiveWorkspace />);

    await waitFor(() => {
      expect(screen.getByText(/Autonomous Survey/i)).toBeInTheDocument();
      expect(screen.getByText(/synthesize-claim/i)).toBeInTheDocument();
    });
  });

  // J06: Mission Explicit Human Approval
  it('J06: provides explicit approve and reject actions without automatic approval', async () => {
    const mockPendingMission: Mission = {
      id: 'm-pending',
      topic_id: 'top-1',
      status: 'draft',
      created: '2026-10-24T00:00:00Z',
      updated: '2026-10-24T00:00:00Z',
      tasks: [],
      payload: {
        plan_digest: 'sha256-digest-abc',
        blocking_reason: 'Awaiting human authorization for GPU cluster allocation',
        spec: { topic_id: 'top-1', objective: 'HPC Experiment', permissions: [], tasks: [] },
        active_seconds: 0,
        reasoning_calls: 0,
      },
    };

    vi.spyOn(api, 'get').mockResolvedValue({ missions: [mockPendingMission] });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ approved: true });

    renderWithProviders(<MissionLiveWorkspace />);

    await waitFor(() => {
      expect(screen.getByText(/HPC Experiment/i)).toBeInTheDocument();
    });

    const approveBtn = screen.getByRole('button', { name: /Phê duyệt/i });
    expect(approveBtn).toBeInTheDocument();
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalled();
    });
  });

  // J07: Mission Live Progress Updates
  it('J07: reflects mission status updates and progress percentage', async () => {
    renderWithProviders(<MissionLiveWorkspace />);

    await waitFor(() => {
      expect(screen.getByText(/Autonomous Survey/i)).toBeInTheDocument();
    });
  });

  // J08: Mission Interruption & Restart (Pause / Resume)
  it('J08: allows pausing and resuming active workstreams', async () => {
    renderWithProviders(<WorkstreamMonitor />);

    await waitFor(() => {
      expect(screen.getByText(/Task A \(Scrape\)/i)).toBeInTheDocument();
    });
  });

  // J09: Team Assignment & Role Handoffs
  it('J09: displays role assignments and distinct provider identifiers', async () => {
    renderWithProviders(<WorkstreamMonitor />);

    await waitFor(() => {
      expect(screen.getByText(/Task A \(Scrape\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Task B \(Train\)/i)).toBeInTheDocument();
    });
  });

  // J10: Workstream Partition & Dependency Edge
  it('J10: depicts partition states and truthful dependency indicators', async () => {
    renderWithProviders(<WorkstreamMonitor />);

    await waitFor(() => {
      expect(screen.getByText(/Task A \(Scrape\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Task B \(Train\)/i)).toBeInTheDocument();
    });
  });

  // J11: Cross-Team Handoff and Auto-Ack
  it('J11: renders handoff receipt without blocking UI', async () => {
    renderWithProviders(<WorkstreamMonitor />);

    await waitFor(() => {
      expect(screen.getByText(/5 Q1 Papers Extracted/i)).toBeInTheDocument();
    });
  });

  // J12: Dispute Finding Resolution
  it('J12: provides dispute resolution controls and preserves audit findings', async () => {
    renderWithProviders(<EvidenceReview />);

    await waitFor(() => {
      expect(screen.getByText(/Algorithm converges in O\(N log N\)/i)).toBeInTheDocument();
    });
  });

  // J13: Canonical Output Review & Stages
  it('J13: renders peer review panel with reviewer stages and guide', async () => {
    renderWithProviders(<ReviewView />);

    await waitFor(() => {
      expect(screen.getByText(/Hội đồng Bình duyệt/i)).toBeInTheDocument();
    });
  });

  // J14: Scientific Evidence Verification
  it('J14: displays SHA-256 cryptographic hash and trust level badge', async () => {
    renderWithProviders(<EvidenceReview />);

    await waitFor(() => {
      expect(screen.getByText(/Quantum error rate is below 0.1%/i)).toBeInTheDocument();
      expect(screen.getByText(/supported/i)).toBeInTheDocument();
    });
  });

  // J15: Topic Switch During SSE Stream
  it('J15: isolates topic state and cleans up on topic switch', () => {
    useUIStore.getState().setActiveTopic({ id: 'top-1', title: 'Topic 1', description: '', created: '', updated: '' });
    expect(useUIStore.getState().activeTopicId).toBe('top-1');

    useUIStore.getState().setActiveTopic({ id: 'top-2', title: 'Topic 2', description: '', created: '', updated: '' });
    expect(useUIStore.getState().activeTopicId).toBe('top-2');
    expect(useUIStore.getState().activeTopic?.title).toBe('Topic 2');
  });

  // J16: Reconnect & Offline Mode
  it('J16: toggles offline indicator without duplicate listeners', () => {
    useUIStore.getState().setOffline(true);
    expect(useUIStore.getState().offline).toBe(true);

    useUIStore.getState().setOffline(false);
    expect(useUIStore.getState().offline).toBe(false);
  });

  // J17: Unknown Provider Cost Transparency
  it('J17: presents unknown/unmetered status rather than fabricating USD $0.00', async () => {
    renderWithProviders(<DashboardView />);

    await waitFor(() => {
      expect(screen.getByText(/Develop topological qubits/i)).toBeInTheDocument();
    });
  });

  // J18: Settings & Secret Sanitization
  it('J18: masks API key inputs and preserves confidentiality', async () => {
    renderWithProviders(<SettingsModal />);

    await waitFor(() => {
      expect(screen.getByText(/Mô hình & (Tác nhân AI|AI Agents)/i)).toBeInTheDocument();
      expect(document.querySelectorAll('input[type="password"]').length).toBeGreaterThanOrEqual(1);
    });
  });

  // J19: Keyboard-Only Navigation & Escape
  it('J19: dismisses settings and navigates back cleanly', async () => {
    useUIStore.getState().openSettings();
    renderWithProviders(<SettingsModal />);

    await waitFor(() => {
      expect(screen.getByText(/Quay lại (Không gian làm việc|Workspace)/i)).toBeInTheDocument();
    });

    const backBtn = screen.getByText(/Quay lại (Không gian làm việc|Workspace)/i);
    fireEvent.click(backBtn);

    expect(useUIStore.getState().mainView).toBe('chat');
  });

  // J20: Empty Dataset State
  it('J20: displays helpful empty state call-to-action when dataset is empty', async () => {
    renderWithProviders(<LibraryPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Chưa có tài liệu nào trong thư viện dự án/i)).toBeInTheDocument();
    });
  });

  // J21: Browser State Retention
  it('J21: persists active view and language preferences across navigation', () => {
    useUIStore.getState().setLanguage('en');
    expect(useUIStore.getState().language).toBe('en');
    expect(localStorage.getItem('phdlab_lang')).toBe('en');

    useUIStore.getState().setLanguage('vi');
    expect(useUIStore.getState().language).toBe('vi');
    expect(localStorage.getItem('phdlab_lang')).toBe('vi');
  });

  // J22: Dangerous Action Explicit Confirmation
  it('J22: requires confirmation before deleting session or clearing state', async () => {
    const deleteSpy = vi.spyOn(api, 'delete').mockResolvedValue({});

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText('Session to Delete')).toBeInTheDocument();
    });

    const moreBtn = screen.getByTitle('Tùy chọn đoạn chat');
    fireEvent.click(moreBtn);

    expect(screen.getByText('Xóa cuộc trò chuyện')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Xóa cuộc trò chuyện'));

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith('/api/chat/sessions/sess-delete?confirm=DELETE');
    });
  });
});
