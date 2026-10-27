import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import type { AppConfig, ModelsResponse } from '../../shared/api/types';
import { useI18n } from '../../shared/state/uiStore';

/** One backend inventory for API, local, subscription CLI and isolated agent runtimes. */
export function GatewayConnections({ config }: { config: AppConfig }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState('');
  const [feedbackError, setFeedbackError] = useState(false);
  const inventory = useQuery({ queryKey: ['models'], queryFn: () => api.get<ModelsResponse>('/api/models') });
  const profile = config.gateway?.cli_profile || 'review';
  async function action(key: string, execute: () => Promise<unknown>) {
    setBusy(key); setFeedback(''); setFeedbackError(false);
    try {
      const result = await execute();
      const value = result && typeof result === 'object' ? result as Record<string, unknown> : {};
      const unavailable = value.launched === false || value.terminal_launched === false || value.ready === false
        || ['UNAVAILABLE', 'BLOCKED', 'UNSUPPORTED', 'AUTH_REQUIRED'].includes(String(value.state || ''));
      setFeedbackError(unavailable);
      setFeedback(unavailable
        ? typeof value.detail === 'string' ? value.detail : t('Thao tác chưa thực hiện được.', 'Action unavailable.')
        : typeof value.reply === 'string' ? t('Model trả lời: ', 'Model replied: ') + value.reply
        : t('Đã thực hiện. Trạng thái kết nối và truy vấn được kiểm tra riêng.', 'Action completed. Connection and inference are verified separately.'));
      await Promise.all([queryClient.invalidateQueries({ queryKey: ['models'] }), queryClient.invalidateQueries({ queryKey: ['config'] })]);
    } catch (error) {
      const message = error instanceof Error ? error.message : t('Không thể thực hiện thao tác.', 'Action unavailable.');
      setFeedbackError(true);
      setFeedback(message);
    } finally { setBusy(null); }
  }
  return <section className="panelbox" aria-label={t('Kết nối AI thống nhất', 'Unified AI connections')} style={{ padding: 20, marginTop: 0 }}>
    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
      <h3 style={{ margin: 0 }}>{t('Kết nối AI', 'AI connections')}</h3>
      <button className="btn sm ghost" type="button" disabled={inventory.isFetching} onClick={() => inventory.refetch()}>
        {t('Làm mới trạng thái', 'Refresh status')}
      </button>
    </div>
    <p className="muted">{t('API, AI local, CLI subscription và agent runtime dùng chung danh mục. Đã cài đặt hoặc đăng nhập chưa có nghĩa là truy vấn đã thành công.', 'API, local AI, subscription CLIs and agent runtimes share one catalog. Installation or sign-in alone does not verify inference.')}</p>
    {inventory.isLoading && <p role="status">{t('Đang tải kết nối…', 'Loading connections…')}</p>}
    {inventory.isError && <p role="alert">{t('Không tải được danh mục. Làm mới để thử lại.', 'Could not load connections. Refresh to retry.')}</p>}
    <div className="list">
      {(inventory.data?.providers || []).filter(provider => provider.transport === 'cli' || provider.transport === 'runtime').map(provider => {
        const hermes = provider.id === 'runtime:hermes';
        const cliId = provider.id.replace(/^cli:/, '');
        const readiness = provider.readiness || {};
        const unsupported = readiness.inference === 'UNSUPPORTED';
        return <article key={provider.id} style={{ border: '1px solid var(--line)', borderRadius: 8, padding: 14, minWidth: 0 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'space-between', alignItems: 'baseline' }}>
            <strong>{provider.label}</strong><span className="chip">{provider.state}</span>
          </div>
          <p className="muted" style={{ overflowWrap: 'anywhere' }}>{provider.runtime?.detail || provider.detail}</p>
          <dl style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 20px', fontSize: 12 }}>
            {[
              [t('Cài đặt', 'Installation'), readiness.installation],
              [t('Đăng nhập', 'Authentication'), readiness.authentication],
              [t('Cách ly', 'Isolation'), readiness.isolation],
              [t('Nguồn model', 'Model catalog'), provider.model_catalog?.origin],
              [t('Truy vấn', 'Inference'), readiness.inference],
            ].map(([label, value]) => <div key={label}><dt className="muted">{label}</dt><dd style={{ margin: 0 }}>{value || t('Chưa xác minh', 'Unverified')}</dd></div>)}
          </dl>
          <p className="muted" style={{ fontSize: 12 }}>{hermes
            ? t('Chỉ model được Nous báo giá miễn phí. Memory, skills và hội thoại lưu theo project; không fallback trả phí.', 'Only models currently priced free by Nous. Memory, skills and conversations persist per project; no paid fallback.')
            : t('Đăng nhập chính thức trong CLI cách ly; không nhập khóa OpenAI API cho ChatGPT subscription.', 'Official sign-in in the isolated CLI; ChatGPT subscription does not require an OpenAI API key.')}</p>
          {hermes && <label className="field"><span>{t('Model mặc định của Hermes', 'Hermes default model')}</span>
            <select className="input" name="hermes-model" value={config.hermes?.model || ''} disabled={busy !== null}
              onChange={event => { const model = event.target.value; action('hermes-model', () => api.post('/api/config', { hermes: { model } })); }}>
              <option value="">{t('Chọn model miễn phí sau khi làm mới danh mục', 'Refresh the catalog, then select a free model')}</option>
              {config.hermes?.model && !provider.models.includes(config.hermes.model) && <option value={config.hermes.model}>{config.hermes.model} ({t('chưa xác minh', 'unverified')})</option>}
              {provider.models.map(model => <option key={model} value={model}>{model}</option>)}
            </select>
          </label>}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
            {hermes && <>
              <button type="button" className="btn sm" disabled={busy !== null} onClick={() => action('hermes-start', () => api.post('/api/runtimes/hermes/start', { profile }))}>{t('Khởi động Hermes', 'Start Hermes')}</button>
              <button type="button" className="btn sm ghost" disabled={busy !== null} onClick={() => action('hermes-stop', () => api.post('/api/runtimes/hermes/stop', { profile }))}>{t('Dừng, giữ dữ liệu', 'Stop, keep data')}</button>
            </>}
            <button type="button" className="btn sm ghost" disabled={busy !== null || unsupported}
              onClick={() => action(provider.id + '-connect', () => hermes ? api.post('/api/runtimes/hermes/connect', { profile }) : api.post(`/api/providers/${cliId}/connect`, { mode: 'terminal' }))}>
              {t('Đăng nhập chính thức', 'Official sign-in')}
            </button>
            {(hermes || cliId === 'codex') && <button type="button" className="btn sm ghost" disabled={busy !== null}
              onClick={() => action(provider.id + '-models', () => hermes ? api.post('/api/runtimes/hermes/models', { profile }) : api.post('/api/models/cli/codex'))}>
              {t('Lấy danh sách model', 'Discover models')}
            </button>}
            <button type="button" className="btn sm ghost" disabled={busy !== null || !provider.available || (hermes && !config.hermes?.model)}
              onClick={() => action(provider.id + '-test', () => api.post('/api/models/test', { provider: provider.id, model: hermes ? config.hermes?.model : '' }))}>
              {busy === provider.id + '-test' ? t('Đang truy vấn…', 'Querying…') : t('Kiểm tra truy vấn', 'Test inference')}
            </button>
          </div>
        </article>;
      })}
    </div>
    <p role={feedbackError ? 'alert' : 'status'} aria-live={feedbackError ? 'assertive' : 'polite'} style={{ overflowWrap: 'anywhere' }}>{feedback}</p>
  </section>;
}
