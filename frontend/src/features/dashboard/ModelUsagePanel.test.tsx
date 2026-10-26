import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';
import { ModelUsagePanel } from './ModelUsagePanel';

describe('measured usage rendering (HTTP fixtures)', () => {
  beforeEach(() => { vi.restoreAllMocks(); useUIStore.setState({ language: 'en' }); });
  it('keeps unknown usage distinct from measured zero and reports partial denominators', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ total_requests: 3, malformed_records: 1, truncated: true, providers: [
      { provider: 'hermes', model: 'observed:free', requests: 3, completed: 1, failed: 1, cancelled: 1,
        input_tokens: null, output_tokens: null, usage_reported: 0, mean_latency_ms: null },
    ] });
    renderWithProviders(<ModelUsagePanel />);
    expect(await screen.findByText('observed:free')).toBeInTheDocument();
    expect(screen.getByText('— / —')).toBeInTheDocument();
    expect(screen.getByText('0 / 3')).toBeInTheDocument();
    expect(screen.getByText('1 / 1 / 1')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Malformed records excluded: 1');
    expect(screen.getByText(/limited to the latest/)).toBeInTheDocument();
  });
  it('shows a malformed response as an error without crashing or inventing a zero report', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({});
    renderWithProviders(<ModelUsagePanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load usage.');
    expect(screen.queryByText('No recorded gateway requests yet.')).not.toBeInTheDocument();
  });
  it('reports the genuine empty state separately from a network failure', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ providers: [], total_requests: 0, malformed_records: 0, truncated: false });
    renderWithProviders(<ModelUsagePanel />);
    expect(await screen.findByText('No recorded gateway requests yet.')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
