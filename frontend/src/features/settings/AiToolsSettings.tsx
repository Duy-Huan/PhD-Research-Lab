import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion, Reorder } from 'motion/react';
import {
  Bot, BookOpen, Cpu, Globe, FolderPen, GripVertical, Plug, Power, ShieldCheck, Search, Copy, Check, X,
  Sparkles, Box, Terminal, Code2, Container, Network, AlertTriangle,
} from 'lucide-react';
import { api } from '../../shared/api/client';
import { useI18n } from '../../shared/state/uiStore';

type Profile = { permissions: string[]; tools: string[] };
type ToolsConfig = { agent_profile?: Profile; provider_pool?: { provider: string; model: string }[] };
type Cfg = { tools?: ToolsConfig; aiws?: { tool_mode?: string } };
type Tool = { id: string; kind: string; description: string; available: boolean; unavailable_reason?: string; permissions: string[] };
type Pending = { id: string; client_name: string };
type ChatGptStatus = { enabled: boolean; mcp_url: string; pending: Pending[]; alerts: unknown[]; cloudflared: boolean; active_tokens: number };

const PERMS = [
  { id: 'read', icon: BookOpen },
  { id: 'compute', icon: Cpu },
  { id: 'network', icon: Globe },
  { id: 'workspace_write', icon: FolderPen },
  { id: 'process', icon: Terminal },
  { id: 'reasoning', icon: Sparkles },
] as const;
const PROVIDERS = ['cli:claude_code', 'cli:codex', 'app:local', 'app:ollama', 'app:gemini', 'app:openai', 'app:anthropic'];
const KIND_ICON: Record<string, React.ElementType> = { native: Sparkles, python: Code2, cli: Terminal, mcp: Network, container: Container };

const tap = { whileHover: { scale: 1.06 }, whileTap: { scale: 0.94 }, transition: { duration: 0.15 } };

/** One card; content collapses so the tab stays short (progressive disclosure). */
const Card: React.FC<{ icon: React.ElementType; title: string; hint?: string; children: React.ReactNode; testId: string }> = ({
  icon: Icon, title, hint, children, testId,
}) => {
  const [open, setOpen] = useState(true);
  return (
    <motion.section layout className="card" data-testid={testId} style={{ padding: 16, marginBottom: 12 }}>
      <button type="button" className="icon" aria-expanded={open} onClick={() => setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', background: 'none', border: 0, cursor: 'pointer' }}>
        <Icon size={18} aria-hidden />
        <strong style={{ fontSize: 15 }}>{title}</strong>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }} style={{ overflow: 'hidden' }}>
            {hint && <p style={{ color: 'var(--muted)', fontSize: 13, margin: '8px 0' }}>{hint}</p>}
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
};

const IconToggle: React.FC<{ on: boolean; label: string; icon: React.ElementType; onClick: () => void; testId: string }> = ({
  on, label, icon: Icon, onClick, testId,
}) => (
  <motion.button type="button" {...tap} aria-pressed={on} aria-label={label} title={label} data-testid={testId} onClick={onClick}
    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 999, cursor: 'pointer',
      border: '1px solid var(--line)', background: on ? 'var(--accent, #c2410c)' : 'transparent', color: on ? '#fff' : 'inherit' }}>
    <Icon size={15} aria-hidden />
    <span style={{ fontSize: 12 }}>{label}</span>
  </motion.button>
);

