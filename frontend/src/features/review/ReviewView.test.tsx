import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { ReviewView } from './ReviewView';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('ReviewView', () => {
  const mockReviewDetail = {
    meta: {
      id: 'rev-1',
      title: 'Deep Bayesian Physics Neural Networks',
      file: 'paper.pdf',
      n_reviewers: 3,
      venue: { kind: 'conference', tier: 'A*', name: 'NeurIPS 2026' },
    },
    state: {
      reviewers: {
        r1: {
          id: 'R1',
          persona: 'Theoretical Rigor Specialist',
          text: 'Thorough mathematical proof in section 3 is required.',
          score: 'Borderline Accept (6/10)',
        },
        r2: {
          id: 'R2',
          persona: 'Empirical Benchmark Reviewer',
          text: 'Missing ablation on high-dimensional Gaussian noise.',
          score: 'Strong Accept (8/10)',
        },
      },
      meta: {
        text: 'The paper provides strong contributions. Address Reviewer 1 theoretical concerns.',
        decision: 'Accept',
      },
      issues: [
        {
          id: 'iss-1',
          severity: 'Major',
          title: 'Section 3 Proof Defect',
          description: 'Lemma 2 assumes convexity without justification.',
          section: '3.2',
          status: 'open',
        },
        {
          id: 'iss-2',
          severity: 'Minor',
          title: 'Citation Typo',
          description: 'Reference [14] year is 2024 not 2021.',
          section: 'References',
          status: 'open',
        },
      ],
      fixes: {
        'iss-1': {
          original: 'Assume f is strictly convex.',
          revised: 'By condition (C.1), f satisfies strong pseudo-convexity.',
          status: 'proposed',
        },
      },
      guide: { text: 'Focus on Lemma 2 revision.' },
      response: { text: 'We thank the reviewers for constructive feedback.' },
    },
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopicId('topic-1');
  });

  it('renders empty state when no reviews exist', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url === '/api/review') {
        return { reviews: [] };
      }
      return {};
    });

    renderWithProviders(<ReviewView />);

    await waitFor(() => {
      expect(screen.getByText(/Chưa có bản thảo nào đang bình duyệt/i)).toBeInTheDocument();
    });
  });

  it('renders review sessions, reviewers R1-R2, meta-review, and issues with fixes', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url === '/api/review') {
        return { reviews: [mockReviewDetail.meta], active: 'rev-1' };
      }
      if (url === '/api/review/rev-1') {
        return mockReviewDetail;
      }
      return {};
    });

    const putSpy = vi.spyOn(api, 'put').mockResolvedValue({});
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});

    // Mock global fetch for SSE stage execution
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => {
          let readCount = 0;
          return {
            read: async () => {
              if (readCount === 0) {
                readCount++;
                const encoder = new TextEncoder();
                return {
                  done: false,
                  value: encoder.encode('data: {"delta": "Analyzing section 1..."}\n\n'),
                };
              }
              return { done: true, value: undefined };
            },
          };
        },
      },
    }) as any;

    renderWithProviders(<ReviewView />);

    await waitFor(() => {
      expect(screen.getByText(/Deep Bayesian Physics Neural Networks/i)).toBeInTheDocument();
      expect(screen.getByText(/Theoretical Rigor Specialist/i)).toBeInTheDocument();
      expect(screen.getByText(/Empirical Benchmark Reviewer/i)).toBeInTheDocument();
      expect(screen.getByText(/Tổng hợp của Trưởng ban Chuyên môn|Area Chair Meta-Review/i)).toBeInTheDocument();
      expect(screen.getByText(/Section 3 Proof Defect/i)).toBeInTheDocument();
    });

    // Accept proposed fix
    const acceptFixBtn = screen.getByText(/Chấp nhận bản sửa/i);
    fireEvent.click(acceptFixBtn);
    expect(putSpy).toHaveBeenCalledWith('/api/review/rev-1/issue/iss-1', {
      status: 'done',
      fix_status: 'accepted',
    });

    // Trigger AI Fix for second issue
    const aiFixBtn = screen.getByText(/Đề xuất (chỉnh )?sửa tự động/i);
    fireEvent.click(aiFixBtn);

    // Click stage button (e.g. Chạy Phản biện #1)
    const runR1Btn = screen.getByText(/Chạy Phản biện #1|Run Reviewer #1/i);
    fireEvent.click(runR1Btn);

    // Apply fixes to LaTeX
    const applyTexBtn = screen.getByText(/Áp dụng vá \.tex|Apply Patches to \.tex/i);
    fireEvent.click(applyTexBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/review/rev-1/apply', {});
  });

  it('handles manuscript file upload and session deletion', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url === '/api/review') {
        return { reviews: [mockReviewDetail.meta], active: 'rev-1' };
      }
      if (url === '/api/review/rev-1') {
        return mockReviewDetail;
      }
      return {};
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      meta: { id: 'rev-new', title: 'New Paper' },
    });
    const deleteSpy = vi.spyOn(api, 'delete').mockResolvedValue({});
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    const { container } = renderWithProviders(<ReviewView />);

    await waitFor(() => {
      expect(screen.getByText(/Deep Bayesian Physics Neural Networks/i)).toBeInTheDocument();
    });

    // Upload manuscript
    const fileInput = container.querySelector('input[type="file"][accept*=".pdf"]') as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();
    const testFile = new File(['%PDF-1.4 test'], 'paper.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [testFile] } });

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/review/upload', expect.any(FormData));
    });

    // Delete review session
    const deleteBtn = container.querySelector('button.icon.sm') as HTMLButtonElement;
    expect(deleteBtn).toBeInTheDocument();
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith('/api/review/rev-1');
    });
  });
});
