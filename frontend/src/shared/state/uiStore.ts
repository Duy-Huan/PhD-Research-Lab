import { create } from 'zustand';
import { useTranslation } from 'react-i18next';
import i18n, { defaultLanguage } from '../i18n';
import type { Project, Topic, AgentOfficeViewModel, AgentCustomProfile } from '../api/types';

function loadStoredAgentProfiles(): Record<string, AgentCustomProfile> {
  try {
    if (typeof localStorage !== 'undefined') {
      const raw = localStorage.getItem('phdlab_agent_profiles');
      if (raw) {
        return JSON.parse(raw);
      }
    }
  } catch (e) {
    console.error('Failed to parse phdlab_agent_profiles from localStorage', e);
  }
  return {};
}

function persistAgentProfiles(profiles: Record<string, AgentCustomProfile>) {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('phdlab_agent_profiles', JSON.stringify(profiles));
    }
  } catch (e) {
    console.error('Failed to save phdlab_agent_profiles to localStorage', e);
  }
}

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
  | 'guide'
  | 'harness'
  | 'cli'
  | null;

export type MainViewMode = 'chat' | 'library' | 'office3d' | 'settings' | 'dashboard' | 'review' | 'guide';
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
  lastDrawerKind: DrawerKind;
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

  // Agent Personal Profiles & Custom Customizations
  agentProfiles: Record<string, AgentCustomProfile>;

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
  toggleDrawer: (defaultKind?: DrawerKind) => void;
  openSettings: (tab?: string) => void;
  open3DOffice: (fullscreen?: boolean) => void;
  setSelectedAgentId: (id: string | null) => void;
  setSelectedMissionId: (id: string | null) => void;
  setSelectedLabObject: (obj: LabInteractiveObject) => void;
  setOfficeChatOpen: (open: boolean) => void;
  setAgentsSocialMode: (social: boolean) => void;
  setPendingCount: (count: number) => void;
  setOffline: (offline: boolean) => void;
  updateAgentProfile: (agentId: string, profile: Partial<AgentCustomProfile>) => void;
  resetAgentProfile: (agentId: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  project: null,
  projects: [],
  activeTopic: null,
  activeTopicId: null,
  topics: [],
  activeSessionId: null,
  activeChatProjectId: null,
  language: defaultLanguage,
  uiScale: 1,
  sidebarOpen: true,
  mainView: 'chat',
  agentStatusView: 'office3d',
  officeFullscreen: true,
  drawerKind: null,
  lastDrawerKind: 'outline',
  drawerTab: 'default',
  settingsTab: 'models',
  selectedAgentId: null,
  selectedMissionId: null,
  selectedLabObject: null,
  officeChatOpen: true,
  agentsSocialMode: true,
  pendingCount: 0,
  offline: false,
  agentProfiles: loadStoredAgentProfiles(),

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
  setLanguage: (language) => {
    i18n.changeLanguage(language);
    try {
      localStorage.setItem('phdlab_lang', language);
    } catch {}
    if (typeof document !== 'undefined') {
      document.documentElement.lang = language;
    }
    set({ language });
  },
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
      return {
        drawerKind,
        drawerTab,
        lastDrawerKind: drawerKind || s.lastDrawerKind || 'outline',
      };
    }),
  closeDrawer: () => set({ drawerKind: null }),
  toggleDrawer: (defaultKind) =>
    set((s) => {
      if (s.drawerKind) {
        return { drawerKind: null };
      }
      const target = defaultKind || s.lastDrawerKind || 'outline';
      return { drawerKind: target, lastDrawerKind: target };
    }),
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
  updateAgentProfile: (agentId, profile) =>
    set((s) => {
      const existing = s.agentProfiles[agentId] || { agentId };
      const nextProfiles: Record<string, AgentCustomProfile> = {
        ...s.agentProfiles,
        [agentId]: {
          ...existing,
          ...profile,
          agentId,
          updatedAt: new Date().toISOString(),
        },
      };
      persistAgentProfiles(nextProfiles);
      return { agentProfiles: nextProfiles };
    }),
  resetAgentProfile: (agentId) =>
    set((s) => {
      const nextProfiles: Record<string, AgentCustomProfile> = { ...s.agentProfiles };
      delete nextProfiles[agentId];
      persistAgentProfiles(nextProfiles);
      return { agentProfiles: nextProfiles };
    }),
}));

export function applyAgentProfiles(
  agents: AgentOfficeViewModel[],
  profiles: Record<string, AgentCustomProfile>
): AgentOfficeViewModel[] {
  return agents.map((agent) => {
    const p = profiles[agent.agentId];
    if (!p) return agent;
    const customName = p.customName?.trim();
    const customTitle = p.customTitle?.trim();
    const customBio = p.customBio?.trim();
    const customGreeting = p.customGreeting?.trim();
    return {
      ...agent,
      displayName: customName || agent.displayName,
      role: customTitle || agent.role,
      personality: customBio || agent.personality,
      speechBubble: customGreeting || agent.speechBubble,
      customName: customName || undefined,
      customTitle: customTitle || undefined,
      customBio: customBio || undefined,
      customColor: p.customColor || undefined,
      customGreeting: customGreeting || undefined,
    };
  });
}

export function useI18n() {
  const language = useUIStore((s) => s.language);
  const setLanguage = useUIStore((s) => s.setLanguage);
  const { t: translate } = useTranslation();

  const t = (viOrKey: string, en?: string): string => {
    if (typeof en === 'string') {
      return language === 'en' ? en : viOrKey;
    }
    const translated = translate(viOrKey);
    return translated !== viOrKey ? translated : viOrKey;
  };

  return { language, setLanguage, t };
}
