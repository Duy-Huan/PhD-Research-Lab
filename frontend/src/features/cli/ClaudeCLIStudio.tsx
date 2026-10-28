import React, { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import { ChatRunCard } from '../chat/ChatRunCard';
import { waitForChatTurn } from './waitForChatTurn';
import {
  Terminal,
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
  Eraser,
  Plus,
} from 'lucide-react';

/** The CLI studio keeps its own conversation, separate from the main chat; the id survives a reload. */
export const CLI_SESSION_KEY = 'phdlab_cli_session';

interface CLICommandSuggestion {
  cmd: string;
  label: string;
  desc: string;
}

interface CliProvider {
  id: string;
  label: string;
  state?: string;
  detail?: string;
  available?: boolean;
}

type Approval = { id: string; name: string; text: string; decision?: 'approve' | 'reject' };
type CliLog = {
  id: string;
  role: 'user' | 'assistant' | 'workflow' | 'system' | 'approval' | 'launch' | 'console';
  title?: string;
  text: string;
  status?: 'running' | 'done' | 'failed';
  runId?: string;
  turnId?: string;
  provider?: string;
  approvals?: Approval[];
};

const WORKFLOWS = [
  { vi: 'Khảo sát', en: 'Literature', cmd: '/lit ', icon: BookOpen },
  { vi: 'Đề cương', en: 'Outline', cmd: '/outline', icon: FileText },
  { vi: 'Thực nghiệm', en: 'Experiment', cmd: '/code', icon: Code },
  { vi: 'Bài báo', en: 'Paper', cmd: '/paper', icon: FileText },
  { vi: 'Phản biện', en: 'Review', cmd: '/review', icon: ShieldCheck },
  { vi: 'Nghiên cứu sâu', en: 'Deep research', cmd: '/deepresearch ', icon: Sparkles },
  { vi: 'Harness', en: 'Harness', cmd: '/harness list', icon: Sliders },
  { vi: 'Tất cả lệnh', en: 'All commands', cmd: '/workflow list', icon: Layers },
];

const consoleName = typeof navigator !== 'undefined' && /Windows/i.test(navigator.userAgent) ? 'cmd' : 'terminal';
const CLI_NAMES: Record<string, string> ={ claude_code: 'Claude Code', codex: 'Codex', gemini_cli: 'Gemini CLI', antigravity: 'Antigravity' };

const frame: React.CSSProperties = { border: '1px solid var(--line)', borderRadius: 10, background: 'var(--panel)' };
const chip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 9px', fontSize: 12, borderRadius: 8,
  border: '1px solid var(--line)', background: 'var(--bg)', color: 'var(--fg)', cursor: 'pointer', whiteSpace: 'nowrap',
};

function readSavedSession(): string {
  try {
    return localStorage.getItem(CLI_SESSION_KEY) || '';
  } catch {
    return '';
  }
}

let logSeq = 0;
const nextId = () => `cli-${Date.now()}-${++logSeq}`;

