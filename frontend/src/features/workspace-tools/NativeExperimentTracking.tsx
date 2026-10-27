import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, request } from '../../shared/api/client';
import { useI18n } from '../../shared/state/uiStore';

interface ProcessRun { run_id: string; status: string; exit_code?: number; metrics?: Record<string, unknown> }
interface ComputeRun {
  run_id: string; backend?: string; status: string; approvals: unknown[]; metrics: Record<string, unknown>;
  verification?: Record<string, string>;
  imports?: {sha256: string}[];
  artifact_refs?: {name: string; path: string}[];
}

export function NativeExperimentTracking() {
  const { t } = useI18n();
  const client = useQueryClient();
  const [files, setFiles] = useState('train.py\nrequirements.txt');
  const [entrypoint, setEntrypoint] = useState('train.py');
  const [required, setRequired] = useState('metrics.json\nbest.pt');
  const [dataset, setDataset] = useState('[]');
  const [target, setTarget] = useState('colab-gpu');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const tracking = useQuery<{ process_runs: ProcessRun[]; protocol_runs: ProcessRun[] }>({
    queryKey: ['native-tracking'], queryFn: async () => {
      const data = await api.get<{process_runs: ProcessRun[]; protocol_runs: ProcessRun[]}>('/api/tracking/runs');
      if (!Array.isArray(data.process_runs) || !Array.isArray(data.protocol_runs)) throw new Error(t('Dữ liệu tracking không hợp lệ.', 'Invalid tracking response.'));
      return data;
    }, refetchInterval: 10000,
  });
  const compute = useQuery<{ runs: ComputeRun[] }>({
    queryKey: ['native-compute'], queryFn: async () => {
      const data = await api.get<{runs: ComputeRun[]}>('/api/compute/runs');
      if (!Array.isArray(data.runs)) throw new Error(t('Dữ liệu compute không hợp lệ.', 'Invalid compute response.'));
      return data;
    },
  });
  const refresh = () => Promise.all([
    client.invalidateQueries({queryKey: ['native-tracking']}),
    client.invalidateQueries({queryKey: ['native-compute']}),
  ]);
  const create = useMutation({
    mutationFn: () => api.post('/api/compute/runs', {
      files: files.split('\n').map(value => value.trim()).filter(Boolean), entrypoint,
      required_artifacts: required.split('\n').map(value => value.trim()).filter(Boolean),
      dataset_manifest: JSON.parse(dataset), compute_target: target,
    }),
    onSuccess: () => { setError(''); void refresh(); }, onError: (err: Error) => setError(err.message),
  });
  async function approve(id: string) {
    setBusy(id); setError('');
    try { await api.post(`/api/compute/runs/${id}/approve`, {}); await refresh(); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(''); }
  }
  async function upload(id: string, file: File) {
    setBusy(id); setError('');
    try {
      await request(`/api/compute/runs/${id}/results`, {method: 'POST', headers: {'Content-Type': 'application/zip'}, body: file});
      await refresh();
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(''); }
  }
  return <section aria-label={t('Theo dõi thí nghiệm native', 'Native experiment tracking')} style={{display: 'grid', gap: 10}}>
    <h4>{t('Nhật ký và kết quả thí nghiệm', 'Experiment journals & results')}</h4>
    <p className="muted">{t('Trạng thái tiến trình, metrics thô và kiểm chứng khoa học được theo dõi riêng.', 'Process status, raw metrics and scientific verification are tracked separately.')}</p>
    <button className="btn sm" type="button" onClick={() => void refresh()}>{t('Làm mới kết quả', 'Refresh results')}</button>
    {(error || tracking.error || compute.error) && <p role="alert">{error || tracking.error?.message || compute.error?.message}</p>}
    {(tracking.isPending || compute.isPending) && <p role="status">{t('Đang tải kết quả…', 'Loading results…')}</p>}
    {tracking.data && [...tracking.data.process_runs, ...tracking.data.protocol_runs].map((run, index) => <details key={`${run.run_id}-${index}`}>
      <summary>{run.run_id}: {run.status}</summary>
      <pre style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{JSON.stringify(run, null, 2)}</pre>

    </details>)}
    {tracking.data && !tracking.data.process_runs.length && !tracking.data.protocol_runs.length && <p>{t('Chưa có lần chạy nào trong project.', 'No runs in this project yet.')}</p>}
    <details>
      <summary>{t('Chuẩn bị gói chạy GPU / Docker / Colab', 'Prepare GPU / Docker / Colab bundle')}</summary>
      <form onSubmit={event => { event.preventDefault(); create.mutate(); }} style={{display: 'grid', gap: 8}}>
        <label>{t('Môi trường chạy', 'Compute target')}<select className="input" value={target} onChange={event => setTarget(event.target.value)}>
          <option value="colab-gpu">Colab GPU</option><option value="local-gpu">Local GPU</option><option value="docker">Docker</option>
        </select></label>
        <label>{t('File code/config cần chuyển (mỗi dòng một file)', 'Code/config files to transfer (one per line)')}<textarea className="input" value={files} onChange={event => setFiles(event.target.value)} required /></label>
        <label>{t('Script khởi chạy', 'Entrypoint')}<input className="input" value={entrypoint} onChange={event => setEntrypoint(event.target.value)} required /></label>
        <label>{t('Artifact bắt buộc (mỗi dòng một tên)', 'Required artifacts (one name per line)')}<textarea className="input" value={required} onChange={event => setRequired(event.target.value)} required /></label>
        <label>{t('Dataset manifest JSON: path và sha256', 'Dataset manifest JSON: path and sha256')}<textarea className="input" value={dataset} onChange={event => setDataset(event.target.value)} required /></label>
        <button className="btn sm" type="submit" disabled={create.isPending}>{t('Chuẩn bị để duyệt', 'Prepare for review')}</button>
      </form>
    </details>
    {compute.data?.runs.map(run => <details key={run.run_id}>
      <summary>{run.run_id}: {run.status}</summary>
      <pre style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{JSON.stringify(run, null, 2)}</pre>
      {run.artifact_refs?.map(artifact => {
        const digest = /^imports\/([0-9a-f]{64})\/artifacts\//.exec(artifact.path)?.[1];
        return digest ? <a className="btn sm" key={artifact.path} download href={`/api/compute/runs/${run.run_id}/imports/${digest}/file?name=${encodeURIComponent(artifact.name)}`}>{artifact.name}</a> : null;
      })}
      {run.backend !== 'native' && <p>{t('Gói dịch vụ cũ: chỉ đọc, giữ nguyên dữ liệu lịch sử.', 'Historical service bundle: read only, original data preserved.')}</p>}
      {run.backend === 'native' && run.status === 'awaiting_approval' && <button className="btn sm" disabled={!!busy} onClick={() => void approve(run.run_id)}>{t('Duyệt chuyển gói code', 'Approve code transfer')}</button>}
      {!!run.approvals?.length && <>
        <a className="btn sm" href={`/api/compute/runs/${run.run_id}/bundle`} download>{t('Tải gói đã duyệt', 'Download approved bundle')}</a>
        <p className="muted">{t('Chạy launch.py trong môi trường đã chọn rồi tải results.zip về đây. Kết quả cần được tái lập và review riêng.', 'Run launch.py in the selected environment, then upload results.zip here. Reproduction and scientific review remain separate.')}</p>
        {run.backend === 'native' && <label>{t('Nhập results.zip', 'Import results.zip')}<input type="file" accept=".zip,application/zip" disabled={!!busy} onChange={event => {
          const file = event.currentTarget.files?.[0];
          if (file) void upload(run.run_id, file);
          event.currentTarget.value = '';
        }} /></label>}
      </>}
    </details>)}
    {!!busy && <p role="status">{t('Đang xử lý…', 'Processing…')}</p>}
  </section>;
}
