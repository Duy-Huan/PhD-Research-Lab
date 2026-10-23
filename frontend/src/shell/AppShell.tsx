import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Group, Panel, Separator } from 'react-resizable-panels';
import { useUIStore, useI18n } from '../shared/state/uiStore';
import { useAppBus } from '../shared/events/useAppBus';
import { api } from '../shared/api/client';
import type { AppConfig, Project } from '../shared/api/types';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { ChatCenter } from '../features/chat/ChatCenter';
import { ContextualDrawer } from './ContextualDrawer';
import { AgentStatusView } from '../features/agent-status/AgentStatusView';
import { SettingsModal, applyThemeById } from '../features/settings/SettingsModal';
import { DashboardView } from '../features/dashboard/DashboardView';
import { ReviewView } from '../features/review/ReviewView';

export const AppShell: React.FC = () => {
  const { setProject, setProjects, mainView, sidebarOpen, drawerKind, setLanguage, uiScale } =
    useUIStore();
  const { t } = useI18n();
  const { isConnected } = useAppBus();

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
      case 'settings':
        return <SettingsModal />;
      case 'dashboard':
        return <DashboardView />;
      case 'review':
        return <ReviewView />;
      case 'chat':
      default:
        return <ChatCenter />;
    }
  };

  return (
    <div id="app" style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      <Group orientation="horizontal" style={{ width: '100%', height: '100%' }}>
        {sidebarOpen && (
          <>
            <Panel
              id="sidebar-panel"
              defaultSize="19%"
              minSize="13%"
              maxSize="32%"
              style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
            >
              <Sidebar />
            </Panel>
            <Separator
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
  );
};
