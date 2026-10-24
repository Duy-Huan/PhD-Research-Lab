import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { FigurePreset, FigureRecord } from '../../shared/api/types';
import {
  BarChart3,
  Plus,
  CheckCircle2,
  ShieldAlert,
  Download,
  RefreshCw,
  FileCode2,
  Paperclip,
  ZoomIn,
  ZoomOut,
  Sliders,
} from 'lucide-react';

export const FigureStudioPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { activeTopicId } = useUIStore();
  const [selectedFigureId, setSelectedFigureId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [zoom, setZoom] = useState<number>(100);

  // Create form state
  const [title, setTitle] = useState('PSNR vs Noise Sigma Across Methods');
  const [caption, setCaption] = useState('Deterministic comparison across noise levels with 95% CI.');
  const [category, setCategory] = useState<'plot_2d' | 'comparison_plate' | 'diagram' | 'waveform' | 'surface_3d'>('plot_2d');
  const [plotKind, setPlotKind] = useState<'line' | 'bar' | 'scatter' | 'ablation'>('line');
  const [preset, setPreset] = useState('ieee-single-column');
  const [palette, setPalette] = useState<'colorblind-safe' | 'grayscale' | 'viridis' | 'publication-classic'>('colorblind-safe');
  const [xLabel, setXLabel] = useState('Noise Sigma');
  const [yLabel, setYLabel] = useState('PSNR');
  const [xUnit, setXUnit] = useState('sigma');
  const [yUnit, setYUnit] = useState('dB');
  const [dotSource, setDotSource] = useState('digraph G { rankdir=LR; Ingest -> Verify -> Publish; }');
  const [azimuth, setAzimuth] = useState(38);
  const [elevation, setElevation] = useState(28);
  const [approvalNote, setApprovalNote] = useState('');
  const [attachSection, setAttachSection] = useState('experiments');

  // Probe capabilities & presets
  const { data: capData } = useQuery<{ presets: FigurePreset[]; renderers: Record<string, unknown> }>({
    queryKey: ['figure-capabilities'],
    queryFn: () => api.get('/api/figures/capabilities'),
  });

  // List topic figures
  const { data: figuresData, isLoading } = useQuery<{ figures: FigureRecord[] }>({
    queryKey: ['figures', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/figures`),
    enabled: !!activeTopicId,
  });

  const figures = figuresData?.figures || [];
  const activeFigure = figures.find((f) => f.id === selectedFigureId) || figures[0] || null;
  const presets = capData?.presets || [];

  // Fetch detailed figure (with versions & SVG preview)
  const { data: figureDetail } = useQuery<FigureRecord>({
    queryKey: ['figure-detail', activeTopicId, activeFigure?.id],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/figures/${activeFigure?.id}`),
    enabled: !!activeTopicId && !!activeFigure?.id,
  });

  const fig = figureDetail || activeFigure;

  const createMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        title: title.trim() || 'Scientific Figure',
        caption: caption.trim(),
        category,
        plot_kind: plotKind,
        x_label: xLabel,
        y_label: yLabel,
        x_unit: xUnit,
        y_unit: yUnit,
        style: { preset, palette },
        outputs: category === 'diagram' ? ['svg', 'dot', 'pdf'] : ['svg', 'png', 'pdf', 'html'],
      };

      if (category === 'plot_2d') {
        payload.source = {
          kind: 'inline_series',
          x_values: [10, 20, 30, 40],
          series: {
            Proposed: [34.2, 31.5, 29.8, 28.1],
            Baseline: [32.0, 29.1, 27.3, 25.6],
          },
          error_bars: { Proposed: [0.2, 0.25, 0.3, 0.35] },
          error_bar_type: 'ci95',
        };
      } else if (category === 'comparison_plate') {
        payload.source = {
          kind: 'comparison_plate',
          comparison_panels: [
            { label: 'Ground Truth', psnr_db: 99.9, ssim: 1.0 },
            { label: 'Noisy Input', psnr_db: 20.17, ssim: 0.512 },
            { label: 'Proposed Hybrid', psnr_db: 31.84, ssim: 0.924 },
          ],
        };
      } else if (category === 'diagram') {
        payload.renderer = 'graphviz';
        payload.source = {
          kind: 'diagram_dot',
          dot_source: dotSource,
          is_illustrative_only: true,
        };
      } else if (category === 'waveform') {
        payload.renderer = 'wavedrom';
        payload.source = {
          kind: 'waveform_json',
          waveform: {
            signal: [
              { name: 'clk', wave: 'p.....' },
              { name: 'tvalid', wave: '01...0' },
              { name: 'tready', wave: '0.1..0' },
            ],
          },
          is_illustrative_only: true,
        };
      } else if (category === 'surface_3d') {
        payload.renderer = 'pyvista_3d';
        payload.source = {
          kind: 'surface_3d',
          mesh_3d: {
            azimuth_deg: azimuth,
            elevation_deg: elevation,
            z_grid: [
              [0.2, 0.4, 0.5, 0.3],
              [0.4, 0.85, 0.95, 0.6],
              [0.5, 0.92, 1.0, 0.7],
              [0.3, 0.55, 0.65, 0.35],
            ],
          },
        };
      }

      return api.post<FigureRecord>(`/api/research/topics/${activeTopicId}/figures`, payload);
    },
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['figures', activeTopicId] });
      setSelectedFigureId(created.id);
      setShowCreate(false);
    },
  });

  const styleMutation = useMutation({
    mutationFn: (newStyle: Record<string, unknown>) =>
      api.put<FigureRecord>(`/api/research/topics/${activeTopicId}/figures/${fig?.id}/style`, {
        style: newStyle,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['figures', activeTopicId] });
      queryClient.invalidateQueries({ queryKey: ['figure-detail', activeTopicId, fig?.id] });
    },
  });

  const validateMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/figures/${fig?.id}/validate`, { version: fig?.selected_version || fig?.current_version }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['figure-detail', activeTopicId, fig?.id] });
    },
  });

  const approveMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/research/topics/${activeTopicId}/figures/${fig?.id}/approve`, {
        version: fig?.selected_version || fig?.current_version,
        note: approvalNote || 'Verified numerical and visual integrity.',
      }),
    onSuccess: () => {
      setApprovalNote('');
      queryClient.invalidateQueries({ queryKey: ['figures', activeTopicId] });
      queryClient.invalidateQueries({ queryKey: ['figure-detail', activeTopicId, fig?.id] });
    },
  });

  const attachMutation = useMutation({
    mutationFn: () =>
      api.post<{ attached: boolean; section: string; latex_snippet: string }>(
        `/api/research/topics/${activeTopicId}/figures/${fig?.id}/attach-paper`,
        {
          section: attachSection,
          version: fig?.selected_version || fig?.current_version,
        }
      ),
    onSuccess: (res) => {
      alert(`Đã đính kèm LaTeX snippet vào mục "${res.section}" của bài báo!`);
    },
  });

  if (!activeTopicId) {
    return (
      <div style={{ padding: 16 }}>
        <p className="muted">Vui lòng chọn một Topic để mở Figure Studio (v6.4.0).</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <BarChart3 size={18} color="var(--accent)" />
          <span>Figure Studio & Kiểm định Đồ thị (v6.4.0)</span>
        </h4>
        <button className="btn sm accent" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} style={{ marginRight: 4 }} /> Tạo Figure mới
        </button>
      </div>

      <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
        Biểu đồ chuẩn xuất bản (IEEE / ACM / Thesis), kiểm tra chéo mã băm SHA-256 với dữ liệu gốc, lưu trữ mã nguồn tái lập <code>source-script.py</code>.
      </p>

      {/* Create Form */}
      {showCreate && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createMutation.mutate();
          }}
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--line-2)',
            borderRadius: 8,
            padding: 12,
            display: 'grid',
            gap: 10,
          }}
        >
          <b>Tạo biểu đồ khoa học mới (FigureSpec 1.0)</b>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <label className="field" style={{ margin: 0 }}>
              <span>Tiêu đề biểu đồ</span>
              <input className="input sm" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </label>
            <label className="field" style={{ margin: 0 }}>
              <span>Loại biểu đồ (Category)</span>
              <select
                className="input sm"
                value={category}
                onChange={(e) => setCategory(e.target.value as any)}
              >
                <option value="plot_2d">2D Publication Plot (Line/Bar/Ablation)</option>
                <option value="comparison_plate">Multi-Panel Image Comparison Plate</option>
                <option value="diagram">Graphviz DOT Architecture / DAG</option>
                <option value="waveform">WaveDrom Digital Timing Waveform</option>
                <option value="surface_3d">3D Scientific Surface / Mesh</option>
              </select>
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
            <label className="field" style={{ margin: 0 }}>
              <span>Preset định dạng</span>
              <select className="input sm" value={preset} onChange={(e) => setPreset(e.target.value)}>
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
                {presets.length === 0 && <option value="ieee-single-column">IEEE Single Column</option>}
              </select>
            </label>
            <label className="field" style={{ margin: 0 }}>
              <span>Bảng màu (Palette)</span>
              <select className="input sm" value={palette} onChange={(e) => setPalette(e.target.value as any)}>
                <option value="colorblind-safe">Colorblind-Safe (Okabe-Ito)</option>
                <option value="publication-classic">Publication Classic</option>
                <option value="viridis">Viridis Perceptual</option>
                <option value="grayscale">Grayscale Print</option>
              </select>
            </label>
            {category === 'plot_2d' && (
              <label className="field" style={{ margin: 0 }}>
                <span>Kiểu đồ thị 2D</span>
                <select className="input sm" value={plotKind} onChange={(e) => setPlotKind(e.target.value as any)}>
                  <option value="line">Line + Error Bars</option>
                  <option value="bar">Bar Chart</option>
                  <option value="ablation">Ablation Comparison</option>
                  <option value="scatter">Scatter</option>
                </select>
              </label>
            )}
          </div>

          {category === 'plot_2d' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8 }}>
              <input className="input sm" value={xLabel} onChange={(e) => setXLabel(e.target.value)} placeholder="Trục X" />
              <input className="input sm" value={xUnit} onChange={(e) => setXUnit(e.target.value)} placeholder="Đơn vị X" />
              <input className="input sm" value={yLabel} onChange={(e) => setYLabel(e.target.value)} placeholder="Trục Y" />
              <input className="input sm" value={yUnit} onChange={(e) => setYUnit(e.target.value)} placeholder="Đơn vị Y" />
            </div>
          )}

          {category === 'diagram' && (
            <label className="field" style={{ margin: 0 }}>
              <span>Mã nguồn Graphviz DOT</span>
              <textarea
                className="input"
                rows={3}
                style={{ fontFamily: 'var(--mono)', fontSize: 12 }}
                value={dotSource}
                onChange={(e) => setDotSource(e.target.value)}
              />
            </label>
          )}

          {category === 'surface_3d' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <label className="field" style={{ margin: 0 }}>
                <span>Góc xoay Azimuth ({azimuth}°)</span>
                <input type="range" min={0} max={360} value={azimuth} onChange={(e) => setAzimuth(Number(e.target.value))} />
              </label>
              <label className="field" style={{ margin: 0 }}>
                <span>Góc nghiêng Elevation ({elevation}°)</span>
                <input type="range" min={5} max={85} value={elevation} onChange={(e) => setElevation(Number(e.target.value))} />
              </label>
            </div>
          )}

          <label className="field" style={{ margin: 0 }}>
            <span>Chú thích (Caption)</span>
            <input className="input sm" value={caption} onChange={(e) => setCaption(e.target.value)} />
          </label>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button type="button" className="btn sm ghost" onClick={() => setShowCreate(false)}>Huỷ</button>
            <button type="submit" className="btn sm accent" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Đang kết xuất…' : 'Kết xuất & Kiểm định'}
            </button>
          </div>
        </form>
      )}

      {/* Figure Selector & Live Studio */}
      {figures.length > 0 && fig && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select
              className="input sm"
              style={{ flex: 1 }}
              value={fig.id}
              onChange={(e) => setSelectedFigureId(e.target.value)}
            >
              {figures.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.title} (v{f.current_version} · {f.status.toUpperCase()})
                </option>
              ))}
            </select>
            <button
              className="btn sm ghost"
              onClick={() => validateMutation.mutate()}
              disabled={validateMutation.isPending}
              title="Chạy kiểm định QA v6.4.2"
            >
              <RefreshCw size={13} style={{ marginRight: 4 }} /> Kiểm định QA
            </button>
          </div>

          {/* SVG Canvas with Zoom Controls */}
          <div
            style={{
              background: '#ffffff',
              border: '1px solid var(--line)',
              borderRadius: 8,
              padding: 12,
              position: 'relative',
              overflow: 'auto',
              minHeight: 240,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
            }}
          >
            <div style={{ position: 'absolute', top: 8, right: 8, display: 'flex', gap: 4 }}>
              <button className="btn sm ghost" onClick={() => setZoom((z) => Math.max(50, z - 20))}>
                <ZoomOut size={13} />
              </button>
              <span className="chip" style={{ fontSize: 11 }}>{zoom}%</span>
              <button className="btn sm ghost" onClick={() => setZoom((z) => Math.min(200, z + 20))}>
                <ZoomIn size={13} />
              </button>
            </div>
            {fig.svg_preview ? (
              <div
                style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'center center', transition: 'transform 0.15s' }}
                dangerouslySetInnerHTML={{ __html: fig.svg_preview }}
              />
            ) : (
              <span className="muted">Đang tải bản xem trước SVG…</span>
            )}
          </div>

          {/* Quick Style Preset & Version Bar */}
          <div
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 8,
              padding: 10,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 8,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Sliders size={14} color="var(--accent)" />
              <span style={{ fontSize: 12.5, fontWeight: 600 }}>Đổi Preset (tạo version bất biến mới):</span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['ieee-single-column', 'ieee-double-column', 'acm', 'thesis'].map((pr) => (
                <button
                  key={pr}
                  className="btn sm ghost"
                  onClick={() => styleMutation.mutate({ preset: pr })}
                  disabled={styleMutation.isPending}
                >
                  {pr}
                </button>
              ))}
            </div>
          </div>

          {/* Verification & Provenance Card */}
          {fig.verification && (
            <div
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--line)',
                borderRadius: 8,
                padding: 12,
                display: 'grid',
                gap: 8,
                fontSize: 12.5,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <b>Báo cáo Kiểm định Khoa học & Nguồn gốc (QA v{fig.verification.validator_version})</b>
                <span
                  className={`chip ${
                    fig.verification.overall_status === 'passed' || fig.status === 'approved'
                      ? 'ok'
                      : fig.verification.overall_status === 'failed'
                      ? 'err'
                      : 'warn'
                  }`}
                >
                  {fig.status === 'approved' ? 'APPROVED' : fig.verification.overall_status.toUpperCase()}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {Object.entries(fig.verification.tests || {}).map(([k, v]) => (
                  <span key={k} className="chip" style={{ fontSize: 11 }}>
                    {k}: <b>{v}</b>
                  </span>
                ))}
              </div>

              {fig.provenance && (
                <div className="muted" style={{ fontSize: 11.5, fontFamily: 'var(--mono)' }}>
                  spec_sha256: {fig.provenance.spec_sha256?.slice(0, 16)}… · data_sha256: {fig.provenance.data_sha256?.slice(0, 16)}… · renderer: {fig.provenance.renderer_used}
                </div>
              )}

              {fig.verification.warnings?.length > 0 && (
                <div style={{ color: 'var(--warn)', fontSize: 12 }}>
                  <ShieldAlert size={13} style={{ display: 'inline', marginRight: 4 }} />
                  {fig.verification.warnings.join(' | ')}
                </div>
              )}

              {/* Export Links */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', paddingTop: 4 }}>
                {['svg', 'png', 'pdf', 'script', 'provenance'].map((fmt) => (
                  <a
                    key={fmt}
                    className="btn sm ghost"
                    href={`/api/research/topics/${activeTopicId}/figures/${fig.id}/export/${fmt}?version=${fig.selected_version || fig.current_version}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: 'none' }}
                  >
                    {fmt === 'script' ? <FileCode2 size={13} style={{ marginRight: 4 }} /> : <Download size={13} style={{ marginRight: 4 }} />}
                    Xuất {fmt.toUpperCase()}
                  </a>
                ))}
              </div>

              {/* Human Approval & Paper Attachment */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', borderTop: '1px solid var(--line-2)', paddingTop: 8, flexWrap: 'wrap' }}>
                {fig.status !== 'approved' ? (
                  <>
                    <input
                      className="input sm"
                      style={{ flex: 1 }}
                      placeholder="Ghi chú phê duyệt của nhà nghiên cứu…"
                      value={approvalNote}
                      onChange={(e) => setApprovalNote(e.target.value)}
                    />
                    <button
                      className="btn sm accent"
                      onClick={() => approveMutation.mutate()}
                      disabled={approveMutation.isPending}
                    >
                      <CheckCircle2 size={13} style={{ marginRight: 4 }} /> Phê duyệt Figure
                    </button>
                  </>
                ) : (
                  <>
                    <select
                      className="input sm"
                      value={attachSection}
                      onChange={(e) => setAttachSection(e.target.value)}
                    >
                      <option value="experiments">Mục: Experiments</option>
                      <option value="results">Mục: Results</option>
                      <option value="method">Mục: Method</option>
                      <option value="introduction">Mục: Introduction</option>
                    </select>
                    <button
                      className="btn sm accent"
                      onClick={() => attachMutation.mutate()}
                      disabled={attachMutation.isPending}
                    >
                      <Paperclip size={13} style={{ marginRight: 4 }} /> Chèn LaTeX vào Bài báo
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {figures.length === 0 && !isLoading && !showCreate && (
        <p className="muted" style={{ fontSize: 13 }}>
          Chưa có biểu đồ nào trong Topic này. Bấm "Tạo Figure mới" để khởi tạo đồ thị chuẩn IEEE/ACM.
        </p>
      )}
    </div>
  );
};