export const ClaudeCLIStudio: React.FC = () => {
  const { t } = useI18n();
  const { project, openDrawer } = useUIStore();
  const selectedCliProvider = useUIStore((s) => s.selectedCliProvider || 'claude_code');
  const setSelectedCliProvider = useUIStore((s) => s.setSelectedCliProvider);
  const [launchingTerminal, setLaunchingTerminal] = useState(false);
  const [terminalLaunched, setTerminalLaunched] = useState(false);
  const [sessionId, setSessionIdState] = useState(readSavedSession);
  const [inputVal, setInputVal] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestIdx, setSelectedSuggestIdx] = useState(0);
  const [isExecuting, setIsExecuting] = useState(false);
  const [cliLogs, setCliLogs] = useState<CliLog[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  const setSessionId = (id: string) => {
    setSessionIdState(id);
    try {
      if (id) localStorage.setItem(CLI_SESSION_KEY, id);
      else localStorage.removeItem(CLI_SESSION_KEY);
    } catch {
      // Storage can be unavailable (private window); the session still works until reload.
    }
  };
  const addLogs = (...logs: Array<Omit<CliLog, 'id'> & { id?: string }>) =>
    setCliLogs((prev) => [...prev, ...logs.map((l) => ({ id: nextId(), ...l }))]);
  const fail = (message: string) => addLogs({ role: 'system', text: message, status: 'failed' });

  const { data: modelsData, isLoading: providersLoading } = useQuery<any>({ queryKey: ['models'], queryFn: () => api.get('/api/models') });
  const providers: CliProvider[] = (Array.isArray(modelsData?.providers) ? modelsData.providers : []).filter((p: any) => p.transport === 'cli');
  const labelOf = (id: string) => {
    const bare = id.replace(/^cli:/, '');
    return providers.find((p) => p.id === `cli:${bare}`)?.label || CLI_NAMES[bare] || id;
  };
  const providerLabel = labelOf(selectedCliProvider);

  const { data: sessionData } = useQuery<any>({
    queryKey: ['cli-session', sessionId],
    queryFn: () => api.get(`/api/chat/sessions/${sessionId}`),
    enabled: !!sessionId,
  });

  // Restore the saved conversation once; later turns append their own entries. The conversation's provider is shared
  // with `phdlab chat` (its /model), so the web follows a choice made in cmd.
  useEffect(() => {
    const saved = sessionData?.settings?.provider;
    if (typeof saved === 'string' && saved.startsWith('cli:')) setSelectedCliProvider(saved.slice(4));
    if (!sessionData?.messages?.length) return;
    setCliLogs((prev) => (prev.length ? prev : sessionData.messages.map((m: any) => ({
      id: m.id || nextId(),
      role: m.role === 'user' ? 'user' : 'assistant',
      text: m.content || m.text || '',
      runId: m.run_id,
      provider: m.provider,
    }))));
  }, [sessionData?.id]);

  const chooseProvider = async (id: string) => {
    setSelectedCliProvider(id);
    if (!sessionId) return;
    try {
      await api.put(`/api/chat/sessions/${sessionId}`, { settings: { provider: `cli:${id}` } });
    } catch (err: any) {
      fail(`${t('Không lưu được công cụ cho phiên', 'Could not save the tool for this session')}: ${err.message}`);
    }
  };

  // Stay on the latest entry while the reader is at the bottom, also when text reflows (fonts, narrow screens).
  const stickToBottom = useRef(true);
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const follow = () => { if (stickToBottom.current) el.scrollTop = el.scrollHeight; };
    follow();
    const observer = new ResizeObserver(follow);
    observer.observe(el);
    if (contentRef.current) observer.observe(contentRef.current);
    return () => observer.disconnect();
  }, [cliLogs, isExecuting]);

  const { data: commandCatalog } = useQuery<{ skills: Array<{ name: string; title?: string; description?: string }> }>({
    queryKey: ['skills'], queryFn: () => api.get('/api/skills'),
  });
  const suggestions: CLICommandSuggestion[] = [
    ...['workflow', 'new', 'accept', 'reject', 'clear'].map((name) => ({ cmd: `/${name}`, label: name, desc: '' })),
    ...(commandCatalog?.skills || []).map((s) => ({ cmd: `/${s.name}`, label: s.title || s.name, desc: s.description || '' })),
  ];
  const filteredSuggestions = suggestions.filter((s) => s.cmd.toLowerCase().startsWith(inputVal.trim().toLowerCase()));

  const handleLaunchExternalTerminal = async () => {
    setLaunchingTerminal(true);
    try {
      await api.post(`/api/providers/${selectedCliProvider}/launch`, { terminal: true });
      setTerminalLaunched(true);
      setTimeout(() => mounted.current && setTerminalLaunched(false), 3000);
    } catch (err: any) {
      fail(t('Không mở được CLI: ', 'Could not launch CLI: ') + (err?.message || t('Không khả dụng', 'Unavailable')));
    } finally {
      setLaunchingTerminal(false);
    }
  };

  const readSession = (sid: string) => () => {
    if (!mounted.current) return Promise.reject(new Error('closed'));
    return api.get<any>(`/api/chat/sessions/${sid}`);
  };

  // Show what a finished turn produced: the answer (with its run), a manual launch, or decisions to make.
  const showTurnResult = (sid: string, tid: string, updated: any, status: string) => {
    const answer = updated.messages?.filter((m: any) => m.role === 'assistant' && m.turn_id === tid).at(-1);
    if (status === 'awaiting_launch') {
      addLogs({ role: 'launch', turnId: tid, text: t('Chế độ thủ công: lượt này chờ bạn khởi chạy.', 'Manual mode: this turn waits for you to launch it.') });
    }
    if (answer?.content) addLogs({ role: 'assistant', text: answer.content, runId: answer.run_id, provider: answer.provider });
    const pending = (updated.approvals || []).filter((a: any) => a.status === 'pending');
    if (pending.length) {
      addLogs({ role: 'approval', text: '', approvals: pending.map((a: any) => ({ id: a.id, name: a.name, text: a.reason || a.id })) });
    }
  };

  const launchTurn = async (logId: string, tid: string) => {
    try {
      await api.post(`/api/chat/sessions/${sessionId}/turns/${tid}/launch`, {});
      setCliLogs((prev) => prev.map((l) => (l.id === logId ? { ...l, status: 'done' } : l)));
      const { session: updated, turn } = await waitForChatTurn(readSession(sessionId), tid, 900_000, 700, ['completed', 'waiting_approval']);
      if (mounted.current) showTurnResult(sessionId, tid, updated, turn.status);
    } catch (err: any) {
      if (mounted.current && err?.message !== 'closed') fail(`${t('Lỗi', 'Error')}: ${err.message}`);
    }
  };

  const decide = async (logId: string, approval: Approval, decision: 'approve' | 'reject') => {
    try {
      await api.post(`/api/chat/sessions/${sessionId}/approvals/${approval.id}`, { decision });
      setCliLogs((prev) => prev.map((l) => (l.id !== logId ? l : {
        ...l, approvals: l.approvals?.map((a) => (a.id === approval.id ? { ...a, decision } : a)),
      })));
    } catch (err: any) {
      fail(`${t('Lỗi', 'Error')}: ${err.message}`);
    }
  };

  // The same conversation in the phdlab terminal chat; browser and console then share it.
  const openConsole = async () => {
    try {
      const sid = await ensureSession();
      const res = await api.post<{ launched: boolean; command: string; detail?: string }>(`/api/chat/sessions/${sid}/console`, {});
      addLogs({
        role: 'console',
        text: res.launched
          ? t(`Đã mở ${consoleName} trên phiên này. Lệnh để mở lại:`, `Opened ${consoleName} on this session. Command to reopen:`)
          : t(`Không tự mở được ${consoleName}. Chạy lệnh này trong thư mục PhD Lab:`, `Could not open ${consoleName}. Run this in the PhD Lab folder:`),
        title: res.command,
      });
    } catch (err: any) {
      fail(`${t('Lỗi', 'Error')}: ${err.message}`);
    }
  };
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      fail(t('Không sao chép được; hãy chọn và sao chép lệnh.', 'Could not copy; select the command and copy it.'));
    }
  };

  const ensureSession = async () => {
    if (sessionId) return sessionId;
    const created = await api.post<{ id: string }>('/api/chat/sessions', { settings: { provider: `cli:${selectedCliProvider}` } });
    setSessionId(created.id);
    return created.id;
  };

  const handleExecute = async (overridePrompt?: string) => {
    const raw = (overridePrompt !== undefined ? overridePrompt : inputVal).trim();
    if (!raw) return;
    setInputVal('');
    setShowSuggestions(false);

    if (raw.split(/\s+/)[0] === '/harness' || raw === '/model') {
      openDrawer(raw === '/model' ? 'settings' : 'harness');
      return;
    }
    if (raw === '/clear') {
      setCliLogs([]);
      return;
    }
    if (raw === '/new') {
      try {
        const created = await api.post<{ id: string }>('/api/chat/sessions', {});
        setSessionId(created.id);
        setCliLogs([]);
      } catch (err: any) {
        fail(`${t('Không tạo được phiên mới', 'Could not start a new session')}: ${err.message}`);
      }
      return;
    }
    if (raw === '/workflow' || raw === '/workflow list') {
      addLogs(
        { role: 'user', text: raw },
        {
          role: 'workflow',
          title: t('Danh mục lệnh', 'Command catalog'),
          text: (commandCatalog?.skills || []).map((s) => `/${s.name} - ${s.title || s.name}: ${s.description || ''}`).join('\n'),
        },
      );
      return;
    }

    addLogs({ role: 'user', text: raw });
    setIsExecuting(true);
    try {
      const sid = await ensureSession();
      if (/^\/(accept|reject)(?: all)?$/.test(raw)) {
        const isAccept = raw.startsWith('/accept');
        const current = await api.get<any>(`/api/chat/sessions/${sid}`);
        const pending = (current.approvals || []).filter((a: any) => a.status === 'pending');
        for (const a of pending) {
          await api.post(`/api/chat/sessions/${sid}/approvals/${a.id}`, { decision: isAccept ? 'approve' : 'reject' });
        }
        const names = pending.map((a: any) => a.name).join(', ');
        addLogs({
          role: 'system',
          text: !pending.length ? t('Không có gì chờ duyệt.', 'Nothing pending approval.')
            : isAccept ? `${t('Đã duyệt', 'Approved')}: ${names}` : `${t('Đã từ chối', 'Rejected')}: ${names}`,
        });
        return;
      }

      const turnRes = await api.post<any>(`/api/chat/sessions/${sid}/turns`, {
        text: raw,
        overrides: { provider: `cli:${selectedCliProvider}` },
      });
      const { session: updated, turn } = await waitForChatTurn(readSession(sid), turnRes.id, 900_000);
      if (mounted.current) showTurnResult(sid, turnRes.id, updated, turn.status);
    } catch (err: any) {
      if (mounted.current && err?.message !== 'closed') fail(`${t('Lỗi', 'Error')}: ${err.message}`);
    } finally {
      if (mounted.current) setIsExecuting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showSuggestions && filteredSuggestions.length > 0) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const step = e.key === 'ArrowDown' ? 1 : -1;
        setSelectedSuggestIdx((prev) => (prev + step + filteredSuggestions.length) % filteredSuggestions.length);
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        const selected = filteredSuggestions[selectedSuggestIdx];
        if (selected && selected.cmd !== inputVal.trim()) {
          e.preventDefault();
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
    setShowSuggestions(val.startsWith('/') && !val.includes(' '));
    setSelectedSuggestIdx(0);
  };

  const renderLog = (log: CliLog) => {
    if (log.role === 'user') {
      return (
        <div key={log.id} style={{ display: 'flex', gap: 8, fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--fg)' }}>
          <span aria-hidden style={{ color: 'var(--accent)', fontWeight: 700 }}>❯</span>
          <span style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{log.text}</span>
        </div>
      );
    }
    if (log.role === 'assistant') {
      return (
        <article
          key={log.id}
          aria-label={t('Câu trả lời AI', 'AI answer')}
          style={{ border: '1px solid var(--line)', boxShadow: 'inset 3px 0 0 var(--accent)', borderRadius: 10, padding: '10px 14px 10px 16px', background: 'var(--bg)' }}
        >
          <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--accent)', marginBottom: 6 }}>✦ {log.provider ? labelOf(log.provider) : 'AI'}</div>
          <div style={{ lineHeight: 1.6, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', color: 'var(--fg)' }}>{log.text}</div>
          {log.runId && <ChatRunCard id={log.runId} />}
        </article>
      );
    }
    if (log.role === 'workflow') {
      return (
        <section key={log.id} aria-label={log.title} style={{ ...frame, background: 'var(--bg)', padding: '10px 14px' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)', marginBottom: 6 }}>✦ {log.title}</div>
          <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', lineHeight: 1.5, fontFamily: 'var(--mono)', fontSize: 12.5 }}>{log.text}</div>
        </section>
      );
    }
    if (log.role === 'console') {
      return (
        <div key={log.id} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 13, color: 'var(--muted)' }}>
          <span>{log.text}</span>
          <code style={{ fontFamily: 'var(--mono)', color: 'var(--fg)', background: 'var(--bg-2)', padding: '2px 6px', borderRadius: 6,
            overflowWrap: 'anywhere' }}>{log.title}</code>
          <button type="button" className="btn sm ghost" onClick={() => copy(log.title || '')}>{t('Sao chép lệnh', 'Copy command')}</button>
        </div>
      );
    }
    if (log.role === 'launch') {
      return (
        <div key={log.id} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', color: 'var(--muted)', fontSize: 13 }}>
          <span>{log.text}</span>
          {log.status === 'done' ? <span>{t('Đã khởi chạy.', 'Launched.')}</span> : (
            <button type="button" className="btn sm" onClick={() => launchTurn(log.id, log.turnId || '')}>
              <Play size={12} /> {t('Khởi chạy', 'Launch')}
            </button>
          )}
        </div>
      );
    }
    if (log.role === 'approval') {
      return (
        <section key={log.id} style={{ border: '1px solid var(--warn)', borderRadius: 10, padding: '10px 14px', background: 'var(--warn-soft, var(--bg))' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: 12.5, marginBottom: 8 }}>
            <AlertTriangle size={14} color="var(--warn)" /> {t('Quyết định cần duyệt', 'Decisions to review')}
          </div>
          <ul aria-label={t('Chờ duyệt', 'Pending approval')} style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 6 }}>
            {log.approvals?.map((a) => (
              <li key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <code style={{ fontFamily: 'var(--mono)' }}>{a.name}</code>
                <span style={{ color: 'var(--muted)', flex: '1 1 160px', overflowWrap: 'anywhere' }}>{a.text}</span>
                {a.decision ? (
                  <span>{a.decision === 'approve' ? t('Đã duyệt', 'Approved') : t('Đã từ chối', 'Rejected')}</span>
                ) : (
                  <>
                    <button type="button" className="btn sm" onClick={() => decide(log.id, a, 'approve')}>
                      <CheckCircle2 size={12} /> {t('Duyệt', 'Approve')}
                    </button>
                    <button type="button" className="btn sm ghost" onClick={() => decide(log.id, a, 'reject')}>
                      <X size={12} /> {t('Từ chối', 'Reject')}
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      );
    }
    return (
      <div
        key={log.id}
        role={log.status === 'failed' ? 'alert' : undefined}
        style={{ color: log.status === 'failed' ? 'var(--err)' : 'var(--muted)', fontSize: 12.5, overflowWrap: 'anywhere' }}
      >
        {log.text}
      </div>
    );
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        width: '100%',
        height: '100%',
        minHeight: 0,
        boxSizing: 'border-box',
        padding: '12px max(12px, calc((100% - 980px) / 2))',
        background: 'var(--bg)',
        color: 'var(--fg)',
        fontSize: 13.5,
        overflow: 'hidden',
      }}
    >
      {/* Narrow screens: one scrollable row per strip and icon-only header actions, so the transcript keeps its room. */}
      <style>{`
        .cli-strip { display: flex; gap: 6px; flex-wrap: wrap; flex-shrink: 0; min-width: 0; }
        .cli-header { padding-right: 48px; }
        @media (max-width: 640px) {
          .cli-strip { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: thin; padding-bottom: 2px; }
          .cli-label { display: none; }
        }
      `}</style>
      {/* .cli-header padding keeps the header clear of the shell's floating "Right menu" handle. */}
      <header className="cli-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexShrink: 0, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <Terminal size={16} color="var(--accent)" style={{ flexShrink: 0 }} />
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>
            {t('Chat CLI', 'CLI chat')}
          </h2>
          <span className="cli-label" style={{ color: 'var(--muted)', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}
            title={project?.name || ''}>
            {project?.name || t('Dự án hiện tại', 'Current project')}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <button type="button" className="btn sm ghost" onClick={openConsole} aria-label={t(`Mở trong ${consoleName}`, `Open in ${consoleName}`)}
            title={t('Tiếp tục cuộc trò chuyện này trong cửa sổ lệnh (phdlab chat)', 'Continue this conversation in a console window (phdlab chat)')}>
            <Terminal size={13} /> <span className="cli-label">{t(`Mở trong ${consoleName}`, `Open in ${consoleName}`)}</span>
          </button>
          <button type="button" className="btn sm ghost" onClick={() => handleExecute('/clear')} aria-label={t('Xóa màn hình', 'Clear screen')}
            title={t('Xóa màn hình', 'Clear screen')}>
            <Eraser size={13} /> <span className="cli-label">{t('Xóa màn hình', 'Clear screen')}</span>
          </button>
          <button type="button" className="btn sm ghost" onClick={() => handleExecute('/new')} aria-label={t('Phiên mới', 'New session')}
            title={t('Phiên mới', 'New session')}>
            <Plus size={13} /> <span className="cli-label">{t('Phiên mới', 'New session')}</span>
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, minWidth: 0 }}>
        <div role="radiogroup" aria-label={t('Công cụ CLI', 'CLI provider')} className="cli-strip" style={{ flex: '1 1 auto' }}>
          {providersLoading && (
            <span role="status" style={{ color: 'var(--muted)', fontSize: 12.5 }}>
              {t('Đang kiểm tra các công cụ CLI…', 'Checking CLI tools…')}
            </span>
          )}
          {providers.map((p) => {
            const id = p.id.replace(/^cli:/, '');
            const current = selectedCliProvider === id;
            return (
              <label
                key={p.id}
                title={`${p.state || ''}${p.detail ? `: ${p.detail}` : ''}`}
                style={{ ...chip, borderColor: current ? 'var(--accent)' : 'var(--line)', opacity: p.available === false ? 0.55 : 1,
                  cursor: p.available === false ? 'not-allowed' : 'pointer' }}
              >
                <input type="radio" name="cli-provider" checked={current} disabled={p.available === false}
                  onChange={() => chooseProvider(id)} style={{ margin: 0 }} />
                <span>{p.label}</span>
              </label>
            );
          })}
        </div>
        <button type="button" className="btn sm" onClick={handleLaunchExternalTerminal} disabled={launchingTerminal} style={{ flexShrink: 0 }}
          aria-label={terminalLaunched ? t('Đã mở terminal', 'Terminal opened') : t('Mở terminal ngoài', 'Open external terminal')}
          title={t('Mở CLI đã chọn trong một cửa sổ terminal riêng', 'Open the selected CLI in its own terminal window')}>
          {launchingTerminal ? <RefreshCw size={12} className="spin" /> : terminalLaunched ? <CheckCircle2 size={12} /> : <Play size={12} />}
          <span className="cli-label">{terminalLaunched ? t('Đã mở terminal', 'Terminal opened') : t('Mở terminal ngoài', 'Open external terminal')}</span>
        </button>
      </div>

      <div role="group" aria-label={t('Quy trình', 'Workflows')} className="cli-strip">
        {WORKFLOWS.map((w) => (
          <button key={w.cmd} type="button" style={chip} onClick={() => { setInputVal(w.cmd); inputRef.current?.focus(); }}>
            <w.icon size={12} color="var(--accent)" />
            <span>{t(w.vi, w.en)} <code style={{ fontFamily: 'var(--mono)', color: 'var(--muted)' }}>{w.cmd.trim()}</code></span>
          </button>
        ))}
      </div>

      <div
        ref={scrollRef}
        role="log"
        aria-label={t('Hội thoại CLI', 'CLI conversation')}
        onScroll={(e) => {
          const el = e.currentTarget;
          stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
        style={{ ...frame, flex: 1, minHeight: 96, overflowY: 'auto', padding: 14 }}
      >
        <div ref={contentRef} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {cliLogs.length === 0 && !isExecuting && (
          <div style={{ color: 'var(--muted)', lineHeight: 1.6 }}>
            {t('Gõ câu hỏi, hoặc gõ / để xem danh sách lệnh (/lit, /outline, /code, /paper, /review…). Câu trả lời của AI hiện ở đây.',
              'Type a question, or type / for the command list (/lit, /outline, /code, /paper, /review…). The AI answers appear here.')}
          </div>
        )}
        {cliLogs.map(renderLog)}
        {isExecuting && (
          <div role="status" style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--muted)' }}>
            <RefreshCw size={13} className="spin" /> {t('Đang chạy…', 'Running…')} {providerLabel}
          </div>
        )}
        </div>
      </div>

      <form
        aria-label={t('Lệnh CLI', 'CLI command')}
        onSubmit={(e) => { e.preventDefault(); handleExecute(); }}
        style={{ position: 'relative', flexShrink: 0 }}
      >
        {showSuggestions && filteredSuggestions.length > 0 && (
          <ul role="listbox" aria-label={t('Gợi ý lệnh', 'Command suggestions')}
            style={{ ...frame, position: 'absolute', bottom: 'calc(100% + 6px)', left: 0, right: 0, maxHeight: 220, overflowY: 'auto',
              margin: 0, padding: 4, listStyle: 'none', boxShadow: 'var(--shadow)', zIndex: 5 }}>
            {filteredSuggestions.map((s, idx) => (
              <li
                key={s.cmd}
                role="option"
                aria-selected={idx === selectedSuggestIdx}
                onMouseDown={(e) => { e.preventDefault(); setInputVal(s.cmd + ' '); setShowSuggestions(false); inputRef.current?.focus(); }}
                style={{ display: 'flex', gap: 10, alignItems: 'baseline', padding: '6px 10px', borderRadius: 6, cursor: 'pointer',
                  background: idx === selectedSuggestIdx ? 'var(--accent-soft, var(--bg))' : 'transparent' }}
              >
                <code style={{ fontFamily: 'var(--mono)', color: 'var(--accent)', fontWeight: 700 }}>{s.cmd}</code>
                <span>{s.label}</span>
                <span style={{ color: 'var(--muted)', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0, flex: 1 }}
                  title={s.desc}>{s.desc}</span>
              </li>
            ))}
          </ul>
        )}
        <div style={{ ...frame, display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px 6px 12px' }}>
          <span aria-hidden style={{ color: 'var(--accent)', fontWeight: 700 }}>❯</span>
          <input
            ref={inputRef}
            type="text"
            aria-label={t('Lệnh CLI', 'CLI command')}
            value={inputVal}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={t('Hỏi hoặc gõ / để chọn lệnh…', 'Ask, or type / for commands…')}
            disabled={isExecuting}
            style={{ flex: 1, minWidth: 0, background: 'transparent', border: 'none', outline: 'none', color: 'var(--fg)',
              fontSize: 14, fontFamily: 'var(--mono)', padding: '6px 0' }}
          />
          <button type="submit" className="btn sm" disabled={isExecuting || !inputVal.trim()} aria-label={t('Gửi', 'Send')}>
            <CornerDownLeft size={14} />
          </button>
        </div>
        <div style={{ marginTop: 4, fontSize: 11.5, color: 'var(--muted)' }}>
          {t('Enter để gửi · / để xem lệnh · gửi tới', 'Enter to send · / for commands · sends to')} {providerLabel}
        </div>
      </form>
    </div>
  );
};
