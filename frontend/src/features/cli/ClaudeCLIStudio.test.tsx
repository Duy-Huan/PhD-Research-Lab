import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { ClaudeCLIStudio } from './ClaudeCLIStudio';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('ClaudeCLIStudio', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setLanguage('vi');
    useUIStore.setState({ activeSessionId: 'sess-cli-test-1', drawerKind: 'cli' });
  });

  it('renders Claude CLI studio with header, workflows quick strip, and prompt input frame', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/config')) {
        return { version: '6.4.2', agent_models: { assistant: 'claude-3-7-sonnet' } };
      }
      if (url.includes('/api/chat/sessions')) {
        return { id: 'sess-cli-test-1', messages: [] };
      }
      return {};
    });

    renderWithProviders(<ClaudeCLIStudio />);

    expect(screen.getByText(/Claude CLI Studio/i)).toBeInTheDocument();
    expect(screen.getByText(/Khảo sát \/lit/i)).toBeInTheDocument();
    expect(screen.getByText(/Đề cương \/outline/i)).toBeInTheDocument();
    expect(screen.getByText(/Thực nghiệm \/code/i)).toBeInTheDocument();
    expect(screen.getByText(/Harness \/harness/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Nhập câu hỏi hoặc \/ để chọn quy trình\/lệnh/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/claude-3-7-sonnet/i)).toBeInTheDocument();
      expect(screen.getByText(/v6.4.2/i)).toBeInTheDocument();
    });
  });

  it('handles /workflow list command and renders workflow catalog table', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ id: 'sess-cli-test-1', messages: [], skills: [
      {name: 'lit', title: 'Literature from backend', description: 'A real registered command'},
      {name: 'science', title: 'OpenScience task', description: 'A bounded engine task'},
    ] });

    renderWithProviders(<ClaudeCLIStudio />);

    const input = screen.getByPlaceholderText(/Nhập câu hỏi hoặc \/ để chọn quy trình\/lệnh/i);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/skills'));
    fireEvent.change(input, { target: { value: '/workflow list' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText(/Danh mục Quy trình Nghiên cứu PhD Lab/i)).toBeInTheDocument();
      expect(screen.getByText(/Literature from backend/i)).toBeInTheDocument();
      expect(screen.getByText(/OpenScience task/i)).toBeInTheDocument();
    });
  });

  it('sends prompt, displays user box and assistant response in framed Claude CLI panels', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ id: 'turn-123', status: 'running' });
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/chat/sessions')) {
        return {
          id: 'sess-cli-test-1',
          turns: [{ id: 'turn-123', status: 'completed' }],
          messages: [
            { id: 'm1', role: 'user', content: 'Tìm hiểu về PINNs' },
            { id: 'm2', role: 'assistant', content: 'PINNs là mạng nơ-ron tích hợp phương trình đạo hàm riêng.' },
          ],
          approvals: [],
        };
      }
      return {};
    });

    renderWithProviders(<ClaudeCLIStudio />);

    const input = screen.getByPlaceholderText(/Nhập câu hỏi hoặc \/ để chọn quy trình\/lệnh/i);
    fireEvent.change(input, { target: { value: 'Tìm hiểu về PINNs' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/chat/sessions/sess-cli-test-1/turns', expect.any(Object));
      expect(screen.getByText(/Tìm hiểu về PINNs/i)).toBeInTheDocument();
      expect(screen.getByText(/PINNs là mạng nơ-ron tích hợp phương trình đạo hàm riêng/i)).toBeInTheDocument();
    });
  });

  it('renders provider switcher tabs and triggers 1-click external terminal launch', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ id: 'sess-cli-test-1', messages: [] });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ ok: true, terminal_launched: true });

    renderWithProviders(<ClaudeCLIStudio />);

    // 1. Verify provider tabs are rendered
    expect(screen.getByRole('button', { name: /Claude Code/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /OpenAI Codex/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Antigravity/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Gemini CLI/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Feynman|OpenCode|OpenScience|PaperOrchestra|Python venv/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name:/OpenAI Codex/i}));
    expect(useUIStore.getState().selectedCliProvider).toBe('codex');

    // 3. Click 1-Click Launch External Terminal button
    const launchExtBtn = screen.getByTitle(/Mở trực tiếp cửa sổ Terminal ngoài máy tính bằng 1 click/i);
    expect(launchExtBtn).toBeInTheDocument();
    fireEvent.click(launchExtBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/providers/codex/launch', { terminal: true });
      expect(screen.getByText(/Đã mở Terminal ngoài!/i)).toBeInTheDocument();
    });
  });
});
