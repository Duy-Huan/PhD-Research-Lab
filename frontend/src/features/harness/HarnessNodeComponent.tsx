import React from 'react';
import { useI18n } from '../../shared/state/uiStore';
import { Handle, Position } from '@xyflow/react';
import {
  Play,
  Flag,
  Bot,
  Users,
  Cpu,
  Wrench,
  Boxes,
  LogIn,
  LogOut,
  GitBranch,
  Split,
  Merge,
  RefreshCw,
  ShieldCheck,
  Scale,
  FileText,
  Database,
  AlertTriangle,
  Bookmark,
  Gauge,
  CheckSquare,
  Code,
  Award,
  CheckCircle2,
  XCircle,
  Loader2,
  Trash2,
  PauseCircle,
} from 'lucide-react';
import { HarnessNodeData, WorkflowNodeType } from '../../shared/api/types';

interface HarnessNodeComponentProps {
  id: string;
  data: HarnessNodeData;
  selected?: boolean;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  lm_evaluation_harness: <Gauge size={15} color="#3b82f6" />,
  inspect_ai: <ShieldCheck size={15} color="#10b981" />,
  promptfoo: <CheckSquare size={15} color="#f59e0b" />,
  ragas: <Database size={15} color="#8b5cf6" />,
  swe_bench: <Code size={15} color="#ec4899" />,
  pytest_harness: <Cpu size={15} color="#06b6d4" />,
  phdlab_research_harness: <Award size={15} color="#ef4444" />,
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

const NODE_TYPE_INFO: Record<
  string,
  { label: string; color: string; icon: React.ReactNode; bg: string }
> = {
  start: {
    label: 'Bắt đầu',
    color: '#10b981',
    icon: <Play size={15} color="#10b981" />,
    bg: 'rgba(16, 185, 129, 0.08)',
  },
  end: {
    label: 'Kết thúc',
    color: '#8b5cf6',
    icon: <Flag size={15} color="#8b5cf6" />,
    bg: 'rgba(139, 92, 246, 0.08)',
  },
  agent_task: {
    label: 'Agent Task',
    color: '#3b82f6',
    icon: <Bot size={15} color="#3b82f6" />,
    bg: 'rgba(59, 130, 246, 0.08)',
  },
  multi_agent_team: {
    label: 'Multi-Agent',
    color: '#6366f1',
    icon: <Users size={15} color="#6366f1" />,
    bg: 'rgba(99, 102, 241, 0.08)',
  },
  research_engine: {
    label: 'Research Engine',
    color: '#06b6d4',
    icon: <Cpu size={15} color="#06b6d4" />,
    bg: 'rgba(6, 182, 212, 0.08)',
  },
  tool_skill: {
    label: 'Skill Tool',
    color: '#f59e0b',
    icon: <Wrench size={15} color="#f59e0b" />,
    bg: 'rgba(245, 158, 11, 0.08)',
  },
  mcp_tool: {
    label: 'MCP Tool',
    color: '#ec4899',
    icon: <Boxes size={15} color="#ec4899" />,
    bg: 'rgba(236, 72, 153, 0.08)',
  },
  input: {
    label: 'Input Data',
    color: '#64748b',
    icon: <LogIn size={15} color="#64748b" />,
    bg: 'rgba(100, 116, 139, 0.08)',
  },
  output: {
    label: 'Output Result',
    color: '#64748b',
    icon: <LogOut size={15} color="#64748b" />,
    bg: 'rgba(100, 116, 139, 0.08)',
  },
  condition: {
    label: 'Condition (If/Else)',
    color: '#eab308',
    icon: <GitBranch size={15} color="#eab308" />,
    bg: 'rgba(234, 179, 8, 0.08)',
  },
  parallel_branch: {
    label: 'Parallel Branch',
    color: '#3b82f6',
    icon: <Split size={15} color="#3b82f6" />,
    bg: 'rgba(59, 130, 246, 0.08)',
  },
  join: {
    label: 'Join / Merge',
    color: '#3b82f6',
    icon: <Merge size={15} color="#3b82f6" />,
    bg: 'rgba(59, 130, 246, 0.08)',
  },
  bounded_loop: {
    label: 'Bounded Loop',
    color: '#14b8a6',
    icon: <RefreshCw size={15} color="#14b8a6" />,
    bg: 'rgba(20, 184, 166, 0.08)',
  },
  human_approval: {
    label: 'Human Approval',
    color: '#f43f5e',
    icon: <ShieldCheck size={15} color="#f43f5e" />,
    bg: 'rgba(244, 63, 94, 0.08)',
  },
  evaluation_gate: {
    label: 'Eval Gate',
    color: '#10b981',
    icon: <Scale size={15} color="#10b981" />,
    bg: 'rgba(16, 185, 129, 0.08)',
  },
  artifact_transformation: {
    label: 'Transformation',
    color: '#8b5cf6',
    icon: <FileText size={15} color="#8b5cf6" />,
    bg: 'rgba(139, 92, 246, 0.08)',
  },
  memory_read: {
    label: 'Memory Read',
    color: '#a855f7',
    icon: <Database size={15} color="#a855f7" />,
    bg: 'rgba(168, 85, 247, 0.08)',
  },
  memory_write: {
    label: 'Memory Write',
    color: '#a855f7',
    icon: <Database size={15} color="#a855f7" />,
    bg: 'rgba(168, 85, 247, 0.08)',
  },
  error_handler: {
    label: 'Error Handler',
    color: '#ef4444',
    icon: <AlertTriangle size={15} color="#ef4444" />,
    bg: 'rgba(239, 68, 68, 0.08)',
  },
  checkpoint: {
    label: 'Checkpoint',
    color: '#f97316',
    icon: <Bookmark size={15} color="#f97316" />,
    bg: 'rgba(249, 115, 22, 0.08)',
  },
};

export const HarnessNodeComponent: React.FC<HarnessNodeComponentProps> = ({ id, data, selected }) => {
  const { t } = useI18n();
  const nodeType: WorkflowNodeType = (data.node_type as WorkflowNodeType) || (data.tool ? 'harnessNode' : 'agent_task');
  const status = data.status || 'idle';

  // Determine display label and icon
  const isBenchmark = nodeType === 'harnessNode' || Boolean(data.tool && TOOL_NAMES[data.tool]);
  const typeMeta = NODE_TYPE_INFO[nodeType] || {
    label: isBenchmark ? (TOOL_NAMES[data.tool || ''] || data.tool || 'Benchmark') : nodeType,
    color: 'var(--accent)',
    icon: isBenchmark ? (TOOL_ICONS[data.tool || ''] || <Gauge size={15} color="var(--accent)" />) : <Bot size={15} color="var(--accent)" />,
    bg: 'var(--panel)',
  };

  const badgeTitle = isBenchmark
    ? TOOL_NAMES[data.tool || ''] || data.tool || 'Harness'
    : typeMeta.label;

  const nodeIcon = isBenchmark
    ? TOOL_ICONS[data.tool || ''] || <Gauge size={15} color="var(--accent)" />
    : typeMeta.icon;

  // Status visual states
  let statusBorder = selected ? 'var(--accent)' : 'var(--line)';
  let statusBg = 'var(--panel)';
  let statusBadge = (
    <span style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--muted)' }} />
      {t('Chưa chạy', 'Not executed')}
    </span>
  );

