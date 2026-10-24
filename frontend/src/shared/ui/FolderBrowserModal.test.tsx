import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { FolderBrowserModal } from './FolderBrowserModal';
import { api } from '../api/client';

describe('FolderBrowserModal', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders modal when open, displays drives, shortcuts and directories', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      current: 'D:\\lab',
      parent: 'D:\\',
      drives: ['C:\\', 'D:\\'],
      shortcuts: [
        { name: 'Workspace Lab', path: 'D:\\lab' },
        { name: 'Documents', path: 'C:\\Users\\win\\Documents' },
      ],
      directories: [
        { name: 'datasets', path: 'D:\\lab\\datasets', hidden: false },
        { name: 'papers', path: 'D:\\lab\\papers', hidden: false },
      ],
    });

    const onSelect = vi.fn();
    const onClose = vi.fn();

    renderWithProviders(
      <FolderBrowserModal
        isOpen={true}
        onClose={onClose}
        onSelect={onSelect}
        initialPath="D:\\lab"
        title="Duyệt thư mục kiểm thử"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Duyệt thư mục kiểm thử')).toBeInTheDocument();
      expect(screen.getByText('datasets')).toBeInTheDocument();
      expect(screen.getByText('papers')).toBeInTheDocument();
    });

    // Drives
    expect(screen.getByText('C:\\')).toBeInTheDocument();
    expect(screen.getByText('D:\\')).toBeInTheDocument();

    // Select papers and confirm
    fireEvent.click(screen.getByText('papers'));
    fireEvent.click(screen.getByRole('button', { name: /Chọn thư mục này/i }));

    expect(onSelect).toHaveBeenCalledWith('D:\\lab\\papers');
    expect(onClose).toHaveBeenCalled();
  });

  it('supports creating a new folder and opening native OS dialog', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      current: 'D:\\lab',
      parent: 'D:\\',
      drives: ['D:\\'],
      shortcuts: [],
      directories: [],
    });

    const postSpy = vi.spyOn(api, 'post').mockImplementation((url: string) => {
      if (url === '/api/system/fs-mkdir') {
        return Promise.resolve({ ok: true, path: 'D:\\lab\\new_experiment' });
      }
      if (url === '/api/system/pick-folder') {
        return Promise.resolve({ path: 'D:\\lab\\picked_via_os', canceled: false });
      }
      return Promise.resolve({});
    });

    const onSelect = vi.fn();
    const onClose = vi.fn();

    renderWithProviders(
      <FolderBrowserModal
        isOpen={true}
        onClose={onClose}
        onSelect={onSelect}
        initialPath="D:\\lab"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Tạo thư mục/i)).toBeInTheDocument();
    });

    // Toggle create folder
    fireEvent.click(screen.getByText(/Tạo thư mục/i));
    const folderInput = screen.getByPlaceholderText(/vd: dataset_2026/i);
    fireEvent.change(folderInput, { target: { value: 'new_experiment' } });
    fireEvent.click(screen.getByRole('button', { name: /Xác nhận tạo/i }));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/system/fs-mkdir', {
        path: 'D:\\lab\\new_experiment',
      });
    });

    // Test OS dialog button
    const osBtn = screen.getByRole('button', { name: /Mở hộp thoại (hệ thống )?Windows/i });
    fireEvent.click(osBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/system/pick-folder', {
        initial_dir: 'D:\\lab\\new_experiment',
        title: 'Chọn thư mục từ máy tính',
      });
      expect(onSelect).toHaveBeenCalledWith('D:\\lab\\picked_via_os');
      expect(onClose).toHaveBeenCalled();
    });
  });
});
