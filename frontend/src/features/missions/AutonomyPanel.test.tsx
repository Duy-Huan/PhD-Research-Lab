import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, cleanup } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { AutonomyPanel } from './AutonomyPanel';
import { autonomyPlan } from './autonomyPlan';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

const protocol = { id: 'p1', digest: 'same', approval: { nonce: 'n1' } };
const replica = { id: 'p2', digest: 'same', approval: { nonce: 'n2' } };
const mission = (status = 'draft') => ({
  id: 'm1', status, payload: { plan_digest: 'plan', blocking_reason: 'Review required', spec: { objective: 'Bounded test', autonomy: { level: 'L2' } } },
  tasks: [{ id: 'step', status: 'completed', payload: { result: { output: { text: 'Real answer is separately tested live' } }, result_digest: 'result' } }],
});

function setup(rows: unknown[] = [], enabled = true) {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
    if (url.endsWith('/missions')) return { missions: rows };
    if (url.includes('/papers')) return { papers: [{ id: 'a', title: 'Paper alpha' }, { id: 'b', title: 'Paper beta' }] };
    if (url.endsWith('/protocols')) return { protocols: [protocol, replica, { id: 'unapproved', approval: null }] };
    return { enabled };
  });
  vi.spyOn(api, 'post').mockResolvedValue({});
  vi.spyOn(api, 'put').mockResolvedValue({});
}

