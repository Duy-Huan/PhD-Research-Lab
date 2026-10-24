import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { MarkdownRenderer } from '../../shared/ui/MarkdownRenderer';
import {
  Award,
  Upload,
  Play,
  Check,
  X,
  Download,
  FileCode,
  MessageSquare,
  AlertTriangle,
  Sparkles,
  Trash2,
} from 'lucide-react';

interface ReviewMeta {
  id: string;
  title?: string;
  file?: string;
  n_reviewers?: number;
  venue?: {
    kind?: string;
    tier?: string;
    name?: string;
  };
}

interface ReviewIssue {
  id: string;
  severity?: string;
  category?: string;
  title?: string;
  description?: string;
  section?: string;
  status?: 'open' | 'done' | 'wontfix';
}

interface ReviewDetail {
  meta: ReviewMeta;
  state: {
    reviewers?: Record<
      string,
      {
        id: string;
        persona: string;
        text: string;
        score?: string;
        decision?: string;
      }
    >;
    meta?: {
      text: string;
      decision?: string;
    } | null;
    issues?: ReviewIssue[];
    fixes?: Record<
      string,
      {
        original?: string;
        revised?: string;
        note?: string;
        status?: 'proposed' | 'accepted' | 'dismissed';
      }
    >;
    guide?: { text: string } | null;
    response?: { text: string } | null;
  };
}

