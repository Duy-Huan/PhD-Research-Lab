import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { Mission, WorkstreamView } from '../../shared/api/types';
import { GitBranch, AlertCircle, CheckCircle2, ArrowRight, RefreshCw, KeyRound } from 'lucide-react';

export const WorkstreamMonitor: React.FC = () => {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const { activeTopicId } = useUIStore();
  const [selectedMissionId, setSelectedMissionId] = useState<string | null>(null);

  // CAS Output state
  const [casKey, setCasKey] = useState('');
  const [casRevision, setCasRevision] = useState<number>(0);
  const [casOpen, setCasOpen] = useState(false);
  const [casConflict, setCasConflict] = useState<string | null>(null);

  // Dispute resolution state
  const [selectedDispute, setSelectedDispute] = useState<{ id: string; revision: number } | null>(null);
  const [disputeNote, setDisputeNote] = useState('');

  // 1. Fetch missions for active topic
  const { data: missionsData, isLoading: missionsLoading } = useQuery<{ missions: Mission[] }>({
    queryKey: ['missions', activeTopicId],
    queryFn: () => api.get<{ missions: Mission[] }>(`/api/research/topics/${activeTopicId}/missions`),
    enabled: !!activeTopicId,
  });

  const missions = missionsData?.missions?.filter((m) => m.payload.spec.collaboration) || [];

  // F05 Remediation: Lazy fetch workstreams for the selected mission only
  const activeMid = selectedMissionId || (missions[0]?.id ?? null);

  const { data: workstreamData, isLoading: wsLoading } = useQuery<WorkstreamView>({
    queryKey: ['workstreams', activeTopicId, activeMid],
    queryFn: () =>
      api.get<WorkstreamView>(`/api/research/topics/${activeTopicId}/missions/${activeMid}/workstreams`),
    enabled: !!activeTopicId && !!activeMid,
  });

  // F03 Remediation: Register canonical output with dynamic expected_revision
  const casMutation = useMutation({
    mutationFn: async ({
      key,
      expectedRevision,
      teamId,
      sourceTask,
      note,
    }: {
      key: string;
      expectedRevision: number;
      teamId: string;
      sourceTask: string;
      note: string;
    }) => {
      setCasConflict(null);
      return api.post(`/api/research/topics/${activeTopicId}/missions/${activeMid}/outputs`, {
        key,
        expected_revision: expectedRevision,
        team_id: teamId,
        source_task: sourceTask,
        artifact_index: 0,
        note,
      });
    },
    onSuccess: () => {
      setCasOpen(false);
      setCasKey('');
      queryClient.invalidateQueries({ queryKey: ['workstreams', activeTopicId, activeMid] });
    },
    onError: (err: any) => {
      if (err.status === 409 || err.code === 'CONFLICT') {
        setCasConflict(t('Xung đột phiên bản: Kết quả đã được cập nhật bởi tiến trình khác. Vui lòng kiểm tra lại phiên bản mới nhất.', 'Version conflict: Output has been updated by another process. Please check the latest version.'));
      } else {
        alert(`Lỗi lưu output: ${err.message}`);
      }
    },
  });

  // Dispute resolution mutation
  const resolveDisputeMutation = useMutation({
    mutationFn: async ({ did, expectedRevision, note }: { did: string; expectedRevision: number; note: string }) => {
      return api.post(`/api/research/topics/${activeTopicId}/missions/${activeMid}/disputes/${did}/resolve`, {
        expected_revision: expectedRevision,
        note,
      });
    },
    onSuccess: () => {
      setSelectedDispute(null);
      setDisputeNote('');
      queryClient.invalidateQueries({ queryKey: ['workstreams', activeTopicId, activeMid] });
    },
  });

  if (!activeTopicId) {
    return (
      <div style={{ padding: 16 }}>
        <p className="muted">Vui lòng chọn một Topic để xem phân luồng Workstreams.</p>
      </div>
    );
  }

  const selectedMission = missions.find((m) => m.id === activeMid);
  const workstreams = selectedMission?.payload.spec.collaboration?.workstreams || [];

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <GitBranch size={18} color="var(--accent)" />
          <span>Phân luồng & Handoffs (Workstreams)</span>
        </h4>
        <button
          className="btn sm ghost"
          onClick={() => queryClient.invalidateQueries({ queryKey: ['workstreams', activeTopicId, activeMid] })}
        >
          <RefreshCw size={13} style={{ marginRight: 4 }} /> Làm mới
        </button>
      </div>

      <p className="muted" style={{ fontSize: 13, margin: 0 }}>
        Mỗi workstream là một nhóm nhiệm vụ logic. Handoffs tự động truyền dữ liệu kiểm thử; các tranh chấp (disputes) yêu cầu quyết định rõ ràng từ nhà nghiên cứu.
      </p>

      {/* Mission Selector */}
      {missions.length > 0 ? (
        <label className="field" style={{ margin: 0 }}>
          <span>Chọn Mission cộng tác</span>
          <select
            className="input"
            value={activeMid || ''}
            onChange={(e) => setSelectedMissionId(e.target.value)}
          >
            {missions.map((m) => (
              <option key={m.id} value={m.id}>
                {m.payload.spec.objective} ({m.status})
              </option>
            ))}
          </select>
        </label>
      ) : (
        <p className="muted" style={{ fontSize: 13 }}>
          Không có Mission cộng tác multi-team nào trong Topic này.
        </p>
      )}

      {/* Swimlane Cards */}
      {workstreams.length > 0 && (
        <div style={{ display: 'grid', gap: 8 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--muted)' }}>
            Các phân luồng công việc (Swimlanes):
          </span>
          {workstreams.map((ws) => (
            <div
              key={ws.id}
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--line)',
                borderRadius: 8,
                padding: '10px 12px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <b style={{ fontSize: 13.5 }}>{ws.id} · {ws.objective}</b>
                <span className="chip" style={{ fontSize: 11 }}>Vai trò: {ws.lead_role}</span>
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                Nhiệm vụ: {ws.task_ids?.join(', ') || 'Chưa gán nhiệm vụ'}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Handoffs & Receipts (F02 Display) */}
      {workstreamData && (
        <div style={{ display: 'grid', gap: 8 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--muted)' }}>
            Handoffs & Biên lai nhận ({workstreamData.messages?.length || 0} bàn giao, {workstreamData.receipts?.length || 0} đã nhận):
          </span>
          <div style={{ maxHeight: 150, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(workstreamData.messages || []).map((msg) => {
              const ack = (workstreamData.receipts || []).find((r) => r.handoff_id === msg.id);
              return (
                <div
                  key={msg.id}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--line-2)',
                    borderRadius: 6,
                    padding: '8px 10px',
                    fontSize: 12.5,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>{msg.source_workstream}</span>
                    <ArrowRight size={13} color="var(--muted)" />
                    <span>{msg.target_workstream}</span>
                    <span className="muted">({msg.task_id})</span>
                  </div>
                  <div>
                    {ack ? (
                      <span className="chip ok" style={{ fontSize: 11, height: 18 }}>
                        <CheckCircle2 size={11} style={{ marginRight: 2 }} /> Đã xác nhận
                      </span>
                    ) : (
                      <span className="chip warn" style={{ fontSize: 11, height: 18 }}>
                        Đang chờ
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
            {(!workstreamData.messages || workstreamData.messages.length === 0) && (
              <p className="muted" style={{ fontSize: 12 }}>Chưa có sự kiện bàn giao handoff nào.</p>
            )}
          </div>
        </div>
      )}

      {/* Disputes Inbox (F02) */}
      {workstreamData && (workstreamData.disputes || []).length > 0 && (
        <div style={{ display: 'grid', gap: 8 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--err)' }}>
            Tranh chấp đang mở (Disputes):
          </span>
          {workstreamData.disputes.map((d) => (
            <div
              key={d.id}
              style={{
                background: 'var(--err-soft)',
                border: '1px solid var(--err)',
                borderRadius: 8,
                padding: 10,
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--err)' }}>
                {d.payload.reason}
              </div>
              <div style={{ fontSize: 12, marginTop: 4 }}>
                Trạng thái: <b>{d.status}</b> · Phiên bản: {d.revision}
              </div>
              {d.status === 'open' && (
                <button
                  className="btn sm accent"
                  style={{ marginTop: 8 }}
                  onClick={() => setSelectedDispute({ id: d.id, revision: d.revision })}
                >
                  Giải quyết với ghi chú của PI
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Dispute Resolution Modal */}
      {selectedDispute && (
        <div
          style={{
            background: 'var(--panel)',
            border: '1px solid var(--accent)',
            borderRadius: 8,
            padding: 12,
            display: 'grid',
            gap: 8,
          }}
        >
          <b>Giải quyết tranh chấp {selectedDispute.id}</b>
          <p className="muted" style={{ fontSize: 12, margin: 0 }}>
            Lưu ý: Giải quyết tranh chấp ghi nhận quyết định nhân lực, không tự động xác nhận một kết luận khoa học.
          </p>
          <textarea
            className="input"
            value={disputeNote}
            onChange={(e) => setDisputeNote(e.target.value)}
            placeholder="Ghi chú quyết định xử lý tranh chấp…"
            rows={2}
          />
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
            <button className="btn sm ghost" onClick={() => setSelectedDispute(null)}>
              Huỷ
            </button>
            <button
              className="btn sm accent"
              onClick={() =>
                resolveDisputeMutation.mutate({
                  did: selectedDispute.id,
                  expectedRevision: selectedDispute.revision,
                  note: disputeNote,
                })
              }
              disabled={!disputeNote.trim() || resolveDisputeMutation.isPending}
            >
              Xác nhận giải quyết
            </button>
          </div>
        </div>
      )}

      {/* Canonical Output CAS Registration (F03 Fix) */}
      <div style={{ borderTop: '1px solid var(--line)', paddingTop: 12 }}>
        <button
          className="btn sm accent"
          onClick={() => {
            setCasConflict(null);
            setCasOpen(true);
          }}
        >
          <KeyRound size={14} style={{ marginRight: 4 }} />
          Đăng ký Canonical Output (Compare-and-Swap)
        </button>

        {casOpen && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const owner = workstreams[0]?.id || '';
              const firstTask = workstreams[0]?.task_ids?.[0] || 'report';
              casMutation.mutate({
                key: casKey.trim(),
                expectedRevision: casRevision,
                teamId: owner,
                sourceTask: firstTask,
                note: 'Registered from React UI',
              });
            }}
            style={{
              marginTop: 10,
              background: 'var(--bg)',
              border: '1px solid var(--line-2)',
              borderRadius: 8,
              padding: 12,
              display: 'grid',
              gap: 8,
            }}
          >
            <b>Đăng ký Canonical Output mới</b>
            {casConflict && (
              <div style={{ color: 'var(--err)', fontSize: 12.5, background: 'var(--err-soft)', padding: 6, borderRadius: 6 }}>
                <AlertCircle size={14} style={{ display: 'inline', marginRight: 4 }} />
                {casConflict}
              </div>
            )}
            <label className="field" style={{ margin: 0 }}>
              <span>Output Key</span>
              <input
                className="input"
                value={casKey}
                onChange={(e) => {
                  setCasKey(e.target.value);
                  // Dynamic revision lookup
                  const existing = workstreamData?.canonical_outputs?.[e.target.value.trim()];
                  setCasRevision(existing ? existing.revision : 0);
                }}
                placeholder="vd: research-report"
                required
              />
            </label>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              Phiên bản kỳ vọng (Expected revision): <b>{casRevision}</b>
            </div>
            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
              <button className="btn sm ghost" type="button" onClick={() => setCasOpen(false)}>
                Huỷ
              </button>
              <button className="btn sm accent" type="submit" disabled={casMutation.isPending || !casKey.trim()}>
                Gửi CAS
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
