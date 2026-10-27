import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { MissionLiveWorkspace } from './MissionLiveWorkspace';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('MissionLiveWorkspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopicId('topic-1');
    useUIStore.getState().setLanguage('en');
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

  it('accepts results using the strict backend ReviewNote body', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ missions: [{ id: 'm-review', status: 'awaiting_review',
      tasks: [], payload: { spec: { objective: 'Completed CPU fixture awaiting review' } } }] });
    const post = vi.spyOn(api, 'post').mockImplementation(async (_url, body) => {
      // Mirrors ReviewNote's extra=forbid boundary; this fixture is not human review.
      expect(Object.keys(body as object)).toEqual(['note']);
      return { status: 'completed' };
    });
    renderWithProviders(<MissionLiveWorkspace />);
    fireEvent.click(await screen.findByRole('button', { name: 'Accept Results' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/research/topics/topic-1/missions/m-review/review', {
      note: 'Reviewed (accept) via React UI',
    }));
  });
});
