import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
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
  Globe,
  Bot,
  Type,
  BookOpen,
  CheckCircle2,
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

export function applyFontById(id: string) {
  const root = document.documentElement;
  if (!id || id === 'sans') {
    root.removeAttribute('data-font');
  } else {
    root.setAttribute('data-font', id);
  }
  try {
    if (!id || id === 'sans') localStorage.removeItem('pl.font');
    else localStorage.setItem('pl.font', id);
  } catch {
    // ignore storage errors
  }
}

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

// Tab definitions are generated dynamically inside SettingsModal using useI18n()

export const SettingsModal: React.FC = () => {
  const queryClient = useQueryClient();
  const { settingsTab, openSettings, setMainView, language, setLanguage, uiScale, setUiScale } = useUIStore();
  const { t } = useI18n();

  const tabs = [
    {
      id: 'models',
      label: t('Mô hình & Tác nhân AI', 'Models & AI Agents'),
      icon: Cpu,
      desc: t('Khóa API đám mây, 4 Tác nhân, VRAM cục bộ & Điều phối', 'Cloud API keys, 4 Agents, Local VRAM & Routing'),
    },
    {
      id: 'engines',
      label: t('Công cụ Nghiên cứu', 'Research Engines'),
      icon: Terminal,
      desc: t('OpenScience, Feynman, OpenCode & Giao diện dòng lệnh', 'OpenScience, Feynman, OpenCode & CLI'),
    },
    {
      id: 'search',
      label: t('Tìm kiếm & Xếp hạng', 'Search & Ranking'),
      icon: Search,
      desc: t('OpenAlex, Semantic Scholar, CORE & SCImago', 'OpenAlex, Semantic Scholar, CORE & SCImago'),
    },
    {
      id: 'hardware',
      label: t('Thí nghiệm & Phần cứng', 'Experiments & Hardware'),
      icon: HardDrive,
      desc: t('Bảo vệ GPU, Chạy ngầm, ClearML & VS Code', 'GPU Guard, Background Runs, ClearML & VS Code'),
    },
    {
      id: 'memory',
      label: t('Bộ nhớ & Ngữ cảnh', 'Memory & Context'),
      icon: Brain,
      desc: t('Bộ nhớ Ngữ cảnh v2, Định mức Token & AIWS', 'Context Memory v2, Token Budget & AIWS'),
    },
    {
      id: 'mcp',
      label: t('MCP & Tường lửa Bảo mật', 'MCP & Security Firewall'),
      icon: Shield,
      desc: t('Máy chủ MCP, Tác nhân Suy luận & Tường lửa Ngữ cảnh', 'MCP Server, Inference Agent & Context Firewall'),
    },
    {
      id: 'skills',
      label: t('Kỹ năng & Tiện ích mở rộng', 'Skills & Plugins'),
      icon: Sparkles,
      desc: t('Lệnh kỹ năng tùy chỉnh & Tiện ích mở rộng GitHub', 'Custom Skills & GitHub Plugins'),
    },
    {
      id: 'look',
      label: t('Giao diện & Ngôn ngữ', 'Appearance & Language'),
      icon: Palette,
      desc: t('Chủ đề màu sắc, Font chữ học thuật & Ngôn ngữ hiển thị', 'Color Themes, Academic Typography & Language'),
    },
  ];
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
  const [pendingCloudPreconnect, setPendingCloudPreconnect] = useState<boolean | null>(null);

  // Save config mutation (POST /api/config — exact backend route)
  const saveConfigMutation = useMutation({
    mutationFn: (patch: Record<string, unknown>) => api.post<AppConfig>('/api/config', patch),
    onSuccess: (saved) => {
      queryClient.setQueryData(['config'], saved);
      queryClient.invalidateQueries({ queryKey: ['config'] });
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['model-connections'] });
      notify(t('Đã lưu cấu hình thành công!', 'Configuration saved successfully!'));
    },
    onError: (err: Error) => {
      notify(t('Lỗi lưu cấu hình: ', 'Failed to save configuration: ') + err.message, 'err');
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

  const { data: connectionData } = useQuery<{ connections: Array<{ provider: string; model: string; state: string }> }>({
    queryKey: ['model-connections'],
    queryFn: () => api.get('/api/models/connections'),
    enabled: activeTab === 'models',
    refetchInterval: activeTab === 'models' ? 5000 : false,
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

  const { data: pluginsData, refetch: refetchPlugins } = useQuery<{ plugins: any[]; optional_plugins?: any[]; root: string }>({
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
  const [syncingProvider, setSyncingProvider] = useState<string | null>(null);
  const [syncResults, setSyncResults] = useState<Record<string, { at: string; changed: number; observed: number }>>({});

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
        <span>{t('Đang tải cấu hình hệ thống PhD Research Lab…', 'Loading PhD Research Lab system configuration…')}</span>
      </div>
    );
  }

  const providerSpecs = config.provider_specs || {};
  const mainProviders = ['anthropic', 'openai', 'gemini', 'deepseek', 'openrouter', 'groq', config.default_cloud];
  const visibleTabs = tabs.filter(
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
      notify(t(`Kết nối ${pid} (${res.model}) thành công! Phản hồi: "${res.reply}"`, `Connected to ${pid} (${res.model}) successfully! Reply: "${res.reply}"`));
    } catch (err) {
      notify(t('Lỗi kết nối: ', 'Connection error: ') + `${pid}: ${(err as Error).message}`, 'err');
    } finally {
      setTestingProvider(null);
    }
  };

  // List models from provider API
  const handleFetchModels = async (pid: string) => {
    try {
      const res = await api.post<{ models: string[] }>(pid === 'codex' ? '/api/models/cli/codex' : '/api/models/list', { provider: pid });
      setFetchedProviderModels((prev) => ({ ...prev, [pid]: res.models || [] }));
      notify(t(`Đã tải ${(res.models || []).length} model từ ${pid}`, `Loaded ${(res.models || []).length} models from ${pid}`));
    } catch (err) {
      notify(t('Không tải được danh sách model: ', 'Failed to load model list: ') + `${pid}: ${(err as Error).message}`, 'err');
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

  const handleLaunchProvider = async (pid: string, label: string) => {
    try {
      await api.post(`/api/providers/${pid}/launch`, {});
      notify(t('Đã mở điều hướng tới ', 'Opened navigation to ') + label);
    } catch (err: any) {
      notify(t('Lỗi mở ứng dụng: ', 'Failed to launch app: ') + (err?.message || 'Unknown error'), 'err');
    }
  };

  const handleSyncProvider = async (pid: string, label: string) => {
    setSyncingProvider(pid);
    try {
      const res = await api.post<{ ok: boolean; total_changed: number; total_observed: number }>(`/api/providers/${pid}/sync`, {});
      setSyncResults((prev) => ({
        ...prev,
        [pid]: {
          at: new Date().toLocaleTimeString(),
          changed: res.total_changed || 0,
          observed: res.total_observed || 0,
        },
      }));
      notify(
        t('Đồng bộ thành công từ ', 'Synchronized successfully from ') +
          label +
          ': ' +
          (res.total_changed || 0) +
          t(' tệp mới/cập nhật', ' new/updated files')
      );
    } catch (err: any) {
      notify(t('Lỗi đồng bộ dữ liệu: ', 'Failed to sync data: ') + (err?.message || 'Unknown error'), 'err');
    } finally {
      setSyncingProvider(null);
    }
  };

  // Engine options for the 4 agents (includes Subscriptions, CLIs, Local, and all 17 Cloud Providers)
  const agentEngineOptions = [
    ['auto', t('Tự động điều phối thông minh', 'Auto (Smart Router: Local → Cloud)')],
    ['codex', t('Gói trả phí ChatGPT dòng lệnh', 'ChatGPT Subscription (Codex CLI)')],
    ['claude_code', t('Gói trả phí Claude dòng lệnh', 'Claude Subscription (Claude Code CLI)')],
    ['antigravity', t('Google Antigravity và công cụ agy', 'Google Antigravity (IDE + agy CLI)')],
    ['gemini_cli', t('Gói trả phí Google Gemini dòng lệnh', 'Google Gemini Subscription (Gemini CLI)')],
    ['claude', t('Anthropic Claude có khóa API', 'Anthropic Claude (API key preferred)')],
    ['cloud', `${t('Đám mây mặc định', 'Default Cloud')} (${config.default_cloud})`],
    ['local', t('LM Studio trên bộ nhớ cục bộ', 'LM Studio (Local VRAM)')],
    ['ollama', t('Ollama trên bộ nhớ cục bộ', 'Ollama (Local VRAM)')],
    ['mcp', t('Công cụ Suy luận MCP', 'MCP Inference Tool')],
    ...Object.entries(providerSpecs).map(([k, v]) => [k, `${v.label} (${t('API Đám mây', 'Cloud API')})`]),
  ];

  const CLI_DEFAULT_MODELS: Record<string, string[]> = {
    codex: [],
    chatgpt_sub: [],
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
      return Array.from(new Set([...(fetchedProviderModels[targetPid] || []), ...cliSaved, ...CLI_DEFAULT_MODELS[targetPid]]));
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
      className="settings-studio"
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
        className="settings-studio-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 110px 14px 24px',
          background: 'var(--panel)',
          borderBottom: '1px solid var(--line)',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            className="btn sm ghost"
            onClick={() => setMainView('chat')}
            title={t('Quay lại khu vực Nghiên cứu & Trò chuyện', 'Back to Research & Chat Workspace')}
          >
            <ArrowLeft size={15} style={{ marginRight: 4 }} />
            <span>{t('Quay lại Không gian làm việc', 'Back to Workspace')}</span>
          </button>
          <div style={{ width: 1, height: 20, background: 'var(--line)' }} />
          <Settings size={20} color="var(--accent)" />
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
              {t('Trung tâm Cài đặt & Cấu hình Hệ thống', 'System Settings & Configuration Center')} (PhD Research Lab v{config.version})
            </h3>
            <span className="muted" style={{ fontSize: 12 }}>
              {t('Dự án đang mở:', 'Active Project:')} <b>{config.project?.name}</b> ({config.project?.data_dir})
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
            title={t('Tỉ lệ thu phóng giao diện', 'UI Display Scale')}
          >
            <span className="muted">{t('Tỉ lệ:', 'Scale:')}</span>
            <select
              aria-label={t('Tỉ lệ thu phóng giao diện', 'UI Display Scale')}
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
              alignItems: 'center',
              gap: 6,
            }}
            title={t('Chuyển đổi ngôn ngữ Tiếng Việt / English', 'Switch Language Vietnamese / English')}
          >
            <button
              type="button"
              className={`btn sm ${(config.ui?.language || language) === 'vi' ? 'accent' : 'ghost'}`}
              style={{ borderRadius: 6, minWidth: 38, height: 28, fontWeight: 700 }}
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
              style={{ borderRadius: 6, minWidth: 38, height: 28, fontWeight: 700 }}
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
      <div className="settings-studio-body" style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* Left Navigation Rail */}
        <nav
          aria-label={t('Mục cài đặt', 'Settings sections')}
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
              placeholder={t('Tìm mục cài đặt…', 'Search settings…')}
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
          className="settings-studio-content"
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
                      {t('Phân công Nhà cung cấp & Mô hình cho 4 Tác nhân AI', 'Assign Providers & Models for 4 Core AI Agents')}
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
                    title={t('Bỏ giới hạn chạy đơn lẻ — cho phép nhiều Agent làm việc song song với mức tự động hóa cao nhất', 'Remove single-run limit — allow multi-agent parallel execution with maximum autonomy')}
                  >
                    <Sparkles size={13} style={{ marginRight: 5 }} />
                    <span>{t('Bật Tự động hóa Đa Tác nhân Song song', 'Enable Parallel Multi-Agent Automation')}</span>
                  </button>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 16px' }}>
                  {t('Khi chọn nhà cung cấp (API Đám mây, Gói trả phí ChatGPT, Claude CLI, Gemini CLI, Antigravity, hoặc Cục bộ), danh sách Mô hình bên phải sẽ tự động lọc chỉ hiển thị các model được nhà cung cấp đó hỗ trợ. Model của assistant sẽ được dùng trực tiếp trong khung Chatbox chính.', 'When selecting a provider (Cloud API, ChatGPT Subscription, Claude CLI, Gemini CLI, Antigravity, or Local), the Model list will automatically filter to show only supported models. The assistant model will be used directly in the primary Chatbox.')}
                </p>

                <div className="table-scroll">
                  <table className="grid">
                    <thead>
                      <tr>
                        <th style={{ width: '34%' }}>{t('Vai trò Tác nhân', 'Agent Role')}</th>
                        <th style={{ width: '34%' }}>{t('Nhà cung cấp / Nguồn Engine', 'Provider / Engine Source')}</th>
                        <th style={{ width: '32%' }}>{t('Mô hình Hỗ trợ', 'Supported Models')}</th>
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
                        const canFetch = targetPid === 'codex' || Boolean(providerSpecs[targetPid]);

                        return (
                          <tr key={agentId}>
                            <td>
                              <b style={{ fontSize: 13.5, textTransform: 'capitalize' }}>{agentId}</b>
                              <div className="muted" style={{ fontSize: 12 }}>{spec.label}</div>
                            </td>
                            <td>
                              <select
                                aria-label={`${agentId} ${t('Nhà cung cấp', 'provider')}`}
                                className="input"
                                value={mode}
                                onChange={(e) => {
                                  const nextMode = e.target.value;
                                  const nextModels = getModelsForEngine(nextMode);
                                  savePatch({
                                    agent_modes: { [agentId]: nextMode },
                                    agent_models: { [agentId]: CLI_DEFAULT_MODELS[nextMode.replace(/^cli:/, '')] ? '' : nextModels[0] || '' },
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
                                  {t('Tự động điều phối theo Router Thông minh', 'Auto-routed by Smart Router')}
                                </span>
                              ) : (
                                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                  <select
                                    aria-label={`${agentId} ${t('Mô hình', 'model')}`}
                                    className="input"
                                    style={{ flex: 1 }}
                                    value={currentModel}
                                    onChange={(e) =>
                                      savePatch({ agent_models: { [agentId]: e.target.value } })
                                    }
                                  >
                                    {(
                                      <option value="">({t('Mặc định của', 'Default for')} {targetPid})</option>
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
                                      title={t(`Tải danh sách model mới nhất từ ${targetPid}`, `Fetch latest models from ${targetPid}`)}
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
                      {t('Nhà cung cấp API Đám mây & Khóa Bảo mật', 'Cloud API Providers & Security Keys')} (17 Providers)
                    </h3>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="muted" style={{ fontSize: 12.5 }}>{t('Đám mây mặc định:', 'Default Cloud:')}</span>
                    <select
                      aria-label={t('Đám mây mặc định', 'Default Cloud')}
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
                  {t('Khóa API chỉ được lưu cục bộ trong data/config.json và chỉ gửi trực tiếp tới endpoint của nhà cung cấp tương ứng.', 'API keys are stored exclusively in local data/config.json and dispatched directly to the chosen provider endpoint.')}
                </p>

                <div className="table-scroll">
                  <table className="grid">
                    <thead>
                      <tr>
                        <th>{t('Nhà cung cấp', 'Provider')}</th>
                        <th>{t('API Key & Endpoint', 'API Key & Endpoint')}</th>
                        <th>{t('Mô hình Mặc định', 'Default Model')}</th>
                        <th>{t('Thao tác', 'Actions')}</th>
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
                                    title={p.has_key ? t('Đã lưu API Key', 'API Key saved') : t('Chưa có API Key', 'No API Key')}
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
                                    {t('Lấy API Key', 'Get API Key')} <ExternalLink size={10} />
                                  </a>
                                )}
                              </td>
                              <td>
                                <input
                                  type="password"
                                  className="input"
                                  style={{ fontSize: 12.5 }}
                                  placeholder={p.has_key ? t('•••••••• (Đã lưu — nhập để đổi)', '•••••••• (Saved — enter to change)') : t('Nhập API key…', 'Enter API key…')}
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
                                  placeholder={t('Nhập hoặc chọn model ID…', 'Enter or select model ID…')}
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
                                    <Check size={13} /> {t('Lưu', 'Save')}
                                  </button>
                                  <button
                                    type="button"
                                    className="btn sm ghost"
                                    disabled={testingProvider === pid}
                                    onClick={() => handleTestProvider(pid)}
                                  >
                                    <Play size={12} /> {testingProvider === pid ? t('Đang thử…', 'Testing…') : t('Thử', 'Test')}
                                  </button>
                                  <button
                                    type="button"
                                    className="btn sm ghost"
                                    onClick={() => handleFetchModels(pid)}
                                    title={t('Tải danh sách model từ nhà cung cấp', 'Fetch models from provider')}
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
                      ? t('Thu gọn danh sách nhà cung cấp phụ', 'Collapse secondary providers')
                      : `${t('Hiển thị tất cả', 'Show all')} ${Object.keys(providerSpecs).length} ${t('nhà cung cấp', 'providers')} (Mistral, Qwen, Moonshot, Cohere, Perplexity, Together, DeepInfra, 9Router, OmniRoute, Custom…)`}
                  </button>
                </div>
              </section>

              {/* 1C. Local VRAM Models (LM Studio & Ollama) */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Server size={18} color="var(--accent)" />
                    <h3 style={{ margin: 0, fontSize: 16 }}>
                      {t('Mô hình Cục bộ trên máy (LM Studio & Ollama VRAM)', 'Local Offline Models (LM Studio & Ollama VRAM)')}
                    </h3>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button type="button" className="btn sm ghost" onClick={() => refetchLocal()}>
                      <RefreshCw size={13} /> {t('Kiểm tra VRAM', 'Check VRAM')}
                    </button>
                    <button
                      type="button"
                      className="btn sm"
                      onClick={async () => {
                        await api.post('/api/models/unload', { engine: 'all' });
                        refetchLocal();
                        notify(t('Đã giải phóng toàn bộ mô hình cục bộ khỏi VRAM!', 'Unloaded all local models from VRAM!'));
                      }}
                    >
                      {t('Giải phóng VRAM', 'Unload All VRAM')}
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
                      {t('Đang nạp trong VRAM:', 'Loaded in VRAM:')}{' '}
                      <b>
                        {[
                          ...(localStatus.lmstudio?.loaded || []),
                          ...(localStatus.ollama?.loaded || []).map((m: any) => m.id || m),
                        ].join(', ') || t('Trống, 0 MB', 'Empty (0 MB)')}
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
                      placeholder={t('Auto hoặc nhập model ID…', 'Auto or enter model ID…')}
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
                      placeholder={t('Auto hoặc vd: qwen2.5:14b…', 'Auto or e.g. qwen2.5:14b…')}
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
                    <span>{t('Tự động chuyển sang Cloud API nếu mô hình Local bị lỗi hoặc quá tải', 'Automatically failover to Cloud API if local model errors or runs out of memory')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.lifecycle?.unload_on_exit !== false}
                      onChange={(e) => savePatch({ lifecycle: { unload_on_exit: e.target.checked } })}
                    />
                    <span>{t('Tự động gỡ mô hình Local khỏi VRAM khi đóng ứng dụng PhD Lab', 'Auto-unload local models from VRAM upon application exit')}</span>
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ fontSize: 13 }}>{t('Tự gỡ mô hình khỏi VRAM khi rảnh sau (phút):', 'Idle VRAM unload timeout (minutes):')}</span>
                    <input
                      type="number"
                      aria-label={t('Tự gỡ mô hình khỏi VRAM khi rảnh sau (phút)', 'Idle VRAM unload timeout (minutes)')}
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

              <section className="panelbox" style={{ padding: 20 }}>
                <h3>{t('Quy tắc kết nối mô hình', 'Model connection rules')}</h3>
                <label className="switch">
                  <input type="checkbox" checked={pendingCloudPreconnect ?? config.lifecycle?.cloud_preconnect !== false}
                    disabled={saveConfigMutation.isPending}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setPendingCloudPreconnect(checked);
                      saveConfigMutation.mutate({ lifecycle: { cloud_preconnect: checked } }, {
                        onSettled: () => setPendingCloudPreconnect(null),
                      });
                    }} />
                  <span>{t('Kết nối sẵn Cloud khi lưu mô hình', 'Preconnect Cloud when saving a model')}</span>
                </label>
                <p className="muted">{t('Cloud tái sử dụng kết nối HTTPS, không load/unload trọng số và không tự sinh câu trả lời khi kiểm tra kết nối. Máy chủ có thể đóng kết nối khi rảnh.', 'Cloud reuses HTTPS connections, never loads/unloads weights, and does not generate answers during preconnection. Servers may close idle connections.')}</p>
                <div role="status" aria-live="polite">
                  {(connectionData?.connections || []).map((item) => (
                    <p key={item.provider} style={{ fontSize: 12 }}>
                      {item.provider} · {item.model}: {({
                        connecting: t('Đang kết nối', 'Connecting'), connected: t('Đã kết nối; chưa kiểm chứng suy luận', 'Connected; inference not verified'),
                        auth_required: t('Cần xác thực', 'Authentication required'), rate_limited: t('Đã chạm hạn mức', 'Rate limited'),
                        model_unconfirmed: t('Đã kết nối; chưa xác nhận model', 'Connected; model unconfirmed'),
                        reachable: t('Đã tới máy chủ; chưa xác nhận quyền/model', 'Reachable; auth/model unconfirmed'),
                        error: t('Kết nối thất bại', 'Connection failed'),
                      } as Record<string, string>)[item.state] || item.state}
                    </p>
                  ))}
                </div>
                <label className="field">
                  <span>{t('Ngân sách lịch sử chat (token ước tính)', 'Chat history budget (estimated tokens)')}</span>
                  <input className="input" type="number" min={400} max={32000}
                    defaultValue={config.aiws?.history_budget_tokens || 4000}
                    onBlur={(e) => {
                      const value = Math.max(400, Math.min(32000, Number(e.target.value) || 4000));
                      e.target.value = String(value);
                      savePatch({ aiws: { history_budget_tokens: value } });
                    }} />
                </label>
                <label className="field">
                  <span>{t('Ngân sách ngữ cảnh nguồn (token ước tính)', 'Source context budget (estimated tokens)')}</span>
                  <input className="input" type="number" min={400} max={32000}
                    defaultValue={config.aiws?.context_budget_tokens || 6000}
                    onBlur={(e) => {
                      const value = Math.max(400, Math.min(32000, Number(e.target.value) || 6000));
                      e.target.value = String(value);
                      savePatch({ aiws: { context_budget_tokens: value } });
                    }} />
                </label>
                <label className="field">
                  <span>{t('Quy tắc model Local cho chat', 'Local model policy for chat')}</span>
                  <select className="select" value={config.lifecycle?.local_interactive || 'idle_unload'}
                    onChange={(e) => savePatch({ lifecycle: { local_interactive: e.target.value } })}>
                    <option value="idle_unload">{t('Giải phóng khi rảnh', 'Unload when idle')}</option>
                    <option value="unload_after_task">{t('Giải phóng sau mỗi tác vụ', 'Unload after each task')}</option>
                    <option value="keep_loaded">{t('Giữ model trong bộ nhớ', 'Keep model loaded')}</option>
                  </select>
                </label>
              </section>

              {/* 1D. Capability-Aware Failover & Routing */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  {t('Định tuyến Thông minh & Chuỗi Dự phòng', 'Smart Routing & Capability-Aware Failover')}
                </h3>
                <label className="switch" style={{ marginBottom: 12 }}>
                  <input
                    type="checkbox"
                    checked={config.routing?.capability_aware !== false}
                    onChange={(e) => savePatch({ routing: { capability_aware: e.target.checked } })}
                  />
                  <span>
                    {t('Bật Capability-Aware Failover (Giữ checkpoint và tự động chuyển đổi khi hết hạn mức/quota)', 'Enable Capability-Aware Failover (Checkpoint retention & automatic provider fallback upon quota limit)')}
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
                  {t('Chế độ Điều phối Research Engines', 'Research Engines Orchestration Mode (Feynman · OpenScience · OpenCode)')}
                </h3>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  {t('PhD Lab quản lý trạng thái nghiên cứu tập trung và ủy quyền từng tác vụ có phạm vi kiểm soát cho các Runtime Engine chuyên biệt.', 'PhD Lab maintains centralized research state while delegating scoped workloads to specialized runtime engines.')}
                </p>

                <div className="grid2">
                  <label className="field">
                    <span>{t('Chế độ Research Engine', 'Research Engine Mode')}</span>
                    <select
                      className="input"
                      value={config.research_providers?.engine_mode || 'auto'}
                      onChange={(e) =>
                        savePatch({ research_providers: { engine_mode: e.target.value } })
                      }
                    >
                      <option value="auto">{t('Router Thông minh (Tự động chọn theo năng lực)', 'Auto Smart Router (Capability-based dynamic routing)')}</option>
                      <option value="feynman">{t('Chỉ dùng Feynman (Tổng quan văn hiến & phản biện)', 'Feynman Only (Literature review & peer critique)')}</option>
                      <option value="openscience">{t('Chỉ dùng OpenScience (Thực nghiệm khoa học)', 'OpenScience Only (Scientific experimentation loop)')}</option>
                      <option value="opencode">{t('Chỉ dùng OpenCode (Lập trình & bản mẫu song song)', 'OpenCode Only (Parallel code prototyping & runtime)')}</option>
                      <option value="collaborative">{t('Phối hợp Đa giai đoạn', 'Collaborative Multi-Engine Pipeline')}</option>
                      <option value="phdlab">{t('Chỉ dùng PhD Lab Cốt lõi (Toàn bộ Agent nội bộ)', 'PhD Lab Native Only (Run all agents natively via PhD Lab)')}</option>
                    </select>
                  </label>

                  <label className="field">
                    <span>{t('Coding CLI mặc định cho lệnh /code', 'Default Coding CLI for /code')}</span>
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
                      <option value="app">{t('Mô hình nội bộ của ứng dụng', 'In-App Core Model')}</option>
                    </select>
                  </label>
                </div>
              </section>

              {/* 2B. OpenScience Runtime Adapter (:4096) */}
              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h3 style={{ margin: 0, fontSize: 16 }}>
                    {t('OpenScience Runtime Adapter (v6.0+ · Loopback :4096)', 'OpenScience Runtime Adapter (v6.0+ · Loopback :4096)')}
                  </h3>
                  <span className={`chip ${config.openscience?.enabled ? 'ok' : ''}`}>
                    {config.openscience?.enabled ? t('Đang bật', 'Enabled') : t('Đang tắt', 'Disabled')}
                  </span>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  {t('Kết nối tới OpenScience Studio cục bộ để thực thi các nhiệm vụ nghiên cứu tự hành, kiểm định giả thuyết và thu thập artifacts.', 'Connect to local OpenScience Studio to execute autonomous research workflows, test hypotheses, and harvest artifacts.')}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.openscience?.enabled}
                      onChange={(e) => savePatch({ openscience: { enabled: e.target.checked } })}
                    />
                    <span>{t('Bật OpenScience Runtime Adapter', 'Enable OpenScience Runtime Adapter')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.openscience?.policy_confirmed}
                      onChange={(e) =>
                        savePatch({ openscience: { policy_confirmed: e.target.checked } })
                      }
                    />
                    <span>{t('Tôi xác nhận đã xem xét quyền runtime và chính sách chia sẻ trace cục bộ', 'I confirm review of runtime permissions and local trace sharing policy')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.openscience?.allow_execution}
                      onChange={(e) =>
                        savePatch({ openscience: { allow_execution: e.target.checked } })
                      }
                    />
                    <span>{t('Cho phép thực thi mã nguồn đề xuất trong Workspace cô lập', 'Allow execution of proposed code within isolated workspace')}</span>
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
                            ? t('•••••• (Đã lưu token)', '•••••• (Token saved)')
                            : t('Nhập OpenScience token…', 'Enter OpenScience token…')
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
                        {t('Lưu Token', 'Save Token')}
                      </button>
                    </div>
                  </label>
                  <label className="field">
                    <span>{t('Giới hạn thời gian (giây)', 'Timeout (seconds)')}</span>
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
                    <span>{t('Ngân sách Tệp kết quả tối đa theo MB', 'Max Artifact Budget (MB)')}</span>
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
                    <span>{t('Nhà cung cấp Model của OpenScience', 'OpenScience Model Provider')}</span>
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
                    <span>{t('Mã định danh Model của OpenScience', 'OpenScience Model ID')}</span>
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
                    {t('Tích hợp OpenCode Parallel Core (v6.4.1 · Loopback :4097)', 'OpenCode Parallel Core Integration (v6.4.1 · Loopback :4097)')}
                  </h3>
                  <span className={`chip ${config.opencode?.enabled !== false ? 'ok' : ''}`}>
                    {config.opencode?.enabled !== false ? t('Đang bật', 'Enabled') : t('Đang tắt', 'Disabled')}
                  </span>
                </div>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  {t('Thực thi kỹ thuật phần mềm và bản mẫu song song trong không gian cô lập <topic>/opencode_prj/ với luồng sự kiện SHA-256 deduplicated.', 'Executes parallel software engineering and prototyping inside isolated <topic>/opencode_prj/ with deduplicated SHA-256 event streams.')}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.opencode?.enabled !== false}
                      onChange={(e) => savePatch({ opencode: { enabled: e.target.checked } })}
                    />
                    <span>{t('Bật OpenCode Parallel Core Runtime', 'Enable OpenCode Parallel Core Runtime')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.opencode?.allow_metered_api}
                      onChange={(e) =>
                        savePatch({ opencode: { allow_metered_api: e.target.checked } })
                      }
                    />
                    <span>{t('Cho phép dùng Metered API (vẫn yêu cầu cổng phê duyệt từng phiên)', 'Allow metered API calls (still requires per-session risk approval)')}</span>
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
                    <span>{t('Timeout mỗi phiên OpenCode (giây)', 'OpenCode Turn Timeout (seconds)')}</span>
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
                    {t('Nhà Cung Cấp Ứng Dụng & Điều Hướng Nhanh Kèm Đồng Bộ', 'App Providers, Quick Launch & 2-Way Data Sync')}
                  </h3>
                  <button type="button" className="btn sm ghost" onClick={() => refetchProviders()}>
                    <RefreshCw size={13} /> {t('Làm mới trạng thái CLI', 'Refresh CLI Status')}
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
                    <span>{t('Dùng Feynman cho /lit, /deepresearch, /compare và /review', 'Use Feynman for /lit, /deepresearch, /compare and /review')}</span>
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
                    <span>{t('Cho phép Feynman dùng chung khóa Anthropic/OpenAI của ứng dụng', 'Allow Feynman to share in-app Anthropic/OpenAI keys')}</span>
                  </label>
                </div>

                <div className="list">
                  {(Array.isArray(researchProvidersData?.providers) ? researchProvidersData.providers : []).map((p: any) => (
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
                      {syncResults[p.id] && (
                        <div style={{ fontSize: 11, color: '#10b981', display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, fontWeight: 500 }}>
                          <CheckCircle2 size={12} />
                          <span>
                            {t('Đã đồng bộ lúc ', 'Synced at ')}{syncResults[p.id].at} • {syncResults[p.id].changed} {t('tệp thay đổi', 'files updated')} • {syncResults[p.id].observed} {t('tệp đã quét', 'files scanned')}
                          </span>
                        </div>
                      )}

                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                        <button
                          type="button"
                          className="btn sm ghost"
                          onClick={() => handleLaunchProvider(p.id, p.label)}
                          title={t('Mở nhanh ứng dụng hoặc trang quản trị nhà cung cấp', 'Directly open app or provider web')}
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', fontSize: 11.5, borderRadius: 6 }}
                        >
                          <ExternalLink size={12} />
                          <span>{t('Mở Ứng dụng', 'Open App')}</span>
                        </button>

                        <button
                          type="button"
                          className="btn sm accent"
                          disabled={syncingProvider === p.id}
                          onClick={() => handleSyncProvider(p.id, p.label)}
                          title={t('Quét và đồng bộ tệp tin, dữ liệu từ ứng dụng về PhD Lab', 'Scan and sync files from app back into PhD Lab')}
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', fontSize: 11.5, borderRadius: 6 }}
                        >
                          <RefreshCw size={12} className={syncingProvider === p.id ? 'spin' : ''} />
                          <span>{syncingProvider === p.id ? t('Đang đồng bộ...', 'Syncing...') : t('Đồng bộ về Lab', 'Sync to Lab')}</span>
                        </button>

                        {['codex', 'claude_code', 'gemini_cli', 'antigravity'].includes(p.id) && <button
                          className="btn sm" disabled={testingProvider === p.id}
                          onClick={() => handleTestProvider(p.id)}>
                          {testingProvider === p.id ? t('Đang thử...', 'Testing...') : t('Test chat CLI thật', 'Test real CLI chat')}
                        </button>}

                        {!p.ready &&
                          ['feynman', 'claude_code', 'codex', 'gemini_cli', 'antigravity'].includes(p.id) && (
                            <button
                              type="button"
                              className="btn sm"
                              onClick={async () => {
                                await api.post(`/api/providers/${p.id}/connect`, {});
                                notify(t('Đã mở cửa sổ đăng nhập cho ', 'Opened login window for ') + p.label);
                              }}
                              style={{ padding: '4px 10px', fontSize: 11.5, borderRadius: 6 }}
                            >
                              {t('Đăng nhập CLI', 'CLI Login')}
                            </button>
                          )}
                      </div>
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
                  {t('Tìm kiếm Bài báo Khoa học & Web', 'Academic Paper & Web Search (OpenAlex · Semantic Scholar · ArXiv)')}
                </h3>
                <div className="grid2">
                  <label className="field">
                    <span>{t('Công cụ tìm kiếm Web', 'Web Search Engine')}</span>
                    <select
                      className="input"
                      value={config.search?.web_engine || 'duckduckgo'}
                      onChange={(e) => savePatch({ search: { web_engine: e.target.value } })}
                    >
                      <option value="duckduckgo">{t('DuckDuckGo (Miễn phí, không cần key)', 'DuckDuckGo (Free, no key required)')}</option>
                      <option value="tavily">Tavily AI Search</option>
                      <option value="brave">Brave Search API</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>{t('Số kết quả mỗi lần truy vấn (1–30)', 'Results per search query (1–30)')}</span>
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
                    <span>{t('Email cho OpenAlex Polite Pool (tăng tốc độ truy vấn)', 'Email for OpenAlex Polite Pool (faster rate limits)')}</span>
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
                  <span>{t('Đọc toàn văn nội dung trang web hàng đầu khi tìm kiếm', 'Scrape full-text content of top search results')}</span>
                </label>

                <h4 style={{ margin: '12px 0 8px', fontSize: 14 }}>
                  {t('Khóa API Cơ sở dữ liệu Học thuật & Tìm kiếm (Tuỳ chọn)', 'Academic Database & Search API Keys (Optional)')}
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
                            placeholder={hasKey ? t('•••••• (Đã lưu key)', '•••••• (Key saved)') : t('Chưa cấu hình', 'Not configured')}
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
                            {t('Lưu', 'Save')}
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
                      {t('Xếp hạng Hội nghị (CORE A*/A/B/C) & Tạp chí (SCImago Q1–Q4)', 'Conference Ranking (CORE A*/A/B/C) & Journal Ranking (SCImago Q1–Q4)')}
                    </h3>
                  </div>
                  <button
                    type="button"
                    className="btn sm ghost"
                    onClick={async () => {
                      await api.get('/api/ranking?refresh=1');
                      refetchRanking();
                      notify(t('Đã làm mới cơ sở dữ liệu xếp hạng học thuật!', 'Academic venue ranking database refreshed!'));
                    }}
                  >
                    <RefreshCw size={13} /> {t('Cập nhật CORE ngay', 'Update CORE Now')}
                  </button>
                </div>

                <div className="grid2" style={{ marginTop: 10 }}>
                  <label className="field">
                    <span>{t('Phiên bản xếp hạng CORE', 'CORE Ranking Edition')}</span>
                    <select
                      className="input"
                      value={config.ranking?.core_source || 'ICORE2026'}
                      onChange={(e) => savePatch({ ranking: { core_source: e.target.value } })}
                    >
                      <option value="ICORE2026">{t('ICORE 2026 (Mới nhất)', 'ICORE 2026 (Latest)')}</option>
                      <option value="CORE2023">CORE 2023</option>
                      <option value="CORE2021">CORE 2021</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>{t('Chu kỳ tự động làm mới (ngày)', 'Auto-refresh interval (days)')}</span>
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
                      <b>{t('Phân hạng Hội nghị CORE:', 'Conferences (CORE):')}</b>{' '}
                      {rankingStatus.conferences?.records
                        ? `${rankingStatus.conferences.records} ${t('hội nghị', 'conferences')} (${rankingStatus.conferences.source})`
                        : t('Chưa tải dữ liệu', 'No data loaded')}
                    </div>
                    <div>
                      <b>{t('Phân hạng Tạp chí SCImago:', 'Journals (SCImago):')}</b>{' '}
                      {rankingStatus.journals?.records
                        ? `${rankingStatus.journals.records} ${t('tạp chí', 'journals')} (${t('Năm', 'Year')} ${rankingStatus.journals.year})`
                        : t('Chưa nhập CSV SCImago', 'No SCImago CSV imported')}
                    </div>
                  </div>
                )}

                {/* Live Venue Lookup Tool */}
                <div style={{ borderTop: '1px solid var(--line)', paddingTop: 12 }}>
                  <b style={{ fontSize: 13 }}>{t('Tra cứu nhanh hạng Hội nghị / Tạp chí:', 'Quick Conference / Journal Rank Lookup:')}</b>
                  <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                    <input
                      className="input"
                      placeholder={t('Nhập tên hội nghị hoặc tạp chí (vd: NeurIPS, CVPR, IEEE TPAMI, Nature)…', 'Enter venue name (e.g. NeurIPS, CVPR, IEEE TPAMI, Nature)…')}
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
                      {t('Tra cứu', 'Lookup')}
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
                  {t('Tiến trình Chạy nền & Cổng Phê duyệt Rủi ro', 'Background Runs & Risk Governance Gateway')}
                </h3>
                <div className="grid2">
                  <label className="field">
                    <span>{t('Mức độ tự chạy không cần hỏi trước', 'Autonomous Approval Level')}</span>
                    <select
                      className="input"
                      value={config.runs?.auto_approve_risk ?? 1}
                      onChange={(e) =>
                        savePatch({ runs: { auto_approve_risk: Number(e.target.value) } })
                      }
                    >
                      <option value={0}>{t('Mức 0 — Chỉ tác vụ đọc (Tìm tài liệu, Phản biện)', 'Level 0 — Read-only tasks (Literature discovery, Peer review)')}</option>
                      <option value={1}>{t('Mức 1 — Cho phép ghi báo cáo/PDF trong dự án', 'Level 1 — Allow report & PDF drafting within project workspace')}</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>{t('Ngân sách thời gian mỗi Run (phút)', 'Max Run Time Budget (minutes)')}</span>
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
                    <span>{t('Số lần tự phục hồi khi lỗi (vd: CUDA OOM → giảm batch)', 'Max Error Auto-Retries (e.g., CUDA OOM → reduce batch)')}</span>
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
                    <span>{t('Tự động phục hồi lỗi có phương án sửa an toàn', 'Auto-recover errors with safe mitigation plan')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.runs?.web_search !== false}
                      onChange={(e) => savePatch({ runs: { web_search: e.target.checked } })}
                    />
                    <span>{t('Truy vấn bài báo thực tế (OpenAlex, Semantic Scholar, ArXiv) trước khi tổng hợp /lit', 'Ground /lit synthesis with real academic search queries (OpenAlex, Semantic Scholar, ArXiv)')}</span>
                  </label>
                </div>
              </section>

              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>
                  {t('Bộ điều phối Tài nguyên Phần cứng', 'Hardware Resource Governor')}
                </h3>
                <div className="grid2">
                  <label className="field">
                    <span>{t('Số Job CPU đồng thời tối đa', 'Max Concurrent CPU Jobs')}</span>
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
                    <span>{t('Số CLI Provider chạy đồng thời', 'Max Concurrent CLI Providers')}</span>
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
                    <span>{t('Số luồng gọi Cloud API đồng thời', 'Max Concurrent Cloud API Calls')}</span>
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
                    <span>{t('Giới hạn nhiệt độ GPU tối đa (°C)', 'Max GPU Temperature Limit (°C)')}</span>
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
                  <span>{t('Tự động giải phóng mô hình cục bộ đang rảnh khỏi VRAM khi cần GPU chạy thí nghiệm', 'Auto-offload idle local models from VRAM during compute experiments')}</span>
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
                    <span>{t('Đường dẫn thực thi VS Code (để trống = tự động tìm)', 'VS Code Executable Path (empty = auto-detect)')}</span>
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
                    <span>{t('Đồng bộ trực tuyến với ClearML Server', 'Sync online with ClearML Server')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!config.research_os?.enabled}
                      onChange={(e) =>
                        savePatch({ research_os: { enabled: e.target.checked } })
                      }
                    />
                    <span>{t('Bật chế độ Autonomous Research OS (Multi-Agent Teams & Workstreams)', 'Enable Autonomous Research OS (Multi-Agent Teams & Workstreams)')}</span>
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
                  {t('Bộ nhớ Ngữ cảnh Dự án v2 và Không gian làm việc AI', 'Project Context Memory (v2) & AI Workspace')}
                </h3>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  {t('Ngữ cảnh dự án (đề cương 5 cấp, quyết định, giả thuyết, kết quả thí nghiệm, tài liệu SKB) được biên dịch tự động cho mỗi lượt hội thoại.', 'Project context (5-level outline, decisions, hypotheses, experiment results, and SKB knowledge) is dynamically compiled for every turn.')}
                </p>

                <div className="grid2">
                  <label className="field">
                    <span>{t('Chế độ Ghi nhớ Tri thức', 'Knowledge Memory Mode')}</span>
                    <select
                      className="input"
                      value={config.aiws?.memory_mode || 'suggest'}
                      onChange={(e) => savePatch({ aiws: { memory_mode: e.target.value } })}
                    >
                      <option value="suggest">{t('Đề xuất — Hiển thị thẻ để bạn Chấp nhận / Bỏ qua (Khuyên dùng)', 'Suggest — Cards rendered for Accept / Dismiss (Recommended)')}</option>
                      <option value="manual">{t('Thủ công — Chỉ lưu khi bạn bấm Ghi nhớ trên tin nhắn', 'Manual — Save only when explicitly clicked on messages')}</option>
                      <option value="auto">{t('Tự động có giới hạn (Chỉ tự lưu câu hỏi mở)', 'Bounded Auto — Automatically store open research questions')}</option>
                      <option value="off">{t('Tắt ghi nhớ tự động', 'Off — Disable automatic memory')}</option>
                    </select>
                  </label>

                  <label className="field">
                    <span>{t('Chế độ Vận hành AI', 'AI Operating Mode')}</span>
                    <select
                      className="input"
                      value={config.aiws?.operating_mode || 'automation'}
                      onChange={(e) => savePatch({ aiws: { operating_mode: e.target.value } })}
                    >
                      <option value="automation">{t('Tự động — AI tự dùng công cụ chỉ-đọc, thay đổi chờ duyệt', 'Automation — Autonomous read-only tools, gated mutations')}</option>
                      <option value="manual">{t('Thủ công — Kiểm duyệt gói ngữ cảnh trước mỗi lượt gửi', 'Manual — Inspect and review context package before prompt dispatch')}</option>
                    </select>
                  </label>

                  <label className="field">
                    <span>{t('Ngân sách Ngữ cảnh mỗi lượt theo Tokens', 'Turn Context Budget (Tokens)')}</span>
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
                    <span>{t('Thời gian tối đa một lượt trả lời (giây)', 'Max Turn Timeout (seconds)')}</span>
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
                  {t('PhD Lab cung cấp MCP Server cục bộ tại', 'PhD Lab exposes a local MCP Server at')} <code>{window.location.origin}/mcp</code> {t('cho phép các CLI bên ngoài truy cập công cụ nghiên cứu có kiểm soát.', 'allowing external CLIs governed access to research tools.')}
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.mcp?.expose_research !== false}
                      onChange={(e) => savePatch({ mcp: { expose_research: e.target.checked } })}
                    />
                    <span>{t('Cung cấp bộ công cụ đọc dữ liệu nghiên cứu qua MCP', 'Expose research read tools via MCP')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.mcp?.allow_writes !== false}
                      onChange={(e) => savePatch({ mcp: { allow_writes: e.target.checked } })}
                    />
                    <span>{t('Cho phép MCP tạo đề xuất ghi (luôn cần nhà nghiên cứu phê duyệt)', 'Allow MCP write proposals (always requires researcher approval)')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.gateway?.block_source_code !== false}
                      onChange={(e) =>
                        savePatch({ gateway: { block_source_code: e.target.checked } })
                      }
                    />
                    <span>{t('Context Firewall: Chặn tự động đính kèm mã nguồn nhạy cảm ra ngoài', 'Context Firewall: Block automatic external exfiltration of sensitive source code')}</span>
                  </label>
                </div>

                <h4 style={{ margin: '16px 0 8px', fontSize: 14 }}>MCP Inference Agent</h4>
                <label className="switch" style={{ marginBottom: 10 }}>
                  <input
                    type="checkbox"
                    checked={!!config.mcp_agent?.enabled}
                    onChange={(e) => savePatch({ mcp_agent: { enabled: e.target.checked } })}
                  />
                  <span>{t('Bật MCP Inference Agent', 'Enable MCP Inference Agent')}</span>
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
                    <span>{t('Tên công cụ suy luận', 'Inference Tool Name')}</span>
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
                  {t('Cài đặt Plugin Kỹ năng từ GitHub (Agent Skills & AI-Scientist-v2)', 'Install Skill Plugins from GitHub (Agent Skills & AI-Scientist-v2)')}
                </h3>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 12px' }}>
                  {t('Cài đặt kỹ năng từ bất kỳ kho mã nguồn GitHub nào chứa SKILL.md hoặc thư mục skills/.', 'Install research skills from any GitHub repo containing SKILL.md or skills/ directory.')}
                </p>

                <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                  <input
                    className="input"
                    placeholder={t('https://github.com/owner/repo (hoặc nhánh/thư mục con)…', 'https://github.com/owner/repo (or branch/subfolder)…')}
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
                        notify(t('Đã cài đặt Plugin từ GitHub thành công!', 'Plugin installed successfully from GitHub!'));
                      } catch (err) {
                        notify(t('Lỗi cài plugin: ', 'Plugin installation error: ') + (err as Error).message, 'err');
                      } finally {
                        setInstallingPlugin(false);
                      }
                    }}
                  >
                    <Plus size={15} /> {installingPlugin ? t('Đang tải…', 'Installing…') : t('Cài Plugin', 'Install Plugin')}
                  </button>
                </div>

                {/* Optional GitHub Plugins Catalog (Tùy chọn: AI-Scientist-v2, v.v.) */}
                <div style={{ marginBottom: 18 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--fg)' }}>
                      {t('Danh mục Plugin Tùy chọn (Optional GitHub Plugins)', 'Optional GitHub Plugins Catalog')}
                    </span>
                    <span className="badge" style={{ fontSize: 11, background: 'var(--bg-2)', color: 'var(--muted)' }}>
                      {t('Động cơ chính: PaperOrchestra', 'Primary Engine: PaperOrchestra')}
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                    {(pluginsData?.optional_plugins || [
                      {
                        id: 'sakanaai-ai-scientist-v2',
                        name: 'AI-Scientist-v2',
                        title: 'The AI Scientist v2 (Sakana AI)',
                        url: 'https://github.com/SakanaAI/AI-Scientist-v2',
                        category: 'writing',
                        description: 'Sinh ý tưởng nghiên cứu, viết nháp bài báo theo template ICML/NeurIPS và biểu mẫu phản biện từ Sakana AI. Tùy chọn độc lập sau PaperOrchestra.',
                        skills: ['/ais-idea', '/ais-review', '/ais-write'],
                        installed: false,
                        enabled: false,
                      },
                      {
                        id: 'k-dense-scientific-skills',
                        name: 'K-Dense Scientific Skills',
                        title: 'Scientific Agent Skills (K-Dense AI)',
                        url: 'https://github.com/K-Dense-AI/scientific-agent-skills',
                        category: 'research',
                        description: 'Tập hợp các kỹ năng chuyên sâu cho tác nhân nghiên cứu khoa học, mô phỏng và phân tích dữ liệu.',
                        skills: ['scientific-analysis'],
                        installed: false,
                        enabled: false,
                      },
                      {
                        id: 'anthropics-skills',
                        name: 'Anthropic Agent Skills',
                        title: 'Official Agent Skills (Anthropic)',
                        url: 'https://github.com/anthropics/skills',
                        category: 'general',
                        description: 'Bộ kỹ năng tác nhân chuẩn từ Anthropic dành cho Claude và hệ thống tác nhân đa năng.',
                        skills: ['general-skills'],
                        installed: false,
                        enabled: false,
                      },
                    ]).map((opt: any) => {
                      const isInstalled = !!opt.installed || (pluginsData?.plugins || []).some((p: any) => p.id === opt.id);
                      const installedPlugin = (pluginsData?.plugins || []).find((p: any) => p.id === opt.id);
                      const isEnabled = installedPlugin ? !!installedPlugin.enabled : false;

                      return (
                        <div
                          key={opt.id}
                          style={{
                            border: opt.id === 'sakanaai-ai-scientist-v2' ? '1px solid var(--accent)' : '1px solid var(--line)',
                            borderRadius: 10,
                            padding: 12,
                            background: 'var(--bg-2)',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            gap: 10,
                          }}
                        >
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6, marginBottom: 4 }}>
                              <b style={{ fontSize: 13, color: 'var(--fg)' }}>{opt.title}</b>
                              <span
                                style={{
                                  fontSize: 10,
                                  padding: '1px 6px',
                                  borderRadius: 4,
                                  background: isInstalled ? '#10b98122' : 'var(--panel)',
                                  color: isInstalled ? '#10b981' : 'var(--muted)',
                                  fontWeight: 600,
                                  border: '1px solid var(--line)',
                                }}
                              >
                                {isInstalled ? t('Đã cài đặt', 'Installed') : t('Tùy chọn', 'Optional')}
                              </span>
                            </div>
                            <p style={{ margin: '0 0 8px', fontSize: 11.5, color: 'var(--muted)', lineHeight: 1.4 }}>
                              {opt.description}
                            </p>
                            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                              {(opt.skills || []).map((sk: string) => (
                                <span
                                  key={sk}
                                  style={{
                                    fontSize: 10,
                                    fontFamily: 'monospace',
                                    padding: '1px 5px',
                                    borderRadius: 4,
                                    background: 'var(--panel)',
                                    color: 'var(--accent)',
                                    border: '1px solid var(--line)',
                                  }}
                                >
                                  {sk}
                                </span>
                              ))}
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 6, borderTop: '1px solid var(--line)' }}>
                            <a
                              href={opt.url}
                              target="_blank"
                              rel="noreferrer"
                              style={{ fontSize: 11, color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                            >
                              <span>GitHub</span>
                              <ExternalLink size={11} />
                            </a>

                            {!isInstalled ? (
                              <button
                                type="button"
                                className="btn xs accent"
                                disabled={installingPlugin}
                                onClick={async () => {
                                  setInstallingPlugin(true);
                                  try {
                                    await api.post('/api/plugins', { url: opt.url, enable: true });
                                    refetchPlugins();
                                    refetchSkills();
                                    notify(t('Đã cài đặt plugin thành công từ GitHub: ', 'Successfully installed plugin from GitHub: ') + opt.title);
                                  } catch (err) {
                                    notify(t('Lỗi cài plugin: ', 'Failed to install plugin: ') + (err as Error).message, 'err');
                                  } finally {
                                    setInstallingPlugin(false);
                                  }
                                }}
                                style={{ gap: 4 }}
                                title={t(`Cài đặt ${opt.title} qua cơ chế GitHub plugin`, `Install ${opt.title} via GitHub plugin mechanism`)}
                              >
                                <Plus size={11} />
                                <span>{t('Cài qua GitHub', 'Get via GitHub')}</span>
                              </button>
                            ) : (
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <label className="switch" style={{ fontSize: 11 }}>
                                  <input
                                    type="checkbox"
                                    checked={isEnabled}
                                    onChange={async (e) => {
                                      await api.put(`/api/plugins/${opt.id}`, { enabled: e.target.checked });
                                      refetchPlugins();
                                      refetchSkills();
                                    }}
                                  />
                                  <span>{t('Bật', 'On')}</span>
                                </label>
                                <button
                                  type="button"
                                  className="btn xs ghost danger"
                                  onClick={async () => {
                                    await api.delete(`/api/plugins/${opt.id}`);
                                    refetchPlugins();
                                    refetchSkills();
                                    notify(t('Đã gỡ plugin: ', 'Uninstalled plugin: ') + opt.title);
                                  }}
                                  title={t('Gỡ plugin', 'Uninstall plugin')}
                                >
                                  <Trash2 size={12} />
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
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
                          {(p.skills || []).length} {t('kỹ năng', 'skills')}
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
                          <span>{t('Bật', 'Enabled')}</span>
                        </label>
                        <button
                          type="button"
                          className="btn sm ghost"
                          onClick={async () => {
                            await api.post(`/api/plugins/${p.id}/update`, {});
                            refetchPlugins();
                            notify(t('Đã cập nhật ', 'Updated ') + p.id);
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
                            notify(t('Đã gỡ plugin ', 'Uninstalled plugin ') + p.id);
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
                  {t('Danh mục Kỹ năng Lệnh /', 'Slash Command Skills Directory')} ({skillsData?.skills?.length || 0} {t('kỹ năng', 'skills')})
                </h3>
                <div className="table-scroll" style={{ maxHeight: 320, overflowY: 'auto' }}>
                  <table className="grid">
                    <thead>
                      <tr>
                        <th>{t('Lệnh', 'Command')}</th>
                        <th>{t('Mô tả', 'Description')}</th>
                        <th>{t('Chế độ & Nguồn', 'Mode & Source')}</th>
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
                            <span className="chip">{s.mode === 'run' ? t('Chạy nền', 'Background') : t('Hội thoại', 'Chat')}</span>{' '}
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
                                  notify(t('Đã xoá kỹ năng /', 'Deleted skill /') + s.name);
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

                <h4 style={{ margin: '18px 0 8px', fontSize: 14 }}>{t('Tạo hoặc Cập nhật Kỹ năng Tùy chỉnh', 'Create or Update Custom Skill')}</h4>
                <textarea
                  className="input mono"
                  rows={8}
                  value={newSkillText}
                  onChange={(e) => setNewSkillText(e.target.value)}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                  <select
                    aria-label={t('Phạm vi lưu kỹ năng', 'Skill save scope')}
                    className="input"
                    style={{ width: 220 }}
                    value={newSkillScope}
                    onChange={(e) => setNewSkillScope(e.target.value as 'project' | 'user')}
                  >
                    <option value="project">{t('Lưu cho Dự án hiện tại', 'Save for Current Project')}</option>
                    <option value="user">{t('Lưu cho Mọi dự án (Toàn cục)', 'Save Globally (User-level)')}</option>
                  </select>
                  <button
                    type="button"
                    className="btn accent"
                    onClick={async () => {
                      try {
                        await api.post('/api/skills', { text: newSkillText, scope: newSkillScope });
                        refetchSkills();
                        notify(t('Đã lưu kỹ năng thành công!', 'Skill saved successfully!'));
                      } catch (err) {
                        notify(t('Lỗi lưu kỹ năng: ', 'Failed to save skill: ') + (err as Error).message, 'err');
                      }
                    }}
                  >
                    {t('Lưu Kỹ năng', 'Save Skill')}
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
                  {t('Chủ đề Giao diện', 'Color Themes & Appearance')}
                </h3>
                <p className="muted" style={{ fontSize: 13, margin: '0 0 14px' }}>
                  {t('Chọn bảng màu phù hợp với không gian làm việc của bạn. Hỗ trợ đầy đủ cả chế độ Sáng học thuật lẫn chế độ Tối OpenScience Studio.', 'Select the color palette for your research workspace. Fully supports Academic Light and OpenScience Studio Dark modes.')}
                </p>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))',
                    gap: 12,
                  }}
                >
                  {BUILTIN_THEMES.map((themeItem) => {
                    const isSelected = selectedTheme === themeItem.id;
                    return (
                      <div
                        key={themeItem.id}
                        onClick={() => {
                          setSelectedTheme(themeItem.id);
                          applyThemeById(themeItem.id);
                          notify(t('Đã áp dụng chủ đề: ', 'Applied theme: ') + themeItem.name);
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
                            background: themeItem.swatch.bg,
                            color: themeItem.swatch.ink,
                            border: `1px solid ${themeItem.swatch.accent}`,
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
                              background: themeItem.swatch.accent,
                            }}
                          />
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <b style={{ fontSize: 13 }}>
                            {themeItem.id === 'system'
                              ? t('Theo hệ thống', 'System Default')
                              : themeItem.id === 'light'
                              ? t('Academic Daylight (Sáng)', 'Academic Daylight (Light)')
                              : themeItem.id === 'dark'
                              ? t('Obsidian Research (Tối)', 'Obsidian Research (Dark)')
                              : themeItem.name}
                          </b>
                          {isSelected && <Check size={15} color="var(--accent)" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="panelbox" style={{ marginTop: 0, padding: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <div>
                    <h3 style={{ margin: '0 0 4px', fontSize: 16 }}>
                      {t('Kiểu chữ Học thuật & Ngôn ngữ Hệ thống', 'Academic Typography & System Languages')}
                    </h3>
                    <p className="muted" style={{ margin: 0, fontSize: 12.5 }}>
                      {t(
                        'Cấu hình đồng bộ font chữ hiển thị bài báo khoa học, câu trả lời AI và ngôn ngữ làm việc của hệ thống.',
                        'Configure synchronized typography for papers, AI responses, and research OS interface.'
                      )}
                    </p>
                  </div>
                </div>

                {/* 3 Đồng bộ Cards: Kích thước, padding, border và visual weight đồng đều 100% */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                    gap: 16,
                    marginBottom: 16,
                  }}
                >
                  {/* Card 1: Kiểu chữ Hiển thị Bài báo & AI */}
                  <div
                    style={{
                      background: 'var(--panel)',
                      border: '1px solid var(--line)',
                      borderRadius: 10,
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      minHeight: 185,
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <Type size={16} color="var(--accent)" />
                        <b style={{ fontSize: 13.5 }}>
                          {t('Font chữ Bài báo & Câu trả lời AI', 'Paper & AI Prose Typography')}
                        </b>
                      </div>
                      <div className="muted" style={{ fontSize: 12, lineHeight: 1.45, marginBottom: 12 }}>
                        {t(
                          'Áp dụng cho nội dung tóm tắt bài báo, bản thảo, câu trả lời của AI và tài liệu nghiên cứu.',
                          'Applied across paper abstracts, full-text reading, AI markdown responses, and research notes.'
                        )}
                      </div>
                    </div>
                    <div>
                      <select
                        id="prose-font-select"
                        className="input"
                        value={config.ui?.prose_font || 'sans'}
                        onChange={(e) => {
                          const font = e.target.value;
                          applyFontById(font);
                          savePatch({ ui: { prose_font: font } });
                        }}
                        style={{ width: '100%' }}
                      >
                        <optgroup label={t('Tạp chí & Xuất bản Khoa học', 'Academic & Journal Serifs')}>
                          <option value="serif">{t('Source Serif 4 (Adobe Academic — Chuẩn tài liệu nghiên cứu)', 'Source Serif 4 (Adobe Academic — Research Paper Standard)')}</option>
                          <option value="latex">{t('Computer Modern / KaTeX (LaTeX arXiv Math — Chuẩn toán học)', 'Computer Modern / KaTeX (LaTeX arXiv Math — Mathematical Standard)')}</option>
                          <option value="merriweather">{t('Merriweather (Google Fonts Library — Tối ưu đọc dài)', 'Merriweather (Google Fonts Library — Optimized Longform Reading)')}</option>
                          <option value="lora">{t('Lora (Contemporary Scholarly Serif — Dấu thanh chuẩn)', 'Lora (Contemporary Scholarly Serif — Diacritics Calibrated)')}</option>
                          <option value="garamond">{t('EB Garamond (Oxford & University Press cổ điển)', 'EB Garamond (Oxford & University Press Classic)')}</option>
                          <option value="times">{t('Times New Roman (Chuẩn nộp bài IEEE / Nature / Springer)', 'Times New Roman (Submission Standard for IEEE / Nature / Springer)')}</option>
                          <option value="charter">{t('Charter (Bitstream Technical Reports — Báo cáo kỹ thuật)', 'Charter (Bitstream Technical Reports — Engineering Papers)')}</option>
                        </optgroup>
                        <optgroup label={t('Hiện đại & Giao diện Rõ nét (Modern Tech & Sans)', 'Modern UI & Sans-Serif')}>
                          <option value="sans">{t('Segoe UI / Noto Sans (Mặc định hệ điều hành — Sans-serif rõ nét)', 'Segoe UI / Noto Sans (OS Native Default — Clean Sans-Serif)')}</option>
                          <option value="inter">{t('Inter (React Ecosystem & Shadcn Standard — Tối giản, thanh lịch)', 'Inter (React Ecosystem & Modern UI Standard)')}</option>
                          <option value="roboto">{t('Roboto & Noto (Google International Standard — Đa ngôn ngữ)', 'Roboto & Noto (Google International Standard — Multilingual)')}</option>
                        </optgroup>
                        <optgroup label={t('Mã nguồn & Báo cáo Tính toán (Computational & Monospace)', 'Computational & Code Monospace')}>
                          <option value="mono">{t('JetBrains Mono (Code, Thuật toán & Dữ liệu toán học)', 'JetBrains Mono (Code, Algorithms & Numerical Data)')}</option>
                          <option value="fira">{t('Fira Code (Lập trình, Ligatures ký hiệu khoa học)', 'Fira Code (Programming, Scientific Ligatures)')}</option>
                        </optgroup>
                      </select>
                    </div>
                  </div>

                  {/* Card 2: 1. Ngôn ngữ Giao diện Người dùng riêng */}
                  <div
                    style={{
                      background: 'var(--panel)',
                      border: '1px solid var(--line)',
                      borderRadius: 10,
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      minHeight: 185,
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <Globe size={16} color="var(--accent)" />
                        <b style={{ fontSize: 13.5 }}>
                          {t('1. Ngôn ngữ Giao diện', '1. User Interface Language')}
                        </b>
                      </div>
                      <div className="muted" style={{ fontSize: 12, lineHeight: 1.45, marginBottom: 12 }}>
                        {t(
                          t('Quy định ngôn ngữ hiển thị của toàn bộ menu, nút bấm, thông báo, nhãn thanh bên và hộp thoại.', 'Controls the display language across all menus, buttons, notifications, sidebar labels, and modals.'),
                          'Display language for menus, buttons, notifications, sidebar labels, and dialogs across software.'
                        )}
                      </div>
                    </div>
                    <div>
                      <select
                        id="ui-language-select"
                        className="input"
                        value={config.ui?.language || language || 'vi'}
                        onChange={(e) => {
                          const newLang = e.target.value as 'vi' | 'en';
                          setLanguage(newLang);
                          savePatch({ ui: { language: newLang } });
                        }}
                        style={{ width: '100%' }}
                      >
                        <option value="vi">{t('Tiếng Việt (Giao diện Tiếng Việt)', 'Vietnamese (Tiếng Việt)')}</option>
                        <option value="en">English (Academic International Interface)</option>
                      </select>
                    </div>
                  </div>

                  {/* Card 3: 2. Ngôn ngữ Phản hồi của AI riêng */}
                  <div
                    style={{
                      background: 'var(--panel)',
                      border: '1px solid var(--line)',
                      borderRadius: 10,
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      minHeight: 185,
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                        <Bot size={16} color="#10b981" />
                        <b style={{ fontSize: 13.5 }}>
                          {t('2. Ngôn ngữ Phản hồi AI', '2. AI Assistant Output Language')}
                        </b>
                      </div>
                      <div className="muted" style={{ fontSize: 12, lineHeight: 1.45, marginBottom: 12 }}>
                        {t(
                          t('Quy định ngôn ngữ các AI Agents và Orchestrator ưu tiên khi giải thích, phân tích và viết báo cáo nghiên cứu.', 'Specifies the default language prioritized by AI Agents and Orchestrator for synthesis, critique, and paper writing.'),
                          'Language AI Agents and Orchestrator prioritize when answering, explaining, analyzing, and drafting research reports.'
                        )}
                      </div>
                    </div>
                    <div>
                      <select
                        id="ai-language-select"
                        className="input"
                        value={config.ui?.ai_language || 'auto'}
                        onChange={(e) => savePatch({ ui: { ai_language: e.target.value } })}
                        style={{ width: '100%' }}
                      >
                        <option value="auto">
                          {t('Tự động nhận diện (Theo ngôn ngữ câu hỏi của bạn)', 'Auto-detect (Match prompt language)')}
                        </option>
                        <option value="vi">
                          {t('Tiếng Việt (Giữ nguyên thuật ngữ khoa học bằng tiếng Anh)', 'Vietnamese (Keep technical terms in English)')}
                        </option>
                        <option value="en">
                          {t('English (Academic & Scientific Standard)', 'English (Academic & Scientific Standard)')}
                        </option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Khung Xem Trước Trực Tiếp Kiểu Chữ Học Thuật (Interactive Academic Typography Preview) */}
                <div
                  style={{
                    background: 'var(--bg-2, var(--code-bg))',
                    border: '1px dashed var(--line-2)',
                    borderRadius: 10,
                    padding: '14px 18px',
                    marginBottom: 16,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <BookOpen size={14} color="var(--accent)" />
                      <span style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>
                        {t('Xem trước Trực quan Kiểu chữ Bài báo & Toán học', 'Live Typography & Paper Reading Preview')}
                      </span>
                    </div>
                    <span
                      style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        borderRadius: 12,
                        background: 'var(--panel)',
                        border: '1px solid var(--line)',
                        color: 'var(--accent)',
                        fontWeight: 600,
                      }}
                    >
                      {config.ui?.prose_font || 'sans'}
                    </span>
                  </div>
                  <div
                    className="prose markdown-body"
                    style={{
                      fontFamily: 'var(--prose)',
                      fontSize: 14.5,
                      lineHeight: 1.65,
                      color: 'var(--ink)',
                      margin: 0,
                    }}
                  >
                    <p style={{ margin: 0 }}>
                      <strong>Abstract:</strong> We formulate the latent representation space{' '}
                      <code>{"\\mathcal{Z} \\in \\mathbb{R}^d"}</code> with continuous loss{' '}
                      <code>{"\\min_\\theta \\mathbb{E}[\\|y - \\hat{y}\\|^2]"}</code>.{' '}
                      <em>{t('Thử nghiệm độ hiển thị sắc nét của font chữ: nghiên cứu khoa học, tối ưu hóa thuật toán, chuyển đổi tri thức và công bố quốc tế.', 'Typography rendering sample: empirical benchmarking, algorithmic optimization, knowledge transfer, and academic dissemination.')}</em>
                    </p>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.ui?.paper_explorer_v2 !== false}
                      onChange={(e) => savePatch({ ui: { paper_explorer_v2: e.target.checked } })}
                    />
                    <span>{t('Bật Paper Explorer v2 & Bộ lọc Hạng Tạp chí Q1–Q4', 'Enable Paper Explorer v2 & Q1–Q4 Journal Filter')}</span>
                  </label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={config.ui?.contextual_actions !== false}
                      onChange={(e) => savePatch({ ui: { contextual_actions: e.target.checked } })}
                    />
                    <span>{t('Hiển thị thanh công cụ ngữ cảnh nhanh trên Header', 'Show contextual quick-action toolbar on Header')}</span>
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
