import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import type { Mission } from '../../shared/api/types';
import { autonomyPlan, type AutonomyLevel, type ApprovedProtocol } from './autonomyPlan';

export const AutonomyPanel: React.FC = () => {
  const { activeTopicId, project } = useUIStore();
  const { t } = useI18n();
  const cache = useQueryClient();
  const [level, setLevel] = useState<AutonomyLevel>('L2');
  const [objective, setObjective] = useState('');
  const [modelOverride, setModel] = useState<string | null>(null);
  const configuration = useQuery({ queryKey: ['config'], queryFn: () => api.get<{ local_model?: string; agent_models?: Record<string, string> }>('/api/config') });
  const model = modelOverride ?? configuration.data?.agent_models?.research ?? configuration.data?.local_model ?? '';
  const [sources, setSources] = useState<string[]>([]);
  const [protocolId, setProtocolId] = useState('');
  const [reproductionId, setReproductionId] = useState('');
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const base = `/api/research/topics/${activeTopicId}`;
  const key = ['autonomy', project?.data_dir, activeTopicId];
  const missions = useQuery({ queryKey: [...key, 'missions'], queryFn: () => api.get<{ missions: Mission[] }>(`${base}/missions`), enabled: !!activeTopicId, refetchInterval: 1000 });
  const papers = useQuery({ queryKey: [...key, 'papers'], queryFn: () => api.get<{ papers: { id: string; title: string }[] }>(`${base}/papers?limit=100`), enabled: !!activeTopicId });
  const protocols = useQuery({ queryKey: [...key, 'protocols'], queryFn: () => api.get<{ protocols: ApprovedProtocol[] }>(`${base}/protocols`), enabled: !!activeTopicId });
  const settings = useQuery({ queryKey: ['autonomy-settings'], queryFn: () => api.get<{ enabled: boolean }>('/api/research/os-settings') });

  async function perform(action: () => Promise<unknown>) {
    setBusy(true); setError('');
    try { await action(); await cache.invalidateQueries({ queryKey: ['autonomy'] }); await cache.invalidateQueries({ queryKey: ['autonomy-settings'] }); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  if (!activeTopicId) return <p>{t('Chọn chủ đề để tạo workflow.', 'Select a topic to create a workflow.')}</p>;

  return <section aria-label="Workflows L1–L4" style={{ display: 'grid', gap: 12 }}>
    <h3>Workflows L1–L4</h3>
    <p>{t('Tối đa 4 workflow độc lập. Model local dùng chung giới hạn tài nguyên. L3/L4 là policy thử nghiệm; kiểm tra kỹ thuật chưa xác nhận tính đúng đắn khoa học.', 'Up to 4 independent workflows. Local models share resource limits. L3/L4 are experimental policies; technical checks do not establish scientific validity.')}</p>
    {!settings.data?.enabled && <button className="btn" disabled={busy} onClick={() => perform(() => api.put('/api/research/os-settings', { enabled: true }))}>{t('Bật Research OS', 'Enable Research OS')}</button>}
    {(error || missions.error || papers.error || protocols.error || settings.error) && <p role="alert">{error || String(missions.error || papers.error || protocols.error || settings.error)}</p>}
    <form onSubmit={event => { event.preventDefault(); perform(() => api.post(`${base}/missions`, autonomyPlan(activeTopicId, level, objective, model, sources, protocols.data?.protocols.find(p => p.id === protocolId), protocols.data?.protocols.find(p => p.id === reproductionId)))); }} style={{ display: 'grid', gap: 8 }}>
      <label>{t('Chế độ tương tác', 'Interaction level')}<select className="input" value={level} onChange={e => setLevel(e.target.value as AutonomyLevel)}>
        <option value="L1">L1 — {t('Hỗ trợ từng bước', 'Bounded assistance')}</option>
        <option value="L2">L2 — {t('Thực thi, xác nhận từng kết quả', 'Execute, verify each result')}</option>
        <option value="L3">L3 — {t('Tự điều phối, review cuối', 'Coordinate, final human review')}</option>
        <option value="L4">L4 — {t('Tự đóng kỹ thuật có kiểm chứng', 'Verified technical closure')}</option>
      </select></label>
      {level === 'L4' && protocolId && <label>{t('Protocol tái lập đã duyệt riêng', 'Separately approved reproduction protocol')}<select className="input" value={reproductionId} onChange={e => setReproductionId(e.target.value)}>
        <option value="">{t('Chọn bản tái lập cùng digest', 'Select reproduction with the same digest')}</option>
        {protocols.data?.protocols.filter(p => p.approval && p.id !== protocolId).map(p => <option key={p.id} value={p.id}>{p.id}</option>)}
      </select></label>}
      <label>{t('Mục tiêu', 'Objective')}<textarea className="input" required maxLength={4000} value={objective} onChange={e => setObjective(e.target.value)} /></label>
      <label>LM Studio model<input className="input" required value={model} onChange={e => setModel(e.target.value)} /></label>
      <fieldset><legend>{t('Chọn ít nhất 2 nguồn', 'Select at least 2 sources')}</legend>
        {papers.data?.papers.map(p => <label key={p.id} style={{ display: 'block' }}><input type="checkbox" checked={sources.includes(p.id)} onChange={e => setSources(e.target.checked ? [...sources, p.id] : sources.filter(id => id !== p.id))} />{p.title}</label>)}
      </fieldset>
      <label>{t('Protocol đã duyệt (tùy chọn)', 'Approved protocol (optional)')}<select className="input" disabled={level === 'L1'} value={protocolId} onChange={e => setProtocolId(e.target.value)}>
        <option value="">{t('Chỉ tổng hợp nguồn; không có thí nghiệm', 'Source synthesis; no experiment')}</option>
        {protocols.data?.protocols.filter(p => p.approval).map(p => <option key={p.id} value={p.id}>{p.id}</option>)}
      </select></label>
      <button className="btn accent" disabled={busy || sources.length < 2} type="submit">{t('Tạo bản nháp', 'Create draft')}</button>
    </form>
    {missions.isLoading && <p role="status">{t('Đang tải…', 'Loading…')}</p>}
    {missions.data?.missions.filter(m => m.payload.spec.autonomy).map(m => {
      const pending = m.tasks.find(task => task.status === 'completed' && !task.payload.human_review);
      const note = notes[m.id] || '';
      const url = `${base}/missions/${m.id}`;
      const review = (accept: boolean) => perform(() => api.post(`${url}/steps/${pending!.id}/review`, { plan_digest: m.payload.plan_digest, result_digest: pending!.payload.result_digest, accept, note }));
      return <article key={m.id} style={{ border: '1px solid var(--line)', padding: 12, minWidth: 0 }}>
        <h4>{m.payload.spec.autonomy!.level} · {m.payload.spec.objective}</h4>
        <p role="status">{m.status} · {t('Review khoa học: chờ xác nhận', 'Scientific review: pending')}</p>
        {m.payload.blocking_reason && <p role="alert">{m.payload.blocking_reason}</p>}
        <details><summary>{t('Kế hoạch và kết quả', 'Plan and results')}</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ digest: m.payload.plan_digest, spec: m.payload.spec, tasks: m.tasks }, null, 2)}</pre></details>
        <label>{t('Ghi chú review', 'Review note')}<input className="input" value={note} onChange={e => setNotes({ ...notes, [m.id]: e.target.value })} /></label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {['draft', 'paused'].includes(m.status) && <button className="btn" disabled={busy || !note.trim() || !settings.data?.enabled} onClick={() => perform(() => api.post(`${url}/approve`, { plan_digest: m.payload.plan_digest, note }))}>{t('Duyệt kế hoạch và chạy', 'Approve plan and run')}</button>}
          {m.status === 'awaiting_step_review' && pending && <>
            <pre style={{ width: '100%', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(pending.payload.result, null, 2)}</pre>
            <button className="btn" disabled={busy || !note.trim()} onClick={() => review(true)}>{t('Chấp nhận bước', 'Accept step')}</button>
            <button className="btn" disabled={busy || !note.trim()} onClick={() => review(false)}>{t('Từ chối bước', 'Reject step')}</button>
          </>}
          {m.status === 'awaiting_review' && <button className="btn" disabled={busy || !note.trim()} onClick={() => perform(() => api.post(`${url}/review`, { note }))}>{t('Hoàn tất review', 'Complete review')}</button>}
          {!['completed', 'cancelled'].includes(m.status) && <button className="btn" disabled={busy} onClick={() => perform(() => api.post(`${url}/cancel`, {}))}>{t('Hủy workflow', 'Cancel workflow')}</button>}
        </div>
      </article>;
    })}
  </section>;
};
