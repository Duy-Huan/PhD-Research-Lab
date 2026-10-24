import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import {
  FileText,
  Save,
  Code,
  Play,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  FlaskConical,
  Plus,
  Download,
  Eye,
  Columns,
  Terminal,
  Cloud,
  Cpu,
  AlertTriangle,
  Loader2,
  FileDown,
} from 'lucide-react';
import { LatexEnginesInfo, PaperProject, CompilePaperResponse } from '../../shared/api/types';

// ── 1. Outline Panel (/api/outline) ────────────────────────────────────────

export const OutlinePanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const { data: outline, isLoading } = useQuery<any>({
    queryKey: ['outline'],
    queryFn: () => api.get('/api/outline'),
  });

  const [fields, setFields] = useState<Record<string, string>>({
    keywords: '',
    topic: '',
    direction: '',
    method: '',
    proposal: '',
  });

  useEffect(() => {
    if (outline) {
      setFields({
        keywords: outline.keywords || '',
        topic: outline.topic || '',
        direction: outline.direction || '',
        method: outline.method || '',
        proposal: outline.proposal || '',
      });
    }
  }, [outline]);

  const saveMutation = useMutation({
    mutationFn: (overrideFields?: Record<string, string>) =>
      api.put('/api/outline', { ...(overrideFields || fields), reason: 'Updated via React Outline Panel' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['outline'] });
      alert(t('Đã lưu đề cương nghiên cứu 5 cấp độ thành công!', '5-Level research outline saved successfully!'));
    },
  });

  const levels = [
    { key: 'keywords', label: t('Cấp 1 — Từ khóa nghiên cứu', 'Level 1 — Research Keywords') },
    { key: 'topic', label: t('Cấp 2 — Chủ đề trọng tâm', 'Level 2 — Central Research Topic') },
    { key: 'direction', label: t('Cấp 3 — Hướng tiếp cận và Giả thuyết', 'Level 3 — Approach & Hypothesis') },
    { key: 'method', label: t('Cấp 4 — Phương pháp và Kiến trúc', 'Level 4 — Methodology & Architecture') },
    { key: 'proposal', label: t('Cấp 5 — Đề cương chi tiết', 'Level 5 — Detailed Proposal') },
  ];

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0 }}>{t('Đề cương nghiên cứu 5 cấp độ', '5-Level Research Outline')}</h4>
        <button className="btn sm accent" onClick={() => saveMutation.mutate(fields)} disabled={saveMutation.isPending}>
          <Save size={13} style={{ marginRight: 4 }} /> {t('Lưu đề cương', 'Save Outline')}
        </button>
      </div>
      {isLoading && <p className="muted">{t('Đang tải đề cương…', 'Loading research outline…')}</p>}
      {levels.map((lv) => (
        <label key={lv.key} className="field" style={{ margin: 0 }}>
          <span>{lv.label}</span>
          <textarea
            className="input"
            rows={lv.key === 'proposal' ? 4 : 2}
            value={fields[lv.key] || ''}
            onChange={(e) => setFields({ ...fields, [lv.key]: e.target.value })}
          />
        </label>
      ))}
    </div>
  );
};

// ── 2. Paper Manuscript Panel (/api/paper) ─────────────────────────────────

