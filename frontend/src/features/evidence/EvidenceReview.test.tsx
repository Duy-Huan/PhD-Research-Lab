import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { EvidenceReview } from './EvidenceReview';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('EvidenceReview', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders prompt when no active topic selected', () => {
    useUIStore.getState().setActiveTopicId(null);
    renderWithProviders(<EvidenceReview />);
    expect(
      screen.getByText(/Vui lòng chọn một Topic để xem và kiểm định bằng chứng/i)
    ).toBeInTheDocument();
  });

  it('renders claims list and allows creating new claim', async () => {
    useUIStore.getState().setActiveTopicId('topic-alpha');

    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/claims')) {
        return {
          claims: [
            {
              id: 'claim-1',
              text: 'Attention mechanism scales quadratically with sequence length',
              kind: 'empirical_finding',
              status: 'verified',
              confidence: 0.95,
              payload: {
                spec: {
                  text: 'Attention mechanism scales quadratically with sequence length',
                  kind: 'empirical_finding',
                  evidence: [],
                },
                status: 'verified',
                evaluations: [],
              },
              evaluations: [
                {
                  id: 'eval-1',
                  decision: 'verified',
                  reason: 'Reproduced in synthetic benchmarks',
                  agent: 'reviewer',
                  timestamp: '2026-10-24T00:00:00Z',
                },
              ],
            },
          ],
        };
      }
      return {};
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});

    renderWithProviders(<EvidenceReview />);

    await waitFor(() => {
      expect(screen.getByText(/Attention mechanism scales quadratically/i)).toBeInTheDocument();
      expect(screen.getByText(/verified/i)).toBeInTheDocument();
    });

    // Open create form
    const addBtn = screen.getByText(/Đề xuất Claim/i);
    fireEvent.click(addBtn);

    const textarea = screen.getByPlaceholderText(/Kiến trúc thu gọn Wavelet/i);
    fireEvent.change(textarea, { target: { value: 'New Test Claim for Transformer' } });

    const submitBtn = screen.getByText(/Gửi đề xuất/i);
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/research/topics/topic-alpha/claims',
        expect.objectContaining({
          text: 'New Test Claim for Transformer',
        })
      );
    });
  });
});
