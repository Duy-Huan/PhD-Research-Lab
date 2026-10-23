import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { Project } from '../../shared/api/types';
import { Folder, Plus, Check } from 'lucide-react';

export const ProjectSwitcher: React.FC = () => {
  const queryClient = useQueryClient();
  const { project, setProject, closeDrawer } = useUIStore();
  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState('');

  const { data: projectData, isLoading } = useQuery<{ projects: Project[] }>({
    queryKey: ['projects'],
    queryFn: () => api.get<{ projects: Project[] }>('/api/projects'),
  });

  const projects = projectData?.projects || [];

  const switchMutation = useMutation({
    mutationFn: (dir: string) =>
      api.post('/api/projects/activate', { data_dir: dir }),
    onSuccess: (_, dir) => {
      const target = projects.find((p) => p.data_dir === dir);
      if (target) setProject(target);
      queryClient.invalidateQueries();
      closeDrawer();
    },
  });

  const createMutation = useMutation({
    mutationFn: (projectName: string) =>
      api.post<Project>('/api/projects', { name: projectName }),
    onSuccess: (newProj) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setProject(newProj);
      setShowNew(false);
      setName('');
      closeDrawer();
    },
  });

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Folder size={18} color="var(--accent)" />
          <span>Dự án nghiên cứu (Projects)</span>
        </h4>
        <button className="btn sm accent" onClick={() => setShowNew(!showNew)}>
          <Plus size={14} style={{ marginRight: 4 }} /> Dự án mới
        </button>
      </div>

      {showNew && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) createMutation.mutate(name.trim());
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
          <b>Tên dự án mới:</b>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="vd: Vision-Language Reasoning"
            required
          />
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
            <button className="btn sm ghost" type="button" onClick={() => setShowNew(false)}>
              Huỷ
            </button>
            <button className="btn sm accent" type="submit" disabled={createMutation.isPending}>
              Tạo dự án
            </button>
          </div>
        </form>
      )}

      {/* Projects List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {isLoading && <p className="muted">Đang tải danh sách dự án…</p>}
        {projects.map((p) => {
          const isSelected = project?.data_dir === p.data_dir;
          return (
            <div
              key={p.data_dir}
              onClick={() => switchMutation.mutate(p.data_dir)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 14px',
                borderRadius: 8,
                background: isSelected ? 'var(--sel)' : 'var(--panel)',
                border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--line)'}`,
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Folder size={18} color={isSelected ? 'var(--accent)' : 'var(--muted)'} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{p.name}</div>
                  <div className="muted" style={{ fontSize: 11.5 }}>
                    {p.data_dir}
                  </div>
                </div>
              </div>
              {isSelected && <Check size={16} color="var(--accent)" />}
            </div>
          );
        })}
      </div>
    </div>
  );
};
