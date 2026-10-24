import React from 'react';
import type { AgentOfficeViewModel } from '../../shared/api/types';
import { Bot, CheckCircle, Clock, Pause, AlertCircle, ShieldAlert, UserCog } from 'lucide-react';

interface AgentStatusListProps {
  agents: AgentOfficeViewModel[];
  onSelectAgent?: (agent: AgentOfficeViewModel) => void;
  onEditProfile?: (agent: AgentOfficeViewModel) => void;
}

export const AgentStatusList: React.FC<AgentStatusListProps> = ({
  agents,
  onSelectAgent,
  onEditProfile,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Serial Scheduler Badge (F08 Remediation) */}
      <div
        style={{
          background: 'var(--code-bg)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          padding: '8px 12px',
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <span className="chip ok" style={{ fontSize: 11, height: 18 }}>
          max_parallel_tasks = 1
        </span>
        <span className="muted">
          Bộ điều phối tuần tự (Serial Scheduler): Tối đa 1 Agent thực thi mã nguồn đồng thời.
        </span>
      </div>

      {/* Agents Roster */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {agents.map((agent) => {
          let badgeClass = 'chip';
          let icon = <Clock size={13} />;

          if (agent.presence === 'running') {
            badgeClass = 'chip ok';
            icon = <Bot size={13} />;
          } else if (agent.presence === 'completed') {
            badgeClass = 'chip ok';
            icon = <CheckCircle size={13} />;
          } else if (agent.presence === 'failed') {
            badgeClass = 'chip err';
            icon = <AlertCircle size={13} />;
          } else if (agent.presence === 'awaiting_approval') {
            badgeClass = 'chip warn';
            icon = <ShieldAlert size={13} />;
          } else if (agent.presence === 'paused') {
            badgeClass = 'chip warn';
            icon = <Pause size={13} />;
          }

          return (
            <div
              key={agent.agentId}
              onClick={() => onSelectAgent?.(agent)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                borderRadius: 8,
                background: 'var(--panel)',
                border: '1px solid var(--line)',
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Bot size={20} color={agent.presence === 'running' ? 'var(--ok)' : 'var(--muted)'} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{agent.displayName}</div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    Vai trò: {agent.role} · Hoạt động: {agent.activity}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {onEditProfile && (
                  <button
                    type="button"
                    className="btn ghost sm"
                    title="Chỉnh sửa hồ sơ & Đặt tên"
                    onClick={(e) => {
                      e.stopPropagation();
                      onEditProfile(agent);
                    }}
                    style={{ padding: '3px 6px', borderRadius: 6 }}
                  >
                    <UserCog size={13} />
                  </button>
                )}
                <span className={badgeClass} style={{ fontSize: 11 }}>
                  {icon}
                  <span style={{ marginLeft: 4 }}>{agent.presence.toUpperCase()}</span>
                </span>
              </div>
            </div>
          );
        })}

        {agents.length === 0 && (
          <p className="muted" style={{ fontSize: 13 }}>
            Không có Agent nào đang hoạt động trong Topic này.
          </p>
        )}
      </div>
    </div>
  );
};
