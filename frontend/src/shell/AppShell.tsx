import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Group, Panel, Separator } from 'react-resizable-panels';
import { MotionConfig } from 'motion/react';
import { useUIStore, useI18n } from '../shared/state/uiStore';
import { useAppBus } from '../shared/events/useAppBus';
import { api } from '../shared/api/client';
import type { AppConfig, Project } from '../shared/api/types';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { ChatCenter } from '../features/chat/ChatCenter';
import { ContextualDrawer } from './ContextualDrawer';
import { AgentStatusView } from '../features/agent-status/AgentStatusView';
import { SettingsModal, applyThemeById, applyFontById } from '../features/settings/SettingsModal';
import { DashboardView } from '../features/dashboard/DashboardView';
import { ReviewView } from '../features/review/ReviewView';
import { LibraryPanel } from '../features/library/LibraryPanel';
import { UserGuidePanel } from '../features/guide/UserGuidePanel';
import { CustomHarnessStudio } from '../features/harness/CustomHarnessStudio';
import { ClaudeCLIStudio } from '../features/cli/ClaudeCLIStudio';
import { PanelRightOpen } from 'lucide-react';

export const AppShell: React.FC = () => {
  const {
    setProject,
    setProjects,
    mainView,
    activeTopicId,
    sidebarOpen,
    toggleSidebar,
    drawerKind,
    lastDrawerKind,
    openDrawer,
    setLanguage,
    uiScale,
  } = useUIStore();
  const { t } = useI18n();
  const motionEnabled = useUIStore((st) => st.motionEnabled);
  const { isConnected } = useAppBus();

  // Split panes become overlays on small screens; do not reserve a hidden sidebar column.
  useEffect(() => {
    const media = window.matchMedia('(max-width: 820px)');
    const collapse = () => {
      if (media.matches && useUIStore.getState().sidebarOpen) toggleSidebar();
    };
    collapse();
    media.addEventListener('change', collapse);
    return () => media.removeEventListener('change', collapse);
  }, [toggleSidebar]);

  useEffect(() => {
    if ((drawerKind || mainView === 'settings' || mainView === 'cli') && window.matchMedia('(max-width: 820px)').matches && useUIStore.getState().sidebarOpen) toggleSidebar();
  }, [drawerKind, mainView, toggleSidebar]);

  // Load app config & projects on boot
  const { data: config } = useQuery<AppConfig>({
    queryKey: ['config'],
    queryFn: () => api.get<AppConfig>('/api/config'),
  });

  const { data: projectsData } = useQuery<{ projects: Project[] }>({
    queryKey: ['projects'],
    queryFn: () => api.get<{ projects: Project[] }>('/api/projects'),
  });

  useEffect(() => {
    if (config?.project) {
      setProject(config.project);
    }
    if (config?.ui?.theme) {
      applyThemeById(config.ui.theme);
    }
    if (config?.ui?.prose_font) {
      applyFontById(config.ui.prose_font);
    }
    if (config?.ui?.language === 'en' || config?.ui?.language === 'vi') {
      setLanguage(config.ui.language);
    }
  }, [config, setProject, setLanguage]);

  useEffect(() => {
    document.documentElement.style.fontSize = `${Math.round(uiScale * 100)}%`;
  }, [uiScale]);

  useEffect(() => {
    if (projectsData?.projects) {
      setProjects(projectsData.projects);
    }
  }, [projectsData, setProjects]);

  const renderMainStage = () => {
    switch (mainView) {
      case 'office3d':
        return <AgentStatusView />;
      case 'harness':
        return (
          <div
            id="harness-space-viewport"
            style={{
              flex: 1,
              height: '100%',
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              position: 'relative',
              background: 'var(--bg)',
            }}
          >
            <CustomHarnessStudio topicId={activeTopicId || undefined} isFullSpace={true} />
          </div>
        );
      case 'settings':
        return <SettingsModal />;
      case 'dashboard':
        return <DashboardView />;
      case 'review':
        return <ReviewView />;
      case 'library':
        return (
          <div
            style={{
              flex: 1,
              height: '100%',
              overflowY: 'auto',
              padding: '16px 24px',
              background: 'var(--bg)',
            }}
          >
            <div style={{ maxWidth: 1100, margin: '0 auto', height: '100%' }}>
              <LibraryPanel />
            </div>
          </div>
        );
      case 'guide':
        return (
          <div
            style={{
              flex: 1,
              height: '100%',
              overflowY: 'auto',
              background: 'var(--bg)',
            }}
          >
            <UserGuidePanel />
          </div>
        );
      case 'cli':
        return <ClaudeCLIStudio />;
      case 'chat':
      default:
        return <ChatCenter />;
    }
  };

  return (
    // v6.6.2: "user" follows the OS reduced-motion setting; the Settings toggle can turn all motion off.
    <MotionConfig reducedMotion={motionEnabled ? 'user' : 'always'}>
    <div id="app" className="react-shell" style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {!sidebarOpen && (
        <div
          id="sidebar-collapsed-rail"
          style={{
            width: 52,
            minWidth: 52,
            maxWidth: 52,
            height: '100%',
            flexShrink: 0,
            background: 'var(--bg-2)',
            borderRight: '1px solid var(--line)',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 10,
            boxSizing: 'border-box',
          }}
        >
          <Sidebar collapsed={true} />
        </div>
      )}

      <Group orientation="horizontal" style={{ width: sidebarOpen ? '100%' : 'calc(100% - 52px)', height: '100%' }}>
        {sidebarOpen && (
          <>
            <Panel
              id="sidebar-panel"
              defaultSize="19%"
              minSize="13%"
              maxSize="32%"
              style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
            >
              <Sidebar collapsed={false} />
            </Panel>
            <Separator
              onDoubleClick={toggleSidebar}
              title={t('Kéo để thay đổi kích thước, nhấp đúp để thu nhỏ/mở rộng', 'Drag to resize, double-click to collapse/expand')}
              style={{
                width: 4,
                background: 'var(--line)',
                cursor: 'col-resize',
                transition: 'background 0.15s',
              }}
            />
          </>
        )}

        <Panel
          id="main-stage-panel"
          defaultSize={drawerKind ? '53%' : sidebarOpen ? '81%' : '100%'}
          minSize="34%"
          style={{ display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}
        >
          <main
            id="main"
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              minWidth: 0,
              height: '100%',
              overflow: 'hidden',
            }}
          >
            {!isConnected && (
              <div className="banner" id="offline">
                <span>
                  {t(
                    'Mất kết nối tới máy chủ PhD Lab — đang thử kết nối lại…',
                    'Disconnected from PhD Lab server — reconnecting…'
                  )}
                </span>
              </div>
            )}
            <Header isLive={isConnected} />
            <div
              style={{
                flex: 1,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
              }}
            >
              {renderMainStage()}

              {/* Persistent right-edge floating handle when right drawer is closed */}
              {!drawerKind && (
                <button
                  id="floating-drawer-toggle"
                  type="button"
                  onClick={() => openDrawer(lastDrawerKind || 'outline')}
                  title={t('Mở bảng công cụ bên phải (Menu phải)', 'Open right inspector menu')}
                  aria-label={`${t('Menu phải', 'Right Menu')} — ${t('Mở menu bên phải', 'Open right menu')}`}
                  style={{
                    position: 'absolute',
                    top: 14,
                    right: 0,
                    zIndex: 25,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '6px 8px 6px 10px',  // icon only (name in title/aria-label): covers no view's controls
                    background: 'var(--panel)',
                    border: '1px solid var(--line)',
                    borderRight: 'none',
                    borderTopLeftRadius: 999,
                    borderBottomLeftRadius: 999,
                    boxShadow: '-2px 3px 10px rgba(0,0,0,0.08)',
                    cursor: 'pointer',
                    color: 'var(--ink)',
                    fontSize: 12,
                    fontWeight: 600,
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--bg-2)';
                    e.currentTarget.style.color = 'var(--accent)';
                    e.currentTarget.style.paddingLeft = '14px';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'var(--panel)';
                    e.currentTarget.style.color = 'var(--ink)';
                    e.currentTarget.style.paddingLeft = '10px';
                  }}
                >
                  <PanelRightOpen size={16} />
                </button>
              )}
            </div>
          </main>
        </Panel>

        {drawerKind && (
          <>
            <Separator
              style={{
                width: 5,
                background: 'var(--line)',
                cursor: 'col-resize',
                transition: 'background 0.15s',
              }}
            />
            <Panel
              id="drawer-panel"
              defaultSize="28%"
              minSize="20%"
              maxSize="58%"
              style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
            >
              <ContextualDrawer />
            </Panel>
          </>
        )}
      </Group>
    </div>
    </MotionConfig>
  );
};
