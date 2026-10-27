import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import {
  FileText,
  Play,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Eye,
  Sliders,
  ShieldCheck,
  Award,
  Layers,
  ChevronRight,
  GitBranch,
  Search,
  Check,
  X,
  FileCheck,
  Users,
} from 'lucide-react';

interface WritingArtifact {
  artifact_id: string;
  task_id: string;
  parent_workflow_id: string;
  section_id: string;
  title: string;
  version: number;
  content_hash: string;
  execution_status: string;
  review_status: string;
  execution_metrics: Record<string, any>;
  storage_path: string;
  created_at: string;
  content: string;
}

interface EngineHealth {
  engine: string;
  ready: boolean;
  state: string;
  backend_mode: string;
  detail: string;
  cli: { installed: boolean; version: string; binary: string | null };
  latex_available: boolean;
  latex_engines: string[];
}

interface QualityGatesReport {
  citations: {
    total_citations: number;
    valid_count: number;
    missing_count: number;
    passed: boolean;
    items: Array<{ key: string; status: string; matched_title?: string; detail?: string }>;
  };
  provenance: {
    total_claims: number;
    verified_claims: number;
    unverified_claims: number;
    passed: boolean;
  };
  figures: {
    total_figures: number;
    valid_figures: number;
    passed: boolean;
  };
  consistency: {
    passed: boolean;
    limitations_explicitly_stated: boolean;
    inconsistencies: string[];
  };
  review: {
    overall_score: number;
    recommendation: string;
    scores: Array<{ criterion: string; score: number; comment: string }>;
    strengths: string[];
    weaknesses: string[];
  };
  overall_readiness: boolean;
}

