import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../shared/state/uiStore';
import { api } from '../shared/api/client';
import type { ChatSession, ChatProject } from '../shared/api/types';
import {
  Sidebar as SidebarIcon,
  Plus,
  ChevronDown,
  ChevronRight,
  Gauge,
  BookOpen,
  Brain,
  Layers,
  GitBranch,
  Bot,
  FileText,
  Code,
  CheckCircle,
  Settings,
  BarChart3,
  Terminal,
  Cpu,
  FlaskConical,
  Award,
  Trash2,
  Pin,
  FolderPlus,
  Folder,
  FolderOpen,
  Search,
  Edit3,
  SquarePen,
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const queryClient = useQueryClient();
  const {
    toggleSidebar,
    project,
    activeSessionId,
    setActiveSessionId,
    activeChatProjectId,
    setActiveChatProjectId,
    openDrawer,
    open3DOffice,
    openSettings,
    setMainView,
    mainView,
    pendingCount,
  } = useUIStore();
  const { t } = useI18n();

  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // Folder (Chat Project) creation & editing state
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderInstructions, setNewFolderInstructions] = useState('');
  const [editingFolder, setEditingFolder] = useState<ChatProject | null>(null);
  const [assigningSessionId, setAssigningSessionId] = useState<string | null>(null);

  // Fetch conversations
  const { data: sessionData } = useQuery<{ sessions: ChatSession[] }>({
    queryKey: ['sessions', project?.data_dir],
    queryFn: () => api.get<{ sessions: ChatSession[] }>('/api/chat/sessions'),
    enabled: !!project,
  });

  // Fetch chat folders (ChatGPT-style Projects with shared context)
  const { data: chatProjectsData } = useQuery<{ projects: ChatProject[] }>({
    queryKey: ['chat-projects', project?.data_dir],
    queryFn: () => api.get<{ projects: ChatProject[] }>('/api/chat/projects'),
    enabled: !!project,
  });

  const sessions = sessionData?.sessions || [];
  const chatFolders = chatProjectsData?.projects || [];

  const filteredSessions = searchQuery
    ? sessions.filter((s) => (s.title || '').toLowerCase().includes(searchQuery.toLowerCase()))
    : sessions;

  const pinnedSessions = filteredSessions.filter((s) => s.pinned);
  const recentSessions = activeChatProjectId
    ? filteredSessions.filter((s) => s.chat_project === activeChatProjectId)
    : filteredSessions;

  const handleTogglePin = async (e: React.MouseEvent, s: ChatSession) => {
    e.stopPropagation();
    await api.put(`/api/chat/sessions/${s.id}`, { pinned: !s.pinned });
    queryClient.invalidateQueries({ queryKey: ['sessions'] });
  };

  const handleAssignFolder = async (sid: string, folderId: string) => {
    await api.put(`/api/chat/sessions/${sid}`, { chat_project: folderId });
    setAssigningSessionId(null);
    queryClient.invalidateQueries({ queryKey: ['sessions'] });
    queryClient.invalidateQueries({ queryKey: ['chat', sid] });
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    const res = await api.post<{ project: ChatProject }>('/api/chat/projects', {
      name: newFolderName.trim(),
      instructions: newFolderInstructions.trim(),
    });
    setNewFolderName('');
    setNewFolderInstructions('');
    setCreatingFolder(false);
    queryClient.invalidateQueries({ queryKey: ['chat-projects'] });
    if (res?.project?.id) {
      setActiveChatProjectId(res.project.id);
    }
  };

  const handleSaveEditFolder = async () => {
    if (!editingFolder) return;
    await api.put(`/api/chat/projects/${editingFolder.id}`, {
      name: editingFolder.name,
      instructions: editingFolder.instructions || '',
    });
    setEditingFolder(null);
    queryClient.invalidateQueries({ queryKey: ['chat-projects'] });
  };

  const handleDeleteFolder = async (e: React.MouseEvent, gid: string) => {
    e.stopPropagation();
    if (!confirm(t('Xóa nhóm thư mục chat này?', 'Delete this chat folder?'))) return;
    await api.delete(`/api/chat/projects/${gid}`);
    if (activeChatProjectId === gid) setActiveChatProjectId(null);
    queryClient.invalidateQueries({ queryKey: ['chat-projects'] });
    queryClient.invalidateQueries({ queryKey: ['sessions'] });
  };

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation();
    if (!confirm(t('Xóa cuộc trò chuyện này?', 'Delete this conversation?'))) return;
    try {
      await api.delete(`/api/chat/sessions/${sid}?confirm=DELETE`);
    } catch {
      await api.delete(`/api/chat/sessions/${sid}`);
    }
    if (activeSessionId === sid) setActiveSessionId(null);
    queryClient.invalidateQueries({ queryKey: ['sessions'] });
  };

  const renderSessionRow = (s: ChatSession) => {
    const isActive = activeSessionId === s.id && mainView === 'chat';
    return (
      <div key={s.id} style={{ position: 'relative' }}>
        <div
          className={`thread-item ${isActive ? 'active' : ''}`}
          onClick={() => {
            setActiveSessionId(s.id);
            setMainView('chat');
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            textAlign: 'left',
            padding: '6px 8px',
            background: isActive ? 'var(--sel)' : 'transparent',
            borderRadius: 8,
            cursor: 'pointer',
            marginBottom: 2,
            gap: 4,
          }}
        >
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="ellipsis" style={{ fontWeight: isActive ? 600 : 400, fontSize: 12.5 }}>
              {s.title || t('Phiên nghiên cứu mới', 'New conversation')}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
            <button
              type="button"
              className="icon sm"
              title={s.pinned ? t('Bỏ ghim', 'Unpin') : t('Ghim đoạn chat', 'Pin chat')}
              onClick={(e) => handleTogglePin(e, s)}
              style={{
                width: 20,
                height: 20,
                opacity: s.pinned ? 1 : 0.5,
                color: s.pinned ? 'var(--accent)' : 'inherit',
              }}
            >
              <Pin size={11} />
            </button>
            <button
              type="button"
              className="icon sm"
              title={t('Chuyển vào Thư mục Nhóm Chat', 'Move to Chat Folder')}
              onClick={(e) => {
                e.stopPropagation();
                setAssigningSessionId(assigningSessionId === s.id ? null : s.id);
              }}
              style={{ width: 20, height: 20, opacity: 0.55 }}
            >
              <Folder size={11} />
            </button>
            <button
              type="button"
              className="icon sm"
              title={t('Xóa', 'Delete')}
              onClick={(e) => handleDeleteSession(e, s.id)}
              style={{ width: 20, height: 20, opacity: 0.55 }}
            >
              <Trash2 size={11} />
            </button>
          </div>
        </div>

        {/* Folder assignment popover */}
        {assigningSessionId === s.id && (
          <div
            style={{
              margin: '2px 0 6px 8px',
              padding: 6,
              background: 'var(--bg-2)',
              border: '1px solid var(--line-2)',
              borderRadius: 8,
              fontSize: 11.5,
              display: 'flex',
              flexDirection: 'column',
              gap: 3,
            }}
          >
            <div className="muted" style={{ fontSize: 10.5, fontWeight: 600 }}>
              {t('Gán vào Nhóm Chat (Chia sẻ Context):', 'Assign to Chat Folder (Shared Context):')}
            </div>
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => handleAssignFolder(s.id, '')}
              style={{ justifyContent: 'flex-start', padding: '3px 6px', fontSize: 11.5 }}
            >
              {t('— Không thuộc nhóm nào —', '— None —')}
            </button>
            {chatFolders.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`btn sm ${s.chat_project === f.id ? 'accent' : 'ghost'}`}
                onClick={() => handleAssignFolder(s.id, f.id)}
                style={{ justifyContent: 'flex-start', padding: '3px 6px', fontSize: 11.5 }}
              >
                <Folder size={11} style={{ marginRight: 5 }} />
                <span className="ellipsis">{f.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <aside
      id="side"
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        background: 'var(--bg-2)',
        overflow: 'hidden',
      }}
      aria-label={t('Thanh bên', 'Sidebar')}
    >
      {/* Top Brand Bar (ChatGPT Style) */}
      <div
        className="brand"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 10px 6px',
        }}
      >
        <img
          src="/img/logo-64.png"
          alt="PhD Lab Logo"
          width="24"
          height="24"
          style={{ borderRadius: 6 }}
        />
        <b style={{ fontSize: 13.5, letterSpacing: '-0.01em' }}>PhD Research Lab</b>
        <span className="grow" />
        <button
          className="icon sm"
          title={t('Tìm kiếm đoạn chat', 'Search chats')}
          onClick={() => setShowSearch((v) => !v)}
        >
          <Search size={15} />
        </button>
        <button
          className="icon sm"
          id="side-toggle"
          title={t('Thu gọn thanh bên', 'Collapse sidebar')}
          onClick={toggleSidebar}
        >
          <SidebarIcon size={15} />
        </button>
      </div>

      {/* Search Input (collapsible) */}
      {showSearch && (
        <div style={{ padding: '4px 10px' }}>
          <input
            type="search"
            placeholder={t('Tìm hội thoại…', 'Search chats…')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
            style={{
              width: '100%',
              padding: '5px 8px',
              borderRadius: 7,
              border: '1px solid var(--line-2)',
              background: 'var(--panel)',
              fontSize: 12,
            }}
          />
        </div>
      )}

      {/* Compact ChatGPT-Style Top Icon Action Rows */}
      <div style={{ padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <button
          type="button"
          className="btn sm ghost"
          onClick={() => {
            setActiveSessionId(null);
            setMainView('chat');
          }}
          style={{
            justifyContent: 'flex-start',
            padding: '7px 10px',
            borderRadius: 8,
            fontWeight: 500,
            gap: 8,
          }}
        >
          <SquarePen size={15} />
          <span>{t('Cuộc trò chuyện mới', 'New chat')}</span>
        </button>

        <button
          type="button"
          className={`btn sm ${mainView === 'office3d' ? 'accent' : 'ghost'}`}
          onClick={() => open3DOffice(true)}
          style={{
            justifyContent: 'flex-start',
            padding: '7px 10px',
            borderRadius: 8,
            fontWeight: 500,
            gap: 8,
          }}
        >
          <Bot size={15} />
          <span>{t('Phòng Lab 3D (University Lab)', '3D University Lab')}</span>
        </button>

        <button
          type="button"
          className="btn sm ghost"
          onClick={() => openDrawer('library')}
          style={{
            justifyContent: 'flex-start',
            padding: '6px 10px',
            borderRadius: 8,
            gap: 8,
          }}
        >
          <BookOpen size={15} />
          <span>{t('Thư viện Bài báo', 'Paper Library')}</span>
        </button>

        <button
          type="button"
          className="btn sm ghost"
          onClick={() => openDrawer('missions')}
          style={{
            justifyContent: 'flex-start',
            padding: '6px 10px',
            borderRadius: 8,
            gap: 8,
          }}
        >
          <Layers size={15} />
          <span>{t('Nhiệm vụ Tự hành (Missions)', 'Autonomous Missions')}</span>
        </button>

        {/* Active Workspace switcher pill */}
        <button
          type="button"
          className="btn sm ghost"
          onClick={() => openDrawer('projects')}
          style={{
            justifyContent: 'space-between',
            padding: '5px 10px',
            borderRadius: 8,
            fontSize: 11.5,
            color: 'var(--muted)',
          }}
        >
          <span className="ellipsis">
            Workspace: <b style={{ color: 'var(--fg)' }}>{project?.name || 'Default'}</b>
          </span>
          <ChevronDown size={13} />
        </button>
      </div>

      {/* Scrollable Pinned + Projects (Chat Folders) + Recents */}
      <nav
        id="threads"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '6px 8px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        {/* 1. PINNED CHATS */}
        {pinnedSessions.length > 0 && (
          <div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--muted)',
                padding: '2px 8px 4px',
                display: 'flex',
                alignItems: 'center',
                gap: 5,
              }}
            >
              <Pin size={11} />
              <span>{t('Đã ghim (Pinned)', 'Pinned')}</span>
            </div>
            {pinnedSessions.map((s) => renderSessionRow(s))}
          </div>
        )}

        {/* 2. PROJECTS / CHAT FOLDERS (Shared Context Memory like ChatGPT) */}
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--muted)',
              padding: '2px 8px 4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>{t('Nhóm Chat (Projects · Nhớ Context)', 'Projects (Shared Context)')}</span>
            <button
              type="button"
              className="icon sm"
              title={t('Tạo thư mục nhóm chat mới', 'New chat folder')}
              onClick={() => setCreatingFolder((v) => !v)}
              style={{ width: 20, height: 20 }}
            >
              <FolderPlus size={13} />
            </button>
          </div>

          {creatingFolder && (
            <div
              style={{
                padding: 8,
                marginBottom: 6,
                background: 'var(--panel)',
                border: '1px solid var(--line-2)',
                borderRadius: 8,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <input
                type="text"
                placeholder={t('Tên thư mục nhóm chat…', 'Folder name…')}
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                style={{
                  fontSize: 12,
                  padding: '5px 8px',
                  borderRadius: 6,
                  border: '1px solid var(--line-2)',
                  background: 'var(--bg)',
                }}
              />
              <textarea
                placeholder={t(
                  'Chỉ dẫn / Bối cảnh chung ghi nhớ cho mọi đoạn chat trong thư mục này…',
                  'Shared context instructions remembered across all chats in this folder…'
                )}
                rows={2}
                value={newFolderInstructions}
                onChange={(e) => setNewFolderInstructions(e.target.value)}
                style={{
                  fontSize: 11.5,
                  padding: '5px 8px',
                  borderRadius: 6,
                  border: '1px solid var(--line-2)',
                  background: 'var(--bg)',
                  resize: 'vertical',
                }}
              />
              <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn sm ghost"
                  onClick={() => setCreatingFolder(false)}
                >
                  {t('Hủy', 'Cancel')}
                </button>
                <button type="button" className="btn sm accent" onClick={handleCreateFolder}>
                  {t('Tạo Nhóm', 'Create')}
                </button>
              </div>
            </div>
          )}

          {/* Edit Folder Instructions Modal Inline */}
          {editingFolder && (
            <div
              style={{
                padding: 8,
                marginBottom: 6,
                background: 'var(--panel)',
                border: '1px solid var(--accent)',
                borderRadius: 8,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <div style={{ fontSize: 11.5, fontWeight: 600 }}>
                {t('Bộ nhớ Ngữ cảnh Thư mục:', 'Folder Shared Context:')}
              </div>
              <input
                type="text"
                value={editingFolder.name}
                onChange={(e) => setEditingFolder({ ...editingFolder, name: e.target.value })}
                style={{
                  fontSize: 12,
                  padding: '4px 7px',
                  borderRadius: 6,
                  border: '1px solid var(--line-2)',
                  background: 'var(--bg)',
                }}
              />
              <textarea
                rows={3}
                value={editingFolder.instructions || ''}
                onChange={(e) =>
                  setEditingFolder({ ...editingFolder, instructions: e.target.value })
                }
                placeholder={t(
                  'Chỉ dẫn chung & kiến thức chia sẻ giữa các đoạn chat trong nhóm…',
                  'Shared instructions & context across all chats in this folder…'
                )}
                style={{
                  fontSize: 11.5,
                  padding: '5px 7px',
                  borderRadius: 6,
                  border: '1px solid var(--line-2)',
                  background: 'var(--bg)',
                }}
              />
              <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn sm ghost"
                  onClick={() => setEditingFolder(null)}
                >
                  {t('Đóng', 'Close')}
                </button>
                <button type="button" className="btn sm accent" onClick={handleSaveEditFolder}>
                  {t('Lưu Context', 'Save')}
                </button>
              </div>
            </div>
          )}

          {/* Folder Items */}
          {chatFolders.map((folder) => {
            const isSelected = activeChatProjectId === folder.id;
            const folderCount = sessions.filter((s) => s.chat_project === folder.id).length;
            return (
              <div
                key={folder.id}
                onClick={() => {
                  setActiveChatProjectId(isSelected ? null : folder.id);
                  setMainView('chat');
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 8px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: isSelected ? 'var(--accent-soft)' : 'transparent',
                  color: isSelected ? 'var(--accent)' : 'inherit',
                  marginBottom: 2,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                  {isSelected ? <FolderOpen size={14} /> : <Folder size={14} />}
                  <span className="ellipsis" style={{ fontSize: 12.5, fontWeight: 500 }}>
                    {folder.name}
                  </span>
                  <span className="muted" style={{ fontSize: 10.5 }}>
                    ({folderCount})
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 2 }}>
                  <button
                    type="button"
                    className="icon sm"
                    title={t('Sửa Bối cảnh Chung (Context)', 'Edit Shared Context')}
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingFolder(folder);
                    }}
                    style={{ width: 20, height: 20, opacity: 0.65 }}
                  >
                    <Edit3 size={11} />
                  </button>
                  <button
                    type="button"
                    className="icon sm"
                    title={t('Xóa thư mục', 'Delete folder')}
                    onClick={(e) => handleDeleteFolder(e, folder.id)}
                    style={{ width: 20, height: 20, opacity: 0.65 }}
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* 3. RECENTS (Filtered by active folder if selected) */}
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: 'var(--muted)',
              padding: '2px 8px 4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span>
              {activeChatProjectId
                ? `${t('Trong nhóm:', 'In folder:')} ${
                    chatFolders.find((f) => f.id === activeChatProjectId)?.name || ''
                  }`
                : t('Gần đây (Recents)', 'Recents')}
            </span>
            {activeChatProjectId && (
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => setActiveChatProjectId(null)}
                style={{ padding: '1px 5px', fontSize: 10.5 }}
              >
                {t('Tất cả', 'All')}
              </button>
            )}
          </div>
          {recentSessions.map((s) => renderSessionRow(s))}
          {recentSessions.length === 0 && (
            <p className="muted" style={{ padding: '8px', fontSize: 12 }}>
              {t('Chưa có cuộc trò chuyện nào.', 'No conversations yet.')}
            </p>
          )}
        </div>
      </nav>

      {/* Bottom Compact Bar: More Tools + Settings */}
      <div
        className="side-menu-bar"
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 4,
          padding: '8px 10px',
          borderTop: '1px solid var(--line)',
        }}
      >
        <button
          className="btn ghost sm"
          id="nav-toggle"
          type="button"
          onClick={() => setMenuOpen(!menuOpen)}
          style={{ flex: 1, justifyContent: 'flex-start', gap: 6 }}
        >
          {menuOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span style={{ fontSize: 12 }}>{t('Công cụ Nghiên cứu', 'Research Studios')}</span>
          {pendingCount > 0 && <span className="count">{pendingCount}</span>}
        </button>

        <button
          type="button"
          className={`icon sm ${mainView === 'settings' ? 'active' : ''}`}
          onClick={() => openSettings()}
          title={t('Cài đặt Hệ thống', 'Settings')}
        >
          <Settings size={15} />
        </button>

        {menuOpen && (
          <div
            className="side-nav"
            style={{
              position: 'absolute',
              bottom: '100%',
              left: 8,
              right: 8,
              background: 'var(--panel)',
              border: '1px solid var(--line-2)',
              borderRadius: 10,
              boxShadow: 'var(--shadow)',
              padding: 6,
              zIndex: 100,
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              maxHeight: '70vh',
              overflowY: 'auto',
            }}
          >
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('topics');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Brain size={14} style={{ marginRight: 6 }} /> {t('Chủ đề · SKB', 'Topics · SKB')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('workstreams');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <GitBranch size={14} style={{ marginRight: 6 }} /> Workstreams
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('figures');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <BarChart3 size={14} style={{ marginRight: 6 }} /> Figure Studio
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('opencode');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Terminal size={14} style={{ marginRight: 6 }} /> OpenCode Runtime
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('intelligence');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Cpu size={14} style={{ marginRight: 6 }} /> Intelligence & RO-Crate
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('protocols');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <FlaskConical size={14} style={{ marginRight: 6 }} /> Protocols
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('claims');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <CheckCircle size={14} style={{ marginRight: 6 }} /> Claims & Evidence
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('paper');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <FileText size={14} style={{ marginRight: 6 }} /> Paper LaTeX
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                setMainView('review');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Award size={14} style={{ marginRight: 6 }} /> Peer Review R1–R3
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('code');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Code size={14} style={{ marginRight: 6 }} /> Code · VS Code
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                setMainView('dashboard');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Gauge size={14} style={{ marginRight: 6 }} /> Dashboard
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};