  if (status === 'running') {
    statusBorder = 'var(--accent)';
    statusBg = 'var(--bg-2)';
    statusBadge = (
      <span style={{ fontSize: 10, color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 600 }}>
        <Loader2 size={11} className="spin" />
        {t('Đang chạy…', 'Running…')}
      </span>
    );
  } else if (status === 'completed') {
    statusBorder = 'var(--ok, #10b981)';
    statusBg = 'rgba(16, 185, 129, 0.04)';
    statusBadge = (
      <span style={{ fontSize: 10, color: 'var(--ok, #10b981)', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 600 }}>
        <CheckCircle2 size={11} />
        {t('Hoàn tất bước', 'Step completed')}
      </span>
    );
  } else if (status === 'failed') {
    statusBorder = 'var(--err, #ef4444)';
    statusBg = 'rgba(239, 68, 68, 0.05)';
    statusBadge = (
      <span style={{ fontSize: 10, color: 'var(--err, #ef4444)', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 600 }}>
        <XCircle size={11} />
        {t('Thất bại', 'Failed')}
      </span>
    );
  } else if (status === 'waiting_approval') {
    statusBorder = '#f43f5e';
    statusBg = 'rgba(244, 63, 94, 0.06)';
    statusBadge = (
      <span style={{ fontSize: 10, color: '#f43f5e', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 600 }}>
        <ShieldCheck size={11} />
        {t('Chờ duyệt', 'Awaiting approval')}
      </span>
    );
  } else if (status === 'paused') {
    statusBorder = '#f59e0b';
    statusBg = 'rgba(245, 158, 11, 0.05)';
    statusBadge = (
      <span style={{ fontSize: 10, color: '#f59e0b', display: 'flex', alignItems: 'center', gap: 3, fontWeight: 600 }}>
        <PauseCircle size={11} />
        {t('Tạm dừng', 'Paused')}
      </span>
    );
  } else if (['blocked', 'unsupported', 'unavailable', 'unverified', 'error', 'skipped'].includes(status)) {
    statusBorder = 'var(--warn, #f59e0b)';
    statusBadge = <span role="status" style={{ fontSize: 10, color: 'var(--warn, #f59e0b)' }}>{status.toUpperCase()}</span>;
  }

