import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import type { Mission } from '../../shared/api/types';
import { Plus, Trash2, Code2, FormInput } from 'lucide-react';

interface MissionBuilderProps {
  topicId: string;
  onSuccess: (m: Mission) => void;
  onCancel: () => void;
}

const DETERMINISTIC_CAPABILITIES = new Set([
  'paper.discover',
  'paper.download',
  'paper.inspect',
  'workspace.sync',
  'mission.report',
  'experiment.run',
  'experiment.verify',
  'artifact.verify',
  'figure.create_2d',
  'figure.create_comparison',
  'figure.render_diagram',
  'figure.render_waveform',
  'figure.create_3d',
  'figure.validate',
  'figure.export',
  'figure.regenerate',
]);

export const MissionBuilder: React.FC<MissionBuilderProps> = ({ topicId, onSuccess, onCancel }) => {
  const queryClient = useQueryClient();
  const [jsonMode, setJsonMode] = useState(false);

  // Structured form state
  const [objective, setObjective] = useState('');
  const [permissions] = useState<string[]>(['workspace_write', 'network', 'reasoning']);
  const [tasks, setTasks] = useState<
    Array<{ id: string; capability: string; preferred_engine: string; depends_on: string[] }>
  >([
    { id: 'inspect_lit', capability: 'paper.inspect', preferred_engine: 'deterministic', depends_on: [] },
    { id: 'synthesize_report', capability: 'mission.report', preferred_engine: 'deterministic', depends_on: ['inspect_lit'] },
  ]);

  // Raw JSON state
  const [rawJson, setRawJson] = useState(() =>
    JSON.stringify(
      {
        topic_id: topicId,
        objective: 'Khảo sát và kiểm định tài liệu',
        permissions: ['workspace_write', 'network'],
        tasks: [
          { id: 'inspect_lit', capability: 'paper.inspect', preferred_engine: 'deterministic', depends_on: [], args: {} },
          { id: 'synthesize_report', capability: 'mission.report', preferred_engine: 'deterministic', depends_on: ['inspect_lit'], args: {} },
        ],
        limits: { max_seconds: 3600, max_reasoning_calls: 3 },
      },
      null,
      2
    )
  );

  const createMutation = useMutation({
    mutationFn: (body: unknown) =>
      api.post<Mission>(`/api/research/topics/${topicId}/missions`, body),
    onSuccess: (m) => {
      queryClient.invalidateQueries({ queryKey: ['missions', topicId] });
      onSuccess(m);
    },
    onError: (err: Error) => {
      alert(`Lỗi tạo Mission: ${err.message}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (jsonMode) {
      try {
        const parsed = JSON.parse(rawJson);
        createMutation.mutate(parsed);
      } catch {
        alert('Cú pháp JSON không hợp lệ');
      }
    } else {
      createMutation.mutate({
        topic_id: topicId,
        objective: objective.trim() || 'Thực thi nhiệm vụ nghiên cứu có giám sát',
        permissions,
        tasks: tasks.map((t) => ({
          id: t.id,
          capability: t.capability,
          preferred_engine: DETERMINISTIC_CAPABILITIES.has(t.capability)
            ? 'deterministic'
            : t.preferred_engine || 'deterministic',
          depends_on: t.depends_on.filter(Boolean),
          args: {},
        })),
        limits: { max_seconds: 3600, max_reasoning_calls: 3 },
      });
    }
  };

  const addTask = () => {
    const id = `task_${tasks.length + 1}`;
    setTasks([...tasks, { id, capability: 'paper.inspect', preferred_engine: 'deterministic', depends_on: [] }]);
  };

  const removeTask = (index: number) => {
    setTasks(tasks.filter((_, i) => i !== index));
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        background: 'var(--panel)',
        border: '1px solid var(--line-2)',
        borderRadius: 8,
        padding: 14,
        display: 'grid',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <b style={{ fontSize: 14 }}>Tạo Nhiệm vụ Nghiên cứu (Mission) mới</b>
        <button
          className="btn sm ghost"
          type="button"
          onClick={() => setJsonMode(!jsonMode)}
        >
          {jsonMode ? <FormInput size={14} style={{ marginRight: 4 }} /> : <Code2 size={14} style={{ marginRight: 4 }} />}
          <span>{jsonMode ? 'Chế độ Form' : 'Chế độ JSON'}</span>
        </button>
      </div>

      {jsonMode ? (
        <textarea
          className="input"
          value={rawJson}
          onChange={(e) => setRawJson(e.target.value)}
          rows={12}
          style={{ fontFamily: 'var(--mono)', fontSize: 12 }}
        />
      ) : (
        <>
          <label className="field" style={{ margin: 0 }}>
            <span>Mục tiêu nhiệm vụ (Objective)</span>
            <input
              className="input"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="vd: Tổng hợp bằng chứng, kết xuất biểu đồ IEEE và kiểm định mã nguồn"
              required
            />
          </label>

          <div style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--muted)' }}>
              Danh sách Tasks & Kỹ năng (v6.4.2):
            </span>
            {tasks.map((t, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                  background: 'var(--bg)',
                  padding: 8,
                  borderRadius: 6,
                }}
              >
                <input
                  className="input sm"
                  style={{ width: 105 }}
                  value={t.id}
                  onChange={(e) => {
                    const copy = [...tasks];
                    copy[idx].id = e.target.value;
                    setTasks(copy);
                  }}
                  placeholder="Task ID"
                />
                <select
                  className="input sm"
                  value={t.capability}
                  onChange={(e) => {
                    const cap = e.target.value;
                    const copy = [...tasks];
                    copy[idx].capability = cap;
                    copy[idx].preferred_engine = DETERMINISTIC_CAPABILITIES.has(cap)
                      ? 'deterministic'
                      : cap === 'code.implement'
                      ? 'deterministic'
                      : 'app';
                    setTasks(copy);
                  }}
                  style={{ flex: 1 }}
                >
                  <option value="paper.discover">paper.discover (Tìm bài báo — Deterministic)</option>
                  <option value="paper.inspect">paper.inspect (Kiểm tra bài báo — Deterministic)</option>
                  <option value="paper.compare">paper.compare (So sánh tài liệu — Reasoning)</option>
                  <option value="code.implement">code.implement (Lập trình native)</option>
                  <option value="figure.create_2d">figure.create_2d (Vẽ đồ thị 2D v6.4.0)</option>
                  <option value="figure.render_diagram">figure.render_diagram (Vẽ sơ đồ DOT v6.4.0)</option>
                  <option value="figure.validate">figure.validate (Kiểm định Figure v6.4.2)</option>
                  <option value="mission.report">mission.report (Viết báo cáo — Deterministic)</option>
                  <option value="experiment.verify">experiment.verify (Kiểm định thí nghiệm)</option>
                  <option value="artifact.verify">artifact.verify (Kiểm định artifact)</option>
                </select>
                <button
                  type="button"
                  className="icon sm"
                  onClick={() => removeTask(idx)}
                  disabled={tasks.length <= 1}
                >
                  <Trash2 size={14} color="var(--err)" />
                </button>
              </div>
            ))}
            <button
              className="btn sm ghost"
              type="button"
              onClick={addTask}
              style={{ width: 'fit-content', marginTop: 4 }}
            >
              <Plus size={14} style={{ marginRight: 4 }} /> Thêm Task
            </button>
          </div>
        </>
      )}

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', borderTop: '1px solid var(--line)', paddingTop: 10 }}>
        <button className="btn sm ghost" type="button" onClick={onCancel}>
          Huỷ
        </button>
        <button className="btn sm accent" type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? 'Đang tạo…' : 'Tạo Mission Draft'}
        </button>
      </div>
    </form>
  );
};
