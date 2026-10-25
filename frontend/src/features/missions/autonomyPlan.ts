export type AutonomyLevel = 'L1' | 'L2' | 'L3' | 'L4';
export interface ApprovedProtocol { id: string; digest: string; approval: { nonce: string } | null; }

export function autonomyPlan(topicId: string, level: AutonomyLevel, objective: string, model: string, paperIds: string[], protocol?: ApprovedProtocol, reproduction?: ApprovedProtocol) {
  if (!objective.trim() || !model.trim() || paperIds.length < 2) throw new Error('Select at least two sources and enter an objective and model.');
  const tasks: Array<{ id: string; capability: string; depends_on: string[]; args: Record<string, unknown>; preferred_engine?: string }> = [
    { id: 'grounding', capability: 'paper.inspect', depends_on: [], args: { paper_ids: paperIds } },
    { id: 'hypothesis', capability: 'paper.compare', preferred_engine: 'app', depends_on: ['grounding'], args: { paper_ids: paperIds, question: objective.trim() } },
  ];
  if (level !== 'L1') {
    if (protocol) {
      if (!protocol.approval) throw new Error('The protocol must be explicitly approved first.');
      tasks.push({ id: 'experiment', capability: 'experiment.run', depends_on: ['hypothesis'], args: { protocol_id: protocol.id, protocol_digest: protocol.digest, approval_nonce: protocol.approval.nonce } });
      if (level === 'L4') {
        if (!reproduction?.approval || reproduction.id === protocol.id || reproduction.digest !== protocol.digest) throw new Error('L4 needs a separately approved reproduction of the exact same protocol.');
        tasks.push({ id: 'reproduction', capability: 'experiment.run', depends_on: ['experiment'], args: { protocol_id: reproduction.id, protocol_digest: reproduction.digest, approval_nonce: reproduction.approval.nonce } });
        tasks.push({ id: 'validate_reproduction', capability: 'experiment.verify', depends_on: ['reproduction'], args: { from_task: 'reproduction' } });
      }
      tasks.push({ id: 'validation', capability: 'experiment.verify', depends_on: [level === 'L4' ? 'reproduction' : 'experiment'], args: { from_task: 'experiment' } });
      if (level === 'L4') tasks[tasks.length - 1].depends_on.push('experiment');
    }
    tasks.push({ id: 'report', capability: 'mission.report', depends_on: tasks.map(task => task.id), args: {} });
    tasks.push({ id: 'integrity', capability: 'artifact.verify', depends_on: ['report'], args: { from_task: 'report' } });
  }
  return {
    topic_id: topicId, objective: objective.trim(), autonomy: { level, max_output_tokens: 512 },
    permissions: ['workspace_write', 'network', 'reasoning', ...(protocol && level !== 'L1' ? ['compute'] : [])],
    control: { success_criteria: ['Preserve scoped evidence and review limitations'], allowed_engines: ['deterministic', 'app'], app_backend: 'local', app_model: model.trim(), allow_api_billing: false, end_date: new Date(Date.now() + 3600_000).toISOString(), max_wall_seconds: 3600 },
    limits: { max_seconds: 600, max_reasoning_calls: 1 }, tasks,
  };
}
