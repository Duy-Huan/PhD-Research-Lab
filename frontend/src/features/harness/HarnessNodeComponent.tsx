import React from 'react';
import { Handle, Position } from '@xyflow/react';
import {
  Gauge,
  ShieldCheck,
  CheckSquare,
  Database,
  Code,
  Cpu,
  Award,
  CheckCircle2,
  XCircle,
  Loader2,
  Trash2,
} from 'lucide-react';
import { HarnessNodeData } from '../../shared/api/types';

interface HarnessNodeComponentProps {
  id: string;
  data: HarnessNodeData;
  selected?: boolean;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  lm_evaluation_harness: <Gauge size={16} color="#3b82f6" />,
  inspect_ai: <ShieldCheck size={16} color="#10b981" />,
  promptfoo: <CheckSquare size={16} color="#f59e0b" />,
  ragas: <Database size={16} color="#8b5cf6" />,
  swe_bench: <Code size={16} color="#ec4899" />,
  pytest_harness: <Cpu size={16} color="#06b6d4" />,
  phdlab_research_harness: <Award size={16} color="#ef4444" />,
};

const TOOL_NAMES: Record<string, string> = {
  lm_evaluation_harness: 'LM-Evaluation-Harness',
  inspect_ai: 'Inspect AI',
  promptfoo: 'Promptfoo',
  ragas: 'Ragas',
  swe_bench: 'SWE-Bench',
  pytest_harness: 'Pytest Harness',
  phdlab_research_harness: 'PhDLab Research Harness',
};

export const HarnessNodeComponent: React.FC<HarnessNodeComponentProps> = ({ id, data, selected }) => {
  const status = data.status || 'idle';
  const toolName = TOOL_NAMES[data.tool] || data.tool;
  const icon = TOOL_ICONS[data.tool] || <Cpu size={16} color="var(--accent)" />;

  let statusBorder = 'var(--line)';
  let statusBg = 'var(--panel)';
  let statusBadge = (
    <span style={{ fontSize: 10.5, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--muted)' }} />
      Sẵn sàng
    </span>
  );

  if (status === 'running') {
    statusBorder = 'var(--accent)';
    statusBg = 'var(--bg-2)';
    statusBadge = (
      <span style={{ fontSize: 10.5, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 600 }}>
        <Loader2 size={11} className="spin" />
        Đang chạy…
      </span>
    );
  } else if (status === 'completed') {
    statusBorder = 'var(--ok, #10b981)';
    statusBg = 'rgba(16, 185, 129, 0.05)';
    statusBadge = (
      <span style={{ fontSize: 10.5, color: 'var(--ok, #10b981)', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 600 }}>
        <CheckCircle2 size={11} />
        Thành công
      </span>
    );
  } else if (status === 'failed') {
    statusBorder = 'var(--err, #ef4444)';
    statusBg = 'rgba(239, 68, 68, 0.06)';
    statusBadge = (
      <span style={{ fontSize: 10.5, color: 'var(--err, #ef4444)', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 600 }}>
        <XCircle size={11} />
        Không đạt
      </span>
    );
  }

  const metricSummary = data.result?.metrics
    ? Object.entries(data.result.metrics)
        .slice(0, 2)
        .map(([k, v]) => `${k}: ${typeof v === 'number' ? (v <= 1 && v > 0 ? `${Math.round(v * 100)}%` : v) : v}`)
        .join(' · ')
    : null;

  return (
    <div
      style={{
        width: 220,
        background: statusBg,
        border: `1.5px solid ${selected ? 'var(--accent)' : statusBorder}`,
        borderRadius: 10,
        padding: '10px 12px',
        boxShadow: selected ? '0 0 0 2px var(--accent-soft, rgba(185, 75, 28, 0.2))' : '0 2px 6px rgba(0,0,0,0.06)',
        color: 'var(--ink)',
        fontSize: 12,
        cursor: 'grab',
        position: 'relative',
        transition: 'all 0.15s ease',
      }}
    >
      {/* Target input handle (Left) */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          width: 9,
          height: 9,
          background: 'var(--accent)',
          border: '2px solid var(--panel)',
        }}
      />

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {icon}
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            {toolName}
          </span>
        </div>
        {typeof data.onDelete === 'function' && (
          <button
            type="button"
            className="icon xs"
            onClick={(e) => {
              e.stopPropagation();
              (data.onDelete as (nid: string) => void)(id);
            }}
            title="Xóa node"
            style={{ padding: 2, color: 'var(--muted)', border: 'none', background: 'transparent' }}
          >
            <Trash2 size={12} />
          </button>
        )}
      </div>

      {/* Node Title */}
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4, lineHeight: 1.3 }}>
        {data.label || 'Quy trình kiểm thử'}
      </div>

      {/* Status & Metrics */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, paddingTop: 6, borderTop: '1px solid var(--line-2)' }}>
        {statusBadge}
        {data.result?.duration_s !== undefined && (
          <span style={{ fontSize: 10, color: 'var(--muted)' }}>
            {data.result.duration_s}s
          </span>
        )}
      </div>

      {metricSummary && (
        <div style={{ marginTop: 4, fontSize: 10.5, fontFamily: 'var(--mono)', color: 'var(--accent)', background: 'var(--bg)', padding: '2px 5px', borderRadius: 4 }}>
          {metricSummary}
        </div>
      )}

      {/* Source output handle (Right) */}
      <Handle
        type="source"
        position={Position.Right}
        style={{
          width: 9,
          height: 9,
          background: 'var(--accent)',
          border: '2px solid var(--panel)',
        }}
      />
    </div>
  );
};
