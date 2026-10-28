import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';
import { GatewayConnections } from './GatewayConnections';

describe('gateway connections (HTTP fixtures, no live-provider claims)', () => {
  let config: any;
  let inventory: any;
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.setState({ language: 'en' });
    config = { gateway: { cli_profile: 'review' }, hermes: { enabled: true, model: 'observed:free' } };
    inventory = { providers: [
      { id: 'runtime:hermes', label: 'Hermes Agent', transport: 'runtime', state: 'READY', available: true,
        models: ['observed:free'], readiness: { authentication: 'UNKNOWN', inference: 'NOT_RUN' },
        model_catalog: { origin: 'live-account-catalog', models: ['observed:free'], verified: false } },
      { id: 'cli:codex', label: 'Codex subscription', transport: 'cli', state: 'UNKNOWN', available: true,
        models: [], readiness: { inference: 'NOT_RUN' } },
    ] };
    vi.spyOn(api, 'get').mockImplementation(async () => inventory);
    vi.spyOn(api, 'post').mockResolvedValue({});
  });
  async function hermes() {
    return within((await screen.findByText('Hermes Agent')).closest('article')!);
  }

  it('keeps installation/authentication/catalog distinct from inference and never requests an API key', async () => {
    renderWithProviders(<GatewayConnections config={config} />);
    const panel = await hermes();
    expect(panel.getByText('UNKNOWN')).toBeInTheDocument();
    expect(panel.getByText('NOT_RUN')).toBeInTheDocument();
    expect(panel.getByText('live-account-catalog')).toBeInTheDocument();
    expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
  });

  it('selects only catalog free choices and saves the Hermes model without another provider settings', async () => {
    renderWithProviders(<GatewayConnections config={config} />);
    const select = (await hermes()).getByRole('combobox', { name: 'Hermes default model' });
    expect(within(select).getByRole('option', { name: 'observed:free' })).toBeInTheDocument();
    expect(within(select).queryByRole('option', { name: 'invented-paid-model' })).not.toBeInTheDocument();
    fireEvent.change(select, { target: { value: 'observed:free' } });
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/config', { hermes: { model: 'observed:free' } }));
  });

  it('keeps Claude Code signed in with a long-lived token from claude setup-token (FQC-CLAUDE-SIGNIN-663)', async () => {
    inventory.providers.push({ id: 'cli:claude_code', label: 'Claude (Claude Code CLI)', transport: 'cli', state: 'AUTH_EXPIRED',
      available: false, models: [], detail: "this computer's Claude sign-in has expired", readiness: { inference: 'NOT_RUN' } });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const view = renderWithProviders(<GatewayConnections config={config} />);
    const claude = within((await screen.findByText('Claude (Claude Code CLI)')).closest('article')!);
    expect(within((await screen.findByText('Codex subscription')).closest('article')!)
      .queryByLabelText(/Long-lived Claude token/)).not.toBeInTheDocument();
    fireEvent.click(claude.getByRole('button', { name: 'Copy command' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('claude setup-token'));
    const field = claude.getByLabelText(/Long-lived Claude token/);
    expect(field).toHaveAttribute('type', 'password');
    expect(claude.getByRole('button', { name: 'Save token' })).toBeDisabled();
    fireEvent.change(field, { target: { value: ' sk-ant-oat01-abc ' } });
    fireEvent.click(claude.getByRole('button', { name: 'Save token' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/config', { gateway: { claude_code_oauth_token: 'sk-ant-oat01-abc' } }));
    expect(field).toHaveValue('');

    view.unmount();
    config.gateway.has_claude_code_oauth_token = true;
    renderWithProviders(<GatewayConnections config={config} />);
    const saved = within((await screen.findByText('Claude (Claude Code CLI)')).closest('article')!);
    expect(saved.getByText(/A long-lived token is saved/)).toBeInTheDocument();
    fireEvent.click(saved.getByRole('button', { name: 'Remove token' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/config', { gateway: { claude_code_oauth_token: '' } }));
  });

  it('uses official native Codex launch instead of a vendor website', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    renderWithProviders(<GatewayConnections config={config} />);
    const panel = within((await screen.findByText('Codex subscription')).closest('article')!);
    fireEvent.click(panel.getByRole('button', { name: 'Official sign-in' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/providers/codex/connect', { mode: 'terminal' }));
    expect(open).not.toHaveBeenCalled();
  });

  it('preserves the selected runtime profile during model discovery', async () => {
    config.gateway.cli_profile = 'assisted';
    renderWithProviders(<GatewayConnections config={config} />);
    fireEvent.click((await hermes()).getByRole('button', { name: 'Discover models' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/runtimes/hermes/models', { profile: 'assisted' }));
  });

  it('does not turn a returned unavailable launch into action success', async () => {
    vi.mocked(api.post).mockResolvedValue({ launched: false, state: 'UNAVAILABLE', detail: 'Pinned runtime is unavailable' });
    renderWithProviders(<GatewayConnections config={config} />);
    fireEvent.click((await hermes()).getByRole('button', { name: 'Official sign-in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Pinned runtime is unavailable');
    expect(screen.queryByText(/Action completed/)).not.toBeInTheDocument();
  });

  it('reports a real test reply separately from connection readiness', async () => {
    vi.mocked(api.post).mockResolvedValue({ reply: 'OK' });
    renderWithProviders(<GatewayConnections config={config} />);
    fireEvent.click((await hermes()).getByRole('button', { name: 'Test inference' }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/models/test', { provider: 'runtime:hermes', model: 'observed:free' }));
    expect(await screen.findByText('Model replied: OK')).toBeInTheDocument();
  });

  it('prevents an unavailable runtime or empty model from starting inference', async () => {
    config.hermes.model = ''; inventory.providers[0].available = false;
    renderWithProviders(<GatewayConnections config={config} />);
    const button = (await hermes()).getByRole('button', { name: 'Test inference' });
    expect(button).toBeDisabled(); fireEvent.click(button);
    expect(api.post).not.toHaveBeenCalled();
  });

  it('shows request errors accessibly and allows a fresh action', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('Controlled network failure'));
    renderWithProviders(<GatewayConnections config={config} />);
    fireEvent.click((await hermes()).getByRole('button', { name: 'Start Hermes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Controlled network failure');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Start Hermes' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Start Hermes' }));
    expect(await screen.findByText(/Action completed/)).toBeInTheDocument();
  });
});
