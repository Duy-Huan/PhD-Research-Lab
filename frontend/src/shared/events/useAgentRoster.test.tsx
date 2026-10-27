import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '../api/client';
import { rosterToOffice, useAgentRoster, type RosterSnapshot } from './useAgentRoster';

// FQC-ROSTER-UI-662: 3D Lab shows the backend roster (every Harness-created agent, Hermes, MCP clients) with real states.
const snapshot: RosterSnapshot = {
  digest: 'd1', counts: { total: 4 },
  agents: [
    { id: 'role:assistant', name: 'Assistant', kind: 'role', source: 'config', role: 'assistant', state: 'tool', detail: '',
      tool: 'stats_mean', job: 'job-1', provider: 'auto' },
    { id: 'harness:wf:n1', name: 'Literature scout', kind: 'harness', source: 'workflow', role: 'literature', state: 'waiting',
      detail: 'Study / Literature scout', tool: '', job: '' },
    { id: 'hermes', name: 'Hermes', kind: 'runtime', source: 'hermes', role: '', state: 'offline', detail: 'not started', tool: '', job: '' },
    { id: 'mcp:chatgpt', name: 'ChatGPT', kind: 'mcp_client', source: 'chatgpt-gateway', role: '', state: 'error', detail: '', tool: '', job: '' },
  ],
};

describe('agent roster', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('maps backend states to office presence, activity, approvals and tool bubbles', () => {
    const [assistant, scout, hermes, chatgpt] = rosterToOffice(snapshot, '/p', 't1');
    expect(assistant).toMatchObject({ agentId: 'role:assistant', presence: 'running', activity: 'executing',
      speechBubble: '🔧 stats_mean', sourceEventId: 'job-1', topicId: 't1' });
    expect(scout).toMatchObject({ displayName: 'Literature scout', presence: 'awaiting_approval', hasApprovalRequest: true,
      personality: 'Study / Literature scout' });
    expect(hermes).toMatchObject({ presence: 'disconnected', engine: 'hermes' });
    expect(chatgpt).toMatchObject({ presence: 'failed', engine: 'mcp' });
  });

  it('polls the snapshot when streaming is unavailable and ignores non-roster payloads', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue(snapshot as any);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
    const { result } = renderHook(() => useAgentRoster(), { wrapper });
    await waitFor(() => expect(result.current?.agents).toHaveLength(4));
    expect(get).toHaveBeenCalledWith('/api/agents/roster');
    get.mockResolvedValue({ unrelated: true } as any);
    const qc2 = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper2 = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc2}>{children}</QueryClientProvider>;
    const other = renderHook(() => useAgentRoster(), { wrapper: wrapper2 });
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    expect(other.result.current).toBeUndefined();
  });
});
