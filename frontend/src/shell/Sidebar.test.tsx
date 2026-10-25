import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/test-utils';
import { Sidebar } from './Sidebar';
import { useUIStore } from '../shared/state/uiStore';
import { api } from '../shared/api/client';

describe('Sidebar', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    const s = useUIStore.getState();
    s.setLanguage('vi');
    s.setProject({ name: 'Default', data_dir: '/path/to/data' });
    s.setActiveSessionId('s-prev');
    s.setActiveChatProjectId(null);
    useUIStore.setState({ sidebarOpen: true });
  });

  it('renders brand and navigation options and handles new chat creation', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/chat/sessions')) {
        return { sessions: [] };
      }
      if (url.includes('/api/chat/projects')) {
        return { projects: [] };
      }
      return {};
    });

    renderWithProviders(<Sidebar />);
    expect(screen.getByText('PhD Research Lab')).toBeInTheDocument();

    const newChatBtn = screen.getByText(/Cuộc trò chuyện mới/i);
    expect(newChatBtn).toBeInTheDocument();
    fireEvent.click(newChatBtn);

    expect(useUIStore.getState().activeSessionId).toBe(null);
    expect(useUIStore.getState().mainView).toBe('chat');
  });

  it('renders pinned sessions and chat projects (folders)', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/chat/sessions')) {
        return {
          sessions: [
            { id: 's-1', title: 'Pinned Research Chat', pinned: true },
            { id: 's-2', title: 'Regular Chat', pinned: false },
          ],
        };
      }
      if (url.includes('/api/chat/projects')) {
        return {
          projects: [
            { id: 'f-1', name: 'Project Alpha Folder', instructions: 'Shared context prompt' },
          ],
        };
      }
      return {};
    });

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getAllByText('Pinned Research Chat').length).toBe(1);
      expect(screen.getByText('Project Alpha Folder')).toBeInTheDocument();
    });
  });

  it('allows clicking folder to filter chats', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/chat/sessions')) {
        return {
          sessions: [
            { id: 's-1', title: 'Chat Inside Folder', chat_project: 'f-1' },
          ],
        };
      }
      if (url.includes('/api/chat/projects')) {
        return {
          projects: [
            { id: 'f-1', name: 'Project Folder 1', instructions: '' },
          ],
        };
      }
      return {};
    });

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText('Project Folder 1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Project Folder 1'));
    expect(useUIStore.getState().activeChatProjectId).toBe('f-1');
  });

  it('opens more options dropdown menu on click and supports pin/rename/delete', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/chat/sessions')) {
        return {
          sessions: [
            { id: 's-10', title: 'Deep Reasoning Session', pinned: false },
          ],
        };
      }
      if (url.includes('/api/chat/projects')) {
        return { projects: [] };
      }
      return {};
    });

    const putSpy = vi.spyOn(api, 'put').mockResolvedValue({});
    const deleteSpy = vi.spyOn(api, 'delete').mockResolvedValue({});
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderWithProviders(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByText('Deep Reasoning Session')).toBeInTheDocument();
    });

    // Click the ... more button
    const moreBtn = screen.getByTitle('Tùy chọn đoạn chat');
    expect(moreBtn).toBeInTheDocument();
    fireEvent.click(moreBtn);

    // Dropdown items should now be visible
    expect(screen.getByText(/Ghim đoạn chat/i)).toBeInTheDocument();
    expect(screen.getByText(/Chuyển vào nhóm chat/i)).toBeInTheDocument();
    expect(screen.getByText(/Đổi tên/i)).toBeInTheDocument();
    expect(screen.getByText(/Xóa cuộc trò chuyện/i)).toBeInTheDocument();

    // Click Pin in menu
    fireEvent.click(screen.getByText(/Ghim đoạn chat/i));

    await waitFor(() => {
      expect(putSpy).toHaveBeenCalledWith(
        '/api/chat/sessions/s-10',
        expect.objectContaining({ pinned: true })
      );
    });

    // Click Delete in menu
    fireEvent.click(moreBtn);
    const deleteOption = screen.getByText(/Xóa cuộc trò chuyện/i);
    fireEvent.click(deleteOption);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith(expect.stringContaining('/api/chat/sessions/s-10'));
    });
  });

  it('creates new chat project folder and supports collapsing sidebar', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ sessions: [], projects: [] });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      project: { id: 'f-new-1', name: 'Turbulence Modeling' },
    });

    renderWithProviders(<Sidebar />);

    // Click "Tạo thư mục nhóm chat mới"
    const newFolderBtn = screen.getByTitle(/Tạo thư mục nhóm chat mới/i);
    fireEvent.click(newFolderBtn);

    const folderInput = screen.getByPlaceholderText(/Tên thư mục nhóm chat/i);
    fireEvent.change(folderInput, { target: { value: 'Turbulence Modeling' } });

    const createBtn = screen.getByText(/Tạo Nhóm/i);
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/chat/projects',
        expect.objectContaining({ name: 'Turbulence Modeling' })
      );
    });

    // Test toggle sidebar
    const collapseBtn = screen.getByTitle(/Thu gọn thanh bên/i);
    fireEvent.click(collapseBtn);
    expect(useUIStore.getState().sidebarOpen).toBe(false);
  });

  it('renders library and outline items inside Research Studios menu and opens library drawer', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ sessions: [], projects: [] });

    renderWithProviders(<Sidebar />);

    // Click the Research Studios (Công cụ Nghiên cứu) menu toggle
    const studiosBtn = screen.getByRole('button', { name: /Công cụ Nghiên cứu|Research Studios/i });
    expect(studiosBtn).toBeInTheDocument();
    fireEvent.click(studiosBtn);

    // Verify Library and Outline are present inside the popup
    const libraryStudioItems = screen.getAllByText(/Thư viện Bài báo|Paper Library/i);
    expect(libraryStudioItems.length).toBeGreaterThanOrEqual(1);

    const outlineStudioItem = screen.getByText(/Đề cương (Nghiên cứu )?5 [Cc]ấp|5-Level Research Outline/i);
    expect(outlineStudioItem).toBeInTheDocument();

    const guideStudioItem = screen.getByText(/Sổ tay Người (mới|dùng)|Beginner Guide|User Guide/i);
    expect(guideStudioItem).toBeInTheDocument();

    // Clicking Guide opens guide drawer
    fireEvent.click(guideStudioItem);
    expect(useUIStore.getState().drawerKind).toBe('guide');
  });

  it('renders collapsed icon rail with all ChatGPT-style quick icons when collapsed', () => {
    useUIStore.setState({ sidebarOpen: false });
    renderWithProviders(<Sidebar collapsed={true} />);

    expect(screen.getByTitle('Mở rộng thanh bên')).toBeInTheDocument();
    expect(screen.getByTitle('Cuộc trò chuyện mới')).toBeInTheDocument();
    expect(screen.getByTitle('Tìm kiếm đoạn chat')).toBeInTheDocument();
    expect(screen.getByTitle('Đoạn chat đã ghim')).toBeInTheDocument();
    expect(screen.getByTitle('Thư viện bài báo')).toBeInTheDocument();
    expect(screen.getByTitle('Lab 3D Trường Đại học')).toBeInTheDocument();
    expect(screen.getByTitle('Nhiệm vụ tự trị')).toBeInTheDocument();
    expect(screen.getByTitle('Cài đặt & Hồ sơ')).toBeInTheDocument();

    // Clicking expand expands sidebar
    fireEvent.click(screen.getByTitle('Mở rộng thanh bên'));
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });

  it('opens system settings modal from bottom-left settings button in expanded and collapsed sidebar', () => {
    // 1. Expanded sidebar bottom-left settings button
    useUIStore.setState({ sidebarOpen: true, mainView: 'chat' });
    const { unmount } = renderWithProviders(<Sidebar collapsed={false} />);
    const sideSettingsBtn = screen.getByTitle(/Cài đặt Hệ thống/i);
    expect(sideSettingsBtn).toBeInTheDocument();
    fireEvent.click(sideSettingsBtn);
    expect(useUIStore.getState().mainView).toBe('settings');

    unmount();

    // 2. Collapsed sidebar bottom-left settings avatar button
    useUIStore.setState({ sidebarOpen: false, mainView: 'chat' });
    renderWithProviders(<Sidebar collapsed={true} />);
    const railSettingsBtn = screen.getByTitle(/Cài đặt & Hồ sơ/i);
    expect(railSettingsBtn).toBeInTheDocument();
    fireEvent.click(railSettingsBtn);
    expect(useUIStore.getState().mainView).toBe('settings');
  });

  it('renders quick apps & sync strip and triggers launch and sync', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ sessions: [], projects: [] });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ ok: true, total_changed: 1, total_observed: 5 });

    renderWithProviders(<Sidebar collapsed={false} />);

    const opencodeLaunchBtn = screen.getByRole('button', { name: /^OpenCode$/i });
    expect(opencodeLaunchBtn).toBeInTheDocument();
    fireEvent.click(opencodeLaunchBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/providers/opencode/launch', {});

    const opencodeSyncBtn = screen.getByTitle(/Đồng bộ dữ liệu từ OpenCode|Sync data from OpenCode/i);
    expect(opencodeSyncBtn).toBeInTheDocument();
    fireEvent.click(opencodeSyncBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/providers/opencode/sync', {});
  });

  it('renders all CLI providers in the Provider & CLI list and supports 1-click manual launch for any provider', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/providers')) {
        return {
          providers: [
            { id: 'claude_code', label: 'Claude Code', state: 'READY', ready: true },
            { id: 'codex', label: 'OpenAI Codex', state: 'READY', ready: true },
            { id: 'paperorchestra', label: 'PaperOrchestra', state: 'READY', ready: true },
          ],
        };
      }
      return { sessions: [], projects: [] };
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ ok: true, terminal_launched: true });

    renderWithProviders(<Sidebar collapsed={false} />);

    // 1. Verify Provider & CLI group header is present
    expect(screen.getByText(/Danh sách Provider & CLI|Provider & CLI Hub/i)).toBeInTheDocument();

    // 2. Verify all providers are listed
    expect(screen.getByText(/Claude CLI Terminal/i)).toBeInTheDocument();
    expect(screen.getByText(/OpenAI Codex CLI/i)).toBeInTheDocument();
    expect(screen.getByText(/Antigravity CLI \(agy\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Gemini CLI/i)).toBeInTheDocument();
    expect(screen.getByText(/Feynman Research CLI/i)).toBeInTheDocument();
    expect(screen.getByText(/OpenCode Sandbox CLI/i)).toBeInTheDocument();
    expect(screen.getByText(/PaperOrchestra Engine/i)).toBeInTheDocument();
    expect(screen.getByText(/OpenScience Runtime/i)).toBeInTheDocument();
    expect(screen.getByText(/Python venv Terminal/i)).toBeInTheDocument();

    // 3. Test 1-click manual launch button for PaperOrchestra
    const poLaunchBtn = screen.getByTitle(/Mở thủ công 1-Click: khởi chạy PaperOrchestra Engine trong cửa sổ terminal ngoài/i);
    expect(poLaunchBtn).toBeInTheDocument();
    fireEvent.click(poLaunchBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/providers/paperorchestra/launch', { terminal: true });
    });

    // 4. Test clicking Codex provider row opens CLI drawer and sets selected provider
    const codexRow = screen.getByText(/OpenAI Codex CLI/i);
    fireEvent.click(codexRow);

    expect(useUIStore.getState().drawerKind).toBe('cli');
    expect(useUIStore.getState().selectedCliProvider).toBe('codex');
  });
});
