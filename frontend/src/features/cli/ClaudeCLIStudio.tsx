import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
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
  const { project, activeSessionId, setActiveSessionId, closeDrawer } = useUIStore();

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
        text: m.content || '',
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
  const COMMAND_SUGGESTIONS: CLICommandSuggestion[] = [
    { cmd: '/workflow', label: t('Danh mục Quy trình', 'Workflow Catalog'), desc: t('Liệt kê và thực thi toàn bộ quy trình nghiên cứu', 'List and run all research workflows') },
    { cmd: '/lit', label: t('Khảo sát Tài liệu', 'Literature Survey'), desc: t('Tìm kiếm bài báo & phát hiện khoảng trống nghiên cứu', 'Search papers and discover research gaps'), workflowId: 'lit' },
    { cmd: '/outline', label: t('Đề cương 5 Cấp độ', '5-Level Outline'), desc: t('Xây dựng đề cương từ ý tưởng đến bài báo hoàn chỉnh', 'Develop research outline from idea to paper'), workflowId: 'outline' },
    { cmd: '/code', label: t('Thực nghiệm Mã nguồn', 'Experiment Sandbox'), desc: t('Mã nguồn thí nghiệm, sandbox cô lập & VS Code', 'Code experiments, isolated sandbox & VS Code'), workflowId: 'experiment' },
    { cmd: '/paper', label: t('Soạn thảo Bài báo LaTeX', 'LaTeX Manuscript'), desc: t('Soạn thảo và xem trước biên dịch PDF bài báo', 'Draft and preview LaTeX compiled paper'), workflowId: 'paper' },
    { cmd: '/review', label: t('Hội đồng Bình duyệt R1–R3', 'Peer Review R1–R3'), desc: t('Đánh giá học thuật đa tác nhân và phản biện bài báo', 'Multi-agent academic peer review'), workflowId: 'review' },
    { cmd: '/deepresearch', label: t('Nghiên cứu Toàn diện', 'Deep Research'), desc: t('Tự hành toàn bộ chu trình nghiên cứu chuyên sâu', 'Autonomous end-to-end deep research'), workflowId: 'deepresearch' },
    { cmd: '/harness', label: t('Harness Tự động hoá', 'Harness Studio'), desc: t('Quy trình harness tuỳ biến kết hợp kiểm thử giả thuyết', 'Custom harness workflow and hypothesis testing'), workflowId: 'harness' },
    { cmd: '/accept', label: t('Chấp nhận Đề xuất', 'Accept Proposals'), desc: t('Chấp nhận đề xuất cập nhật hoặc chạy thí nghiệm nền', 'Accept proposed changes or background runs') },
    { cmd: '/reject', label: t('Từ chối Đề xuất', 'Reject Proposals'), desc: t('Từ chối đề xuất hoặc huỷ thí nghiệm nền', 'Reject proposed changes or cancel runs') },
    { cmd: '/model', label: t('Cấu hình Mô hình', 'Model Settings'), desc: t('Xem hoặc đổi nhà cung cấp mô hình AI', 'View or change AI model provider') },
    { cmd: '/clear', label: t('Xoá màn hình', 'Clear Terminal'), desc: t('Dọn sạch màn hình làm việc terminal', 'Clean up terminal screen') },
    { cmd: '/help', label: t('Trợ giúp Toàn diện', 'Full Help Manual'), desc: t('Xem danh mục đầy đủ các lệnh và hướng dẫn', 'View complete list of commands and guide') },
  ];

  const filteredSuggestions = COMMAND_SUGGESTIONS.filter((s) =>
    s.cmd.toLowerCase().startsWith(inputVal.trim().toLowerCase())
  );

  // Send turn mutation
  const handleExecute = async (overridePrompt?: string) => {
    const raw = (overridePrompt !== undefined ? overridePrompt : inputVal).trim();
    if (!raw) return;

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
          text: `
| Mã Quy trình | Tên Quy trình | Lệnh thực thi | Mô tả |
| :--- | :--- | :--- | :--- |
| **lit** | Khảo sát Tài liệu & Research Gap | \`/lit <từ khoá>\` | Thu thập bài báo, trích xuất phương pháp & lập bản đồ khoảng trống |
| **outline** | Đề cương Nghiên cứu 5 Cấp độ | \`/outline\` | Phát triển đề cương từng bước từ ý tưởng đến bài báo hoàn chỉnh |
| **experiment** | Thực nghiệm & Mã nguồn Sandbox | \`/code\` | Sinh mã, chạy thử nghiệm cô lập và tích hợp VS Code |
| **paper** | Soạn thảo Bài báo LaTeX | \`/paper\` | Viết từng mục bài báo, biên dịch LaTeX online & local |
| **review** | Hội đồng Bình duyệt R1–R3 | \`/review\` | Đánh giá học thuật nghiêm ngặt, chấm điểm và gợi ý sửa đổi |
| **deepresearch** | Nghiên cứu Toàn diện Đa Tác nhân | \`/deepresearch <chủ đề>\` | Tự động hóa hoàn toàn chu trình nghiên cứu đa bước |
| **harness** | Harness Tự động hoá Tùy biến | \`/harness run <id>\` | Quy trình kiểm thử giả thuyết và chạy thí nghiệm tự hành |

*Gõ \`/workflow run <mã>\` hoặc bấm vào các nút quy trình trên thanh công cụ để thực thi.*
          `.trim(),
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
      if (raw.startsWith('/accept') || raw.startsWith('/reject')) {
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
      const turnRes = await api.post<any>(`/api/chat/sessions/${sid}/turns`, {
        text: raw,
        overrides: {},
      });

      // Poll until completed
      const tid = turnRes.id;
      let finalContent = '';
      let pendingDecisions: any[] = [];

      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 700));
        const updatedSess = await api.get<any>(`/api/chat/sessions/${sid}`);
        const turnObj = (updatedSess.turns || []).find((x: any) => x.id === tid);
        const status = turnObj?.status || 'running';

        if (status === 'completed' || status === 'waiting_approval' || status === 'awaiting_launch') {
          const msgs = updatedSess.messages || [];
          const lastMsg = msgs[msgs.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            finalContent = lastMsg.content;
          }
          pendingDecisions = (updatedSess.approvals || []).filter((a: any) => a.status === 'pending');
          break;
        }
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
