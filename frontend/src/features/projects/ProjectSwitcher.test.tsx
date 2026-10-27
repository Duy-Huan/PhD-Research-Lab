import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { ProjectSwitcher } from './ProjectSwitcher';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('ProjectSwitcher', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setProject({
      name: 'Alpha Project',
      data_dir: '/data/alpha',
      created: '2026-10-24T00:00:00Z',
    });
  });

  it('renders projects and switches project on click', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      projects: [
        { name: 'Alpha Project', data_dir: '/data/alpha', created: '2026-10-24T00:00:00Z', is_default: false },
        { name: 'Beta Project', data_dir: '/data/beta', created: '2026-10-24T01:00:00Z', is_default: false },
      ],
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});

    renderWithProviders(<ProjectSwitcher />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument();
      expect(screen.getByText('Beta Project')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Beta Project'));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/projects/activate', {
        data_dir: '/data/beta',
      });
      expect(useUIStore.getState().project?.data_dir).toBe('/data/beta');
    });
  });

  it('creates a new project', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ projects: [] });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      name: 'Gamma Project',
      data_dir: '/data/gamma',
    });

    renderWithProviders(<ProjectSwitcher />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Dự án mới|New Project/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Dự án mới|New Project/i }));
    const input = screen.getByPlaceholderText(/Vision-Language Reasoning/i);
    fireEvent.change(input, { target: { value: 'Gamma Project' } });

    fireEvent.click(screen.getByRole('button', { name: /Tạo dự án|Create Project/i }));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/projects', {
        name: 'Gamma Project',
      });
    });
  });

  it('creates a new project with custom data_dir and references_dir', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ projects: [] });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      name: 'Custom Project',
      data_dir: 'D:\\research\\custom-project',
      references_dir: 'D:\\research\\papers',
    });

    renderWithProviders(<ProjectSwitcher />);

    fireEvent.click(screen.getByRole('button', { name: /Dự án mới|New Project/i }));
    const nameInput = screen.getByPlaceholderText(/Vision-Language Reasoning/i);
    const dataDirInput = screen.getByPlaceholderText(/D:\\research\\my-project/i);
    const refsDirInput = screen.getByPlaceholderText(/D:\\research\\papers/i);

    fireEvent.change(nameInput, { target: { value: 'Custom Project' } });
    fireEvent.change(dataDirInput, { target: { value: 'D:\\research\\custom-project' } });
    fireEvent.change(refsDirInput, { target: { value: 'D:\\research\\papers' } });

    fireEvent.click(screen.getByRole('button', { name: /Tạo dự án|Create Project/i }));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/projects', {
        name: 'Custom Project',
        data_dir: 'D:\\research\\custom-project',
        references_dir: 'D:\\research\\papers',
      });
    });
  });

  it('opens existing project from machine using Open Project form', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ projects: [] });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      name: 'existing-lab',
      data_dir: 'D:\\research\\existing-lab',
    });

    renderWithProviders(<ProjectSwitcher />);

    const openBtn = screen.getByRole('button', { name: /Mở dự án|Open Project/i });
    fireEvent.click(openBtn);

    const folderInput = screen.getByPlaceholderText(/my-existing-project/i);
    fireEvent.change(folderInput, { target: { value: 'D:\\research\\existing-lab' } });

    const submitOpenBtn = screen.getByRole('button', { name: /Mở & Kích hoạt|Open & Activate/i });
    fireEvent.click(submitOpenBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/projects/open', {
        data_dir: 'D:\\research\\existing-lab',
      });
      expect(useUIStore.getState().project?.data_dir).toBe('D:\\research\\existing-lab');
    });
  });

  it('renames a project and updates UI store when active', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      projects: [
        { name: 'Quantum Project', data_dir: 'D:\\lab\\quantum', is_default: false },
      ],
    });

    useUIStore.getState().setProject({
      name: 'Quantum Project',
      data_dir: 'D:\\lab\\quantum',
    });

    const putSpy = vi.spyOn(api, 'put').mockResolvedValue({
      name: 'Quantum Optics Lab',
      data_dir: 'D:\\lab\\quantum',
    });

    renderWithProviders(<ProjectSwitcher />);

    await waitFor(() => {
      expect(screen.getByText('Quantum Project')).toBeInTheDocument();
    });

    const optionsBtn = screen.getByTitle(/Tùy chọn dự án|Project options/i);
    fireEvent.click(optionsBtn);

    const renameBtn = screen.getByTitle(/Đổi tên dự án|Rename project/i);
    fireEvent.click(renameBtn);

    const renameInput = screen.getByPlaceholderText(/Nhập tên mới/i);
    fireEvent.change(renameInput, { target: { value: 'Quantum Optics Lab' } });

    const saveRenameBtn = screen.getByRole('button', { name: /Lưu tên mới|Save Name/i });
    fireEvent.click(saveRenameBtn);

    await waitFor(() => {
      expect(putSpy).toHaveBeenCalledWith('/api/projects/rename', {
        data_dir: 'D:\\lab\\quantum',
        name: 'Quantum Optics Lab',
      });
      expect(useUIStore.getState().project?.name).toBe('Quantum Optics Lab');
    });
  });

  it('deletes a project with confirmation and option to delete disk files', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      projects: [
        { name: 'Default project', data_dir: 'D:\\lab\\data', is_default: true },
        { name: 'Obsolete Project', data_dir: 'D:\\lab\\obsolete', is_default: false },
      ],
    });

    useUIStore.getState().setProject({
      name: 'Obsolete Project',
      data_dir: 'D:\\lab\\obsolete',
    });

    const deleteSpy = vi.spyOn(api, 'delete').mockResolvedValue({ ok: true, projects: [] });

    renderWithProviders(<ProjectSwitcher />);

    await waitFor(() => {
      expect(screen.getByText('Obsolete Project')).toBeInTheDocument();
    });

    const optionsBtns = screen.getAllByTitle(/Tùy chọn dự án|Project options/i);
    // Default project delete button is disabled inside menu
    fireEvent.click(optionsBtns[0]);
    const defaultDeleteBtn = screen.getByTitle(/Dự án Mặc định không thể xóa/i);
    expect(defaultDeleteBtn).toBeDisabled();

    // Click delete on obsolete project inside menu
    fireEvent.click(optionsBtns[1]);
    const deleteBtn = screen.getByTitle(/Xóa hoặc gỡ dự án/i);
    fireEvent.click(deleteBtn);

    expect(screen.getByText(/Xác nhận Xóa Dự án/i)).toBeInTheDocument();

    // Check delete files checkbox
    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    const confirmDeleteBtn = screen.getByRole('button', { name: /Xóa hoàn toàn cả tệp/i });
    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith(
        '/api/projects?data_dir=D%3A%5Clab%5Cobsolete&delete_files=true'
      );
      // Active project falls back to default project
      expect(useUIStore.getState().project?.is_default).toBe(true);
    });
  });

  it('reveals project folder in file explorer', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      projects: [
        { name: 'Fluid Lab', data_dir: 'D:\\lab\\fluids', is_default: false },
      ],
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ path: 'D:\\lab\\fluids' });

    renderWithProviders(<ProjectSwitcher />);

    await waitFor(() => {
      expect(screen.getByText('Fluid Lab')).toBeInTheDocument();
    });

    const optionsBtn = screen.getByTitle(/Tùy chọn dự án|Project options/i);
    fireEvent.click(optionsBtn);

    const revealBtn = screen.getByTitle(/Mở thư mục trong máy tính/i);
    fireEvent.click(revealBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/projects/reveal', {
        data_dir: 'D:\\lab\\fluids',
      });
    });
  });
});
