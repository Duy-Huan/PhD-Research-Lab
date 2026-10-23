import React, { useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useI18n } from '../../shared/state/uiStore';
import type { SkillItem, ModelsResponse } from '../../shared/api/types';
import {
  ArrowUp,
  Plus,
  Sparkles,
  X,
  Square,
  Compass,
  BookOpen,
  FlaskConical,
  Terminal,
  FileText,
  Cpu,
  BrainCircuit,
} from 'lucide-react';

interface ComposerProps {
  onSend: (
    text: string,
    overrides?: { provider?: string; model?: string; reasoning?: string; sources?: string[] }
  ) => void;
  disabled?: boolean;
  isStreaming?: boolean;
  onCancel?: () => void;
  compact?: boolean;
}

export const Composer: React.FC<ComposerProps> = ({
  onSend,
  disabled = false,
  isStreaming = false,
  onCancel,
  compact = false,
}) => {
  const { t } = useI18n();
  const [text, setText] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [reasoningEffort, setReasoningEffort] = useState<string>('auto');
  const [uploadingFile, setUploadingFile] = useState(false);
  const [contextChips, setContextChips] = useState<
    Array<{ id: string; label: string; sourceKey: string }>
  >([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load models catalog from backend /api/models
  const { data: modelsData } = useQuery<ModelsResponse>({
    queryKey: ['models'],
    queryFn: () => api.get<ModelsResponse>('/api/models'),
  });

  // Load skills for slash menu
  const { data: skillsData } = useQuery<{ skills: SkillItem[] }>({
    queryKey: ['skills'],
    queryFn: () => api.get<{ skills: SkillItem[] }>('/api/skills'),
  });

  const skills = skillsData?.skills || [];

  // Requirement #7: Model selector in chatbox ONLY displays models of the provider assigned to the assistant agent!
  const assistantCatalog = modelsData?.agent_catalog?.assistant;
  const assistantEngine = assistantCatalog?.engine || 'cloud:google';
  const assistantLabel = assistantCatalog?.label || assistantEngine;
  const assistantDefaultModel = assistantCatalog?.selected || '';

  // Also check providers list for matching engine if agent_catalog models is empty
  const providerCode = assistantEngine.startsWith('cloud:')
    ? assistantEngine.split(':', 2)[1]
    : assistantEngine;
  const matchingProvider = (modelsData?.providers || []).find(
    (p) => p.id === providerCode || p.id === assistantEngine
  );
  const rawAssistantModels =
    assistantCatalog?.models && assistantCatalog.models.length > 0
      ? assistantCatalog.models
      : matchingProvider?.models || (assistantDefaultModel ? [assistantDefaultModel] : []);
  const assistantModels = Array.from(
    new Set([
      ...(assistantDefaultModel ? [assistantDefaultModel] : []),
      ...rawAssistantModels,
    ])
  ).filter(Boolean);

  // Filter skills when typing '/'
  const slashMatches = text.startsWith('/')
    ? skills.filter(
        (s) =>
          s.name.toLowerCase().includes(text.slice(1).toLowerCase()) ||
          (s.title && s.title.toLowerCase().includes(text.slice(1).toLowerCase()))
      )
    : [];

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;

    const overrides: {
      provider?: string;
      model?: string;
      reasoning?: string;
      sources?: string[];
    } = {};

    // Always use the provider assigned to assistant, and the selected model from that provider
    if (assistantEngine) {
      overrides.provider = assistantEngine;
    }
    if (selectedModel) {
      overrides.model = selectedModel;
    } else if (assistantDefaultModel) {
      overrides.model = assistantDefaultModel;
    }
    if (reasoningEffort && reasoningEffort !== 'auto') {
      overrides.reasoning = reasoningEffort;
    }
    if (contextChips.length > 0) {
      overrides.sources = contextChips.map((c) => c.sourceKey);
    }

    onSend(trimmed, Object.keys(overrides).length > 0 ? overrides : undefined);
    setText('');
  };

  const selectSkill = (skillName: string) => {
    setText(`/${skillName} `);
    textareaRef.current?.focus();
  };

  const removeChip = (id: string) => {
    setContextChips((prev) => prev.filter((c) => c.id !== id));
  };

  const handleFileAttach = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFile(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post<{ id: string; name?: string; filename?: string }>(
        '/api/chat/attachments',
        form
      );
      if (res?.id) {
        setContextChips((prev) => [
          ...prev,
          {
            id: res.id,
            label: res.name || res.filename || file.name,
            sourceKey: `att:${res.id}`,
          },
        ]);
      }
    } catch (err) {
      alert(`Error: ${(err as Error).message}`);
    } finally {
      setUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const quickCommands = [
    { cmd: '/outline', label: 'Outline', icon: Compass },
    { cmd: '/search ', label: 'Search', icon: BookOpen },
    { cmd: '/feynman ', label: 'Feynman', icon: Sparkles },
    { cmd: '/openscience ', label: 'OpenScience', icon: FlaskConical },
    { cmd: '/opencode ', label: 'OpenCode', icon: Terminal },
    { cmd: '/status', label: 'Status', icon: Cpu },
  ];

  return (
    <div
      className="composer-wrap"
      style={{
        padding: compact ? '8px 10px 10px' : '8px 20px 16px',
        background: 'transparent',
        position: 'sticky',
        bottom: 0,
        zIndex: 10,
      }}
    >
      <div style={{ maxWidth: compact ? '100%' : 820, margin: '0 auto', position: 'relative' }}>
        {/* Context Chips Bar */}
        {contextChips.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
            {contextChips.map((chip) => (
              <span
                key={chip.id}
                className="chip"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  background: 'var(--accent-soft)',
                  color: 'var(--accent)',
                  borderColor: 'var(--accent)',
                  borderRadius: 999,
                  fontSize: 11.5,
                }}
              >
                <FileText size={11} />
                <span>{chip.label}</span>
                <button
                  type="button"
                  className="icon sm"
                  onClick={() => removeChip(chip.id)}
                  style={{ width: 15, height: 15, padding: 0 }}
                >
                  <X size={11} />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Slash Suggestions Menu */}
        {text.startsWith('/') && slashMatches.length > 0 && (
          <div
            className="slash-menu"
            style={{
              position: 'absolute',
              bottom: '100%',
              left: 0,
              right: 0,
              marginBottom: 6,
              background: 'var(--panel)',
              border: '1px solid var(--line-2)',
              borderRadius: 14,
              boxShadow: 'var(--shadow)',
              maxHeight: 220,
              overflowY: 'auto',
              zIndex: 100,
              padding: 6,
            }}
          >
            {slashMatches.map((s) => (
              <button
                key={s.name}
                className="btn sm ghost"
                onClick={() => selectSkill(s.name)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  width: '100%',
                  textAlign: 'left',
                  padding: '7px 10px',
                }}
              >
                <b>/{s.name}</b>
                <span className="muted" style={{ fontSize: 12 }}>
                  {s.title || s.description}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* ChatGPT-Style Rounded Pill Box */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            border: '1px solid var(--line-2)',
            borderRadius: 24,
            padding: compact ? '8px 12px' : '10px 16px',
            background: 'var(--panel)',
            boxShadow: '0 4px 20px rgba(0,0,0,0.06)',
          }}
        >
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t(
              'Hỏi bất kỳ điều gì hoặc gõ / để gọi kỹ năng nghiên cứu…',
              'Ask anything, or type / for research skills…'
            )}
            rows={compact ? 1 : 2}
            style={{
              width: '100%',
              border: 'none',
              background: 'transparent',
              outline: 'none',
              resize: 'none',
              font: 'inherit',
              fontSize: 13.5,
              lineHeight: 1.5,
              maxHeight: 160,
            }}
          />

          {/* Bottom Controls Inside Pill (ChatGPT Style: + on left, Reasoning & Scoped Model & Send on right) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 6,
              flexWrap: 'wrap',
            }}
          >
            {/* Left: + Attach + Compact Icon Slash Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
              <input
                ref={fileInputRef}
                type="file"
                style={{ display: 'none' }}
                onChange={handleFileAttach}
              />
              <button
                type="button"
                className="icon sm"
                title={t(
                  'Đính kèm tài liệu PDF, DOCX, CSV, Code…',
                  'Attach PDF, DOCX, CSV, Code…'
                )}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingFile}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  border: '1px solid var(--line-2)',
                  background: 'var(--bg-2)',
                }}
              >
                <Plus size={15} />
              </button>

              {!compact &&
                quickCommands.map((q) => {
                  const Icon = q.icon;
                  return (
                    <button
                      key={q.cmd}
                      type="button"
                      className="btn sm ghost"
                      title={q.cmd}
                      onClick={() => {
                        if (q.cmd === '/status' || q.cmd === '/outline') {
                          onSend(q.cmd);
                        } else {
                          setText(q.cmd);
                          textareaRef.current?.focus();
                        }
                      }}
                      style={{
                        fontSize: 11,
                        padding: '3px 8px',
                        borderRadius: 999,
                        border: '1px solid var(--line)',
                        gap: 4,
                      }}
                    >
                      <Icon size={11} color="var(--accent)" />
                      <span>{q.label}</span>
                    </button>
                  );
                })}
            </div>

            {/* Right: Reasoning Effort Selector + Assistant-Scoped Model Selector + Send Circle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {/* Reasoning Effort (Mức độ tư duy) */}
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '2px 8px',
                  borderRadius: 999,
                  border: '1px solid var(--line)',
                  background: 'var(--bg-2)',
                }}
                title={t('Mức độ tư duy suy luận (Reasoning Effort)', 'Reasoning Effort')}
              >
                <BrainCircuit size={12} color="var(--accent)" />
                <select
                  value={reasoningEffort}
                  onChange={(e) => setReasoningEffort(e.target.value)}
                  style={{
                    fontSize: 11.5,
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--fg)',
                    outline: 'none',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  <option value="auto">{t('Tư duy: Auto', 'Thinking: Auto')}</option>
                  <option value="low">{t('Tư duy: Nhanh (Low)', 'Thinking: Low')}</option>
                  <option value="medium">{t('Tư duy: Vừa (Medium)', 'Thinking: Medium')}</option>
                  <option value="high">{t('Tư duy: Sâu (High)', 'Thinking: High')}</option>
                  <option value="off">{t('Tư duy: Tắt (Off)', 'Thinking: Off')}</option>
                </select>
              </div>

              {/* Assistant Provider Scoped Model Dropdown */}
              <select
                value={selectedModel || assistantDefaultModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                style={{
                  fontSize: 11.5,
                  padding: '4px 10px',
                  borderRadius: 999,
                  border: '1px solid var(--line)',
                  background: 'var(--bg-2)',
                  color: 'var(--fg)',
                  maxWidth: compact ? 145 : 210,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
                title={t(
                  `Chỉ hiển thị model của hãng gán cho Assistant (${assistantLabel})`,
                  `Models of Assistant's assigned provider (${assistantLabel})`
                )}
              >
                {assistantModels.length === 0 ? (
                  <option value="">{assistantLabel} (Default)</option>
                ) : (
                  assistantModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))
                )}
              </select>

              {isStreaming && onCancel ? (
                <button
                  type="button"
                  onClick={onCancel}
                  title={t('Dừng phản hồi', 'Stop generating')}
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: '50%',
                    border: 'none',
                    background: 'var(--danger, #ef4444)',
                    color: '#fff',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                  }}
                >
                  <Square size={12} fill="currentColor" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!text.trim() || disabled}
                  title={t('Gửi (Enter)', 'Send (Enter)')}
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: '50%',
                    border: 'none',
                    background: text.trim() && !disabled ? 'var(--fg)' : 'var(--line-2)',
                    color: text.trim() && !disabled ? 'var(--bg)' : 'var(--muted)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: text.trim() && !disabled ? 'pointer' : 'not-allowed',
                    transition: 'all 0.15s',
                  }}
                >
                  <ArrowUp size={16} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
