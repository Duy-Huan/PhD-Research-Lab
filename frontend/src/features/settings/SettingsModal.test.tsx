import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { SettingsModal } from './SettingsModal';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

describe('SettingsModal', () => {
  const mockConfig = {
    version: '6.4.2',
    providers: {
      google: { model: 'gemini-2.5-pro' },
      anthropic: { model: 'claude-3-7-sonnet' },
      openai: { model: 'gpt-4o' },
    },
    agents: {
      assistant: { label: 'Trợ lý chính' },
      research: { label: 'Khảo sát tài liệu' },
      reviewer: { label: 'Bình duyệt khoa học' },
      utility: { label: 'Tiện ích' },
    },
    agent_modes: {
      assistant: 'cloud:google',
      research: 'claude_code',
      reviewer: 'codex',
      utility: 'antigravity',
    },
    agent_models: {
      assistant: 'gemini-2.5-pro',
      research: 'claude-3-7-sonnet',
      reviewer: 'o3-mini',
      utility: 'gemini-2.5-flash',
    },
    provider_specs: {
      google: { label: 'Google Cloud AI', models: ['gemini-2.5-pro', 'gemini-2.5-flash'] },
      anthropic: { label: 'Anthropic Claude', models: ['claude-3-7-sonnet', 'claude-3-5-haiku'] },
      openai: { label: 'OpenAI', models: ['gpt-4o', 'o3-mini'] },
    },
    runs: {
      auto_approve_risk: 0,
      slot_cloud: 2,
      slot_cli: 1,
      slot_cpu: 2,
      slot_local_llm: 1,
    },
    ui: { language: 'vi', theme: 'system', scale: 1, prose_font: 'sans' },
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    useUIStore.getState().setLanguage('vi');
    useUIStore.setState({ mainView: 'settings', settingsTab: 'models' });
  });

  it('renders settings tabs and model configuration and enables maximum automation', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});
    vi.spyOn(api, 'get').mockResolvedValue(mockConfig);

    renderWithProviders(<SettingsModal />);

    await waitFor(() => {
      expect(screen.getByText(/Trợ lý chính/i)).toBeInTheDocument();
      expect(screen.getByText(/Bật Tự động hóa Đa Tác nhân/i)).toBeInTheDocument();
    });

    // Toggle parallel mode
    const parallelBtn = screen.getByText(/Bật Tự động hóa Đa Tác nhân/i);
    fireEvent.click(parallelBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/config',
        expect.objectContaining({
          runs: expect.objectContaining({
            auto_approve_risk: 1,
            slot_cloud: 8,
            slot_cli: 4,
          }),
        })
      );
    });
  });

  it('switches settings tabs, tests appearance settings, and returns to workspace', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({});
    vi.spyOn(api, 'get').mockResolvedValue(mockConfig);

    renderWithProviders(<SettingsModal />);

    await waitFor(() => {
      expect(screen.getByText(/Research Engines|Công cụ Nghiên cứu/i)).toBeInTheDocument();
    });

    // Switch to Research Engines tab
    const provTab = screen.getByText(/Research Engines|Công cụ Nghiên cứu/i);
    fireEvent.click(provTab);

    // Switch to Appearance tab
    const appearanceTab = screen.getByText(/Giao diện & Ngôn ngữ/i);
    fireEvent.click(appearanceTab);

    await waitFor(() => {
      expect(screen.getByText(/Chủ đề Giao diện|Color Themes/i)).toBeInTheDocument();
    });

    // Switch language to English using header ENG button
    const engBtn = screen.getByText('ENG');
    fireEvent.click(engBtn);
    expect(useUIStore.getState().language).toBe('en');

    // Switch UI Scale
    const scaleSelect = screen.getByTitle(/Tỉ lệ thu phóng giao diện|UI Display Scale/i).querySelector('select') as HTMLSelectElement;
    fireEvent.change(scaleSelect, { target: { value: '1.1' } });
    expect(useUIStore.getState().uiScale).toBe(1.1);

    // Change prose font
    const fontSelect = screen.getByDisplayValue(/Sans-serif/i);
    fireEvent.change(fontSelect, { target: { value: 'serif' } });
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/config',
        expect.objectContaining({
          ui: expect.objectContaining({ prose_font: 'serif' }),
        })
      );
    });

    // Test separated UI language and AI language controls
    const aiLangSelect = document.getElementById('ai-language-select') as HTMLSelectElement;
    expect(aiLangSelect).toBeInTheDocument();
    fireEvent.change(aiLangSelect, { target: { value: 'en' } });
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/config',
        expect.objectContaining({
          ui: expect.objectContaining({ ai_language: 'en' }),
        })
      );
    });

    // Click back to workspace button
    const backBtn = screen.getByTitle(/Quay lại khu vực Nghiên cứu & Trò chuyện|Back to Research & Chat Workspace/i);
    fireEvent.click(backBtn);
    expect(useUIStore.getState().mainView).toBe('chat');
  });

  it('triggers provider launch and data synchronization back to PhD Lab', async () => {
    useUIStore.setState({ mainView: 'settings', settingsTab: 'engines' });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      ok: true,
      total_changed: 3,
      total_observed: 12,
    });
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/providers')) {
        return {
          providers: [
            { id: 'opencode', label: 'OpenCode Sandbox', category: 'coding', ready: true, state: 'READY', detail: 'Ready' },
          ],
        };
      }
      return mockConfig;
    });

    renderWithProviders(<SettingsModal />);

    const launchBtn = await screen.findByRole('button', { name: /Mở Ứng dụng|Open App/i });
    fireEvent.click(launchBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/providers/opencode/launch', {});

    const syncBtn = await screen.findByRole('button', { name: /Đồng bộ về Lab|Sync to Lab/i });
    fireEvent.click(syncBtn);
    expect(postSpy).toHaveBeenCalledWith('/api/providers/opencode/sync', {});
  });
});
