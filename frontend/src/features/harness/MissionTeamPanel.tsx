import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useI18n, useUIStore } from '../../shared/state/uiStore';

// v6.6.4 (A9): the team is proposed by a model from the model list, each agent stays bound to a listed model (an
// unavailable one is shown, never swapped), and the canvas runs as a governed mission the researcher approves in Missions.

export interface TeamModel { id: string; label: string; state: string; available: boolean }
export interface TeamAgent { id: string; role: string; purpose: string; prompt?: string; tools: string[]; model: string; model_available?: boolean }
interface Compiled { spec: { tasks: { id: string; capability: string }[] }; notes: string[]; mission?: { id: string; status: string } }

interface Props {
  workflow: () => { nodes: unknown[]; edges: unknown[]; name?: string };
  level: 'L2' | 'L3' | 'L4';
  objective: string;
  topicId?: string;
}

export const MissionTeamPanel: React.FC<Props> = ({ workflow, level, objective, topicId }) => {
  const { t } = useI18n();
  const { activeTopicId, openDrawer } = useUIStore();
  const topic = topicId || activeTopicId || '';
  const models = useQuery({ queryKey: ['harness-models'], queryFn: () => api.get<{ models: TeamModel[] }>('/api/harness/models') });
  const [architect, setArchitect] = useState('');
  const [team, setTeam] = useState<TeamAgent[]>([]);
  const [rationale, setRationale] = useState('');
  const [compiled, setCompiled] = useState<Compiled | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const list = models.data?.models ?? [];
  const byId = Object.fromEntries(list.map(m => [m.id, m]));

  async function act(name: string, action: () => Promise<void>) {
    setBusy(name); setError('');
    try { await action(); } catch (err) { setError((err as Error).message); } finally { setBusy(''); }
  }
  const propose = () => act('propose', async () => {
    const res = await api.post<{ agents: TeamAgent[]; rationale: string }>('/api/harness/team/propose', { objective, architect_model: architect });
    setTeam(res.agents); setRationale(res.rationale); setCompiled(null);
  });
  const compile = (create: boolean) => act(create ? 'create' : 'compile', async () => {
    setCompiled(await api.post<Compiled>('/api/harness/compile', { workflow: workflow(), topic_id: topic, level, team, objective, create }));
  });

  return (
    <section aria-label={t('Đội agent của nhiệm vụ', 'Mission team')} style={{ display: 'grid', gap: 8, paddingBottom: 10, borderBottom: '1px solid var(--line)' }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>{t('Đội agent do AI đề xuất', 'AI-proposed team')}</span>
      <label style={{ display: 'grid', gap: 4, fontSize: 12 }}>
        {t('Mô hình kiến trúc sư (từ danh sách mô hình)', 'Architect model (from the model list)')}
        <select className="input sm" value={architect} onChange={e => setArchitect(e.target.value)} aria-busy={models.isLoading}>
          <option value="">{models.isLoading ? t('Đang tải mô hình…', 'Loading models…') : t('Chọn mô hình', 'Choose a model')}</option>
          {list.map(m => <option key={m.id} value={m.id}>{m.label} ({m.id}){m.available ? '' : ` — ${t('chưa sẵn sàng', 'unavailable')}: ${m.state}`}</option>)}
        </select>
      </label>
      <button type="button" className="btn sm accent" disabled={!architect || !objective.trim() || !!busy} onClick={propose}
              title={objective.trim() ? undefined : t('Nhập mục tiêu ở tab Architect', 'Enter the objective in the Architect tab')}>
        {busy === 'propose' ? t('Đang đề xuất…', 'Proposing…') : t('Đề xuất đội bằng AI', 'Propose team with AI')}
      </button>
      {rationale && <p className="muted" style={{ fontSize: 11.5, margin: 0 }}>{rationale}</p>}
      {team.map((a, i) => (
        <div key={a.id} style={{ border: '1px solid var(--line)', borderRadius: 8, padding: 8, display: 'grid', gap: 4, fontSize: 12 }}>
          <b>{a.id} <span className="muted">· {a.role}</span></b>
          <span>{a.purpose}</span>
          {a.tools.length > 0 && <span className="muted" style={{ fontSize: 11 }}>{t('Công cụ', 'Tools')}: {a.tools.join(', ')}</span>}
          <label style={{ display: 'grid', gap: 2 }}>
            {t('Mô hình', 'Model')}
            <select className="input sm" value={a.model} aria-label={`${t('Mô hình của', 'Model of')} ${a.id}`}
                    onChange={e => setTeam(team.map((x, j) => j === i ? { ...x, model: e.target.value, model_available: byId[e.target.value]?.available } : x))}>
              {list.map(m => <option key={m.id} value={m.id}>{m.label} ({m.id})</option>)}
            </select>
          </label>
          {byId[a.model] && !byId[a.model].available && (
            <span role="status" style={{ color: 'var(--warn, #b45309)', fontSize: 11.5 }}>
              {t('Mô hình chưa sẵn sàng', 'Model unavailable')}: {byId[a.model].state}. {t('Nhiệm vụ sẽ tạm dừng ở bước này, không đổi sang mô hình khác.', 'The mission pauses at this step; no other model is used.')}
            </span>
          )}
        </div>
      ))}
      {team.length > 0 && (
        <div style={{ display: 'flex', gap: 6 }}>
          <button type="button" className="btn sm" disabled={!topic || !!busy} onClick={() => compile(false)}>
            {busy === 'compile' ? t('Đang biên dịch…', 'Compiling…') : t('Xem nhiệm vụ', 'Preview mission')}
          </button>
          <button type="button" className="btn sm accent" disabled={!topic || !!busy} onClick={() => compile(true)}>
            {busy === 'create' ? t('Đang tạo…', 'Creating…') : t('Tạo nhiệm vụ để duyệt', 'Create mission for approval')}
          </button>
        </div>
      )}
      {team.length > 0 && !topic && <p className="muted" style={{ fontSize: 11.5, margin: 0 }}>{t('Chọn một Chủ đề trước.', 'Select a Topic first.')}</p>}
      {error && <p role="alert" style={{ fontSize: 12, margin: 0 }}>{error}</p>}
      {compiled && (
        <div style={{ display: 'grid', gap: 4, fontSize: 12 }}>
          <b>{t('Các bước của nhiệm vụ', 'Mission steps')} ({compiled.spec.tasks.length})</b>
          <ol style={{ margin: 0, paddingLeft: 18 }}>
            {compiled.spec.tasks.map(task => <li key={task.id}><code>{task.capability}</code> <span className="muted">{task.id}</span></li>)}
          </ol>
          {compiled.notes.map(note => <p key={note} className="muted" style={{ fontSize: 11.5, margin: 0 }}>{note}</p>)}
          {compiled.mission && (
            <p role="status" style={{ margin: 0 }}>
              {t('Đã tạo nhiệm vụ nháp', 'Draft mission created')} <code>{compiled.mission.id}</code>.{' '}
              <button type="button" className="btn xs" onClick={() => openDrawer('missions')}>{t('Mở Nhiệm vụ để duyệt', 'Open Missions to approve')}</button>
            </p>
          )}
        </div>
      )}
    </section>
  );
};
