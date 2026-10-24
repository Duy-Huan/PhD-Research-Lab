import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { MissionTask } from '../../shared/api/types';

interface MissionDAGProps {
  tasks: MissionTask[];
  onSelectTask?: (taskId: string) => void;
}

export const MissionDAG: React.FC<MissionDAGProps> = ({ tasks, onSelectTask }) => {
  // Construct nodes and edges from tasks
  const { nodes, edges } = useMemo(() => {
    const n: Node[] = [];
    const e: Edge[] = [];

    // Simple horizontal/grid layout
    tasks.forEach((t, index) => {
      const spec = t.payload.spec;
      let bgColor = 'var(--panel)';
      let borderColor = 'var(--line)';

      if (t.status === 'running') {
        bgColor = 'var(--ok-soft)';
        borderColor = 'var(--ok)';
      } else if (t.status === 'completed') {
        bgColor = 'var(--code-bg)';
        borderColor = 'var(--line-2)';
      } else if (t.status === 'failed') {
        bgColor = 'var(--err-soft)';
        borderColor = 'var(--err)';
      } else if (t.status === 'interrupted') {
        bgColor = 'var(--warn-soft)';
        borderColor = 'var(--warn)';
      }

      n.push({
        id: t.id,
        position: { x: (index % 3) * 220, y: Math.floor(index / 3) * 120 },
        data: {
          label: (
            <div
              style={{
                padding: '8px 10px',
                borderRadius: 8,
                fontSize: 12,
                cursor: 'pointer',
              }}
              onClick={() => onSelectTask?.(t.id)}
            >
              <b>{spec.id}</b>
              <div style={{ color: 'var(--muted)', fontSize: 11 }}>{spec.capability}</div>
              <div style={{ marginTop: 4, fontWeight: 600 }}>{t.status.toUpperCase()}</div>
            </div>
          ),
        },
        style: {
          background: bgColor,
          border: `1.5px solid ${borderColor}`,
          borderRadius: 8,
          width: 180,
          color: 'var(--ink)',
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      });

      // Dependency edges
      if (spec.depends_on) {
        spec.depends_on.forEach((dep) => {
          e.push({
            id: `${dep}->${t.id}`,
            source: dep,
            target: t.id,
            animated: t.status === 'running',
            style: { stroke: 'var(--line-2)', strokeWidth: 2 },
          });
        });
      }
    });

    return { nodes: n, edges: e };
  }, [tasks, onSelectTask]);

  return (
    <div style={{ width: '100%', height: 320, background: 'var(--bg)', borderRadius: 8, border: '1px solid var(--line)' }}>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background color="var(--line-2)" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
};
