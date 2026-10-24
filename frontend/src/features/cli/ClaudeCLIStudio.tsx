import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import { waitForChatTurn } from './waitForChatTurn';
import {
  Terminal,
  Send,
  Play,
  CheckCircle2,
  AlertTriangle,
  FileText,
  BookOpen,
  Code,
  ShieldCheck,
  RefreshCw,
  Sliders,
  Sparkles,
  Layers,
  X,
  CornerDownLeft,
  ChevronRight,
  Maximize2,
} from 'lucide-react';

interface CLICommandSuggestion {
  cmd: string;
  label: string;
  desc: string;
  workflowId?: string;
}

export const ClaudeCLIStudio: React.FC = () => {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const { project, activeSessionId, setActiveSessionId, closeDrawer, openDrawer } = useUIStore();
  const selectedCliProvider = useUIStore((s) => s.selectedCliProvider || 'claude_code');
  const setSelectedCliProvider = useUIStore((s) => s.setSelectedCliProvider);
  const [launchingTerminal, setLaunchingTerminal] = useState(false);
  const [terminalLaunched, setTerminalLaunched] = useState(false);

  const handleLaunchExternalTerminal = async (pidOverride?: string) => {
    const pid = pidOverride || selectedCliProvider || 'claude_code';
    setLaunchingTerminal(true);
    try {
      await api.post(`/api/providers/${pid}/launch`, { terminal: true });
      setTerminalLaunched(true);
      setTimeout(() => setTerminalLaunched(false), 3000);
    } catch (err: any) {
      console.error(`Failed to launch terminal for ${pid}:`, err);
    } finally {
      setLaunchingTerminal(false);
    }
  };

  const [inputVal, setInputVal] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestIdx, setSelectedSuggestIdx] = useState(0);
  const [isExecuting, setIsExecuting] = useState(false);
  const [cliLogs, setCliLogs] = useState<Array<{
    id: string;
    role: 'user' | 'assistant' | 'tool' | 'workflow' | 'system' | 'approval';
    title?: string;
    text: string;
    status?: 'running' | 'done' | 'failed';
    approvals?: Array<{ id: string; name: string; text: string }>;
  }>>([]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 1. Fetch system config for version and assistant model
  const { data: config } = useQuery<any>({
    queryKey: ['config'],
    queryFn: () => api.get('/api/config'),
  });

  const assistantModel = config?.agent_models?.assistant || 'tự động';
  const { data: modelsData } = useQuery<any>({queryKey: ['models'], queryFn: () => api.get('/api/models')});
  const labVersion = config?.version || '6.4.2';

  // 2. Fetch current session messages if activeSessionId exists
  const { data: sessionData, refetch: refetchSession } = useQuery<any>({
    queryKey: ['chat-session', activeSessionId],
    queryFn: () => (activeSessionId ? api.get(`/api/chat/sessions/${activeSessionId}`) : null),
    enabled: !!activeSessionId,
  });

  // Load existing messages into CLI logs on initial render or session change
  useEffect(() => {
    if (sessionData?.messages && sessionData.messages.length > 0) {
      const initialLogs = sessionData.messages.map((m: any) => ({
        id: m.id || Math.random().toString(),
        role: (m.role === 'user' ? 'user' : 'assistant') as 'user' | 'assistant',
        title: m.role === 'user' ? 'User' : 'PhD Research Lab',
        text: m.content || m.text || '',
      }));
      setCliLogs(initialLogs);
    }
  }, [sessionData?.id]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [cliLogs, isExecuting]);

  // Available workflows & slash commands
  const { data: commandCatalog } = useQuery<{ skills: Array<{name: string; title?: string; description?: string}> }>({
    queryKey: ['skills'], queryFn: () => api.get('/api/skills'),
  });
  const COMMAND_SUGGESTIONS: CLICommandSuggestion[] = [
    ...['workflow', 'new', 'accept', 'reject', 'clear'].map(name => ({cmd: `/${name}`, label: name, desc: ''})),
    ...(commandCatalog?.skills || []).map(s => ({cmd: `/${s.name}`, label: s.title || s.name, desc: s.description || ''})),
  ];

  const filteredSuggestions = COMMAND_SUGGESTIONS.filter((s) =>
    s.cmd.toLowerCase().startsWith(inputVal.trim().toLowerCase())
  );

  // Send turn mutation
  const handleExecute = async (overridePrompt?: string) => {
    const raw = (overridePrompt !== undefined ? overridePrompt : inputVal).trim();
    if (!raw) return;

    if (raw.split(/\s+/)[0] === '/harness' || raw === '/model') {
      openDrawer(raw === '/model' ? 'settings' : 'harness');
      return;
    }

    if (raw === '/clear') {
      setCliLogs([]);
      setInputVal('');
      setShowSuggestions(false);
      return;
    }

    if (raw === '/new') {
      try {
        const newSess = await api.post<{ id: string }>('/api/chat/sessions', {});
        setActiveSessionId(newSess.id);
        setCliLogs([]);
        setInputVal('');
        setShowSuggestions(false);
      } catch (err: any) {
        alert(err.message);
      }
      return;
    }

    // Handle /workflow list directly
    if (raw === '/workflow' || raw === '/workflow list') {
      setCliLogs((prev) => [
        ...prev,
        { id: Math.random().toString(), role: 'user', title: 'User', text: raw },
        {
          id: Math.random().toString(),
          role: 'workflow',
          title: t('Danh mục Quy trình Nghiên cứu PhD Lab', 'PhD Lab Research Workflows'),
          text: (commandCatalog?.skills || []).map(s => `/${s.name} - ${s.title || s.name}: ${s.description || ''}`).join('\n'),
        },
      ]);
      setInputVal('');
      setShowSuggestions(false);
      return;
    }

    // Add user turn to CLI logs
    const userLogId = Math.random().toString();
    setCliLogs((prev) => [
      ...prev,
      { id: userLogId, role: 'user', title: 'User', text: raw },
    ]);
    setInputVal('');
    setShowSuggestions(false);
    setIsExecuting(true);

    try {
      // Ensure session exists
      let sid = activeSessionId;
      if (!sid) {
        const created = await api.post<{ id: string }>('/api/chat/sessions', {});
        sid = created.id;
        setActiveSessionId(sid);
      }

      // Check if command is /accept or /reject
      if (/^\/(accept|reject)(?: all)?$/.test(raw)) {
        const isAccept = raw.startsWith('/accept');
        const sess = await api.get<any>(`/api/chat/sessions/${sid}`);
        const pendingApprovals = (sess.approvals || []).filter((a: any) => a.status === 'pending');
        if (pendingApprovals.length === 0) {
          setCliLogs((prev) => [
            ...prev,
            { id: Math.random().toString(), role: 'system', text: t('Không có gì chờ duyệt.', 'Nothing pending approval.') },
          ]);
        } else {
          for (const a of pendingApprovals) {
            await api.post(`/api/chat/sessions/${sid}/approvals/${a.id}`, {
              decision: isAccept ? 'approve' : 'reject',
            });
          }
          setCliLogs((prev) => [
            ...prev,
            {
              id: Math.random().toString(),
              role: 'system',
              text: isAccept
                ? t('Đã chấp thuận toàn bộ các đề xuất thành công.', 'Successfully approved all pending proposals.')
                : t('Đã từ chối các đề xuất.', 'Rejected pending proposals.'),
            },
          ]);
        }
        setIsExecuting(false);
        refetchSession();
        return;
      }

      // Post turn
      const engine = modelsData?.agent_catalog?.assistant?.engine;
      const provider = !engine ? undefined : /^(cli|app):/.test(engine) ? engine
        : `${['codex', 'claude_code', 'gemini_cli', 'antigravity'].includes(engine) ? 'cli' : 'app'}:${engine}`;
      const turnRes = await api.post<any>(`/api/chat/sessions/${sid}/turns`, {
        text: raw,
        overrides: { ...(provider ? { provider } : {}), model: modelsData?.agent_catalog?.assistant?.selected || '' },
      });

      // Wait for the actual turn; provider failures must be visible immediately.
      const tid = turnRes.id;
      const { session: updatedSess, turn } = await waitForChatTurn(
        () => api.get(`/api/chat/sessions/${sid}`), tid,
        (config?.aiws?.max_turn_s || 900) * 1000
      );
      const finalContent = updatedSess.messages?.filter(m => m.role === 'assistant' && m.turn_id === tid).at(-1)?.content || '';
      const pendingDecisions = (updatedSess.approvals || []).filter(a => a.status === 'pending');
      if (turn.status === 'awaiting_launch') {
        setCliLogs(prev => [...prev, { id: tid, role: 'system', text: t('Chế độ thủ công: chờ khởi chạy trong cuộc hội thoại.', 'Manual mode: waiting for launch in the conversation.') }]);
      }

      if (finalContent) {
        setCliLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            role: 'assistant',
            title: 'PhD Research Lab',
            text: finalContent,
          },
        ]);
      }

      if (pendingDecisions.length > 0) {
        setCliLogs((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            role: 'approval',
            title: t('Quyết định & Chờ duyệt', 'Decisions & Approvals Needed'),
            text: pendingDecisions.map((a: any, idx: number) => `[${idx + 1}] ${a.name} — ${a.reason || a.id}`).join('\n'),
            approvals: pendingDecisions.map((a: any) => ({
              id: a.id,
              name: a.name,
              text: a.reason || a.id,
            })),
          },
        ]);
      }

      refetchSession();
    } catch (err: any) {
      setCliLogs((prev) => [
        ...prev,
        { id: Math.random().toString(), role: 'system', text: `✗ Lỗi: ${err.message}`, status: 'failed' },
      ]);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showSuggestions && filteredSuggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedSuggestIdx((prev) => (prev + 1) % filteredSuggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedSuggestIdx((prev) => (prev - 1 + filteredSuggestions.length) % filteredSuggestions.length);
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault();
        const selected = filteredSuggestions[selectedSuggestIdx];
        if (selected) {
          setInputVal(selected.cmd + ' ');
          setShowSuggestions(false);
          return;
        }
      }
      if (e.key === 'Escape') {
        setShowSuggestions(false);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleExecute();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputVal(val);
    if (val.startsWith('/')) {
      setShowSuggestions(true);
      setSelectedSuggestIdx(0);
    } else {
      setShowSuggestions(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        background: '#0d1117',
        color: '#e6edf3',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: 12.5,
        overflow: 'hidden',
      }}
    >
      {/* 1. Header Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 12px',
          background: '#161b22',
          borderBottom: '1px solid #30363d',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f0883e', fontWeight: 700 }}>
            <Terminal size={15} />
            <span>Claude CLI Studio</span>
          </div>
          <span style={{ fontSize: 11, color: '#7d8590' }}>v{labVersion}</span>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#3fb950', display: 'inline-block' }} />
          <span style={{ fontSize: 11, color: '#58a6ff' }}>{project?.name || t('Dự án Hiện tại', 'Current Project')}</span>
          <span style={{ fontSize: 11, color: '#7d8590' }}>•</span>
          <span style={{ fontSize: 11, color: '#a371f7' }}>{assistantModel}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            type="button"
            onClick={() => handleExecute('/clear')}
            className="btn sm ghost"
            style={{ fontSize: 11, color: '#8b949e', border: '1px solid #30363d', borderRadius: 4, padding: '2px 8px' }}
          >
            {t('Xoá màn hình', 'Clear')}
          </button>
          <button
            type="button"
            onClick={() => handleExecute('/new')}
            className="btn sm ghost"
            style={{ fontSize: 11, color: '#8b949e', border: '1px solid #30363d', borderRadius: 4, padding: '2px 8px' }}
          >
            {t('Đoạn chat mới', 'New Chat')}
          </button>
        </div>
      </div>

      {/* 1.5. Provider Switcher Strip & 1-Click Native Terminal Launcher */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          background: '#13171f',
          borderBottom: '1px solid #21262d',
          flexShrink: 0,
          gap: 8,
          overflowX: 'auto',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, overflowX: 'auto', flex: 1 }}>
          <span style={{ fontSize: 10, color: '#8b949e', textTransform: 'uppercase', fontWeight: 700, letterSpacing: 0.5, flexShrink: 0 }}>
            {t('Provider:', 'Provider:')}
          </span>
          {[
            { id: 'claude_code', label: 'Claude Code', color: '#d97706' },
            { id: 'codex', label: 'OpenAI Codex', color: '#10b981' },
            { id: 'antigravity', label: 'Antigravity (agy)', color: '#3b82f6' },
            { id: 'gemini_cli', label: 'Gemini CLI', color: '#8b5cf6' },
            { id: 'feynman', label: 'Feynman Research', color: '#ec4899' },
            { id: 'opencode', label: 'OpenCode Sandbox', color: '#06b6d4' },
            { id: 'paperorchestra', label: 'PaperOrchestra', color: '#f59e0b' },
            { id: 'openscience', label: 'OpenScience', color: '#6366f1' },
            { id: 'python', label: 'Python venv', color: '#eab308' },
          ].map((p) => {
            const isCur = selectedCliProvider === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedCliProvider(p.id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '3px 8px',
                  fontSize: 11,
                  fontWeight: isCur ? 700 : 500,
                  borderRadius: 6,
                  background: isCur ? 'rgba(210, 96, 42, 0.18)' : '#161b22',
                  border: isCur ? `1px solid ${p.color}` : '1px solid #30363d',
                  color: isCur ? p.color : '#c9d1d9',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s ease',
                }}
              >
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: p.color }} />
                <span>{p.label}</span>
              </button>
            );
          })}
        </div>

        {/* 1-Click Launch External Terminal Button */}
        <button
          type="button"
          onClick={() => handleLaunchExternalTerminal()}
          disabled={launchingTerminal}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            padding: '3px 10px',
            fontSize: 11,
            fontWeight: 600,
            borderRadius: 6,
            background: terminalLaunched ? '#238636' : '#21262d',
            border: '1px solid #388bfd',
            color: '#ffffff',
            cursor: 'pointer',
            flexShrink: 0,
            whiteSpace: 'nowrap',
          }}
          title={t('Mở trực tiếp cửa sổ Terminal ngoài máy tính bằng 1 click', '1-Click launch native external terminal window')}
        >
          {launchingTerminal ? (
            <RefreshCw size={11} className="spin" />
          ) : terminalLaunched ? (
            <CheckCircle2 size={11} />
          ) : (
            <Play size={10} fill="currentColor" />
          )}
          <span>
            {terminalLaunched
              ? t('Đã mở Terminal ngoài!', 'External Terminal Opened!')
              : t('1-Click Mở Terminal Ngoài', '1-Click Open Native Terminal')}
          </span>
        </button>
      </div>

      {/* 2. Quick Workflows Strip */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 12px',
          background: '#0d1117',
          borderBottom: '1px solid #21262d',
          overflowX: 'auto',
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 10.5, color: '#8b949e', textTransform: 'uppercase', fontWeight: 600, letterSpacing: 0.5 }}>
          {t('Quy trình', 'Workflows')}:
        </span>
        {[
          { label: 'Khảo sát /lit', cmd: '/lit ', icon: BookOpen, color: '#58a6ff' },
          { label: 'Đề cương /outline', cmd: '/outline', icon: FileText, color: '#3fb950' },
          { label: 'Thực nghiệm /code', cmd: '/code', icon: Code, color: '#d29922' },
          { label: 'Bài báo /paper', cmd: '/paper', icon: FileText, color: '#f0883e' },
          { label: 'Phản biện /review', cmd: '/review', icon: ShieldCheck, color: '#bc8cff' },
          { label: 'Nghiên cứu /deepresearch', cmd: '/deepresearch ', icon: Sparkles, color: '#79c0ff' },
          { label: 'Harness /harness', cmd: '/harness list', icon: Sliders, color: '#ff7b72' },
          { label: 'Tất cả /workflow', cmd: '/workflow list', icon: Layers, color: '#d2602a' },
        ].map((w) => (
          <button
            key={w.cmd}
            type="button"
            onClick={() => {
              setInputVal(w.cmd);
              inputRef.current?.focus();
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '3px 7px',
              fontSize: 11,
              borderRadius: 6,
              background: '#161b22',
              border: '1px solid #30363d',
              color: w.color,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            <w.icon size={11} />
            <span>{w.label}</span>
          </button>
        ))}
      </div>

      {/* 3. Terminal Body Output Feed */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '14px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {/* Claude CLI Welcome Banner */}
        <div
          style={{
            border: '1px solid #d2602a',
            borderRadius: 8,
            padding: '10px 14px',
            background: 'rgba(210, 96, 42, 0.05)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#d2602a', fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
            <span>✦</span>
            <span>PhD Research Lab — Claude CLI Terminal Mode</span>
          </div>
          <div style={{ color: '#8b949e', fontSize: 12, lineHeight: 1.5 }}>
            {t('Hỗ trợ toàn diện mọi workflow: /lit (Tài liệu), /outline (Đề cương), /code (Mã nguồn), /paper (Bài báo LaTeX), /review (Phản biện), /harness (Kiểm định).',
              'Full support for all workflows: /lit (Literature), /outline (Outline), /code (Code Sandbox), /paper (LaTeX Paper), /review (Peer Review), /harness (Harness Verification).')}
          </div>
          <div style={{ color: '#58a6ff', fontSize: 11.5, marginTop: 4 }}>
            {t('Gõ / để mở danh mục lệnh hoặc chọn trực tiếp quy trình bên trên.', 'Type / to view command catalog or click workflows above.')}
          </div>
        </div>

        {/* Message / Event Logs */}
        {cliLogs.map((log) => {
          if (log.role === 'user') {
            return (
              <div
                key={log.id}
                style={{
                  border: '1px solid #30363d',
                  borderRadius: 8,
                  padding: '10px 12px',
                  background: '#161b22',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#58a6ff', fontWeight: 600, fontSize: 11.5, marginBottom: 4 }}>
                  <span>╭── 👤 User</span>
                  <span style={{ color: '#8b949e' }}>────────────────────────────────</span>
                </div>
                <div style={{ color: '#e6edf3', display: 'flex', alignItems: 'flex-start', gap: 6, paddingLeft: 4 }}>
                  <span style={{ color: '#d2602a', fontWeight: 700 }}>❯</span>
                  <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{log.text}</span>
                </div>
              </div>
            );
          }

          if (log.role === 'workflow') {
            return (
              <div
                key={log.id}
                style={{
                  border: '1px solid #f0883e',
                  borderRadius: 8,
                  padding: '10px 12px',
                  background: 'rgba(240, 136, 62, 0.04)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f0883e', fontWeight: 600, fontSize: 11.5, marginBottom: 6 }}>
                  <span>╭── ✦ {log.title || 'Quy trình Nghiên cứu'}</span>
                  <span style={{ color: '#8b949e' }}>────────────────────────────────</span>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5, color: '#c9d1d9' }}>
                  {log.text}
                </div>
              </div>
            );
          }

          if (log.role === 'approval') {
            return (
              <div
                key={log.id}
                style={{
                  border: '1px solid #d29922',
                  borderRadius: 8,
                  padding: '10px 12px',
                  background: 'rgba(210, 153, 34, 0.08)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#d29922', fontWeight: 700, fontSize: 12, marginBottom: 6 }}>
                  <AlertTriangle size={14} />
                  <span>{log.title || t('Quyết định & Chờ duyệt', 'Decisions Needed')}</span>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', color: '#e6edf3', fontSize: 12, marginBottom: 10, lineHeight: 1.5 }}>
                  {log.text}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => handleExecute('/accept all')}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      padding: '4px 10px',
                      background: '#238636',
                      border: 'none',
                      borderRadius: 6,
                      color: '#ffffff',
                      fontSize: 11.5,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    <CheckCircle2 size={12} />
                    <span>{t('Chấp nhận tất cả', 'Accept All')}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExecute('/reject all')}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      padding: '4px 10px',
                      background: '#21262d',
                      border: '1px solid #30363d',
                      borderRadius: 6,
                      color: '#f85149',
                      fontSize: 11.5,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    <X size={12} />
                    <span>{t('Từ chối tất cả', 'Reject All')}</span>
                  </button>
                </div>
              </div>
            );
          }

          if (log.role === 'system') {
            return (
              <div key={log.id} style={{ color: log.status === 'failed' ? '#f85149' : '#8b949e', fontSize: 11.5, padding: '2px 4px' }}>
                {log.text}
              </div>
            );
          }

          // Assistant response box
          return (
            <div
              key={log.id}
              style={{
                border: '1px solid #30363d',
                borderRadius: 8,
                padding: '10px 14px',
                background: '#161b22',
                boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f0883e', fontWeight: 700, fontSize: 12, marginBottom: 6 }}>
                <span>╭── ✦ PhD Research Lab</span>
                <span style={{ color: '#8b949e', fontWeight: 400 }}>──────────────────────────────</span>
              </div>
              <div style={{ color: '#c9d1d9', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {log.text}
              </div>
            </div>
          );
        })}

        {/* Live Running Spinner Box */}
        {isExecuting && (
          <div
            style={{
              border: '1px dashed #d2602a',
              borderRadius: 8,
              padding: '10px 14px',
              background: 'rgba(210, 96, 42, 0.03)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              color: '#d2602a',
              fontSize: 12,
            }}
          >
            <RefreshCw size={13} className="spin" />
            <span>{t('Đang điều phối tác nhân và thực thi quy trình...', 'Coordinating agents and executing workflow...')}</span>
          </div>
        )}
      </div>

      {/* 4. Autocomplete Popup */}
      {showSuggestions && filteredSuggestions.length > 0 && (
        <div
          style={{
            maxHeight: 180,
            overflowY: 'auto',
            background: '#161b22',
            borderTop: '1px solid #30363d',
            borderBottom: '1px solid #30363d',
            padding: '4px',
            flexShrink: 0,
          }}
        >
          {filteredSuggestions.map((s, idx) => (
            <div
              key={s.cmd}
              onClick={() => {
                setInputVal(s.cmd + ' ');
                setShowSuggestions(false);
                inputRef.current?.focus();
              }}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '5px 10px',
                borderRadius: 4,
                background: idx === selectedSuggestIdx ? '#21262d' : 'transparent',
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: '#d2602a', fontWeight: 700 }}>{s.cmd}</span>
                <span style={{ color: '#e6edf3', fontWeight: 500 }}>{s.label}</span>
              </div>
              <span style={{ color: '#8b949e', fontSize: 11 }}>{s.desc}</span>
            </div>
          ))}
        </div>
      )}

      {/* 5. Prompt Input Box */}
      <div
        style={{
          padding: '10px 12px',
          background: '#161b22',
          borderTop: '1px solid #30363d',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            border: '1px solid #30363d',
            borderRadius: 8,
            padding: '4px 10px',
            background: '#0d1117',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span style={{ color: '#d2602a', fontWeight: 700, fontSize: 14 }}>❯</span>
          <input
            ref={inputRef}
            type="text"
            value={inputVal}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={t('Nhập câu hỏi hoặc / để chọn quy trình/lệnh...', 'Enter prompt or / for workflows/commands...')}
            disabled={isExecuting}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#e6edf3',
              fontSize: 12.5,
              fontFamily: 'inherit',
            }}
          />
          <button
            type="button"
            onClick={() => handleExecute()}
            disabled={isExecuting || !inputVal.trim()}
            style={{
              padding: '4px 8px',
              background: inputVal.trim() ? '#d2602a' : '#21262d',
              border: 'none',
              borderRadius: 6,
              color: '#ffffff',
              cursor: inputVal.trim() ? 'pointer' : 'default',
              display: 'flex',
              alignItems: 'center',
            }}
            title={t('Thực thi lệnh', 'Execute command')}
          >
            <CornerDownLeft size={13} />
          </button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 5, fontSize: 10.5, color: '#8b949e' }}>
          <span>{t('Enter gửi • Shift+Enter dòng mới • / danh sách lệnh', 'Enter to send • Shift+Enter new line • / commands list')}</span>
          <span>{t('Giao diện Dòng lệnh Claude CLI Học thuật', 'Academic Claude CLI Terminal Studio')}</span>
        </div>
      </div>
    </div>
  );
};
