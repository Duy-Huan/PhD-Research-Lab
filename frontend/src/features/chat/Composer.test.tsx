import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { Composer } from './Composer';
import { api } from '../../shared/api/client';

describe('Composer', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders input, reasoning effort selector, and model selector', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/models')) {
        return {
          default: 'cloud:google',
          providers: [{ id: 'google', label: 'Google AI', models: ['gemini-2.5-pro'] }],
          agent_catalog: {
            assistant: {
              engine: 'cloud:google',
              label: 'Google Cloud AI',
              models: ['gemini-2.5-pro', 'gemini-2.5-flash'],
              selected: 'gemini-2.5-pro',
            },
          },
        };
      }
      if (url.includes('/api/skills')) {
        return { skills: [{ name: 'outline', title: '5-Level Outline' }] };
      }
      return {};
    });

    const onSend = vi.fn();
    renderWithProviders(<Composer onSend={onSend} />);

    await waitFor(() => {
      expect(screen.getByText(/Tư duy: (Tự động|Auto)|Thinking: Auto/i)).toBeInTheDocument();
      expect(screen.getByText('gemini-2.5-pro')).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Hỏi bất kỳ điều gì/i);
    fireEvent.change(textarea, { target: { value: 'Hello research world' } });

    const sendBtn = screen.getByTitle(/Gửi/i);
    fireEvent.click(sendBtn);

    expect(onSend).toHaveBeenCalledWith(
      'Hello research world',
      expect.objectContaining({
        provider: 'app:gemini',
        model: 'gemini-2.5-pro',
      })
    );
  });

  it('allows selecting reasoning effort', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({});
    const onSend = vi.fn();
    renderWithProviders(<Composer onSend={onSend} />);

    const select = screen.getByTitle(/Mức độ tư duy/i).querySelector('select')!;
    fireEvent.change(select, { target: { value: 'high' } });

    const textarea = screen.getByPlaceholderText(/Hỏi bất kỳ điều gì/i);
    fireEvent.change(textarea, { target: { value: 'Deep task' } });

    const sendBtn = screen.getByTitle(/Gửi/i);
    fireEvent.click(sendBtn);

    expect(onSend).toHaveBeenCalledWith(
      'Deep task',
      expect.objectContaining({
        reasoning: 'high',
      })
    );
  });

  it('autocompletes slash command on Tab key press', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/skills')) {
        return { skills: [{ name: 'feynman', title: 'Literature SKB' }] };
      }
      return {};
    });

    const onSend = vi.fn();
    renderWithProviders(<Composer onSend={onSend} />);

    const textarea = screen.getByPlaceholderText(/Hỏi bất kỳ điều gì/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '/fey' } });

    await waitFor(() => {
      expect(screen.getByText('/feynman')).toBeInTheDocument();
    });

    fireEvent.keyDown(textarea, { key: 'Tab' });
    expect(textarea.value).toBe('/feynman ');
  });

  it('toggles research utilities popout menu on icon click', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({});
    const onSend = vi.fn();
    renderWithProviders(<Composer onSend={onSend} />);

    const toolsBtn = screen.getByTitle(/Tiện ích & Kỹ năng nghiên cứu/i);
    expect(toolsBtn).toBeInTheDocument();

    fireEvent.click(toolsBtn);
    expect(screen.getByText('Outline')).toBeInTheDocument();
    expect(screen.getByText('Feynman')).toBeInTheDocument();
    expect(screen.getByText('OpenScience')).toBeInTheDocument();
  });

  it('renders unauthenticated CLI warning and supports terminal login or web/app forward', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/models')) {
        return {
          agent_catalog: {
            assistant: {
              engine: 'cli:codex',
              label: 'OpenAI Codex (ChatGPT)',
              models: ['gpt-5-codex'],
              selected: 'gpt-5-codex',
            },
          },
          providers: [
            { id: 'cli:codex', state: 'AUTH_EXPIRED', available: false },
          ],
        };
      }
      return {};
    });

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});
    renderWithProviders(<Composer onSend={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/Chưa đăng nhập OpenAI Codex \(ChatGPT\)/i)).toBeInTheDocument();
    });

    // Test terminal login click
    const termBtn = screen.getByRole('button', { name: /Đăng nhập CLI|Terminal Login/i });
    fireEvent.click(termBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/providers/codex/connect', { mode: 'terminal' });

    // Test web/app forward click
    const webBtn = screen.getByRole('button', { name: /Mở ứng dụng CLI|Open CLI App/i });
    fireEvent.click(webBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/providers/codex/connect', { mode: 'app' });
  });

  it('handles pasting screenshot images from clipboard with preview thumbnail', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({});
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      id: 'att_img123456',
      name: 'screenshot_test.png',
      kind: 'image',
      width: 400,
      height: 300,
    });

    renderWithProviders(<Composer onSend={vi.fn()} />);

    const textarea = screen.getByPlaceholderText(/Hỏi bất kỳ điều gì/i);

    // Mock clipboard paste with image file
    const file = new File(['fake-png-data'], 'screenshot_test.png', { type: 'image/png' });
    const clipboardData = {
      items: [
        {
          type: 'image/png',
          getAsFile: () => file,
        },
      ],
      getData: () => '',
    };

    fireEvent.paste(textarea, { clipboardData });

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/chat/attachments', expect.any(FormData));
      expect(screen.getByTestId('attached-images-strip')).toBeInTheDocument();
      expect(screen.getAllByText('screenshot_test.png').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('handles pasting long prompts and renders collapsible .txt document cards with preview', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({});
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ id: 'att_doc789012' });
    const onSend = vi.fn();

    renderWithProviders(<Composer onSend={onSend} />);

    const textarea = screen.getByPlaceholderText(/Hỏi bất kỳ điều gì/i);

    // Create a long text prompt with 15 lines (>10 lines threshold)
    const longPromptLines = Array.from({ length: 15 }, (_, i) => `Line ${i + 1}: Detailed experimental analysis and findings on model behavior`).join('\n');

    const clipboardData = {
      items: [],
      getData: (type: string) => (type === 'text' ? longPromptLines : ''),
    };

    fireEvent.paste(textarea, { clipboardData });

    await waitFor(() => {
      expect(screen.getByTestId('attached-documents-strip')).toBeInTheDocument();
      expect(screen.getByText(/15 (dòng|lines)/i)).toBeInTheDocument();
    });

    // Test preview modal
    const viewBtn = screen.getByRole('button', { name: /Xem|View/i });
    fireEvent.click(viewBtn);

    expect(screen.getByText(/Line 1: Detailed experimental analysis/)).toBeInTheDocument();

    // Close preview
    const closeBtn = screen.getByText(/Line 1: Detailed experimental analysis/).closest('div')!.parentElement!.querySelector('button.icon')!;
    fireEvent.click(closeBtn);

    // Send the prompt with attached document
    const sendBtn = screen.getByTitle(/Gửi/i);
    expect(sendBtn).not.toBeDisabled();
    fireEvent.click(sendBtn);

    expect(onSend).toHaveBeenCalledWith(
      expect.stringContaining('Line 1: Detailed experimental analysis'),
      expect.any(Object)
    );
  });

  it('handles dragging and dropping image files into composer', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({});
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      id: 'att_drop999',
      name: 'architecture_diagram.png',
      kind: 'image',
    });

    renderWithProviders(<Composer onSend={vi.fn()} />);

    const textarea = screen.getByPlaceholderText(/Hỏi bất kỳ điều gì/i);
    const dropzone = textarea.parentElement!;

    // Drag enter / over
    fireEvent.dragOver(dropzone);
    expect(screen.getByText(/Thả hình ảnh hoặc file văn bản vào đây/i)).toBeInTheDocument();

    // Drop image
    const file = new File(['img-content'], 'architecture_diagram.png', { type: 'image/png' });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/chat/attachments', expect.any(FormData));
      expect(screen.getAllByText('architecture_diagram.png').length).toBeGreaterThanOrEqual(1);
    });
  });
});
