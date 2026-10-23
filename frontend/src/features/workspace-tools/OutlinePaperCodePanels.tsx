import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import {
  FileText,
  Save,
  Code,
  Play,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  FlaskConical,
  Plus,
} from 'lucide-react';

// ── 1. Outline Panel (/api/outline) ────────────────────────────────────────

export const OutlinePanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { data: outline, isLoading } = useQuery<any>({
    queryKey: ['outline'],
    queryFn: () => api.get('/api/outline'),
  });

  const [fields, setFields] = useState<Record<string, string>>({
    keywords: '',
    topic: '',
    direction: '',
    method: '',
    proposal: '',
  });

  useEffect(() => {
    if (outline) {
      setFields({
        keywords: outline.keywords || '',
        topic: outline.topic || '',
        direction: outline.direction || '',
        method: outline.method || '',
        proposal: outline.proposal || '',
      });
    }
  }, [outline]);

  const saveMutation = useMutation({
    mutationFn: () => api.put('/api/outline', { ...fields, reason: 'Updated via React Outline Panel' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['outline'] });
      alert('Đã lưu đề cương nghiên cứu 5 cấp độ!');
    },
  });

  const levels = [
    { key: 'keywords', label: 'Cấp 1 — Từ khóa nghiên cứu (Keywords)' },
    { key: 'topic', label: 'Cấp 2 — Chủ đề trọng tâm (Research Topic)' },
    { key: 'direction', label: 'Cấp 3 — Hướng tiếp cận & Giả thuyết (Direction)' },
    { key: 'method', label: 'Cấp 4 — Phương pháp & Kiến trúc (Methodology)' },
    { key: 'proposal', label: 'Cấp 5 — Đề cương chi tiết (Proposal)' },
  ];

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0 }}>Đề cương nghiên cứu 5 cấp độ (Outline)</h4>
        <button className="btn sm accent" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Save size={13} style={{ marginRight: 4 }} /> Lưu đề cương
        </button>
      </div>
      {isLoading && <p className="muted">Đang tải đề cương…</p>}
      {levels.map((lv) => (
        <label key={lv.key} className="field" style={{ margin: 0 }}>
          <span>{lv.label}</span>
          <textarea
            className="input"
            rows={lv.key === 'proposal' ? 4 : 2}
            value={fields[lv.key] || ''}
            onChange={(e) => setFields({ ...fields, [lv.key]: e.target.value })}
          />
        </label>
      ))}
    </div>
  );
};

// ── 2. Paper Manuscript Panel (/api/paper) ─────────────────────────────────

export const PaperPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { data: paper, isLoading } = useQuery<{
    title: string;
    authors: string;
    style: string;
    venue: string;
    sections: Array<{ id: string; title: string; text: string; state: string; versions: number }>;
    pdf: boolean;
  }>({
    queryKey: ['paper'],
    queryFn: () => api.get('/api/paper'),
  });

  const [selectedSectionId, setSelectedSectionId] = useState('abstract');
  const [sectionText, setSectionText] = useState('');

  const sections = paper?.sections || [];
  const activeSec = sections.find((s) => s.id === selectedSectionId) || sections[0];

  useEffect(() => {
    if (activeSec) {
      setSectionText(activeSec.text || '');
    }
  }, [activeSec?.id, activeSec?.text]);

  const saveSectionMutation = useMutation({
    mutationFn: () =>
      api.put('/api/paper/section', {
        section: activeSec?.id || selectedSectionId,
        text: sectionText,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper'] });
      alert('Đã lưu nội dung mục bài báo!');
    },
  });

  const compileMutation = useMutation({
    mutationFn: () => api.post('/api/paper/compile', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper'] });
      alert('Đã biên dịch PDF thành công!');
    },
    onError: (err: Error) => {
      alert(`Không thể biên dịch LaTeX: ${err.message}`);
    },
  });

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileText size={18} color="var(--accent)" />
          <span>Bản thảo Bài báo LaTeX (Manuscript)</span>
        </h4>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            className="btn sm ghost"
            onClick={() => compileMutation.mutate()}
            disabled={compileMutation.isPending}
          >
            <Play size={13} style={{ marginRight: 4 }} /> Biên dịch PDF
          </button>
          {paper?.pdf && (
            <a
              className="btn sm ghost"
              href="/api/paper/pdf"
              target="_blank"
              rel="noopener noreferrer"
              style={{ textDecoration: 'none' }}
            >
              Xem PDF
            </a>
          )}
        </div>
      </div>

      {isLoading && <p className="muted">Đang tải bản thảo…</p>}

      {sections.length > 0 && (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select
              className="input sm"
              style={{ flex: 1 }}
              value={activeSec?.id || ''}
              onChange={(e) => setSelectedSectionId(e.target.value)}
            >
              {sections.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title} ({s.state || 'trống'} · {s.versions} phiên bản)
                </option>
              ))}
            </select>
            <button
              className="btn sm accent"
              onClick={() => saveSectionMutation.mutate()}
              disabled={saveSectionMutation.isPending}
            >
              <Save size={13} style={{ marginRight: 4 }} /> Lưu Mục
            </button>
          </div>

          <textarea
            className="input"
            rows={14}
            style={{ fontFamily: 'var(--mono)', fontSize: 12.5 }}
            value={sectionText}
            onChange={(e) => setSectionText(e.target.value)}
            placeholder="Nội dung LaTeX của mục này…"
          />
        </>
      )}
    </div>
  );
};

// ── 3. Code & VS Code Panel (/api/code) ────────────────────────────────────