export const ReviewView: React.FC = () => {
  const queryClient = useQueryClient();
  const { setMainView } = useUIStore();
  const { t } = useI18n();
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [streamingStage, setStreamingStage] = useState<string | null>(null);
  const [streamBuffer, setStreamBuffer] = useState('');

  const getPersonaLabel = (revId: string, persona?: string): string => {
    if (!persona) return revId;
    if (persona.includes('Domain expert')) {
      return `${revId} · ${t('Chuyên gia Lĩnh vực - Tính mới & Đóng góp', 'Domain expert - Novelty & Significance')}`;
    }
    if (persona.includes('Methodology') || persona.includes('demanding')) {
      return `${revId} · ${t('Chuyên gia Phương pháp & Thực nghiệm', 'Methodology & Experiments Expert')}`;
    }
    if (persona.includes('Clarity') || persona.includes('presentation')) {
      return `${revId} · ${t('Tính rõ ràng, Trình bày & Chuẩn hội nghị', 'Clarity, Presentation & Venue-fit')}`;
    }
    if (persona.includes('Comprehensive')) {
      return `${revId} · ${t('Phản biện Toàn diện', 'Comprehensive Reviewer')}`;
    }
    return `${revId} · ${persona}`;
  };

  // List reviews
  const { data: listData } = useQuery<{ reviews: ReviewMeta[]; active?: string }>({
    queryKey: ['reviews'],
    queryFn: () => api.get('/api/review'),
  });

  const activeId = selectedReviewId || listData?.active || listData?.reviews?.[0]?.id || null;

  // Fetch active review details
  const { data: reviewDetail, refetch: refetchDetail } = useQuery<ReviewDetail>({
    queryKey: ['review', activeId],
    queryFn: () => api.get<ReviewDetail>(`/api/review/${activeId}`),
    enabled: !!activeId,
  });

  const handleUploadManuscript = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post<{ meta: ReviewMeta }>('/api/review/upload', form);
      queryClient.invalidateQueries({ queryKey: ['reviews'] });
      if (res?.meta?.id) setSelectedReviewId(res.meta.id);
    } catch (err) {
      alert(`Lỗi tải bản thảo: ${(err as Error).message}`);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleAttachLatexSource = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeId) return;
    try {
      const form = new FormData();
      form.append('file', file);
      await api.post(`/api/review/${activeId}/source`, form);
      refetchDetail();
      alert('Đã đính kèm tệp nguồn LaTeX (.tex) để áp dụng bản vá tự động!');
    } catch (err) {
      alert(`Lỗi đính kèm .tex: ${(err as Error).message}`);
    } finally {
      e.target.value = '';
    }
  };

  // Run SSE stage (reviewer 1..3, meta, issues, guide, response)
  const runStageStream = async (stage: string, extraBody: Record<string, unknown> = {}) => {
    if (!activeId) return;
    setStreamingStage(`${stage}${extraBody.idx ? ` R${extraBody.idx}` : ''}`);
    setStreamBuffer('');

    try {
      const res = await fetch(`/api/review/${activeId}/stage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage, ...extraBody }),
      });

      if (!res.ok || !res.body) {
        const errText = await res.text();
        throw new Error(errText || `HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const payload = JSON.parse(line.slice(5).trim());
              if (payload.delta) {
                setStreamBuffer((prev) => prev + payload.delta);
              }
            } catch {
              // ignore non-json
            }
          }
        }
      }
      refetchDetail();
    } catch (err) {
      alert(`Lỗi chạy giai đoạn ${stage}: ${(err as Error).message}`);
    } finally {
      setStreamingStage(null);
      setStreamBuffer('');
    }
  };

  const handleProposeFix = async (issueId: string) => {
    if (!activeId) return;
    setStreamingStage(`fix ${issueId}`);
    setStreamBuffer('');
    try {
      const res = await fetch(`/api/review/${activeId}/fix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issue_id: issueId }),
      });
      if (res.body) {
        const reader = res.body.getReader();
        while (true) {
          const { done } = await reader.read();
          if (done) break;
        }
      }
      refetchDetail();
    } catch (err) {
      alert(`Lỗi sinh bản sửa: ${(err as Error).message}`);
    } finally {
      setStreamingStage(null);
      setStreamBuffer('');
    }
  };

  const handleIssueDecision = async (
    issueId: string,
    status?: 'open' | 'done' | 'wontfix',
    fixStatus?: 'accepted' | 'dismissed'
  ) => {
    if (!activeId) return;
    await api.put(`/api/review/${activeId}/issue/${issueId}`, {
      status,
      fix_status: fixStatus,
    });
    refetchDetail();
  };

  const handleApplyFixesToLatex = async () => {
    if (!activeId) return;
    try {
      await api.post(`/api/review/${activeId}/apply`, {});
      alert('Đã áp dụng tất cả bản vá vào tệp source_revised.tex!');
    } catch (err) {
      alert(`Lỗi áp dụng LaTeX: ${(err as Error).message}`);
    }
  };

  const handleDeleteReview = async (rid: string) => {
    if (!confirm('Xóa phiên bình duyệt này?')) return;
    await api.delete(`/api/review/${rid}`);
    if (selectedReviewId === rid) setSelectedReviewId(null);
    queryClient.invalidateQueries({ queryKey: ['reviews'] });
  };

  const reviewers = reviewDetail?.state?.reviewers || {};
  const issues = reviewDetail?.state?.issues || [];
  const fixes = reviewDetail?.state?.fixes || {};

  return (
    <div
      style={{
        padding: '24px 28px',
        height: '100%',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
        background: 'var(--bg)',
      }}
    >
      {/* Top Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
          paddingBottom: 14,
          borderBottom: '1px solid var(--line)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Award size={22} color="var(--accent)" />
            <h2 style={{ margin: 0, fontSize: 20 }}>
              {t('Hội đồng Bình duyệt Học thuật (R1–R3 & Trưởng ban)', 'Academic Peer Review Studio (R1–R3 & Area Chair)')}
            </h2>
          </div>
          <p className="muted" style={{ margin: '4px 0 0', fontSize: 13 }}>
            {t(
              'Tải bản thảo PDF/DOCX/LaTeX → Chạy 3 Phản biện độc lập → Tổng hợp Đánh giá chung → Trích xuất Vấn đề & Tự động sửa LaTeX.',
              'Upload manuscript PDF/DOCX/LaTeX → Run 3 Independent Reviews → Synthesize Meta-Review → Extract Issues & Auto-patch LaTeX.'
            )}
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <label className="btn sm accent" style={{ cursor: 'pointer', margin: 0 }}>
            <Upload size={14} style={{ marginRight: 5 }} />
            <span>{uploading ? t('Đang tải…', 'Uploading…') : t('Tải Bản thảo mới dạng tệp PDF, TEX hoặc DOCX', 'Upload Manuscript (PDF/TEX/DOCX)')}</span>
            <input
              type="file"
              accept=".pdf,.tex,.docx,.md,.txt"
              onChange={handleUploadManuscript}
              style={{ display: 'none' }}
              disabled={uploading}
            />
          </label>
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => setMainView('chat')}
          >
            <MessageSquare size={14} style={{ marginRight: 5 }} />
            <span>{t('Quay lại Hội thoại', 'Back to Chat')}</span>
          </button>
        </div>
      </div>

      {/* Review Session Selector */}
      {listData?.reviews && listData.reviews.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {listData.reviews.map((r) => (
            <div
              key={r.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderRadius: 8,
                border: `1px solid ${activeId === r.id ? 'var(--accent)' : 'var(--line)'}`,
                background: activeId === r.id ? 'var(--accent-soft)' : 'var(--panel)',
                cursor: 'pointer',
              }}
              onClick={() => setSelectedReviewId(r.id)}
            >
              <b style={{ fontSize: 12.5 }}>{r.title || r.file || r.id}</b>
              <button
                type="button"
                className="icon sm"
                onClick={(ev) => {
                  ev.stopPropagation();
                  handleDeleteReview(r.id);
                }}
                style={{ width: 18, height: 18 }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {!activeId ? (
        <div
          style={{
            padding: 40,
            textAlign: 'center',
            background: 'var(--panel)',
            borderRadius: 14,
            border: '1px dashed var(--line-2)',
          }}
        >
          <Award size={36} color="var(--accent)" style={{ marginBottom: 10 }} />
          <h3 style={{ margin: '0 0 6px' }}>{t('Chưa có bản thảo nào đang bình duyệt', 'No manuscript currently under review')}</h3>
          <p className="muted" style={{ margin: 0, fontSize: 13.5 }}>
            {t(
              'Nhấn nút "Tải Bản thảo mới" ở góc trên bên phải để bắt đầu quy trình phản biện R1–R3 chuẩn hội nghị A* và tạp chí Q1.',
              'Click "Upload Manuscript (PDF/TEX/DOCX)" at top right to start R1–R3 review calibrated for A* conferences and Q1 journals.'
            )}
          </p>
        </div>
      ) : (
        <>
          {/* Pipeline Control Bar */}
          <div
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              padding: 14,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 10,
            }}
          >
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn sm accent"
                disabled={!!streamingStage}
                onClick={() => runStageStream('reviewer', { idx: 1 })}
              >
                <Play size={13} style={{ marginRight: 4 }} /> {t('Chạy Phản biện #1', 'Run Reviewer #1')}
              </button>
              <button
                type="button"
                className="btn sm accent"
                disabled={!!streamingStage}
                onClick={() => runStageStream('reviewer', { idx: 2 })}
              >
                <Play size={13} style={{ marginRight: 4 }} /> {t('Chạy Phản biện #2', 'Run Reviewer #2')}
              </button>
              <button
                type="button"
                className="btn sm accent"
                disabled={!!streamingStage}
                onClick={() => runStageStream('reviewer', { idx: 3 })}
              >
                <Play size={13} style={{ marginRight: 4 }} /> {t('Chạy Phản biện #3', 'Run Reviewer #3')}
              </button>
              <button
                type="button"
                className="btn sm ghost"
                disabled={!!streamingStage}
                onClick={() => runStageStream('meta')}
              >
                {t('Tổng hợp Đánh giá chung', 'Synthesize Meta-Review')}
              </button>
              <button
                type="button"
                className="btn sm ghost"
                disabled={!!streamingStage}
                onClick={() => runStageStream('issues')}
              >
                {t('Trích xuất Danh sách Vấn đề', 'Extract Issue Checklist')}
              </button>
              <button
                type="button"
                className="btn sm ghost"
                disabled={!!streamingStage}
                onClick={() => runStageStream('response')}
              >
                {t('Tạo Thư Phản hồi', 'Generate Rebuttal Letter')}
              </button>
            </div>

            <div style={{ display: 'flex', gap: 6 }}>
              <label className="btn sm ghost" style={{ cursor: 'pointer', margin: 0 }}>
                <FileCode size={13} style={{ marginRight: 4 }} />
                <span>{t('Đính kèm tệp .tex gốc', 'Attach Source .tex')}</span>
                <input
                  type="file"
                  accept=".tex"
                  onChange={handleAttachLatexSource}
                  style={{ display: 'none' }}
                />
              </label>
              <button
                type="button"
                className="btn sm ghost"
                onClick={handleApplyFixesToLatex}
              >
                {t('Áp dụng vá .tex', 'Apply Patches to .tex')}
              </button>
              <a
                className="btn sm ghost"
                href={`/api/review/${activeId}/download/report`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: 'none' }}
              >
                <Download size={13} style={{ marginRight: 4 }} /> {t('Tải Báo cáo', 'Download Report')}
              </a>
            </div>
          </div>

          {/* Live Streaming Output Banner */}
          {streamingStage && (
            <div
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--accent)',
                borderRadius: 12,
                padding: 16,
              }}
            >
              <div style={{ fontWeight: 600, color: 'var(--accent)', marginBottom: 6 }}>
                {t('Đang chạy giai đoạn:', 'Running stage:')} {streamingStage}…
              </div>
              <pre
                style={{
                  fontSize: 12.5,
                  whiteSpace: 'pre-wrap',
                  maxHeight: 240,
                  overflowY: 'auto',
                  margin: 0,
                }}
              >
                {streamBuffer || t('Đang khởi tạo hội đồng phản biện…', 'Initializing peer review panel…')}
              </pre>
            </div>
          )}

          {/* Reviewer Cards R1 - R3 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: 14,
            }}
          >
            {Object.values(reviewers).map((rev) => (
              <div
                key={rev.id}
                style={{
                  background: 'var(--panel)',
                  border: '1px solid var(--line)',
                  borderRadius: 12,
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <b>
                    {getPersonaLabel(rev.id, rev.persona)}
                  </b>
                  {rev.score && <span className="chip ok">{rev.score}</span>}
                </div>
                <div
                  style={{
                    fontSize: 12.5,
                    lineHeight: 1.55,
                    maxHeight: 380,
                    overflowY: 'auto',
                  }}
                >
                  <MarkdownRenderer content={rev.text || ''} />
                </div>
              </div>
            ))}
          </div>

          {/* Area Chair Meta-Review */}
          {reviewDetail?.state?.meta && (
            <div
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--accent)',
                borderRadius: 12,
                padding: 16,
              }}
            >
              <h4 style={{ margin: '0 0 8px' }}>
                {t('Tổng hợp của Trưởng ban Chuyên môn', 'Area Chair Meta-Review & Synthesis')}
              </h4>
              <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                <MarkdownRenderer content={reviewDetail.state.meta.text || ''} />
              </div>
            </div>
          )}

          {/* Extracted Issues & Quick Fixes */}
          {issues.length > 0 && (
            <div
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--line)',
                borderRadius: 12,
                padding: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <h4 style={{ margin: 0 }}>
                {t('Danh sách Vấn đề Cần Chỉnh sửa', 'Manuscript Revision Checklist')} ({issues.length} {t('vấn đề', 'issues')})
              </h4>
              {issues.map((iss) => {
                const fix = fixes[iss.id];
                return (
                  <div
                    key={iss.id}
                    style={{
                      padding: 12,
                      borderRadius: 10,
                      border: '1px solid var(--line)',
                      background: 'var(--bg)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <AlertTriangle size={15} color="var(--warn)" />
                        <b style={{ fontSize: 13 }}>
                          [{iss.severity || 'Major'}] {iss.title || iss.id}
                        </b>
                      </div>
                      <span className="chip" style={{ fontSize: 11 }}>
                        {iss.status || 'open'}
                      </span>
                    </div>
                    <div style={{ fontSize: 12.5 }}>{iss.description}</div>

                    {fix ? (
                      <div
                        style={{
                          padding: 10,
                          borderRadius: 8,
                          background: 'var(--panel)',
                          border: '1px solid var(--line-2)',
                          fontSize: 12,
                        }}
                      >
                        <div>
                          <b>{t('Đoạn văn đề xuất sửa', 'Proposed patch')} ({fix.status}):</b>
                        </div>
                        <pre style={{ whiteSpace: 'pre-wrap', margin: '6px 0' }}>
                          {fix.revised}
                        </pre>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            type="button"
                            className="btn sm accent"
                            onClick={() => handleIssueDecision(iss.id, 'done', 'accepted')}
                          >
                            <Check size={12} style={{ marginRight: 4 }} /> {t('Chấp nhận bản sửa', 'Accept patch')}
                          </button>
                          <button
                            type="button"
                            className="btn sm ghost"
                            onClick={() => handleIssueDecision(iss.id, 'open', 'dismissed')}
                          >
                            <X size={12} style={{ marginRight: 4 }} /> {t('Từ chối', 'Dismiss')}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          type="button"
                          className="btn sm ghost"
                          onClick={() => handleProposeFix(iss.id)}
                          disabled={!!streamingStage}
                        >
                          <Sparkles size={13} style={{ marginRight: 4 }} /> {t('Đề xuất chỉnh sửa tự động', 'Auto Propose AI Fix')}
                        </button>
                        <button
                          type="button"
                          className="btn sm ghost"
                          onClick={() => handleIssueDecision(iss.id, 'done')}
                        >
                          {t('Đánh dấu Đã xong', 'Mark Done')}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
};
