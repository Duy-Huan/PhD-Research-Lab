import type {
  Mission,
  OpenCodeSession,
  AgentOfficeViewModel,
  AgentPresence,
  AgentActivity,
} from '../api/types';

function inferZone(role: string, engine: string): AgentOfficeViewModel['zone'] {
  const r = (role || '').toLowerCase();
  const e = (engine || '').toLowerCase();
  if (e === 'opencode' || r.includes('code') || r.includes('implement') || r.includes('compute')) {
    return 'compute';
  }
  if (r.includes('paper') || r.includes('lit') || r.includes('inspect') || e === 'feynman') {
    return 'literature';
  }
  if (r.includes('verify') || r.includes('validate') || r.includes('review') || r.includes('claim')) {
    return 'review';
  }
  if (r.includes('experiment') || r.includes('protocol') || r.includes('figure')) {
    return 'lab_bench';
  }
  if (r.includes('orchestrat') || r.includes('plan') || r.includes('pi')) {
    return 'podium';
  }
  return 'lab_bench';
}

function inferArchetype(role: string, engine: string): AgentOfficeViewModel['archetype'] {
  const r = (role || '').toLowerCase();
  const e = (engine || '').toLowerCase();
  if (e === 'opencode' || r.includes('code') || r.includes('implement')) return 'opencode';
  if (e === 'feynman' || r.includes('paper') || r.includes('lit')) return 'feynman';
  if (e === 'openscience' || r.includes('protocol') || r.includes('experiment')) return 'openscience';
  if (r.includes('review') || r.includes('verify') || r.includes('claim')) return 'reviewer';
  if (r.includes('figure') || r.includes('latex')) return 'figure_fellow';
  return 'pi';
}

export function mapMissionsToAgentViewModels(
  missions: Mission[],
  projectId: string,
  topicId?: string,
  opencodeSessions: OpenCodeSession[] = []
): AgentOfficeViewModel[] {
  const models: AgentOfficeViewModel[] = [];

  for (const m of missions) {
    if (topicId && m.topic_id !== topicId) continue;

    for (const t of m.tasks) {
      const spec = t.payload.spec;
      const engine = t.payload.result?.engine || spec.preferred_engine || 'deterministic';
      const role = spec.capability || 'researcher';
      const displayName = `${spec.id} (${engine})`;

      let presence: AgentPresence = 'idle';
      let activity: AgentActivity = 'none';

      if (t.status === 'running') {
        presence = 'running';
        if (spec.capability.includes('paper') || spec.capability.includes('inspect')) {
          activity = 'reading';
        } else if (spec.capability.includes('code') || spec.capability.includes('opencode')) {
          activity = 'writing';
        } else if (spec.capability.includes('verify') || spec.capability.includes('validate')) {
          activity = 'reviewing';
        } else if (spec.capability.includes('experiment')) {
          activity = 'executing';
        } else if (spec.capability.includes('figure') || spec.capability.includes('report')) {
          activity = 'reporting';
        } else {
          activity = 'searching';
        }
      } else if (t.status === 'pending') {
        presence = m.status === 'running' || m.status === 'queued' ? 'queued' : 'idle';
      } else if (t.status === 'completed') {
        presence = 'completed';
      } else if (t.status === 'failed') {
        presence = 'failed';
      } else if (t.status === 'interrupted' || t.status === 'blocked') {
        presence = 'paused';
      }

      if (m.payload.blocking_reason) {
        presence = 'awaiting_approval';
      }

      models.push({
        agentId: `${m.id}_${t.id}`,
        missionId: m.id,
        taskId: t.id,
        projectId,
        topicId: m.topic_id,
        displayName,
        role,
        engine,
        presence,
        activity,
        lastObservedAt: m.updated || m.created,
        canInspect: true,
        canPause: presence === 'running',
        canResume: presence === 'paused',
        hasApprovalRequest: presence === 'awaiting_approval',
        zone: inferZone(role, engine),
        archetype: inferArchetype(role, engine),
        personality: 'Autonomous Mission Task Specialist',
        skillCommand: '/status',
        speechBubble:
          presence === 'running'
            ? `Executing ${spec.capability}…`
            : presence === 'awaiting_approval'
            ? 'Waiting for PI approval…'
            : undefined,
      });
    }
  }

  // Also map v6.4.1 OpenCode Parallel Core sessions into AgentOfficeViewModel
  for (const s of opencodeSessions) {
    if (topicId && s.topic_id !== topicId) continue;

    let presence: AgentPresence = 'idle';
    let activity: AgentActivity = 'none';

    if (s.status === 'running') {
      presence = 'running';
      activity = 'writing';
    } else if (s.status === 'awaiting_approval') {
      presence = 'awaiting_approval';
      activity = 'reviewing';
    } else if (s.status === 'blocked_by_quota') {
      presence = 'rate_limited';
      activity = 'none';
    } else if (s.status === 'completed') {
      presence = 'completed';
    } else if (s.status === 'failed') {
      presence = 'failed';
    } else if (s.status === 'paused' || s.status === 'reconciled_with_gap') {
      presence = 'paused';
    }

    models.push({
      agentId: `opencode_${s.id}`,
      sessionId: s.id,
      missionId: s.mission_id || undefined,
      taskId: s.task_id || s.id,
      projectId,
      topicId: s.topic_id,
      displayName: `${s.id} (opencode)`,
      role: s.payload?.spec?.goal?.slice(0, 40) || 'opencode.implement',
      engine: 'opencode',
      presence,
      activity,
      lastObservedAt: s.updated || s.created,
      canInspect: true,
      canPause: presence === 'running',
      canResume: presence === 'paused',
      hasApprovalRequest: s.status === 'awaiting_approval',
      zone: 'compute',
      archetype: 'opencode',
      personality: 'Systems & GPU Sandbox Engineer',
      skillCommand: '/opencode',
      speechBubble:
        presence === 'running' ? 'Running parallel benchmark in sandbox…' : undefined,
    });
  }

  return models;
}

