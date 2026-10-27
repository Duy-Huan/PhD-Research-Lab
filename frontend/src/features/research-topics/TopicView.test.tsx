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
    useUIStore.getState().setLanguage('vi');
  });

  it('creates the first paper topic in an empty project', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/research/topics')) {
        return {
          topics: [],
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

    await screen.findByText(/Xác định chủ đề bài báo/);

    // Create topic
    const newBtn = screen.getByText(/Xác định chủ đề bài báo/i);
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
  it('preserves an existing paper and prevents adding a second topic to the same project', async () => {
    vi.spyOn(api,'get').mockResolvedValue({topics:[{id:'top-1',title:'Existing paper',keywords:[]}]});
    const post=vi.spyOn(api,'post').mockResolvedValue({});
    renderWithProviders(<TopicView />);
    expect(await screen.findByText('Existing paper')).toBeInTheDocument();
    expect(screen.getByRole('button',{name:/Xác định chủ đề bài báo/})).toBeDisabled();
    expect(post).not.toHaveBeenCalled();
  });

});
