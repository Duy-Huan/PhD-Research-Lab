import React, { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Group, Panel, Separator } from 'react-resizable-panels';
import {
  useUIStore,
  useI18n,
  applyAgentProfiles,
  type InteractiveLabObjectKind,
} from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type {
  Mission,
  OpenCodeSession,
  AgentOfficeViewModel,
  AppConfig,
  LibraryPaper,
  ChatSession,
} from '../../shared/api/types';
import {
  mapMissionsToAgentViewModels,
  buildUniversityLabRoster,
} from '../../shared/events/eventAdapter';
import { AgentStatusList } from './AgentStatusList';
import { OfficeCanvas } from './office3d/OfficeCanvas';
import { AgentProfileModal } from './AgentProfileModal';
import { ChatCenter } from '../chat/ChatCenter';
import { LibraryPanel } from '../library/LibraryPanel';
import { OutlinePanel } from '../workspace-tools/OutlinePaperCodePanels';
import { OpenCodePanel } from '../opencode/OpenCodePanel';
import { ReviewView } from '../review/ReviewView';
import { FigureStudioPanel } from '../figures/FigureStudioPanel';
import { MissionLiveWorkspace } from '../missions/MissionLiveWorkspace';
import { IntelligenceHubPanel } from '../intelligence/IntelligenceHubPanel';
import {
  List,
  History,
  Box,
  ArrowLeft,
  Maximize2,
  Minimize2,
  Users,
  Layers,
  Terminal,
  Sparkles,
  X,
  MessageSquare,
  BookOpen,
  Compass,
  Award,
  BarChart3,
  Cpu,
  Send,
  UserCog,
} from 'lucide-react';

type DockTab = 'chat' | 'agent' | 'object';

