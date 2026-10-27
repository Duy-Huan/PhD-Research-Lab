import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useI18n } from '../../shared/state/uiStore';

interface UsageReport {
  scope: string; total_requests: number; malformed_records: number; truncated: boolean;
  providers: Array<{ provider: string; model: string; requests: number; completed: number; failed: number;
    cancelled: number; input_tokens: number | null; output_tokens: number | null; usage_reported: number;
    mean_latency_ms: number | null }>;
}

export function ModelUsagePanel() {
  const { t } = useI18n();
  const report = useQuery({ queryKey: ['model-usage'], queryFn: async () => {
    const result = await api.get<UsageReport>('/api/models/usage');
    if (!result || !Array.isArray(result.providers)) throw new Error('Invalid usage response');
    return result;
  }, refetchInterval: 10000 });
  return <section className="panelbox" style={{ padding: 16 }} aria-label={t('Sử dụng model', 'Model usage')}>
    <h3>{t('Sử dụng model qua gateway', 'Gateway model usage')}</h3>
    <p className="muted">{t('Theo project hiện tại. Chỉ hiển thị usage do runtime trả về; chi phí subscription và số liệu không được báo cáo vẫn chưa xác định.', 'Current project only. Usage comes from runtime reports; subscription cost and unreported measurements remain unknown.')}</p>
    {report.isLoading && <p role="status">{t('Đang tải số liệu…', 'Loading usage…')}</p>}
    {report.isError && <p role="alert">{t('Không tải được số liệu sử dụng.', 'Could not load usage.')}</p>}
    {report.data && !report.data.providers.length && <p>{t('Chưa có truy vấn gateway được ghi nhận.', 'No recorded gateway requests yet.')}</p>}
    {!!report.data?.providers.length && <div style={{ overflowX: 'auto' }}>
      <table className="table" style={{ width: '100%', fontVariantNumeric: 'tabular-nums' }}>
        <thead><tr>{[t('Provider / model', 'Provider / model'), t('Thành công / lỗi / hủy', 'Completed / failed / cancelled'), t('Token vào / ra', 'Input / output tokens'), t('Đã có usage', 'Usage reported'), t('Độ trễ TB', 'Mean latency')].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
        <tbody>{report.data?.providers.map(row => <tr key={row.provider + ':' + row.model}>
          <td style={{ overflowWrap: 'anywhere' }}>{row.provider}<br /><span className="muted">{row.model === '(not reported)' ? t('Model chưa được báo cáo', 'Model not reported') : row.model}</span></td>
          <td>{row.completed} / {row.failed} / {row.cancelled}</td>
          <td>{row.input_tokens ?? '—'} / {row.output_tokens ?? '—'}</td>
          <td>{row.usage_reported} / {row.requests}</td>
          <td>{row.mean_latency_ms === null ? '—' : new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(row.mean_latency_ms) + ' ms'}</td>
        </tr>)}</tbody>
      </table>
    </div>}
    {!!report.data?.malformed_records && <p role="alert">{t('Có bản ghi hỏng chưa được tính: ', 'Malformed records excluded: ')}{report.data.malformed_records}</p>}
    {report.data?.truncated && <p>{t('Báo cáo giới hạn 2.000 truy vấn mới nhất.', 'Report is limited to the latest2,000 requests.')}</p>}
  </section>;
}
