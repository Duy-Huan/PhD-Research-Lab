import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { AppConfig, SkillItem } from '../../shared/api/types';
import {
  Settings,
  Cpu,
  FlaskConical,
  Search,
  HardDrive,
  Brain,
  Shield,
  Sparkles,
  Palette,
  Check,
  RefreshCw,
  Play,
  Trash2,
  Plus,
  ExternalLink,
  Key,
  Server,
  Terminal,
  ArrowLeft,
  Award,
  Plug,
} from 'lucide-react';

const BUILTIN_THEMES = [
  {
    id: 'system',
    name: 'Theo hệ thống (Auto)',
    base: 'light',
    swatch: { bg: '#f7f6f2', panel: '#ffffff', ink: '#1c1b19', accent: '#b94b1c' },
  },
  {
    id: 'light',
    name: 'Academic Daylight (Sáng)',
    base: 'light',
    swatch: { bg: '#f7f6f2', panel: '#ffffff', ink: '#1c1b19', accent: '#b94b1c' },
  },
  {
    id: 'dark',
    name: 'Obsidian Research (Tối)',
    base: 'dark',
    swatch: { bg: '#1d1c1a', panel: '#252422', ink: '#ecebe6', accent: '#e7783f' },
  },
  {
    id: 'openscience-indigo',
    name: 'OpenScience Studio (Indigo)',
    base: 'dark',
    swatch: { bg: '#0f1420', panel: '#171f30', ink: '#edf2ff', accent: '#4f8cff' },
    colors: {
      bg: '#0f1420',
      panel: '#171f30',
      side: '#0b0f19',
      raise: '#1e293b',
      ink: '#edf2ff',
      'ink-2': '#cbd5e1',
      muted: '#94a3b8',
      faint: '#64748b',
      line: '#263248',
      'line-2': '#334155',
      accent: '#3b82f6',
      'accent-2': '#60a5fa',
      'accent-ink': '#ffffff',
      'accent-soft': '#1e3a5f',
      'code-bg': '#131b2e',
      sel: '#1e3a8a',
    },
  },
  {
    id: 'lab-midnight',
    name: 'MIT Media Lab Midnight',
    base: 'dark',
    swatch: { bg: '#181b24', panel: '#202431', ink: '#eceef5', accent: '#a6b9ff' },
    colors: {
      bg: '#181b24',
      panel: '#202431',
      side: '#151821',
      raise: '#282e3d',
      ink: '#eceef5',
      'ink-2': '#c4cbdb',
      muted: '#a4afc5',
      faint: '#8d99ae',
      line: '#373f52',
      'line-2': '#505c73',
      accent: '#a6b9ff',
      'accent-2': '#c5d1ff',
      'accent-ink': '#151821',
      'accent-soft': '#303c61',
    },
  },
  {
    id: 'lab-forest',
    name: 'Oxford Botanical Lab (Forest)',
    base: 'light',
    swatch: { bg: '#f2f6f2', panel: '#ffffff', ink: '#1b3028', accent: '#27764b' },
    colors: {
      bg: '#f2f6f2',
      panel: '#ffffff',
      side: '#e8efe9',
      raise: '#ffffff',
      ink: '#1b3028',
      'ink-2': '#344e41',
      muted: '#586c60',
      faint: '#6d7e73',
      line: '#d2ded4',
      'line-2': '#afc3b3',
      accent: '#27764b',
      'accent-2': '#1e5b39',
      'accent-ink': '#ffffff',
      'accent-soft': '#e1f0e6',
    },
  },
];

export function applyThemeById(id: string) {
  const root = document.documentElement;
  const customTokens = [
    'bg', 'panel', 'side', 'raise', 'ink', 'ink-2', 'muted', 'faint',
    'line', 'line-2', 'accent', 'accent-2', 'accent-ink', 'accent-soft',
    'code-bg', 'sel',
  ];
  for (const t of customTokens) {
    root.style.removeProperty('--' + t);
  }
  const found = BUILTIN_THEMES.find((t) => t.id === id);
  if (found && found.colors) {
    root.setAttribute('data-theme', found.base);
    root.setAttribute('data-theme-package', found.id);
    for (const [k, v] of Object.entries(found.colors)) {
      root.style.setProperty('--' + k, v);
    }
  } else if (id === 'dark' || id === 'light') {
    root.removeAttribute('data-theme-package');
    root.setAttribute('data-theme', id);
  } else {
    root.removeAttribute('data-theme-package');
    root.removeAttribute('data-theme');
  }
  try {
    if (id === 'system') localStorage.removeItem('pl.theme');
    else localStorage.setItem('pl.theme', id);
  } catch {
    // ignore storage errors
  }
}

const TABS = [
  { id: 'models', label: 'Mô hình & AI Agents', icon: Cpu, desc: 'Cloud API keys, 4 Agents, VRAM local & Routing' },
  { id: 'engines', label: 'Research Engines', icon: Terminal, desc: 'OpenScience, Feynman, OpenCode & CLI' },
  { id: 'search', label: 'Tìm kiếm & Xếp hạng', icon: Search, desc: 'OpenAlex, Semantic Scholar, CORE & SCImago' },
  { id: 'hardware', label: 'Thí nghiệm & Phần cứng', icon: HardDrive, desc: 'GPU Guard, Background Runs, ClearML, VS Code' },
  { id: 'memory', label: 'Bộ nhớ & Ngữ cảnh', icon: Brain, desc: 'Context Memory v2, Token Budget & AIWS' },
  { id: 'mcp', label: 'MCP & Bảo mật CLI', icon: Shield, desc: 'MCP Server, Inference Agent & Context Firewall' },
  { id: 'skills', label: 'Kỹ năng (/) & Plugins', icon: Sparkles, desc: 'Lệnh /skills tùy chỉnh & GitHub Skill Plugins' },
  { id: 'look', label: 'Giao diện & Ngôn ngữ', icon: Palette, desc: 'Chủ đề màu OpenScience, Font chữ & Ngôn ngữ' },
];

