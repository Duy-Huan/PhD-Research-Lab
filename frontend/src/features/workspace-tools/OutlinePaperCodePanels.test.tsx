import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { OutlinePanel, PaperPanel, CodePanel, ProtocolsPanel } from './OutlinePaperCodePanels';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('Workspace Tool Panels', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setActiveTopicId('topic-1');
  });

  it('renders OutlinePanel with 5 levels and saves fields', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      keywords: 'wavelet, shrinkage',
      topic: 'Medical image super-resolution',
      direction: 'Adaptive thresholding',
      method: 'Dual-tree complex wavelet',
      proposal: 'Full thesis proposal draft',
    });
    const putSpy = vi.spyOn(api, 'put').mockResolvedValue({ ok: true });
    vi.spyOn(window, 'alert').mockImplementation(() => {});

    renderWithProviders(<OutlinePanel />);

    await waitFor(() => {
      expect(screen.getByText(/Đề cương nghiên cứu 5 cấp độ/i)).toBeInTheDocument();
      expect(screen.getByDisplayValue('wavelet, shrinkage')).toBeInTheDocument();
    });

    const saveBtn = screen.getByRole('button', { name: /Lưu đề cương/i });
    expect(saveBtn).toBeInTheDocument();
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(putSpy).toHaveBeenCalledWith(
        '/api/outline',
        expect.objectContaining({
          keywords: 'wavelet, shrinkage',
        })
      );
    });
  });

  it('renders PaperPanel with engine mode switcher (Local vs Online) and live preview', async () => {
    vi.spyOn(api, 'get').mockImplementation((url: string) => {
      if (url === '/api/paper') {
        return Promise.resolve({
          title: 'Deep Wavelet Neural Network',
          authors: 'Dr. Researcher',
          style: 'IEEE',
          venue: 'CVPR',
          sections: [
            { id: 'abstract', title: 'Abstract', text: 'In this paper...', state: 'drafted', versions: 2 },
            { id: 'introduction', title: 'Introduction', text: 'Recent advances...', state: 'reviewed', versions: 1 },
          ],
          pdf: true,
        });
      }
      if (url === '/api/paper/engines') {
        return Promise.resolve({
          available: ['tectonic', 'pdflatex'],
          paths: { tectonic: 'C:/tex/tectonic.exe' },
          online: true,
          default: 'tectonic',
          platform: 'win32',
        });
      }
      if (url === '/api/paper/log') {
        return Promise.resolve('Output written on main.pdf (2 pages).');
      }
      return Promise.resolve({});
    });

    const compileSpy = vi.spyOn(api, 'post').mockResolvedValue({
      ok: true,
      engine: 'tectonic',
      layout: 'template',
      seconds: 1.8,
      pages: 2,
      notes: [],
      errors: [],
    });

    renderWithProviders(<PaperPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Bản thảo Bài báo LaTeX/i)).toBeInTheDocument();
    });

    // Check mode pills: Local and Online
    const localBtn = screen.getByRole('button', { name: /Cục bộ/i });
    const onlineBtn = screen.getByRole('button', { name: /Trực tuyến/i });
    expect(localBtn).toBeInTheDocument();
    expect(onlineBtn).toBeInTheDocument();

    // Switch to Online mode
    fireEvent.click(onlineBtn);
    expect(screen.getByText(/Biên dịch đám mây qua dịch vụ LaTeX công khai/i)).toBeInTheDocument();

    // Switch to Local mode
    fireEvent.click(localBtn);
    expect(screen.getByText(/Trình biên dịch cục bộ:/i)).toBeInTheDocument();

    // Check tabs: PDF Preview, LaTeX Editor, Split View, Build Log
    const previewTab = screen.getByRole('button', { name: /Xem trước PDF/i });
    const editorTab = screen.getByRole('button', { name: /Soạn thảo LaTeX/i });
    const splitTab = screen.getByRole('button', { name: /Xem song song/i });
    const logTab = screen.getByRole('button', { name: /Nhật ký biên dịch/i });

    expect(previewTab).toBeInTheDocument();
    expect(editorTab).toBeInTheDocument();
    expect(splitTab).toBeInTheDocument();
    expect(logTab).toBeInTheDocument();

    // Trigger PDF Compilation
    const compileBtn = screen.getByRole('button', { name: /Biên dịch PDF/i });
    fireEvent.click(compileBtn);

    await waitFor(() => {
      expect(compileSpy).toHaveBeenCalledWith('/api/paper/compile', expect.any(Object));
    });

    // Verify PDF preview iframe is present
    await waitFor(() => {
      const iframe = screen.getByTitle(/Xem trước PDF bài báo/i);
      expect(iframe).toBeInTheDocument();
    });

    // Switch to Editor view
    fireEvent.click(editorTab);
    await waitFor(() => {
      expect(screen.getByDisplayValue(/In this paper.../i)).toBeInTheDocument();
    });

    // Switch to Split view
    fireEvent.click(splitTab);
    await waitFor(() => {
      expect(screen.getByText(/Xem trước PDF song song/i)).toBeInTheDocument();
    });

    // Switch to Log view
    fireEvent.click(logTab);
    await waitFor(() => {
      expect(screen.getByText(/Nhật ký biên dịch LaTeX chi tiết/i)).toBeInTheDocument();
    });
  });

  it('renders CodePanel, creates repo and launches VS Code', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      projects: [{ name: 'wavelet-bench', path: '/src/wavelet', description: 'Bench repo' }],
      active: 'wavelet-bench',
    });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ launched: true });

    renderWithProviders(<CodePanel />);

    await waitFor(() => {
      expect(screen.getByText(/Dự án Mã nguồn và VS Code/i)).toBeInTheDocument();
      expect(screen.getByText(/wavelet-bench/i)).toBeInTheDocument();
    });

    const vscodeBtn = screen.getByRole('button', { name: /Mở trong VS Code/i });
    fireEvent.click(vscodeBtn);
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/code/vscode');
    });
  });

  it('renders ProtocolsPanel and handles active topic states', async () => {
    vi.spyOn(api, 'get').mockImplementation((url: string) => {
      if (url.includes('/protocols')) {
        return Promise.resolve({
          protocols: [
            {
              id: 'proto-1',
              revision: 1,
              digest: 'abc1234567890abcdef',
              payload: { title: 'Wavelet Shrinkage Protocol' },
              approval: true,
            },
          ],
        });
      }
      if (url.includes('/experiments')) {
        return Promise.resolve({
          experiments: [{ id: 'exp-101', status: 'completed' }],
        });
      }
      return Promise.resolve({});
    });

    renderWithProviders(<ProtocolsPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Giao thức và Thí nghiệm Có Kiểm soát/i)).toBeInTheDocument();
      expect(screen.getByText(/Wavelet Shrinkage Protocol/i)).toBeInTheDocument();
      expect(screen.getByText(/exp-101/i)).toBeInTheDocument();
    });
  });
});