export const CodePanel: React.FC = () => {
  const queryClient = useQueryClient();
  const [newProjectName, setNewProjectName] = useState('');

  const { data: codeData, isLoading } = useQuery<any>({
    queryKey: ['code-projects'],
    queryFn: () => api.get('/api/code'),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post('/api/code', {
        name: newProjectName.trim(),
        description: 'Created from React UI',
        git: true,
        seed: true,
      }),
    onSuccess: () => {
      setNewProjectName('');
      queryClient.invalidateQueries({ queryKey: ['code-projects'] });
    },
  });

  const vscodeMutation = useMutation({
    mutationFn: () => api.post('/api/code/vscode'),
    onError: (err: Error) => alert(`Lỗi mở VS Code: ${err.message}`),
  });

  const projects = codeData?.projects || [];

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Code size={18} color="var(--accent)" />
          <span>Dự án Mã nguồn & VS Code</span>
        </h4>
        <button className="btn sm accent" onClick={() => vscodeMutation.mutate()}>
          <ExternalLink size={13} style={{ marginRight: 4 }} /> Mở trong VS Code
        </button>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (newProjectName.trim()) createMutation.mutate();
        }}
        style={{ display: 'flex', gap: 8 }}
      >
        <input
          className="input sm"
          style={{ flex: 1 }}
          placeholder="Tên repo mã nguồn mới (vd: wavelet-bench)…"
          value={newProjectName}
          onChange={(e) => setNewProjectName(e.target.value)}
        />
        <button type="submit" className="btn sm ghost" disabled={createMutation.isPending}>
          <Plus size={13} style={{ marginRight: 4 }} /> Tạo Repo
        </button>
      </form>

      {isLoading && <p className="muted">Đang tải danh sách dự án code…</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {projects.map((p: any) => (
          <div
            key={p.name}
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 8,
              padding: 10,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <b style={{ fontSize: 13.5 }}>{p.name}</b>
              <div className="muted" style={{ fontSize: 12 }}>{p.path || p.description || 'Python venv + Git'}</div>
            </div>
            {codeData?.active === p.name && (
              <span className="chip ok" style={{ fontSize: 11 }}>Đang mở</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ── 4. Protocols & Experiments Panel (/api/research/topics/{tid}/protocols) ─

export const ProtocolsPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { activeTopicId } = useUIStore();
  const [title, setTitle] = useState('Baseline Wavelet Shrinkage Protocol');
  const [hypothesis, setHypothesis] = useState('Adaptive shrinkage improves PSNR by >= 1.5 dB over fixed threshold');

  const { data: protData } = useQuery<{ protocols: any[] }>({
    queryKey: ['protocols', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/protocols`),
    enabled: !!activeTopicId,
  });

  const { data: expData } = useQuery<{ experiments: any[] }>({
    queryKey: ['experiments', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/experiments`),
    enabled: !!activeTopicId,
  });

  const createProtocolMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/research/topics/${activeTopicId}/protocols`, {
        title,
        hypothesis,
        dataset: { name: 'synthetic_gaussian_1d', split: 'test', seed: 42, n_samples: 64 },
        baseline: { name: 'moving_average', params: { window: 3 } },
        treatment: { name: 'soft_threshold', params: { alphas: [0.05, 0.1, 0.15] } },
        metrics: ['psnr_db', 'mae'],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['protocols', activeTopicId] });
    },
  });

  const approveProtocolMutation = useMutation({
    mutationFn: ({ pid, digest }: { pid: string; digest: string }) =>
      api.post(`/api/research/topics/${activeTopicId}/protocols/${pid}/approve`, {
        digest,
        note: 'Approved via Protocols Panel',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['protocols', activeTopicId] });
    },
  });

  if (!activeTopicId) {
    return (
      <div style={{ padding: 16 }}>
        <p className="muted">Vui lòng chọn Topic để quản lý Protocols & Experiments.</p>
      </div>
    );
  }

  const protocols = protData?.protocols || [];
  const experiments = expData?.experiments || [];

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <FlaskConical size={18} color="var(--accent)" />
          <span>Protocols & Thí nghiệm Có Kiểm soát</span>
        </h4>
        <button className="btn sm accent" onClick={() => createProtocolMutation.mutate()}>
          <Plus size={13} style={{ marginRight: 4 }} /> Tạo Protocol
        </button>
      </div>

      <div style={{ display: 'grid', gap: 6 }}>
        <input className="input sm" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Tên Protocol" />
        <input className="input sm" value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} placeholder="Giả thuyết kiểm định" />
      </div>

      <b style={{ fontSize: 13 }}>Danh sách Protocols ({protocols.length})</b>
      {protocols.map((pr: any) => (
        <div
          key={pr.id}
          style={{
            background: 'var(--panel)',
            border: '1px solid var(--line)',
            borderRadius: 8,
            padding: 10,
            fontSize: 12.5,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <b>{pr.payload?.title || pr.id}</b> (rev {pr.revision})
            <div className="muted" style={{ fontSize: 11.5 }}>digest: {pr.digest?.slice(0, 16)}…</div>
          </div>
          {pr.approval ? (
            <span className="chip ok" style={{ fontSize: 11 }}>
              <CheckCircle2 size={11} style={{ marginRight: 3 }} /> Đã duyệt
            </span>
          ) : (
            <button
              className="btn sm ghost"
              onClick={() => approveProtocolMutation.mutate({ pid: pr.id, digest: pr.digest })}
            >
              Phê duyệt
            </button>
          )}
        </div>
      ))}

      <b style={{ fontSize: 13 }}>Kết quả Thí nghiệm ({experiments.length})</b>
      {experiments.map((ex: any) => (
        <div
          key={ex.id}
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--line-2)',
            borderRadius: 8,
            padding: 10,
            fontSize: 12,
          }}
        >
          <b>Run {ex.id}</b> · Trạng thái: <b>{ex.status}</b>
        </div>
      ))}
    </div>
  );
};