  // Engine or Model Subtitle
  const engineOrRole =
    (data.config?.engine as string) ||
    (data.config?.agent_role as string) ||
    (data.config?.provider as string) ||
    (data.params?.engine as string) ||
    '';

  const metricSummary = data.result?.metrics
    ? Object.entries(data.result.metrics)
        .slice(0, 2)
        .map(([k, v]) => `${k}: ${typeof v === 'number' ? (v <= 1 && v > 0 ? `${Math.round(v * 100)}%` : v) : v}`)
        .join(' · ')
    : null;

  return (
    <div
      style={{
        width: 230,
        background: statusBg,
        borderLeft: `1.5px solid ${statusBorder}`,
        borderRight: `1.5px solid ${statusBorder}`,
        borderBottom: `1.5px solid ${statusBorder}`,
        borderTop: `3px solid ${typeMeta.color}`,
        borderRadius: 8,
        padding: '9px 12px',
        boxShadow: selected ? '0 0 0 2px var(--accent-soft, rgba(185, 75, 28, 0.25))' : '0 2px 7px rgba(0,0,0,0.06)',
        color: 'var(--ink)',
        fontSize: 12,
        cursor: 'grab',
        position: 'relative',
        transition: 'all 0.15s ease',
      }}
    >
      {/* ----------------- Specific Input Handles ----------------- */}
      {nodeType !== 'start' && nodeType !== 'input' && (
        <>
          {nodeType === 'bounded_loop' ? (
            <>
              {/* Loop body in (Top) */}
              <Handle
                type="target"
                id="loop_in"
                position={Position.Top}
                style={{
                  width: 9,
                  height: 9,
                  background: '#14b8a6',
                  border: '2px solid var(--panel)',
                }}
                title="Loop Back In"
              />
              {/* Primary In (Left) */}
              <Handle
                type="target"
                id="in"
                position={Position.Left}
                style={{
                  width: 9,
                  height: 9,
                  background: typeMeta.color,
                  border: '2px solid var(--panel)',
                }}
              />
            </>
          ) : nodeType === 'join' ? (
            <>
              <Handle
                type="target"
                id="in_1"
                position={Position.Left}
                style={{ top: '25%', width: 8, height: 8, background: typeMeta.color, border: '2px solid var(--panel)' }}
                title="Branch 1"
              />
              <Handle
                type="target"
                id="in_2"
                position={Position.Left}
                style={{ top: '50%', width: 8, height: 8, background: typeMeta.color, border: '2px solid var(--panel)' }}
                title="Branch 2"
              />
              <Handle
                type="target"
                id="in_3"
                position={Position.Left}
                style={{ top: '75%', width: 8, height: 8, background: typeMeta.color, border: '2px solid var(--panel)' }}
                title="Branch 3"
              />
            </>
          ) : (
            <Handle
              type="target"
              id="in"
              position={Position.Left}
              style={{
                width: 9,
                height: 9,
                background: typeMeta.color,
                border: '2px solid var(--panel)',
              }}
            />
          )}
        </>
      )}

      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, overflow: 'hidden' }}>
          {nodeIcon}
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: typeMeta.color,
              textTransform: 'uppercase',
              letterSpacing: 0.5,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: 160,
            }}
          >
            {badgeTitle}
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
            style={{ padding: 2, color: 'var(--muted)', border: 'none', background: 'transparent', cursor: 'pointer' }}
          >
            <Trash2 size={12} />
          </button>
        )}
      </div>

      {/* Node Title */}
      <div
        style={{
          fontWeight: 600,
          fontSize: 12.5,
          marginBottom: 3,
          lineHeight: 1.35,
          color: 'var(--ink)',
          wordBreak: 'break-word',
        }}
      >
        {data.label || 'Tác vụ nghiên cứu'}
      </div>

      {/* Engine / Subtitle if present */}
      {engineOrRole && (
        <div
          style={{
            fontSize: 10,
            color: 'var(--muted)',
            marginBottom: 4,
            textTransform: 'capitalize',
            fontFamily: 'var(--mono)',
          }}
        >
          {engineOrRole}
        </div>
      )}

      {/* Status & Duration row */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 6,
          paddingTop: 5,
          borderTop: '1px solid var(--line-2)',
        }}
      >
        {statusBadge}
        {data.result?.duration_s !== undefined && (
          <span style={{ fontSize: 10, color: 'var(--muted)' }}>
            {data.result.duration_s}s
          </span>
        )}
      </div>

      {/* Metrics display */}
      {metricSummary && (
        <div
          style={{
            marginTop: 4,
            fontSize: 10,
            fontFamily: 'var(--mono)',
            color: 'var(--accent)',
            background: 'var(--bg)',
            padding: '2px 5px',
            borderRadius: 4,
          }}
        >
          {metricSummary}
        </div>
      )}

      {/* ----------------- Specific Output Handles ----------------- */}
      {nodeType !== 'end' && nodeType !== 'output' && (
        <>
          {nodeType === 'condition' ? (
            <>
              {/* True handle */}
              <div
                style={{
                  position: 'absolute',
                  right: 4,
                  top: '25%',
                  fontSize: 9,
                  fontWeight: 700,
                  color: '#10b981',
                }}
              >
                T
              </div>
              <Handle
                type="source"
                id="true"
                position={Position.Right}
                style={{ top: '25%', width: 8, height: 8, background: '#10b981', border: '2px solid var(--panel)' }}
                title="True Branch"
              />
              {/* False handle */}
              <div
                style={{
                  position: 'absolute',
                  right: 4,
                  top: '75%',
                  fontSize: 9,
                  fontWeight: 700,
                  color: '#ef4444',
                }}
              >
                F
              </div>
              <Handle
                type="source"
                id="false"
                position={Position.Right}
                style={{ top: '75%', width: 8, height: 8, background: '#ef4444', border: '2px solid var(--panel)' }}
                title="False Branch"
              />
            </>
          ) : nodeType === 'human_approval' ? (
            <>
              <div style={{ position: 'absolute', right: 4, top: '28%', fontSize: 9, fontWeight: 700, color: '#10b981' }}>
                ✓
              </div>
              <Handle
                type="source"
                id="approved"
                position={Position.Right}
                style={{ top: '30%', width: 8, height: 8, background: '#10b981', border: '2px solid var(--panel)' }}
                title="Approved"
              />
              <div style={{ position: 'absolute', right: 4, top: '70%', fontSize: 9, fontWeight: 700, color: '#ef4444' }}>
                ✕
              </div>
              <Handle
                type="source"
                id="rejected"
                position={Position.Right}
                style={{ top: '72%', width: 8, height: 8, background: '#ef4444', border: '2px solid var(--panel)' }}
                title="Rejected"
              />
            </>
          ) : nodeType === 'bounded_loop' ? (
            <>
              <div style={{ position: 'absolute', right: 4, top: '28%', fontSize: 9, fontWeight: 700, color: '#14b8a6' }}>
                ⟳
              </div>
              <Handle
                type="source"
                id="loop_out"
                position={Position.Right}
                style={{ top: '30%', width: 8, height: 8, background: '#14b8a6', border: '2px solid var(--panel)' }}
                title="Loop Body"
              />
              <div style={{ position: 'absolute', right: 4, top: '70%', fontSize: 9, fontWeight: 700, color: '#8b5cf6' }}>
                ✓
              </div>
              <Handle
                type="source"
                id="done"
                position={Position.Right}
                style={{ top: '72%', width: 8, height: 8, background: '#8b5cf6', border: '2px solid var(--panel)' }}
                title="Loop Completed"
              />
            </>
          ) : nodeType === 'parallel_branch' ? (
            <>
              <Handle
                type="source"
                id="branch_1"
                position={Position.Right}
                style={{ top: '25%', width: 8, height: 8, background: typeMeta.color, border: '2px solid var(--panel)' }}
                title="Branch 1"
              />
              <Handle
                type="source"
                id="branch_2"
                position={Position.Right}
                style={{ top: '50%', width: 8, height: 8, background: typeMeta.color, border: '2px solid var(--panel)' }}
                title="Branch 2"
              />
              <Handle
                type="source"
                id="branch_3"
                position={Position.Right}
                style={{ top: '75%', width: 8, height: 8, background: typeMeta.color, border: '2px solid var(--panel)' }}
                title="Branch 3"
              />
            </>
          ) : (
            <Handle
              type="source"
              id="out"
              position={Position.Right}
              style={{
                width: 9,
                height: 9,
                background: typeMeta.color,
                border: '2px solid var(--panel)',
              }}
            />
          )}
        </>
      )}
    </div>
  );
};
