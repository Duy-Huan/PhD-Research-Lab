import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils';
import { ContextualDrawer } from './ContextualDrawer';
import { useUIStore } from '../shared/state/uiStore';
import { api } from '../shared/api/client';

describe('ContextualDrawer', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue({});
    useUIStore.getState().closeDrawer();
  });

  it('renders nothing when drawerKind is null', () => {
    const { container } = renderWithProviders(<ContextualDrawer />);
    expect(container.firstChild).toBeNull();
  });

  it('renders all valid drawer kinds cleanly', () => {
    const kinds = [
      'topics',
      'library',
      'missions',
      'workstreams',
      'figures',
      'opencode',
      'intelligence',
      'protocols',
      'claims',
      'projects',
      'outline',
      'code',
      'paper',
      'agent-status',
      'dashboard',
      'settings',
      'review',
    ] as const;

    for (const kind of kinds) {
      useUIStore.setState({ drawerKind: kind as any });
      const { unmount } = renderWithProviders(<ContextualDrawer />);
      expect(screen.getAllByRole('complementary').length).toBeGreaterThanOrEqual(1);
      unmount();
    }

    // Default unknown case
    useUIStore.setState({ drawerKind: 'unknown_kind' as any });
    const { unmount } = renderWithProviders(<ContextualDrawer />);
    expect(screen.getAllByRole('complementary').length).toBeGreaterThanOrEqual(1);
    unmount();
  });

  it('closes drawer when close button is clicked', () => {
    useUIStore.setState({ drawerKind: 'library' });
    renderWithProviders(<ContextualDrawer />);

    const closeBtn = screen.getByTitle(/Đóng bảng|Close panel/i);
    expect(closeBtn).toBeInTheDocument();
    fireEvent.click(closeBtn);

    expect(useUIStore.getState().drawerKind).toBeNull();
  });

  it('collapses drawer when collapse button is clicked', () => {
    useUIStore.setState({ drawerKind: 'missions' });
    renderWithProviders(<ContextualDrawer />);

    const collapseBtn = screen.getByRole('button', { name: /Ẩn bảng công cụ bên phải|Collapse right menu/i });
    expect(collapseBtn).toBeInTheDocument();
    fireEvent.click(collapseBtn);

    expect(useUIStore.getState().drawerKind).toBeNull();
  });
});
