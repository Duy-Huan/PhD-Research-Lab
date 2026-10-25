import React, { useEffect, useRef } from 'react';
import { MarkdownRenderer } from '../../shared/ui/MarkdownRenderer';
import { ChatRunCard } from './ChatRunCard';
import { APP_VERSION } from '../../shared/version';
import type {
  ChatMessage,
  ChatApproval,
  ChatMemoryItem,
  ChatTurn,
  ChatProject,
} from '../../shared/api/types';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import {
  Bot,
  User,
  Check,
  X,
  Copy,
  Brain,
  FlaskConical,
  BookOpen,
  Terminal,
  Compass,
  Award,
  ShieldAlert,
  BookmarkPlus,
  Pin,
  FolderOpen,
  FileText,
  Image as ImageIcon,
} from 'lucide-react';

interface MessageListProps {
  sessionTitle?: string;
  activeFolder?: ChatProject;
  messages: ChatMessage[];
  approvals?: ChatApproval[];
  memoryItems?: ChatMemoryItem[];
  turns?: ChatTurn[];
  streamingText?: string;
  isStreaming?: boolean;
  compact?: boolean;
  onAcceptProposal?: (proposalId: string) => void;
  onRejectProposal?: (proposalId: string) => void;
  onMemoryDecision?: (candidateId: string, decision: 'approve' | 'reject') => void;
  onRememberMessage?: (messageId: string, content: string) => void;
  onPinMessage?: (messageId: string, pinned: boolean) => void;
  onQuickSend?: (prompt: string) => void;
  onCancelTurn?: () => void;
  onLaunchTurn?: (turnId: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  activeFolder,
  messages,
  approvals = [],
  memoryItems = [],
  turns = [],
  streamingText,
  isStreaming = false,
  compact = false,
  onAcceptProposal,
  onRejectProposal,
  onMemoryDecision,
  onRememberMessage,
  onPinMessage,
  onQuickSend,
  onLaunchTurn,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { openDrawer, open3DOffice, setMainView } = useUIStore();
  const { t } = useI18n();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, approvals.length]);

  const copyText = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const pendingApprovals = approvals.filter((a) => a.status === 'pending');
  const pendingMemories = memoryItems.filter((m) => m.status === 'pending');
  const shownRuns = new Set<string>();
  const displayMessages = messages.filter(message => {
    if (!message.run_id || message.role !== 'assistant') return true;
    if (shownRuns.has(message.run_id)) return false;
    shownRuns.add(message.run_id);
    return true;
  });

  return (
    <div
      className="message-list"
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: compact ? '12px 14px' : '24px 28px',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
      }}
    >
      {/* Active Folder Shared Context Banner */}
      {activeFolder && (
        <div
          style={{
            maxWidth: 820,
            width: '100%',
            margin: '0 auto',
            padding: '7px 12px',
            borderRadius: 10,
            background: 'var(--accent-soft)',
            border: '1px solid var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            fontSize: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <FolderOpen size={14} color="var(--accent)" />
            <b>{activeFolder.name}</b>
            <span className="muted ellipsis">
              ·{' '}
              {activeFolder.instructions
                ? activeFolder.instructions
                : t(
                    'Đang đồng bộ bộ nhớ ngữ cảnh giữa các cuộc trò chuyện trong nhóm này',
                    'Syncing shared context memory across all chats in this folder'
                  )}
            </span>
          </div>
        </div>
      )}

      {/* ChatGPT-Style Minimal Centered Greeting when Empty */}
      {messages.length === 0 && !streamingText && (
        <div
          style={{
            margin: 'auto',
            maxWidth: 760,
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            gap: 18,
            padding: compact ? '16px 8px' : '32px 16px',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 14px',
              borderRadius: 999,
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              boxShadow: 'var(--shadow)',
              color: 'var(--ink)',
            }}
          >
            <img src="/img/logo-64.png" alt="Logo" width={20} height={20} />
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>PhD Research Lab · v{APP_VERSION}</span>
          </div>

          <h2
            style={{
              margin: 0,
              fontSize: compact ? 20 : 28,
              fontWeight: 600,
              letterSpacing: '-0.02em',
              color: 'var(--ink)',
            }}
          >
            {t('Hôm nay chúng ta bắt đầu từ đâu?', 'Where should we begin?')}
          </h2>

          {/* Icon-First Quick Action Pills (like ChatGPT starter pills) */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'center',
              gap: 8,
              maxWidth: 680,
            }}
          >
            <button
              type="button"
              className="btn sm ghost"
              onClick={() =>
                onQuickSend?.(
                  t(
                    '/outline Xây dựng đề cương nghiên cứu 5 cấp độ cho chủ đề hiện tại.',
                    '/outline Build a 5-level research outline for the current topic.'
                  )
                )
              }
              style={{
                borderRadius: 999,
                padding: '7px 14px',
                border: '1px solid var(--line-2)',
                background: 'var(--panel)',
                color: 'var(--ink)',
                gap: 6,
              }}
            >
              <Compass size={14} color="var(--accent)" />
              <span>{t('Đề cương 5 cấp', '5-Level Outline')}</span>
            </button>

            <button
              type="button"
              className="btn sm ghost"
              onClick={() =>
                onQuickSend?.(
                  t(
                    '/feynman Khảo sát bài báo Q1/A* mới nhất và phân tích Research Gap.',
                    '/feynman Survey recent Q1/A* papers and analyze the Research Gap.'
                  )
                )
              }
              style={{
                borderRadius: 999,
                padding: '7px 14px',
                border: '1px solid var(--line-2)',
                background: 'var(--panel)',
                color: 'var(--ink)',
                gap: 6,
              }}
            >
              <BookOpen size={14} color="#10b981" />
              <span>{t('Khảo sát SKB', 'Literature SKB')}</span>
            </button>

            <button
              type="button"
              className="btn sm ghost"
              onClick={() =>
                onQuickSend?.(
                  t(
                    '/openscience Thiết kế giao thức thí nghiệm có kiểm soát & nghiên cứu loại trừ Ablation.',
                    '/openscience Design a controlled experimental protocol & ablation study.'
                  )
                )
              }
              style={{
                borderRadius: 999,
                padding: '7px 14px',
                border: '1px solid var(--line-2)',
                background: 'var(--panel)',
                color: 'var(--ink)',
                gap: 6,
              }}
            >
              <FlaskConical size={14} color="#8b5cf6" />
              <span>OpenScience</span>
            </button>

            <button
              type="button"
              className="btn sm ghost"
              onClick={() => openDrawer('opencode')}
              style={{
                borderRadius: 999,
                padding: '7px 14px',
                border: '1px solid var(--line-2)',
                background: 'var(--panel)',
                color: 'var(--ink)',
                gap: 6,
              }}
            >
              <Terminal size={14} color="#f59e0b" />
              <span>OpenCode</span>
            </button>

            <button
              type="button"
              className="btn sm ghost"
              onClick={() => setMainView('review')}
              style={{
                borderRadius: 999,
                padding: '7px 14px',
                border: '1px solid var(--line-2)',
                background: 'var(--panel)',
                color: 'var(--ink)',
                gap: 6,
              }}
            >
              <Award size={14} color="#ec4899" />
              <span>Peer Review</span>
            </button>

            {!compact && (
              <button
                type="button"
                className="btn sm accent"
                onClick={() => open3DOffice(true)}
                style={{
                  borderRadius: 999,
                  padding: '7px 14px',
                  gap: 6,
                }}
              >
                <Bot size={14} />
                <span>3D Lab</span>
              </button>
            )}

            <button
              type="button"
              className="btn sm ghost"
              onClick={() => openDrawer('intelligence')}
              style={{
                borderRadius: 999,
                padding: '7px 14px',
                border: '1px solid var(--line-2)',
                background: 'var(--panel)',
                color: 'var(--ink)',
                gap: 6,
              }}
            >
              <Brain size={14} color="#06b6d4" />
              <span>RO-Crate</span>
            </button>
          </div>
        </div>
      )}

      {turns.filter(turn => turn.status === 'failed').map(turn => (
        <div role="alert" key={turn.id} style={{ color: 'var(--danger, #b91c1c)' }}>
          {t('Không thể trả lời', 'Unable to answer')}: {turn.error || t('Lượt chat thất bại.', 'Chat turn failed.')}
        </div>
      ))}
      {turns.filter(turn => turn.status === 'awaiting_launch').map(turn => (
        <div key={turn.id}>
          {t('Đang chờ khởi chạy thủ công.', 'Waiting for manual launch.')}
          <button className="btn" onClick={() => onLaunchTurn?.(turn.id)}>{t('Khởi chạy', 'Launch')}</button>
        </div>
      ))}
      {/* Messages Stream (Centered max-width 820px like ChatGPT) */}
      <div
        style={{
          maxWidth: 820,
          width: '100%',
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        {displayMessages.map((msg) => {
          const bodyText = msg.text ?? msg.content ?? '';
          const isUser = msg.role === 'user';

          return (
            <article
              key={msg.id}
              className={`msg-card ${msg.role}`}
              style={{
                display: 'flex',
                gap: 12,
                maxWidth: isUser ? '82%' : '100%',
                alignSelf: isUser ? 'flex-end' : 'stretch',
                background: isUser ? 'var(--bg-2)' : 'var(--panel)',
                color: 'var(--ink)',
                padding: isUser ? '10px 16px' : '14px 18px',
                borderRadius: isUser ? 20 : 14,
                border: `1px solid ${msg.pinned ? 'var(--accent)' : 'var(--line)'}`,
              }}
            >
              {!isUser && (
                <div style={{ marginTop: 2 }}>
                  <Bot size={18} color="var(--accent)" />
                </div>
              )}

              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8,
                    marginBottom: 4,
                  }}
                >
                  <b style={{ fontSize: 12, color: 'var(--muted)' }}>
                    {isUser ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <User size={12} /> {t('Bạn', 'You')}
                      </span>
                    ) : (
                      `PhD Lab Assistant (${msg.provider || (msg.run_id ? 'phdlab' : msg.model) || 'AI'})`
                    )}
                  </b>
                  <div style={{ display: 'flex', gap: 3 }}>
                    {onPinMessage && (
                      <button
                        type="button"
                        className="icon sm"
                        title={msg.pinned ? t('Bỏ ghim', 'Unpin') : t('Ghim tin nhắn', 'Pin')}
                        onClick={() => onPinMessage(msg.id, !msg.pinned)}
                        style={{
                          width: 22,
                          height: 22,
                          color: msg.pinned ? 'var(--accent)' : 'inherit',
                        }}
                      >
                        <Pin size={12} />
                      </button>
                    )}
                    <button
                      type="button"
                      className="icon sm"
                      title={t('Sao chép', 'Copy')}
                      onClick={() => copyText(bodyText)}
                      style={{ width: 22, height: 22 }}
                    >
                      <Copy size={12} />
                    </button>
                    {!isUser && onRememberMessage && (
                      <button
                        type="button"
                        className="icon sm"
                        title={t('Lưu vào Bộ nhớ Dự án', 'Save to Project Memory')}
                        onClick={() => onRememberMessage(msg.id, bodyText)}
                        style={{ width: 22, height: 22 }}
                      >
                        <BookmarkPlus size={12} />
                      </button>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    fontSize: 13.5,
                    lineHeight: 1.65,
                    wordBreak: 'break-word',
                  }}
                >
                  <MarkdownRenderer content={bodyText} />
                </div>

                {/* Attached Sources & Images if present */}
                {msg.sources && msg.sources.some((s) => s.startsWith('att:')) && (
                  <div
                    style={{
                      marginTop: 8,
                      paddingTop: 6,
                      borderTop: '1px dashed var(--line)',
                      display: 'flex',
                      gap: 6,
                      flexWrap: 'wrap',
                    }}
                  >
                    {msg.sources.filter((s) => s.startsWith('att:')).map((s) => {
                      const attId = s.replace('att:', '');
                      return (
                        <a
                          key={s}
                          href={`/api/chat/attachments/${attId}/file`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="chip"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            fontSize: 11,
                            textDecoration: 'none',
                            color: 'inherit',
                          }}
                          title={t('Mở tệp đính kèm trong tab mới', 'Open attachment in new tab')}
                        >
                          <FileText size={11} color="var(--accent)" />
                          <span>att:{attId}</span>
                        </a>
                      );
                    })}
                  </div>
                )}

                {/* Citations if present */}
                {msg.citations && msg.citations.length > 0 && (
                  <div
                    style={{
                      marginTop: 10,
                      paddingTop: 8,
                      borderTop: '1px dashed var(--line)',
                      display: 'flex',
                      gap: 6,
                      flexWrap: 'wrap',
                    }}
                  >
                    {msg.citations.map((c, i) => (
                      <span key={i} className="chip" style={{ fontSize: 11 }}>
                        [{c.key || i + 1}] {c.title || c.url}
                      </span>
                    ))}
                  </div>
                )}

                {/* Legacy inline proposals if attached on msg */}
                {msg.proposals && msg.proposals.length > 0 && (
                  <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {msg.proposals.map((p) => (
                      <div
                        key={p.id}
                        style={{
                          background: 'var(--bg)',
                          border: '1px solid var(--line-2)',
                          borderRadius: 8,
                          padding: 10,
                        }}
                      >
                        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>
                          {t('Đề xuất', 'Proposal')}: {p.kind}
                        </div>
                        <pre style={{ fontSize: 12, margin: '6px 0', overflowX: 'auto' }}>
                          {JSON.stringify(p.payload, null, 2)}
                        </pre>
                        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                          <button
                            className="btn sm accent"
                            onClick={() => onAcceptProposal?.(p.id)}
                          >
                            <Check size={13} style={{ marginRight: 4 }} />{' '}
                            {t('Chấp nhận', 'Approve')}
                          </button>
                          <button className="btn sm ghost" onClick={() => onRejectProposal?.(p.id)}>
                            <X size={13} style={{ marginRight: 4 }} /> {t('Từ chối', 'Reject')}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {msg.run_id && <ChatRunCard id={msg.run_id} />}
              </div>
            </article>
          );
        })}

        {/* Session-level Pending Approvals */}
        {pendingApprovals.map((app) => (
          <div
            key={app.id}
            style={{
              background: 'var(--warn-soft)',
              border: '1px solid var(--warn)',
              borderRadius: 12,
              padding: '12px 16px',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <ShieldAlert size={16} color="var(--warn)" />
              <b style={{ fontSize: 13 }}>
                {t('Phê duyệt Hành động:', 'Action Approval:')} {app.name}
              </b>
            </div>
            {app.reason && <div style={{ fontSize: 12.5 }}>{app.reason}</div>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                className="btn sm accent"
                onClick={() => onAcceptProposal?.(app.id)}
              >
                <Check size={13} style={{ marginRight: 4 }} /> {t('Phê duyệt', 'Approve')}
              </button>
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => onRejectProposal?.(app.id)}
              >
                <X size={13} style={{ marginRight: 4 }} /> {t('Từ chối', 'Reject')}
              </button>
            </div>
          </div>
        ))}

        {/* Session-level Memory Candidates */}
        {pendingMemories.map((mem) => (
          <div
            key={mem.id}
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--accent)',
              borderRadius: 12,
              padding: '10px 14px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <div style={{ fontSize: 12.5 }}>
              <span className="chip" style={{ marginRight: 6, fontSize: 11 }}>
                Memory ({mem.type})
              </span>
              <span>{mem.text}</span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
              <button
                type="button"
                className="btn sm accent"
                onClick={() => onMemoryDecision?.(mem.id, 'approve')}
              >
                {t('Lưu', 'Save')}
              </button>
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => onMemoryDecision?.(mem.id, 'reject')}
              >
                {t('Bỏ qua', 'Skip')}
              </button>
            </div>
          </div>
        ))}

        {/* Live Streaming Message */}
        {isStreaming && (
          <article
            className="msg-card assistant streaming"
            style={{
              display: 'flex',
              gap: 12,
              background: 'var(--panel)',
              color: 'var(--ink)',
              padding: '14px 18px',
              borderRadius: 14,
              border: '1px solid var(--accent)',
            }}
          >
            <div style={{ marginTop: 2 }}>
              <Bot size={18} color="var(--accent)" />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--accent)',
                  marginBottom: 4,
                  fontWeight: 600,
                }}
              >
                {t('Đang suy luận…', 'Thinking & synthesizing…')}
              </div>
              <div
                style={{
                  fontSize: 13.5,
                  lineHeight: 1.65,
                  wordBreak: 'break-word',
                }}
              >
                {streamingText ? (
                  <MarkdownRenderer content={streamingText} />
                ) : (
                  <span className="muted">{t('Đang kết nối tới Agent…', 'Connecting to Agent…')}</span>
                )}
              </div>
            </div>
          </article>
        )}
      </div>

      <div ref={bottomRef} />
    </div>
  );
};
