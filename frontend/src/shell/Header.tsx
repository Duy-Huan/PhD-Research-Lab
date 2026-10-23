import React from 'react';
import { useUIStore, useI18n } from '../shared/state/uiStore';
import {
  Menu,
  PanelRight,
  ChevronDown,
  BarChart3,
  Terminal,
  Cpu,
  Bot,
  Settings,
  Gauge,
  Award,
  MessageSquare,
  BookOpen,
  Compass,
  ZoomIn,
} from 'lucide-react';

interface HeaderProps {
  title?: string;
  crumb?: string;
  isLive?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ isLive = true }) => {
  const {
    sidebarOpen,
    toggleSidebar,
    activeTopic,
    openDrawer,
    drawerKind,
    closeDrawer,
    mainView,
    setMainView,
    open3DOffice,
    openSettings,
    language,
    setLanguage,
    uiScale,
    setUiScale,
  } = useUIStore();
  const { t } = useI18n();

  const topicLabel = activeTopic ? activeTopic.title || activeTopic.name : '';

  const handlePanelToggle = () => {
    if (drawerKind) {
      closeDrawer();
    } else {
      openDrawer('outline');
    }
  };

  const cycleScale = () => {
    const scales = [0.9, 1.0, 1.08, 1.15];
    const idx = scales.findIndex((s) => Math.abs(s - uiScale) < 0.03);
    const next = scales[(idx + 1) % scales.length];
    setUiScale(next);
  };

  return (
    <header
      id="top"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        padding: '6px 12px',
        borderBottom: '1px solid var(--line)',
        background: 'var(--panel)',
        flexShrink: 0,
      }}
    >
      {/* Left: Sidebar Toggle + Topic Pill */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        {!sidebarOpen && (
          <button
            className="icon"
            id="side-open"
            title={t('Mở thanh bên', 'Open sidebar')}
            aria-label={t('Mở thanh bên', 'Open sidebar')}
            onClick={toggleSidebar}
          >
            <Menu size={17} />
          </button>
        )}

        <button
          className="btn sm ghost"
          id="topic-btn"
          type="button"
          onClick={() => openDrawer('topics')}
          title={t('Chọn Chủ đề Nghiên cứu & SKB', 'Select Research Topic & SKB')}
          style={{
            borderRadius: 999,
            padding: '4px 10px',
            fontSize: 12,
            border: '1px solid var(--line)',
          }}
        >
          <span className="ellipsis" style={{ maxWidth: 160 }}>
            {topicLabel || t('Topic SKB', 'Topic SKB')}
          </span>
          <ChevronDown size={13} style={{ marginLeft: 3 }} />
        </button>
      </div>

      {/* Center: ChatGPT-Style Segmented Mode Pill Switcher */}
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 2,
          padding: 3,
          borderRadius: 999,
          background: 'var(--bg-2)',
          border: '1px solid var(--line)',
        }}
      >
        <button
          type="button"
          className={`btn sm ${mainView === 'chat' ? 'accent' : 'ghost'}`}
          onClick={() => setMainView('chat')}
          title={t('Trò chuyện Nghiên cứu (Chat)', 'Research Chat')}
          style={{ borderRadius: 999, padding: '4px 12px', gap: 5 }}
        >
          <MessageSquare size={14} />
          <span style={{ fontSize: 12 }}>Chat</span>
        </button>
        <button
          type="button"
          className={`btn sm ${mainView === 'office3d' ? 'accent' : 'ghost'}`}
          onClick={() => open3DOffice(true)}
          title={t(
            'Không gian Phòng Lab Đại học 3D Toàn màn hình',
            'Full-Screen 3D University Research Lab'
          )}
          style={{ borderRadius: 999, padding: '4px 12px', gap: 5 }}
        >
          <Bot size={14} />
          <span style={{ fontSize: 12 }}>3D Lab</span>
        </button>
        <button
          type="button"
          className={`btn sm ${mainView === 'review' ? 'accent' : 'ghost'}`}
          onClick={() => setMainView('review')}
          title={t('Hội đồng Bình duyệt R1–R3 & LaTeX', 'Peer Review R1–R3 & LaTeX')}
          style={{ borderRadius: 999, padding: '4px 10px', gap: 4 }}
        >
          <Award size={14} />
        </button>
        <button
          type="button"
          className={`btn sm ${mainView === 'dashboard' ? 'accent' : 'ghost'}`}
          onClick={() => setMainView('dashboard')}
          title={t('Bảng điều khiển Hệ thống (Dashboard)', 'System Dashboard')}
          style={{ borderRadius: 999, padding: '4px 10px', gap: 4 }}
        >
          <Gauge size={14} />
        </button>
      </div>

      {/* Right: Icon-First Studio Bar + Language + Scale + Settings */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button
          className={`icon ${drawerKind === 'outline' ? 'active' : ''}`}
          type="button"
          onClick={() => openDrawer('outline')}
          title={t('Đề cương 5 cấp độ (Outline)', '5-Level Research Outline')}
        >
          <Compass size={16} />
        </button>
        <button
          className={`icon ${drawerKind === 'library' ? 'active' : ''}`}
          type="button"
          onClick={() => openDrawer('library')}
          title={t('Thư viện PDF & Tìm kiếm bài báo', 'PDF Library & Paper Search')}
        >
          <BookOpen size={16} />
        </button>
        <button
          className={`icon ${drawerKind === 'figures' ? 'active' : ''}`}
          type="button"
          onClick={() => openDrawer('figures')}
          title="Figure Studio (v6.4.0)"
        >
          <BarChart3 size={16} />
        </button>
        <button
          className={`icon ${drawerKind === 'opencode' ? 'active' : ''}`}
          type="button"
          onClick={() => openDrawer('opencode')}
          title="OpenCode Parallel Core (v6.4.1)"
        >
          <Terminal size={16} />
        </button>
        <button
          className={`icon ${drawerKind === 'intelligence' ? 'active' : ''}`}
          type="button"
          onClick={() => openDrawer('intelligence')}
          title="Unified Research Intelligence (v6.4.2)"
        >
          <Cpu size={16} />
        </button>

        {/* Language Toggle Pill (VI / EN) */}
        <button
          type="button"
          className="btn sm ghost"
          onClick={() => setLanguage(language === 'vi' ? 'en' : 'vi')}
          title={t('Chuyển đổi ngôn ngữ VI / ENG', 'Switch language VI / ENG')}
          style={{
            borderRadius: 999,
            padding: '3px 8px',
            fontSize: 11,
            fontWeight: 700,
            border: '1px solid var(--line)',
          }}
        >
          {language.toUpperCase()}
        </button>

        {/* UI Scale Button */}
        <button
          type="button"
          className="btn sm ghost"
          onClick={cycleScale}
          title={t('Tỉ lệ hiển thị giao diện (Scale)', 'UI Display Scale')}
          style={{
            borderRadius: 999,
            padding: '3px 7px',
            fontSize: 11,
            border: '1px solid var(--line)',
            gap: 3,
          }}
        >
          <ZoomIn size={12} />
          <span>{Math.round(uiScale * 100)}%</span>
        </button>

        {/* Settings Icon */}
        <button
          type="button"
          className={`icon ${mainView === 'settings' ? 'active' : ''}`}
          onClick={() => openSettings()}
          title={t('Cài đặt Hệ thống & Models', 'System & Model Settings')}
        >
          <Settings size={16} />
        </button>

        <span
          className={`dot ${isLive ? 'active' : ''}`}
          id="live"
          title={
            isLive
              ? t('Trực tuyến', 'Connected to PhD Lab server')
              : t('Đang kết nối lại…', 'Reconnecting…')
          }
          style={{
            display: 'inline-block',
            width: 7,
            height: 7,
            borderRadius: '50%',
            backgroundColor: isLive ? 'var(--ok)' : 'var(--muted)',
            margin: '0 3px',
          }}
        />

        <button
          className={`icon ${drawerKind ? 'active' : ''}`}
          id="panel-btn"
          title={t('Đóng/Mở Bảng Công cụ', 'Toggle Inspector Drawer')}
          aria-label={t('Bảng kết quả & công cụ', 'Inspector Drawer')}
          onClick={handlePanelToggle}
        >
          <PanelRight size={17} />
        </button>
      </div>
    </header>
  );
};
