import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils';
import { Header } from './Header';
import { useUIStore } from '../shared/state/uiStore';

describe('Header', () => {
  beforeEach(() => {
    const s = useUIStore.getState();
    s.setLanguage('vi');
    s.setMainView('chat');
    s.setUiScale(1.0);
    s.closeDrawer();
  });

  it('renders mode switcher pills and allows switching to 3D Lab, Review, Dashboard, and Chat', () => {
    renderWithProviders(<Header isLive={true} />);

    // Click 3D Lab pill
    const labBtn = screen.getByRole('button', { name: /^(Lab 3D|3D Lab)$/ }); // icon-only, named by aria-label (v6.6.2)
    fireEvent.click(labBtn);
    expect(useUIStore.getState().mainView).toBe('office3d');

    // Click Review pill
    const reviewBtn = screen.getByTitle(/Hội đồng Bình duyệt/i);
    fireEvent.click(reviewBtn);
    expect(useUIStore.getState().mainView).toBe('review');

    // Click Dashboard pill
    const dashBtn = screen.getByTitle(/Bảng điều khiển Hệ thống/i);
    fireEvent.click(dashBtn);
    expect(useUIStore.getState().mainView).toBe('dashboard');

    // Click Chat pill
    const chatBtn = screen.getByRole('button', { name: /^(Trò chuyện|Chat)$/ });
    fireEvent.click(chatBtn);
    expect(useUIStore.getState().mainView).toBe('chat');
  });

  it('toggles language between VI and EN', () => {
    renderWithProviders(<Header isLive={true} />);
    const langBtn = screen.getByText('VI');
    fireEvent.click(langBtn);
    expect(useUIStore.getState().language).toBe('en');
  });

  it('cycles UI scale when clicking scale button', () => {
    renderWithProviders(<Header isLive={true} />);
    const scaleBtn = screen.getByText('100%');
    fireEvent.click(scaleBtn);
    expect(useUIStore.getState().uiScale).toBe(1.08);
  });

  it('opens inspector drawers for library, outline, figures, native code, and intelligence', () => {
    renderWithProviders(<Header isLive={true} />);

    const outlineBtn = screen.getByTitle(/Đề cương/i);
    fireEvent.click(outlineBtn);
    expect(useUIStore.getState().drawerKind).toBe('outline');

    const libraryBtn = screen.getByTitle(/Thư viện PDF/i);
    fireEvent.click(libraryBtn);
    expect(useUIStore.getState().drawerKind).toBe('library');

    const figuresBtn = screen.getByTitle(/Xưởng Đồ họa|Figure Studio/i);
    fireEvent.click(figuresBtn);
    expect(useUIStore.getState().drawerKind).toBe('figures');

    const codeBtn = screen.getByTitle(/Mã nguồn & thí nghiệm native|Native code & experiments/i);
    fireEvent.click(codeBtn);
    expect(useUIStore.getState().drawerKind).toBe('code');

    const intelBtn = screen.getByTitle(/Trung tâm Phân tích|Unified Research Intelligence/i);
    fireEvent.click(intelBtn);
    expect(useUIStore.getState().drawerKind).toBe('intelligence');

    const guideBtn = screen.getByTitle(/Hướng dẫn Người (mới|dùng)|User Guide/i);
    fireEvent.click(guideBtn);
    expect(useUIStore.getState().drawerKind).toBe('guide');
  });

  it('keeps native code navigation unbranded by retired software in both languages', () => {
    renderWithProviders(<Header isLive={true} />);
    expect(screen.queryByTitle(/OpenCode|ClearML|Feynman|OpenScience/i)).toBeNull();
    expect(screen.getByTitle('Mã nguồn & thí nghiệm native')).toBeTruthy();
    fireEvent.click(screen.getByText('VI'));
    fireEvent.click(screen.getByTitle('Native code & experiments'));
    expect(useUIStore.getState().drawerKind).toBe('code');
    expect(screen.queryByTitle(/OpenCode|ClearML|Feynman|OpenScience/i)).toBeNull();
  });

  it('toggles right inspector drawer using dedicated corner panel-btn', () => {
    renderWithProviders(<Header isLive={true} />);
    const panelBtn = screen.getByRole('button', { name: /Menu phải|Inspector Drawer|Bảng kết quả/i });

    // Initial state is closed
    expect(useUIStore.getState().drawerKind).toBeNull();

    // Click to open
    fireEvent.click(panelBtn);
    expect(useUIStore.getState().drawerKind).not.toBeNull();

    // Click to close/hide
    fireEvent.click(panelBtn);
    expect(useUIStore.getState().drawerKind).toBeNull();
  });
});
