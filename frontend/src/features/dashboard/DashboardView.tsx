import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';
import {
  Gauge,
  Cpu,
  CheckCircle2,
  Clock,
  RefreshCw,
  Pin,
  Play,
  Trash2,
  Compass,
  Bot,
  MessageSquare,
  Layers,
} from 'lucide-react';

interface DashboardResponse {
  project: string;
  goal: string;
  outline_level: number;
  outline_label: string;
  status: string;
  current?: {
    run: string;
    title: string;
    status: string;
    step: string;
    provider: string;
    progress: string;
  } | null;
  active_runs: Array<Record<string, unknown>>;
  pending: Array<{
    kind: string;
    id: string;
    title: string;
    status: string;
    text: string;
    session_id: string;
  }>;
  next_decision: string;
  pins: Array<{
    id: string;
    title: string;
    status: string;
    summary?: string;
  }>;
  recent_runs: Array<{
    id: string;
    title: string;
    status: string;
    provider?: string;
    done?: number;
    steps?: number;
  }>;
  resources?: {
    cpu_percent?: number;
    ram_used_gb?: number;
    ram_total_gb?: number;
    active_slots?: number;
    max_slots?: number;
  };
  gpus?: Array<{
    index?: number;
    name?: string;
    memory_used_mb?: number;
    memory_total_mb?: number;
    utilization?: number;
  }>;
  local_models?: Record<string, string[]>;
  providers?: Array<{
    id: string;
    name: string;
    status?: string;
    ready?: boolean;
  }>;
}

