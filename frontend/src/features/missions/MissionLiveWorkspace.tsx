import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { Mission, MissionTask } from '../../shared/api/types';
import { MissionDAG } from './MissionDAG';
import { TaskInspector } from './TaskInspector';
import { MissionBuilder } from './MissionBuilder';
import { Layers, Plus, CheckCircle, Pause, RotateCcw, AlertTriangle, ShieldCheck } from 'lucide-react';

export const MissionLiveWorkspace: React.FC = () => {
  const queryClient = useQueryClient();
  const { activeTopicId } = useUIStore();
  const [showBuilder, setShowBuilder] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedMissionId, setSelectedMissionId] = useState<string | null>(null);

  // Fetch missions for topic
  const { data: missionsData, isLoading } = useQuery<{ missions: Mission[] }>({
    queryKey: ['missions', activeTopicId],
    queryFn: () => api.get<{ missions: Mission[] }>(`/api/research/topics/${activeTopicId}/missions`),
    enabled: !!activeTopicId,
  });

  const missions = missionsData?.missions || [];
  const activeMission = missions.find((m) => m.id === selectedMissionId) || missions[0];

  // Approve & run mission mutation
  const approveMutation = useMutation({
    mutationFn: async ({ mid }: { mid: string }) => {
      let digest = activeMission?.payload?.plan_digest || activeMission?.payload?.approval?.plan_digest;
      if (!digest) {
        const reqRes = await api.post<Mission>(
          `/api/research/topics/${activeTopicId}/missions/${mid}/request-approval`,
          {}
        );
        digest = reqRes.payload?.plan_digest;
      }
      if (!digest) {
        const plan = await api.post<{ plan_digest: string }>(
          `/api/research/topics/${activeTopicId}/missions/plan`,
          activeMission.payload.spec
        );
        digest = plan.plan_digest;
      }
      return api.post(`/api/research/topics/${activeTopicId}/missions/${mid}/approve`, {
        plan_digest: digest,
        note: 'Approved via React Mission Workspace',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', activeTopicId] });
    },
    onError: (err: Error) => {
      alert(`Lỗi phê duyệt: ${err.message}`);
    },
  });

  // Pause mutation
  const pauseMutation = useMutation({
    mutationFn: (mid: string) =>
      api.post(`/api/research/topics/${activeTopicId}/missions/${mid}/pause`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', activeTopicId] });
    },
  });

  // Retry mutation
  const retryMutation = useMutation({
    mutationFn: ({ mid, taskId }: { mid: string; taskId: string }) =>
      api.post(`/api/research/topics/${activeTopicId}/missions/${mid}/retry`, {
        task_id: taskId,
        reconcile_note: 'Retried via React UI',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', activeTopicId] });
    },
  });

  // Review mutation (when awaiting_review)
  const reviewMutation = useMutation({
    mutationFn: ({ mid, decision }: { mid: string; decision: 'accept' | 'reject' }) =>
      api.post(`/api/research/topics/${activeTopicId}/missions/${mid}/review`, {
        decision,
        note: `Reviewed (${decision}) via React UI`,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['missions', activeTopicId] });
    },
  });

  if (!activeTopicId) {
    return (
      <div style={{ padding: 16 }}>
        <p className="muted">Vui lòng chọn Topic để xem hoặc tạo Missions.</p>
      </div>
    );
  }

  const selectedTask: MissionTask | null =
    activeMission?.tasks?.find((t) => t.id === selectedTaskId) || null;

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Layers size={18} color="var(--accent)" />
          <span>Nhiệm vụ nghiên cứu (Research Missions)</span>
        </h4>
        <button
          className="btn sm accent"
          onClick={() => setShowBuilder(!showBuilder)}
        >
          <Plus size={14} style={{ marginRight: 4 }} />
          <span>Tạo Mission</span>
        </button>
      </div>

      {showBuilder && (
        <MissionBuilder
          topicId={activeTopicId}
          onSuccess={() => setShowBuilder(false)}
          onCancel={() => setShowBuilder(false)}
        />
      )}

      {/* Mission Select & Actions */}
      {missions.length > 0 && activeMission && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <select
              className="input sm"
              style={{ flex: 1, maxWidth: 280 }}
              value={activeMission.id}
              onChange={(e) => {
                setSelectedMissionId(e.target.value);
                setSelectedTaskId(null);
              }}
            >
              {missions.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.payload.spec.objective} ({m.status.toUpperCase()})
                </option>
              ))}
            </select>

            <div style={{ display: 'flex', gap: 6 }}>
              {['draft', 'paused'].includes(activeMission.status) && (
                <button
                  className="btn sm accent"
                  onClick={() => approveMutation.mutate({ mid: activeMission.id })}
                  disabled={approveMutation.isPending}
                >
                  <CheckCircle size={14} style={{ marginRight: 4 }} /> Phê duyệt & Chạy
                </button>
              )}
              {activeMission.status === 'awaiting_review' && (
                <button
                  className="btn sm accent"
                  onClick={() => reviewMutation.mutate({ mid: activeMission.id, decision: 'accept' })}
                  disabled={reviewMutation.isPending}
                >
                  <ShieldCheck size={14} style={{ marginRight: 4 }} /> Nghiệm thu Kết quả
                </button>
              )}
              {activeMission.status === 'running' && (
                <button
                  className="btn sm ghost"
                  onClick={() => pauseMutation.mutate(activeMission.id)}
                  disabled={pauseMutation.isPending}
                >
                  <Pause size={14} style={{ marginRight: 4 }} /> Tạm dừng
                </button>
              )}
              {['failed', 'paused', 'interrupted'].includes(activeMission.status) && (
                <button
                  className="btn sm ghost"
                  onClick={() => {
                    const failedTask = activeMission.tasks.find((t) =>
                      ['failed', 'interrupted'].includes(t.status)
                    );
                    if (failedTask) {
                      retryMutation.mutate({ mid: activeMission.id, taskId: failedTask.id });
                    }
                  }}
                  disabled={retryMutation.isPending}
                >
                  <RotateCcw size={14} style={{ marginRight: 4 }} /> Thử lại
                </button>
              )}
            </div>
          </div>

          {activeMission.payload.blocking_reason && (
            <div style={{ background: 'var(--warn-soft)', padding: '8px 12px', borderRadius: 6, fontSize: 12.5, color: 'var(--warn)' }}>
              <AlertTriangle size={14} style={{ display: 'inline', marginRight: 4 }} />
              Tạm dừng: {activeMission.payload.blocking_reason}
            </div>
          )}

          {/* Mission DAG */}
          <MissionDAG tasks={activeMission.tasks} onSelectTask={(tid) => setSelectedTaskId(tid)} />

          {/* Task Inspector */}
          {selectedTask && (
            <TaskInspector task={selectedTask} onClose={() => setSelectedTaskId(null)} />
          )}
        </div>
      )}

      {missions.length === 0 && !isLoading && !showBuilder && (
        <p className="muted" style={{ fontSize: 13 }}>
          Chưa có Mission nào trong Topic này. Bấm "Tạo Mission" để bắt đầu quy trình có giám sát.
        </p>
      )}
    </div>
  );
};
