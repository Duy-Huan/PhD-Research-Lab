import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { OpenCodePanel } from './OpenCodePanel';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('OpenCodePanel historical reader', () => {
  beforeEach(() => {
    vi.restoreAllMocks();useUIStore.getState().setLanguage('en');
    useUIStore.getState().setActiveTopicId('topic-1');
    vi.spyOn(api,'post').mockResolvedValue({});
  });
  it('asks for the paper topic without starting a provider', () => {
    useUIStore.getState().setActiveTopicId(null);
    const get = vi.spyOn(api,'get');
    renderWithProviders(<OpenCodePanel />);
    expect(screen.getByText('Select the paper topic to view coding history.')).toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();expect(api.post).not.toHaveBeenCalled();
  });
  it('preserves original session metadata while removing all executable controls', async () => {
    vi.spyOn(api,'get').mockResolvedValue({sessions:[{id:'old-session',status:'running',payload:{spec:{goal:'Original research code'}}}]});
    renderWithProviders(<OpenCodePanel />);
    expect(await screen.findByText('old-session: running')).toBeInTheDocument();
    expect(screen.getByText(/Original research code/)).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });
  it('does not disguise unavailable history as an empty successful result', async () => {
    vi.spyOn(api,'get').mockRejectedValue(new Error('History unavailable'));
    renderWithProviders(<OpenCodePanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('History unavailable');
    expect(screen.queryByText('No historical records.')).not.toBeInTheDocument();
  });
});
