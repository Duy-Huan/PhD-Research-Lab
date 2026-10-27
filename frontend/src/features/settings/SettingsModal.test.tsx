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

  it('keeps PaperOrchestra integrated and opens native tools without third-party launches', async () => {
    useUIStore.setState({mainView:'settings',settingsTab:'engines'});
    const post=vi.spyOn(api,'post').mockResolvedValue({});
    vi.spyOn(api,'get').mockImplementation(async url => {
      if(url.includes('/api/providers')) return {providers:[
        {id:'paperorchestra',label:'PaperOrchestra',kind:'embedded_engine',state:'READY',ready:true},
        {id:'tracking',label:'Native tracking',kind:'native_tool',state:'READY',ready:true},
      ]};
      if(url==='/api/models') return {providers:[],agent_catalog:{}};
      return mockConfig;
    });
    renderWithProviders(<SettingsModal />);
    fireEvent.click(await screen.findByRole('button',{name:'PaperOrchestra Studio'}));
    expect(useUIStore.getState().drawerKind).toBe('paper');
    fireEvent.click(screen.getByRole('button',{name:/Mở workspace native|Open native workspace/}));
    expect(useUIStore.getState().drawerKind).toBe('code');
    expect(post).not.toHaveBeenCalled();
  });

  it('renders optional plugins catalog and allows installing AI-Scientist-v2 via GitHub plugin mechanism', async () => {
    useUIStore.setState({ mainView: 'settings', settingsTab: 'skills' });
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ id: 'sakanaai-ai-scientist-v2', skills: [] });
    vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
      if (url.includes('/api/plugins')) {
        return {
          plugins: [],
          optional_plugins: [
            {
              id: 'sakanaai-ai-scientist-v2',
              name: 'AI-Scientist-v2',
              title: 'The AI Scientist v2 (Sakana AI)',
              url: 'https://github.com/SakanaAI/AI-Scientist-v2',
              category: 'writing',
              description: 'Sinh ý tưởng nghiên cứu, viết nháp bài báo theo template ICML/NeurIPS',
              skills: ['/ais-idea', '/ais-review', '/ais-write'],
              installed: false,
              enabled: false,
            },
          ],
        };
      }
      if (url.includes('/api/skills')) {
        return { skills: [] };
      }
      return mockConfig;
    });

    renderWithProviders(<SettingsModal />);

    // 1. Verify Optional GitHub Plugins Catalog title is rendered
    await waitFor(() => {
      expect(screen.getByText(/Danh mục Plugin Tùy chọn|Optional GitHub Plugins/i)).toBeInTheDocument();
      expect(screen.getByText(/The AI Scientist v2 \(Sakana AI\)/i)).toBeInTheDocument();
      expect(screen.getByText(/\/ais-idea/i)).toBeInTheDocument();
      expect(screen.getByText(/\/ais-review/i)).toBeInTheDocument();
      expect(screen.getByText(/\/ais-write/i)).toBeInTheDocument();
    });

    // 2. Click "Cài qua GitHub" button on AI-Scientist-v2 card
    const installBtn = screen.getByTitle(/Cài đặt The AI Scientist v2 \(Sakana AI\) qua cơ chế GitHub plugin/i);
    expect(installBtn).toBeInTheDocument();
    fireEvent.click(installBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/api/plugins', {
        url: 'https://github.com/SakanaAI/AI-Scientist-v2',
        enable: true,
      });
    });
  });
});
