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
  MoreHorizontal,
  Compass,
  HelpCircle,
  MessageSquare,
  Sliders,
  ExternalLink,
  RefreshCw,
} from 'lucide-react';

export interface SidebarProps {
  collapsed?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed: propCollapsed }) => {
  const queryClient = useQueryClient();
  const {
    sidebarOpen,
    toggleSidebar,
    project,
    activeSessionId,
    setActiveSessionId,
    activeChatProjectId,
    setActiveChatProjectId,
    openDrawer,
    closeDrawer,
    drawerKind,
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
  const [sessionMenuOpenId, setSessionMenuOpenId] = useState<string | null>(null);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState('');

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
  const recentSessions = (
    activeChatProjectId
      ? filteredSessions.filter((s) => s.chat_project === activeChatProjectId)
      : filteredSessions
  ).filter((s) => !s.pinned);

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

  const handleRenameSession = async (sid: string, newTitle: string) => {
    if (!newTitle.trim()) {
      setRenamingSessionId(null);
      return;
    }
    await api.put(`/api/chat/sessions/${sid}`, { title: newTitle.trim() });
    setRenamingSessionId(null);
    queryClient.invalidateQueries({ queryKey: ['sessions'] });
  };

  const renderSessionRow = (s: ChatSession) => {
    const isActive = activeSessionId === s.id && mainView === 'chat';
    const isMenuOpen = sessionMenuOpenId === s.id;
    const isRenaming = renamingSessionId === s.id;

    if (isRenaming) {
      return (
        <form
          key={s.id}
          onSubmit={(e) => {
            e.preventDefault();
            handleRenameSession(s.id, renameTitle);
          }}
          onClick={(e) => e.stopPropagation()}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '4px 6px',
            background: 'var(--panel)',
            border: '1px solid var(--accent)',
            borderRadius: 8,
            marginBottom: 2,
          }}
        >
          <input
            autoFocus
            className="input sm"
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') setRenamingSessionId(null);
            }}
            placeholder={t('Tên đoạn chat…', 'Chat title…')}
            style={{ flex: 1, fontSize: 12, height: 26, padding: '2px 6px' }}
          />
          <button
            type="submit"
            className="btn sm accent"
            style={{ padding: '2px 8px', height: 26, fontSize: 11 }}
          >
            {t('Lưu', 'Save')}
          </button>
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => setRenamingSessionId(null)}
            style={{ padding: '2px 6px', height: 26, fontSize: 11 }}
          >
            ✕
          </button>
        </form>
      );
    }

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
            background: isActive ? 'var(--sel)' : isMenuOpen ? 'var(--line-2)' : 'transparent',
            borderRadius: 8,
            cursor: 'pointer',
            marginBottom: 2,
            gap: 6,
          }}
        >
          <div style={{ minWidth: 0, flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
            {s.pinned && (
              <span title={t('Đoạn chat đã ghim', 'Pinned conversation')} style={{ display: 'inline-flex', flexShrink: 0 }}>
                <Pin
                  size={11}
                  color="var(--accent)"
                  style={{ transform: 'rotate(25deg)' }}
                />
              </span>
            )}
            <div className="ellipsis" style={{ fontWeight: isActive ? 600 : 400, fontSize: 12.5 }}>
              {s.title || t('Phiên nghiên cứu mới', 'New conversation')}
            </div>
          </div>

          {/* Grouped Actions: Single ... button */}
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            <button
              type="button"
              className="icon sm thread-more-btn"
              title={t('Tùy chọn đoạn chat', 'Chat options')}
              onClick={(e) => {
                e.stopPropagation();
                setSessionMenuOpenId(isMenuOpen ? null : s.id);
              }}
              style={{
                width: 22,
                height: 22,
                opacity: isMenuOpen || isActive ? 0.9 : 0.6,
                borderRadius: 6,
                background: isMenuOpen ? 'var(--line-2)' : 'transparent',
              }}
            >
              <MoreHorizontal size={14} />
            </button>
          </div>
        </div>

        {/* Floating Context Menu */}
        {isMenuOpen && (
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
                setSessionMenuOpenId(null);
              }}
            />
            <div
              style={{
                position: 'absolute',
                top: '100%',
                right: 4,
                marginTop: 2,
                background: 'var(--panel)',
                border: '1px solid var(--line-2)',
                borderRadius: 8,
                boxShadow: 'var(--shadow)',
                padding: 4,
                zIndex: 95,
                minWidth: 180,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* 1. Pin / Unpin */}
              <button
                type="button"
                className="btn sm ghost"
                onClick={(e) => {
                  handleTogglePin(e, s);
                  setSessionMenuOpenId(null);
                }}
                style={{ justifyContent: 'flex-start', padding: '5px 8px', fontSize: 12 }}
              >
                <Pin
                  size={12}
                  style={{
                    marginRight: 6,
                    color: s.pinned ? 'var(--accent)' : 'inherit',
                  }}
                />
                <span>{s.pinned ? t('Bỏ ghim', 'Unpin') : t('Ghim đoạn chat', 'Pin chat')}</span>
              </button>

              {/* 2. Move to Folder */}
              <button
                type="button"
                className="btn sm ghost"
                onClick={(e) => {
                  e.stopPropagation();
                  setAssigningSessionId(assigningSessionId === s.id ? null : s.id);
                  setSessionMenuOpenId(null);
                }}
                style={{ justifyContent: 'flex-start', padding: '5px 8px', fontSize: 12 }}
              >
                <Folder size={12} style={{ marginRight: 6 }} />
                <span>{t('Chuyển vào nhóm chat…', 'Move to folder…')}</span>
              </button>

              {/* 3. Rename */}
              <button
                type="button"
                className="btn sm ghost"
                onClick={(e) => {
                  e.stopPropagation();
                  setRenamingSessionId(s.id);
                  setRenameTitle(s.title || '');
                  setSessionMenuOpenId(null);
                }}
                style={{ justifyContent: 'flex-start', padding: '5px 8px', fontSize: 12 }}
              >
                <Edit3 size={12} style={{ marginRight: 6 }} />
                <span>{t('Đổi tên', 'Rename')}</span>
              </button>

              <div style={{ height: 1, background: 'var(--line-2)', margin: '2px 0' }} />

              {/* 4. Delete / Archive */}
              <button
                type="button"
                className="btn sm ghost"
                onClick={(e) => {
                  handleDeleteSession(e, s.id);
                  setSessionMenuOpenId(null);
                }}
                style={{
                  justifyContent: 'flex-start',
                  padding: '5px 8px',
                  fontSize: 12,
                  color: 'var(--err)',
                }}
              >
                <Trash2 size={12} style={{ marginRight: 6 }} />
                <span>{t('Xóa cuộc trò chuyện', 'Delete conversation')}</span>
              </button>
            </div>
          </>
        )}

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

  const isCollapsed = propCollapsed !== undefined ? propCollapsed : !sidebarOpen;

  if (isCollapsed) {
    return (
      <aside
        id="side"
        className="sidebar-collapsed-rail"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          width: '100%',
          height: '100%',
          background: 'var(--bg-2)',
          padding: '8px 0',
          gap: 6,
          boxSizing: 'border-box',
          overflow: 'hidden',
        }}
        aria-label={t('Thanh bên thu gọn', 'Collapsed sidebar')}
      >
        {/* Top: PhD Lab Logo & Expand Button */}
        <button
          type="button"
          id="side-expand"
          className="icon sm"
          title={t('Mở rộng thanh bên', 'Expand sidebar')}
          aria-label={t('Mở rộng thanh bên', 'Expand sidebar')}
          onClick={toggleSidebar}
          style={{
            width: 38,
            height: 38,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            background: 'transparent',
            border: 'none',
            padding: 0,
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <img
            src="/img/logo-64.png"
            alt="PhD Lab Logo"
            width="24"
            height="24"
            style={{ borderRadius: 6 }}
          />
        </button>

        {/* 1. New Chat (SquarePen) */}
        <button
          type="button"
          id="side-rail-new-chat"
          className="icon sm"
          title={t('Cuộc trò chuyện mới', 'New chat')}
          aria-label={t('Cuộc trò chuyện mới', 'New chat')}
          onClick={() => {
            setActiveSessionId(null);
            setMainView('chat');
          }}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--ink)',
            cursor: 'pointer',
            background: 'transparent',
            border: 'none',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
            e.currentTarget.style.color = 'var(--accent)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.color = 'var(--ink)';
          }}
        >
          <SquarePen size={18} />
        </button>

        {/* 2. Search (Search) */}
        <button
          type="button"
          id="side-rail-search"
          className="icon sm"
          title={t('Tìm kiếm đoạn chat', 'Search chats')}
          aria-label={t('Tìm kiếm đoạn chat', 'Search chats')}
          onClick={() => {
            toggleSidebar();
            setShowSearch(true);
          }}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--ink)',
            cursor: 'pointer',
            background: 'transparent',
            border: 'none',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
            e.currentTarget.style.color = 'var(--accent)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.color = 'var(--ink)';
          }}
        >
          <Search size={18} />
        </button>

        {/* 3. Pinned (Pin) */}
        <button
          type="button"
          id="side-rail-pinned"
          className="icon sm"
          title={t('Đoạn chat đã ghim', 'Pinned chats')}
          aria-label={t('Đoạn chat đã ghim', 'Pinned chats')}
          onClick={toggleSidebar}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: pinnedSessions.length > 0 ? 'var(--accent)' : 'var(--ink)',
            cursor: 'pointer',
            background: 'transparent',
            border: 'none',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <Pin size={18} />
        </button>

        {/* 4. Chat History / Recents (MessageSquare) */}
        <button
          type="button"
          id="side-rail-recents"
          className="icon sm"
          title={t('Lịch sử đoạn chat gần đây', 'Recent chat history')}
          aria-label={t('Lịch sử đoạn chat gần đây', 'Recent chat history')}
          onClick={toggleSidebar}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--ink)',
            cursor: 'pointer',
            background: 'transparent',
            border: 'none',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <MessageSquare size={18} />
        </button>

        {/* 5. Paper Library (BookOpen) */}
        <button
          type="button"
          id="side-rail-library"
          className="icon sm"
          title={t('Thư viện bài báo', 'Paper Library')}
          aria-label={t('Thư viện bài báo', 'Paper Library')}
          onClick={() => setMainView('library')}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: mainView === 'library' ? 'var(--accent)' : 'var(--ink)',
            background: mainView === 'library' ? 'var(--panel)' : 'transparent',
            cursor: 'pointer',
            border: 'none',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = mainView === 'library' ? 'var(--panel)' : 'transparent';
          }}
        >
          <BookOpen size={18} />
        </button>

        {/* 6. 3D University Lab (FlaskConical / Bot) */}
        <button
          type="button"
          id="side-rail-3dlab"
          className="icon sm"
          title={t('Lab 3D Trường Đại học', '3D University Lab')}
          aria-label={t('Lab 3D Trường Đại học', '3D University Lab')}
          onClick={() => open3DOffice()}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: mainView === 'office3d' ? 'var(--accent)' : 'var(--ink)',
            background: mainView === 'office3d' ? 'var(--panel)' : 'transparent',
            cursor: 'pointer',
            border: 'none',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = mainView === 'office3d' ? 'var(--panel)' : 'transparent';
          }}
        >
          <Bot size={18} />
        </button>

        {/* 7. Autonomous Missions (Compass) */}
        <button
          type="button"
          id="side-rail-missions"
          className="icon sm"
          title={t('Nhiệm vụ tự trị', 'Autonomous Missions')}
          aria-label={t('Nhiệm vụ tự trị', 'Autonomous Missions')}
          onClick={() => openDrawer('missions')}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: drawerKind === 'missions' ? 'var(--accent)' : 'var(--ink)',
            background: drawerKind === 'missions' ? 'var(--panel)' : 'transparent',
            cursor: 'pointer',
            border: 'none',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = drawerKind === 'missions' ? 'var(--panel)' : 'transparent';
          }}
        >
          <Compass size={18} />
        </button>

        <div style={{ flex: 1 }} />

        {/* Bottom 1: User Guide */}
        <button
          type="button"
          id="side-rail-guide"
          className="icon sm"
          title={t('Hướng dẫn sử dụng', 'User Guide')}
          aria-label={t('Hướng dẫn sử dụng', 'User Guide')}
          onClick={() => setMainView('guide')}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: mainView === 'guide' ? 'var(--accent)' : 'var(--ink)',
            background: mainView === 'guide' ? 'var(--panel)' : 'transparent',
            cursor: 'pointer',
            border: 'none',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--panel)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = mainView === 'guide' ? 'var(--panel)' : 'transparent';
          }}
        >
          <HelpCircle size={18} />
        </button>

        {/* Bottom 2: Settings / User Profile Avatar (matching ChatGPT Image 2 bottom avatar) */}
        <button
          type="button"
          id="side-rail-settings"
          className="icon sm"
          title={t('Cài đặt & Hồ sơ', 'Settings & Profile')}
          aria-label={t('Cài đặt & Hồ sơ', 'Settings & Profile')}
          onClick={() => openSettings()}
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            background: 'transparent',
            border: 'none',
            padding: 0,
            transition: 'transform 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'scale(1.08)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #4f46e5, #06b6d4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontSize: 13,
              fontWeight: 700,
              boxShadow: '0 2px 5px rgba(0,0,0,0.15)',
            }}
          >
            P
          </div>
        </button>
      </aside>
    );
  }

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
          <span>{t('Phòng Lab 3D', '3D University Lab')}</span>
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
          <span>{t('Nhiệm vụ Tự hành', 'Autonomous Missions')}</span>
        </button>

        <button
          type="button"
          className="btn sm ghost"
          onClick={() => {
            setMainView('harness');
            if (window.matchMedia('(max-width: 820px)').matches && sidebarOpen) toggleSidebar();
          }}
          style={{
            justifyContent: 'flex-start',
            padding: '6px 10px',
            borderRadius: 8,
            gap: 8,
            color: mainView === 'harness' ? 'var(--accent)' : undefined,
            background: mainView === 'harness' ? 'var(--panel)' : 'transparent',
          }}
        >
          <Sliders size={15} />
          <span>{t('Harness Studio', 'Harness Studio')}</span>
        </button>

        <button
          type="button"
          className="btn sm ghost"
          onClick={() => openDrawer('cli')}
          style={{
            justifyContent: 'flex-start',
            padding: '6px 10px',
            borderRadius: 8,
            gap: 8,
            color: drawerKind === 'cli' ? 'var(--accent)' : undefined,
          }}
          title={t('Mở Giao diện Dòng lệnh Claude CLI Học thuật', 'Open Academic Claude CLI Terminal Studio')}
        >
          <Terminal size={15} />
          <span>{t('Claude CLI Học thuật', 'Claude CLI Terminal')}</span>
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
            {t('Không gian làm việc:', 'Workspace:')} <b style={{ color: 'var(--fg)' }}>{project?.name || t('Mặc định', 'Default')}</b>
          </span>
          <ChevronDown size={13} />
        </button>

        {/* Quick App Providers & Sync Strip */}
        <div
          style={{
            padding: '7px 9px',
            borderRadius: 8,
            background: 'var(--bg-2)',
            border: '1px solid var(--line)',
            display: 'flex',
            flexDirection: 'column',
            gap: 5,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {t('Ứng dụng Nhanh & Đồng bộ', 'Quick Apps & Sync')}
            </span>
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => openSettings('models')}
              title={t('Mở Cài đặt Nhà cung cấp', 'Open Provider Settings')}
              style={{ fontSize: 10.5, padding: '1px 6px', height: 'auto', borderRadius: 4 }}
            >
              {t('Tất cả', 'All')}
            </button>
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {[
              { id: 'chatgpt', label: 'ChatGPT', title: 'OpenAI ChatGPT' },
              { id: 'claude', label: 'Claude', title: 'Anthropic Claude' },
              { id: 'opencode', label: 'OpenCode', title: 'OpenCode' },
              { id: 'antigravity', label: 'Antigravity', title: 'Google Antigravity' },
              { id: 'feynman', label: 'Feynman', title: 'Feynman AI' },
              { id: 'lmstudio', label: 'LM Studio', title: 'LM Studio' },
            ].map((app) => (
              <div
                key={app.id}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  background: 'var(--panel)',
                  border: '1px solid var(--line)',
                  borderRadius: 6,
                  overflow: 'hidden',
                  fontSize: 11,
                }}
              >
                <button
                  type="button"
                  onClick={() => api.post(`/api/providers/${app.id}/launch`, {})}
                  title={t('Mở trực tiếp ', 'Open directly ') + app.title}
                  style={{
                    padding: '3px 6px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--fg)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 3,
                  }}
                >
                  <ExternalLink size={10} />
                  <span>{app.label}</span>
                </button>
                <button
                  type="button"
                  onClick={() => api.post(`/api/providers/${app.id}/sync`, {})}
                  title={t('Đồng bộ dữ liệu từ ', 'Sync data from ') + app.title}
                  style={{
                    minWidth: 24,
                    minHeight: 24,
                    padding: '3px 5px',
                    background: 'var(--bg-2)',
                    border: 'none',
                    borderLeft: '1px solid var(--line)',
                    cursor: 'pointer',
                    color: 'var(--accent)',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <RefreshCw size={10} />
                </button>
              </div>
            ))}
          </div>
        </div>
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
              <span>{t('Đã ghim', 'Pinned')}</span>
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
            <span>{t('Nhóm Chat Nghiên cứu', 'Chat Projects')}</span>
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
                    title={t('Chỉnh sửa Ngữ cảnh Chung', 'Edit Shared Context')}
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
                : t('Gần đây', 'Recents')}
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
          className={`icon sm ${drawerKind === 'guide' ? 'active' : ''}`}
          onClick={() => (drawerKind === 'guide' ? closeDrawer() : openDrawer('guide'))}
          title={t('Hướng dẫn Người dùng', 'User Guide & Onboarding')}
        >
          <HelpCircle size={15} />
        </button>

        <button
          type="button"
          className={`icon sm ${mainView === 'settings' ? 'active' : ''}`}
          onClick={() => openSettings()}
          id="side-settings-btn"
          title={t('Cài đặt Hệ thống', 'System Settings')}
          aria-label={t('Cài đặt Hệ thống', 'System Settings')}
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
                openDrawer('guide');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start', color: 'var(--accent)', fontWeight: 600 }}
            >
              <HelpCircle size={14} style={{ marginRight: 6 }} /> {t('Sổ tay Người dùng', 'User Guide & Manual')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('library');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <BookOpen size={14} style={{ marginRight: 6 }} /> {t('Thư viện Bài báo', 'Paper Library & Search')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('outline');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Compass size={14} style={{ marginRight: 6 }} /> {t('Đề cương Nghiên cứu 5 Cấp độ', '5-Level Research Outline')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('topics');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Brain size={14} style={{ marginRight: 6 }} /> {t('Chủ đề Nghiên cứu', 'Research Topics')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('workstreams');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <GitBranch size={14} style={{ marginRight: 6 }} /> {t('Luồng công việc', 'Workstreams')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('figures');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <BarChart3 size={14} style={{ marginRight: 6 }} /> {t('Xưởng biểu đồ', 'Figure Studio')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('opencode');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Terminal size={14} style={{ marginRight: 6 }} /> {t('Môi trường OpenCode', 'OpenCode Runtime')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('intelligence');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Cpu size={14} style={{ marginRight: 6 }} /> {t('Tri thức & RO-Crate', 'Intelligence & RO-Crate')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('protocols');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <FlaskConical size={14} style={{ marginRight: 6 }} /> {t('Giao thức nghiên cứu', 'Protocols')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('claims');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <CheckCircle size={14} style={{ marginRight: 6 }} /> {t('Luận điểm & Bằng chứng', 'Claims & Evidence')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('paper');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <FileText size={14} style={{ marginRight: 6 }} /> {t('Bản thảo LaTeX', 'Paper LaTeX')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                setMainView('review');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Award size={14} style={{ marginRight: 6 }} /> {t('Hội đồng bình duyệt R1–R3', 'Peer Review R1–R3')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                openDrawer('code');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Code size={14} style={{ marginRight: 6 }} /> {t('Mã nguồn & VS Code', 'Code · VS Code')}
            </button>
            <button
              className="btn sm ghost"
              onClick={() => {
                setMainView('dashboard');
                setMenuOpen(false);
              }}
              style={{ justifyContent: 'flex-start' }}
            >
              <Gauge size={14} style={{ marginRight: 6 }} /> {t('Bảng điều khiển', 'Dashboard')}
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};
