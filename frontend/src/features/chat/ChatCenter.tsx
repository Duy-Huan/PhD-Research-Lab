import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
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
  const esRef = useRef<EventSource | null>(null);

  // Fetch current session details directly
  const { data: sessionData, refetch: refetchSession } = useQuery<ChatSession>({
    queryKey: ['chat', activeSessionId],
    queryFn: () => api.get<ChatSession>(`/api/chat/sessions/${activeSessionId}`),
    enabled: !!activeSessionId,
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

  // Subscribe to session SSE stream for live token deltas and turn completion
  useEffect(() => {
    if (!activeSessionId) {
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
          setStreamingText((prev) => prev + (data.delta || data.text || ''));
        } else if (
          data.type === 'turn.completed' ||
          data.type === 'turn.failed' ||
          data.type === 'turn.cancelled' ||
          data.type === 'message.created' ||
          data.type === 'approval.requested'
        ) {
          if (
            data.type === 'turn.completed' ||
            data.type === 'turn.failed' ||
            data.type === 'turn.cancelled'
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
  }, [activeSessionId, queryClient]);

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

      const result = await api.post<{
        turn?: { id: string; status: string };
        session?: ChatSession;
      }>(`/api/chat/sessions/${sid}/turns`, {
        text,
        overrides: overrides || {},
      });

      if (result?.turn?.id) {
        setActiveTurnId(result.turn.id);
      }
      return { sid, result };
    },
    onSuccess: ({ sid }) => {
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
    await api.post(`/api/chat/sessions/${activeSessionId}/memory`, {
      message_id: messageId,
      type: 'fact',
      content: content.slice(0, 600),
      title: content.slice(0, 60),
      save: true,
    });
    queryClient.invalidateQueries({ queryKey: ['chat', activeSessionId] });
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
      }}
    >
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