export const PaperPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { t } = useI18n();

  // Paper project data
  const { data: paper, isLoading: isPaperLoading } = useQuery<PaperProject>({
    queryKey: ['paper'],
    queryFn: () => api.get('/api/paper'),
  });

  // LaTeX compiler engines discovery
  const { data: enginesData } = useQuery<LatexEnginesInfo>({
    queryKey: ['paper-engines'],
    queryFn: () => api.get('/api/paper/engines'),
  });

  // Editor and preview state
  const [selectedSectionId, setSelectedSectionId] = useState('abstract');
  const [sectionText, setSectionText] = useState('');
  const [engineMode, setEngineMode] = useState<'local' | 'online'>('local');
  const [selectedLocalEngine, setSelectedLocalEngine] = useState<string>('auto');
  const [layoutMode, setLayoutMode] = useState<'template' | 'simple'>('template');
  const [activeView, setActiveView] = useState<'editor' | 'preview' | 'split' | 'log'>('preview');
  const [lastCompiledTime, setLastCompiledTime] = useState<number>(Date.now());
  const [compileResult, setCompileResult] = useState<CompilePaperResponse | null>(null);
  const [logContent, setLogContent] = useState<string>('');
  const [isLogLoading, setIsLogLoading] = useState<boolean>(false);

  const sections = paper?.sections || [];
  const activeSec = sections.find((s) => s.id === selectedSectionId) || sections[0];

  useEffect(() => {
    if (activeSec) {
      setSectionText(activeSec.text || '');
    }
  }, [activeSec?.id, activeSec?.text]);

  // Sync default engine from discovery
  useEffect(() => {
    if (enginesData) {
      if (enginesData.available.length === 0 && enginesData.online) {
        setEngineMode('online');
      }
    }
  }, [enginesData]);

  // Section saving mutation
  const saveSectionMutation = useMutation({
    mutationFn: () =>
      api.put('/api/paper/section', {
        section: activeSec?.id || selectedSectionId,
        text: sectionText,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper'] });
      alert(t('Đã lưu nội dung mục bài báo!', 'Section content saved!'));
    },
    onError: (err: Error) => {
      alert(t(`Lỗi lưu mục bài báo: ${err.message}`, `Failed to save section: ${err.message}`));
    },
  });

  // Compilation mutation
  const compileMutation = useMutation({
    mutationFn: async () => {
      const chosenEngine =
        engineMode === 'online'
          ? 'online'
          : selectedLocalEngine === 'auto'
          ? 'local'
          : selectedLocalEngine;

      const res = await api.post<CompilePaperResponse>('/api/paper/compile', {
        engine: chosenEngine,
        layout: layoutMode,
        allow_online: engineMode === 'online',
      });
      return res;
    },
    onSuccess: (data: CompilePaperResponse) => {
      setCompileResult(data);
      setLastCompiledTime(Date.now());
      queryClient.invalidateQueries({ queryKey: ['paper'] });
      // If user was on editor view, switch to split or preview to see the output
      if (activeView === 'editor') {
        setActiveView('preview');
      }
    },
    onError: (err: any) => {
      const msg = err?.response?.data?.message || err?.message || 'Unknown error';
      alert(t(`Không thể biên dịch LaTeX: ${msg}`, `Failed to compile LaTeX: ${msg}`));
    },
  });

  // Fetch build log
  const fetchLog = async () => {
    setIsLogLoading(true);
    try {
      const res = await api.get<string>('/api/paper/log');
      setLogContent(res || t('(Chưa có bản ghi nhật ký biên dịch)', '(No build log yet)'));
    } catch (e: any) {
      setLogContent(t('Lỗi tải nhật ký: ', 'Failed to load log: ') + (e?.message || ''));
    } finally {
      setIsLogLoading(false);
    }
  };

  const handleSwitchToLog = () => {
    setActiveView('log');
    fetchLog();
  };

  const hasPdf = Boolean(paper?.pdf);
  const pdfUrl = `/api/paper/pdf?t=${lastCompiledTime}`;
  const availableEngines = enginesData?.available || [];
  const isOnlineAvailable = Boolean(enginesData?.online);

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8, fontSize: 15 }}>
          <FileText size={18} color="var(--accent)" />
          <span>{t('Bản thảo Bài báo LaTeX', 'Paper Manuscript')}</span>
        </h4>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button
            className="btn sm accent"
            onClick={() => compileMutation.mutate()}
            disabled={compileMutation.isPending}
            title={t('Biên dịch LaTeX sang tài liệu PDF', 'Compile LaTeX to PDF document')}
          >
            {compileMutation.isPending ? (
              <Loader2 size={13} className="spin" style={{ marginRight: 4 }} />
            ) : (
              <Play size={13} style={{ marginRight: 4 }} />
            )}
            {compileMutation.isPending
              ? t('Đang biên dịch…', 'Compiling…')
              : t('Biên dịch PDF', 'Compile PDF')}
          </button>

          {hasPdf && (
            <>
              <a
                className="btn sm ghost"
                href="/api/paper/pdf?download=1"
                download="main.pdf"
                title={t('Tải xuống tệp PDF', 'Download PDF file')}
                style={{ textDecoration: 'none', display: 'flex', alignItems: 'center' }}
              >
                <Download size={13} style={{ marginRight: 4 }} />
                {t('Tải PDF', 'Download PDF')}
              </a>
              <a
                className="btn sm ghost"
                href="/api/paper/pdf"
                target="_blank"
                rel="noopener noreferrer"
                title={t('Mở bản xem trước PDF trong tab mới', 'Open PDF preview in a new tab')}
                style={{ textDecoration: 'none', display: 'flex', alignItems: 'center' }}
              >
                <ExternalLink size={13} style={{ marginRight: 4 }} />
                {t('Tab mới', 'New Tab')}
              </a>
            </>
          )}

          <a
            className="btn sm ghost"
            href="/api/paper/latex.zip"
            download="latex.zip"
            title={t('Xuất toàn bộ gói nguồn LaTeX dạng tệp nén ZIP', 'Export full LaTeX source code as a ZIP archive')}
            style={{ textDecoration: 'none', display: 'flex', alignItems: 'center' }}
          >
            <FileDown size={13} style={{ marginRight: 4 }} />
            {t('Xuất ZIP', 'Export ZIP')}
          </a>
        </div>
      </div>

      {/* Engine & Preview Mode Configuration */}
      <div
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          {/* Mode Pill Toggle (Local vs Online) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>
              {t('Chế độ biên dịch:', 'Engine Mode:')}
            </span>
            <div style={{ display: 'inline-flex', background: 'var(--bg)', borderRadius: 6, padding: 2, border: '1px solid var(--line)' }}>
              <button
                type="button"
                className={`btn xs ${engineMode === 'local' ? 'accent' : 'ghost'}`}
                onClick={() => setEngineMode('local')}
                style={{ borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px' }}
              >
                <Cpu size={12} />
                <span>{t('Cục bộ', 'Local')}</span>
              </button>
              <button
                type="button"
                className={`btn xs ${engineMode === 'online' ? 'accent' : 'ghost'}`}
                onClick={() => setEngineMode('online')}
                style={{ borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px' }}
              >
                <Cloud size={12} />
                <span>{t('Trực tuyến', 'Online')}</span>
              </button>
            </div>
          </div>

          {/* Layout Mode Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>
              {t('Bố cục:', 'Layout:')}
            </span>
            <select
              className="input sm"
              style={{ padding: '3px 8px', fontSize: 12 }}
              value={layoutMode}
              onChange={(e) => setLayoutMode(e.target.value as 'template' | 'simple')}
            >
              <option value="template">{t('Mẫu xuất bản chuẩn', 'Standard Template')}</option>
              <option value="simple">{t('Bố cục nhanh cho xem trước', 'Quick Layout (Fast Preview)')}</option>
            </select>
          </div>
        </div>

        {/* Engine-specific sub-controls */}
        {engineMode === 'local' ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--muted)' }}>{t('Trình biên dịch cục bộ:', 'Local Compiler:')}</span>
            <select
              className="input sm"
              style={{ flex: 1, minWidth: 160 }}
              value={selectedLocalEngine}
              onChange={(e) => setSelectedLocalEngine(e.target.value)}
            >
              <option value="auto">
                {t('Tự động chọn', 'Auto Detect')} {availableEngines.length > 0 ? `(${availableEngines.join(', ')})` : ''}
              </option>
              {availableEngines.map((eng) => (
                <option key={eng} value={eng}>
                  {eng} ({enginesData?.paths?.[eng] || t('Khả dụng', 'Available')})
                </option>
              ))}
            </select>
            {availableEngines.length === 0 && (
              <span style={{ color: 'var(--amber, #f59e0b)', fontSize: 11.5, display: 'flex', alignItems: 'center', gap: 4 }}>
                <AlertTriangle size={12} />
                {t('Chưa phát hiện trình biên dịch TeX cục bộ như Tectonic hoặc TeX Live. Bạn có thể chọn chế độ Trực tuyến.', 'No local TeX found such as Tectonic or TeX Live. You can switch to Online mode.')}
              </span>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--muted)' }}>
            <Cloud size={14} color="var(--accent)" />
            <span>
              {t(
                'Biên dịch đám mây qua dịch vụ LaTeX công khai (không yêu cầu cài đặt TeX Live hoặc MiKTeX trên máy).',
                'Cloud compilation via public LaTeX service (no TeX Live or MiKTeX installation required).'
              )}
            </span>
          </div>
        )}
      </div>

      {/* Segmented View Tabs */}
      <div style={{ display: 'flex', gap: 6, borderBottom: '1px solid var(--line)', paddingBottom: 6 }}>
        <button
          type="button"
          className={`btn sm ${activeView === 'preview' ? 'accent' : 'ghost'}`}
          onClick={() => setActiveView('preview')}
          style={{ display: 'flex', alignItems: 'center', gap: 5 }}
        >
          <Eye size={13} />
          <span>{t('Xem trước PDF', 'PDF Preview')}</span>
        </button>
        <button
          type="button"
          className={`btn sm ${activeView === 'editor' ? 'accent' : 'ghost'}`}
          onClick={() => setActiveView('editor')}
          style={{ display: 'flex', alignItems: 'center', gap: 5 }}
        >
          <FileText size={13} />
          <span>{t('Soạn thảo LaTeX', 'LaTeX Editor')}</span>
        </button>
        <button
          type="button"
          className={`btn sm ${activeView === 'split' ? 'accent' : 'ghost'}`}
          onClick={() => setActiveView('split')}
          style={{ display: 'flex', alignItems: 'center', gap: 5 }}
        >
          <Columns size={13} />
          <span>{t('Xem song song', 'Split View')}</span>
        </button>
        <button
          type="button"
          className={`btn sm ${activeView === 'log' ? 'accent' : 'ghost'}`}
          onClick={handleSwitchToLog}
          style={{ display: 'flex', alignItems: 'center', gap: 5 }}
        >
          <Terminal size={13} />
          <span>{t('Nhật ký biên dịch', 'Build Log')}</span>
        </button>
      </div>

      {/* Diagnostics / Result Banner */}
      {compileResult && (
        <div
          style={{
            padding: 10,
            borderRadius: 6,
            fontSize: 12,
            background: compileResult.ok ? 'var(--bg-2)' : 'rgba(239, 68, 68, 0.08)',
            border: `1px solid ${compileResult.ok ? 'var(--line)' : 'var(--red, #ef4444)'}`,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
            <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 5, color: compileResult.ok ? 'var(--accent)' : 'var(--red, #ef4444)' }}>
              {compileResult.ok ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
              {compileResult.ok ? t('Biên dịch thành công', 'Compilation Succeeded') : t('Biên dịch thất bại', 'Compilation Failed')}
            </span>
            <div style={{ display: 'flex', gap: 10, color: 'var(--muted)', fontSize: 11.5 }}>
              <span>{t('Trình biên dịch:', 'Engine:')} <b>{compileResult.engine}</b></span>
              <span>{t('Thời gian:', 'Time:')} <b>{compileResult.seconds}s</b></span>
              {compileResult.pages && (
                <span>{t('Số trang:', 'Pages:')} <b>{compileResult.pages}</b></span>
              )}
            </div>
          </div>

          {/* Notes or warnings */}
          {compileResult.notes && compileResult.notes.length > 0 && (
            <div style={{ color: 'var(--amber, #f59e0b)', fontSize: 11.5 }}>
              {compileResult.notes.map((n, i) => (
                <div key={i}>• {n}</div>
              ))}
            </div>
          )}

          {/* Errors list */}
          {compileResult.errors && compileResult.errors.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
              <span style={{ fontWeight: 600, color: 'var(--red, #ef4444)', fontSize: 11.5 }}>
                {t('Danh sách lỗi biên dịch:', 'Compilation Errors:')}
              </span>
              {compileResult.errors.map((err, i) => (
                <div
                  key={i}
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 11,
                    background: 'var(--bg)',
                    padding: '4px 6px',
                    borderRadius: 4,
                  }}
                >
                  <b>{err.section_title || err.section || 'latex'}</b>
                  {err.line ? `:${err.line}` : ''} — {err.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Main Content Area */}
      {isPaperLoading && <p className="muted">{t('Đang tải bản thảo…', 'Loading manuscript…')}</p>}

      {/* View 1: Editor View */}
      {activeView === 'editor' && sections.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select
              className="input sm"
              style={{ flex: 1 }}
              value={activeSec?.id || ''}
              onChange={(e) => setSelectedSectionId(e.target.value)}
            >
              {sections.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title} ({s.state || t('trống', 'empty')} · {s.versions} {t('phiên bản', 'versions')})
                </option>
              ))}
            </select>
            <button
              className="btn sm accent"
              onClick={() => saveSectionMutation.mutate()}
              disabled={saveSectionMutation.isPending}
            >
              <Save size={13} style={{ marginRight: 4 }} /> {t('Lưu mục', 'Save Section')}
            </button>
          </div>

          <textarea
            className="input"
            rows={15}
            style={{ fontFamily: 'var(--mono)', fontSize: 12.5 }}
            value={sectionText}
            onChange={(e) => setSectionText(e.target.value)}
            placeholder={t('Nhập nội dung mã nguồn LaTeX của mục này…', 'Enter LaTeX source code for this section…')}
          />
        </div>
      )}

      {/* View 2: Live PDF Preview */}
      {activeView === 'preview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {hasPdf ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {t('Bản xem trước trực tiếp PDF', 'Live PDF Preview')}
                </span>
                <button
                  type="button"
                  className="btn xs ghost"
                  onClick={() => setLastCompiledTime(Date.now())}
                  title={t('Làm mới bản xem trước', 'Refresh Preview')}
                >
                  <RefreshCw size={12} style={{ marginRight: 4 }} />
                  {t('Làm mới', 'Refresh')}
                </button>
              </div>
              <iframe
                key={lastCompiledTime}
                src={pdfUrl}
                title={t('Xem trước PDF bài báo', 'Paper PDF Preview')}
                style={{
                  width: '100%',
                  height: '560px',
                  border: '1px solid var(--line)',
                  borderRadius: 8,
                  background: 'var(--bg-2)',
                }}
              />
            </div>
          ) : (
            <div
              style={{
                border: '1px dashed var(--line-2)',
                borderRadius: 8,
                padding: 36,
                textAlign: 'center',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 12,
              }}
            >
              <FileText size={32} color="var(--muted)" />
              <div style={{ fontSize: 13, fontWeight: 500 }}>
                {t('Chưa có bản xem trước PDF', 'No PDF Preview Available')}
              </div>
              <p className="muted" style={{ margin: 0, fontSize: 12, maxWidth: 360 }}>
                {t(
                  'Chọn chế độ Cục bộ hoặc Trực tuyến ở thanh cấu hình phía trên, sau đó nhấn "Biên dịch PDF" để tạo bản xem trước bài báo.',
                  'Choose Local or Online mode above, then click "Compile PDF" to generate the paper preview.'
                )}
              </p>
              <button
                className="btn sm accent"
                onClick={() => compileMutation.mutate()}
                disabled={compileMutation.isPending}
              >
                <Play size={13} style={{ marginRight: 4 }} />
                {t('Biên dịch ngay', 'Compile Now')}
              </button>
            </div>
          )}
        </div>
      )}

      {/* View 3: Split View (Editor on top, PDF Preview below) */}
      {activeView === 'split' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Top: Section Editor */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <select
                className="input sm"
                style={{ flex: 1 }}
                value={activeSec?.id || ''}
                onChange={(e) => setSelectedSectionId(e.target.value)}
              >
                {sections.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title} ({s.state || t('trống', 'empty')} · {s.versions} {t('phiên bản', 'versions')})
                  </option>
                ))}
              </select>
              <button
                className="btn sm accent"
                onClick={() => saveSectionMutation.mutate()}
                disabled={saveSectionMutation.isPending}
              >
                <Save size={13} style={{ marginRight: 4 }} /> {t('Lưu mục', 'Save Section')}
              </button>
            </div>

            <textarea
              className="input"
              rows={8}
              style={{ fontFamily: 'var(--mono)', fontSize: 12 }}
              value={sectionText}
              onChange={(e) => setSectionText(e.target.value)}
              placeholder={t('Nội dung LaTeX của mục này…', 'LaTeX content of this section…')}
            />
          </div>

          {/* Bottom: Embedded PDF Preview */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, fontWeight: 600 }}>{t('Xem trước PDF song song', 'Parallel PDF Preview')}</span>
              <button
                type="button"
                className="btn xs ghost"
                onClick={() => setLastCompiledTime(Date.now())}
              >
                <RefreshCw size={11} style={{ marginRight: 3 }} /> {t('Làm mới', 'Refresh')}
              </button>
            </div>
            {hasPdf ? (
              <iframe
                key={lastCompiledTime}
                src={pdfUrl}
                title={t('Xem trước PDF song song', 'Parallel PDF Preview')}
                style={{
                  width: '100%',
                  height: '420px',
                  border: '1px solid var(--line)',
                  borderRadius: 8,
                  background: 'var(--bg-2)',
                }}
              />
            ) : (
              <div
                style={{
                  border: '1px dashed var(--line-2)',
                  borderRadius: 8,
                  padding: 24,
                  textAlign: 'center',
                }}
              >
                <p className="muted" style={{ margin: 0, fontSize: 12 }}>
                  {t('Chưa có bản xem trước PDF. Nhấn "Biên dịch PDF" để tạo bản PDF.', 'No PDF preview yet. Click "Compile PDF" to generate.')}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* View 4: Build Log Viewer */}
      {activeView === 'log' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>{t('Nhật ký biên dịch LaTeX chi tiết', 'Detailed LaTeX Build Log')}</span>
            <button
              type="button"
              className="btn xs ghost"
              onClick={fetchLog}
              disabled={isLogLoading}
            >
              <RefreshCw size={11} style={{ marginRight: 3 }} /> {t('Tải lại nhật ký', 'Reload Log')}
            </button>
          </div>
          <pre
            style={{
              background: 'var(--bg-2)',
              border: '1px solid var(--line)',
              borderRadius: 6,
              padding: 10,
              fontSize: 11,
              fontFamily: 'var(--mono)',
              maxHeight: 460,
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              margin: 0,
            }}
          >
            {isLogLoading ? t('Đang tải nhật ký…', 'Loading log…') : logContent}
          </pre>
        </div>
      )}
    </div>
  );
};

