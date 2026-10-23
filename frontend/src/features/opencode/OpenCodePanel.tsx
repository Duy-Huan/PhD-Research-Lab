import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { OpenCodeStatus, OpenCodeSession } from '../../shared/api/types';
import {
  Terminal,
  FolderGit2,
  Play,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  XCircle,
  CheckCircle2,
  Lock,
} from 'lucide-react';

export const OpenCodePanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { activeTopicId } = useUIStore();
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [goal, setGoal] = useState('');
  const [usagePolicy, setUsagePolicy] = useState<'subscription_limited' | 'local_only'>('subscription_limited');
  const [approvalNote, setApprovalNote] = useState('');

  // 1. OpenCode Runtime Health
  const { data: statusData } = useQuery<OpenCodeStatus>({
    queryKey: ['opencode-status'],
    queryFn: () => api.get<OpenCodeStatus>('/api/opencode/status'),
  });

  // 2. Sessions for Active Topic
  const { data: sessionsData, isLoading } = useQuery<{ sessions: OpenCodeSession[] }>({
    queryKey: ['opencode-sessions', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/opencode/sessions`),
    enabled: !!activeTopicId,
  });

  const sessions = sessionsData?.sessions || [];
  const activeSession = sessions.find((s) => s.id === selectedSessionId) || sessions[0] || null;

  // Ensure Topic Workspace
  const workspaceMutation = useMutation({
    mutationFn: () =>
      api.post<{ id: string; path: string }>(`/api/research/topics/${activeTopicId}/opencode/workspace`, {
        enable_bridge_plugin: true,
      }),
    onSuccess: (ws) => {
      alert(`Đã khởi tạo và đồng bộ không gian làm việc cô lập:\n${ws.path}`);
    },
  });

  // Start Session
  const startSessionMutation = useMutation({
    mutationFn: () =>
      api.post<OpenCodeSession>(`/api/research/topics/${activeTopicId}/opencode/sessions`, {
        goal: goal.trim() || 'Analyze repository and implement bounded baseline tests',
        usage_policy: usagePolicy,
        allow_metered_api: false,
        enable_bridge_plugin: true,
      }),
    onSuccess: (sess) => {
      queryClient.invalidateQueries({ queryKey: ['opencode-sessions', activeTopicId] });
      setSelectedSessionId(sess.id);
      setGoal('');
    },
    onError: (err: Error) => {
      alert(`Lỗi khởi chạy phiên OpenCode: ${err.message}`);
    },
  });

  // Reconcile Session
  const reconcileMutation = useMutation({
    mutationFn: (simulateGap: boolean) =>
      api.post(`/api/research/topics/${activeTopicId}/opencode/sessions/${activeSession?.id}/reconcile`, {
        simulate_gap: simulateGap,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['opencode-sessions', activeTopicId] });
    },
  });

  // Cancel Session
  const cancelMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/research/topics/${activeTopicId}/opencode/sessions/${activeSession?.id}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['opencode-sessions', activeTopicId] });
    },
  });

  // Decide Approval
  const decideApprovalMutation = useMutation({
    mutationFn: ({ aid, decision }: { aid: string; decision: 'approve' | 'reject' }) =>
      api.post(`/api/research/topics/${activeTopicId}/opencode/sessions/${activeSession?.id}/approvals/${aid}`, {
        decision,
        note: approvalNote || `Decided (${decision}) via React UI`,
      }),
    onSuccess: () => {
      setApprovalNote('');
      queryClient.invalidateQueries({ queryKey: ['opencode-sessions', activeTopicId] });
    },
  });

  if (!activeTopicId) {
    return (
      <div style={{ padding: 16 }}>
        <p className="muted">Vui lòng chọn một Topic để sử dụng OpenCode Parallel Core (v6.4.1).</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Terminal size={18} color="var(--accent)" />
          <span>OpenCode Parallel Core Runtime (v6.4.1)</span>
        </h4>
        <button
          className="btn sm ghost"
          onClick={() => workspaceMutation.mutate()}
          disabled={workspaceMutation.isPending}
        >
          <FolderGit2 size={14} style={{ marginRight: 4 }} />
          <span>Khởi tạo opencode_prj/</span>
        </button>
      </div>

      {/* Runtime Health & Policy Card */}
      {statusData && (
        <div
          style={{
            background: 'var(--panel)',
            border: '1px solid var(--line)',
            borderRadius: 8,
            padding: 12,
            display: 'grid',
            gap: 6,
            fontSize: 12.5,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b>Trạng thái Runtime: {statusData.state.toUpperCase()}</b>
            <div style={{ display: 'flex', gap: 6 }}>
              <span className="chip ok" style={{ fontSize: 11 }}>
                <Lock size={11} style={{ marginRight: 3 }} /> Loopback Only
              </span>
              <span className="chip" style={{ fontSize: 11 }}>
                Metered API: {statusData.metered_api_allowed ? 'ALLOWED' : 'DISABLED (0$)'}
              </span>
            </div>
          </div>
          <div className="muted" style={{ fontSize: 12 }}>
            Endpoint: <code>{statusData.base_url}</code> · {statusData.detail}
          </div>
          <div className="muted" style={{ fontSize: 11.5 }}>
            Ưu tiên Provider: {statusData.provider_priority?.join(' → ')}
          </div>
        </div>
      )}

      {/* Start Bounded Session Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          startSessionMutation.mutate();
        }}
        style={{
          background: 'var(--bg)',
          border: '1px solid var(--line-2)',
          borderRadius: 8,
          padding: 12,
          display: 'grid',
          gap: 8,
        }}
      >
        <b style={{ fontSize: 13 }}>Giao tác vụ lập trình có ranh giới (OpenCodeTaskSpec)</b>
        <textarea
          className="input"
          rows={2}
          placeholder="Nhập mục tiêu kỹ thuật (vd: Viết unit test kiểm định hàm thu gọn wavelet trong opencode_prj/)…"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          required
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <select
            className="input sm"
            value={usagePolicy}
            onChange={(e) => setUsagePolicy(e.target.value as any)}
          >
            <option value="subscription_limited">Subscription / Free Quota Only (Tự động dừng khi hết hạn mức)</option>
            <option value="local_only">Local Models Only (Ollama / LM Studio)</option>
          </select>
          <button type="submit" className="btn sm accent" disabled={startSessionMutation.isPending}>
            <Play size={13} style={{ marginRight: 4 }} /> Khởi chạy Phiên OpenCode
          </button>
        </div>
      </form>

      {/* Active Session Inspector */}
      {sessions.length > 0 && activeSession && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <select
              className="input sm"
              style={{ flex: 1 }}
              value={activeSession.id}
              onChange={(e) => setSelectedSessionId(e.target.value)}
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} — {s.payload.spec.goal.slice(0, 42)} ({s.status.toUpperCase()})
                </option>
              ))}
            </select>

            <button
              className="btn sm ghost"
              onClick={() => reconcileMutation.mutate(false)}
              disabled={reconcileMutation.isPending}
              title="Đồng bộ trạng thái & artifact từ opencode_prj"
            >
              <RefreshCw size={13} style={{ marginRight: 4 }} /> Đồng bộ
            </button>
            {activeSession.status === 'running' && (
              <button
                className="btn sm ghost"
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
              >
                <XCircle size={13} style={{ marginRight: 4 }} /> Huỷ
              </button>
            )}
          </div>

          {activeSession.payload.blocking_reason && (
            <div style={{ background: 'var(--warn-soft)', border: '1px solid var(--warn)', borderRadius: 8, padding: 10, fontSize: 12.5 }}>
              <AlertTriangle size={14} style={{ display: 'inline', marginRight: 4 }} />
              <b>Tạm dừng an toàn:</b> {activeSession.payload.blocking_reason}
            </div>
          )}

          {/* Pending Approvals */}
          {activeSession.approvals?.filter((a) => a.status === 'pending').map((ap) => (
            <div
              key={ap.id}
              style={{
                background: 'var(--warn-soft)',
                border: '1.5px solid var(--warn)',
                borderRadius: 8,
                padding: 12,
                display: 'grid',
                gap: 8,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <b>Yêu cầu phê duyệt hành động rủi ro ({ap.risk.toUpperCase()})</b>
                <code>{ap.id}</code>
              </div>
              <div style={{ fontSize: 12.5 }}>
                Hành động: <b>{ap.action}</b> · Phạm vi: <code>{ap.payload.scope}</code>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  className="input sm"
                  style={{ flex: 1 }}
                  placeholder="Ghi chú phê duyệt / từ chối…"
                  value={approvalNote}
                  onChange={(e) => setApprovalNote(e.target.value)}
                />
                <button
                  className="btn sm accent"
                  onClick={() => decideApprovalMutation.mutate({ aid: ap.id, decision: 'approve' })}
                >
                  <CheckCircle2 size={13} style={{ marginRight: 4 }} /> Chấp thuận
                </button>
                <button
                  className="btn sm ghost"
                  onClick={() => decideApprovalMutation.mutate({ aid: ap.id, decision: 'reject' })}
                >
                  Từ chối
                </button>
              </div>
            </div>
          ))}

          {/* Deduplicated Event Stream */}
          <div
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: 8,
              padding: 12,
              display: 'grid',
              gap: 6,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <b style={{ fontSize: 13 }}>Luồng sự kiện đã khử trùng lặp SHA-256 ({activeSession.events?.length || 0} events)</b>
              <ShieldCheck size={15} color="var(--ok)" />
            </div>
            <div style={{ maxHeight: 200, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {activeSession.events?.map((ev) => (
                <div
                  key={ev.id}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--line-2)',
                    borderRadius: 6,
                    padding: '6px 10px',
                    fontSize: 12,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>
                      <b>#{ev.seq} {ev.event_type}</b>
                    </span>
                    <span className="muted" style={{ fontFamily: 'var(--mono)', fontSize: 10.5 }}>
                      fp:{ev.fingerprint.slice(0, 10)}
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>
                    {JSON.stringify(ev.payload)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {sessions.length === 0 && !isLoading && (
        <p className="muted" style={{ fontSize: 13 }}>
          Chưa có phiên OpenCode nào trong Topic này.
        </p>
      )}
    </div>
  );
};
