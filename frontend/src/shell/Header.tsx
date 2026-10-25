import React from 'react';
import { useUIStore, useI18n } from '../shared/state/uiStore';
import {
  Menu,
  PanelRight,
  PanelRightClose,
  PanelRightOpen,
  ChevronDown,
  BarChart3,
  Terminal,
  Cpu,
  Bot,
  Gauge,
  Award,
  Sliders,
  MessageSquare,
  BookOpen,
  Compass,
  ZoomIn,
  HelpCircle,
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
    toggleDrawer,
    mainView,
    setMainView,
    open3DOffice,
    language,
    setLanguage,
    uiScale,
    setUiScale,
  } = useUIStore();
  const { t } = useI18n();

  const topicLabel = activeTopic ? activeTopic.title || activeTopic.name : '';

  const handlePanelToggle = () => {
    toggleDrawer();
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
        flexWrap: 'wrap',
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
      <div className="header-topic" style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
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
            {topicLabel || t('Chủ đề SKB', 'Topic SKB')}
          </span>
          <ChevronDown size={13} style={{ marginLeft: 3 }} />
        </button>
      </div>

      {/* Center: ChatGPT-Style Segmented Mode Pill Switcher */}
      <div
        className="header-modes"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: 4,
          borderRadius: 999,
          background: 'var(--bg-2)',
          border: '1px solid var(--line)',
        }}
      >
        <button
          type="button"
          className={`btn sm ${mainView === 'chat' ? 'accent' : 'ghost'}`}
          onClick={() => setMainView('chat')}
          title={t('Trò chuyện Nghiên cứu', 'Research Chat')}
          style={{ borderRadius: 999, padding: '5px 12px', minHeight: 28, gap: 5 }}
        >
          <MessageSquare size={14} />
          <span style={{ fontSize: 12 }}>{t('Trò chuyện', 'Chat')}</span>
        </button>
        <button
          type="button"
          className={`btn sm ${mainView === 'library' ? 'accent' : 'ghost'}`}
          onClick={() => setMainView('library')}
          title={t('Thư viện Bài báo & Tài liệu', 'Paper Library & Documents')}
          style={{ borderRadius: 999, padding: '5px 12px', minHeight: 28, gap: 5 }}
        >
          <BookOpen size={14} />
          <span style={{ fontSize: 12 }}>{t('Thư viện', 'Library')}</span>
        </button>
        <button
          type="button"
          className={`btn sm ${mainView === 'office3d' ? 'accent' : 'ghost'}`}
          onClick={() => open3DOffice(true)}
          title={t(
            'Không gian Phòng Lab Đại học 3D Toàn màn hình',
            'Full-Screen 3D University Research Lab'
          )}
          style={{ borderRadius: 999, padding: '5px 12px', minHeight: 28, gap: 5 }}
        >
          <Bot size={14} />
          <span style={{ fontSize: 12 }}>{t('Lab 3D', '3D Lab')}</span>
        </button>
        <button
          type="button"
          className={`btn sm ${mainView === 'harness' ? 'accent' : 'ghost'}`}
          onClick={() => setMainView('harness')}
          title={t(
            'Không gian Kiểm định & Thiết kế Quy trình Harness Studio Toàn màn hình',
            'Full-Space Visual Harness Studio & Evaluation Pipeline'
          )}
          style={{ borderRadius: 999, padding: '5px 12px', minHeight: 28, gap: 5 }}
        >
          <Sliders size={14} />
          <span style={{ fontSize: 12 }}>{t('Harness', 'Harness')}</span>
        </button>
        <button
          type="button"
          className={`btn sm ${mainView === 'review' ? 'accent' : 'ghost'}`}
          onClick={() => setMainView('review')}
          title={t('Hội đồng Bình duyệt R1–R3 & LaTeX', 'Peer Review R1–R3 & LaTeX')}
          style={{ borderRadius: 999, padding: '5px 10px', minHeight: 28, minWidth: 32, gap: 4 }}
        >
          <Award size={14} />
        </button>
        <button
          type="button"
          className={`btn sm ${mainView === 'dashboard' ? 'accent' : 'ghost'}`}
          onClick={() => setMainView('dashboard')}
          title={t('Bảng điều khiển Hệ thống', 'System Dashboard')}
          style={{ borderRadius: 999, padding: '5px 10px', minHeight: 28, minWidth: 32, gap: 4 }}
        >
          <Gauge size={14} />
        </button>
      </div>

      {/* Right: Icon-First Studio Bar + Language + Scale + Settings + Dedicated Panel Toggle */}
      <div className="header-tools" style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0, minWidth: 0 }}>
        {/* Collapsible/Scrollable Studio Shortcut Icons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 3, minWidth: 0 }}>
          <button
            className={`icon ${drawerKind === 'outline' ? 'active' : ''}`}
            type="button"
            onClick={() => openDrawer('outline')}
            title={t('Đề cương Nghiên cứu 5 Cấp độ', '5-Level Research Outline')}
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
            title={t('Xưởng Đồ họa Khoa học', 'Figure Studio')}
          >
            <BarChart3 size={16} />
          </button>
          <button
            className={`icon ${drawerKind === 'opencode' ? 'active' : ''}`}
            type="button"
            onClick={() => openDrawer('opencode')}
            title={t('Nhân Thực nghiệm Tính toán OpenCode', 'OpenCode Parallel Core')}
          >
            <Terminal size={16} />
          </button>
          <button
            className={`icon ${drawerKind === 'intelligence' ? 'active' : ''}`}
            type="button"
            onClick={() => openDrawer('intelligence')}
            title={t('Trung tâm Phân tích Tri thức', 'Unified Research Intelligence')}
          >
            <Cpu size={16} />
          </button>
        </div>

        {/* Language Toggle Pill (VI / EN) */}
        <button
          type="button"
          className="btn sm ghost"
          onClick={() => setLanguage(language === 'vi' ? 'en' : 'vi')}
          title={t('Chuyển đổi ngôn ngữ VI / ENG', 'Switch language VI / ENG')}
          aria-label={`${language.toUpperCase()} — ${t('Chuyển đổi ngôn ngữ VI / ENG', 'Switch language VI / ENG')}`}
          style={{
            borderRadius: 999,
            padding: '4px 10px',
            fontSize: 11,
            fontWeight: 700,
            border: '1px solid var(--line)',
            flexShrink: 0,
            minHeight: 26,
            minWidth: 32,
          }}
        >
          {language.toUpperCase()}
        </button>

        {/* UI Scale Button */}
        <button
          type="button"
          className="btn sm ghost"
          onClick={cycleScale}
          title={t('Tỉ lệ hiển thị giao diện', 'UI Display Scale')}
          aria-label={`${Math.round(uiScale * 100)}% — ${t('Tỉ lệ hiển thị giao diện', 'UI Display Scale')}`}
          style={{
            borderRadius: 999,
            padding: '4px 8px',
            fontSize: 11,
            border: '1px solid var(--line)',
            gap: 3,
            flexShrink: 0,
            minHeight: 26,
            minWidth: 44,
          }}
        >
          <ZoomIn size={12} />
          <span>{Math.round(uiScale * 100)}%</span>
        </button>

        {/* User Guide Button */}
        <button
          type="button"
          className={`icon ${drawerKind === 'guide' ? 'active' : ''}`}
          onClick={() => (drawerKind === 'guide' ? closeDrawer() : openDrawer('guide'))}
          title={t('Hướng dẫn Người dùng & Sổ tay Nghiên cứu', 'User Guide & Beginner Onboarding')}
          style={{ flexShrink: 0 }}
        >
          <HelpCircle size={16} />
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
            flexShrink: 0,
          }}
        />

        {/* Dedicated, prominent right-corner toggle button that NEVER gets pushed off-screen */}
        <button
          className={`btn sm ${drawerKind ? 'accent' : 'ghost'}`}
          id="panel-btn"
          title={
            drawerKind
              ? t('Ẩn bảng công cụ bên phải', 'Hide right tools panel')
              : t('Mở bảng công cụ bên phải', 'Open right tools panel')
          }
          aria-label={`${drawerKind ? t('Ẩn bảng công cụ', 'Hide panel') : t('Bảng công cụ', 'Tools panel')} — ${t('Bảng kết quả & công cụ', 'Inspector Drawer')}`}
          onClick={handlePanelToggle}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '4px 10px',
            borderRadius: 8,
            border: drawerKind ? '1px solid var(--accent)' : '1px solid var(--line)',
            background: drawerKind ? 'var(--accent-soft, var(--bg-2))' : 'var(--bg-2)',
            color: drawerKind ? 'var(--accent)' : 'var(--ink)',
            fontWeight: 600,
            fontSize: 12,
            flexShrink: 0,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
        >
          {drawerKind ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
          <span>{drawerKind ? t('Ẩn bảng công cụ', 'Hide panel') : t('Bảng công cụ', 'Tools panel')}</span>
        </button>
      </div>
    </header>
  );
};
