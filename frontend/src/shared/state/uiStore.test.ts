import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useUIStore, useI18n } from './uiStore';
import type { Project, Topic } from '../api/types';

describe('uiStore', () => {
  beforeEach(() => {
    const s = useUIStore.getState();
    s.setLanguage('vi');
    s.setUiScale(1.0);
    s.setMainView('chat');
    s.setAgentStatusView('office3d');
    s.setActiveSessionId(null);
    s.setActiveChatProjectId(null);
    s.setSelectedLabObject(null);
    s.setSelectedAgentId(null);
    s.setSelectedMissionId(null);
    s.setOfficeChatOpen(true);
    s.setAgentsSocialMode(true);
    s.setPendingCount(0);
    s.setOffline(false);
  });

  it('manages language switching and i18n correctly', () => {
    const { setLanguage } = useUIStore.getState();
    expect(useUIStore.getState().language).toBe('vi');

    setLanguage('en');
    expect(useUIStore.getState().language).toBe('en');

    setLanguage('vi');
    expect(useUIStore.getState().language).toBe('vi');
  });

  it('manages UI scale and updates root font-size', () => {
    const { setUiScale } = useUIStore.getState();
    setUiScale(1.1);
    expect(useUIStore.getState().uiScale).toBe(1.1);
    expect(document.documentElement.style.fontSize).toBe('110%');
  });

  it('manages views, 3D office and drawer states with dedicated drawer kinds', () => {
    const s = useUIStore.getState();
    s.setMainView('office3d');
    expect(useUIStore.getState().mainView).toBe('office3d');

    s.openDrawer('library');
    expect(useUIStore.getState().drawerKind).toBe('library');

    s.closeDrawer();
    expect(useUIStore.getState().drawerKind).toBeNull();

    s.open3DOffice(true);
    expect(useUIStore.getState().mainView).toBe('office3d');
    expect(useUIStore.getState().officeFullscreen).toBe(true);

    // Test special drawer routing to main views
    s.openDrawer('agent-status');
    expect(useUIStore.getState().mainView).toBe('office3d');

    s.openDrawer('settings', 'providers');
    expect(useUIStore.getState().mainView).toBe('settings');
    expect(useUIStore.getState().settingsTab).toBe('providers');

    s.openDrawer('dashboard');
    expect(useUIStore.getState().mainView).toBe('dashboard');

    s.openDrawer('review');
    expect(useUIStore.getState().mainView).toBe('review');

    s.openSettings('autonomy');
    expect(useUIStore.getState().mainView).toBe('settings');
    expect(useUIStore.getState().settingsTab).toBe('autonomy');

    // Test toggleDrawer remembers last opened drawer
    s.openDrawer('missions');
    expect(useUIStore.getState().drawerKind).toBe('missions');
    expect(useUIStore.getState().lastDrawerKind).toBe('missions');

    s.toggleDrawer();
    expect(useUIStore.getState().drawerKind).toBeNull();
    // lastDrawerKind should still be 'missions'
    expect(useUIStore.getState().lastDrawerKind).toBe('missions');

    // Toggling again should restore 'missions'
    s.toggleDrawer();
    expect(useUIStore.getState().drawerKind).toBe('missions');

    s.closeDrawer();
    expect(useUIStore.getState().drawerKind).toBeNull();
  });

  it('manages projects, topics and active context synchronization', () => {
    const s = useUIStore.getState();
    const mockProjects: Project[] = [
      { name: 'Lab 1', data_dir: '/lab1' },
      { name: 'Lab 2', data_dir: '/lab2' },
    ];
    s.setProjects(mockProjects);
    expect(useUIStore.getState().projects).toHaveLength(2);

    const mockTopics: Topic[] = [
      { id: 't-1', title: 'Quantum AI', description: '', created: '', updated: '' },
      { id: 't-2', title: 'Graph Transformers', description: '', created: '', updated: '' },
    ];
    s.setTopics(mockTopics);
    expect(useUIStore.getState().topics).toHaveLength(2);

    s.setActiveTopic(mockTopics[0]);
    expect(useUIStore.getState().activeTopicId).toBe('t-1');

    s.setActiveTopicId('t-2');
    expect(useUIStore.getState().activeTopic?.title).toBe('Graph Transformers');

    s.setActiveTopic(null);
    expect(useUIStore.getState().activeTopicId).toBeNull();

    s.setProject({ name: 'Special Project', data_dir: '/data' });
    expect(useUIStore.getState().project?.name).toBe('Special Project');

    s.setOfficeFullscreen(false);
    expect(useUIStore.getState().officeFullscreen).toBe(false);
  });

  it('manages chat folders (Projects) and active session', () => {
    const s = useUIStore.getState();
    s.setActiveSessionId('session-123');
    expect(useUIStore.getState().activeSessionId).toBe('session-123');

    s.setActiveChatProjectId('folder-abc');
    expect(useUIStore.getState().activeChatProjectId).toBe('folder-abc');
  });

  it('manages 3D interactive objects, agents, sidebar toggle, and notifications', () => {
    const s = useUIStore.getState();
    s.setSelectedLabObject('hpc_opencode');
    expect(useUIStore.getState().selectedLabObject).toBe('hpc_opencode');

    s.setSelectedAgentId('agent-pi');
    expect(useUIStore.getState().selectedAgentId).toBe('agent-pi');

    s.setSelectedMissionId('mission-42');
    expect(useUIStore.getState().selectedMissionId).toBe('mission-42');

    s.setAgentStatusView('timeline');
    expect(useUIStore.getState().agentStatusView).toBe('timeline');

    s.setAgentsSocialMode(false);
    expect(useUIStore.getState().agentsSocialMode).toBe(false);

    s.setOfficeChatOpen(false);
    expect(useUIStore.getState().officeChatOpen).toBe(false);

    const initialSidebar = s.sidebarOpen;
    s.toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(!initialSidebar);

    s.setPendingCount(5);
    expect(useUIStore.getState().pendingCount).toBe(5);

    s.setOffline(true);
    expect(useUIStore.getState().offline).toBe(true);
  });

  it('useI18n hook handles dual-string fallback and translation keys in both languages', () => {
    const { result } = renderHook(() => useI18n());

    act(() => {
      result.current.setLanguage('vi');
    });
    expect(result.current.language).toBe('vi');
    expect(result.current.t('Xin chào', 'Hello')).toBe('Xin chào');

    act(() => {
      result.current.setLanguage('en');
    });
    expect(result.current.language).toBe('en');
    expect(result.current.t('Xin chào', 'Hello')).toBe('Hello');
    expect(result.current.t('chat.emptyGreeting')).toBeDefined();
  });
});
