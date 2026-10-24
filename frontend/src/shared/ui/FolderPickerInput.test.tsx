import React, { useState } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { FolderPickerInput } from './FolderPickerInput';
import { api } from '../api/client';

describe('FolderPickerInput', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders input with value and supports manual typing', () => {
    const handleChange = vi.fn();
    renderWithProviders(
      <FolderPickerInput
        value={'D:\\my-folder'}
        onChange={handleChange}
        placeholder="Select path"
      />
    );

    const input = screen.getByPlaceholderText('Select path') as HTMLInputElement;
    expect(input.value).toBe('D:\\my-folder');

    fireEvent.change(input, { target: { value: 'D:\\new-folder' } });
    expect(handleChange).toHaveBeenCalledWith('D:\\new-folder');
  });

  it('invokes native OS folder picker via API when clicking Browse OS button', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      path: 'D:\\selected\\from\\os',
      canceled: false,
    });
    const handleChange = vi.fn();

    renderWithProviders(
      <FolderPickerInput
        value=""
        onChange={handleChange}
        placeholder="e.g. D:\\research"
        dialogTitle="Chọn thư mục"
      />
    );

    const browseBtn = screen.getByRole('button', { name: /Duyệt máy|Browse/i });
    fireEvent.click(browseBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/system/pick-folder', {
        initial_dir: '',
        title: 'Chọn thư mục',
      });
      expect(handleChange).toHaveBeenCalledWith('D:\\selected\\from\\os');
    });
  });

  it('opens interactive in-app FolderBrowserModal when clicking tree icon button', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      current: 'D:\\test-root',
      parent: 'D:\\',
      drives: ['C:\\', 'D:\\'],
      shortcuts: [{ name: 'Workspace Lab', path: 'D:\\test-root' }],
      directories: [{ name: 'subfolder_a', path: 'D:\\test-root\\subfolder_a', hidden: false }],
    });

    const handleChange = vi.fn();

    renderWithProviders(
      <FolderPickerInput
        value="D:\\test-root"
        onChange={handleChange}
        placeholder="Enter path"
      />
    );

    const treeBtn = screen.getByTitle(/Xem và duyệt cây thư mục/i);
    fireEvent.click(treeBtn);

    await waitFor(() => {
      expect(screen.getByText(/subfolder_a/i)).toBeInTheDocument();
    });

    // Click subfolder and select it
    fireEvent.click(screen.getByText(/subfolder_a/i));
    const confirmBtn = screen.getByRole('button', { name: /Chọn thư mục này/i });
    fireEvent.click(confirmBtn);

    expect(handleChange).toHaveBeenCalledWith('D:\\test-root\\subfolder_a');
  });
});
