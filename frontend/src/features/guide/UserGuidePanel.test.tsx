import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { UserGuidePanel } from './UserGuidePanel';
import { useUIStore } from '../../shared/state/uiStore';

describe('UserGuidePanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders hero banner and quickstart 5 steps by default', () => {
    renderWithProviders(<UserGuidePanel />);

    expect(screen.getByText(/Sổ tay & Hướng dẫn Sử dụng Chi tiết cho Người Mới/i)).toBeInTheDocument();
    expect(screen.getByText(/Quy trình 5 bước Nghiên cứu Khởi đầu cho Người Mới/i)).toBeInTheDocument();
    expect(screen.getByText(/Khởi tạo Dự án & Thiết lập Thư mục Lưu trữ/i)).toBeInTheDocument();
  });

  it('switches between all guide tabs and renders specialized content', async () => {
    renderWithProviders(<UserGuidePanel />);

    // 1. Tab Workflows
    const workflowsTab = screen.getByRole('button', { name: /Quy trình|Research Workflows/i });
    fireEvent.click(workflowsTab);
    expect(screen.getByText(/Danh mục Toàn bộ Quy trình Nghiên cứu Khoa học|Comprehensive Scientific Research Workflows Catalog/i)).toBeInTheDocument();
    expect(screen.getByText(/10 Quy trình Chuyên sâu|10 Specialized Workflows/i)).toBeInTheDocument();
    expect(screen.getByText(/Quy trình Khảo cứu Tài liệu & Đề xuất Giả thuyết Khoa học|Literature Exploration/i)).toBeInTheDocument();
    expect(screen.getByText(/Quy trình Đánh giá Harness Kéo thả Tùy chỉnh & Công cụ Mã nguồn Mở|Visual Custom Harness Studio/i)).toBeInTheDocument();
    expect(screen.getByText(/Quy trình Thuần Bản địa PhD Lab Độc lập Hoàn toàn|Pure PhD Lab Native/i)).toBeInTheDocument();

    // 2. Tab Agents & 3D Lab
    const agentsTab = screen.getByRole('button', { name: /Hội đồng AI.*(3D Lab|Phòng Lab)|AI Agents & 3D Lab/i });
    fireEvent.click(agentsTab);
    expect(screen.getAllByText(/Giáo sư Hướng dẫn|Supervisor/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Chuyên gia Phản biện|Critic/i)).toBeInTheDocument();
    expect(screen.getByText(/Mẹo Tương tác trong Phòng Lab 3D|3D Lab Interaction Tips/i)).toBeInTheDocument();

    // 3. Tab Commands (/)
    const commandsTab = screen.getByRole('button', { name: /Lệnh tắt|Slash Commands/i });
    fireEvent.click(commandsTab);
    expect(screen.getByText(/\/lit/i)).toBeInTheDocument();
    expect(screen.getByText(/\/hypothesis/i)).toBeInTheDocument();
    expect(screen.getByText(/\/review/i)).toBeInTheDocument();

    // 4. Tab Library
    const libraryTab = screen.getByRole('button', { name: /Thư viện PDF & Xếp hạng|PDF Library & Ranking/i });
    fireEvent.click(libraryTab);
    expect(screen.getByText(/Quản lý Siêu dữ liệu & Trích dẫn Google Scholar|Smart Citation/i)).toBeInTheDocument();
    expect(screen.getByText(/Tier 1 Venues|Top-Tier/i)).toBeInTheDocument();

    // 5. Tab Shortcuts & FAQ
    const shortcutsTab = screen.getByRole('button', { name: /Phím tắt & Câu hỏi thường gặp|Shortcuts & FAQ/i });
    fireEvent.click(shortcutsTab);
    expect(screen.getByText(/Bảng Phím tắt Nhanh|Keyboard Shortcuts/i)).toBeInTheDocument();
    expect(screen.getByText(/Ctrl \+ Enter/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Local-First|Bảo mật Cục bộ/i).length).toBeGreaterThanOrEqual(1);
  });

  it('filters workflows catalog using search query input', () => {
    renderWithProviders(<UserGuidePanel />);

    const workflowsTab = screen.getByRole('button', { name: /Quy trình|Research Workflows/i });
    fireEvent.click(workflowsTab);

    const searchInput = screen.getByPlaceholderText(/Tìm nhanh trong sổ tay|Search guide topics/i);
    fireEvent.change(searchInput, { target: { value: 'latex' } });

    expect(screen.getByText(/Quy trình Soạn thảo Bản thảo & Biên dịch LaTeX Hai Chế độ|Manuscript Drafting/i)).toBeInTheDocument();
    expect(screen.queryByText(/Quy trình Khảo cứu Tài liệu & Đề xuất Giả thuyết Khoa học/i)).not.toBeInTheDocument();
  });

  it('quick action buttons trigger drawers and workspaces', () => {
    const s = useUIStore.getState();
    const openDrawerSpy = vi.spyOn(s, 'openDrawer');
    const openOfficeSpy = vi.spyOn(s, 'open3DOffice');

    renderWithProviders(<UserGuidePanel />);

    const workspaceBtns = screen.getAllByRole('button', { name: /Không gian Dự án|Dự án \(Workspaces\)|Workspaces/i });
    fireEvent.click(workspaceBtns[0]);
    expect(openDrawerSpy).toHaveBeenCalledWith('projects');

    const lab3dBtn = screen.getByRole('button', { name: /Khám phá Lab 3D|Explore 3D Lab/i });
    fireEvent.click(lab3dBtn);
    expect(openOfficeSpy).toHaveBeenCalled();

    // From workflows tab
    const workflowsTab = screen.getByRole('button', { name: /Quy trình|Research Workflows/i });
    fireEvent.click(workflowsTab);

    const harnessBtn = screen.getByRole('button', { name: /Mở Harness Studio Kéo thả|Open Harness Studio/i });
    fireEvent.click(harnessBtn);
    expect(openDrawerSpy).toHaveBeenCalledWith('harness');
  });

  it('synchronizes language between Vietnamese and English', () => {
    useUIStore.getState().setLanguage('vi');
    const { unmount } = renderWithProviders(<UserGuidePanel />);

    expect(screen.getByText(/Sổ tay & Hướng dẫn Sử dụng Chi tiết cho Người Mới/i)).toBeInTheDocument();
    expect(screen.getByText(/Quy trình 5 bước Nghiên cứu Khởi đầu cho Người Mới/i)).toBeInTheDocument();

    // Toggle language inside guide
    const langBtn = screen.getByTitle(/Chuyển đổi ngôn ngữ hiển thị của sổ tay/i);
    fireEvent.click(langBtn);

    expect(useUIStore.getState().language).toBe('en');

    unmount();

    // In English mode
    renderWithProviders(<UserGuidePanel />);
    expect(screen.getByText(/User Guide & Beginner Onboarding Manual/i)).toBeInTheDocument();
    expect(screen.getByText(/5-Step Research Quickstart Workflow/i)).toBeInTheDocument();
    expect(screen.getByText(/Create Research Project & Storage Directories/i)).toBeInTheDocument();
  });
});
