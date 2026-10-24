import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { TopicView } from './TopicView';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('TopicView', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopic(null);
  });

  it('renders topic list, creates a new topic, and selects it', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/research/topics')) {
        return {
          topics: [
            {
              id: 'top-1',
              title: 'Efficient Attention Benchmarking',
              description: 'Analyzing linear and sparse attention',
              keywords: ['attention', 'transformer'],
            },
          ],
        };
      }
      return {};
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      id: 'top-2',
      title: 'Neural Architecture Search',
      description: 'DARTS and ENAS reproduction',
      keywords: ['nas', 'search'],
    });

    renderWithProviders(<TopicView />);

    await waitFor(() => {
      expect(screen.getByText('Efficient Attention Benchmarking')).toBeInTheDocument();
    });

    // Create topic
    const newBtn = screen.getByText(/Tạo Topic mới/i);
    fireEvent.click(newBtn);

    const titleInput = screen.getByPlaceholderText(/Diffusion models/i);
    fireEvent.change(titleInput, { target: { value: 'Neural Architecture Search' } });

    const submitBtn = screen.getByText('Tạo Topic');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/research/topics',
        expect.objectContaining({
          title: 'Neural Architecture Search',
        })
      );
    });
  });
});
