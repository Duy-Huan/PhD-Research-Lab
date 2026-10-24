import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useI18n } from '../state/uiStore';
import {
  FolderOpen,
  FolderTree,
  Folder,
  FolderPlus,
  HardDrive,
  Monitor,
  Home,
  FileText,
  Download,
  FlaskConical,
  ArrowUp,
  RefreshCw,
  Search,
  Check,
  X,
  ChevronRight,
  FolderGit2,
} from 'lucide-react';

export interface FolderBrowserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (selectedPath: string) => void;
  initialPath?: string;
  title?: string;
}

interface FsBrowseResponse {
  current: string;
  parent: string | null;
  drives: string[];
  shortcuts: Array<{ name: string; path: string }>;
  directories: Array<{ name: string; path: string; hidden: boolean }>;
}

export const FolderBrowserModal: React.FC<FolderBrowserModalProps> = ({
  isOpen,
  onClose,
  onSelect,
  initialPath = '',
  title,
}) => {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [selectedPath, setSelectedPath] = useState(initialPath);
  const [searchFilter, setSearchFilter] = useState('');
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [isPickingOS, setIsPickingOS] = useState(false);
  const [pathInput, setPathInput] = useState(initialPath);

  useEffect(() => {
    if (isOpen) {
      setCurrentPath(initialPath || '');
      setSelectedPath(initialPath || '');
      setPathInput(initialPath || '');
      setSearchFilter('');
      setIsCreatingFolder(false);
    }
  }, [isOpen, initialPath]);

  const { data, isLoading, refetch, isError } = useQuery<FsBrowseResponse>({
    queryKey: ['fs-browse', currentPath],
    queryFn: () =>
      api.get<FsBrowseResponse>(`/api/system/fs-browse${currentPath ? `?path=${encodeURIComponent(currentPath)}` : ''}`),
    enabled: isOpen,
    staleTime: 5000,
  });

  useEffect(() => {
    if (data?.current) {
      setPathInput(data.current);
      if (!selectedPath) setSelectedPath(data.current);
    }
  }, [data?.current]);

  const mkdirMutation = useMutation({
    mutationFn: (targetPath: string) => api.post('/api/system/fs-mkdir', { path: targetPath }),
    onSuccess: (res: any) => {
      queryClient.invalidateQueries({ queryKey: ['fs-browse', currentPath] });
      setIsCreatingFolder(false);
      setNewFolderName('');
      if (res?.path) {
        setSelectedPath(res.path);
        setCurrentPath(res.path);
      }
    },
    onError: (err: Error) => {
      alert(`${t('Lỗi tạo thư mục', 'Error creating folder')}: ${err.message}`);
    },
  });

  const handlePickViaOS = async () => {
    try {
      setIsPickingOS(true);
      const res = await api.post<{ path: string; canceled: boolean }>('/api/system/pick-folder', {
        initial_dir: currentPath || initialPath || '',
        title: title || t('Chọn thư mục từ máy tính', 'Select folder from computer'),
      });
      if (res && res.path && !res.canceled) {
        onSelect(res.path);
        onClose();
      }
    } catch (err: any) {
      alert(`${t('Lỗi mở hộp thoại', 'Failed to open OS dialog')}: ${err?.message || err}`);
    } finally {
      setIsPickingOS(false);
    }
  };

  const handleCreateNewFolder = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim() || !data?.current) return;
    const separator = data.current.includes('/') ? '/' : '\\';
    const cleanCurrent = data.current.endsWith(separator) ? data.current : data.current + separator;
    const target = cleanCurrent + newFolderName.trim();
    mkdirMutation.mutate(target);
  };

  const handleConfirmSelect = () => {
    const finalPath = selectedPath || data?.current || currentPath;
    if (finalPath) {
      onSelect(finalPath);
      onClose();
    }
  };

  const getShortcutIcon = (name: string) => {
    switch (name.toLowerCase()) {
      case 'home':
        return <Home size={13} />;
      case 'desktop':
        return <Monitor size={13} />;
      case 'documents':
        return <FileText size={13} />;
      case 'downloads':
        return <Download size={13} />;
      case 'workspace lab':
        return <FlaskConical size={13} color="var(--accent)" />;
      case 'active project':
        return <FolderGit2 size={13} color="var(--accent)" />;
      default:
        return <Folder size={13} />;
    }
  };

  if (!isOpen) return null;

  const filteredDirs = (data?.directories || []).filter((d) =>
    searchFilter ? d.name.toLowerCase().includes(searchFilter.toLowerCase()) : true
  );

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(0, 0, 0, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 820,
          maxHeight: '90vh',
          background: 'var(--panel)',
          border: '1px solid var(--line-2)',
          borderRadius: 14,
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.45)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '14px 18px',
            borderBottom: '1px solid var(--line)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--bg-2)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <FolderTree size={20} color="var(--accent)" />
            <div>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--fg)' }}>
                {title || t('Duyệt thư mục trên máy tính · Computer Folder Browser', 'Browse Computer Folders')}
              </h3>
              <span className="muted" style={{ fontSize: 11.5 }}>
                {t(
                  'Duyệt ổ đĩa trên máy tính hoặc mở hộp thoại Windows Explorer trực tiếp.',
                  'Browse local drives or open native Windows Explorer dialog directly.'
                )}
              </span>
            </div>
          </div>
          <button
            className="btn sm ghost"
            onClick={onClose}
            style={{ borderRadius: 999, width: 30, height: 30, padding: 0 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Action Toolbar */}
        <div
          style={{
            padding: '10px 18px',
            background: 'var(--bg)',
            borderBottom: '1px solid var(--line)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
          }}
        >
          {/* Direct OS Picker Button */}
          <button
            type="button"
            className="btn sm accent"
            onClick={handlePickViaOS}
            disabled={isPickingOS}
            style={{ borderRadius: 8, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 }}
            title={t('Mở hộp thoại chọn thư mục của hệ điều hành', 'Open native OS folder dialog')}
          >
            <Monitor size={14} />
            <span>
              {isPickingOS
                ? t('Đang mở hộp thoại Windows...', 'Opening Windows Dialog...')
                : t('Mở hộp thoại hệ thống Windows', 'Open Windows Dialog')}
            </span>
          </button>

          <div style={{ width: 1, height: 22, background: 'var(--line)' }} />

          {/* Up to Parent Button */}
          <button
            type="button"
            className="btn sm ghost"
            disabled={!data?.parent}
            onClick={() => {
              if (data?.parent) {
                setCurrentPath(data.parent);
                setSelectedPath(data.parent);
              }
            }}
            title={t('Lên thư mục cha', 'Up to parent folder')}
            style={{ borderRadius: 8 }}
          >
            <ArrowUp size={14} style={{ marginRight: 4 }} />
            <span>{t('Lên cấp', 'Up')}</span>
          </button>

          {/* Refresh Button */}
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => refetch()}
            title={t('Làm mới', 'Refresh')}
            style={{ borderRadius: 8, padding: '6px 10px' }}
          >
            <RefreshCw size={13} className={isLoading ? 'spin' : ''} />
          </button>

          {/* New Folder Toggle */}
          <button
            type="button"
            className={`btn sm ${isCreatingFolder ? 'accent' : 'ghost'}`}
            onClick={() => setIsCreatingFolder(!isCreatingFolder)}
            title={t('Tạo thư mục con mới tại vị trí này', 'Create new subfolder here')}
            style={{ borderRadius: 8 }}
          >
            <FolderPlus size={14} style={{ marginRight: 4 }} />
            <span>{t('Tạo thư mục', 'New Folder')}</span>
          </button>

          {/* Search Filter in current directory */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: 8, color: 'var(--muted)' }} />
            <input
              className="input sm"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder={t('Lọc thư mục…', 'Filter folders…')}
              style={{ paddingLeft: 26, width: 160, borderRadius: 8, fontSize: 11.5 }}
            />
          </div>
        </div>

        {/* Current Path Breadcrumb / Input Bar */}
        <div
          style={{
            padding: '8px 18px',
            background: 'var(--panel)',
            borderBottom: '1px solid var(--line)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
            {t('Vị trí:', 'Path:')}
          </span>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (pathInput.trim()) {
                setCurrentPath(pathInput.trim());
                setSelectedPath(pathInput.trim());
              }
            }}
            style={{ display: 'flex', flex: 1, gap: 6 }}
          >
            <input
              className="input sm"
              value={pathInput}
              onChange={(e) => setPathInput(e.target.value)}
              placeholder="D:\research\my-project"
              style={{
                flex: 1,
                fontFamily: 'var(--mono)',
                fontSize: 12,
                borderRadius: 6,
              }}
            />
            <button type="submit" className="btn sm ghost" style={{ borderRadius: 6, fontSize: 11.5 }}>
              {t('Đi đến', 'Go')}
            </button>
          </form>
        </div>

        {/* Inline Create Folder Form */}
        {isCreatingFolder && (
          <form
            onSubmit={handleCreateNewFolder}
            style={{
              padding: '10px 18px',
              background: 'var(--accent-soft)',
              borderBottom: '1px solid var(--line)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <FolderPlus size={16} color="var(--accent)" />
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg)' }}>
              {t('Tên thư mục mới:', 'New Folder Name:')}
            </span>
            <input
              className="input sm"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder={t('vd: dataset_2026', 'e.g. dataset_2026')}
              autoFocus
              style={{ width: 220, borderRadius: 6 }}
            />
            <button
              type="submit"
              className="btn sm accent"
              disabled={mkdirMutation.isPending || !newFolderName.trim()}
              style={{ borderRadius: 6 }}
            >
              {mkdirMutation.isPending ? t('Đang tạo…', 'Creating…') : t('Xác nhận tạo', 'Create')}
            </button>
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => setIsCreatingFolder(false)}
              style={{ borderRadius: 6 }}
            >
              {t('Hủy', 'Cancel')}
            </button>
          </form>
        )}

        {/* Main Split Body: Sidebar (Drives & Shortcuts) + Directory Grid */}
        <div style={{ display: 'flex', flex: 1, minHeight: 320, maxHeight: 420, overflow: 'hidden' }}>
          {/* Left Navigation: Drives & Shortcuts */}
          <div
            style={{
              width: 190,
              flexShrink: 0,
              background: 'var(--bg-2)',
              borderRight: '1px solid var(--line)',
              padding: '12px 10px',
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
              overflowY: 'auto',
            }}
          >
            {/* Drives */}
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  color: 'var(--muted)',
                  letterSpacing: 0.5,
                  marginBottom: 6,
                  paddingLeft: 6,
                }}
              >
                {t('Ổ đĩa máy tính', 'Local Drives')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {(data?.drives || []).map((drive) => {
                  const isActive = currentPath.toLowerCase().startsWith(drive.toLowerCase());
                  return (
                    <button
                      key={drive}
                      type="button"
                      onClick={() => {
                        setCurrentPath(drive);
                        setSelectedPath(drive);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '6px 8px',
                        borderRadius: 6,
                        border: 'none',
                        background: isActive ? 'var(--accent-soft)' : 'transparent',
                        color: isActive ? 'var(--accent)' : 'var(--fg)',
                        fontWeight: isActive ? 600 : 400,
                        fontSize: 12,
                        cursor: 'pointer',
                        textAlign: 'left',
                        fontFamily: 'var(--mono)',
                      }}
                    >
                      <HardDrive size={14} color={isActive ? 'var(--accent)' : 'var(--muted)'} />
                      <span>{drive}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Shortcuts */}
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  color: 'var(--muted)',
                  letterSpacing: 0.5,
                  marginBottom: 6,
                  paddingLeft: 6,
                }}
              >
                {t('Lối tắt', 'Shortcuts')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {(data?.shortcuts || []).map((sc) => {
                  const isActive = currentPath.toLowerCase() === sc.path.toLowerCase();
                  return (
                    <button
                      key={sc.path + sc.name}
                      type="button"
                      onClick={() => {
                        setCurrentPath(sc.path);
                        setSelectedPath(sc.path);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '6px 8px',
                        borderRadius: 6,
                        border: 'none',
                        background: isActive ? 'var(--accent-soft)' : 'transparent',
                        color: isActive ? 'var(--accent)' : 'var(--fg)',
                        fontWeight: isActive ? 600 : 400,
                        fontSize: 12,
                        cursor: 'pointer',
                        textAlign: 'left',
                      }}
                      title={sc.path}
                    >
                      {getShortcutIcon(sc.name)}
                      <span className="ellipsis" style={{ flex: 1 }}>
                        {sc.name}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Directory List */}
          <div
            style={{
              flex: 1,
              padding: 14,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              background: 'var(--panel)',
            }}
          >
            {isLoading && (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
                <RefreshCw size={18} className="spin" style={{ display: 'inline-block', marginBottom: 6 }} />
                <div>{t('Đang nạp danh sách thư mục…', 'Loading directory contents…')}</div>
              </div>
            )}

            {isError && (
              <div style={{ padding: 18, color: '#ef4444', fontSize: 12 }}>
                {t('Không thể truy cập đường dẫn này hoặc bị giới hạn quyền.', 'Cannot access this path or permission denied.')}
              </div>
            )}

            {!isLoading && filteredDirs.length === 0 && (
              <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 12.5 }}>
                <FolderOpen size={28} style={{ opacity: 0.4, marginBottom: 8 }} />
                <div>{t('Không có thư mục con nào tại vị trí này.', 'No subfolders found in this directory.')}</div>
                <div style={{ marginTop: 6, fontSize: 11 }}>
                  {t('Bạn có thể chọn vị trí hiện tại hoặc bấm "Tạo thư mục" để thêm mới.', 'You can select this current location or click "New Folder".')}
                </div>
              </div>
            )}

            {!isLoading &&
              filteredDirs.map((dir) => {
                const isSelected = selectedPath === dir.path;
                return (
                  <div
                    key={dir.path}
                    onClick={() => setSelectedPath(dir.path)}
                    onDoubleClick={() => {
                      setCurrentPath(dir.path);
                      setSelectedPath(dir.path);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '7px 10px',
                      borderRadius: 8,
                      background: isSelected ? 'var(--accent-soft)' : 'transparent',
                      border: `1px solid ${isSelected ? 'var(--accent)' : 'transparent'}`,
                      cursor: 'pointer',
                      transition: 'background 0.1s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                      <Folder
                        size={16}
                        color={isSelected ? 'var(--accent)' : '#f59e0b'}
                        style={{ flexShrink: 0 }}
                      />
                      <span
                        className="ellipsis"
                        style={{
                          fontSize: 12.5,
                          fontWeight: isSelected ? 600 : 400,
                          color: dir.hidden ? 'var(--muted)' : 'var(--fg)',
                        }}
                      >
                        {dir.name}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <button
                        type="button"
                        className="btn sm ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          setCurrentPath(dir.path);
                          setSelectedPath(dir.path);
                        }}
                        title={t('Mở thư mục này', 'Open this directory')}
                        style={{ padding: '3px 8px', fontSize: 11, borderRadius: 6 }}
                      >
                        <span>{t('Mở', 'Open')}</span>
                        <ChevronRight size={12} style={{ marginLeft: 2 }} />
                      </button>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '12px 18px',
            borderTop: '1px solid var(--line)',
            background: 'var(--bg-2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ minWidth: 0, flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
              {t('Thư mục được chọn:', 'Selected:')}
            </span>
            <span
              className="ellipsis"
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--accent)',
                background: 'var(--panel)',
                padding: '4px 10px',
                borderRadius: 6,
                border: '1px solid var(--line)',
                display: 'inline-block',
                maxWidth: '100%',
              }}
              title={selectedPath || data?.current || currentPath}
            >
              {selectedPath || data?.current || currentPath || t('(Chưa chọn)', '(None selected)')}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            <button className="btn sm ghost" type="button" onClick={onClose} style={{ borderRadius: 999 }}>
              {t('Hủy', 'Cancel')}
            </button>
            <button
              className="btn sm accent"
              type="button"
              onClick={handleConfirmSelect}
              style={{ borderRadius: 999, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Check size={14} />
              <span>{t('Chọn thư mục này', 'Select This Folder')}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
