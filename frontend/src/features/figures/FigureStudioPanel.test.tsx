import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { FigureStudioPanel } from './FigureStudioPanel';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { FigureRecord } from '../../shared/api/types';

describe('FigureStudioPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopicId('topic-1');
  });

  it('renders prompt when no active topic selected', () => {
    useUIStore.getState().setActiveTopicId(null);
    renderWithProviders(<FigureStudioPanel />);
    expect(
      screen.getByText(/Vui lòng chọn một Topic để mở Figure Studio/i)
    ).toBeInTheDocument();
  });

  it('renders Figure Studio panel, creates a new figure, and tests zoom controls', async () => {
    const dummyFigure: any = {
      id: 'fig-101',
      topic_id: 'topic-1',
      title: 'Loss Convergence Across Epochs',
      caption: 'Validation loss vs training epochs',
      category: 'plot_2d',
      status: 'validated',
      svg_preview: '<svg><circle cx="50" cy="50" r="40" /></svg>',
      created: '2026-10-24T00:00:00Z',
      updated: '2026-10-24T00:00:00Z',
    };

    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/figures/capabilities')) {
        return {
          presets: [{ id: 'ieee-single-column', name: 'IEEE Single Column' }],
          renderers: { plot_2d: true },
        };
      }
      if (url.includes('/api/research/topics/topic-1/figures/fig-101')) {
        return dummyFigure;
      }
      if (url.includes('/api/research/topics/topic-1/figures')) {
        return { figures: [dummyFigure] };
      }
      return {};
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ id: 'fig-created' });

    renderWithProviders(<FigureStudioPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Figure Studio/i)).toBeInTheDocument();
      expect(screen.getByText(/Loss Convergence Across Epochs/i)).toBeInTheDocument();
    });

    // Test Zoom In and Zoom Out buttons
    const percentBadge = screen.getByText(/100%/i);
    const zoomContainer = percentBadge.parentElement;
    const zoomButtons = zoomContainer?.querySelectorAll('button') || [];
    if (zoomButtons.length >= 2) {
      fireEvent.click(zoomButtons[1]); // Zoom in
      expect(screen.getByText(/120%/i)).toBeInTheDocument();
      fireEvent.click(zoomButtons[0]); // Zoom out
      expect(screen.getByText(/100%/i)).toBeInTheDocument();
    }

    // Toggle creation form
    const createBtn = screen.getByText(/Tạo Figure mới/i);
    fireEvent.click(createBtn);

    // Switch category to diagram
    const categorySelect = screen.getByDisplayValue(/2D Publication Plot/i);
    fireEvent.change(categorySelect, { target: { value: 'diagram' } });

    // Submit form
    const submitBtn = screen.getByText(/Kết xuất & Kiểm định/i);
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/research/topics/topic-1/figures',
        expect.anything()
      );
    });
  });
});
