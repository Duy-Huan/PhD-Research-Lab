// v6.6.2: one live roster of every agent (configured roles, every Harness-created agent, Hermes, MCP clients) from
// /api/agents/roster/stream, shared by 3D Lab, Harness and the status views. States come from backend records only.
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { AgentActivity, AgentOfficeViewModel, AgentPresence } from '../api/types';
import { inferArchetype, inferZone } from './eventAdapter';

export type RosterState = 'idle' | 'thinking' | 'tool' | 'waiting' | 'error' | 'done' | 'offline';
export interface RosterAgent {
  id: string;
  name: string;
  kind: 'role' | 'harness' | 'runtime' | 'mcp_client';
  source: string;
  role: string;
  state: RosterState;
  detail: string;
  tool: string;
  job: string;
  provider?: string;
}
export interface RosterSnapshot {
  agents: RosterAgent[];
  counts: Record<string, number>;
  digest: string;
}

const PRESENCE: Record<RosterState, AgentPresence> = {
  idle: 'idle', thinking: 'running', tool: 'running', waiting: 'awaiting_approval', error: 'failed', done: 'completed',
  offline: 'disconnected',
};
const ACTIVITY: Record<RosterState, AgentActivity> = {
  idle: 'none', thinking: 'reading', tool: 'executing', waiting: 'reviewing', error: 'none', done: 'reporting', offline: 'none',
};

export function rosterToOffice(snapshot: RosterSnapshot, projectId: string, topicId?: string): AgentOfficeViewModel[] {
  return snapshot.agents.map((a) => {
    const engine = a.provider || (a.kind === 'runtime' ? 'hermes' : a.kind === 'mcp_client' ? 'mcp' : 'auto');
    return {
      agentId: a.id, projectId, topicId, displayName: a.name, role: a.role || a.kind, engine,
      presence: PRESENCE[a.state] || 'unknown', activity: ACTIVITY[a.state] || 'unknown', lastObservedAt: '',
      sourceEventId: a.job || undefined, canInspect: true, canPause: false, canResume: false,
      hasApprovalRequest: a.state === 'waiting', zone: inferZone(a.role || a.kind, engine),
      archetype: inferArchetype(a.role || a.kind, engine), personality: a.detail || undefined,
      speechBubble: a.tool ? `🔧 ${a.tool}` : undefined,
    };
  });
}

/** Live roster: SSE stream with a polling fallback when EventSource is unavailable or fails. */
export function useAgentRoster(): RosterSnapshot | undefined {
  const [live, setLive] = useState<RosterSnapshot>();
  const [streamFailed, setStreamFailed] = useState(typeof EventSource === 'undefined');
  useEffect(() => {
    if (typeof EventSource === 'undefined') return undefined;
    const es = new EventSource('/api/agents/roster/stream');
    if (typeof es.addEventListener !== 'function') {
      // Minimal EventSource implementations cannot receive named events: poll instead.
      es.close?.();
      setStreamFailed(true);
      return undefined;
    }
    es.addEventListener('roster', (ev) => {
      try {
        setLive(JSON.parse((ev as MessageEvent).data));
      } catch {
        /* a malformed frame is ignored; the next change sends a full snapshot */
      }
    });
    es.onerror = () => setStreamFailed(true);
    return () => es.close();
  }, []);
  const { data: polled } = useQuery({
    queryKey: ['agent-roster'],
    queryFn: () => api.get<RosterSnapshot>('/api/agents/roster'),
    enabled: streamFailed || !live,
    refetchInterval: streamFailed ? 3000 : false,
  });
  const snap = live || polled;
  return snap && Array.isArray(snap.agents) ? snap : undefined; // anything else is not a roster (older backend)
}