export const AiToolsSettings: React.FC = () => {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data: cfg } = useQuery({ queryKey: ['config'], queryFn: () => api.get<Cfg>('/api/config') });
  const save = useMutation({
    mutationFn: (patch: Record<string, unknown>) => api.post<Cfg>('/api/config', patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config'] }),
  });
  const profile: Profile = cfg?.tools?.agent_profile || { permissions: ['read', 'compute', 'network', 'workspace_write'], tools: ['*'] };
  const agentMode = (cfg?.aiws?.tool_mode || 'agent') === 'agent';
  const pool = (cfg?.tools?.provider_pool || []).map((m) => m.provider);

  const togglePerm = (p: string) => {
    const next = profile.permissions.includes(p) ? profile.permissions.filter((x) => x !== p) : [...profile.permissions, p];
    save.mutate({ tools: { agent_profile: { ...profile, permissions: next } } });
  };
  const savePool = (ids: string[]) => save.mutate({ tools: { provider_pool: ids } });

  const [query, setQuery] = useState('');
  const { data: tools } = useQuery({
    queryKey: ['tool-registry', query],
    queryFn: () => (query.trim()
      ? api.get<{ results: Tool[] }>(`/api/tools/search?q=${encodeURIComponent(query)}`).then((r) => r.results)
      : api.get<{ tools: Tool[] }>('/api/tools').then((r) => r.tools)),
  });

  const { data: gpt } = useQuery({
    queryKey: ['chatgpt-connector'],
    queryFn: () => api.get<ChatGptStatus>('/api/tools/clients/chatgpt'),
    refetchInterval: 3000,
  });
  const gptAction = useMutation({
    mutationFn: ({ action, body }: { action: string; body?: unknown }) => api.post(`/api/tools/clients/chatgpt/${action}`, body ?? {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['chatgpt-connector'] }),
  });
  const { data: clients } = useQuery({
    queryKey: ['mcp-clients'],
    queryFn: () => api.get<{ antigravity: { registered: boolean } }>('/api/tools/clients'),
  });
  const agy = useMutation({
    mutationFn: (action: 'register' | 'unregister') => api.post(`/api/tools/clients/antigravity/${action}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcp-clients'] }),
  });
  const { data: skills } = useQuery({
    queryKey: ['hermes-skills'],
    queryFn: () => api.get<{ project: string[]; shared: string[]; shareable: string[] }>('/api/runtimes/hermes/skills'),
  });
  const share = useMutation({
    mutationFn: (skill: string) => api.post('/api/runtimes/hermes/share-skill', { skill, approved_by: 'owner' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hermes-skills'] }),
  });
  const [copied, setCopied] = useState(false);
  const unused = useMemo(() => PROVIDERS.filter((p) => !pool.includes(p)), [pool]);

  if (!cfg) return <div data-testid="ai-tools-settings" aria-busy="true" />; // never show or save defaults before the real config

  return (
    <div data-testid="ai-tools-settings">
      <Card icon={Bot} title={t('aiTools.agent')} hint={t('aiTools.permissionsHint')} testId="ai-tools-agent">
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <input type="checkbox" checked={agentMode} data-testid="agent-mode-toggle"
            onChange={(e) => save.mutate({ aiws: { tool_mode: e.target.checked ? 'agent' : 'legacy' } })} />
          <span>{t('aiTools.agentMode')}</span>
          <span title={t('aiTools.agentModeHint')} style={{ color: 'var(--muted)', fontSize: 12 }}>ⓘ</span>
        </label>
        <div role="group" aria-label={t('aiTools.permissions')} style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {PERMS.map(({ id, icon }) => (
            <IconToggle key={id} on={profile.permissions.includes(id)} label={t(`aiTools.perm.${id}`)} icon={icon}
              onClick={() => togglePerm(id)} testId={`perm-${id}`} />
          ))}
        </div>
      </Card>

      <Card icon={Plug} title={t('aiTools.providers')} hint={t('aiTools.providersHint')} testId="ai-tools-providers">
        <Reorder.Group axis="y" values={pool} onReorder={savePool} style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {pool.map((id) => (
            <Reorder.Item key={id} value={id} data-testid={`pool-${id}`}
              style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', border: '1px solid var(--line)', borderRadius: 8, marginBottom: 6, cursor: 'grab', background: 'var(--panel)' }}>
              <GripVertical size={14} aria-hidden />
              <span style={{ flex: 1, fontFamily: 'monospace', fontSize: 13 }}>{id}</span>
              <motion.button type="button" {...tap} className="icon" aria-label={t('aiTools.remove')} title={t('aiTools.remove')}
                onClick={() => savePool(pool.filter((p) => p !== id))}><X size={14} /></motion.button>
            </Reorder.Item>
          ))}
        </Reorder.Group>
        {unused.length > 0 && (
          <select aria-label={t('aiTools.addProvider')} value="" data-testid="pool-add"
            onChange={(e) => e.target.value && savePool([...pool, e.target.value])}>
            <option value="">+ {t('aiTools.addProvider')}</option>
            {unused.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        )}
      </Card>

      <Card icon={Box} title={t('aiTools.registry')} testId="ai-tools-registry">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
          <Search size={14} aria-hidden />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('aiTools.searchTools')}
            aria-label={t('aiTools.searchTools')} style={{ flex: 1 }} data-testid="tool-search" />
        </div>
        <motion.ul layout style={{ listStyle: 'none', padding: 0, margin: 0, maxHeight: 280, overflowY: 'auto' }}>
          <AnimatePresence initial={false}>
            {(tools || []).slice(0, 60).map((tool) => {
              const Icon = KIND_ICON[tool.kind] || Sparkles;
              return (
                <motion.li key={tool.id} layout initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  title={tool.available ? tool.description : tool.unavailable_reason || t('aiTools.unavailable')}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid var(--line)' }}>
                  <span aria-label={tool.available ? t('aiTools.available') : t('aiTools.unavailable')}
                    style={{ width: 8, height: 8, borderRadius: 8, background: tool.available ? '#16a34a' : '#9ca3af' }} />
                  <Icon size={14} aria-label={tool.kind} />
                  <span style={{ fontFamily: 'monospace', fontSize: 12, flex: 1 }}>{tool.id}</span>
                </motion.li>
              );
            })}
          </AnimatePresence>
          {tools && tools.length === 0 && <li style={{ color: 'var(--muted)' }}>{t('aiTools.noTools')}</li>}
        </motion.ul>
      </Card>

      <Card icon={ShieldCheck} title={t('aiTools.chatgpt')} hint={t('aiTools.chatgptHint')} testId="ai-tools-chatgpt">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span data-testid="chatgpt-state" style={{ fontSize: 12 }}>{gpt?.enabled ? t('aiTools.on') : t('aiTools.off')}</span>
          {!gpt?.enabled ? (
            <motion.button type="button" {...tap} onClick={() => gptAction.mutate({ action: 'enable' })} disabled={!gpt?.cloudflared}
              aria-label={t('aiTools.enable')}><Power size={14} /> {t('aiTools.enable')}</motion.button>
          ) : (
            <motion.button type="button" {...tap} onClick={() => gptAction.mutate({ action: 'kill' })} aria-label={t('aiTools.kill')}
              style={{ color: '#b91c1c' }}><Power size={14} /> {t('aiTools.kill')}</motion.button>
          )}
          {gpt?.mcp_url && (
            <motion.button type="button" {...tap} aria-label={t('aiTools.copyUrl')} title={gpt.mcp_url}
              onClick={() => { void navigator.clipboard?.writeText(gpt.mcp_url); setCopied(true); }}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </motion.button>
          )}
          {gpt && gpt.alerts.length > 0 && (
            <span title={t('aiTools.alerts')} style={{ color: '#b45309', display: 'inline-flex', gap: 4 }}>
              <AlertTriangle size={14} aria-hidden /> {gpt.alerts.length}
            </span>
          )}
        </div>
        {gpt && !gpt.cloudflared && <p style={{ fontSize: 12, color: 'var(--muted)' }}>{t('aiTools.needsCloudflared')}</p>}
        {gpt && gpt.pending.length > 0 && (
          <div data-testid="chatgpt-pending" style={{ marginTop: 8 }}>
            <strong style={{ fontSize: 13 }}>{t('aiTools.pending')}</strong>
            {gpt.pending.map((p) => (
              <div key={p.id} style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 4 }}>
                <span style={{ fontFamily: 'monospace' }}>{p.id.slice(0, 6)}</span>
                <motion.button type="button" {...tap} onClick={() => gptAction.mutate({ action: 'approve', body: { request_id: p.id } })}>
                  <Check size={14} /> {t('aiTools.approve')}</motion.button>
                <motion.button type="button" {...tap} onClick={() => gptAction.mutate({ action: 'deny', body: { request_id: p.id } })}>
                  <X size={14} /> {t('aiTools.deny')}</motion.button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card icon={Network} title={t('aiTools.antigravity')} hint={t('aiTools.antigravityHint')} testId="ai-tools-antigravity">
        <motion.button type="button" {...tap} onClick={() => agy.mutate(clients?.antigravity?.registered ? 'unregister' : 'register')}>
          {clients?.antigravity?.registered ? t('aiTools.unregister') : t('aiTools.register')}
        </motion.button>
      </Card>

      <Card icon={Sparkles} title={t('aiTools.hermes')} hint={t('aiTools.hermesHint')} testId="ai-tools-hermes">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {(skills?.shareable || []).map((s) => (
            <motion.button type="button" key={s} {...tap} onClick={() => share.mutate(s)} title={t('aiTools.shareSkill')}>
              ↗ {s}
            </motion.button>
          ))}
        </div>
        {skills && skills.shared.length > 0 && (
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>{t('aiTools.sharedSkills')}: {skills.shared.join(', ')}</p>
        )}
      </Card>
    </div>
  );
};

export default AiToolsSettings;
