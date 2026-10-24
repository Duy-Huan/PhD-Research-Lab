import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import type { DrawerKind } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { ChatSession, ChatProject } from '../../shared/api/types';
import { MessageList } from './MessageList';
import { Composer } from './Composer';

interface ChatCenterProps {
  compact?: boolean;
}

export const ChatCenter: React.FC<ChatCenterProps> = ({ compact = false }) => {
  const queryClient = useQueryClient();
  const { activeSessionId, setActiveSessionId, activeTopic, activeChatProjectId, project } =
    useUIStore();
  const { t } = useI18n();
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [memoryFeedback, setMemoryFeedback] = useState<{ error: boolean; text: string } | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const { data: actionsData } = useQuery<{ actions: Array<{ name: string; route_or_component_key: string }> }>({
    queryKey: ['skills'], queryFn: () => api.get('/api/skills'),
  });

  // Fetch current session details directly
  const { data: sessionData, refetch: refetchSession } = useQuery<ChatSession>({
    queryKey: ['chat', activeSessionId],
    queryFn: () => api.get<ChatSession>(`/api/chat/sessions/${activeSessionId}`),
    enabled: !!activeSessionId,
    refetchInterval: query => query.state.data?.turns?.some(t => ['queued', 'running'].includes(t.status)) ? 1500 : false,
  });

  // Fetch chat folders so we can display shared folder context badge
  const { data: chatProjectsData } = useQuery<{ projects: ChatProject[] }>({
    queryKey: ['chat-projects', project?.data_dir],
    queryFn: () => api.get<{ projects: ChatProject[] }>('/api/chat/projects'),
    enabled: !!project,
  });

  const currentFolderId = sessionData?.chat_project || activeChatProjectId || '';
  const activeFolder = (chatProjectsData?.projects || []).find((p) => p.id === currentFolderId);

  const messages = sessionData?.messages || [];
  const approvals = sessionData?.approvals || [];
  const memoryItems = sessionData?.memory_items || [];
  const turns = sessionData?.turns || [];

  useEffect(() => {
    if (!activeSessionId || sessionData?.id !== activeSessionId) {
      setIsStreaming(false);
      setActiveTurnId(null);
      setStreamingText('');
      return;
    }
    const running = sessionData.turns?.find(t => ['queued', 'running'].includes(t.status));
    setIsStreaming(Boolean(running));
    setActiveTurnId(running?.id || null);
    if (!running) setStreamingText('');
  }, [sessionData, activeSessionId]);

  // Subscribe to session SSE stream for live token deltas and turn completion
  useEffect(() => {
    if (!activeSessionId || sessionData?.id !== activeSessionId) {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      return;
    }

    const afterSeq = sessionData?.last_seq || 0;
    const es = new EventSource(`/api/chat/sessions/${activeSessionId}/stream?after=${afterSeq}`);
    esRef.current = es;

    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === 'message.delta') {
          setIsStreaming(true);
          if (data.turn_id) setActiveTurnId(data.turn_id);
          setStreamingText((prev) => prev + (data.data?.text || data.delta || data.text || ''));
        } else if (
          data.type === 'turn.completed' ||
          data.type === 'turn.failed' ||
          data.type === 'turn.cancelled' ||
          data.type === 'message.created' ||
          data.type === 'message.completed' ||
          data.type === 'turn.awaiting_launch' ||
          data.type === 'action.approval_required' ||
          data.type === 'tool.approval_required' ||
          data.type === 'approval.requested'
        ) {
          if (
            data.type === 'turn.completed' ||
            data.type === 'turn.failed' ||
          data.type === 'turn.cancelled' ||
          data.type === 'turn.awaiting_launch' ||
          data.type === 'tool.approval_required'
          ) {
            setIsStreaming(false);
            setStreamingText('');
            setActiveTurnId(null);
          }
          queryClient.invalidateQueries({ queryKey: ['chat', activeSessionId] });
          queryClient.invalidateQueries({ queryKey: ['sessions'] });
        }
      } catch {
        // Ignore malformed SSE keepalive frames
      }
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [activeSessionId, sessionData?.id, queryClient]);

  // Send turn mutation
  const sendMutation = useMutation({
    mutationFn: async ({
      text,
      overrides,
    }: {
      text: string;
      overrides?: { provider?: string; model?: string; reasoning?: string; sources?: string[] };
    }) => {
      let sid = activeSessionId;

      // If no active session, create one first (inheriting activeChatProjectId folder!)
      if (!sid) {
        const created = await api.post<ChatSession>('/api/chat/sessions', {
          title: text.slice(0, 48),
          topic_id: activeTopic?.id || '',
          chat_project: activeChatProjectId || '',
          settings:
            overrides?.provider || overrides?.model || overrides?.reasoning
              ? {
                  provider: overrides?.provider,
                  model: overrides?.model,
                  reasoning: overrides?.reasoning,
                }
              : {},
        });
        sid = created.id;
        setActiveSessionId(sid);
      }

      setIsStreaming(true);
      setStreamingText('');

      try {
        const result = await api.post<{
          id?: string;
          status?: string;
          turn?: { id: string; status: string };
          session?: ChatSession;
        }>(`/api/chat/sessions/${sid}/turns`, {
          text,
          overrides: overrides || {},
        });

        const turnId = result?.id || result?.turn?.id;
        if (turnId) {
          setActiveTurnId(turnId);
        }
        return { sid, result };
      } catch (err: any) {
        // If a turn was already running/stuck, attempt to cancel it so the user can send again
        if (err.message && err.message.toLowerCase().includes('already running')) {
          try {
            await api.post(`/api/chat/sessions/${sid}/cancel`, {});
          } catch {
            // ignore
          }
        }
        throw err;
      }
    },
    onSuccess: ({ sid, result }) => {
      const status = result.status || result.turn?.status;
      if (status && !['queued', 'running'].includes(status)) {
        setIsStreaming(false);
        setStreamingText('');
        setActiveTurnId(null);
      }
      queryClient.invalidateQueries({ queryKey: ['chat', sid] });
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
    onError: (err: Error) => {
      setIsStreaming(false);
      setStreamingText(`${t('Lỗi', 'Error')}: ${err.message}`);
    },
  });

  const handleSend = (
    text: string,
    overrides?: { provider?: string; model?: string; reasoning?: string; sources?: string[] }
  ) => {
    const command = text.trim().split(/\s+/)[0].slice(1);
    const action = actionsData?.actions?.find(a => a.name === command && text.trim().startsWith('/'));
    const drawers: Record<string, DrawerKind> = { papers: 'library', library: 'library', topics: 'topics',
      settings: 'settings', missions: 'missions', monitor: 'missions', workstreams: 'workstreams',
      teams: 'missions', protocols: 'protocols', claims: 'claims' };
    if (action && drawers[action.route_or_component_key]) {
      useUIStore.getState().openDrawer(drawers[action.route_or_component_key]);
      return;
    }
    sendMutation.mutate({ text, overrides });
  };

  const handleCancelTurn = async () => {
    if (!activeSessionId || !activeTurnId) return;
    try {
      await api.post(`/api/chat/sessions/${activeSessionId}/turns/${activeTurnId}/cancel`, {});
    } catch {
      // ignore
    } finally {
      setIsStreaming(false);
      setStreamingText('');
      setActiveTurnId(null);
      refetchSession();
    }
  };

  const handleAcceptProposal = async (aid: string) => {
    if (!activeSessionId) return;
    await api.post(`/api/chat/sessions/${activeSessionId}/approvals/${aid}`, {
      decision: 'approve',
    });
    queryClient.invalidateQueries({ queryKey: ['chat', activeSessionId] });
  };

  const handleRejectProposal = async (aid: string) => {
    if (!activeSessionId) return;
    await api.post(`/api/chat/sessions/${activeSessionId}/approvals/${aid}`, {
      decision: 'reject',
    });
    queryClient.invalidateQueries({ queryKey: ['chat', activeSessionId] });
  };

  const handleMemoryDecision = async (cid: string, decision: 'approve' | 'reject') => {
    await api.post(`/api/memory/candidates/${cid}/${decision}`, {});
    if (activeSessionId) {
      queryClient.invalidateQueries({ queryKey: ['chat', activeSessionId] });
    }
  };

  const handleRememberMessage = async (messageId: string, content: string) => {
    if (!activeSessionId) return;
    setMemoryFeedback(null);
    try {
      await api.post(`/api/chat/sessions/${activeSessionId}/memory`, {
        message_id: messageId,
        // Saving model prose creates a knowledge note, not a verified scientific fact.
        type: 'knowledge',
        content: content.slice(0, 600),
        title: content.slice(0, 60),
        save: true,
      });
      queryClient.invalidateQueries({ queryKey: ['chat', activeSessionId] });
      setMemoryFeedback({ error: false, text: t('Đã lưu vào Bộ nhớ Dự án', 'Saved to Project Memory') });
    } catch (error) {
      setMemoryFeedback({ error: true, text: (error as Error).message });
    }
  };

  const handlePinMessage = async (messageId: string, pinned: boolean) => {
    if (!activeSessionId) return;
    await api.put(`/api/chat/sessions/${activeSessionId}/messages/${messageId}/pin`, {
      pinned,
    });
    queryClient.invalidateQueries({ queryKey: ['chat', activeSessionId] });
  };

  return (
    <div
      id="view"
      style={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        height: '100%',
        minHeight: 0,
        position: 'relative',
        background: 'var(--bg)',
        color: 'var(--ink)',
      }}
    >
      {sendMutation.isError && <div role="alert">{sendMutation.error.message}</div>}
      {memoryFeedback && <div role={memoryFeedback.error ? 'alert' : 'status'} style={{ padding: '8px 16px' }}>{memoryFeedback.text}</div>}
      <MessageList
        sessionTitle={sessionData?.title}
        activeFolder={activeFolder}
        messages={messages}
        approvals={approvals}
        memoryItems={memoryItems}
        turns={turns}
        streamingText={streamingText}
        isStreaming={isStreaming}
        compact={compact}
        onAcceptProposal={handleAcceptProposal}
        onRejectProposal={handleRejectProposal}
        onMemoryDecision={handleMemoryDecision}
        onRememberMessage={handleRememberMessage}
        onPinMessage={handlePinMessage}
        onQuickSend={(prompt) => handleSend(prompt)}
        onCancelTurn={activeTurnId ? handleCancelTurn : undefined}
        onLaunchTurn={async tid => {
          if (!activeSessionId) return;
          await api.post(`/api/chat/sessions/${activeSessionId}/turns/${tid}/launch`, {});
          refetchSession();
        }}
      />
      <Composer
        onSend={handleSend}
        disabled={sendMutation.isPending}
        isStreaming={isStreaming}
        onCancel={activeTurnId ? handleCancelTurn : undefined}
        compact={compact}
      />
    </div>
  );
};