describe('autonomy policy contracts and user decisions', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopicId('topic1');
    useUIStore.getState().setLanguage('en');
  });

  it('builds bounded L1–L4 plans and preserves independent reproduction approvals', () => {
    for (const level of ['L1', 'L2', 'L3', 'L4'] as const) {
      const spec = autonomyPlan('t', level, ' Goal ', ' qwen/qwen3.5-9b ', ['a', 'b']);
      expect(spec.control.allow_api_billing).toBe(false);
      expect(spec.autonomy.level).toBe(level);
      expect(spec.tasks.map(t => t.capability)).toContain('paper.compare');
      expect(spec.tasks.some(t => t.capability === 'mission.report')).toBe(level !== 'L1');
    }
    expect(autonomyPlan('t', 'L2', 'Goal', 'm', ['a', 'b'], protocol).permissions).toContain('compute');
    expect(autonomyPlan('t', 'L1', 'Goal', 'm', ['a', 'b'], protocol).permissions).not.toContain('compute');
    const l4 = autonomyPlan('t', 'L4', 'Goal', 'm', ['a', 'b'], protocol, replica);
    expect(l4.tasks.find(t => t.id === 'reproduction')?.args.approval_nonce).toBe('n2');
    expect(l4.tasks.at(-2)?.depends_on).toContain('reproduction');
    for (const params of [['', 'm', ['a', 'b']], ['Goal', '', ['a', 'b']], ['Goal', 'm', ['a']]] as const) {
      expect(() => autonomyPlan('t', 'L2', params[0], params[1], [...params[2]])).toThrow();
    }
    expect(() => autonomyPlan('t', 'L2', 'Goal', 'm', ['a', 'b'], { ...protocol, approval: null })).toThrow(/approved/);
    for (const invalid of [undefined, protocol, { ...replica, digest: 'different' }]) {
      expect(() => autonomyPlan('t', 'L4', 'Goal', 'm', ['a', 'b'], protocol, invalid)).toThrow(/reproduction/);
    }
  });

  it('requires a topic and provides explicit Research OS opt-in', async () => {
    setup([], false);
    useUIStore.getState().setActiveTopicId(null);
    const rendered = renderWithProviders(<AutonomyPanel />);
    expect(screen.getByText(/Select a topic/)).toBeInTheDocument();
    rendered.unmount();
    useUIStore.getState().setActiveTopicId('topic1');
    renderWithProviders(<AutonomyPanel />);
    fireEvent.click(await screen.findByText('Enable Research OS'));
    await waitFor(() => expect(api.put).toHaveBeenCalledWith('/api/research/os-settings', { enabled: true }));
  });

  it('creates an L4 draft from user-selected sources, model and reproduction', async () => {
    setup(); renderWithProviders(<AutonomyPanel />);
    fireEvent.change(screen.getByLabelText('Interaction level'), { target: { value: 'L4' } });
    fireEvent.change(screen.getByLabelText('Objective'), { target: { value: 'Bounded objective' } });
    fireEvent.change(screen.getByLabelText('LM Studio model'), { target: { value: 'local-model-variant' } });
    fireEvent.click(await screen.findByLabelText('Paper alpha'));
    fireEvent.click(screen.getByLabelText('Paper alpha')); // deselection must remove the source
    fireEvent.click(screen.getByLabelText('Paper alpha'));
    fireEvent.click(screen.getByLabelText('Paper beta'));
    fireEvent.change(screen.getByLabelText('Approved protocol (optional)'), { target: { value: 'p1' } });
    fireEvent.change(screen.getByLabelText('Separately approved reproduction protocol'), { target: { value: 'p2' } });
    fireEvent.click(screen.getByText('Create draft'));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/research/topics/topic1/missions', expect.objectContaining({ autonomy: { level: 'L4', max_output_tokens: 512 } })));
  });

  it.each([
    ['draft', 'Approve plan and run', '/approve'],
    ['paused', 'Approve plan and run', '/approve'],
    ['awaiting_step_review', 'Accept step', '/steps/step/review'],
    ['awaiting_step_review', 'Reject step', '/steps/step/review'],
    ['awaiting_review', 'Complete review', '/review'],
    ['running', 'Cancel workflow', '/cancel'],
  ])('binds %s user action %s to the persisted plan/result', async (status, label, suffix) => {
    setup([mission(status)]); renderWithProviders(<AutonomyPanel />);
    const button = await screen.findByText(label);
    if (suffix !== '/cancel') {
      expect(button).toBeDisabled();
      fireEvent.change(screen.getByLabelText('Review note'), { target: { value: 'I inspected the displayed result' } });
    }
    fireEvent.click(button);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/research/topics/topic1/missions/m1' + suffix, expect.any(Object)));
    if (suffix.includes('/steps/')) expect(api.post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ result_digest: 'result', plan_digest: 'plan', accept: label === 'Accept step' }));
  });

  it('surfaces request failures, final states and missing step data without false success', async () => {
    setup([mission('running')]);
    vi.mocked(api.post).mockRejectedValue(new Error('Transport failed'));
    renderWithProviders(<AutonomyPanel />);
    fireEvent.click(await screen.findByText('Cancel workflow'));
    expect(await screen.findByText('Transport failed')).toBeInTheDocument();
    cleanup();
    setup([{ ...mission('completed'), tasks: [] }, { ...mission('awaiting_step_review'), id: 'm2', tasks: [] }]);
    renderWithProviders(<AutonomyPanel />);
    await screen.findByText(/completed ·/);
    expect(screen.queryByText('Accept step')).not.toBeInTheDocument();
  });

  it('reports query errors and creates a source-only draft with no protocol', async () => {
    setup();
    const normalGet = vi.mocked(api.get).getMockImplementation()!;
    vi.mocked(api.get).mockImplementation(async url => {
      if (url.endsWith('/protocols')) throw new Error('Protocol list unavailable');
      return normalGet(url);
    });
    renderWithProviders(<AutonomyPanel />);
    expect(await screen.findByText('Error: Protocol list unavailable')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Objective'), { target: { value: 'Source-only analysis' } });
    fireEvent.click(await screen.findByLabelText('Paper alpha'));
    fireEvent.click(screen.getByLabelText('Paper beta'));
    fireEvent.click(screen.getByText('Create draft'));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ permissions: ['workspace_write', 'network', 'reasoning'] })));
  });

  it('surfaces settings discovery failure before plan approval', async () => {
    setup();
    const normalGet = vi.mocked(api.get).getMockImplementation()!;
    vi.mocked(api.get).mockImplementation(async url => {
      if (url.endsWith('/os-settings')) throw new Error('Settings unavailable');
      return normalGet(url);
    });
    renderWithProviders(<AutonomyPanel />);
    expect(await screen.findByText('Error: Settings unavailable')).toBeInTheDocument();
  });
});
