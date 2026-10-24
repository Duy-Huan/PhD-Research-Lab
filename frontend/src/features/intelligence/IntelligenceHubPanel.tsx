import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { Mission, URAPArtifact } from '../../shared/api/types';
import {
  Cpu,
  GitMerge,
  ShieldCheck,
  Activity,
  PackageCheck,
  FileSpreadsheet,
  Download,
  Play,
  Route,
} from 'lucide-react';

export const IntelligenceHubPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { activeTopicId } = useUIStore();
  const [tab, setTab] = useState<'urap' | 'trace' | 'context' | 'repro'>('urap');
  const [selectedMissionId, setSelectedMissionId] = useState<string>('');
  const [selectedArtifactId, setSelectedArtifactId] = useState<string>('');

  // Context Pack & Router state
  const [role, setRole] = useState<'literature_reviewer' | 'experiment_engineer' | 'verification_auditor' | 'synthesis_author'>('literature_reviewer');
  const [maxTokens, setMaxTokens] = useState(3500);
  const [contextPackResult, setContextPackResult] = useState<any>(null);
  const [capability, setCapability] = useState('paper.discover');
  const [simulateQuota, setSimulateQuota] = useState(false);
  const [routeResult, setRouteResult] = useState<any>(null);

  // Repro & Report state
  const [reproResult, setReproResult] = useState<any>(null);
  const [replayResult, setReplayResult] = useState<any>(null);
  const [reportResult, setReportResult] = useState<any>(null);
  const [integrityResult, setIntegrityResult] = useState<any>(null);

  // Missions list
  const { data: missionsData } = useQuery<{ missions: Mission[] }>({
    queryKey: ['missions', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/missions`),
    enabled: !!activeTopicId,
  });
  const missions = missionsData?.missions || [];
  const activeMid = selectedMissionId || missions[0]?.id || '';

  // 1. URAP Artifacts
  const { data: urapData } = useQuery<{ items: URAPArtifact[]; count: number }>({
    queryKey: ['urap-artifacts', activeTopicId, activeMid],
    queryFn: () =>
      api.get(`/api/research/topics/${activeTopicId}/artifacts-urap${activeMid ? `?mission_id=${activeMid}` : ''}`),
    enabled: !!activeTopicId,
  });
  const artifacts = urapData?.items || [];
  const activeAid = selectedArtifactId || artifacts[0]?.artifact_id || '';

  // Lineage for selected artifact
  const { data: lineageData } = useQuery<{ nodes: any[]; edges: any[] }>({
    queryKey: ['urap-lineage', activeAid],
    queryFn: () => api.get(`/api/artifacts/${activeAid}/lineage`),
    enabled: !!activeAid && tab === 'urap',
  });

  // 2. Correlated Mission Trace
  const { data: traceData } = useQuery<any>({
    queryKey: ['mission-trace', activeTopicId, activeMid],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/missions/${activeMid}/trace`),
    enabled: !!activeTopicId && !!activeMid && tab === 'trace',
  });

  // Mutations
  const registerSampleArtifactMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/research/topics/${activeTopicId}/artifacts-urap`, {
        mission_id: activeMid,
        task_id: 'manual_verify',
        artifact_type: 'experiment_result',
        producer_runtime: 'phdlab',
        content_text: JSON.stringify({ psnr_db: 31.42, ssim: 0.912, timestamp: new Date().toISOString() }),
        verification_status: 'auto_screened',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['urap-artifacts', activeTopicId, activeMid] });
    },
  });

  const verifyIntegrityMutation = useMutation({
    mutationFn: (aid: string) => api.post(`/api/artifacts/${aid}/verify-integrity`),
    onSuccess: (res) => {
      setIntegrityResult(res);
      queryClient.invalidateQueries({ queryKey: ['urap-artifacts', activeTopicId, activeMid] });
    },
  });

  const buildContextPackMutation = useMutation({
    mutationFn: () =>
      api.post('/api/tasks/preview_task/context-pack', {
        topic_id: activeTopicId,
        mission_id: activeMid,
        role,
        objective: 'Build role-tailored context pack with prompt injection defense',
        max_tokens: maxTokens,
      }),
    onSuccess: (res) => setContextPackResult(res),
  });

  const routePreviewMutation = useMutation({
    mutationFn: () =>
      api.post('/api/tasks/preview_task/route-preview', {
        topic_id: activeTopicId,
        mission_id: activeMid,
        capability,
        preferred_engine: capability === 'opencode.implement' ? 'opencode' : 'deterministic',
        simulate_quota_exhausted: simulateQuota,
        allow_metered_api: false,
      }),
    onSuccess: (res) => setRouteResult(res),
  });

  const exportReproMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/missions/${activeMid || 'default'}/reproducibility-export`, {
        topic_id: activeTopicId,
        include_ro_crate: true,
      }),
    onSuccess: (res) => setReproResult(res),
  });

  const replayReproMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/missions/${activeMid || 'default'}/reproducibility-replay`, {
        topic_id: activeTopicId,
        tolerance: 1e-6,
      }),
    onSuccess: (res) => setReplayResult(res),
  });

  const composeReportMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/missions/${activeMid || 'default'}/report-manifest`, {
        topic_id: activeTopicId,
        title: 'Unified Research Technical Report (v6.4.2)',
        export_format: 'md',
      }),
    onSuccess: (res) => setReportResult(res),
  });

  if (!activeTopicId) {
    return (
      <div style={{ padding: 16 }}>
        <p className="muted">Vui lòng chọn một Topic để mở Unified Research Intelligence Hub (v6.4.2).</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Cpu size={18} color="var(--accent)" />
          <span>Research Intelligence Hub (v6.4.2)</span>
        </h4>
        {missions.length > 0 && (
          <select
            className="input sm"
            style={{ maxWidth: 210 }}
            value={activeMid}
            onChange={(e) => setSelectedMissionId(e.target.value)}
          >
            {missions.map((m) => (
              <option key={m.id} value={m.id}>
                Mission: {m.payload.spec.objective.slice(0, 26)}…
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Sub-navigation Tabs */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', borderBottom: '1px solid var(--line)', paddingBottom: 8 }}>
        <button className={`btn sm ${tab === 'urap' ? 'accent' : 'ghost'}`} onClick={() => setTab('urap')}>
          <GitMerge size={13} style={{ marginRight: 4 }} /> URAP Artifacts & Lineage
        </button>
        <button className={`btn sm ${tab === 'trace' ? 'accent' : 'ghost'}`} onClick={() => setTab('trace')}>
          <Activity size={13} style={{ marginRight: 4 }} /> Mission Trace
        </button>
        <button className={`btn sm ${tab === 'context' ? 'accent' : 'ghost'}`} onClick={() => setTab('context')}>
          <Route size={13} style={{ marginRight: 4 }} /> Context & Smart Router
        </button>
        <button className={`btn sm ${tab === 'repro' ? 'accent' : 'ghost'}`} onClick={() => setTab('repro')}>
          <PackageCheck size={13} style={{ marginRight: 4 }} /> RO-Crate & Report
        </button>
      </div>

      {/* TAB 1: URAP 1.0 Artifacts & Lineage */}
      {tab === 'urap' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b style={{ fontSize: 13 }}>URAP 1.0 Content-Addressed Artifacts ({artifacts.length})</b>
            <button
              className="btn sm ghost"
              onClick={() => registerSampleArtifactMutation.mutate()}
              disabled={registerSampleArtifactMutation.isPending}
            >
              + Ghi nhận Artifact mẫu
            </button>
          </div>

          {artifacts.map((art) => (
            <div
              key={art.artifact_id}
              onClick={() => setSelectedArtifactId(art.artifact_id)}
              style={{
                background: activeAid === art.artifact_id ? 'var(--sel)' : 'var(--panel)',
                border: `1px solid ${activeAid === art.artifact_id ? 'var(--accent)' : 'var(--line)'}`,
                borderRadius: 8,
                padding: 10,
                cursor: 'pointer',
                display: 'grid',
                gap: 4,
                fontSize: 12.5,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <b>{art.artifact_id} · {art.artifact_type}</b>
                <span
                  className={`chip ${
                    art.verification.status === 'user_verified' || art.verification.status === 'auto_screened'
                      ? 'ok'
                      : art.verification.status === 'stale'
                      ? 'err'
                      : 'warn'
                  }`}
                  style={{ fontSize: 11 }}
                >
                  {art.verification.status.toUpperCase()}
                </span>
              </div>
              <div className="muted" style={{ fontSize: 11.5, fontFamily: 'var(--mono)' }}>
                sha256: {art.content.sha256.slice(0, 20)}… · runtime: {art.producer.runtime_id}
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
                <button
                  className="btn sm ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    verifyIntegrityMutation.mutate(art.artifact_id);
                  }}
                >
                  <ShieldCheck size={13} style={{ marginRight: 4 }} /> Kiểm định SHA-256 trên đĩa
                </button>
              </div>
            </div>
          ))}

          {integrityResult && (
            <div
              style={{
                background: integrityResult.valid ? 'var(--bg)' : 'var(--err-soft)',
                border: `1px solid ${integrityResult.valid ? 'var(--ok)' : 'var(--err)'}`,
                borderRadius: 8,
                padding: 10,
                fontSize: 12.5,
              }}
            >
              <b>Kết quả kiểm định {integrityResult.artifact_id}:</b> {integrityResult.detail}
              {integrityResult.stale_downstream?.length > 0 && (
                <div>Downstream bị đánh dấu STALE: {integrityResult.stale_downstream.join(', ')}</div>
              )}
            </div>
          )}

          {lineageData && (
            <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, padding: 10, fontSize: 12 }}>
              <b>Đồ thị nguồn gốc (Lineage Graph):</b> {lineageData.nodes.length} nodes · {lineageData.edges.length} edges
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Correlated Mission Trace */}
      {tab === 'trace' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {!activeMid ? (
            <p className="muted">Chưa có Mission nào trong Topic này để xem Trace.</p>
          ) : traceData ? (
            <>
              <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, padding: 10, fontSize: 12.5 }}>
                <div><b>Trace ID:</b> <code>{traceData.trace_id}</code> · <b>Trạng thái:</b> {traceData.mission_status}</div>
                <div className="muted" style={{ marginTop: 4 }}>
                  Task Spans: {traceData.task_spans?.length || 0} · Trace Events: {traceData.trace_events?.length || 0} · Routing Decisions: {traceData.routing_decisions?.length || 0}
                </div>
              </div>
              <div style={{ maxHeight: 260, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {traceData.trace_events?.map((ev: any) => (
                  <div key={ev.id} style={{ background: 'var(--bg)', border: '1px solid var(--line-2)', borderRadius: 6, padding: 8, fontSize: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <b>#{ev.seq} {ev.event_type}</b>
                      <code>{ev.span_id}</code>
                    </div>
                    <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>
                      {JSON.stringify(ev.payload)}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="muted">Đang tải Mission Trace…</p>
          )}
        </div>
      )}

      {/* TAB 3: Context Pack Inspector & Smart Router */}
      {tab === 'context' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, padding: 12, display: 'grid', gap: 8 }}>
            <b style={{ fontSize: 13 }}>1. Role-Aware Context Pack Builder (Chống Prompt Injection)</b>
            <div style={{ display: 'flex', gap: 8 }}>
              <select className="input sm" style={{ flex: 1 }} value={role} onChange={(e) => setRole(e.target.value as any)}>
                <option value="literature_reviewer">literature_reviewer (Chỉ tài liệu & trích dẫn)</option>
                <option value="experiment_engineer">experiment_engineer (Protocols, code & metrics)</option>
                <option value="verification_auditor">verification_auditor (Raw measurements & hashes)</option>
                <option value="synthesis_author">synthesis_author (Verified findings & figures)</option>
              </select>
              <input
                type="number"
                className="input sm"
                style={{ width: 100 }}
                value={maxTokens}
                onChange={(e) => setMaxTokens(Number(e.target.value))}
              />
              <button className="btn sm accent" onClick={() => buildContextPackMutation.mutate()}>
                Tạo Context Pack
              </button>
            </div>
            {contextPackResult && (
              <div style={{ background: 'var(--bg)', padding: 10, borderRadius: 6, fontSize: 12 }}>
                <div><b>Pack ID:</b> <code>{contextPackResult.context_pack_id}</code> · <b>Focus:</b> {contextPackResult.role_focus}</div>
                <div>
                  <b>Tokens:</b> {contextPackResult.budget?.token_estimate} / {contextPackResult.budget?.max_tokens} ·{' '}
                  <b>Prompt Injections bị chặn:</b> {contextPackResult.retrieval?.injection_attempts_blocked}
                </div>
                <div className="muted" style={{ marginTop: 4 }}>
                  Quyền bị cấm: {contextPackResult.constraints?.prohibited_actions?.join(', ')}
                </div>
              </div>
            )}
          </div>

          <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, padding: 12, display: 'grid', gap: 8 }}>
            <b style={{ fontSize: 13 }}>2. Smart Router Diagnostics (Deterministic-First & Zero Paid Fallback)</b>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <select className="input sm" value={capability} onChange={(e) => setCapability(e.target.value)}>
                <option value="paper.discover">paper.discover (Deterministic — 0 LLM)</option>
                <option value="figure.create_2d">figure.create_2d (Deterministic — 0 LLM)</option>
                <option value="opencode.implement">opencode.implement (OpenCode Peer Runtime)</option>
                <option value="paper.compare">paper.compare (Reasoning Engine)</option>
              </select>
              <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <input
                  type="checkbox"
                  checked={simulateQuota}
                  onChange={(e) => setSimulateQuota(e.target.checked)}
                />
                Giả lập hết Quota
              </label>
              <button className="btn sm accent" onClick={() => routePreviewMutation.mutate()}>
                Kiểm tra Định tuyến
              </button>
            </div>
            {routeResult && (
              <div style={{ background: 'var(--bg)', padding: 10, borderRadius: 6, fontSize: 12 }}>
                <div>
                  <b>Engine được chọn:</b> <code>{routeResult.selected_engine}</code> · <b>Trạng thái:</b> <b>{routeResult.status}</b>
                </div>
                <div>
                  <b>Số lệnh gọi LLM:</b> {routeResult.llm_calls} · <b>Metered API Fallback:</b> <code>{routeResult.metered_api_fallback}</code>
                </div>
                <div className="muted" style={{ marginTop: 4 }}>{routeResult.rationale}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Reproducibility Pack (RO-Crate 1.1) & Unified Report Composer */}
      {tab === 'repro' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, padding: 12, display: 'grid', gap: 8 }}>
            <b style={{ fontSize: 13 }}>1. Xuất Gói Tái lập Khoa học (Reproducibility Pack + RO-Crate 1.1)</b>
            <p className="muted" style={{ fontSize: 12, margin: 0 }}>
              Đóng gói môi trường (<code>requirements.lock</code>, <code>seed_policy.json</code>), kịch bản chạy lại, đồ thị URAP lineage, <code>ro-crate-metadata.json</code> và bảng băm <code>checksums.sha256</code> (tự động lọc bỏ khoá bí mật).
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                className="btn sm accent"
                onClick={() => exportReproMutation.mutate()}
                disabled={exportReproMutation.isPending}
              >
                <PackageCheck size={13} style={{ marginRight: 4 }} /> Đóng gói RO-Crate (.zip)
              </button>
              <button
                className="btn sm ghost"
                onClick={() => replayReproMutation.mutate()}
                disabled={replayReproMutation.isPending}
              >
                <Play size={13} style={{ marginRight: 4 }} /> Chạy Kiểm định Replay Độc lập
              </button>
              {activeMid && (
                <a
                  className="btn sm ghost"
                  href={`/api/missions/${activeMid}/reproducibility-export/download?topic_id=${activeTopicId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: 'none' }}
                >
                  <Download size={13} style={{ marginRight: 4 }} /> Tải xuống .ZIP
                </a>
              )}
            </div>
            {reproResult && (
              <div style={{ background: 'var(--bg)', padding: 10, borderRadius: 6, fontSize: 12 }}>
                <div><b>Export ID:</b> <code>{reproResult.export_id}</code> · <b>SHA-256:</b> <code>{reproResult.bundle_sha256?.slice(0, 20)}…</code></div>
                <div className="muted">Tệp trong gói ({reproResult.files?.length}): {reproResult.files?.join(', ')}</div>
              </div>
            )}
            {replayResult && (
              <div
                style={{
                  background: replayResult.passed ? 'var(--bg)' : 'var(--err-soft)',
                  border: `1px solid ${replayResult.passed ? 'var(--ok)' : 'var(--err)'}`,
                  padding: 10,
                  borderRadius: 6,
                  fontSize: 12,
                }}
              >
                <b>Kết quả Replay:</b> {replayResult.status.toUpperCase()} · Đã xác minh {replayResult.verified_file_count} tệp · Sai số trong ngưỡng {replayResult.tolerance}
              </div>
            )}
          </div>

          <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, padding: 12, display: 'grid', gap: 8 }}>
            <b style={{ fontSize: 13 }}>2. Unified Research Report Composer (Module H)</b>
            <p className="muted" style={{ fontSize: 12, margin: 0 }}>
              Tổng hợp báo cáo kỹ thuật gắn kết Claims đã xác minh, Figures, URAP Artifacts và tự động gắn nhãn cảnh báo <code>[UNVERIFIED / HYPOTHESIS]</code> hoặc <code>[PREPRINT]</code>.
            </p>
            <div>
              <button
                className="btn sm accent"
                onClick={() => composeReportMutation.mutate()}
                disabled={composeReportMutation.isPending}
              >
                <FileSpreadsheet size={13} style={{ marginRight: 4 }} /> Kết xuất Báo cáo Tổng hợp
              </button>
            </div>
            {reportResult && (
              <pre
                style={{
                  background: 'var(--bg)',
                  padding: 10,
                  borderRadius: 6,
                  fontSize: 11.5,
                  maxHeight: 220,
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {reportResult.markdown}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