export const PaperOrchestraStudio: React.FC = () => {
  const { activeTopicId } = useUIStore();
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const [level, setLevel] = useState<'L2' | 'L3' | 'L4'>('L3');
  const [backendMode, setBackendMode] = useState<'auto' | 'cli' | 'harness_skills'>('auto');
  const [selectedSection, setSelectedSection] = useState('abstract');
  const [objective, setObjective] = useState('');
  const [venue, setVenue] = useState('IEEE / ACM');
  const [approvalNote, setApprovalNote] = useState('');
  const [diffVersionA, setDiffVersionA] = useState<number>(1);
  const [diffVersionB, setDiffVersionB] = useState<number>(1);

  // 1. Fetch PaperOrchestra Engine Health
  const { data: health, isLoading: isHealthLoading, refetch: refetchHealth } = useQuery<EngineHealth>({
    queryKey: ['paperorchestra-health'],
    queryFn: () => api.get('/api/paperorchestra/health'),
  });

  // 2. Fetch Versioned Writing Artifacts for the active topic
  const { data: artifactsData, refetch: refetchArtifacts } = useQuery<{ artifacts: WritingArtifact[] }>({
    queryKey: ['paperorchestra-artifacts', activeTopicId],
    queryFn: () => api.get(`/api/paperorchestra/artifacts/${activeTopicId || 'global'}`),
    enabled: true,
  });

  const artifacts = artifactsData?.artifacts || [];

  // 3. Quality Gates Mutation
  const qualityGatesMutation = useMutation({
    mutationFn: () =>
      api.post<QualityGatesReport>('/api/paperorchestra/quality-gates', {
        topic_id: activeTopicId || '',
        sections: {},
      }),
  });

  // 4. Plan & Launch Writing Mission
  const planMissionMutation = useMutation({
    mutationFn: async () => {
      const topicId = activeTopicId;
      if (!topicId) throw new Error(t('Chọn chủ đề trước khi tạo nhiệm vụ.', 'Select a topic before creating a writing mission.'));
      const res = await api.post<{ spec: any }>('/api/paperorchestra/plan-mission', {
        topic_id: topicId,
        level,
        objective: objective.trim() || t('Soạn thảo bản thảo bài báo hoàn chỉnh', 'Synthesize complete research paper manuscript'),
        section: selectedSection,
        target_venue: venue,
      });
      if (!res.spec) throw new Error(t('Không nhận được kế hoạch nhiệm vụ.', 'No mission specification was returned.'));
      await api.post(`/api/research/topics/${topicId}/missions`, res.spec);
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paperorchestra-artifacts'] });
      queryClient.invalidateQueries({ queryKey: ['missions'] });
      alert(t('Đã khởi tạo quy trình PaperOrchestra!', 'PaperOrchestra workflow initiated!'));
    },
    onError: (err: Error) => {
      alert(`Error: ${err.message}`);
    },
  });

  const sectionTabs = [
    { id: 'abstract', label: 'Abstract' },
    { id: 'introduction', label: 'Introduction' },
    { id: 'related_work', label: 'Related Work' },
    { id: 'methodology', label: 'Methodology' },
    { id: 'experiments', label: 'Experiments' },
    { id: 'discussion', label: 'Discussion' },
    { id: 'conclusion', label: 'Conclusion' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Engine Status Banner */}
      <div
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                fontWeight: 600,
                color: health?.ready ? 'var(--accent)' : 'var(--amber, #f59e0b)',
                fontSize: 13,
              }}
            >
              <CheckCircle2 size={15} />
              <span>PaperOrchestra v6.4.3</span>
            </span>
            <span className="chip" style={{ fontSize: 11 }}>
              {health?.cli?.installed ? t('Official CLI Sẵn sàng', 'Official CLI Ready') : t('Harness Skills Fallback', 'Harness Skills Fallback')}
            </span>
          </div>

          <button
            type="button"
            className="btn xs ghost"
            onClick={() => refetchHealth()}
            title={t('Làm mới trạng thái', 'Refresh status')}
          >
            <RefreshCw size={12} className={isHealthLoading ? 'spin' : ''} />
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6, fontSize: 11.5 }}>
          <p style={{ margin: 0, color: 'var(--muted)' }}>
            {health?.detail || t('Đang kiểm tra môi trường PaperOrchestra…', 'Probing PaperOrchestra environment…')}
          </p>
          <span style={{ color: 'var(--muted)', fontSize: 11, background: 'var(--bg-2)', padding: '2px 8px', borderRadius: 4, border: '1px solid var(--line)' }}>
            {t('The AI Scientist v2: Plugin tùy chọn (quản lý trong Cài đặt → Kỹ năng & Plugins)', 'The AI Scientist v2: Optional plugin (manage in Settings → Skills & Plugins)')}
          </span>
        </div>

        {/* Backend & Level Selector */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 4 }}>
          {/* Autonomy Level */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>
              {t('Cấp độ:', 'Level:')}
            </span>
            <div style={{ display: 'inline-flex', background: 'var(--bg)', borderRadius: 6, padding: 2, border: '1px solid var(--line)' }}>
              {(['L2', 'L3', 'L4'] as const).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  className={`btn xs ${level === lvl ? 'accent' : 'ghost'}`}
                  onClick={() => setLevel(lvl)}
                  style={{ borderRadius: 4, padding: '3px 8px' }}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </div>

          {/* Execution Backend */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>
              {t('Backend:', 'Backend:')}
            </span>
            <select
              className="input sm"
              style={{ padding: '3px 8px', fontSize: 12 }}
              value={backendMode}
              onChange={(e) => setBackendMode(e.target.value as any)}
            >
              <option value="auto">{t('Tự động (Auto Detect)', 'Auto Detect')}</option>
              <option value="cli">{t('Official PaperOrchestra CLI', 'Official PaperOrchestra CLI')}</option>
              <option value="harness_skills">{t('Harness Specialist Multi-Agent', 'Harness Specialist Multi-Agent')}</option>
            </select>
          </div>
        </div>
      </div>

      {/* Progress & Section Status Tracker */}
      <div
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Layers size={14} color="var(--accent)" />
          <span>{t('Tiến trình Soạn thảo Từng mục', 'Section Manuscript Progress')}</span>
        </span>

        <div style={{ display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 4 }}>
          {sectionTabs.map((tab) => {
            const hasDraft = artifacts.some((a) => a.section_id === tab.id);
            const isSelected = selectedSection === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                className={`btn sm ${isSelected ? 'accent' : 'ghost'}`}
                onClick={() => setSelectedSection(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  fontSize: 11.5,
                  whiteSpace: 'nowrap',
                  borderRadius: 6,
                }}
              >
                {hasDraft ? <CheckCircle2 size={12} color="var(--accent)" /> : <FileText size={12} />}
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Objective & Launch Input */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
          <textarea
            className="input"
            rows={2}
            style={{ fontSize: 12 }}
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder={t(
              'Nhập mục tiêu nghiên cứu hoặc yêu cầu văn phong (vd: Khảo sát mô hình tự chú ý cho thị giác máy tính)…',
              'Enter research objective or style guidelines (e.g. Investigate self-attention mechanisms for vision)...'
            )}
          />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>{t('Target Venue:', 'Target Venue:')}</span>
              <input
                className="input sm"
                style={{ width: 140, fontSize: 12, padding: '3px 8px' }}
                value={venue}
                onChange={(e) => setVenue(e.target.value)}
              />
            </div>

            <button
              type="button"
              className="btn sm accent"
              onClick={() => planMissionMutation.mutate()}
              disabled={planMissionMutation.isPending || !activeTopicId}
              title={!activeTopicId ? t('Chọn chủ đề trước khi tạo nhiệm vụ.', 'Select a topic before creating a writing mission.') : undefined}
              style={{ display: 'flex', alignItems: 'center', gap: 5 }}
            >
              <Play size={13} />
              <span>{t(`Khởi chạy ${level} Writing Task`, `Launch ${level} Writing Task`)}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Quality Gates & Evidence Inspection */}
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <ShieldCheck size={14} color="var(--accent)" />
            <span>{t('Cổng Kiểm định Khoa học (§5 Quality Gates)', 'Scientific Quality Gates (§5)')}</span>
          </span>

          <button
            type="button"
            className="btn sm ghost"
            onClick={() => qualityGatesMutation.mutate()}
            disabled={qualityGatesMutation.isPending}
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <RefreshCw size={12} className={qualityGatesMutation.isPending ? 'spin' : ''} />
            <span>{t('Đánh giá Chất lượng', 'Run Quality Checks')}</span>
          </button>
        </div>

        {qualityGatesMutation.data && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8, fontSize: 11.5 }}>
            {/* Citations Card */}
            <div style={{ padding: 8, borderRadius: 6, background: 'var(--bg)', border: '1px solid var(--line)' }}>
              <b>{t('Trích dẫn (Citations)', 'Citations')}</b>
              <div style={{ color: qualityGatesMutation.data.citations.passed ? 'var(--accent)' : 'var(--amber, #f59e0b)', marginTop: 4 }}>
                {qualityGatesMutation.data.citations.valid_count} / {qualityGatesMutation.data.citations.total_citations} {t('hợp lệ', 'valid')}
              </div>
            </div>

            {/* Figures Card */}
            <div style={{ padding: 8, borderRadius: 6, background: 'var(--bg)', border: '1px solid var(--line)' }}>
              <b>{t('Đồ họa (Figures)', 'Figures')}</b>
              <div style={{ color: qualityGatesMutation.data.figures.passed ? 'var(--accent)' : 'var(--amber, #f59e0b)', marginTop: 4 }}>
                {qualityGatesMutation.data.figures.valid_figures} / {qualityGatesMutation.data.figures.total_figures} {t('xác thực', 'verified')}
              </div>
            </div>

            {/* Provenance Card */}
            <div style={{ padding: 8, borderRadius: 6, background: 'var(--bg)', border: '1px solid var(--line)' }}>
              <b>{t('Provenance Số liệu', 'Provenance')}</b>
              <div style={{ color: qualityGatesMutation.data.provenance.passed ? 'var(--accent)' : 'var(--amber, #f59e0b)', marginTop: 4 }}>
                {qualityGatesMutation.data.provenance.verified_claims} / {qualityGatesMutation.data.provenance.total_claims} {t('đo lường', 'measured')}
              </div>
            </div>

            {/* Peer Review Score */}
            <div style={{ padding: 8, borderRadius: 6, background: 'var(--bg)', border: '1px solid var(--line)' }}>
              <b>{t('Peer Review Score', 'Review Score')}</b>
              <div style={{ color: 'var(--accent)', marginTop: 4, fontWeight: 700 }}>
                {qualityGatesMutation.data.review.overall_score} / 10 ({qualityGatesMutation.data.review.recommendation})
              </div>
            </div>
          </div>
        )}

        {/* Human Sign-Off / Approval Action before Submission */}
        <div style={{ borderTop: '1px solid var(--line)', paddingTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600 }}>{t('Ký duyệt Xuất bản của Tác giả', 'Author Submission Approval')}</span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              className="input sm"
              style={{ flex: 1, fontSize: 12 }}
              value={approvalNote}
              onChange={(e) => setApprovalNote(e.target.value)}
              placeholder={t('Ghi chú xác nhận tính trung thực và duyệt nộp bài báo…', 'Approval note confirming integrity prior to submission…')}
            />
            <button
              type="button"
              className="btn sm ghost"
              disabled
              title={t('Chưa có cơ chế lưu ký duyệt tại đây. Kiểm tra bằng chứng trong Review Room.', 'Submission sign-off is unavailable here. Review evidence in Review Room.')}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <FileCheck size={13} />
              <span>{t('Ký duyệt', 'Sign-Off')}</span>
            </button>
          </div>
          <span className="muted" style={{ fontSize: 11 }}>
            {t('Ghi chú ở trên là bản nháp cục bộ; ký duyệt chưa được hỗ trợ tại bảng này.', 'The note above is a local draft; this panel does not support submission approval.')}
          </span>
        </div>
      </div>

      {/* Version Comparison & Artifact History */}
      <div
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <GitBranch size={14} color="var(--accent)" />
          <span>{t('Lịch sử Phiên bản & Artifact Traceability', 'Artifact History & Traceability')}</span>
        </span>

        {artifacts.length === 0 ? (
          <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>
            {t('(Chưa có artifact nào được lưu trữ cho chủ đề này)', '(No artifacts recorded yet)')}
          </span>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
            {artifacts.map((art) => (
              <div
                key={art.artifact_id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '6px 8px',
                  background: 'var(--bg)',
                  borderRadius: 6,
                  fontSize: 11.5,
                  border: '1px solid var(--line)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <b>{art.section_id}</b>
                  <span className="muted">v{art.version}</span>
                  <span className="muted" style={{ fontFamily: 'var(--mono)', fontSize: 10 }}>
                    {art.content_hash.slice(0, 10)}…
                  </span>
                </div>
                <span className="chip" style={{ fontSize: 10 }}>
                  {art.review_status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