export const DashboardView: React.FC = () => {
  const queryClient = useQueryClient();
  const { setMainView, open3DOffice, openDrawer, setActiveSessionId } = useUIStore();
  const [unloading, setUnloading] = useState(false);

  const { data: dashboard, isLoading, refetch } = useQuery<DashboardResponse>({
    queryKey: ['dashboard', 'advanced'],
    queryFn: () => api.get<DashboardResponse>('/api/dashboard?advanced=1'),
    refetchInterval: 8000,
  });

  const handleUnloadVram = async () => {
    setUnloading(true);
    try {
      await api.post('/api/models/unload', { engine: 'all', force: true });
      refetch();
    } catch (err) {
      alert(`Không thể giải phóng VRAM: ${(err as Error).message}`);
    } finally {
      setUnloading(false);
    }
  };

  return (
    <div
      style={{
        padding: '24px 28px',
        height: '100%',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        background: 'var(--bg)',
      }}
    >
      {/* Top Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
          paddingBottom: 14,
          borderBottom: '1px solid var(--line)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Gauge size={22} color="var(--accent)" />
            <h2 style={{ margin: 0, fontSize: 20 }}>
              Trung tâm Điều hành Nghiên cứu (OpenScience Dashboard)
            </h2>
          </div>
          <p className="muted" style={{ margin: '4px 0 0', fontSize: 13 }}>
            Dự án: <b>{dashboard?.project || 'Mặc định'}</b> · Trạng thái:{' '}
            <span className="chip ok" style={{ fontSize: 11 }}>
              {dashboard?.status || 'idle'}
            </span>
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw size={14} style={{ marginRight: 5 }} />
            <span>Làm mới</span>
          </button>
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => open3DOffice(true)}
          >
            <Bot size={14} style={{ marginRight: 5 }} />
            <span>Phòng Lab 3D</span>
          </button>
          <button
            type="button"
            className="btn sm accent"
            onClick={() => setMainView('chat')}
          >
            <MessageSquare size={14} style={{ marginRight: 5 }} />
            <span>Quay lại Hội thoại</span>
          </button>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 14,
        }}
      >
        {/* Outline Level */}
        <div
          style={{
            background: 'var(--panel)',
            padding: 16,
            borderRadius: 12,
            border: '1px solid var(--line)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Compass size={17} color="var(--accent)" />
            <b style={{ fontSize: 13 }}>Cấp độ Đề cương (Outline)</b>
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            Cấp {dashboard?.outline_level ?? 0} / 5
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            {dashboard?.outline_label || 'Chưa khởi tạo đề cương'}
          </div>
        </div>

        {/* Pending Approvals */}
        <div
          style={{
            background: 'var(--panel)',
            padding: 16,
            borderRadius: 12,
            border: '1px solid var(--line)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Clock size={17} color="var(--warn)" />
            <b style={{ fontSize: 13 }}>Quyết định Chờ duyệt</b>
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {dashboard?.pending?.length ?? 0}
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            {dashboard?.next_decision || 'Không có yêu cầu chờ duyệt'}
          </div>
        </div>

        {/* Active & Recent Runs */}
        <div
          style={{
            background: 'var(--panel)',
            padding: 16,
            borderRadius: 12,
            border: '1px solid var(--line)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Play size={17} color="#10b981" />
            <b style={{ fontSize: 13 }}>Tiến trình Thực thi (Runs)</b>
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {dashboard?.active_runs?.length ?? 0} đang chạy
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            Tổng lịch sử gần đây: {dashboard?.recent_runs?.length ?? 0} tiến trình
          </div>
        </div>

        {/* Hardware & VRAM */}
        <div
          style={{
            background: 'var(--panel)',
            padding: 16,
            borderRadius: 12,
            border: '1px solid var(--line)',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 8,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Cpu size={17} color="#8b5cf6" />
              <b style={{ fontSize: 13 }}>Phần cứng & GPU VRAM</b>
            </div>
            <button
              type="button"
              className="btn sm ghost"
              onClick={handleUnloadVram}
              disabled={unloading}
              title="Giải phóng các mô hình cục bộ (Ollama / LM Studio) khỏi VRAM"
              style={{ fontSize: 11, padding: '2px 6px' }}
            >
              <Trash2 size={11} style={{ marginRight: 3 }} />
              {unloading ? 'Đang xả…' : 'Xả VRAM'}
            </button>
          </div>
          {dashboard?.gpus && dashboard.gpus.length > 0 ? (
            dashboard.gpus.map((g, idx) => (
              <div key={idx} style={{ fontSize: 12.5 }}>
                <b>{g.name || `GPU #${idx}`}</b>: {g.memory_used_mb} / {g.memory_total_mb} MB
              </div>
            ))
          ) : (
            <div className="muted" style={{ fontSize: 12.5 }}>
              Chế độ CPU / Cloud API (Không phát hiện GPU rời)
            </div>
          )}
        </div>
      </div>

      {/* Research Goal Banner */}
      <div
        style={{
          background: 'var(--panel)',
          border: '1px solid var(--line)',
          borderRadius: 12,
          padding: 16,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <div>
          <b style={{ fontSize: 13.5, display: 'block', marginBottom: 4 }}>
            Mục tiêu Nghiên cứu Trọng tâm (Research Objective)
          </b>
          <div style={{ fontSize: 13.5 }}>
            {dashboard?.goal ||
              'Chưa thiết lập mục tiêu. Hãy mở bảng Đề cương (Outline) hoặc gõ /outline trong khung chat.'}
          </div>
        </div>
        <button
          type="button"
          className="btn sm ghost"
          onClick={() => openDrawer('outline')}
        >
          Mở Đề cương 5 cấp
        </button>
      </div>

      {/* Two-Column Grid: Pending + Runs vs. Pinned Results + Providers */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: 16,
        }}
      >
        {/* Left Column: Pending Decisions & Recent Runs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              padding: 16,
            }}
          >
            <h4 style={{ margin: '0 0 12px', fontSize: 14 }}>
              Hành động Chờ Nhà nghiên cứu Phê duyệt ({dashboard?.pending?.length || 0})
            </h4>
            {dashboard?.pending && dashboard.pending.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {dashboard.pending.map((item, i) => (
                  <div
                    key={item.id || i}
                    style={{
                      background: 'var(--warn-soft)',
                      border: '1px solid var(--warn)',
                      borderRadius: 8,
                      padding: '10px 12px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 10,
                    }}
                  >
                    <div>
                      <b style={{ fontSize: 13 }}>
                        [{item.kind.toUpperCase()}] {item.title}
                      </b>
                      {item.text && (
                        <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                          {item.text}
                        </div>
                      )}
                    </div>
                    {item.session_id && (
                      <button
                        type="button"
                        className="btn sm accent"
                        onClick={() => {
                          setActiveSessionId(item.session_id);
                          setMainView('chat');
                          queryClient.invalidateQueries({ queryKey: ['chat', item.session_id] });
                        }}
                      >
                        Xem & Duyệt
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                Tất cả đề xuất và thực thi đều đã được xử lý.
              </p>
            )}
          </div>

          <div
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              padding: 16,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <h4 style={{ margin: 0, fontSize: 14 }}>Tiến trình Thực thi Gần đây (Runs)</h4>
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => openDrawer('missions')}
              >
                <Layers size={13} style={{ marginRight: 4 }} /> Mở Missions
              </button>
            </div>
            {dashboard?.recent_runs && dashboard.recent_runs.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {dashboard.recent_runs.map((run) => (
                  <div
                    key={run.id}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid var(--line)',
                      background: 'var(--bg)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <b style={{ fontSize: 13 }}>{run.title || run.id}</b>
                      <div className="muted" style={{ fontSize: 11.5 }}>
                        Provider: {run.provider || 'Orchestrator'} · Bước: {run.done ?? 0}/
                        {run.steps ?? 0}
                      </div>
                    </div>
                    <span className="chip" style={{ fontSize: 11 }}>
                      {run.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                Chưa có tiến trình chạy nền nào.
              </p>
            )}
          </div>
        </div>

        {/* Right Column: Pinned Results & Research Engines */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              padding: 16,
            }}
          >
            <h4 style={{ margin: '0 0 12px', fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Pin size={15} color="var(--accent)" />
              <span>Kết quả Nghiên cứu Đã Ghim (Pinned Findings)</span>
            </h4>
            {dashboard?.pins && dashboard.pins.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {dashboard.pins.map((p) => (
                  <div
                    key={p.id}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 8,
                      border: '1px solid var(--line)',
                      background: 'var(--bg)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <b style={{ fontSize: 13 }}>{p.title}</b>
                      <span className="chip ok" style={{ fontSize: 10.5 }}>
                        {p.status}
                      </span>
                    </div>
                    {p.summary && (
                      <p className="muted" style={{ margin: '4px 0 0', fontSize: 12 }}>
                        {p.summary}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                Chưa có kết quả ghim nào. Bạn có thể ghim phát hiện quan trọng từ hội thoại hoặc thí nghiệm.
              </p>
            )}
          </div>

          <div
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 12,
              padding: 16,
            }}
          >
            <h4 style={{ margin: '0 0 12px', fontSize: 14 }}>
              Trạng thái Các Động cơ Nghiên cứu (Research Engines)
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {(dashboard?.providers || []).map((prov) => (
                <div
                  key={prov.id}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--bg)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: 12.5,
                  }}
                >
                  <span>{prov.name || prov.id}</span>
                  <CheckCircle2
                    size={14}
                    color={prov.ready || prov.status === 'ready' ? 'var(--ok)' : 'var(--muted)'}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
