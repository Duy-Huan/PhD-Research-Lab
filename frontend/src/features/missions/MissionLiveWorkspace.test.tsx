import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { MissionLiveWorkspace } from './MissionLiveWorkspace';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('MissionLiveWorkspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopicId('topic-1');
  });

  it('renders mission list and task status', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/research/topics/topic-1/missions')) {
        return {
          missions: [
            {
              id: 'm-1',
              status: 'running',
              tasks: [
                {
                  id: 't-1',
                  status: 'running',
                  payload: {
                    spec: { id: 'step-1', capability: 'code.execute' },
                  },
                },
              ],
              payload: {
                spec: { objective: 'Comprehensive Experiment Loop' },
              },
            },
          ],
        };
      }
      return {};
    });

    renderWithProviders(<MissionLiveWorkspace />);

    await waitFor(() => {
      expect(screen.getByText(/Comprehensive Experiment Loop/i)).toBeInTheDocument();
    });
  });
});
