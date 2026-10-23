import React from 'react';
import { useUIStore, useI18n } from '../shared/state/uiStore';
import { TopicView } from '../features/research-topics/TopicView';
import { LibraryPanel } from '../features/library/LibraryPanel';
import { WorkstreamMonitor } from '../features/workstreams/WorkstreamMonitor';
import { MissionLiveWorkspace } from '../features/missions/MissionLiveWorkspace';
import { AgentStatusView } from '../features/agent-status/AgentStatusView';
import { EvidenceReview } from '../features/evidence/EvidenceReview';
import { DashboardView } from '../features/dashboard/DashboardView';
import { SettingsModal } from '../features/settings/SettingsModal';
import { ProjectSwitcher } from '../features/projects/ProjectSwitcher';
import { FigureStudioPanel } from '../features/figures/FigureStudioPanel';
import { OpenCodePanel } from '../features/opencode/OpenCodePanel';
import { IntelligenceHubPanel } from '../features/intelligence/IntelligenceHubPanel';
import { ReviewView } from '../features/review/ReviewView';
import {
  OutlinePanel,
  PaperPanel,
  CodePanel,
  ProtocolsPanel,
} from '../features/workspace-tools/OutlinePaperCodePanels';
import { X } from 'lucide-react';

export const ContextualDrawer: React.FC = () => {
  const { drawerKind, closeDrawer } = useUIStore();
  const { t } = useI18n();

  if (!drawerKind) return null;

  let title = t('Bảng chi tiết', 'Inspector');
  let content = null;

  switch (drawerKind) {
    case 'topics':
      title = t('Chủ đề nghiên cứu & SKB', 'Research Topics & SKB');
      content = <TopicView />;
      break;
    case 'library':
      title = t('Thư viện PDF & Tìm kiếm', 'Academic PDF Library');
      content = <LibraryPanel />;
      break;
    case 'missions':
      title = t('Nhiệm vụ Tự hành (Missions)', 'Autonomous Missions');
      content = <MissionLiveWorkspace />;
      break;
    case 'workstreams':
      title = t('Phân luồng Workstreams', 'Parallel Workstreams');
      content = <WorkstreamMonitor />;
      break;
    case 'figures':
      title = t('Figure Studio (v6.4.0)', 'Figure Studio (v6.4.0)');
      content = <FigureStudioPanel />;
      break;
    case 'opencode':
      title = t('OpenCode Parallel Core (v6.4.1)', 'OpenCode Parallel Core (v6.4.1)');
      content = <OpenCodePanel />;
      break;
    case 'intelligence':
      title = t('Research Intelligence Hub (v6.4.2)', 'Research Intelligence Hub (v6.4.2)');
      content = <IntelligenceHubPanel />;
      break;
    case 'agent-status':
      title = t('AI Agents & 3D Lab', 'AI Agents & 3D Lab');
      content = <AgentStatusView />;
      break;
    case 'protocols':
      title = t('Protocols & Thí nghiệm', 'Controlled Protocols');
      content = <ProtocolsPanel />;
      break;
    case 'claims':
      title = t('Bằng chứng & Claims', 'Claims & Evidence');
      content = <EvidenceReview />;
      break;
    case 'dashboard':
      title = t('Bảng điều khiển (Dashboard)', 'System Dashboard');
      content = <DashboardView />;
      break;
    case 'settings':
      title = t('Cài đặt hệ thống', 'System Settings');
      content = <SettingsModal />;
      break;
    case 'review':
      title = t('Hội đồng Bình duyệt R1–R3', 'Peer Review Panel R1–R3');
      content = <ReviewView />;
      break;
    case 'projects':
      title = t('Dự án Nghiên cứu', 'Research Workspaces');
      content = <ProjectSwitcher />;
      break;
    case 'outline':
      title = t('Đề cương 5 cấp độ (Outline)', '5-Level Research Outline');
      content = <OutlinePanel />;
      break;
    case 'code':
      title = t('Dự án Mã nguồn & VS Code', 'Code Workspace & VS Code');
      content = <CodePanel />;
      break;
    case 'paper':
      title = t('Bản thảo Bài báo (LaTeX)', 'Paper Manuscript (LaTeX)');
      content = <PaperPanel />;
      break;
    default:
      content = null;
  }

  return (
    <aside
      id="panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        background: 'var(--panel)',
        overflow: 'hidden',
        zIndex: 20,
      }}
    >
      <div
        className="panel-h"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 12px',
          borderBottom: '1px solid var(--line)',
          background: 'var(--bg-2)',
          flexShrink: 0,
        }}
      >
        <span className="ttl" style={{ fontWeight: 600, fontSize: 13 }}>
          {title}
        </span>
        <button
          className="icon sm"
          title={t('Đóng bảng', 'Close panel')}
          aria-label={t('Đóng bảng', 'Close panel')}
          onClick={closeDrawer}
        >
          <X size={15} />
        </button>
      </div>
      <div className="panel-b" style={{ flex: 1, overflowY: 'auto' }}>
        {content}
      </div>
    </aside>
  );
};
