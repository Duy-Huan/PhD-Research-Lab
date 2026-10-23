import { create } from 'zustand';
import type { Project, Topic } from '../api/types';

export type DrawerKind =
  | 'topics'
  | 'library'
  | 'missions'
  | 'workstreams'
  | 'agent-status'
  | 'claims'
  | 'dashboard'
  | 'settings'
  | 'projects'
  | 'outline'
  | 'code'
  | 'paper'
  | 'figures'
  | 'opencode'
  | 'intelligence'
  | 'protocols'
  | 'review'
  | null;

export type MainViewMode = 'chat' | 'office3d' | 'settings' | 'dashboard' | 'review';
export type AgentStatusViewMode = 'office3d' | 'list' | 'timeline';

export type LabInteractiveObject =
  | 'library'
  | 'outline'
  | 'hpc_opencode'
  | 'roundtable_review'
  | 'figure_studio'
  | 'missions'
  | 'intelligence'
  | null;

export type InteractiveLabObjectKind = LabInteractiveObject;

interface UIState {
  // Active project & topic context
  project: Project | null;
  projects: Project[];
  activeTopic: Topic | null;
  activeTopicId: string | null;
  topics: Topic[];

  // Active conversation & folder (ChatGPT-style Projects)
  activeSessionId: string | null;
  activeChatProjectId: string | null;

  // Language & UI Scale
  language: 'vi' | 'en';
  uiScale: number;

  // Layout & navigation
  sidebarOpen: boolean;
  mainView: MainViewMode;
  agentStatusView: AgentStatusViewMode;
  officeFullscreen: boolean;
  drawerKind: DrawerKind;
  drawerTab: string;
  settingsTab: string;

  // 3D Agent Office selection & interactive states
  selectedAgentId: string | null;
  selectedMissionId: string | null;
  selectedLabObject: LabInteractiveObject;
  officeChatOpen: boolean;
  agentsSocialMode: boolean;

  // Notifications & badges
  pendingCount: number;
  offline: boolean;

  // Actions
  setProject: (project: Project | null) => void;
  setProjects: (projects: Project[]) => void;
  setActiveTopic: (topic: Topic | null) => void;
  setActiveTopicId: (id: string | null) => void;
  setTopics: (topics: Topic[]) => void;
  setActiveSessionId: (id: string | null) => void;
  setActiveChatProjectId: (id: string | null) => void;
  setLanguage: (lang: 'vi' | 'en') => void;
  setUiScale: (scale: number) => void;
  toggleSidebar: () => void;
  setMainView: (view: MainViewMode) => void;
  setAgentStatusView: (view: AgentStatusViewMode) => void;
  setOfficeFullscreen: (full: boolean) => void;
  openDrawer: (kind: DrawerKind, tab?: string) => void;
  closeDrawer: () => void;
  openSettings: (tab?: string) => void;
  open3DOffice: (fullscreen?: boolean) => void;
  setSelectedAgentId: (id: string | null) => void;
  setSelectedMissionId: (id: string | null) => void;
  setSelectedLabObject: (obj: LabInteractiveObject) => void;
  setOfficeChatOpen: (open: boolean) => void;
  setAgentsSocialMode: (social: boolean) => void;
  setPendingCount: (count: number) => void;
  setOffline: (offline: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  project: null,
  projects: [],
  activeTopic: null,
  activeTopicId: null,
  topics: [],
  activeSessionId: null,
  activeChatProjectId: null,
  language: 'vi',
  uiScale: 1,
  sidebarOpen: true,
  mainView: 'chat',
  agentStatusView: 'office3d',
  officeFullscreen: true,
  drawerKind: null,
  drawerTab: 'default',
  settingsTab: 'models',
  selectedAgentId: null,
  selectedMissionId: null,
  selectedLabObject: null,
  officeChatOpen: true,
  agentsSocialMode: true,
  pendingCount: 0,
  offline: false,

  setProject: (project) => set({ project }),
  setProjects: (projects) => set({ projects }),
  setActiveTopic: (activeTopic) =>
    set({ activeTopic, activeTopicId: activeTopic ? activeTopic.id : null }),
  setActiveTopicId: (activeTopicId) =>
    set((s) => ({
      activeTopicId,
      activeTopic: s.topics.find((t) => t.id === activeTopicId) || s.activeTopic,
    })),
  setTopics: (topics) => set({ topics }),
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setActiveChatProjectId: (activeChatProjectId) => set({ activeChatProjectId }),
  setLanguage: (language) => set({ language }),
  setUiScale: (uiScale) => {
    document.documentElement.style.fontSize = `${Math.round(uiScale * 100)}%`;
    set({ uiScale });
  },
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setMainView: (mainView) => set({ mainView }),
  setAgentStatusView: (agentStatusView) => set({ agentStatusView }),
  setOfficeFullscreen: (officeFullscreen) => set({ officeFullscreen }),
  openDrawer: (drawerKind, drawerTab = 'default') =>
    set((s) => {
      if (drawerKind === 'agent-status') {
        return { mainView: 'office3d', officeFullscreen: true, drawerKind: null };
      }
      if (drawerKind === 'settings') {
        return {
          mainView: 'settings',
          settingsTab: drawerTab !== 'default' ? drawerTab : s.settingsTab,
          drawerKind: null,
        };
      }
      if (drawerKind === 'dashboard') {
        return { mainView: 'dashboard', drawerKind: null };
      }
      if (drawerKind === 'review') {
        return { mainView: 'review', drawerKind: null };
      }
      return { drawerKind, drawerTab };
    }),
  closeDrawer: () => set({ drawerKind: null }),
  openSettings: (tab = 'models') =>
    set({ mainView: 'settings', settingsTab: tab, drawerKind: null }),
  open3DOffice: (fullscreen = true) =>
    set({ mainView: 'office3d', officeFullscreen: fullscreen, drawerKind: null }),
  setSelectedAgentId: (selectedAgentId) => set({ selectedAgentId }),
  setSelectedMissionId: (selectedMissionId) => set({ selectedMissionId }),
  setSelectedLabObject: (selectedLabObject) => set({ selectedLabObject }),
  setOfficeChatOpen: (officeChatOpen) => set({ officeChatOpen }),
  setAgentsSocialMode: (agentsSocialMode) => set({ agentsSocialMode }),
  setPendingCount: (pendingCount) => set({ pendingCount }),
  setOffline: (offline) => set({ offline }),
}));

export function useI18n() {
  const language = useUIStore((s) => s.language);
  const setLanguage = useUIStore((s) => s.setLanguage);
  const t = (vi: string, en: string) => (language === 'en' ? en : vi);
  return { language, setLanguage, t };
}
