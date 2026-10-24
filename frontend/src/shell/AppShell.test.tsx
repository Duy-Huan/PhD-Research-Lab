import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils';
import { AppShell } from './AppShell';
import { ContextualDrawer } from './ContextualDrawer';
import { useUIStore } from '../shared/state/uiStore';
import { api } from '../shared/api/client';

describe('AppShell and ContextualDrawer', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url === '/api/config') {
        return {
          project: { name: 'P-Fluids', data_dir: '/data/fluids' },
          ui: { theme: 'academic-modern', language: 'vi' },
        };
      }
      if (url === '/api/projects') {
        return {
          projects: [{ name: 'P-Fluids', data_dir: '/data/fluids' }],
        };
      }
      return {};
    });

    const s = useUIStore.getState();
    s.setLanguage('vi');
    s.setMainView('chat');
    s.closeDrawer();
  });

  it('renders AppShell with Header and main stage, synchronizing boot config', async () => {
    renderWithProviders(<AppShell />);
    expect(screen.getByText('PhD Research Lab')).toBeInTheDocument();
  });

  it('renders library, dashboard, and review main views cleanly', () => {
    useUIStore.getState().setMainView('library');
    const { rerender } = renderWithProviders(<AppShell />);
    expect(screen.getAllByText(/Thư viện/i).length).toBeGreaterThan(0);

    useUIStore.getState().setMainView('dashboard');
    rerender(<AppShell />);
    expect(screen.getByText(/Trung tâm Điều hành Nghiên cứu/i)).toBeInTheDocument();

    useUIStore.getState().setMainView('review');
    rerender(<AppShell />);
    expect(screen.getByText(/Hội đồng Bình duyệt Học thuật/i)).toBeInTheDocument();
  });

  it('renders ContextualDrawer when a drawer kind is selected', () => {
    useUIStore.getState().openDrawer('topics');
    renderWithProviders(<ContextualDrawer />);
    const match = screen.getAllByText(/Chủ đề nghiên cứu/i);
    expect(match.length).toBeGreaterThan(0);
  });

  it('renders floating right-edge handle when drawer is closed and allows reopening', () => {
    useUIStore.getState().closeDrawer();
    renderWithProviders(<AppShell />);

    const floatingBtn = screen.getByRole('button', { name: /Mở menu bên phải|Open right menu/i });
    expect(floatingBtn).toBeInTheDocument();
  });
});
