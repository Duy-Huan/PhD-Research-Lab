import React, { useState } from 'react';
import type { MissionTask } from '../../shared/api/types';
import { X, AlertTriangle, FileCheck } from 'lucide-react';

interface TaskInspectorProps {
  task: MissionTask | null;
  onClose: () => void;
}

export const TaskInspector: React.FC<TaskInspectorProps> = ({ task, onClose }) => {
  const [tab, setTab] = useState<'overview' | 'inputs' | 'logs' | 'verification'>('overview');

  if (!task) return null;

  const spec = task.payload.spec;
  const result = task.payload.result;
  const execRecord = task.payload.execution_record;

  return (
    <div
      style={{
        background: 'var(--panel)',
        border: '1px solid var(--line-2)',
        borderRadius: 8,
        padding: 14,
        marginTop: 10,
        boxShadow: 'var(--shadow)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <b style={{ fontSize: 14 }}>Chi tiết nhiệm vụ: {spec.id}</b>
        <button className="icon sm" onClick={onClose}>
          <X size={14} />
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 6, borderBottom: '1px solid var(--line)', paddingBottom: 6, marginBottom: 10 }}>
        <button
          className={`btn sm ${tab === 'overview' ? 'accent' : 'ghost'}`}
          onClick={() => setTab('overview')}
        >
          Tổng quan
        </button>
        <button
          className={`btn sm ${tab === 'inputs' ? 'accent' : 'ghost'}`}
          onClick={() => setTab('inputs')}
        >
          Đầu vào
        </button>
        <button
          className={`btn sm ${tab === 'logs' ? 'accent' : 'ghost'}`}
          onClick={() => setTab('logs')}
        >
          Kết quả / Logs
        </button>
        <button
          className={`btn sm ${tab === 'verification' ? 'accent' : 'ghost'}`}
          onClick={() => setTab('verification')}
        >
          Kiểm thử & Bằng chứng
        </button>
      </div>

      {/* Tab Content */}
      {tab === 'overview' && (
        <div style={{ display: 'grid', gap: 6, fontSize: 13 }}>
          <div>Trạng thái: <b>{task.status.toUpperCase()}</b></div>
          <div>Kỹ năng (Capability): <code>{spec.capability}</code></div>
          <div>Engine thực thi: <code>{result?.engine || spec.preferred_engine || 'deterministic'}</code></div>
          <div>Số lần thử (Attempts): {task.payload.attempts}</div>
          {execRecord && (
            <div>Thời gian chạy: {execRecord.elapsed_seconds != null ? `${execRecord.elapsed_seconds.toFixed(2)}s` : 'N/A'}</div>
          )}
        </div>
      )}

      {tab === 'inputs' && (
        <div style={{ display: 'grid', gap: 6, fontSize: 13 }}>
          <div>Phụ thuộc vào: {spec.depends_on?.join(', ') || 'Không có (chạy đầu tiên)'}</div>
          <div>Tham số (Args):</div>
          <pre style={{ fontSize: 12, background: 'var(--bg)', padding: 8, borderRadius: 6 }}>
            {JSON.stringify(spec.args || spec.arguments || {}, null, 2)}
          </pre>
        </div>
      )}

      {tab === 'logs' && (
        <div style={{ display: 'grid', gap: 6, fontSize: 13 }}>
          {result?.error ? (
            <div style={{ color: 'var(--err)', background: 'var(--err-soft)', padding: 8, borderRadius: 6 }}>
              <AlertTriangle size={14} style={{ display: 'inline', marginRight: 4 }} />
              {result.error}
            </div>
          ) : (
            <pre style={{ fontSize: 12, background: 'var(--bg)', padding: 8, borderRadius: 6, maxHeight: 180, overflowY: 'auto' }}>
              {JSON.stringify(result || 'Không có logs chi tiết', null, 2)}
            </pre>
          )}
        </div>
      )}

      {tab === 'verification' && (
        <div style={{ display: 'grid', gap: 6, fontSize: 13 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <FileCheck size={16} color="var(--accent)" />
            <span>Xác minh độc lập: <b>{execRecord?.verification_status || 'Chưa kiểm định'}</b></span>
          </div>
          <p className="muted" style={{ fontSize: 12 }}>
            Hoàn thành kỹ thuật của một task không đồng nghĩa với xác nhận tính mới hoặc tính hợp lệ của một kết luận khoa học.
          </p>
        </div>
      )}
    </div>
  );
};