// ── 3. Code & VS Code Panel (/api/code) ────────────────────────────────────

export const CodePanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const [newProjectName, setNewProjectName] = useState('');

  const { data: codeData, isLoading } = useQuery<any>({
    queryKey: ['code-projects'],
    queryFn: () => api.get('/api/code'),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post('/api/code', {
        name: newProjectName.trim(),
        description: 'Created from React UI',
        git: true,
        seed: true,
      }),
    onSuccess: () => {
      setNewProjectName('');
      queryClient.invalidateQueries({ queryKey: ['code-projects'] });
    },
  });

  const vscodeMutation = useMutation({
    mutationFn: () => api.post('/api/code/vscode'),
    onError: (err: Error) =>
      alert(t(`Lỗi mở VS Code: ${err.message}`, `Failed to open VS Code: ${err.message}`)),
  });

  const projects = codeData?.projects || [];

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Code size={18} color="var(--accent)" />
          <span>{t('Dự án Mã nguồn và VS Code', 'Code Workspace & VS Code')}</span>
        </h4>
        <button className="btn sm accent" onClick={() => vscodeMutation.mutate()}>
          <ExternalLink size={13} style={{ marginRight: 4 }} /> {t('Mở trong VS Code', 'Open in VS Code')}
        </button>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (newProjectName.trim()) createMutation.mutate();
        }}
        style={{ display: 'flex', gap: 8 }}
      >
        <input
          className="input sm"
          style={{ flex: 1 }}
          placeholder={t('Tên repo mã nguồn mới (ví dụ: wavelet-bench)…', 'New code repository name (e.g. wavelet-bench)…')}
          value={newProjectName}
          onChange={(e) => setNewProjectName(e.target.value)}
        />
        <button type="submit" className="btn sm ghost" disabled={createMutation.isPending}>
          <Plus size={13} style={{ marginRight: 4 }} /> {t('Tạo Repo', 'Create Repo')}
        </button>
      </form>

      {isLoading && <p className="muted">{t('Đang tải danh sách dự án code…', 'Loading code projects…')}</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {projects.map((p: any) => (
          <div
            key={p.name}
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 8,
              padding: 10,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <b style={{ fontSize: 13.5 }}>{p.name}</b>
              <div className="muted" style={{ fontSize: 12 }}>{p.path || p.description || 'Python venv + Git'}</div>
            </div>
            {codeData?.active === p.name && (
              <span className="chip ok" style={{ fontSize: 11 }}>{t('Đang mở', 'Active')}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ── 4. Protocols & Experiments Panel (/api/research/topics/{tid}/protocols) ─

export const ProtocolsPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const { activeTopicId } = useUIStore();
  const [title, setTitle] = useState('Baseline Wavelet Shrinkage Protocol');
  const [hypothesis, setHypothesis] = useState('Adaptive shrinkage improves PSNR by >= 1.5 dB over fixed threshold');

  const { data: protData } = useQuery<{ protocols: any[] }>({
    queryKey: ['protocols', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/protocols`),
    enabled: !!activeTopicId,
  });

  const { data: expData } = useQuery<{ experiments: any[] }>({
    queryKey: ['experiments', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/experiments`),
    enabled: !!activeTopicId,
  });

  const createProtocolMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/research/topics/${activeTopicId}/protocols`, {
        title,
        hypothesis,
        dataset: { name: 'synthetic_gaussian_1d', split: 'test', seed: 42, n_samples: 64 },
        baseline: { name: 'moving_average', params: { window: 3 } },
        treatment: { name: 'soft_threshold', params: { alphas: [0.05, 0.1, 0.15] } },
        metrics: ['psnr_db', 'mae'],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['protocols', activeTopicId] });
    },
  });

  const approveProtocolMutation = useMutation({
    mutationFn: ({ pid, digest }: { pid: string; digest: string }) =>
      api.post(`/api/research/topics/${activeTopicId}/protocols/${pid}/approve`, {
        digest,
        note: 'Approved via Protocols Panel',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['protocols', activeTopicId] });
    },
  });

  if (!activeTopicId) {
    return (
      <div style={{ padding: 16 }}>
        <p className="muted">{t('Vui lòng chọn Chủ đề để quản lý Giao thức và Thí nghiệm.', 'Please select a Topic to manage Protocols & Experiments.')}</p>
      </div>
    );
  }

  const protocols = protData?.protocols || [];
  const experiments = expData?.experiments || [];

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <FlaskConical size={18} color="var(--accent)" />
          <span>{t('Giao thức và Thí nghiệm Có Kiểm soát', 'Controlled Protocols & Experiments')}</span>
        </h4>
        <button className="btn sm accent" onClick={() => createProtocolMutation.mutate()}>
          <Plus size={13} style={{ marginRight: 4 }} /> {t('Tạo Giao thức', 'Create Protocol')}
        </button>
      </div>

      <div style={{ display: 'grid', gap: 6 }}>
        <input className="input sm" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('Tên Giao thức', 'Protocol Title')} />
        <input className="input sm" value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} placeholder={t('Giả thuyết kiểm định', 'Testable Hypothesis')} />
      </div>

      <b style={{ fontSize: 13 }}>{t('Danh sách Giao thức', 'Protocols List')} ({protocols.length})</b>
      {protocols.map((pr: any) => (
        <div
          key={pr.id}
          style={{
            background: 'var(--panel)',
            border: '1px solid var(--line)',
            borderRadius: 8,
            padding: 10,
            fontSize: 12.5,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <b>{pr.payload?.title || pr.id}</b> (rev {pr.revision})
            <div className="muted" style={{ fontSize: 11.5 }}>digest: {pr.digest?.slice(0, 16)}…</div>
          </div>
          {pr.approval ? (
            <span className="chip ok" style={{ fontSize: 11 }}>
              <CheckCircle2 size={11} style={{ marginRight: 3 }} /> {t('Đã duyệt', 'Approved')}
            </span>
          ) : (
            <button
              className="btn sm ghost"
              onClick={() => approveProtocolMutation.mutate({ pid: pr.id, digest: pr.digest })}
            >
              {t('Phê duyệt', 'Approve')}
            </button>
          )}
        </div>
      ))}

      <b style={{ fontSize: 13 }}>{t('Kết quả Thí nghiệm', 'Experiment Results')} ({experiments.length})</b>
      {experiments.map((ex: any) => (
        <div
          key={ex.id}
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--line-2)',
            borderRadius: 8,
            padding: 10,
            fontSize: 12,
          }}
        >
          <b>Run {ex.id}</b> · {t('Trạng thái:', 'Status:')} <b>{ex.status}</b>
        </div>
      ))}
    </div>
  );
};
