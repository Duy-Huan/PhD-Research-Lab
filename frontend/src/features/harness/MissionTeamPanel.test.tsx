import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { MissionTeamPanel } from './MissionTeamPanel';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

const MODELS = { models: [
  { id: 'cli:codex', label: 'Codex', state: 'CONNECTED', available: true },
  { id: 'app:local', label: 'Local', state: 'NO_MODEL', available: false },
] };
const TEAM = { agents: [{ id: 'researcher', role: 'researcher', purpose: 'Proposes the hypothesis', tools: ['library.search'], model: 'cli:codex' }], rationale: 'One role is enough' };

describe('MissionTeamPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setLanguage('en');
    useUIStore.getState().setActiveTopicId('topic-1');
  });

  it('proposes a team with the chosen architect model and shows an unavailable model without swapping it', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(MODELS);
    const post = vi.spyOn(api, 'post').mockResolvedValue(TEAM);
    renderWithProviders(<MissionTeamPanel workflow={() => ({ nodes: [], edges: [] })} level="L3" objective="Does smoothing help?" />);
    const architect = await screen.findByRole('combobox', { name: /Architect model/ });
    await screen.findByRole('option', { name: /Local \(app:local\) — unavailable: NO_MODEL/ });
    fireEvent.change(architect, { target: { value: 'cli:codex' } });
    fireEvent.click(screen.getByRole('button', { name: 'Propose team with AI' }));
    expect(await screen.findByText('Proposes the hypothesis')).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith('/api/harness/team/propose', { objective: 'Does smoothing help?', architect_model: 'cli:codex' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Model of researcher' }), { target: { value: 'app:local' } });
    expect(screen.getByRole('status')).toHaveTextContent('Model unavailable: NO_MODEL. The mission pauses at this step; no other model is used.');
  });

  it('compiles the canvas, lists the mission steps and notes, and creates a draft for approval', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(MODELS);
    const compiled = { spec: { tasks: [{ id: 'node-hypothesis', capability: 'agent.task' }, { id: 'node-end', capability: 'mission.report' }] },
                       notes: ['Gate: compiled to an integrity check'] };
    const post = vi.spyOn(api, 'post').mockImplementation(async (url: string, body: any) =>
      url.endsWith('/propose') ? TEAM : body.create ? { ...compiled, mission: { id: 'm-1', status: 'draft' } } : compiled);
    renderWithProviders(<MissionTeamPanel workflow={() => ({ nodes: [{ id: 'n' }], edges: [] })} level="L3" objective="Goal" />);
    await screen.findByRole('option', { name: /Codex \(cli:codex\)/ });  // options load first
    fireEvent.change(screen.getByRole('combobox', { name: /Architect model/ }), { target: { value: 'cli:codex' } });
    fireEvent.click(screen.getByRole('button', { name: 'Propose team with AI' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Preview mission' }));
    expect(await screen.findByText('agent.task')).toBeInTheDocument();
    expect(screen.getByText('Gate: compiled to an integrity check')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Create mission for approval' }));
    expect(await screen.findByText('m-1')).toBeInTheDocument();
    expect(post).toHaveBeenLastCalledWith('/api/harness/compile', expect.objectContaining({ topic_id: 'topic-1', level: 'L3', create: true, workflow: { nodes: [{ id: 'n' }], edges: [] } }));
    fireEvent.click(screen.getByRole('button', { name: 'Open Missions to approve' }));
    await waitFor(() => expect(useUIStore.getState().drawerKind).toBe('missions'));
  });

  it('shows the server error when the architect model is unavailable', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(MODELS);
    vi.spyOn(api, 'post').mockRejectedValue(new Error('cli:codex is unavailable (DISCONNECTED)'));
    renderWithProviders(<MissionTeamPanel workflow={() => ({ nodes: [], edges: [] })} level="L3" objective="Goal" />);
    await screen.findByRole('option', { name: /Codex \(cli:codex\)/ });  // options load first
    fireEvent.change(screen.getByRole('combobox', { name: /Architect model/ }), { target: { value: 'cli:codex' } });
    fireEvent.click(screen.getByRole('button', { name: 'Propose team with AI' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('cli:codex is unavailable (DISCONNECTED)');
  });
});