export const SettingsModal: React.FC = () => {
  const queryClient = useQueryClient();
  const { settingsTab, openSettings, setMainView, language, setLanguage, uiScale, setUiScale } = useUIStore();
  const [activeTab, setActiveTab] = useState(settingsTab || 'models');
  const [searchFilter, setSearchFilter] = useState('');
  const [toastMsg, setToastMsg] = useState<{ text: string; kind?: 'ok' | 'err' } | null>(null);

  // Sync activeTab if store changes
  useEffect(() => {
    if (settingsTab) setActiveTab(settingsTab);
  }, [settingsTab]);

  const notify = (text: string, kind: 'ok' | 'err' = 'ok') => {
    setToastMsg({ text, kind });
    setTimeout(() => setToastMsg(null), 4000);
  };

  // Load main config
  const { data: config, isLoading } = useQuery<AppConfig>({
    queryKey: ['config'],
    queryFn: () => api.get<AppConfig>('/api/config'),
  });

  // Save config mutation (POST /api/config — exact backend route)
  const saveConfigMutation = useMutation({
    mutationFn: (patch: Record<string, unknown>) => api.post<AppConfig>('/api/config', patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      queryClient.invalidateQueries({ queryKey: ['models'] });
      notify('Đã lưu cấu hình thành công!');
    },
    onError: (err: Error) => {
      notify(`Lỗi lưu cấu hình: ${err.message}`, 'err');
    },
  });

  const savePatch = (patch: Record<string, unknown>) => {
    saveConfigMutation.mutate(patch);
  };

  // Sub-queries for active tabs
  const { data: localStatus, refetch: refetchLocal } = useQuery<any>({
    queryKey: ['models-local'],
    queryFn: () => api.get('/api/models/local'),
    enabled: activeTab === 'models',
  });

  const { data: researchProvidersData, refetch: refetchProviders } = useQuery<{ providers: any[] }>({
    queryKey: ['research-providers-status'],
    queryFn: () => api.get('/api/providers?fresh=1'),
    enabled: activeTab === 'engines',
  });

  const { data: rankingStatus, refetch: refetchRanking } = useQuery<any>({
    queryKey: ['ranking-status'],
    queryFn: () => api.get('/api/ranking'),
    enabled: activeTab === 'search',
  });

  const { data: skillsData, refetch: refetchSkills } = useQuery<{ skills: SkillItem[]; errors: any[] }>({
    queryKey: ['skills'],
    queryFn: () => api.get('/api/skills'),
    enabled: activeTab === 'skills',
  });

  const { data: pluginsData, refetch: refetchPlugins } = useQuery<{ plugins: any[]; root: string }>({
    queryKey: ['plugins'],
    queryFn: () => api.get('/api/plugins'),
    enabled: activeTab === 'skills',
  });

  // Local state for inputs
  const [providerKeyInputs, setProviderKeyInputs] = useState<Record<string, string>>({});
  const [providerModelInputs, setProviderModelInputs] = useState<Record<string, string>>({});
  const [providerUrlInputs, setProviderUrlInputs] = useState<Record<string, string>>({});
  const [fetchedProviderModels, setFetchedProviderModels] = useState<Record<string, string[]>>({});
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [showAllProviders, setShowAllProviders] = useState(false);

  // OpenScience token state
  const [osciToken, setOsciToken] = useState('');
  // Search keys state
  const [searchKeyInputs, setSearchKeyInputs] = useState<Record<string, string>>({});
  // Venue lookup test
  const [venueLookupQuery, setVenueLookupQuery] = useState('');
  const [venueLookupResult, setVenueLookupResult] = useState<any>(null);
  // New Skill Editor
  const [newSkillScope, setNewSkillScope] = useState<'project' | 'user'>('project');
  const [newSkillText, setNewSkillText] = useState(
    `---\nname: tomtat\ntitle: Tóm tắt bài báo chuyên sâu\ndescription: Tóm tắt bài báo theo cấu trúc học thuật chuẩn\nusage: <tên bài / file>\ncategory: research\nagent: research\nmode: chat\nrisk: 0\n---\nTóm tắt chi tiết bài báo theo 6 mục: Vấn đề nghiên cứu, Phương pháp đề xuất, Bộ dữ liệu & Thực nghiệm, Kết quả chính, Hạn chế, và Liên hệ với Đề cương hiện tại.\n`
  );
  // GitHub Plugin URL
  const [pluginUrl, setPluginUrl] = useState('');
  const [installingPlugin, setInstallingPlugin] = useState(false);
  // Theme state
  const [selectedTheme, setSelectedTheme] = useState<string>(() => {
    try {
      return localStorage.getItem('pl.theme') || 'system';
    } catch {
      return 'system';
    }
  });

  if (isLoading || !config) {
    return (
      <div style={{ padding: 32, display: 'flex', alignItems: 'center', gap: 12 }}>
        <div className="spin" />
        <span>Đang tải cấu hình hệ thống PhD Research Lab…</span>
      </div>
    );
  }

  const providerSpecs = config.provider_specs || {};
  const mainProviders = ['anthropic', 'openai', 'gemini', 'deepseek', 'openrouter', 'groq', config.default_cloud];
  const visibleTabs = TABS.filter(
    (t) =>
      !searchFilter.trim() ||
      (t.label + ' ' + t.desc).toLowerCase().includes(searchFilter.trim().toLowerCase())
  );

  // Test provider connection
  const handleTestProvider = async (pid: string) => {
    setTestingProvider(pid);
    try {
      const res = await api.post<{ ok: boolean; model: string; reply: string }>('/api/models/test', {
        provider: pid,
        model: providerModelInputs[pid] || config.providers?.[pid]?.model,
      });
      notify(`Kết nối ${pid} (${res.model}) thành công! Phản hồi: "${res.reply}"`);
    } catch (err) {
      notify(`Lỗi kết nối ${pid}: ${(err as Error).message}`, 'err');
    } finally {
      setTestingProvider(null);
    }
  };

  // List models from provider API
  const handleFetchModels = async (pid: string) => {
    try {
      const res = await api.post<{ models: string[] }>('/api/models/list', { provider: pid });
      setFetchedProviderModels((prev) => ({ ...prev, [pid]: res.models || [] }));
      notify(`Đã tải ${(res.models || []).length} model từ ${pid}`);
    } catch (err) {
      notify(`Không tải được danh sách model từ ${pid}: ${(err as Error).message}`, 'err');
    }
  };

  // Save a single cloud provider row
  const handleSaveProvider = (pid: string) => {
    const patch: Record<string, string> = {};
    if (providerModelInputs[pid] !== undefined) {
      patch.model = providerModelInputs[pid];
    } else if (config.providers?.[pid]?.model) {
      patch.model = config.providers[pid].model;
    }
    if (providerKeyInputs[pid]?.trim()) {
      patch.api_key = providerKeyInputs[pid].trim();
    }
    if (providerUrlInputs[pid] !== undefined) {
      patch.base_url = providerUrlInputs[pid].trim();
    }
    savePatch({ providers: { [pid]: patch } });
    setProviderKeyInputs((prev) => ({ ...prev, [pid]: '' }));
  };

  // Engine options for the 4 agents (includes Subscriptions, CLIs, Local, and all 17 Cloud Providers)
  const agentEngineOptions = [
    ['auto', 'Tự động (Smart Router: Local → Cloud)'],
    ['codex', 'ChatGPT Subscription (Plus/Pro/Team · Codex CLI)'],
    ['claude_code', 'Claude Subscription (Pro/Max · Claude Code CLI)'],
    ['antigravity', 'Google Antigravity (IDE + agy CLI)'],
    ['gemini_cli', 'Google Gemini Subscription (Gemini CLI)'],
    ['claude', 'Anthropic Claude (Ưu tiên nếu có API key)'],
    ['cloud', `Cloud mặc định (${config.default_cloud})`],
    ['local', 'LM Studio (Local VRAM)'],
    ['ollama', 'Ollama (Local VRAM)'],
    ['mcp', 'MCP Inference Tool'],
    ...Object.entries(providerSpecs).map(([k, v]) => [k, `${v.label} (Cloud API)`]),
  ];

  const CLI_DEFAULT_MODELS: Record<string, string[]> = {
    codex: ['gpt-5', 'gpt-5-codex', 'gpt-5-mini', 'o3', 'o4-mini', 'gpt-4.1'],
    chatgpt_sub: ['gpt-5', 'gpt-5-codex', 'gpt-5-mini', 'o3', 'o4-mini', 'gpt-4.1'],
    claude_code: ['sonnet', 'opus', 'haiku', 'claude-sonnet-4-6', 'claude-opus-4-6'],
    gemini_cli: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash'],
    antigravity: ['gemini-2.5-pro', 'gemini-2.5-flash', 'claude-sonnet-4-6'],
  };

  // Strict provider-scoped model list for any selected agent engine/provider
  const getModelsForEngine = (mode: string): string[] => {
    const clean = (mode || '').replace(/^cli:/, '').replace(/^app:/, '');
    if (clean === 'auto') return [];
    const targetPid =
      clean === 'cloud'
        ? config.default_cloud
        : clean === 'claude'
        ? 'anthropic'
        : clean;

    if (targetPid === 'local') {
      const lmModels = (localStatus?.lmstudio?.models || []).map((m: any) =>
        typeof m === 'string' ? m : m.id
      );
      return Array.from(new Set([config.local_model, ...lmModels].filter(Boolean)));
    }
    if (targetPid === 'ollama') {
      const olModels = (localStatus?.ollama?.models || []).map((m: any) =>
        typeof m === 'string' ? m : m.name || m.id
      );
      return Array.from(new Set([config.ollama_model, ...olModels].filter(Boolean)));
    }
    if (targetPid === 'mcp') {
      return config.mcp_agent?.models || [];
    }
    if (CLI_DEFAULT_MODELS[targetPid]) {
      const cliSaved = config.gateway?.cli_models?.[targetPid] || [];
      return Array.from(new Set([...cliSaved, ...CLI_DEFAULT_MODELS[targetPid]]));
    }
    if (providerSpecs[targetPid]) {
      const fetched = fetchedProviderModels[targetPid] || [];
      const specModels = providerSpecs[targetPid]?.models || [];
      const currentDefault = config.providers?.[targetPid]?.model || providerSpecs[targetPid]?.model || '';
      return Array.from(new Set([currentDefault, ...fetched, ...specModels].filter(Boolean)));
    }
    return [];
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        background: 'var(--bg)',
        overflow: 'hidden',
      }}
    >
      {/* Top Studio Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 24px',
          background: 'var(--panel)',
          borderBottom: '1px solid var(--line)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            className="btn sm ghost"
            onClick={() => setMainView('chat')}
            title="Quay lại khu vực Nghiên cứu & Trò chuyện"
          >
            <ArrowLeft size={15} style={{ marginRight: 4 }} />
            <span>Quay lại Workspace</span>
          </button>
          <div style={{ width: 1, height: 20, background: 'var(--line)' }} />
          <Settings size={20} color="var(--accent)" />
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
              Trung tâm Cài đặt & Cấu hình Hệ thống (PhD Research Lab v{config.version})
            </h3>
            <span className="muted" style={{ fontSize: 12 }}>
              Dự án đang mở: <b>{config.project?.name}</b> ({config.project?.data_dir})
            </span>
          </div>
        </div>

        {/* Language Switcher (ENG / VI), UI Scale & Live Toast Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {toastMsg && (
            <div
              className={`chip ${toastMsg.kind === 'err' ? 'err' : 'ok'}`}
              style={{ padding: '6px 14px', fontSize: 13, fontWeight: 600 }}
            >
              {toastMsg.text}
            </div>
          )}

          {/* UI Scale Selector */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              background: 'var(--bg-2)',
              padding: '3px 8px',
              borderRadius: 8,
              border: '1px solid var(--line)',
              fontSize: 12,
            }}
            title="Tỉ lệ thu phóng giao diện (UI Scale)"
          >
            <span className="muted">Scale:</span>
            <select
              value={String(uiScale)}
              onChange={(e) => setUiScale(Number(e.target.value))}
              style={{
                border: 'none',
                background: 'transparent',
                color: 'var(--ink)',
                fontWeight: 600,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              <option value="0.85">85%</option>
              <option value="0.9">90%</option>
              <option value="1">100%</option>
              <option value="1.1">110%</option>
              <option value="1.2">120%</option>
            </select>
          </div>

          {/* Prominent ENG / VI Toggle */}
          <div
            style={{
              display: 'inline-flex',
              borderRadius: 8,
              border: '1px solid var(--line-2)',
              overflow: 'hidden',
              background: 'var(--bg-2)',
            }}
            title="Chuyển đổi ngôn ngữ Tiếng Việt / English"
          >
            <button
              type="button"
              className={`btn sm ${(config.ui?.language || language) === 'vi' ? 'accent' : 'ghost'}`}
              style={{ borderRadius: 0, padding: '4px 10px', fontWeight: 700 }}
              onClick={() => {
                setLanguage('vi');
                savePatch({ ui: { language: 'vi' } });
              }}
            >
              VI
            </button>
            <button
              type="button"
              className={`btn sm ${(config.ui?.language || language) === 'en' ? 'accent' : 'ghost'}`}
              style={{ borderRadius: 0, padding: '4px 10px', fontWeight: 700 }}
              onClick={() => {
                setLanguage('en');
                savePatch({ ui: { language: 'en' } });
              }}
            >
              ENG
            </button>
          </div>
        </div>
      </div>

      {/* Main Split View: Left Navigation Rail + Right Settings Content */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* Left Navigation Rail */}
        <nav
          style={{
            width: 280,
            borderRight: '1px solid var(--line)',
            background: 'var(--side)',
            padding: 14,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            overflowY: 'auto',
            flexShrink: 0,
          }}
        >
          <div style={{ position: 'relative', marginBottom: 8 }}>
            <Search
              size={14}
              color="var(--muted)"
              style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }}
            />
            <input
              type="search"
              className="input"
              style={{ paddingLeft: 32, fontSize: 13 }}
              placeholder="Tìm mục cài đặt…"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
            />
          </div>

          {visibleTabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setActiveTab(tab.id);
                  openSettings(tab.id);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  padding: '10px 12px',
                  borderRadius: 10,
                  border: isActive ? '1px solid var(--accent)' : '1px solid transparent',
                  background: isActive ? 'var(--panel)' : 'transparent',
                  boxShadow: isActive ? 'var(--shadow)' : 'none',
                  textAlign: 'left',
                  cursor: 'pointer',
                  width: '100%',
                }}
              >
                <Icon
                  size={18}
                  color={isActive ? 'var(--accent)' : 'var(--muted)'}
                  style={{ marginTop: 2, flexShrink: 0 }}
                />
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontWeight: isActive ? 650 : 500,
                      fontSize: 13.5,
                      color: isActive ? 'var(--ink)' : 'var(--ink-2)',
                    }}
                  >
                    {tab.label}
                  </div>
                  <div className="muted" style={{ fontSize: 11.5, lineHeight: 1.35, marginTop: 2 }}>
                    {tab.desc}
                  </div>
                </div>
              </button>
            );
          })}
        </nav>

        {/* Right Scrollable Settings Content */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '24px 36px 64px',
            maxWidth: 1080,
          }}
        >
          {/* ================================================================
              TAB 1: MODELS & AI AGENTS
             ================================================================ */}
          {activeTab === 'models' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {/* 1A. 4 Core AI Agents */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Cpu size={18} color="var(--accent)" />
                    <h3 style={{ margin: 0, fontSize: 16 }}>
                      Phân công Hãng Cung cấp & Model cho 4 AI Agents cốt lõi
                    </h3>
                  </div>
                  <button
                    type="button"
                    className="btn sm accent"
                    onClick={() =>
                      savePatch({
                        research_os: { enabled: true, team_enabled: true, multi_team_enabled: true },
                        lifecycle: { single_model_vram: false },
                        runs: { slot_cloud: 8, slot_cli: 4, slot_cpu: 4, slot_gpu: 1, auto_approve_risk: 1 },
                        aiws: { operating_mode: 'automation' },
                      })
                    }
                    title="Bỏ giới hạn chạy đơn lẻ — cho phép nhiều Agent làm việc song song với mức tự động hóa cao nhất"
                  >
                    <Sparkles size={13} style={{ marginRight: 5 }} />
                    <span>Bật Tự Động Hóa Đa Agent Tối Đa (Parallel Mode)</span>
                  </button>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 16px' }}>
                  Khi chọn hãng cung cấp (Cloud API, ChatGPT Subscription, Claude CLI, Gemini CLI, Antigravity, hoặc Local), danh sách Model bên phải sẽ tự động lọc chỉ hiển thị các model được hãng đó hỗ trợ. Model của <b>assistant</b> sẽ được dùng trực tiếp trong khung Chatbox chính.
                </p>

                <div className="table-scroll">
                  <table className="grid">
                    <thead>
                      <tr>
                        <th style={{ width: '34%' }}>Vai trò Agent</th>
                        <th style={{ width: '34%' }}>Hãng cung cấp / Nguồn Engine</th>
                        <th style={{ width: '32%' }}>Model hỗ trợ bởi Hãng đã chọn</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(config.agents || {}).map(([agentId, spec]) => {
                        const mode = config.agent_modes?.[agentId] || spec.default;
                        const currentModel = config.agent_models?.[agentId] || '';
                        const supportedModels = getModelsForEngine(mode);
                        const cleanMode = mode.replace(/^cli:/, '').replace(/^app:/, '');
                        const targetPid =
                          cleanMode === 'cloud'
                            ? config.default_cloud
                            : cleanMode === 'claude'
                            ? 'anthropic'
                            : cleanMode;
                        const canFetch = Boolean(providerSpecs[targetPid]);

                        return (
                          <tr key={agentId}>
                            <td>
                              <b style={{ fontSize: 13.5, textTransform: 'capitalize' }}>{agentId}</b>
                              <div className="muted" style={{ fontSize: 12 }}>{spec.label}</div>
                            </td>
                            <td>
                              <select
                                className="input"
                                value={mode}
                                onChange={(e) => {
                                  const nextMode = e.target.value;
                                  const nextModels = getModelsForEngine(nextMode);
                                  savePatch({
                                    agent_modes: { [agentId]: nextMode },
                                    agent_models: { [agentId]: nextModels[0] || '' },
                                  });
                                }}
                              >
                                {agentEngineOptions.map(([val, label]) => (
                                  <option key={val} value={val}>
                                    {label}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              {mode === 'auto' ? (
                                <span className="muted" style={{ fontSize: 12.5 }}>
                                  Tự động điều phối theo Smart Router
                                </span>
                              ) : (
                                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                  <select
                                    className="input"
                                    style={{ flex: 1 }}
                                    value={currentModel || supportedModels[0] || ''}
                                    onChange={(e) =>
                                      savePatch({ agent_models: { [agentId]: e.target.value } })
                                    }
                                  >
                                    {supportedModels.length === 0 && (
                                      <option value="">(Mặc định của {targetPid})</option>
                                    )}
                                    {supportedModels.map((m) => (
                                      <option key={m} value={m}>
                                        {m}
                                      </option>
                                    ))}
                                  </select>
                                  {canFetch && (
                                    <button
                                      type="button"
                                      className="btn sm ghost"
                                      title={`Tải danh sách model mới nhất từ ${targetPid}`}
                                      onClick={() => handleFetchModels(targetPid)}
                                    >
                                      <RefreshCw size={13} />
                                    </button>
                                  )}
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* 1B. Cloud API Providers */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Key size={18} color="var(--accent)" />
                    <h3 style={{ margin: 0, fontSize: 16 }}>
                      Nhà cung cấp Cloud API & Khóa Bảo mật (17 Providers)
                    </h3>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="muted" style={{ fontSize: 12.5 }}>Cloud mặc định:</span>
                    <select
                      className="input"
                      style={{ width: 210, padding: '4px 8px' }}
                      value={config.default_cloud}
                      onChange={(e) => savePatch({ default_cloud: e.target.value })}
                    >
                      {Object.entries(providerSpecs).map(([pid, spec]) => (
                        <option key={pid} value={pid}>
                          {spec.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  Khóa API chỉ được lưu cục bộ trong <code>data/config.json</code> và chỉ gửi trực tiếp tới endpoint của nhà cung cấp tương ứng.
                </p>

                <div className="table-scroll">
                  <table className="grid">
                    <thead>
                      <tr>
                        <th>Nhà cung cấp</th>
                        <th>API Key & Endpoint</th>
                        <th>Model Mặc định</th>
                        <th>Thao tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(providerSpecs)
                        .filter(([pid]) => showAllProviders || mainProviders.includes(pid) || config.providers?.[pid]?.has_key)
                        .map(([pid, spec]) => {
                          const p = config.providers?.[pid] || { model: spec.model };
                          const modelChoices = Array.from(
                            new Set([
                              providerModelInputs[pid],
                              p.model,
                              spec.model,
                              ...(spec.models || []),
                              ...(fetchedProviderModels[pid] || []),
                            ].filter(Boolean))
                          );
                          return (
                            <tr key={pid}>
                              <td>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                  <span
                                    className={`dot ${p.has_key ? 'ok' : ''}`}
                                    title={p.has_key ? 'Đã lưu API Key' : 'Chưa có API Key'}
                                  />
                                  <b>{spec.label}</b>
                                </div>
                                {spec.key_url && (
                                  <a
                                    href={spec.key_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ fontSize: 11.5, display: 'inline-flex', alignItems: 'center', gap: 3 }}
                                  >
                                    Lấy API Key <ExternalLink size={10} />
                                  </a>
                                )}
                              </td>
                              <td>
                                <input
                                  type="password"
                                  className="input"
                                  style={{ fontSize: 12.5 }}
                                  placeholder={p.has_key ? '•••••••• (Đã lưu — nhập để đổi)' : 'Nhập API key…'}
                                  value={providerKeyInputs[pid] || ''}
                                  onChange={(e) =>
                                    setProviderKeyInputs((prev) => ({ ...prev, [pid]: e.target.value }))
                                  }
                                />
                                <input
                                  type="text"
                                  className="input"
                                  style={{ fontSize: 11.5, marginTop: 4, padding: '4px 8px' }}
                                  placeholder={`Base URL: ${spec.base_url || 'https://...'}`}
                                  value={
                                    providerUrlInputs[pid] !== undefined
                                      ? providerUrlInputs[pid]
                                      : p.base_url || ''
                                  }
                                  onChange={(e) =>
                                    setProviderUrlInputs((prev) => ({ ...prev, [pid]: e.target.value }))
                                  }
                                />
                              </td>
                              <td>
                                <input
                                  list={`models-list-${pid}`}
                                  className="input"
                                  style={{ fontSize: 12.5 }}
                                  value={
                                    providerModelInputs[pid] !== undefined
                                      ? providerModelInputs[pid]
                                      : p.model || spec.model || ''
                                  }
                                  onChange={(e) =>
                                    setProviderModelInputs((prev) => ({ ...prev, [pid]: e.target.value }))
                                  }
                                  placeholder="Nhập hoặc chọn model ID…"
                                />
                                <datalist id={`models-list-${pid}`}>
                                  {modelChoices.map((m) => (
                                    <option key={m} value={m} />
                                  ))}
                                </datalist>
                              </td>
                              <td>
                                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                  <button
                                    type="button"
                                    className="btn sm accent"
                                    onClick={() => handleSaveProvider(pid)}
                                  >
                                    <Check size={13} /> Lưu
                                  </button>
                                  <button
                                    type="button"
                                    className="btn sm ghost"
                                    disabled={testingProvider === pid}
                                    onClick={() => handleTestProvider(pid)}
                                  >
                                    <Play size={12} /> {testingProvider === pid ? 'Đang thử…' : 'Thử'}
                                  </button>
                                  <button
                                    type="button"
                                    className="btn sm ghost"
                                    onClick={() => handleFetchModels(pid)}
                                    title="Tải danh sách model từ nhà cung cấp"
                                  >
                                    ↻ Models
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>

                <div style={{ marginTop: 10 }}>
                  <button
                    type="button"
                    className="btn sm ghost"
                    onClick={() => setShowAllProviders(!showAllProviders)}
                  >
                    {showAllProviders
                      ? 'Thu gọn danh sách nhà cung cấp phụ'
                      : `Hiển thị tất cả ${Object.keys(providerSpecs).length} nhà cung cấp (Mistral, Qwen, Moonshot, Cohere, Perplexity, Together, DeepInfra, 9Router, OmniRoute, Custom…)`}
                  </button>
                </div>
              </section>

              {/* 1C. Local VRAM Models (LM Studio & Ollama) */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Server size={18} color="var(--accent)" />
                    <h3 style={{ margin: 0, fontSize: 16 }}>
                      Mô hình Local trên máy (LM Studio & Ollama VRAM)
                    </h3>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button type="button" className="btn sm ghost" onClick={() => refetchLocal()}>
                      <RefreshCw size={13} /> Kiểm tra VRAM
                    </button>
                    <button
                      type="button"
                      className="btn sm"
                      onClick={async () => {
                        await api.post('/api/models/unload', { engine: 'all' });
                        refetchLocal();
                        notify('Đã giải phóng toàn bộ mô hình local khỏi VRAM!');
                      }}
                    >
                      Giải phóng VRAM (Unload All)
                    </button>
                  </div>
                </div>

                {/* Live status bar */}
                {localStatus && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '8px 12px',
                      background: 'var(--code-bg)',
                      borderRadius: 8,
                      marginBottom: 14,
                      fontSize: 12.5,
                    }}
                  >
                    <span className={`dot ${localStatus.lmstudio?.online ? 'ok' : ''}`} />
                    <span>LM Studio: {localStatus.lmstudio?.online ? 'Online' : 'Offline'}</span>
                    <span className={`dot ${localStatus.ollama?.online ? 'ok' : ''}`} />
                    <span>Ollama: {localStatus.ollama?.online ? 'Online' : 'Offline'}</span>
                    <span className="muted" style={{ marginLeft: 'auto' }}>
                      Đang nạp trong VRAM:{' '}
                      <b>
                        {[
                          ...(localStatus.lmstudio?.loaded || []),
                          ...(localStatus.ollama?.loaded || []).map((m: any) => m.id || m),
                        ].join(', ') || 'Trống (0 MB)'}
                      </b>
                    </span>
                  </div>
                )}

                <div className="grid2">
                  <label className="field">
                    <span>LM Studio Base URL</span>
                    <input
                      className="input"
                      defaultValue={config.lmstudio_base_url}
                      onBlur={(e) => savePatch({ lmstudio_base_url: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span>Model LM Studio</span>
                    <input
                      className="input"
                      placeholder="Auto hoặc nhập model ID…"
                      defaultValue={config.local_model}
                      onBlur={(e) => savePatch({ local_model: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span>Ollama Base URL</span>
                    <input
                      className="input"
                      defaultValue={config.ollama_base_url}
                      onBlur={(e) => savePatch({ ollama_base_url: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span>Model Ollama</span>
                    <input
                      className="input"
                      placeholder="Auto hoặc vd: qwen2.5:14b…"
                      defaultValue={config.ollama_model}
                      onBlur={(e) => savePatch({ ollama_model: e.target.value })}
                    />
                  </label>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.fallback_to_cloud}
                      onChange={(e) => savePatch({ fallback_to_cloud: e.target.checked })}
                    />
                    <span>Tự động chuyển sang Cloud API nếu mô hình Local bị lỗi hoặc quá tải</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.lifecycle?.unload_on_exit !== false}
                      onChange={(e) => savePatch({ lifecycle: { unload_on_exit: e.target.checked } })}
                    />
                    <span>Tự động gỡ mô hình Local khỏi VRAM khi đóng ứng dụng PhD Lab</span>
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ fontSize: 13 }}>Tự gỡ mô hình khỏi VRAM khi rảnh sau (phút):</span>
                    <input
                      type="number"
                      className="input"
                      style={{ width: 90 }}
                      min={1}
                      max={240}
                      defaultValue={config.lifecycle?.local_idle_min || 10}
                      onBlur={(e) =>
                        savePatch({ lifecycle: { local_idle_min: Number(e.target.value) || 10 } })
                      }
                    />
                  </div>
                </div>
              </section>

              {/* 1D. Capability-Aware Failover & Routing */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Định tuyến Thông minh & Chuỗi Dự phòng (Capability-Aware Routing)
                </h3>
                <label className="switch" style={{ marginBottom: 12 }}>
                  <input
                    type="checkbox"
                    checked={config.routing?.capability_aware !== false}
                    onChange={(e) => savePatch({ routing: { capability_aware: e.target.checked } })}
                  />
                  <span>
                    Bật Capability-Aware Failover (Giữ checkpoint và tự động chuyển đổi khi hết hạn mức/quota)
                  </span>
                </label>
              </section>
            </div>
          )}

          {/* ================================================================
              TAB 2: RESEARCH ENGINES (OpenScience · Feynman · OpenCode · CLI)
             ================================================================ */}
          {activeTab === 'engines' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {/* 2A. Engine Mode & Priority */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Chế độ Điều phối Research Engines (Feynman · OpenScience · OpenCode)
                </h3>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  PhD Lab quản lý trạng thái nghiên cứu tập trung và ủy quyền từng tác vụ có phạm vi kiểm soát cho các Runtime Engine chuyên biệt.
                </p>

                <div className="grid2">
                  <label className="field">
                    <span>Chế độ Research Engine (Engine Mode)</span>
                    <select
                      className="input"
                      value={config.research_providers?.engine_mode || 'auto'}
                      onChange={(e) =>
                        savePatch({ research_providers: { engine_mode: e.target.value } })
                      }
                    >
                      <option value="auto">Auto Smart Router (Tự động chọn theo năng lực)</option>
                      <option value="feynman">Feynman Only (Chuyên tổng quan & phản biện)</option>
                      <option value="openscience">OpenScience Only (Chuyên thực nghiệm khoa học)</option>
                      <option value="opencode">OpenCode Only (Chuyên lập trình & bản mẫu song song)</option>
                      <option value="collaborative">Collaborative (Phối hợp đa giai đoạn)</option>
                    </select>
                  </label>

                  <label className="field">
                    <span>Coding CLI mặc định cho lệnh /code</span>
                    <select
                      className="input"
                      value={config.research_providers?.coding_default || 'claude_code'}
                      onChange={(e) =>
                        savePatch({ research_providers: { coding_default: e.target.value } })
                      }
                    >
                      <option value="claude_code">Claude Code CLI</option>
                      <option value="codex">OpenAI Codex CLI</option>
                      <option value="gemini_cli">Google Gemini CLI</option>
                      <option value="antigravity">Google Antigravity CLI</option>
                      <option value="app">Mô hình nội bộ của ứng dụng</option>
                    </select>
                  </label>
                </div>
              </section>

              {/* 2B. OpenScience Runtime Adapter (:4096) */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h3 style={{ margin: 0, fontSize: 16 }}>
                    OpenScience Runtime Adapter (v6.0+ · Loopback :4096)
                  </h3>
                  <span className={`chip ${config.openscience?.enabled ? 'ok' : ''}`}>
                    {config.openscience?.enabled ? 'Đang bật' : 'Đang tắt'}
                  </span>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  Kết nối tới OpenScience Studio cục bộ để thực thi các nhiệm vụ nghiên cứu tự hành, kiểm định giả thuyết và thu thập artifacts.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.openscience?.enabled}
                      onChange={(e) => savePatch({ openscience: { enabled: e.target.checked } })}
                    />
                    <span>Bật OpenScience Runtime Adapter</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.openscience?.policy_confirmed}
                      onChange={(e) =>
                        savePatch({ openscience: { policy_confirmed: e.target.checked } })
                      }
                    />
                    <span>Tôi xác nhận đã xem xét quyền runtime và chính sách chia sẻ trace cục bộ</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.openscience?.allow_execution}
                      onChange={(e) =>
                        savePatch({ openscience: { allow_execution: e.target.checked } })
                      }
                    />
                    <span>Cho phép thực thi mã nguồn đề xuất trong Workspace cô lập</span>
                  </label>
                </div>

                <div className="grid2">
                  <label className="field">
                    <span>OpenScience Loopback URL</span>
                    <input
                      className="input"
                      defaultValue={config.openscience?.base_url || 'http://127.0.0.1:4096'}
                      onBlur={(e) => savePatch({ openscience: { base_url: e.target.value } })}
                    />
                  </label>
                  <label className="field">
                    <span>Deployment Token</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <input
                        type="password"
                        className="input"
                        placeholder={
                          config.openscience?.has_token
                            ? '•••••• (Đã lưu token)'
                            : 'Nhập OpenScience token…'
                        }
                        value={osciToken}
                        onChange={(e) => setOsciToken(e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn sm accent"
                        onClick={() => {
                          if (osciToken.trim()) {
                            savePatch({ openscience: { token: osciToken.trim() } });
                            setOsciToken('');
                          }
                        }}
                      >
                        Lưu Token
                      </button>
                    </div>
                  </label>
                  <label className="field">
                    <span>Giới hạn thời gian (giây)</span>
                    <input
                      type="number"
                      className="input"
                      defaultValue={config.openscience?.timeout_s || 600}
                      onBlur={(e) =>
                        savePatch({ openscience: { timeout_s: Number(e.target.value) || 600 } })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Ngân sách Artifact tối đa (MiB)</span>
                    <input
                      type="number"
                      className="input"
                      defaultValue={config.openscience?.max_artifact_mb || 64}
                      onBlur={(e) =>
                        savePatch({ openscience: { max_artifact_mb: Number(e.target.value) || 64 } })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Model Provider của OpenScience</span>
                    <input
                      className="input"
                      placeholder="vd: anthropic, openai…"
                      defaultValue={config.openscience?.model_provider || ''}
                      onBlur={(e) =>
                        savePatch({ openscience: { model_provider: e.target.value } })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Model ID của OpenScience</span>
                    <input
                      className="input"
                      placeholder="vd: claude-sonnet-4-20250514…"
                      defaultValue={config.openscience?.model_id || ''}
                      onBlur={(e) => savePatch({ openscience: { model_id: e.target.value } })}
                    />
                  </label>
                </div>
              </section>

              {/* 2C. OpenCode Parallel Core (v6.4.1 · Loopback :4097) */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h3 style={{ margin: 0, fontSize: 16 }}>
                    OpenCode Parallel Core Integration (v6.4.1 · Loopback :4097)
                  </h3>
                  <span className={`chip ${config.opencode?.enabled !== false ? 'ok' : ''}`}>
                    {config.opencode?.enabled !== false ? 'Đang bật' : 'Đang tắt'}
                  </span>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  Thực thi kỹ thuật phần mềm và bản mẫu song song trong không gian cô lập <code>&lt;topic&gt;/opencode_prj/</code> với luồng sự kiện SHA-256 deduplicated.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.opencode?.enabled !== false}
                      onChange={(e) => savePatch({ opencode: { enabled: e.target.checked } })}
                    />
                    <span>Bật OpenCode Parallel Core Runtime</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.opencode?.allow_metered_api}
                      onChange={(e) =>
                        savePatch({ opencode: { allow_metered_api: e.target.checked } })
                      }
                    />
                    <span>Cho phép dùng Metered API (vẫn yêu cầu cổng phê duyệt từng phiên)</span>
                  </label>
                </div>

                <div className="grid2">
                  <label className="field">
                    <span>OpenCode Server URL (Loopback)</span>
                    <input
                      className="input"
                      defaultValue={config.opencode?.base_url || 'http://127.0.0.1:4097'}
                      onBlur={(e) => savePatch({ opencode: { base_url: e.target.value } })}
                    />
                  </label>
                  <label className="field">
                    <span>Timeout mỗi phiên OpenCode (giây)</span>
                    <input
                      type="number"
                      className="input"
                      defaultValue={config.opencode?.timeout_s || 600}
                      onBlur={(e) =>
                        savePatch({ opencode: { timeout_s: Number(e.target.value) || 600 } })
                      }
                    />
                  </label>
                </div>
              </section>

              {/* 2D. Feynman & Live CLI Providers */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <h3 style={{ margin: 0, fontSize: 16 }}>
                    Feynman CLI & Trạng thái Các Research Providers
                  </h3>
                  <button type="button" className="btn sm ghost" onClick={() => refetchProviders()}>
                    <RefreshCw size={13} /> Làm mới trạng thái CLI
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.research_providers?.feynman_enabled !== false}
                      onChange={(e) =>
                        savePatch({ research_providers: { feynman_enabled: e.target.checked } })
                      }
                    />
                    <span>Dùng Feynman cho /lit, /deepresearch, /compare và /review</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.research_providers?.feynman_share_app_key}
                      onChange={(e) =>
                        savePatch({
                          research_providers: { feynman_share_app_key: e.target.checked },
                        })
                      }
                    />
                    <span>Cho phép Feynman dùng chung khóa Anthropic/OpenAI của ứng dụng</span>
                  </label>
                </div>

                <div className="list">
                  {(researchProvidersData?.providers || []).map((p: any) => (
                    <div
                      key={p.id}
                      className="li"
                      style={{
                        border: '1px solid var(--line)',
                        borderRadius: 8,
                        marginBottom: 6,
                        background: 'var(--bg)',
                      }}
                    >
                      <span
                        className={`dot ${
                          p.ready ? 'ok' : ['NOT_CONFIGURED', 'STOPPED'].includes(p.state) ? 'warn' : ''
                        }`}
                      />
                      <div className="m">
                        <div className="t" style={{ fontWeight: 600 }}>
                          {p.label}{' '}
                          <span className="chip" style={{ marginLeft: 6 }}>
                            {p.category}
                          </span>
                        </div>
                        <div className="s" style={{ whiteSpace: 'normal' }}>
                          {p.state} — {p.detail}
                        </div>
                      </div>
                      {!p.ready &&
                        ['feynman', 'claude_code', 'codex', 'gemini_cli', 'antigravity'].includes(
                          p.id
                        ) && (
                          <button
                            type="button"
                            className="btn sm"
                            onClick={async () => {
                              await api.post(`/api/providers/${p.id}/connect`, {});
                              notify(`Đã mở cửa sổ đăng nhập cho ${p.label}`);
                            }}
                          >
                            Đăng nhập CLI
                          </button>
                        )}
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {/* ================================================================
              TAB 3: SEARCH & VENUE RANKING (CORE / SCIMAGO)
             ================================================================ */}
          {activeTab === 'search' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Tìm kiếm Bài báo Khoa học & Web (OpenAlex · Semantic Scholar · ArXiv)
                </h3>
                <div className="grid2">
                  <label className="field">
                    <span>Công cụ tìm kiếm Web</span>
                    <select
                      className="input"
                      value={config.search?.web_engine || 'duckduckgo'}
                      onChange={(e) => savePatch({ search: { web_engine: e.target.value } })}
                    >
                      <option value="duckduckgo">DuckDuckGo (Miễn phí, không cần key)</option>
                      <option value="tavily">Tavily AI Search</option>
                      <option value="brave">Brave Search API</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Số kết quả mỗi lần truy vấn (1–30)</span>
                    <input
                      type="number"
                      className="input"
                      min={1}
                      max={30}
                      defaultValue={config.search?.n_results || 8}
                      onBlur={(e) =>
                        savePatch({ search: { n_results: Number(e.target.value) || 8 } })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Email cho OpenAlex Polite Pool (tăng tốc độ truy vấn)</span>
                    <input
                      type="email"
                      className="input"
                      placeholder="researcher@university.edu"
                      defaultValue={config.search?.mailto || ''}
                      onBlur={(e) => savePatch({ search: { mailto: e.target.value } })}
                    />
                  </label>
                </div>

                <label className="switch" style={{ marginBottom: 16 }}>
                  <input
                    type="checkbox"
                    checked={config.search?.read_pages !== false}
                    onChange={(e) => savePatch({ search: { read_pages: e.target.checked } })}
                  />
                  <span>Đọc toàn văn nội dung trang web hàng đầu khi tìm kiếm</span>
                </label>

                <h4 style={{ margin: '12px 0 8px', fontSize: 14 }}>
                  Khóa API Cơ sở dữ liệu Học thuật & Tìm kiếm (Tuỳ chọn)
                </h4>
                <div className="grid2">
                  {[
                    ['s2_key', 'Semantic Scholar API Key'],
                    ['openalex_key', 'OpenAlex API Key'],
                    ['ieee_key', 'IEEE Xplore API Key'],
                    ['serpapi_key', 'SerpAPI Key (Google Scholar)'],
                    ['tavily_key', 'Tavily Search API Key'],
                    ['brave_key', 'Brave Search API Key'],
                  ].map(([k, label]) => {
                    const hasKey = !!(config.search as any)?.['has_' + k];
                    return (
                      <label key={k} className="field">
                        <span>{label}</span>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <input
                            type="password"
                            className="input"
                            placeholder={hasKey ? '•••••• (Đã lưu key)' : 'Chưa cấu hình'}
                            value={searchKeyInputs[k] || ''}
                            onChange={(e) =>
                              setSearchKeyInputs((prev) => ({ ...prev, [k]: e.target.value }))
                            }
                          />
                          <button
                            type="button"
                            className="btn sm"
                            onClick={() => {
                              if (searchKeyInputs[k]?.trim()) {
                                savePatch({ search: { [k]: searchKeyInputs[k].trim() } });
                                setSearchKeyInputs((prev) => ({ ...prev, [k]: '' }));
                              }
                            }}
                          >
                            Lưu
                          </button>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </section>

              {/* Venue Ranking (CORE & SCImago) */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Award size={18} color="var(--accent)" />
                    <h3 style={{ margin: 0, fontSize: 16 }}>
                      Xếp hạng Hội nghị (CORE A*/A/B/C) & Tạp chí (SCImago Q1–Q4)
                    </h3>
                  </div>
                  <button
                    type="button"
                    className="btn sm ghost"
                    onClick={async () => {
                      await api.get('/api/ranking?refresh=1');
                      refetchRanking();
                      notify('Đã làm mới cơ sở dữ liệu xếp hạng học thuật!');
                    }}
                  >
                    <RefreshCw size={13} /> Cập nhật CORE ngay
                  </button>
                </div>

                <div className="grid2" style={{ marginTop: 10 }}>
                  <label className="field">
                    <span>Phiên bản xếp hạng CORE</span>
                    <select
                      className="input"
                      value={config.ranking?.core_source || 'ICORE2026'}
                      onChange={(e) => savePatch({ ranking: { core_source: e.target.value } })}
                    >
                      <option value="ICORE2026">ICORE 2026 (Mới nhất)</option>
                      <option value="CORE2023">CORE 2023</option>
                      <option value="CORE2021">CORE 2021</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Chu kỳ tự động làm mới (ngày)</span>
                    <input
                      type="number"
                      className="input"
                      defaultValue={config.ranking?.refresh_days || 30}
                      onBlur={(e) =>
                        savePatch({ ranking: { refresh_days: Number(e.target.value) || 30 } })
                      }
                    />
                  </label>
                </div>

                {rankingStatus && (
                  <div
                    style={{
                      background: 'var(--code-bg)',
                      padding: 12,
                      borderRadius: 8,
                      fontSize: 13,
                      display: 'grid',
                      gap: 6,
                      marginBottom: 14,
                    }}
                  >
                    <div>
                      <b>Hội nghị (CORE):</b>{' '}
                      {rankingStatus.conferences?.records
                        ? `${rankingStatus.conferences.records} hội nghị (${rankingStatus.conferences.source})`
                        : 'Chưa tải dữ liệu'}
                    </div>
                    <div>
                      <b>Tạp chí (SCImago):</b>{' '}
                      {rankingStatus.journals?.records
                        ? `${rankingStatus.journals.records} tạp chí (Năm ${rankingStatus.journals.year})`
                        : 'Chưa nhập CSV SCImago'}
                    </div>
                  </div>
                )}

                {/* Live Venue Lookup Tool */}
                <div style={{ borderTop: '1px solid var(--line)', paddingTop: 12 }}>
                  <b style={{ fontSize: 13 }}>Tra cứu nhanh hạng Hội nghị / Tạp chí:</b>
                  <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                    <input
                      className="input"
                      placeholder="Nhập tên hội nghị hoặc tạp chí (vd: NeurIPS, CVPR, IEEE TPAMI, Nature)…"
                      value={venueLookupQuery}
                      onChange={(e) => setVenueLookupQuery(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn sm accent"
                      onClick={async () => {
                        if (!venueLookupQuery.trim()) return;
                        const r = await api.get(
                          `/api/ranking/lookup?venue=${encodeURIComponent(venueLookupQuery.trim())}`
                        );
                        setVenueLookupResult(r);
                      }}
                    >
                      Tra cứu
                    </button>
                  </div>
                  {venueLookupResult && (
                    <pre
                      className="preview-box mono"
                      style={{ marginTop: 8, fontSize: 12, maxHeight: 140 }}
                    >
                      {JSON.stringify(venueLookupResult, null, 2)}
                    </pre>
                  )}
                </div>
              </section>
            </div>
          )}

          {/* ================================================================
              TAB 4: EXPERIMENTS & HARDWARE
             ================================================================ */}
          {activeTab === 'hardware' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Tiến trình Chạy nền (Background Runs) & Cổng Phê duyệt Rủi ro
                </h3>
                <div className="grid2">
                  <label className="field">
                    <span>Mức độ tự chạy không cần hỏi trước</span>
                    <select
                      className="input"
                      value={config.runs?.auto_approve_risk ?? 1}
                      onChange={(e) =>
                        savePatch({ runs: { auto_approve_risk: Number(e.target.value) } })
                      }
                    >
                      <option value={0}>Mức 0 — Chỉ tác vụ đọc (Tìm tài liệu, Phản biện)</option>
                      <option value={1}>Mức 1 — Cho phép ghi báo cáo/PDF trong dự án</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Ngân sách thời gian mỗi Run (phút)</span>
                    <input
                      type="number"
                      className="input"
                      defaultValue={config.runs?.max_minutes || 120}
                      onBlur={(e) =>
                        savePatch({ runs: { max_minutes: Number(e.target.value) || 120 } })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Số lần tự phục hồi khi lỗi (vd: CUDA OOM → giảm batch)</span>
                    <input
                      type="number"
                      className="input"
                      min={0}
                      max={5}
                      defaultValue={config.runs?.max_retries ?? 1}
                      onBlur={(e) =>
                        savePatch({ runs: { max_retries: Number(e.target.value) || 0 } })
                      }
                    />
                  </label>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.runs?.auto_recover !== false}
                      onChange={(e) => savePatch({ runs: { auto_recover: e.target.checked } })}
                    />
                    <span>Tự động phục hồi lỗi có phương án sửa an toàn</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.runs?.web_search !== false}
                      onChange={(e) => savePatch({ runs: { web_search: e.target.checked } })}
                    />
                    <span>Truy vấn bài báo thực tế (OpenAlex, Semantic Scholar, ArXiv) trước khi tổng hợp /lit</span>
                  </label>
                </div>
              </section>

              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Bộ điều phối Tài nguyên Phần cứng (Hardware Resource Governor)
                </h3>
                <div className="grid2">
                  <label className="field">
                    <span>Số Job CPU đồng thời tối đa</span>
                    <input
                      type="number"
                      className="input"
                      min={1}
                      max={4}
                      defaultValue={config.runs?.slot_cpu || 1}
                      onBlur={(e) => savePatch({ runs: { slot_cpu: Number(e.target.value) || 1 } })}
                    />
                  </label>
                  <label className="field">
                    <span>Số CLI Provider chạy đồng thời</span>
                    <input
                      type="number"
                      className="input"
                      min={1}
                      max={4}
                      defaultValue={config.runs?.slot_cli || 2}
                      onBlur={(e) => savePatch({ runs: { slot_cli: Number(e.target.value) || 2 } })}
                    />
                  </label>
                  <label className="field">
                    <span>Số luồng gọi Cloud API đồng thời</span>
                    <input
                      type="number"
                      className="input"
                      min={1}
                      max={8}
                      defaultValue={config.runs?.slot_cloud || 3}
                      onBlur={(e) =>
                        savePatch({ runs: { slot_cloud: Number(e.target.value) || 3 } })
                      }
                    />
                  </label>
                  <label className="field">
                    <span>Giới hạn nhiệt độ GPU tối đa (°C)</span>
                    <input
                      type="number"
                      className="input"
                      min={60}
                      max={95}
                      defaultValue={config.resources?.gpu_temp_limit_c || 83}
                      onBlur={(e) =>
                        savePatch({
                          resources: { gpu_temp_limit_c: Number(e.target.value) || 83 },
                        })
                      }
                    />
                  </label>
                </div>

                <label className="switch" style={{ marginTop: 6 }}>
                  <input
                    type="checkbox"
                    checked={!!config.resources?.auto_unload_for_gpu}
                    onChange={(e) =>
                      savePatch({ resources: { auto_unload_for_gpu: e.target.checked } })
                    }
                  />
                  <span>Tự động giải phóng mô hình Local đang rảnh khỏi VRAM khi cần GPU chạy thí nghiệm</span>
                </label>
              </section>

              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  ClearML Tracking, VS Code & Research OS Mode
                </h3>
                <div className="grid2">
                  <label className="field">
                    <span>ClearML Web Server URL</span>
                    <input
                      className="input"
                      defaultValue={config.clearml?.web_url || 'http://localhost:8080'}
                      onBlur={(e) => savePatch({ clearml: { web_url: e.target.value } })}
                    />
                  </label>
                  <label className="field">
                    <span>Đường dẫn thực thi VS Code (để trống = tự động tìm)</span>
                    <input
                      className="input"
                      placeholder="code hoặc C:\...\Code.exe"
                      defaultValue={config.workspace?.vscode_path || ''}
                      onBlur={(e) => savePatch({ workspace: { vscode_path: e.target.value } })}
                    />
                  </label>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.clearml?.server_enabled}
                      onChange={(e) =>
                        savePatch({ clearml: { server_enabled: e.target.checked } })
                      }
                    />
                    <span>Đồng bộ trực tuyến với ClearML Server</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.research_os?.enabled}
                      onChange={(e) =>
                        savePatch({ research_os: { enabled: e.target.checked } })
                      }
                    />
                    <span>Bật chế độ Autonomous Research OS (Multi-Agent Teams & Workstreams)</span>
                  </label>
                </div>
              </section>
            </div>
          )}

          {/* ================================================================
              TAB 5: MEMORY & CONTEXT
             ================================================================ */}
          {activeTab === 'memory' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Bộ nhớ Ngữ cảnh Dự án (Context Memory v2) & AI Workspace
                </h3>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  Ngữ cảnh dự án (đề cương 5 cấp, quyết định, giả thuyết, kết quả thí nghiệm, tài liệu SKB) được biên dịch tự động cho mỗi lượt hội thoại.
                </p>

                <div className="grid2">
                  <label className="field">
                    <span>Chế độ Ghi nhớ Tri thức (Memory Mode)</span>
                    <select
                      className="input"
                      value={config.aiws?.memory_mode || 'suggest'}
                      onChange={(e) => savePatch({ aiws: { memory_mode: e.target.value } })}
                    >
                      <option value="suggest">Đề xuất — Hiển thị thẻ để bạn Chấp nhận / Bỏ qua (Khuyên dùng)</option>
                      <option value="manual">Thủ công — Chỉ lưu khi bạn bấm Ghi nhớ trên tin nhắn</option>
                      <option value="auto">Tự động có giới hạn (Chỉ tự lưu câu hỏi mở)</option>
                      <option value="off">Tắt ghi nhớ tự động</option>
                    </select>
                  </label>

                  <label className="field">
                    <span>Chế độ Vận hành AI (Operating Mode)</span>
                    <select
                      className="input"
                      value={config.aiws?.operating_mode || 'automation'}
                      onChange={(e) => savePatch({ aiws: { operating_mode: e.target.value } })}
                    >
                      <option value="automation">Tự động — AI tự dùng công cụ chỉ-đọc, thay đổi chờ duyệt</option>
                      <option value="manual">Thủ công — Kiểm duyệt gói ngữ cảnh trước mỗi lượt gửi</option>
                    </select>
                  </label>

                  <label className="field">
                    <span>Ngân sách Ngữ cảnh mỗi lượt (Tokens)</span>
                    <input
                      type="number"
                      className="input"
                      step={500}
                      min={500}
                      max={60000}
                      defaultValue={config.aiws?.context_budget_tokens || 6000}
                      onBlur={(e) =>
                        savePatch({
                          aiws: { context_budget_tokens: Number(e.target.value) || 6000 },
                        })
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Thời gian tối đa một lượt trả lời (giây)</span>
                    <input
                      type="number"
                      className="input"
                      min={30}
                      max={7200}
                      defaultValue={config.aiws?.max_turn_s || 900}
                      onBlur={(e) =>
                        savePatch({ aiws: { max_turn_s: Number(e.target.value) || 900 } })
                      }
                    />
                  </label>
                </div>
              </section>
            </div>
          )}

          {/* ================================================================
              TAB 6: MCP & CLI SECURITY
             ================================================================ */}
          {activeTab === 'mcp' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Plug size={18} color="var(--accent)" />
                  <h3 style={{ margin: 0, fontSize: 16 }}>
                    Model Context Protocol (MCP) Server & Context Firewall
                  </h3>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  PhD Lab cung cấp MCP Server cục bộ tại <code>{window.location.origin}/mcp</code> cho phép các CLI bên ngoài truy cập công cụ nghiên cứu có kiểm soát.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.mcp?.expose_research !== false}
                      onChange={(e) => savePatch({ mcp: { expose_research: e.target.checked } })}
                    />
                    <span>Cung cấp bộ công cụ đọc dữ liệu nghiên cứu qua MCP (Expose Research Tools)</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.mcp?.allow_writes !== false}
                      onChange={(e) => savePatch({ mcp: { allow_writes: e.target.checked } })}
                    />
                    <span>Cho phép MCP tạo đề xuất ghi (Write Proposals — luôn cần nhà nghiên cứu phê duyệt)</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.gateway?.block_source_code !== false}
                      onChange={(e) =>
                        savePatch({ gateway: { block_source_code: e.target.checked } })
                      }
                    />
                    <span>Context Firewall: Chặn tự động đính kèm mã nguồn nhạy cảm ra ngoài</span>
                  </label>
                </div>

                <h4 style={{ margin: '16px 0 8px', fontSize: 14 }}>MCP Inference Agent</h4>
                <label className="switch" style={{ marginBottom: 10 }}>
                  <input
                    type="checkbox"
                    checked={!!config.mcp_agent?.enabled}
                    onChange={(e) => savePatch({ mcp_agent: { enabled: e.target.checked } })}
                  />
                  <span>Bật MCP Inference Agent</span>
                </label>
                <div className="grid2">
                  <label className="field">
                    <span>MCP Inference Endpoint URL</span>
                    <input
                      className="input"
                      defaultValue={config.mcp_agent?.url || 'http://127.0.0.1:8766/mcp'}
                      onBlur={(e) => savePatch({ mcp_agent: { url: e.target.value } })}
                    />
                  </label>
                  <label className="field">
                    <span>Tên công cụ suy luận (Tool Name)</span>
                    <input
                      className="input"
                      defaultValue={config.mcp_agent?.tool || 'research'}
                      onBlur={(e) => savePatch({ mcp_agent: { tool: e.target.value } })}
                    />
                  </label>
                </div>
              </section>
            </div>
          )}

          {/* ================================================================
              TAB 7: SKILLS (/) & GITHUB PLUGINS
             ================================================================ */}
          {activeTab === 'skills' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {/* 7A. GitHub Plugins */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Cài đặt Plugin Kỹ năng từ GitHub (Agent Skills & AI-Scientist-v2)
                </h3>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 12px' }}>
                  Cài đặt kỹ năng từ bất kỳ repository GitHub nào chứa <code>SKILL.md</code> hoặc thư mục <code>skills/</code>.
                </p>

                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                  <input
                    className="input"
                    placeholder="https://github.com/owner/repo (hoặc nhánh/thư mục con)…"
                    value={pluginUrl}
                    onChange={(e) => setPluginUrl(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn accent"
                    disabled={installingPlugin || !pluginUrl.trim()}
                    onClick={async () => {
                      setInstallingPlugin(true);
                      try {
                        await api.post('/api/plugins', { url: pluginUrl.trim(), enable: true });
                        setPluginUrl('');
                        refetchPlugins();
                        refetchSkills();
                        notify('Đã cài đặt Plugin từ GitHub thành công!');
                      } catch (err) {
                        notify(`Lỗi cài plugin: ${(err as Error).message}`, 'err');
                      } finally {
                        setInstallingPlugin(false);
                      }
                    }}
                  >
                    <Plus size={15} /> {installingPlugin ? 'Đang tải…' : 'Cài Plugin'}
                  </button>
                </div>

                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
                  <span className="muted" style={{ fontSize: 12 }}>Gợi ý cài nhanh:</span>
                  {[
                    ['SakanaAI/AI-Scientist-v2', 'https://github.com/SakanaAI/AI-Scientist-v2'],
                    ['K-Dense Scientific Skills', 'https://github.com/K-Dense-AI/scientific-agent-skills'],
                    ['Anthropic Skills', 'https://github.com/anthropics/skills'],
                  ].map(([label, u]) => (
                    <button
                      key={u}
                      type="button"
                      className="chip"
                      style={{ cursor: 'pointer' }}
                      onClick={() => setPluginUrl(u)}
                    >
                      + {label}
                    </button>
                  ))}
                </div>

                {/* Installed plugins */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {(pluginsData?.plugins || []).map((p: any) => (
                    <div
                      key={p.id}
                      style={{
                        border: '1px solid var(--line)',
                        borderRadius: 10,
                        padding: 12,
                        background: 'var(--bg)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <b>
                          {p.owner}/{p.repo}
                          {p.subdir ? `/${p.subdir}` : ''}
                        </b>
                        <div className="muted" style={{ fontSize: 12 }}>
                          {p.ref} · commit {String(p.commit || '').slice(0, 8)} ·{' '}
                          {(p.skills || []).length} kỹ năng
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <label className="switch" style={{ fontSize: 12.5 }}>
                          <input
                            type="checkbox"
                            checked={!!p.enabled}
                            onChange={async (e) => {
                              await api.put(`/api/plugins/${p.id}`, { enabled: e.target.checked });
                              refetchPlugins();
                              refetchSkills();
                            }}
                          />
                          <span>Bật</span>
                        </label>
                        <button
                          type="button"
                          className="btn sm ghost"
                          onClick={async () => {
                            await api.post(`/api/plugins/${p.id}/update`, {});
                            refetchPlugins();
                            notify(`Đã cập nhật ${p.id}`);
                          }}
                        >
                          <RefreshCw size={13} />
                        </button>
                        <button
                          type="button"
                          className="btn sm ghost danger"
                          onClick={async () => {
                            await api.delete(`/api/plugins/${p.id}`);
                            refetchPlugins();
                            refetchSkills();
                            notify(`Đã gỡ plugin ${p.id}`);
                          }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* 7B. Built-in & Custom /skills */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Danh mục Kỹ năng Lệnh <code>/</code> ({skillsData?.skills?.length || 0} kỹ năng)
                </h3>
                <div className="table-scroll" style={{ maxHeight: 320, overflowY: 'auto' }}>
                  <table className="grid">
                    <thead>
                      <tr>
                        <th>Lệnh</th>
                        <th>Mô tả</th>
                        <th>Chế độ & Nguồn</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {(skillsData?.skills || []).map((s) => (
                        <tr key={s.name}>
                          <td className="mono" style={{ fontWeight: 600, color: 'var(--accent-2)' }}>
                            /{s.name}
                          </td>
                          <td>
                            <b>{s.title}</b>
                            <div className="muted" style={{ fontSize: 12 }}>{s.description}</div>
                          </td>
                          <td>
                            <span className="chip">{s.mode === 'run' ? 'Chạy nền' : 'Chat'}</span>{' '}
                            <span className="chip">{s.origin || 'builtin'}</span>
                          </td>
                          <td>
                            {['user', 'project'].includes(s.origin || '') && (
                              <button
                                type="button"
                                className="btn sm ghost danger"
                                onClick={async () => {
                                  await api.delete(`/api/skills/${s.name}`);
                                  refetchSkills();
                                  notify(`Đã xoá kỹ năng /${s.name}`);
                                }}
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <h4 style={{ margin: '18px 0 8px', fontSize: 14 }}>Tạo hoặc Cập nhật Kỹ năng Tùy chỉnh</h4>
                <textarea
                  className="input mono"
                  rows={8}
                  value={newSkillText}
                  onChange={(e) => setNewSkillText(e.target.value)}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                  <select
                    className="input"
                    style={{ width: 220 }}
                    value={newSkillScope}
                    onChange={(e) => setNewSkillScope(e.target.value as 'project' | 'user')}
                  >
                    <option value="project">Lưu cho Dự án hiện tại</option>
                    <option value="user">Lưu cho Mọi dự án (Global)</option>
                  </select>
                  <button
                    type="button"
                    className="btn accent"
                    onClick={async () => {
                      try {
                        await api.post('/api/skills', { text: newSkillText, scope: newSkillScope });
                        refetchSkills();
                        notify('Đã lưu kỹ năng thành công!');
                      } catch (err) {
                        notify(`Lỗi lưu kỹ năng: ${(err as Error).message}`, 'err');
                      }
                    }}
                  >
                    Lưu Kỹ năng
                  </button>
                </div>
              </section>
            </div>
          )}

          {/* ================================================================
              TAB 8: APPEARANCE & LANGUAGE
             ================================================================ */}
          {activeTab === 'look' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  Chủ đề Giao diện (Academic & OpenScience Studio Themes)
                </h3>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  Chọn bảng màu phù hợp với không gian làm việc của bạn. Hỗ trợ đầy đủ cả chế độ Sáng học thuật lẫn chế độ Tối OpenScience Studio.
                </p>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
                    gap: 12,
                  }}
                >
                  {BUILTIN_THEMES.map((t) => {
                    const isSelected = selectedTheme === t.id;
                    return (
                      <div
                        key={t.id}
                        onClick={() => {
                          setSelectedTheme(t.id);
                          applyThemeById(t.id);
                          notify(`Đã áp dụng chủ đề: ${t.name}`);
                        }}
                        style={{
                          border: isSelected ? '2px solid var(--accent)' : '1px solid var(--line)',
                          borderRadius: 12,
                          padding: 12,
                          background: 'var(--panel)',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 8,
                        }}
                      >
                        <div
                          style={{
                            height: 54,
                            borderRadius: 8,
                            background: t.swatch.bg,
                            color: t.swatch.ink,
                            border: `1px solid ${t.swatch.accent}`,
                            borderLeftWidth: 5,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '0 12px',
                            fontWeight: 700,
                            fontSize: 18,
                          }}
                        >
                          <span>Aa</span>
                          <span
                            style={{
                              width: 16,
                              height: 16,
                              borderRadius: '50%',
                              background: t.swatch.accent,
                            }}
                          />
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <b style={{ fontSize: 13 }}>{t.name}</b>
                          {isSelected && <Check size={15} color="var(--accent)" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>
                  Kiểu chữ Học thuật & Ngôn ngữ Hệ thống
                </h3>
                <div className="grid2">
                  <label className="field">
                    <span>Font chữ hiển thị câu trả lời & bài báo</span>
                    <select
                      className="input"
                      value={config.ui?.prose_font || 'sans'}
                      onChange={(e) => {
                        const font = e.target.value;
                        if (font === 'serif') {
                          document.documentElement.setAttribute('data-font', 'serif');
                        } else {
                          document.documentElement.removeAttribute('data-font');
                        }
                        savePatch({ ui: { prose_font: font } });
                      }}
                    >
                      <option value="sans">Sans-serif (Segoe UI / Noto Sans — Hiện đại, rõ nét)</option>
                      <option value="serif">Serif (Cambria / Source Serif — Phong cách Tạp chí Khoa học)</option>
                    </select>
                  </label>

                  <label className="field">
                    <span>Ngôn ngữ Giao diện & Phản hồi mặc định của AI</span>
                    <select
                      className="input"
                      value={config.ui?.language || 'vi'}
                      onChange={(e) => savePatch({ ui: { language: e.target.value } })}
                    >
                      <option value="vi">Tiếng Việt (Vietnamese)</option>
                      <option value="en">English (Academic International)</option>
                    </select>
                  </label>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.ui?.paper_explorer_v2 !== false}
                      onChange={(e) => savePatch({ ui: { paper_explorer_v2: e.target.checked } })}
                    />
                    <span>Bật Paper Explorer v2 & Bộ lọc Hạng Tạp chí Q1–Q4</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.ui?.contextual_actions !== false}
                      onChange={(e) => savePatch({ ui: { contextual_actions: e.target.checked } })}
                    />
                    <span>Hiển thị thanh công cụ ngữ cảnh nhanh trên Header</span>
                  </label>
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
