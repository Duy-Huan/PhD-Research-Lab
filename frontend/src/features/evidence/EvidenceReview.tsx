import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useI18n, useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { Claim } from '../../shared/api/types';
import { FileText, Plus, ShieldCheck, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';

export const EvidenceReview: React.FC = () => {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const { activeTopicId } = useUIStore();
  const [showCreate, setShowCreate] = useState(false);
  const [claimText, setClaimText] = useState('');
  const [kind, setKind] = useState<'empirical_finding' | 'source_claim' | 'hypothesis'>('empirical_finding');
  const [sourceId, setSourceId] = useState('');
  const [decisionNote, setDecisionNote] = useState('');

  const { data: claimsData, isLoading } = useQuery<{ claims: Claim[] }>({
    queryKey: ['claims', activeTopicId],
    queryFn: () => api.get<{ claims: Claim[] }>(`/api/research/topics/${activeTopicId}/claims`),
    enabled: !!activeTopicId,
  });

  const claims = claimsData?.claims || [];

  const createMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/research/topics/${activeTopicId}/claims`, {
        text: claimText.trim(),
        kind,
        evidence: sourceId.trim()
          ? [{ source_type: 'paper', source_id: sourceId.trim(), excerpt: claimText.trim().slice(0, 120) }]
          : [],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['claims', activeTopicId] });
      setShowCreate(false);
      setClaimText('');
      setSourceId('');
    },
    onError: (err: Error) => {
      alert(`Lỗi tạo Claim: ${err.message}`);
    },
  });

  const evaluateMutation = useMutation({
    mutationFn: (cid: string) =>
      api.post(`/api/research/topics/${activeTopicId}/claims/${cid}/evaluate`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['claims', activeTopicId] });
    },
  });

  const decisionMutation = useMutation({
    mutationFn: ({ cid, decision }: { cid: string; decision: 'accept' | 'reject' | 'contest' }) =>
      api.post(`/api/research/topics/${activeTopicId}/claims/${cid}/decision`, {
        decision,
        note: decisionNote || `Researcher decision (${decision}) via React UI`,
      }),
    onSuccess: () => {
      setDecisionNote('');
      queryClient.invalidateQueries({ queryKey: ['claims', activeTopicId] });
    },
    onError: (err: Error) => {
      alert(`Không thể cập nhật quyết định: ${err.message}`);
    },
  });

  if (!activeTopicId) {
    return (
      <div style={{ padding: 16 }}>
        <p className="muted">{t('Vui lòng chọn một Topic để xem và kiểm định bằng chứng khoa học.', 'Select a topic to review and verify its scientific evidence.')}</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <ShieldCheck size={18} color="var(--accent)" />
          <span>{t('Bằng chứng & kiểm định', 'Claims & evidence')}</span>
        </h4>
        <button className="btn sm accent" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={14} style={{ marginRight: 4 }} /> {t('Đề xuất claim', 'Propose a claim')}
        </button>
      </div>

      <p className="muted" style={{ fontSize: 13, margin: 0 }}>
        {t('Khẳng định nguồn (Source claim) ≠ Đo lường (Measurement) ≠ Quyết định nhân lực. Mỗi claim phải được kiểm chứng cơ học và xác nhận bởi nhà nghiên cứu.', 'A source claim is not a measurement, and neither is a human decision. Every claim is checked mechanically and confirmed by the researcher.')}
      </p>

      {showCreate && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (claimText.trim()) createMutation.mutate();
          }}
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--line-2)',
            borderRadius: 8,
            padding: 12,
            display: 'grid',
            gap: 8,
          }}
        >
          <b>Nội dung khẳng định khoa học:</b>
          <div style={{ display: 'flex', gap: 8 }}>
            <select className="input sm" value={kind} onChange={(e) => setKind(e.target.value as any)}>
              <option value="empirical_finding">empirical_finding (Kết quả thực nghiệm)</option>
              <option value="source_claim">source_claim (Khẳng định từ bài báo)</option>
              <option value="hypothesis">hypothesis (Giả thuyết nghiên cứu)</option>
            </select>
            <input
              className="input sm"
              style={{ flex: 1 }}
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              placeholder="ID Nguồn bằng chứng (Paper ID / Run ID - tuỳ chọn)…"
            />
          </div>
          <textarea
            className="input"
            value={claimText}
            onChange={(e) => setClaimText(e.target.value)}
            placeholder="vd: Kiến trúc thu gọn Wavelet cải thiện PSNR thêm 1.8 dB trên tập kiểm thử…"
            rows={3}
            required
          />
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
            <button className="btn sm ghost" type="button" onClick={() => setShowCreate(false)}>
              Huỷ
            </button>
            <button className="btn sm accent" type="submit" disabled={createMutation.isPending}>
              Gửi đề xuất
            </button>
          </div>
        </form>
      )}

      {/* Claims List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {isLoading && <p className="muted">Đang tải danh sách claims…</p>}
        {claims.map((claim) => (
          <article
            key={claim.id}
            style={{
              padding: '12px 14px',
              borderRadius: 8,
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="chip" style={{ fontSize: 11 }}>
                Loại: {claim.payload?.kind || (claim.payload as any)?.spec?.kind || (claim as any).kind || 'empirical_finding'}
              </span>
              <span
                className={`chip ${
                  claim.status === 'accepted' || claim.status === 'supported' || claim.status === 'checked'
                    ? 'ok'
                    : claim.status === 'rejected' || claim.status === 'contested'
                    ? 'err'
                    : 'warn'
                }`}
                style={{ fontSize: 11 }}
              >
                {claim.status.toUpperCase()}
              </span>
            </div>

            <div style={{ fontSize: 13.5, lineHeight: 1.5, fontWeight: 500 }}>
              {claim.payload?.text || (claim.payload as any)?.spec?.text || (claim as any).text || claim.id}
            </div>

            {/* Evidence items */}
            {claim.evidence && Array.isArray(claim.evidence) && claim.evidence.length > 0 && (
              <div style={{ borderTop: '1px solid var(--line-2)', paddingTop: 6, fontSize: 12 }}>
                <span className="muted">Bằng chứng liên kết:</span>
                {claim.evidence.map((ev, i) => (
                  <div key={i} style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <FileText size={13} color="var(--accent)" />
                    <span>Nguồn: {ev.payload?.source_id || (ev as any).source_id || 'N/A'}</span>
                    {ev.payload?.provenance?.page && (
                      <span className="muted">(Trang {ev.payload.provenance.page})</span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Mechanical Evaluation & Human Governance */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', borderTop: '1px solid var(--line-2)', paddingTop: 8 }}>
              <button
                className="btn sm ghost"
                onClick={() => evaluateMutation.mutate(claim.id)}
                disabled={evaluateMutation.isPending}
              >
                <RefreshCw size={12} style={{ marginRight: 4 }} /> Kiểm chứng cơ học
              </button>
              <button
                className="btn sm ghost"
                onClick={() => decisionMutation.mutate({ cid: claim.id, decision: 'accept' })}
                disabled={decisionMutation.isPending}
              >
                <CheckCircle2 size={12} style={{ marginRight: 4 }} /> Xác nhận (Accept)
              </button>
              <button
                className="btn sm ghost"
                onClick={() => decisionMutation.mutate({ cid: claim.id, decision: 'reject' })}
                disabled={decisionMutation.isPending}
              >
                <XCircle size={12} style={{ marginRight: 4 }} /> Bác bỏ (Reject)
              </button>
            </div>
          </article>
        ))}

        {claims.length === 0 && !isLoading && !showCreate && (
          <p className="muted" style={{ fontSize: 13 }}>
            {t('Chưa có Claim nào được đề xuất trong Topic này.', 'No claims proposed in this topic yet.')}
          </p>
        )}
      </div>
    </div>
  );
};
