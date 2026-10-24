import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { LibraryPanel } from './LibraryPanel';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('LibraryPanel', () => {
  const mockPapers = [
    {
      id: 'p-1',
      key: 'vaswani2017',
      file: 'vaswani2017.pdf',
      title: 'Attention Is All You Need',
      authors: ['Vaswani', 'Shazeer', 'Parmar'],
      year: '2017',
      venue: 'NeurIPS',
      rank: { rank: 'CORE A*', tier: 'CORE A*' },
      abstract: 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.',
      bibtex: '@inproceedings{vaswani2017,\n  title={Attention Is All You Need}\n}',
    },
    {
      id: 'p-2',
      key: 'he2016deep',
      file: 'he2016deep.pdf',
      title: 'Deep Residual Learning for Image Recognition',
      authors: ['Kaiming He', 'Xiangyu Zhang'],
      year: '2016',
      venue: 'CVPR',
      ranking: { tier: 'IEEE TPAMI / CVPR' },
      abstract: 'Deeper neural networks are more difficult to train.',
      metadata_only: false,
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setProject({ name: 'Default', data_dir: '/path/data' });
  });

  it('renders search input and paper list with ranking and in-app preview', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ papers: mockPapers });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});
    const deleteSpy = vi.spyOn(api, 'delete').mockResolvedValue({});
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    const { container } = renderWithProviders(<LibraryPanel />);

    await waitFor(() => {
      expect(screen.getByText('Attention Is All You Need')).toBeInTheDocument();
      expect(screen.getByText('Deep Residual Learning for Image Recognition')).toBeInTheDocument();
      expect(screen.getByText('CORE A*')).toBeInTheDocument();
    });

    // Filter papers
    const filterInput = screen.getByPlaceholderText(/Lọc theo tiêu đề/i);
    fireEvent.change(filterInput, { target: { value: 'Residual' } });
    expect(screen.queryByText('Attention Is All You Need')).not.toBeInTheDocument();
    expect(screen.getByText('Deep Residual Learning for Image Recognition')).toBeInTheDocument();

    // Reset filter
    fireEvent.change(filterInput, { target: { value: '' } });

    // Open In-App Preview modal
    const previewBtns = screen.getAllByText('Xem trước');
    fireEvent.click(previewBtns[0]);

    expect(screen.getByText(/Tóm tắt bài báo/i)).toBeInTheDocument();
    expect(screen.getAllByText(/The dominant sequence transduction models/i).length).toBeGreaterThanOrEqual(1);

    // Close Preview modal
    const closeBtn = screen.getAllByRole('button').find((b) => b.querySelector('svg.lucide-x'));
    if (closeBtn) fireEvent.click(closeBtn);

    // Test AI Metadata Refine button
    const refineBtns = screen.getAllByText(/Chuẩn hóa AI/i);
    if (refineBtns.length > 0) {
      fireEvent.click(refineBtns[0]);
      expect(postSpy).toHaveBeenCalledWith('/api/library/refine', { file: 'vaswani2017.pdf' });
    }

    // Test Delete Paper button
    const deleteBtns = screen.getAllByTitle(/Xóa bài báo/i);
    if (deleteBtns.length > 0) {
      fireEvent.click(deleteBtns[0]);
      expect(deleteSpy).toHaveBeenCalledWith('/api/library/vaswani2017.pdf');
    }
  });

  it('switches to Academic Search tab and executes query', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ papers: [] });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      sources: [
        {
          title: 'Physics-informed Neural Networks (PINNs)',
          authors: ['Raissi', 'Perdikaris', 'Karniadakis'],
          year: 2019,
          venue: 'Journal of Computational Physics',
          abstract: 'We introduce physics-informed neural networks.',
          url: 'https://doi.org/10.1016/j.jcp.2018.10.045',
        },
      ],
    });

    renderWithProviders(<LibraryPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Tìm kiếm Học thuật/i)).toBeInTheDocument();
    });

    // Switch to search tab
    const searchTabBtn = screen.getByText(/Tìm kiếm Học thuật/i);
    fireEvent.click(searchTabBtn);

    // Enter query and submit
    const queryInput = screen.getByPlaceholderText(/Nhập chủ đề, từ khóa/i);
    fireEvent.change(queryInput, { target: { value: 'PINNs fluid dynamics' } });

    const searchSubmitBtn = screen.getByRole('button', { name: /^Tìm kiếm$/i });
    fireEvent.click(searchSubmitBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/search', expect.objectContaining({
        query: 'PINNs fluid dynamics',
      }));
      expect(screen.getByText('Physics-informed Neural Networks (PINNs)')).toBeInTheDocument();
    });

    // Save source to library
    const saveBtn = screen.getByText(/Lưu vào Thư viện/i);
    fireEvent.click(saveBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/library/save', expect.anything());
  });

  it('handles PDF upload and Copy all BibTeX', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ papers: mockPapers });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});

    // Mock fetch for BibTeX export
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => '@article{sample, title={Sample}}',
    }) as any;

    // Mock navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    const { container } = renderWithProviders(<LibraryPanel />);

    await waitFor(() => {
      expect(screen.getByText('Attention Is All You Need')).toBeInTheDocument();
    });

    // Upload PDF
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();
    const pdfFile = new File(['%PDF-1.4 sample'], 'transformer.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/library/upload', expect.any(FormData));
    });

    // Click BibTeX button
    const bibBtn = screen.getByText('BibTeX');
    fireEvent.click(bibBtn);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('@article{sample, title={Sample}}');
    });
  });

  it('renders Google Scholar links and formats academic citations (BibTeX, APA, IEEE)', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ papers: mockPapers });
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });

    renderWithProviders(<LibraryPanel />);

    await waitFor(() => {
      expect(screen.getByText('Attention Is All You Need')).toBeInTheDocument();
    });

    // Click quick "Trích dẫn" button on the paper card
    const citeBtns = screen.getAllByRole('button', { name: /Trích dẫn|Cite/i });
    expect(citeBtns.length).toBeGreaterThan(0);
    fireEvent.click(citeBtns[0]);

    // Preview modal should open with Google Scholar section
    await waitFor(() => {
      expect(screen.getByText(/Trích nguồn tham khảo & Google Scholar/i)).toBeInTheDocument();
    });

    // Check Google Scholar search links
    const scholarLink = screen.getByRole('link', { name: /Google Scholar/i });
    expect(scholarLink).toHaveAttribute('href', expect.stringContaining('scholar.google.com/scholar?q='));

    const citesLink = screen.getByRole('link', { name: /Bài viết trích dẫn|Cited by/i });
    expect(citesLink).toHaveAttribute('href', expect.stringContaining('scholar.google.com/scholar?q='));

    // Switch between citation formats: APA, IEEE
    const apaBtn = screen.getByRole('button', { name: /^apa$/i });
    fireEvent.click(apaBtn);

    const ieeeBtn = screen.getByRole('button', { name: /^ieee$/i });
    fireEvent.click(ieeeBtn);

    // Click copy citation
    const copyBtn = screen.getByRole('button', { name: /Sao chép trích dẫn|Copy Citation/i });
    fireEvent.click(copyBtn);
    expect(navigator.clipboard.writeText).toHaveBeenCalled();
  });
});
