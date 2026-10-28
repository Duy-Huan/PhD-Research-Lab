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
import { IntelligenceHubPanel } from '../features/intelligence/IntelligenceHubPanel';
import { ReviewView } from '../features/review/ReviewView';
import {
  OutlinePanel,
  PaperPanel,
  CodePanel,
  ProtocolsPanel,
} from '../features/workspace-tools/OutlinePaperCodePanels';
import { UserGuidePanel } from '../features/guide/UserGuidePanel';
import { CustomHarnessStudio } from '../features/harness/CustomHarnessStudio';
import { X, PanelRightClose } from 'lucide-react';

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
      title = t('Nhiệm vụ Tự hành', 'Autonomous Missions');
      content = <MissionLiveWorkspace />;
      break;
    case 'workstreams':
      title = t('Phân luồng Công việc', 'Parallel Workstreams');
      content = <WorkstreamMonitor />;
      break;
    case 'figures':
      title = t('Xưởng Đồ họa Khoa học', 'Scientific Figure Studio');
      content = <FigureStudioPanel />;
      break;
    case 'opencode':
      title = t('Mã nguồn và thí nghiệm native', 'Native code & experiments');
      content = <CodePanel />;
      break;
    case 'intelligence':
      title = t('Trung tâm Phân tích Tri thức', 'Research Intelligence Hub');
      content = <IntelligenceHubPanel />;
      break;
    case 'agent-status':
      title = t('AI Agents & Phòng Lab 3D', 'AI Agents & 3D Lab');
      content = <AgentStatusView />;
      break;
    case 'protocols':
      title = t('Giao thức Thí nghiệm', 'Controlled Protocols');
      content = <ProtocolsPanel />;
      break;
    case 'claims':
      title = t('Bằng chứng & Luận điểm', 'Claims & Evidence');
      content = <EvidenceReview />;
      break;
    case 'dashboard':
      title = t('Bảng điều khiển Hệ thống', 'System Dashboard');
      content = <DashboardView />;
      break;
    case 'settings':
      title = t('Cài đặt Hệ thống', 'System Settings');
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
      title = t('Đề cương Nghiên cứu 5 Cấp độ', '5-Level Research Outline');
      content = <OutlinePanel />;
      break;
    case 'code':
      title = t('Mã nguồn & VS Code', 'Code Workspace & VS Code');
      content = <CodePanel />;
      break;
    case 'paper':
      title = t('Bản thảo Bài báo LaTeX', 'Paper Manuscript (LaTeX)');
      content = <PaperPanel />;
      break;
    case 'guide':
      title = t('Sổ tay Hướng dẫn Người mới', 'User Guide & Onboarding Manual');
      content = <UserGuidePanel />;
      break;
    case 'harness':
      title = t('Harness Studio & Thiết kế Quy trình Kéo thả', 'Harness Studio & Visual Drag-and-Drop Workflow');
      content = <CustomHarnessStudio />;
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            className="btn sm ghost"
            id="drawer-collapse-btn"
            title={t('Ẩn bảng công cụ bên phải (Thu gọn)', 'Collapse right menu')}
            aria-label={t('Ẩn bảng công cụ bên phải', 'Collapse right menu')}
            onClick={closeDrawer}
            style={{
              padding: '2px 7px',
              fontSize: 11.5,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              border: '1px solid var(--line)',
              borderRadius: 6,
            }}
          >
            <PanelRightClose size={13} />
            <span>{t('Ẩn', 'Hide')}</span>
          </button>
          <button
            className="icon sm"
            id="drawer-close-btn"
            title={t('Đóng bảng', 'Close panel')}
            aria-label={t('Đóng bảng', 'Close panel')}
            onClick={closeDrawer}
          >
            <X size={15} />
          </button>
        </div>
      </div>
      <div className="panel-b" style={{ flex: 1, overflowY: 'auto' }}>
        {content}
      </div>
    </aside>
  );
};