export const AgentStatusView: React.FC = () => {
  const queryClient = useQueryClient();
  const {
    activeTopicId,
    activeTopic,
    project,
    agentStatusView,
    setAgentStatusView,
    officeFullscreen,
    setOfficeFullscreen,
    setMainView,
    openSettings,
    selectedLabObject,
    setSelectedLabObject,
    officeChatOpen,
    setOfficeChatOpen,
    agentsSocialMode,
    setAgentsSocialMode,
    activeSessionId,
    setActiveSessionId,
    activeChatProjectId,
    agentProfiles,
  } = useUIStore();
  const { t } = useI18n();

  const [selectedAgent, setSelectedAgent] = useState<AgentOfficeViewModel | null>(null);
  const [editingProfileAgent, setEditingProfileAgent] = useState<AgentOfficeViewModel | null>(null);
  const [rosterOpen, setRosterOpen] = useState(true);
  const [dockTab, setDockTab] = useState<DockTab>('chat');
  const [directAgentInput, setDirectAgentInput] = useState('');
  const [sendingDirect, setSendingDirect] = useState(false);

  const { data: config } = useQuery<AppConfig>({
    queryKey: ['config'],
    queryFn: () => api.get<AppConfig>('/api/config'),
  });

  // Fetch papers count for 3D Library badge
  const { data: libraryData } = useQuery<{ references?: LibraryPaper[]; papers?: LibraryPaper[] }>({
    queryKey: ['library', project?.data_dir],
    queryFn: () => api.get<{ references?: LibraryPaper[]; papers?: LibraryPaper[] }>('/api/library'),
    enabled: !!project,
  });

  // Fetch missions for agent state mapping
  const { data: missionsData } = useQuery<{ missions: Mission[] }>({
    queryKey: ['missions', activeTopicId],
    queryFn: () =>
      api.get<{ missions: Mission[] }>(`/api/research/topics/${activeTopicId}/missions`),
    enabled: !!activeTopicId,
  });

  // Fetch v6.4.1 OpenCode sessions for agent state mapping
  const { data: opencodeData } = useQuery<{ sessions: OpenCodeSession[] }>({
    queryKey: ['opencode-sessions', activeTopicId],
    queryFn: () =>
      api.get<{ sessions: OpenCodeSession[] }>(
        `/api/research/topics/${activeTopicId}/opencode/sessions`
      ),
    enabled: !!activeTopicId,
  });

  const papers = libraryData?.references || libraryData?.papers || [];
  const missions = missionsData?.missions || [];
  const opencodeSessions = opencodeData?.sessions || [];
  const liveAgents = mapMissionsToAgentViewModels(
    missions,
    project?.data_dir || '',
    activeTopicId || undefined,
    opencodeSessions
  );

  // Build full University Lab roster with user custom personal profiles applied
  const baseAgents = buildUniversityLabRoster(
    liveAgents,
    project?.data_dir || '',
    activeTopicId || undefined,
    config?.agent_modes
  );
  const agents = useMemo(() => applyAgentProfiles(baseAgents, agentProfiles), [baseAgents, agentProfiles]);

  const activeSelectedAgent = useMemo(() => {
    if (!selectedAgent) return null;
    return agents.find((a) => a.agentId === selectedAgent.agentId) || selectedAgent;
  }, [agents, selectedAgent]);

  const runningCount = agents.filter((a) => a.presence === 'running').length;

  const handleSelect3DAgent = (agent: AgentOfficeViewModel) => {
    setSelectedAgent(agent);
    setOfficeChatOpen(true);
    setDockTab('agent');
  };

  const handleSelect3DObject = (obj: InteractiveLabObjectKind) => {
    setSelectedLabObject(obj);
    if (obj) {
      setOfficeChatOpen(true);
      setDockTab('object');
    }
  };

  // Send a direct message/task to the clicked 3D Agent and sync with main chat session
  const handleSendDirectToAgent = async (customPrompt?: string) => {
    const targetAgent = activeSelectedAgent || selectedAgent;
    if (!targetAgent) return;
    const raw = (customPrompt ?? directAgentInput).trim();
    if (!raw || sendingDirect) return;

    setSendingDirect(true);
    try {
      let sid = activeSessionId;
      if (!sid) {
        const created = await api.post<ChatSession>('/api/chat/sessions', {
          title: `[${targetAgent.displayName}] ${raw.slice(0, 36)}`,
          topic_id: activeTopic?.id || '',
          chat_project: activeChatProjectId || '',
        });
        sid = created.id;
        setActiveSessionId(sid);
      }

      const skillPrefix = targetAgent.skillCommand || '';
      const formattedText = raw.startsWith('/')
        ? raw
        : `${skillPrefix ? skillPrefix + ' ' : ''}[Gửi trực tiếp tới ${targetAgent.displayName}]: ${raw}`;

      await api.post(`/api/chat/sessions/${sid}/turns`, {
        text: formattedText,
        overrides: {},
      });

      setDirectAgentInput('');
      queryClient.invalidateQueries({ queryKey: ['chat', sid] });
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
      // Switch dock tab to synchronized chat so user sees live streaming answer immediately
      setDockTab('chat');
    } finally {
      setSendingDirect(false);
    }
  };

  const renderInteractiveObjectWorkflow = () => {
    switch (selectedLabObject) {
      case 'library':
        return <LibraryPanel />;
      case 'outline':
        return <OutlinePanel />;
      case 'hpc_opencode':
        return <OpenCodePanel />;
      case 'roundtable_review':
        return <ReviewView />;
      case 'figure_studio':
        return <FigureStudioPanel />;
      case 'missions':
        return <MissionLiveWorkspace />;
      case 'intelligence':
        return <IntelligenceHubPanel />;
      default:
        return <OutlinePanel />;
    }
  };

  return (
    <div
      style={{
        position: officeFullscreen ? 'fixed' : 'relative',
        inset: officeFullscreen ? 0 : undefined,
        zIndex: officeFullscreen ? 80 : 1,
        width: '100%',
        height: officeFullscreen ? '100vh' : '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#064e3b',
        color: '#f8fafc',
        overflow: 'hidden',
      }}
    >
      {/* ── Top Biophilic Green University Lab Command Bar ── */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          padding: '8px 14px',
          background: 'rgba(6, 78, 59, 0.94)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(52, 211, 153, 0.3)',
          zIndex: 25,
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            type="button"
            onClick={() => {
              setOfficeFullscreen(false);
              setMainView('chat');
            }}
            title={t('Quay lại giao diện thường', 'Back to standard view')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 10px',
              borderRadius: 999,
              border: '1px solid rgba(52, 211, 153, 0.4)',
              background: 'rgba(255, 255, 255, 0.1)',
              color: '#f8fafc',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <ArrowLeft size={14} />
            <span>{t('2D Workspace', '2D Workspace')}</span>
          </button>

          <img
            src="/img/logo-64.png"
            alt="PhD Lab Logo"
            width={28}
            height={28}
            style={{ borderRadius: 6, background: '#fff', padding: 2 }}
          />
          <div>
            <div style={{ fontWeight: 800, fontSize: 14, letterSpacing: '-0.01em' }}>
              PhD Research Lab — {t('Không gian Đại học 3D Xanh', '3D Green University Lab')}
            </div>
            <div style={{ fontSize: 11, color: '#a7f3d0' }}>
              {t('Click vào từng Agent để trò chuyện trực tiếp, hoặc click Vật thể 3D (Kệ sách, Bảng, HPC, Bàn tròn) để mở Workflow', 'Click any 3D Agent to chat directly, or click 3D Furniture (Library, Board, HPC, Roundtable) to run workflows')}
            </div>
          </div>
        </div>

        {/* Interactive 3D Object Quick Shortcut Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => handleSelect3DObject('outline')}
            style={{
              border: '1px solid rgba(52, 211, 153, 0.35)',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              background:
                selectedLabObject === 'outline' && dockTab === 'object'
                  ? '#10b981'
                  : 'rgba(255,255,255,0.08)',
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title={t('Bảng Đề cương 5 cấp', '5-Level Outline Board')}
          >
            <Compass size={12} />
            <span>Outline</span>
          </button>

          <button
            type="button"
            onClick={() => handleSelect3DObject('library')}
            style={{
              border: '1px solid rgba(52, 211, 153, 0.35)',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              background:
                selectedLabObject === 'library' && dockTab === 'object'
                  ? '#10b981'
                  : 'rgba(255,255,255,0.08)',
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title={t('Kệ sách Thư viện PDF', 'Library Bookshelves')}
          >
            <BookOpen size={12} />
            <span>Library ({papers.length})</span>
          </button>

          <button
            type="button"
            onClick={() => handleSelect3DObject('hpc_opencode')}
            style={{
              border: '1px solid rgba(52, 211, 153, 0.35)',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              background:
                selectedLabObject === 'hpc_opencode' && dockTab === 'object'
                  ? '#10b981'
                  : 'rgba(255,255,255,0.08)',
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title="HPC Server & OpenCode"
          >
            <Terminal size={12} />
            <span>HPC</span>
          </button>

          <button
            type="button"
            onClick={() => handleSelect3DObject('roundtable_review')}
            style={{
              border: '1px solid rgba(52, 211, 153, 0.35)',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              background:
                selectedLabObject === 'roundtable_review' && dockTab === 'object'
                  ? '#10b981'
                  : 'rgba(255,255,255,0.08)',
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title="Peer Review Roundtable"
          >
            <Award size={12} />
            <span>Review</span>
          </button>

          <button
            type="button"
            onClick={() => handleSelect3DObject('figure_studio')}
            style={{
              border: '1px solid rgba(52, 211, 153, 0.35)',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              background:
                selectedLabObject === 'figure_studio' && dockTab === 'object'
                  ? '#10b981'
                  : 'rgba(255,255,255,0.08)',
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title="Figure Hologram Table"
          >
            <BarChart3 size={12} />
            <span>Figures</span>
          </button>

          <button
            type="button"
            onClick={() => handleSelect3DObject('missions')}
            style={{
              border: '1px solid rgba(52, 211, 153, 0.35)',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              background:
                selectedLabObject === 'missions' && dockTab === 'object'
                  ? '#10b981'
                  : 'rgba(255,255,255,0.08)',
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title="Autonomous Missions"
          >
            <Layers size={12} />
            <span>Missions ({missions.length})</span>
          </button>

          <button
            type="button"
            onClick={() => handleSelect3DObject('intelligence')}
            style={{
              border: '1px solid rgba(52, 211, 153, 0.35)',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              background:
                selectedLabObject === 'intelligence' && dockTab === 'object'
                  ? '#10b981'
                  : 'rgba(255,255,255,0.08)',
              color: '#fff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
            title="Unified Intelligence & RO-Crate"
          >
            <Cpu size={12} />
          </button>
        </div>

        {/* Right Controls: View Switcher + Toggle Synced Chat Dock + Fullscreen */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              display: 'flex',
              background: 'rgba(15, 23, 42, 0.5)',
              padding: 2,
              borderRadius: 999,
              border: '1px solid rgba(52, 211, 153, 0.3)',
            }}
          >
            <button
              type="button"
              onClick={() => setAgentStatusView('office3d')}
              title="3D Lab"
              style={{
                padding: '4px 9px',
                borderRadius: 999,
                border: 'none',
                fontSize: 11.5,
                fontWeight: 600,
                background: agentStatusView === 'office3d' ? '#10b981' : 'transparent',
                color: '#fff',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <Box size={12} /> 3D
            </button>
            <button
              type="button"
              onClick={() => setAgentStatusView('list')}
              title="2D Matrix"
              style={{
                padding: '4px 9px',
                borderRadius: 999,
                border: 'none',
                fontSize: 11.5,
                fontWeight: 600,
                background: agentStatusView === 'list' ? '#10b981' : 'transparent',
                color: '#fff',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <List size={12} /> 2D
            </button>
            <button
              type="button"
              onClick={() => setAgentStatusView('timeline')}
              title="Event Log"
              style={{
                padding: '4px 9px',
                borderRadius: 999,
                border: 'none',
                fontSize: 11.5,
                fontWeight: 600,
                background: agentStatusView === 'timeline' ? '#10b981' : 'transparent',
                color: '#fff',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <History size={12} />
            </button>
          </div>

          <button
            type="button"
            onClick={() => setRosterOpen(!rosterOpen)}
            title={t('Danh sách Agents', 'Agent Roster')}
            style={{
              padding: '5px 9px',
              borderRadius: 999,
              border: '1px solid rgba(52, 211, 153, 0.35)',
              background: rosterOpen ? '#059669' : 'rgba(255,255,255,0.08)',
              color: '#fff',
              fontSize: 11.5,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <Users size={13} />
            <span>{agents.length}</span>
          </button>

          <button
            type="button"
            onClick={() => setOfficeChatOpen(!officeChatOpen)}
            title={t(
              'Đóng/Mở Khung Chat & Workflow Đồng bộ ngay trên 3D Lab',
              'Toggle Synchronized Chat & Workflow Dock in 3D Lab'
            )}
            style={{
              padding: '5px 11px',
              borderRadius: 999,
              border: '1px solid #34d399',
              background: officeChatOpen ? '#10b981' : 'rgba(255,255,255,0.1)',
              color: '#fff',
              fontSize: 11.5,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            <MessageSquare size={13} />
            <span>{t('Khung Chat & Workflow 3D', '3D Chat & Workflow')}</span>
          </button>

          <button
            type="button"
            onClick={() => setOfficeFullscreen(!officeFullscreen)}
            title={officeFullscreen ? t('Thu nhỏ', 'Exit Fullscreen') : t('Toàn màn hình', 'Fullscreen')}
            style={{
              padding: '5px 8px',
              borderRadius: 999,
              border: '1px solid rgba(52, 211, 153, 0.35)',
              background: 'rgba(255,255,255,0.1)',
              color: '#fff',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
            }}
          >
            {officeFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
        </div>
      </header>

      {/* ── Resizable Split Stage: 3D University Lab (Left) + Synchronized Chat & Workflow Dock (Right) ── */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Group orientation="horizontal" style={{ width: '100%', height: '100%' }}>
          {/* Left Panel: 3D Lab Viewport */}
          <Panel
            id="office3d-viewport"
            defaultSize={officeChatOpen ? '62%' : '100%'}
            minSize="38%"
            style={{ position: 'relative', height: '100%' }}
          >
            {agentStatusView === 'office3d' && (
              <OfficeCanvas
                agents={agents}
                selectedAgentId={selectedAgent?.agentId}
                selectedLabObject={selectedLabObject}
                topicTitle={activeTopic?.title}
                paperCount={papers.length}
                missionCount={missions.length}
                socializeMode={agentsSocialMode}
                onToggleSocialize={() => setAgentsSocialMode(!agentsSocialMode)}
                fullViewport
                onSelectAgent={handleSelect3DAgent}
                onSelectLabObject={handleSelect3DObject}
              />
            )}

            {agentStatusView === 'list' && (
              <div
                style={{
                  height: '100%',
                  overflowY: 'auto',
                  padding: '24px 32px',
                  background: 'var(--bg)',
                  color: 'var(--ink)',
                }}
              >
                <div style={{ maxWidth: 1120, margin: '0 auto' }}>
                  <h3 style={{ marginTop: 0 }}>
                    {t('Ma trận Trạng thái Nhà nghiên cứu AI 2D', 'AI Researchers Status Matrix (2D)')}
                  </h3>
                  <AgentStatusList
                    agents={agents}
                    onSelectAgent={handleSelect3DAgent}
                    onEditProfile={(a) => setEditingProfileAgent(a)}
                  />
                </div>
              </div>
            )}

            {agentStatusView === 'timeline' && (
              <div
                style={{
                  height: '100%',
                  overflowY: 'auto',
                  padding: '24px 32px',
                  background: 'var(--bg)',
                  color: 'var(--ink)',
                }}
              >
                <div
                  style={{
                    maxWidth: 960,
                    margin: '0 auto',
                    background: 'var(--panel)',
                    padding: 20,
                    borderRadius: 12,
                    border: '1px solid var(--line)',
                  }}
                >
                  <h3 style={{ marginTop: 0 }}>
                    {t('Nhật ký Hoạt động của các AI Agents', 'Live Agent Activity Timeline')}
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {agents.map((a) => (
                      <div
                        key={a.agentId}
                        onClick={() => handleSelect3DAgent(a)}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          padding: '10px 14px',
                          borderRadius: 8,
                          border: '1px solid var(--line)',
                          background: 'var(--bg)',
                          cursor: 'pointer',
                        }}
                      >
                        <div>
                          <b>{a.displayName}</b>
                          <div className="muted" style={{ fontSize: 12 }}>
                            {a.role}
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className="chip">{a.engine}</span>
                          <span className="chip">{a.activity}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Floating Roster Overlay on Top-Left of 3D View */}
            {agentStatusView === 'office3d' && rosterOpen && (
              <aside
                style={{
                  position: 'absolute',
                  top: 12,
                  left: 12,
                  width: 260,
                  maxHeight: 'calc(100% - 80px)',
                  background: 'rgba(6, 78, 59, 0.88)',
                  backdropFilter: 'blur(12px)',
                  borderRadius: 12,
                  border: '1px solid rgba(52, 211, 153, 0.35)',
                  boxShadow: '0 10px 28px rgba(0, 0, 0, 0.35)',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                  zIndex: 20,
                }}
              >
                <div
                  style={{
                    padding: '8px 12px',
                    borderBottom: '1px solid rgba(52, 211, 153, 0.25)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: 12,
                    fontWeight: 700,
                    color: '#ecfdf5',
                  }}
                >
                  <span>
                    {t('Nhân sự AI trong Lab', 'Lab AI Researchers')} ({runningCount}/{agents.length})
                  </span>
                  <button
                    type="button"
                    onClick={() => setRosterOpen(false)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#a7f3d0',
                      cursor: 'pointer',
                    }}
                  >
                    <X size={13} />
                  </button>
                </div>

                <div style={{ overflowY: 'auto', padding: 6, display: 'grid', gap: 5 }}>
                  {agents.map((a) => {
                    const isSel = selectedAgent?.agentId === a.agentId;
                    return (
                      <button
                        key={a.agentId}
                        type="button"
                        onClick={() => handleSelect3DAgent(a)}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 2,
                          padding: '7px 9px',
                          borderRadius: 8,
                          border: `1px solid ${
                            isSel ? '#fbbf24' : 'rgba(52, 211, 153, 0.2)'
                          }`,
                          background: isSel
                            ? 'rgba(16, 185, 129, 0.35)'
                            : 'rgba(15, 23, 42, 0.45)',
                          color: '#f8fafc',
                          textAlign: 'left',
                          cursor: 'pointer',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: 4,
                          }}
                        >
                          <span style={{ fontWeight: 700, fontSize: 11.5 }} className="ellipsis">
                            {a.displayName}
                          </span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <span
                              role="button"
                              tabIndex={0}
                              title={t('Tùy biến hồ sơ & Đặt tên', 'Customize Profile & Custom Name')}
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingProfileAgent(a);
                              }}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                padding: '2px 4px',
                                borderRadius: 4,
                                color: '#a7f3d0',
                                background: 'rgba(52, 211, 153, 0.15)',
                                cursor: 'pointer',
                              }}
                            >
                              <UserCog size={11} />
                            </span>
                            <span
                              style={{
                                fontSize: 9.5,
                                padding: '1px 5px',
                                borderRadius: 999,
                                background: 'rgba(16, 185, 129, 0.25)',
                                color: '#6ee7b7',
                              }}
                            >
                              {a.engine}
                            </span>
                          </div>
                        </div>
                        <div className="ellipsis" style={{ fontSize: 10.5, color: '#cbd5e1' }}>
                          {a.role}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </aside>
            )}
          </Panel>

          {/* Right Panel: Resizable Synchronized Chat & 3D Interactive Workflow Dock */}
          {officeChatOpen && (
            <>
              <Separator
                style={{
                  width: 5,
                  background: 'rgba(52, 211, 153, 0.35)',
                  cursor: 'col-resize',
                }}
              />
              <Panel
                id="office3d-chat-dock"
                defaultSize="38%"
                minSize="24%"
                maxSize="60%"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  height: '100%',
                  background: 'var(--panel)',
                  color: 'var(--ink)',
                  overflow: 'hidden',
                }}
              >
                {/* Dock Header Tabs: 1. Synced Chat | 2. Direct Agent Chat | 3. 3D Object Workflow */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 10px',
                    borderBottom: '1px solid var(--line)',
                    background: 'var(--bg-2)',
                    gap: 4,
                    flexShrink: 0,
                  }}
                >
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className={`btn sm ${dockTab === 'chat' ? 'accent' : 'ghost'}`}
                      onClick={() => setDockTab('chat')}
                      style={{ borderRadius: 999, padding: '4px 10px', fontSize: 11.5, gap: 4 }}
                    >
                      <MessageSquare size={12} />
                      <span>{t('Chat Đồng bộ', 'Synced Chat')}</span>
                    </button>

                    <button
                      type="button"
                      className={`btn sm ${dockTab === 'agent' ? 'accent' : 'ghost'}`}
                      onClick={() => {
                        if (!selectedAgent && agents.length > 0) {
                          setSelectedAgent(agents[0]);
                        }
                        setDockTab('agent');
                      }}
                      style={{ borderRadius: 999, padding: '4px 10px', fontSize: 11.5, gap: 4 }}
                    >
                      <Users size={12} />
                      <span>
                        {selectedAgent
                          ? selectedAgent.displayName.split('·')[0].trim()
                          : t('Trò chuyện Agent', 'Agent Chat')}
                      </span>
                    </button>

                    <button
                      type="button"
                      className={`btn sm ${dockTab === 'object' ? 'accent' : 'ghost'}`}
                      onClick={() => {
                        if (!selectedLabObject) setSelectedLabObject('library');
                        setDockTab('object');
                      }}
                      style={{ borderRadius: 999, padding: '4px 10px', fontSize: 11.5, gap: 4 }}
                    >
                      <BookOpen size={12} />
                      <span>
                        {selectedLabObject === 'library'
                          ? t('Thư viện 3D', '3D Library')
                          : selectedLabObject === 'outline'
                          ? t('Bảng Đề cương', '3D Outline')
                          : selectedLabObject === 'hpc_opencode'
                          ? 'HPC OpenCode'
                          : selectedLabObject === 'roundtable_review'
                          ? 'Peer Review'
                          : selectedLabObject === 'figure_studio'
                          ? 'Figure Studio'
                          : selectedLabObject === 'missions'
                          ? 'Missions'
                          : t('Vật thể 3D', '3D Object')}
                      </span>
                    </button>
                  </div>

                  <button
                    type="button"
                    className="icon sm"
                    onClick={() => setOfficeChatOpen(false)}
                    title={t('Đóng khung', 'Close dock')}
                  >
                    <X size={15} />
                  </button>
                </div>

                {/* Dock Body */}
                <div
                  style={{
                    flex: 1,
                    minHeight: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                    background: 'var(--bg)',
                    color: 'var(--ink)',
                  }}
                >
                  {/* TAB 1: Full Synchronized Main Chat Center */}
                  {dockTab === 'chat' && <ChatCenter compact />}

                  {/* TAB 2: Direct Agent Status & Interactive Conversation */}
                  {dockTab === 'agent' && (() => {
                    const currentAgent = activeSelectedAgent || selectedAgent;
                    return (
                    <div
                      style={{
                        flex: 1,
                        overflowY: 'auto',
                        padding: 14,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 12,
                      }}
                    >
                      {currentAgent ? (
                        <>
                          <div
                            style={{
                              padding: 14,
                              borderRadius: 12,
                              background: 'var(--bg-2)',
                              border: '1px solid var(--accent)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 8,
                            }}
                          >
                            <div
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'flex-start',
                              }}
                            >
                              <div>
                                <span
                                  className="chip"
                                  style={{
                                    fontSize: 10.5,
                                    background: 'var(--accent-soft)',
                                    color: 'var(--accent)',
                                    marginBottom: 4,
                                  }}
                                >
                                  {currentAgent.engine} · {currentAgent.presence}
                                </span>
                                <h3 style={{ margin: '4px 0 2px', fontSize: 16 }}>
                                  {currentAgent.displayName}
                                </h3>
                                <div className="muted" style={{ fontSize: 12.5 }}>
                                  {currentAgent.role}
                                </div>
                              </div>
                              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                <button
                                  type="button"
                                  className="btn sm accent"
                                  onClick={() => setEditingProfileAgent(currentAgent)}
                                >
                                  <UserCog size={12} style={{ marginRight: 4 }} />
                                  {t('Hồ sơ & Đổi tên', 'Profile & Custom Name')}
                                </button>
                                <button
                                  type="button"
                                  className="btn sm ghost"
                                  onClick={() => {
                                    setOfficeFullscreen(false);
                                    openSettings('models');
                                  }}
                                >
                                  <Sparkles size={12} style={{ marginRight: 4 }} />
                                  {t('Đổi Model', 'Change Model')}
                                </button>
                              </div>
                            </div>

                            {currentAgent.personality && (
                              <div
                                style={{
                                  fontSize: 12,
                                  padding: '8px 10px',
                                  borderRadius: 8,
                                  background: 'var(--panel)',
                                  border: '1px solid var(--line)',
                                }}
                              >
                                <b>{t('Tính cách & Chuyên môn:', 'Persona & Expertise:')}</b>{' '}
                                {currentAgent.personality}
                              </div>
                            )}

                            {(currentAgent.customGreeting || currentAgent.speechBubble) && (
                              <div
                                style={{
                                  fontSize: 12.5,
                                  padding: '8px 10px',
                                  borderRadius: 8,
                                  background: 'rgba(16, 185, 129, 0.12)',
                                  border: '1px solid #10b981',
                                }}
                              >
                                💬 <b>{t('Đang nói:', 'Speaking:')}</b> "{currentAgent.customGreeting || currentAgent.speechBubble}"
                              </div>
                            )}

                            {/* Quick Direct Interaction Buttons */}
                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                              <button
                                type="button"
                                className="btn sm accent"
                                onClick={() =>
                                  handleSendDirectToAgent(
                                    t(
                                      'Hãy báo cáo chi tiết trạng thái công việc hiện tại của bạn và đề xuất bước tiếp theo.',
                                      'Please report your current status and suggest the next research step.'
                                    )
                                  )
                                }
                              >
                                {t('Hỏi Trạng thái', 'Ask Status')}
                              </button>
                              <button
                                type="button"
                                className="btn sm ghost"
                                onClick={() =>
                                  handleSendDirectToAgent(
                                    t(
                                      'Hãy phối hợp với các Agent khác trong Lab để thực hiện nhiệm vụ nghiên cứu hiện tại.',
                                      'Coordinate with the other lab agents to execute the current research task.'
                                    )
                                  )
                                }
                              >
                                {t('Yêu cầu Phối hợp Nhóm', 'Request Team Sync')}
                              </button>
                            </div>

                            {/* Direct Chat Input to this Agent */}
                            <div
                              style={{
                                display: 'flex',
                                gap: 6,
                                marginTop: 6,
                              }}
                            >
                              <input
                                type="text"
                                value={directAgentInput}
                                onChange={(e) => setDirectAgentInput(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleSendDirectToAgent();
                                }}
                                placeholder={t(
                                  `Nhắn trực tiếp cho ${currentAgent.displayName}…`,
                                  `Message ${currentAgent.displayName} directly…`
                                )}
                                style={{
                                  flex: 1,
                                  padding: '7px 10px',
                                  borderRadius: 8,
                                  border: '1px solid var(--line-2)',
                                  background: 'var(--panel)',
                                  color: 'var(--ink)',
                                  fontSize: 12.5,
                                }}
                              />
                              <button
                                type="button"
                                className="btn sm accent"
                                disabled={!directAgentInput.trim() || sendingDirect}
                                onClick={() => handleSendDirectToAgent()}
                              >
                                <Send size={13} />
                              </button>
                            </div>
                          </div>

                          {/* Embedded Live Chat below the Agent Inspector */}
                          <div
                            style={{
                              flex: 1,
                              minHeight: 320,
                              border: '1px solid var(--line)',
                              borderRadius: 12,
                              overflow: 'hidden',
                              display: 'flex',
                              flexDirection: 'column',
                            }}
                          >
                            <ChatCenter compact />
                          </div>
                        </>
                      ) : (
                        <p className="muted">
                          {t(
                            'Hãy click vào một nhân vật AI trong phòng Lab 3D để trò chuyện trực tiếp.',
                            'Click any 3D AI Researcher in the lab to chat directly.'
                          )}
                        </p>
                      )}
                    </div>
                  );
                })()}

                  {/* TAB 3: Interactive 3D Furniture / Object Workflow */}
                  {dockTab === 'object' && (
                    <div style={{ flex: 1, overflowY: 'auto' }}>
                      {renderInteractiveObjectWorkflow()}
                    </div>
                  )}
                </div>
              </Panel>
            </>
          )}
        </Group>
      </div>

      {/* AI Agent Custom Profile & Name Dialog */}
      <AgentProfileModal
        agent={editingProfileAgent}
        isOpen={!!editingProfileAgent}
        onClose={() => setEditingProfileAgent(null)}
      />
    </div>
  );
};
