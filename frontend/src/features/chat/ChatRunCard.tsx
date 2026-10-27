import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useI18n } from '../../shared/state/uiStore';

export function ChatRunCard({ id }: { id: string }) {
  const { t } = useI18n();
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const query = useQuery<any>({queryKey: ['chat-run', id], queryFn: () => api.get(`/api/runs/${id}`),
    refetchInterval: q => ['COMPLETED', 'FAILED', 'CANCELLED'].includes(q.state.data?.status) ? false : 2000});
  const run = query.data;
  async function act(action: string) {
    setBusy(true); setError('');
    try { await api.post(`/api/runs/${id}/${action}`, {}); await query.refetch(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <aside aria-label={`Run ${id}`} style={{marginTop: 8}}>
    <b>{id}: {run?.status || t('Đang tải', 'Loading')}</b>
    {run?.reason && <div>{run.reason}</div>}
    {run?.status === 'APPROVAL_PENDING' && <button className="btn" disabled={busy} onClick={() => act('approve')}>
      {t('Duyệt và chạy', 'Approve and run')}
    </button>}
    {run && !['COMPLETED', 'FAILED', 'CANCELLED'].includes(run.status) && <button className="btn" disabled={busy} onClick={() => act('cancel')}>
      {t('Hủy run', 'Cancel run')}
    </button>}
    {(error || query.error) && <div role="alert">{error || query.error?.message}</div>}
  </aside>;
}