/**
 * Builds the complete University Lab Roster combining live Mission/OpenCode agents
 * with the permanent core faculty stations of the PhD Research Lab.
 */
export function buildUniversityLabRoster(
  liveAgents: AgentOfficeViewModel[],
  projectId: string,
  topicId?: string,
  agentModes?: Record<string, string>
): AgentOfficeViewModel[] {
  const nowIso = new Date().toISOString();
  const anyRunning = liveAgents.some((a) => a.presence === 'running');

  const coreFaculty: AgentOfficeViewModel[] = [
    {
      agentId: 'faculty_pi_orchestrator',
      projectId,
      topicId,
      displayName: 'Prof. AI Orchestrator (PI)',
      role: 'Principal Investigator · Điều phối Đề cương 5 Cấp & Mission DAG',
      engine: agentModes?.assistant || agentModes?.research || 'auto',
      presence: anyRunning ? 'running' : 'idle',
      activity: anyRunning ? 'reviewing' : 'reading',
      lastObservedAt: nowIso,
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: liveAgents.some((a) => a.hasApprovalRequest),
      zone: 'podium',
      archetype: 'pi',
      personality: 'Điềm tĩnh, chiến lược, định hướng giả thuyết khoa học & điều phối toàn Lab',
      skillCommand: '/outline',
      speechBubble: anyRunning
        ? 'Đang giám sát tiến độ DAG & đồng bộ kết quả giữa các nhóm…'
        : 'Sẵn sàng thảo luận Đề cương 5 cấp độ & phân công nhiệm vụ mới!',
    },
    {
      agentId: 'faculty_feynman_lit',
      projectId,
      topicId,
      displayName: 'Dr. Feynman (Literature & SKB)',
      role: 'Literature & Deep Discovery · OpenAlex / ArXiv / Semantic Scholar',
      engine: 'feynman',
      presence: 'idle',
      activity: 'reading',
      lastObservedAt: nowIso,
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      zone: 'literature',
      archetype: 'feynman',
      personality: 'Uyên bác, tò mò, chuyên gia săn tìm bài báo Q1/A* và phát hiện Research Gap',
      skillCommand: '/feynman',
      speechBubble: 'Đang đối chiếu trích dẫn CORE/SCImago Q1 trong Thư viện SKB…',
    },
    {
      agentId: 'faculty_openscience_lab',
      projectId,
      topicId,
      displayName: 'Dr. OpenScience (Protocols)',
      role: 'Scientific Hypothesis & Controlled Experimentation (:4096)',
      engine: 'openscience',
      presence: 'idle',
      activity: 'executing',
      lastObservedAt: nowIso,
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      zone: 'lab_bench',
      archetype: 'openscience',
      personality: 'Thực nghiệm chuẩn mực, kiểm soát biến số chặt chẽ, thiết kế Ablation Study',
      skillCommand: '/openscience',
      speechBubble: 'Đang kiểm định giao thức thí nghiệm (Protocol) & đối chứng Baseline…',
    },
    {
      agentId: 'faculty_opencode_core',
      projectId,
      topicId,
      displayName: 'Lead OpenCode (HPC & Code)',
      role: 'Parallel Core Engineering & Reproducible Sandbox (:4097)',
      engine: 'opencode',
      presence: 'idle',
      activity: 'writing',
      lastObservedAt: nowIso,
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      zone: 'compute',
      archetype: 'opencode',
      personality: 'Tốc độ cao, tối ưu hóa CUDA/VRAM, viết code song song sạch & tái lập 100%',
      skillCommand: '/opencode',
      speechBubble: 'Cụm HPC & GPU Sandbox sẵn sàng chạy huấn luyện song song!',
    },
    {
      agentId: 'faculty_reviewer_chair',
      projectId,
      topicId,
      displayName: 'Area Chair & Reviewer R1–R3',
      role: 'Peer Review, Claim Verification & Evidence Audit',
      engine: agentModes?.reviewer || 'claude',
      presence: 'idle',
      activity: 'reviewing',
      lastObservedAt: nowIso,
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      zone: 'review',
      archetype: 'reviewer',
      personality: 'Khắt khe, khách quan, soi xét từng Claim và bằng chứng theo chuẩn NeurIPS/ICML',
      skillCommand: '/review',
      speechBubble: 'Sẵn sàng thẩm định bản thảo theo chuẩn Hội đồng R1–R3 & Area Chair.',
    },
    {
      agentId: 'faculty_figure_studio',
      projectId,
      topicId,
      displayName: 'Figure Studio & LaTeX Fellow',
      role: 'Scientific Visualization (Nature/IEEE Presets) & Manuscript',
      engine: agentModes?.utility || 'auto',
      presence: 'idle',
      activity: 'reporting',
      lastObservedAt: nowIso,
      canInspect: true,
      canPause: false,
      canResume: false,
      hasApprovalRequest: false,
      zone: 'lounge',
      archetype: 'figure_fellow',
      personality: 'Tinh tế, chuẩn thẩm mỹ Nature/Science/IEEE, chuyên gia biểu đồ vector & LaTeX',
      skillCommand: '/paper',
      speechBubble: 'Đang tinh chỉnh đồ thị Vector SVG 600 DPI & bố cục LaTeX.',
    },
  ];

  if (liveAgents.length === 0) {
    return coreFaculty;
  }

  return [...liveAgents, ...coreFaculty];
}
