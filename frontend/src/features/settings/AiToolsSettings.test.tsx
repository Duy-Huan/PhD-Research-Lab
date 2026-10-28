import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';
import { aiToolsEn, aiToolsVi } from '../../shared/i18n/aiTools';
import { AiToolsSettings } from './AiToolsSettings';

// FQC-AI-TOOLS-UI-662: the AI tools tab drives the 6.6.2 backend (HTTP fixtures; no live provider claims).
describe('AI tools settings', () => {
  let config: any;
  let chatgpt: any;
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.setState({ language: 'en' });
    config = { aiws: { tool_mode: 'agent' },
      tools: { agent_profile: { permissions: ['read', 'compute'], tools: ['*'] }, provider_pool: [{ provider: 'cli:codex', model: '' }] } };
    chatgpt = { enabled: false, mcp_url: '', pending: [{ id: 'req123456', client_name: 'ChatGPT' }], alerts: [{ kind: 'deny_ip' }],
      cloudflared: true, active_tokens: 0 };
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url === '/api/config') return config;
      if (url === '/api/tools') return { tools: [
        { id: 'stats_mean', kind: 'python', description: 'mean', available: true, permissions: ['compute'] },
        { id: 'delegate.codex', kind: 'native', description: 'delegate', available: false, unavailable_reason: 'codex: NOT_INSTALLED', permissions: [] }] };
      if (url.startsWith('/api/tools/search')) return { results: [{ id: 'stats_mean', kind: 'python', description: 'mean', available: true, permissions: [] }] };
      if (url === '/api/tools/clients/chatgpt') return chatgpt;
      if (url === '/api/tools/clients') return { antigravity: { registered: false } };
      if (url === '/api/runtimes/hermes/skills') return { project: ['lit-review'], shared: [], shareable: ['lit-review'] };
      return {};
    });
    vi.spyOn(api, 'post').mockResolvedValue({});
  });

  it('toggles a permission of the agent profile and keeps the others', async () => {
    renderWithProviders(<AiToolsSettings />);
    const network = await screen.findByTestId('perm-network');
    expect(network).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('perm-read')).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(network);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/config',
      { tools: { agent_profile: { permissions: ['read', 'compute', 'network'], tools: ['*'] } } }));
  });

  it('offers every permission the backend grants, including process for running programs', async () => {
    renderWithProviders(<AiToolsSettings />);
    // backend/tools/spec.py PERMISSIONS: without a toggle the owner could never grant sandbox_run_code (needs process).
    for (const id of ['read', 'compute', 'network', 'workspace_write', 'process', 'reasoning']) {
      expect(await screen.findByTestId(`perm-${id}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId('perm-process')).toHaveTextContent('Run programs');
    fireEvent.click(screen.getByTestId('perm-process'));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/config',
      { tools: { agent_profile: { permissions: ['read', 'compute', 'process'], tools: ['*'] } } }));
  });

  it('switches between agent and legacy tool mode', async () => {
    renderWithProviders(<AiToolsSettings />);
    const toggle = await screen.findByTestId('agent-mode-toggle');
    await waitFor(() => expect(toggle).toBeChecked());
    fireEvent.click(toggle);
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/config', { aiws: { tool_mode: 'legacy' } }));
  });

  it('adds and removes fallback providers', async () => {
    renderWithProviders(<AiToolsSettings />);
    await screen.findByTestId('pool-cli:codex');
    fireEvent.change(screen.getByTestId('pool-add'), { target: { value: 'app:local' } });
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/config', { tools: { provider_pool: ['cli:codex', 'app:local'] } }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/config', { tools: { provider_pool: [] } }));
  });

  it('lists registry tools with availability and searches', async () => {
    renderWithProviders(<AiToolsSettings />);
    expect(await screen.findByText('stats_mean')).toBeInTheDocument();
    expect(screen.getByText('delegate.codex').closest('li')).toHaveAttribute('title', 'codex: NOT_INSTALLED');
    // FQC-UI-QA-663: tool ids are identifiers (marked as code), each shown with its plain-language description.
    expect(screen.getByText('delegate.codex').tagName).toBe('CODE');
    expect(screen.getByText('stats_mean').closest('li')).toHaveTextContent('mean');
    // Card headers are targets: 18 px tall on Linux fonts in CI (VIS-TARGET), so they keep a 24 px minimum.
    expect(screen.getByRole('button', { name: 'Tool registry' })).toHaveStyle({ minHeight: '24px' });
    fireEvent.change(screen.getByTestId('tool-search'), { target: { value: 'mean' } });
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/tools/search?q=mean'));
  });

  it('approves a pending ChatGPT connection, shows alerts and the kill switch when enabled', async () => {
    renderWithProviders(<AiToolsSettings />);
    fireEvent.click(await screen.findByRole('button', { name: /Allow/ }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/tools/clients/chatgpt/approve', { request_id: 'req123456' }));
    expect(screen.getByTitle('Alerts')).toHaveTextContent('1');
    chatgpt = { ...chatgpt, enabled: true, mcp_url: 'https://x.trycloudflare.com/mcp', pending: [] };
    renderWithProviders(<AiToolsSettings />);
    fireEvent.click(await screen.findByRole('button', { name: 'Disconnect now' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/tools/clients/chatgpt/kill', {}));
  });

  it('registers Antigravity and shares a Hermes skill with the owner as approver', async () => {
    renderWithProviders(<AiToolsSettings />);
    fireEvent.click(await screen.findByRole('button', { name: 'Register' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/tools/clients/antigravity/register'));
    fireEvent.click(await screen.findByTitle('Share skill'));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/runtimes/hermes/share-skill', { skill: 'lit-review', approved_by: 'owner' }));
  });

  it('has the same i18n keys in Vietnamese and English', () => {
    const keys = (o: any, p = ''): string[] => Object.entries(o).flatMap(([k, v]) =>
      (typeof v === 'object' ? keys(v, `${p}${k}.`) : [`${p}${k}`]));
    expect(keys(aiToolsVi).sort()).toEqual(keys(aiToolsEn).sort());
    for (const k of keys(aiToolsVi)) expect(k.split('.').reduce((o: any, x) => o[x], aiToolsEn)).toBeTruthy();
  });
});
