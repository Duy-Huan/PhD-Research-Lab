import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import type { OpenCodeSession } from '../../shared/api/types';

/** Historical data only. No retired application launch, write, approval or polling. */
export const OpenCodePanel: React.FC = () => {
  const { activeTopicId } = useUIStore();
  const { t } = useI18n();
  const query = useQuery<{ sessions: OpenCodeSession[] }>({
    queryKey: ['historical-opencode-sessions', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/opencode/sessions`),
    enabled: !!activeTopicId,
  });
  if (!activeTopicId) return <p className="muted">{t('Chọn chủ đề bài báo để xem lịch sử coding.', 'Select the paper topic to view coding history.')}</p>;
  return <details><summary>{t('Lịch sử OpenCode (chỉ đọc)', 'OpenCode history (read only)')}</summary>
    <p className="muted">{t('Trạng thái bên dưới là dữ liệu cũ, không phải tiến trình đang chạy.', 'The records below are historical; they do not represent currently running processes.')}</p>
    {query.isPending && <p role="status">{t('Đang tải lịch sử…', 'Loading history…')}</p>}
    {query.error && <p role="alert">{query.error.message}</p>}
    {query.data?.sessions.length === 0 && <p>{t('Chưa có lịch sử.', 'No historical records.')}</p>}
    {query.data?.sessions.map(session => <details key={session.id}>
      <summary>{session.id}: {session.status}</summary>
      <pre style={{whiteSpace:'pre-wrap', overflowWrap:'anywhere'}}>{JSON.stringify(session.payload, null, 2)}</pre>
    </details>)}
  </details>;
};
