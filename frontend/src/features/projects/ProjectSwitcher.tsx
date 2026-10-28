import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { Project } from '../../shared/api/types';
import {
  Folder,
  Plus,
  Check,
  FolderGit2,
  HardDrive,
  BookOpen,
  FolderOpen,
  Edit2,
  Trash2,
  ExternalLink,
  MoreHorizontal,
  Copy,
  Search,
  X,
  AlertTriangle,
} from 'lucide-react';
import { FolderPickerInput } from '../../shared/ui/FolderPickerInput';

export const ProjectSwitcher: React.FC = () => {
  const queryClient = useQueryClient();
  const { project, setProject, closeDrawer } = useUIStore();
  const { t } = useI18n();

  // Mode toggles
  const [showNew, setShowNew] = useState(false);
  const [showOpen, setShowOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Form states
  const [newName, setNewName] = useState('');
  const [newDataDir, setNewDataDir] = useState('');
  const [newRefsDir, setNewRefsDir] = useState('');
  const [projectsRoot, setProjectsRoot] = useState('');
  const { data: uiConfig } = useQuery({
    queryKey: ['config'],
    queryFn: () => api.get<{ ui?: { projects_root?: string } }>('/api/config'),
  });
  useEffect(() => {
    setProjectsRoot(uiConfig?.ui?.projects_root || '');
  }, [uiConfig?.ui?.projects_root]);
  const [openExistingDir, setOpenExistingDir] = useState('');

  // Rename modal states
  const [renamingProject, setRenamingProject] = useState<Project | null>(null);
  const [renameInputValue, setRenameInputValue] = useState('');

  // Delete modal states
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);

  // Dropdown menu state
  const [projectMenuOpenId, setProjectMenuOpenId] = useState<string | null>(null);
  const [deleteFilesOnDisk, setDeleteFilesOnDisk] = useState(false);

  // Copied indicator
  const [copiedDir, setCopiedDir] = useState<string | null>(null);

  // Query projects
  const { data: projectData, isLoading } = useQuery<{ projects: Project[] }>({
    queryKey: ['projects'],
    queryFn: () => api.get<{ projects: Project[] }>('/api/projects'),
  });

  const projects = projectData?.projects || [];

  // Switch / Activate Project
  const switchMutation = useMutation({
    mutationFn: (dir: string) => api.post('/api/projects/activate', { data_dir: dir }),
    onSuccess: (_, dir) => {
      const target = projects.find((p) => p.data_dir === dir);
      if (target) setProject(target);
      queryClient.invalidateQueries();
      closeDrawer();
    },
    onError: (err: Error) => {
      alert(`${t('Lỗi kích hoạt dự án', 'Error activating project')}: ${err.message}`);
    },
  });

  // Create Project
  const createMutation = useMutation({
    mutationFn: (payload: { name: string; data_dir?: string; references_dir?: string }) =>
      api.post<Project>('/api/projects', payload),
    onSuccess: (newProj) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setProject(newProj);
      setShowNew(false);
      setNewName('');
      setNewDataDir('');
      setNewRefsDir('');
      closeDrawer();
    },
    onError: (err: Error) => {
      alert(`${t('Lỗi tạo dự án', 'Error creating project')}: ${err.message}`);
    },
  });

  // Open Existing Project from Folder
  const openMutation = useMutation({
    mutationFn: (dir: string) => api.post<Project>('/api/projects/open', { data_dir: dir }),
    onSuccess: (openedProj) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setProject(openedProj);
      setShowOpen(false);
      setOpenExistingDir('');
      closeDrawer();
    },
    onError: (err: Error) => {
      alert(`${t('Lỗi mở dự án', 'Error opening project')}: ${err.message}`);
    },
  });

  // Rename Project
  const renameMutation = useMutation({
    mutationFn: ({ dir, name }: { dir: string; name: string }) =>
      api.put('/api/projects/rename', { data_dir: dir, name }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      if (project?.data_dir === variables.dir) {
        setProject({ ...project, name: variables.name });
      }
      setRenamingProject(null);
      setRenameInputValue('');
    },
    onError: (err: Error) => {
      alert(`${t('Lỗi đổi tên dự án', 'Error renaming project')}: ${err.message}`);
    },
  });

  // Delete Project
  const deleteMutation = useMutation({
    mutationFn: ({ dir, deleteFiles }: { dir: string; deleteFiles: boolean }) =>
      api.delete(`/api/projects?data_dir=${encodeURIComponent(dir)}&delete_files=${deleteFiles}`),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      // If deleted project was currently active, switch to Default project
      if (project?.data_dir === variables.dir) {
        const defaultProj = projects.find((p) => p.is_default);
        if (defaultProj) setProject(defaultProj);
      }
      setDeletingProject(null);
      setDeleteFilesOnDisk(false);
    },
    onError: (err: Error) => {
      alert(`${t('Lỗi xóa dự án', 'Error deleting project')}: ${err.message}`);
    },
  });

  // Reveal Project in OS File Explorer
  const revealMutation = useMutation({
    mutationFn: (dir?: string) => api.post('/api/projects/reveal', { data_dir: dir }),
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    const payload: { name: string; data_dir?: string; references_dir?: string } = {
      name: newName.trim(),
    };
    if (newDataDir.trim()) payload.data_dir = newDataDir.trim();
    if (newRefsDir.trim()) payload.references_dir = newRefsDir.trim();
    createMutation.mutate(payload);
  };

  const handleOpenSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!openExistingDir.trim()) return;
    openMutation.mutate(openExistingDir.trim());
  };

  const handleRenameSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!renamingProject || !renameInputValue.trim()) return;
    renameMutation.mutate({
      dir: renamingProject.data_dir,
      name: renameInputValue.trim(),
    });
  };

  const handleDeleteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!deletingProject) return;
    deleteMutation.mutate({
      dir: deletingProject.data_dir,
      deleteFiles: deleteFilesOnDisk,
    });
  };

  const handleCopyPath = (e: React.MouseEvent, path: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(path);
    setCopiedDir(path);
    setTimeout(() => setCopiedDir(null), 2000);
  };

  const filteredProjects = projects.filter((p) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return p.name.toLowerCase().includes(q) || p.data_dir.toLowerCase().includes(q);
  });

  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6, fontSize: 15, fontWeight: 700 }}>
          <Folder size={19} color="var(--accent)" />
          <span>{t('Dự án Nghiên cứu', 'Research Workspaces')}</span>
        </h4>

        {/* Action Buttons: New Project & Open Project */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            type="button"
            className={`btn sm ${showOpen ? 'accent' : 'ghost'}`}
            onClick={() => {
              setShowOpen(!showOpen);
              if (showNew) setShowNew(false);
            }}
            style={{ borderRadius: 999, fontWeight: 600 }}
            title={t('Mở thư mục dự án có sẵn từ máy tính', 'Open existing project folder')}
          >
            <FolderOpen size={14} style={{ marginRight: 4 }} color={showOpen ? 'currentColor' : 'var(--accent)'} />
            <span>{showOpen ? t('Đóng', 'Close') : t('Mở dự án', 'Open Project')}</span>
          </button>

          <button
            type="button"
            className={`btn sm ${showNew ? 'accent' : 'accent'}`}
            onClick={() => {
              setShowNew(!showNew);
              if (showOpen) setShowOpen(false);
            }}
            style={{ borderRadius: 999, fontWeight: 600 }}
            title={t('Khởi tạo dự án nghiên cứu mới', 'Create new research project')}
          >
            <Plus size={14} style={{ marginRight: 4 }} />
            <span>{showNew ? t('Đóng', 'Close') : t('Dự án mới', 'New Project')}</span>
          </button>
        </div>
      </div>

      {/* Search Bar */}
      {projects.length > 3 && (
        <div style={{ position: 'relative' }}>
          <Search size={14} color="var(--muted)" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
          <input
            className="input sm"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('Tìm kiếm dự án theo tên hoặc đường dẫn…', 'Search projects by name or path…')}
            style={{ paddingLeft: 30, borderRadius: 8, width: '100%' }}
          />
        </div>
      )}

      {/* 1. Panel: Create New Project */}
      {showNew && (
        <form
          onSubmit={handleCreateSubmit}
          style={{
            background: 'var(--panel)',
            border: '1px solid var(--line-2)',
            borderRadius: 12,
            padding: 14,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            boxShadow: 'var(--shadow)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b style={{ fontSize: 13.5, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Plus size={15} color="var(--accent)" />
              <span>{t('Khởi tạo Dự án Nghiên cứu Mới', 'Create New Research Project')}</span>
            </b>
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => setShowNew(false)}
              style={{ width: 24, height: 24, padding: 0, borderRadius: 999 }}
            >
              <X size={14} />
            </button>
          </div>

          {/* Project Name */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg)' }}>
              {t('Tên dự án *', 'Project Name *')}
            </label>
            <input
              className="input"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="vd: Vision-Language Reasoning"
              required
              autoFocus
              style={{ borderRadius: 8 }}
            />
          </div>

          {/* Project & Data Directory */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <HardDrive size={13} color="var(--accent)" />
              <span>{t('Đường dẫn thư mục dự án & Dữ liệu', 'Project & Data Directory')}</span>
            </label>
            <FolderPickerInput
              value={newDataDir}
              onChange={setNewDataDir}
              placeholder={t('vd: D:\\research\\my-project (để trống dùng mặc định)', 'e.g. D:\\research\\my-project (leave blank for default)')}
              dialogTitle={t('Chọn thư mục lưu trữ dự án & Data từ máy', 'Select Project & Data Directory')}
            />
            <span className="muted" style={{ fontSize: 11 }}>
              {t(
                'Thư mục lưu trữ cơ sở dữ liệu, bộ nhớ ngữ cảnh và trạng thái nghiên cứu.',
                'Folder storing database, research context memory, and experiment states.'
              )}
            </span>
          </div>

          {/* v6.6.2 default folder for new projects (any drive); used when the folder above is left blank */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }} data-testid="projects-root">
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <HardDrive size={13} color="var(--accent)" />
              <span>{t('projects.defaultRoot')}</span>
            </label>
            <FolderPickerInput
              value={projectsRoot}
              onChange={(value) => {
                setProjectsRoot(value);
                void api.post('/api/config', { ui: { projects_root: value } });
              }}
              placeholder={t('projects.defaultRoot')}
              dialogTitle={t('projects.pickFolder')}
            />
          </div>

          {/* References Directory */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <BookOpen size={13} color="#10b981" />
              <span>{t('Thư mục tài liệu PDF tham khảo', 'References / PDF Directory')}</span>
            </label>
            <FolderPickerInput
              value={newRefsDir}
              onChange={setNewRefsDir}
              placeholder={t('vd: D:\\research\\papers (tùy chọn hoặc tự tạo /references)', 'e.g. D:\\research\\papers (optional or auto-created /references)')}
              dialogTitle={t('Chọn thư mục tài liệu PDF tham khảo từ máy tính', 'Select References / PDF Directory')}
            />
            <span className="muted" style={{ fontSize: 11 }}>
              {t(
                'Thư mục chứa các tệp PDF bài báo của dự án.',
                'Folder containing scientific PDF papers of this research project.'
              )}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button
              className="btn sm ghost"
              type="button"
              onClick={() => setShowNew(false)}
              style={{ borderRadius: 999 }}
            >
              {t('Hủy', 'Cancel')}
            </button>
            <button
              className="btn sm accent"
              type="submit"
              disabled={createMutation.isPending}
              style={{ borderRadius: 999, fontWeight: 600 }}
            >
              {createMutation.isPending ? t('Đang tạo…', 'Creating…') : t('Tạo dự án', 'Create Project')}
            </button>
          </div>
        </form>
      )}

      {/* 2. Panel: Open Existing Project from Computer */}
      {showOpen && (
        <form
          onSubmit={handleOpenSubmit}
          style={{
            background: 'var(--panel)',
            border: '1px solid var(--accent)',
            borderRadius: 12,
            padding: 14,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            boxShadow: 'var(--shadow)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b style={{ fontSize: 13.5, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--accent)' }}>
              <FolderOpen size={16} />
              <span>{t('Mở Dự án Nghiên cứu có sẵn từ Máy tính', 'Open Existing Project from Computer')}</span>
            </b>
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => setShowOpen(false)}
              style={{ width: 24, height: 24, padding: 0, borderRadius: 999 }}
            >
              <X size={14} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg)', display: 'flex', alignItems: 'center', gap: 5 }}>
              <HardDrive size={13} color="var(--accent)" />
              <span>{t('Thư mục dự án trên máy *', 'Existing Project Directory on Machine *')}</span>
            </label>
            <FolderPickerInput
              value={openExistingDir}
              onChange={setOpenExistingDir}
              placeholder="e.g. D:\research\my-existing-project"
              required
              dialogTitle={t('Chọn thư mục dự án nghiên cứu cần mở từ máy', 'Select Project Folder to Open')}
            />
            <span className="muted" style={{ fontSize: 11 }}>
              {t(
                'Chọn một thư mục dự án nghiên cứu đã có sẵn (chứa project_meta.json hoặc workspace nghiên cứu).',
                'Select a previously created research project directory.'
              )}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button
              className="btn sm ghost"
              type="button"
              onClick={() => setShowOpen(false)}
              style={{ borderRadius: 999 }}
            >
              {t('Hủy', 'Cancel')}
            </button>
            <button
              className="btn sm accent"
              type="submit"
              disabled={openMutation.isPending || !openExistingDir.trim()}
              style={{ borderRadius: 999, fontWeight: 600 }}
            >
              {openMutation.isPending ? t('Đang mở…', 'Opening…') : t('Mở & Kích hoạt', 'Open & Activate')}
            </button>
          </div>
        </form>
      )}

      {/* 3. Rename Project Modal */}
      {renamingProject && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            background: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setRenamingProject(null);
          }}
        >
          <form
            onSubmit={handleRenameSubmit}
            style={{
              width: '100%',
              maxWidth: 440,
              background: 'var(--panel)',
              border: '1px solid var(--line-2)',
              borderRadius: 12,
              padding: 18,
              boxShadow: '0 16px 40px rgba(0,0,0,0.4)',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <b style={{ fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Edit2 size={16} color="var(--accent)" />
                <span>{t('Đổi tên Dự án Nghiên cứu', 'Rename Research Project')}</span>
              </b>
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => setRenamingProject(null)}
                style={{ width: 26, height: 26, padding: 0, borderRadius: 999 }}
              >
                <X size={14} />
              </button>
            </div>

            <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
              {renamingProject.data_dir}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--fg)' }}>
                {t('Tên mới cho dự án:', 'New Project Name:')}
              </label>
              <input
                className="input"
                value={renameInputValue}
                onChange={(e) => setRenameInputValue(e.target.value)}
                placeholder={t('Nhập tên mới…', 'Enter new name…')}
                autoFocus
                required
                style={{ borderRadius: 8 }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button
                className="btn sm ghost"
                type="button"
                onClick={() => setRenamingProject(null)}
                style={{ borderRadius: 999 }}
              >
                {t('Hủy', 'Cancel')}
              </button>
              <button
                className="btn sm accent"
                type="submit"
                disabled={renameMutation.isPending || !renameInputValue.trim()}
                style={{ borderRadius: 999, fontWeight: 600 }}
              >
                {renameMutation.isPending ? t('Đang lưu…', 'Saving…') : t('Lưu tên mới', 'Save Name')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 4. Delete Project Confirmation Modal */}
      {deletingProject && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setDeletingProject(null);
          }}
        >
          <form
            onSubmit={handleDeleteSubmit}
            style={{
              width: '100%',
              maxWidth: 460,
              background: 'var(--panel)',
              border: '1px solid #ef4444',
              borderRadius: 12,
              padding: 20,
              boxShadow: '0 20px 48px rgba(0,0,0,0.5)',
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 999,
                  background: 'rgba(239, 68, 68, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <AlertTriangle size={20} color="#ef4444" />
              </div>
              <div>
                <h4 style={{ margin: 0, fontSize: 15, color: '#ef4444', fontWeight: 700 }}>
                  {t('Xác nhận Xóa Dự án', 'Confirm Delete Project')}
                </h4>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                  {deletingProject.name}
                </div>
              </div>
            </div>

            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--fg)' }}>
              {t(
                `Bạn có chắc chắn muốn xóa dự án "${deletingProject.name}" khỏi hệ thống nghiên cứu?`,
                `Are you sure you want to remove project "${deletingProject.name}" from PhD Lab?`
              )}
            </p>

            <div
              style={{
                fontSize: 11.5,
                fontFamily: 'var(--mono)',
                background: 'var(--bg-2)',
                padding: '6px 10px',
                borderRadius: 6,
                border: '1px solid var(--line)',
                color: 'var(--muted)',
                wordBreak: 'break-all',
              }}
            >
              {deletingProject.data_dir}
            </div>

            {/* Checkbox: Also Delete Disk Files */}
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                fontSize: 12,
                cursor: 'pointer',
                color: 'var(--fg)',
                marginTop: 4,
              }}
            >
              <input
                type="checkbox"
                checked={deleteFilesOnDisk}
                onChange={(e) => setDeleteFilesOnDisk(e.target.checked)}
                style={{ marginTop: 2 }}
              />
              <span>
                {t(
                  'Đồng thời xóa vĩnh viễn toàn bộ tệp trong thư mục dự án khỏi ổ đĩa máy tính.',
                  'Also permanently delete all files in this project folder from disk.'
                )}
              </span>
            </label>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 6 }}>
              <button
                className="btn sm ghost"
                type="button"
                onClick={() => setDeletingProject(null)}
                style={{ borderRadius: 999 }}
              >
                {t('Hủy', 'Cancel')}
              </button>
              <button
                className="btn sm"
                type="submit"
                disabled={deleteMutation.isPending}
                style={{
                  borderRadius: 999,
                  fontWeight: 600,
                  background: '#ef4444',
                  color: '#ffffff',
                  border: 'none',
                }}
              >
                {deleteMutation.isPending
                  ? t('Đang xóa…', 'Deleting…')
                  : deleteFilesOnDisk
                  ? t('Xóa hoàn toàn cả tệp', 'Delete Project & Files')
                  : t('Gỡ khỏi danh sách', 'Remove from Lab')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 5. Projects List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {isLoading && <p className="muted">{t('Đang tải danh sách dự án…', 'Loading projects list…')}</p>}

        {!isLoading && filteredProjects.length === 0 && (
          <p className="muted" style={{ fontSize: 12, textAlign: 'center', padding: 16 }}>
            {t('Không tìm thấy dự án nào phù hợp.', 'No projects found.')}
          </p>
        )}

        {filteredProjects.map((p) => {
          const isSelected = project?.data_dir === p.data_dir;
          const isDefault = !!p.is_default;

          return (
            <div
              key={p.data_dir}
              role="article"
              aria-label={`Project ${p.name}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                padding: '10px 14px',
                borderRadius: 10,
                background: isSelected ? 'var(--accent-soft)' : 'var(--panel)',
                border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--line)'}`,
                transition: 'all 0.15s ease',
              }}
            >
              {/* Row 1: Icon, Name, Badges & Action Toolbar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div
                  onClick={() => switchMutation.mutate(p.data_dir)}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1, cursor: 'pointer' }}
                >
                  <FolderGit2
                    size={18}
                    color={isSelected ? 'var(--accent)' : 'var(--muted)'}
                    style={{ flexShrink: 0 }}
                  />
                  <span
                    className="ellipsis"
                    style={{
                      fontWeight: 600,
                      fontSize: 13.5,
                      color: isSelected ? 'var(--accent)' : 'var(--fg)',
                    }}
                    title={p.name}
                  >
                    {p.name}
                  </span>

                  {/* Badges */}
                  {isDefault && (
                    <span
                      style={{
                        fontSize: 10.5,
                        fontWeight: 600,
                        padding: '1px 6px',
                        borderRadius: 999,
                        background: 'var(--bg-2)',
                        color: 'var(--muted)',
                        border: '1px solid var(--line)',
                        flexShrink: 0,
                      }}
                    >
                      {t('Mặc định', 'Default')}
                    </span>
                  )}
                  {isSelected && (
                    <span
                      style={{
                        fontSize: 10.5,
                        fontWeight: 600,
                        padding: '1px 6px',
                        borderRadius: 999,
                        background: 'var(--accent)',
                        color: '#ffffff',
                        flexShrink: 0,
                      }}
                    >
                      {t('Đang mở', 'Active')}
                    </span>
                  )}
                </div>

                {/* Card Actions Group */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 3, flexShrink: 0 }}>
                  {/* Switch button if not selected */}
                  {!isSelected && (
                    <button
                      type="button"
                      className="btn sm ghost"
                      onClick={() => switchMutation.mutate(p.data_dir)}
                      title={t('Kích hoạt dự án này', 'Activate project')}
                      style={{ padding: '3px 8px', fontSize: 11.5, borderRadius: 6 }}
                    >
                      <span>{t('Kích hoạt', 'Activate')}</span>
                    </button>
                  )}

                  {/* Dropdown Menu for Project Actions (Reveal, Rename, Delete) */}
                  <div style={{ position: 'relative' }}>
                    <button
                      type="button"
                      className="btn sm ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        setProjectMenuOpenId(projectMenuOpenId === p.data_dir ? null : p.data_dir);
                      }}
                      title={t('Tùy chọn dự án', 'Project options')}
                      style={{
                        padding: '4px 6px',
                        borderRadius: 6,
                        background: projectMenuOpenId === p.data_dir ? 'var(--line-2)' : 'transparent',
                      }}
                    >
                      <MoreHorizontal size={14} color="var(--ink)" />
                    </button>

                    {projectMenuOpenId === p.data_dir && (
                      <>
                        <div
                          style={{
                            position: 'fixed',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            zIndex: 90,
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            setProjectMenuOpenId(null);
                          }}
                        />
                        <div
                          style={{
                            position: 'absolute',
                            top: '100%',
                            right: 0,
                            marginTop: 4,
                            background: 'var(--panel)',
                            border: '1px solid var(--line-2)',
                            borderRadius: 8,
                            boxShadow: 'var(--shadow)',
                            padding: 4,
                            zIndex: 95,
                            minWidth: 175,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 2,
                          }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          {/* 1. Reveal in Explorer */}
                          <button
                            type="button"
                            className="btn sm ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              revealMutation.mutate(p.data_dir);
                              setProjectMenuOpenId(null);
                            }}
                            title={t('Mở thư mục trong máy tính', 'Open folder in File Explorer')}
                            style={{ justifyContent: 'flex-start', padding: '6px 10px', fontSize: 12, gap: 8, width: '100%' }}
                          >
                            <ExternalLink size={13} color="var(--muted)" />
                            <span>{t('Mở thư mục', 'Open in Explorer')}</span>
                          </button>

                          {/* 2. Rename */}
                          <button
                            type="button"
                            className="btn sm ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              setRenamingProject(p);
                              setRenameInputValue(p.name);
                              setProjectMenuOpenId(null);
                            }}
                            title={t('Đổi tên dự án', 'Rename project')}
                            style={{ justifyContent: 'flex-start', padding: '6px 10px', fontSize: 12, gap: 8, width: '100%' }}
                          >
                            <Edit2 size={13} color="var(--muted)" />
                            <span>{t('Đổi tên', 'Rename')}</span>
                          </button>

                          {/* Divider */}
                          <div style={{ height: 1, background: 'var(--line)', margin: '2px 0' }} />

                          {/* 3. Delete / Remove (Disabled for default project) */}
                          <button
                            type="button"
                            className="btn sm ghost"
                            disabled={isDefault}
                            onClick={(e) => {
                              e.stopPropagation();
                              if (isDefault) return;
                              setDeletingProject(p);
                              setDeleteFilesOnDisk(false);
                              setProjectMenuOpenId(null);
                            }}
                            title={
                              isDefault
                                ? t('Dự án Mặc định không thể xóa', 'Default project cannot be deleted')
                                : t('Xóa hoặc gỡ dự án', 'Delete or remove project')
                            }
                            style={{
                              justifyContent: 'flex-start',
                              padding: '6px 10px',
                              fontSize: 12,
                              gap: 8,
                              width: '100%',
                              color: isDefault ? 'var(--muted)' : '#ef4444',
                              opacity: isDefault ? 0.35 : 1,
                              cursor: isDefault ? 'not-allowed' : 'pointer',
                            }}
                          >
                            <Trash2 size={13} color={isDefault ? 'var(--muted)' : '#ef4444'} />
                            <span>{t('Xóa hoặc gỡ dự án', 'Delete Project')}</span>
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Row 2: Directory Path & Quick Copy */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 6,
                  paddingLeft: 26,
                }}
              >
                <span
                  className="ellipsis"
                  style={{
                    fontSize: 11,
                    fontFamily: 'var(--mono)',
                    color: 'var(--muted)',
                  }}
                  title={p.data_dir}
                >
                  {p.data_dir}
                </span>

                <button
                  type="button"
                  onClick={(e) => handleCopyPath(e, p.data_dir)}
                  className="btn sm ghost"
                  style={{ padding: '1px 5px', fontSize: 10, borderRadius: 4, height: 20 }}
                  title={t('Sao chép đường dẫn thư mục', 'Copy path')}
                >
                  {copiedDir === p.data_dir ? (
                    <Check size={11} color="#10b981" />
                  ) : (
                    <Copy size={11} color="var(--muted)" />
                  )}
                  <span style={{ marginLeft: 3 }}>
                    {copiedDir === p.data_dir ? t('Đã chép', 'Copied') : t('Chép', 'Copy')}
                  </span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
