import React, { useState, useRef, useEffect } from 'react';
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
  AlertCircle,
  ExternalLink,
  Bot,
  Eye,
  Copy,
  Image as ImageIcon,
} from 'lucide-react';

interface AttachedImage {
  id: string;
  name: string;
  url: string;
  size: number;
  width?: number;
  height?: number;
}

interface AttachedDocument {
  id: string;
  name: string;
  content: string;
  size: number;
  lines: number;
  chars: number;
  attId?: string;
}

const formatBytes = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

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
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [reasoningEffort, setReasoningEffort] = useState<string>('auto');
  const [uploadingFile, setUploadingFile] = useState(false);
  const [toolsMenuOpen, setToolsMenuOpen] = useState(false);
  const [slashIndex, setSlashIndex] = useState(0);
  const [contextChips, setContextChips] = useState<
    Array<{ id: string; label: string; sourceKey: string }>
  >([]);
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const [attachedDocuments, setAttachedDocuments] = useState<AttachedDocument[]>([]);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<AttachedDocument | null>(null);
  const [previewImage, setPreviewImage] = useState<AttachedImage | null>(null);
  const [copiedDoc, setCopiedDoc] = useState(false);
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
  const assistantEngine = assistantCatalog?.engine || '';
  const assistantLabel = assistantCatalog?.label || assistantEngine;
  const assistantDefaultModel = assistantCatalog?.selected || '';

  // Also check providers list for matching engine if agent_catalog models is empty
  const providerCode = assistantEngine.replace(/^(cloud|cli|app|runtime):/, '');
  const matchingProvider = (modelsData?.providers || []).find(
    (p) => p.id === assistantCatalog?.provider_id || p.id === providerCode || p.id === assistantEngine || p.id === `cli:${providerCode}` || p.id === `app:${providerCode}` || p.id === `runtime:${providerCode}`
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

  const isCliOrSub =
    ['codex', 'claude_code', 'antigravity', 'gemini_cli'].includes(providerCode) ||
    assistantEngine.startsWith('cli:');
  const isAuthExpired =
    matchingProvider?.state === 'AUTH_EXPIRED' ||
    matchingProvider?.state === 'UNAVAILABLE' ||
    (matchingProvider?.available === false && isCliOrSub);

  useEffect(() => { setSelectedModel(null); }, [assistantEngine, assistantDefaultModel]);

  // Filter skills when typing '/'
  const slashMatches = text.startsWith('/')
    ? skills.filter(
        (s) =>
          s.name.toLowerCase().includes(text.slice(1).toLowerCase()) ||
          (s.title && s.title.toLowerCase().includes(text.slice(1).toLowerCase()))
      )
    : [];

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Slash commands keyboard navigation & Tab autocomplete
    if (text.startsWith('/') && slashMatches.length > 0) {
      if (e.key === 'Tab') {
        e.preventDefault();
        const selected = slashMatches[slashIndex] || slashMatches[0];
        if (selected) {
          selectSkill(selected.name);
        }
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSlashIndex((prev) => (prev + 1) % slashMatches.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSlashIndex((prev) => (prev - 1 + slashMatches.length) % slashMatches.length);
        return;
      }
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const selected = slashMatches[slashIndex] || slashMatches[0];
        if (selected) {
          selectSkill(selected.name);
        }
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setText('');
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const uploadAndAttachFile = async (file: File) => {
    setUploadingFile(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post<{
        id: string;
        name?: string;
        filename?: string;
        kind?: string;
        width?: number;
        height?: number;
      }>('/api/chat/attachments', form);

      if (res?.id) {
        const attId = res.id;
        const name = res.name || res.filename || file.name;
        const isImg = res.kind === 'image' || file.type.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|tiff?)$/i.test(name);

        if (isImg) {
          setAttachedImages((prev) => [
            ...prev,
            {
              id: attId,
              name,
              url: `/api/chat/attachments/${attId}/file`,
              size: file.size,
              width: res.width,
              height: res.height,
            },
          ]);
        }

        setContextChips((prev) => {
          if (prev.some((c) => c.id === attId)) return prev;
          return [
            ...prev,
            {
              id: attId,
              label: name,
              sourceKey: `att:${attId}`,
            },
          ];
        });
      }
    } catch (err) {
      alert(`Error: ${(err as Error).message}`);
    } finally {
      setUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const uploadTextAttachment = async (file: File, docLocalId: string) => {
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await api.post<{ id: string }>('/api/chat/attachments', form);
      if (res?.id) {
        setAttachedDocuments((prev) =>
          prev.map((d) => (d.id === docLocalId ? { ...d, attId: res.id } : d))
        );
        setContextChips((prev) => {
          if (prev.some((c) => c.id === res.id)) return prev;
          return [
            ...prev,
            {
              id: res.id,
              label: file.name,
              sourceKey: `att:${res.id}`,
            },
          ];
        });
      }
    } catch (err) {
      console.warn('Could not register text attachment in backend:', err);
    }
  };

  const handlePaste = async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    // 1. Check for image files in clipboard items (e.g. screenshot Win+Shift+S)
    const items = Array.from(e.clipboardData.items || []);
    const imageItem = items.find((item) => item.type.startsWith('image/'));
    if (imageItem) {
      e.preventDefault();
      const file = imageItem.getAsFile();
      if (file) {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(11, 19);
        const namedFile = new File([file], `screenshot_${timestamp}.png`, { type: file.type || 'image/png' });
        await uploadAndAttachFile(namedFile);
      }
      return;
    }

    // 2. Check for long text pasted into composer
    const pastedText = e.clipboardData.getData('text');
    if (pastedText && (pastedText.length > 600 || pastedText.split('\n').length > 10)) {
      e.preventDefault();
      const docLocalId = `doc_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
      const lines = pastedText.split('\n').length;
      const chars = pastedText.length;
      const filename = `pasted_prompt_${new Date().toLocaleTimeString().replace(/:/g, '')}.txt`;
      const blob = new Blob([pastedText], { type: 'text/plain;charset=utf-8' });
      const textFile = new File([blob], filename, { type: 'text/plain' });

      setAttachedDocuments((prev) => [
        ...prev,
        {
          id: docLocalId,
          name: filename,
          content: pastedText,
          size: blob.size,
          lines,
          chars,
        },
      ]);

      await uploadTextAttachment(textFile, docLocalId);
      return;
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);

    const files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;

    for (const file of files) {
      if (file.type.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp|tiff?)$/i.test(file.name)) {
        await uploadAndAttachFile(file);
      } else if (
        file.type.startsWith('text/') ||
        /\.(txt|md|py|json|csv|tsv|log|tex|js|ts|tsx|jsx|html|css|yaml|yml|sh|bat)$/i.test(file.name)
      ) {
        try {
          const content = await file.text();
          if (content.length > 600 || content.split('\n').length > 10) {
            const docLocalId = `doc_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
            const lines = content.split('\n').length;
            setAttachedDocuments((prev) => [
              ...prev,
              {
                id: docLocalId,
                name: file.name,
                content,
                size: file.size,
                lines,
                chars: content.length,
              },
            ]);
            await uploadTextAttachment(file, docLocalId);
          } else {
            await uploadAndAttachFile(file);
          }
        } catch {
          await uploadAndAttachFile(file);
        }
      } else {
        await uploadAndAttachFile(file);
      }
    }
  };

  const removeImage = (id: string) => {
    setAttachedImages((prev) => prev.filter((img) => img.id !== id));
    setContextChips((prev) => prev.filter((c) => c.id !== id && c.sourceKey !== `att:${id}`));
  };

  const removeDocument = (id: string, attId?: string) => {
    setAttachedDocuments((prev) => prev.filter((d) => d.id !== id));
    if (attId) {
      setContextChips((prev) => prev.filter((c) => c.id !== attId && c.sourceKey !== `att:${attId}`));
    }
  };

  const handleSend = () => {
    const trimmed = text.trim();
    const hasDocuments = attachedDocuments.length > 0;
    const hasImages = attachedImages.length > 0;

    if (!trimmed && !hasDocuments && !hasImages) return;
    if (disabled) return;

    let finalPrompt = trimmed;
    if (hasDocuments) {
      const docSections = attachedDocuments
        .map(
          (d) =>
            `\n\n--- [Đính kèm: ${d.name} (${d.lines} dòng, ${formatBytes(d.size)})] ---\n${d.content}\n--- [Hết file ${d.name}] ---`
        )
        .join('');
      if (!finalPrompt) {
        finalPrompt =
          t(
            'Vui lòng đọc và phân tích tài liệu đính kèm bên dưới:',
            'Please inspect and analyze the attached document below:'
          ) + docSections;
      } else {
        finalPrompt = finalPrompt + docSections;
      }
    }

    const overrides: {
      provider?: string;
      model?: string;
      reasoning?: string;
      sources?: string[];
    } = {};

    // Normalize CLI shorthands properly so backend accepts it seamlessly
    const mappedProvider = /^(app|cli):/.test(assistantEngine) ? assistantEngine
      : assistantCatalog?.provider_id || (assistantEngine ? `${isCliOrSub ? 'cli' : providerCode === 'hermes' ? 'runtime' : 'app'}:${providerCode === 'claude' ? 'claude_code' : providerCode === 'google' ? 'gemini' : providerCode}` : '');

    if (mappedProvider) {
      overrides.provider = mappedProvider;
    }
    overrides.model = selectedModel ?? assistantDefaultModel;
    if (reasoningEffort && reasoningEffort !== 'auto') {
      overrides.reasoning = reasoningEffort;
    }
    if (contextChips.length > 0) {
      overrides.sources = contextChips.map((c) => c.sourceKey);
    }

    onSend(finalPrompt, Object.keys(overrides).length > 0 ? overrides : undefined);
    setText('');
    setAttachedDocuments([]);
    setAttachedImages([]);
    setToolsMenuOpen(false);
  };

  const selectSkill = (skillName: string) => {
    setText(`/${skillName} `);
    textareaRef.current?.focus();
  };

  const removeChip = (id: string) => {
    setContextChips((prev) => prev.filter((c) => c.id !== id));
    setAttachedImages((prev) => prev.filter((img) => img.id !== id));
    setAttachedDocuments((prev) => prev.filter((d) => d.attId !== id));
  };

  const handleFileAttach = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadAndAttachFile(file);
  };

  const quickCommands = [
    { cmd: '/paperorchestra ', label: 'PaperOrchestra', icon: FileText },
    { cmd: '/outline', label: 'Outline', icon: Compass },
    { cmd: '/search ', label: 'Search', icon: BookOpen },
    { cmd: '/lit ', label: t('Khảo sát tài liệu', 'Literature'), icon: BookOpen },
    { cmd: '/science ', label: t('Phân tích khoa học', 'Scientific analysis'), icon: Bot },
    { cmd: '/phdlab ', label: 'PhD Lab Native', icon: Bot },
    { cmd: '/code ', label: t('Lập trình native', 'Native coding'), icon: Terminal },
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
            {slashMatches.map((s, idx) => (
              <button
                key={s.name}
                className={`btn sm ghost ${idx === slashIndex ? 'active' : ''}`}
                onClick={() => selectSkill(s.name)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  width: '100%',
                  textAlign: 'left',
                  padding: '7px 10px',
                  background: idx === slashIndex ? 'var(--accent-soft)' : 'transparent',
                  borderRadius: 8,
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

        {/* Unauthenticated CLI / Subscription Banner */}
        {isCliOrSub && isAuthExpired && (
          <div
            style={{
              padding: '6px 12px',
              borderRadius: 12,
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              marginBottom: 4,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
              <AlertCircle size={14} color="#ef4444" style={{ flexShrink: 0 }} />
              <span className="ellipsis" style={{ color: 'var(--ink)', fontSize: 11.5 }}>
                {t(
                  `Chưa đăng nhập ${assistantLabel} trên máy tính.`,
                  `Not signed in to ${assistantLabel} on this computer.`
                )}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
              <button
                type="button"
                className="btn sm accent"
                style={{ padding: '4px 10px', minHeight: 26, minWidth: 28, fontSize: 11, borderRadius: 6 }}
                onClick={async () => {
                  await api.post(`/api/providers/${providerCode}/connect`, { mode: 'terminal' });
                  alert(t(`Đã mở terminal đăng nhập cho ${assistantLabel}`, `Opened terminal login for ${assistantLabel}`));
                }}
                title={t('Mở Terminal trên máy để đăng nhập CLI', 'Open terminal to log in CLI')}
                aria-label={t('Mở Terminal trên máy để đăng nhập CLI', 'Open terminal to log in CLI')}
              >
                <Terminal size={11} style={{ marginRight: 3 }} />
                <span>{t('Đăng nhập CLI', 'Terminal Login')}</span>
              </button>
              <button
                type="button"
                className="btn sm ghost"
                style={{ padding: '4px 10px', minHeight: 26, minWidth: 28, fontSize: 11, borderRadius: 6 }}
                onClick={async () => {
                  await api.post(`/api/providers/${providerCode}/connect`, { mode: 'app' });
                }}
                title={t('Mở ứng dụng CLI đã cài trên máy', 'Open the installed native CLI app')}
                aria-label={t('Mở ứng dụng CLI', 'Open CLI App')}
              >
                <ExternalLink size={11} style={{ marginRight: 3 }} />
                <span>{t('Mở ứng dụng CLI', 'Open CLI App')}</span>
              </button>
            </div>
          </div>
        )}

        {/* ChatGPT-Style Rounded Pill Box */}
        <div
          onDragOver={handleDragOver}
          onDragEnter={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            border: isDraggingOver ? '2px dashed var(--accent)' : '1px solid var(--line-2)',
            borderRadius: 24,
            padding: compact ? '8px 12px' : '10px 16px',
            background: isDraggingOver ? 'var(--accent-soft)' : 'var(--panel)',
            color: 'var(--ink)',
            boxShadow: '0 4px 20px rgba(0,0,0,0.06)',
            transition: 'all 0.15s ease',
            position: 'relative',
          }}
        >
          {/* Drag Overlay Hint */}
          {isDraggingOver && (
            <div
              style={{
                padding: '8px 12px',
                textAlign: 'center',
                color: 'var(--accent)',
                fontWeight: 600,
                fontSize: 12.5,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              <ImageIcon size={18} />
              <span>{t('Thả hình ảnh hoặc file văn bản vào đây để đính kèm…', 'Drop image or text file here to attach…')}</span>
            </div>
          )}

          {/* Attached Images Preview Strip */}
          {attachedImages.length > 0 && (
            <div
              data-testid="attached-images-strip"
              style={{
                display: 'flex',
                gap: 8,
                flexWrap: 'wrap',
                paddingBottom: 6,
                borderBottom: '1px solid var(--line)',
              }}
            >
              {attachedImages.map((img) => (
                <div
                  key={img.id}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '3px 8px 3px 4px',
                    borderRadius: 10,
                    background: 'var(--bg-2)',
                    border: '1px solid var(--line-2)',
                    fontSize: 11.5,
                  }}
                >
                  <img
                    src={img.url}
                    alt={img.name}
                    onClick={() => setPreviewImage(img)}
                    style={{
                      width: 32,
                      height: 32,
                      objectFit: 'cover',
                      borderRadius: 6,
                      cursor: 'pointer',
                      border: '1px solid var(--line)',
                    }}
                    title={t('Bấm để xem ảnh lớn', 'Click to view full image')}
                  />
                  <div style={{ display: 'flex', flexDirection: 'column', maxWidth: 120 }}>
                    <span className="ellipsis" style={{ fontWeight: 500 }} title={img.name}>
                      {img.name}
                    </span>
                    <span className="muted" style={{ fontSize: 10 }}>
                      {formatBytes(img.size)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="icon sm"
                    onClick={() => removeImage(img.id)}
                    style={{ width: 16, height: 16, padding: 0 }}
                    title={t('Xóa ảnh', 'Remove image')}
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Attached Long Prompts / .txt Cards Strip */}
          {attachedDocuments.length > 0 && (
            <div
              data-testid="attached-documents-strip"
              style={{
                display: 'flex',
                gap: 8,
                flexWrap: 'wrap',
                paddingBottom: 6,
                borderBottom: '1px solid var(--line)',
              }}
            >
              {attachedDocuments.map((doc) => (
                <div
                  key={doc.id}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 10px',
                    borderRadius: 12,
                    background: 'var(--accent-soft)',
                    border: '1px solid var(--accent)',
                    color: 'var(--ink)',
                    fontSize: 12,
                  }}
                >
                  <FileText size={16} color="var(--accent)" style={{ flexShrink: 0 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, maxWidth: 160 }}>
                    <b className="ellipsis" style={{ fontSize: 11.5 }} title={doc.name}>
                      {doc.name}
                    </b>
                    <span style={{ fontSize: 10.5, color: 'var(--muted)' }}>
                      {doc.lines} {t('dòng', 'lines')} · {formatBytes(doc.size)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn sm ghost"
                    onClick={() => setPreviewDoc(doc)}
                    style={{ padding: '2px 6px', fontSize: 11, height: 22, borderRadius: 6, gap: 3 }}
                    title={t('Xem nội dung văn bản', 'Preview text content')}
                  >
                    <Eye size={11} />
                    <span>{t('Xem', 'View')}</span>
                  </button>
                  <button
                    type="button"
                    className="icon sm"
                    onClick={() => removeDocument(doc.id, doc.attId)}
                    style={{ width: 18, height: 18, padding: 0 }}
                    title={t('Gỡ bỏ tài liệu', 'Remove document')}
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
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
              color: 'var(--ink)',
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
                  color: 'var(--ink)',
                }}
              >
                <Plus size={15} />
              </button>

              {/* Single compact icon for Research Utilities (User Request #3: gom lai trong mot icon nho, click vao xo ra) */}
              <div style={{ position: 'relative' }}>
                <button
                  type="button"
                  className="icon sm"
                  title={t('Tiện ích & Kỹ năng nghiên cứu', 'Research Utilities')}
                  onClick={() => setToolsMenuOpen((prev) => !prev)}
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    border: '1px solid var(--line-2)',
                    background: toolsMenuOpen ? 'var(--accent-soft)' : 'var(--bg-2)',
                    color: toolsMenuOpen ? 'var(--accent)' : 'var(--ink)',
                  }}
                >
                  <Sparkles size={14} />
                </button>

                {toolsMenuOpen && (
                  <>
                    <div
                      style={{ position: 'fixed', inset: 0, zIndex: 90 }}
                      onClick={() => setToolsMenuOpen(false)}
                    />
                    <div
                      className="tools-dropdown"
                      style={{
                        position: 'absolute',
                        bottom: '100%',
                        left: 0,
                        marginBottom: 6,
                        background: 'var(--panel)',
                        border: '1px solid var(--line-2)',
                        borderRadius: 12,
                        boxShadow: 'var(--shadow)',
                        padding: 6,
                        zIndex: 95,
                        minWidth: 230,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2,
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          color: 'var(--muted)',
                          padding: '4px 8px',
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em',
                        }}
                      >
                        {t('Tiện ích nghiên cứu', 'Research Utilities')}
                      </div>
                      {quickCommands.map((q) => {
                        const Icon = q.icon;
                        return (
                          <button
                            key={q.cmd}
                            type="button"
                            className="btn sm ghost"
                            onClick={() => {
                              setToolsMenuOpen(false);
                              if (q.cmd === '/status' || q.cmd === '/outline') {
                                onSend(q.cmd);
                              } else {
                                setText(q.cmd);
                                textareaRef.current?.focus();
                              }
                            }}
                            style={{
                              justifyContent: 'flex-start',
                              padding: '6px 10px',
                              borderRadius: 8,
                              fontSize: 12.5,
                              gap: 8,
                              width: '100%',
                              textAlign: 'left',
                            }}
                          >
                            <Icon size={14} color="var(--accent)" />
                            <span style={{ fontWeight: 500 }}>{q.label}</span>
                            <span className="muted" style={{ marginLeft: 'auto', fontSize: 11 }}>
                              {q.cmd.trim()}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Right: Reasoning Effort Selector + Assistant-Scoped Model Selector + Send Circle */}
            <div className="composer-model-controls" style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, maxWidth: '100%', flexWrap: 'wrap' }}>
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
                title={t('Mức độ tư duy suy luận', 'Reasoning Effort')}
              >
                <BrainCircuit size={12} color="var(--accent)" />
                <select
                  aria-label={t('Mức độ tư duy suy luận', 'Reasoning Effort')}
                  value={reasoningEffort}
                  onChange={(e) => setReasoningEffort(e.target.value)}
                  style={{
                    fontSize: 11.5,
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--ink)',
                    outline: 'none',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  <option value="auto">{t('Tư duy: Tự động', 'Thinking: Auto')}</option>
                  <option value="low">{t('Tư duy: Nhanh', 'Thinking: Low')}</option>
                  <option value="medium">{t('Tư duy: Vừa', 'Thinking: Medium')}</option>
                  <option value="high">{t('Tư duy: Chuyên sâu', 'Thinking: High')}</option>
                  <option value="off">{t('Tư duy: Tắt', 'Thinking: Off')}</option>
                </select>
              </div>

              {/* Assistant Provider Scoped Model Dropdown */}
              <select
                value={selectedModel ?? assistantDefaultModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                style={{
                  fontSize: 11.5,
                  padding: '4px 10px',
                  borderRadius: 999,
                  border: '1px solid var(--line)',
                  background: 'var(--bg-2)',
                  color: 'var(--ink)',
                  maxWidth: compact ? 145 : 210,
                  minWidth: 0,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
                title={t(
                  `Chỉ hiển thị model của hãng gán cho Assistant (${assistantLabel})`,
                  `Models of Assistant's assigned provider (${assistantLabel})`
                )}
              >
                <option value="">{assistantLabel} (Default)</option>
                {assistantModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
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
                  disabled={(!text.trim() && attachedDocuments.length === 0 && attachedImages.length === 0) || disabled}
                  title={t('Gửi', 'Send (Enter)')}
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: '50%',
                    border: 'none',
                    background: (text.trim() || attachedDocuments.length > 0 || attachedImages.length > 0) && !disabled ? 'var(--accent)' : 'var(--line-2)',
                    color: (text.trim() || attachedDocuments.length > 0 || attachedImages.length > 0) && !disabled ? 'var(--accent-ink)' : 'var(--muted)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: (text.trim() || attachedDocuments.length > 0 || attachedImages.length > 0) && !disabled ? 'pointer' : 'not-allowed',
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

      {/* Document Content Preview Modal */}
      {previewDoc && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setPreviewDoc(null)}
        >
          <div
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line-2)',
              borderRadius: 16,
              maxWidth: 720,
              width: '100%',
              maxHeight: '80vh',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: 'var(--shadow)',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: '12px 18px',
                borderBottom: '1px solid var(--line)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <FileText size={18} color="var(--accent)" />
                <b style={{ fontSize: 13.5 }}>{previewDoc.name}</b>
                <span className="muted" style={{ fontSize: 12 }}>
                  ({previewDoc.lines} {t('dòng', 'lines')} · {formatBytes(previewDoc.size)})
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  type="button"
                  className="btn sm ghost"
                  onClick={() => {
                    navigator.clipboard.writeText(previewDoc.content);
                    setCopiedDoc(true);
                    setTimeout(() => setCopiedDoc(false), 2000);
                  }}
                  style={{ fontSize: 11.5, gap: 4 }}
                >
                  <Copy size={12} />
                  <span>{copiedDoc ? t('Đã chép!', 'Copied!') : t('Sao chép', 'Copy')}</span>
                </button>
                <button
                  type="button"
                  className="icon sm"
                  onClick={() => setPreviewDoc(null)}
                >
                  <X size={15} />
                </button>
              </div>
            </div>
            <div
              style={{
                padding: 16,
                overflowY: 'auto',
                flex: 1,
                fontFamily: 'monospace',
                fontSize: 12.5,
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                background: 'var(--bg-2)',
              }}
            >
              {previewDoc.content}
            </div>
          </div>
        </div>
      )}

      {/* Image Preview Lightbox Modal */}
      {previewImage && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.75)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
          }}
          onClick={() => setPreviewImage(null)}
        >
          <div
            style={{
              position: 'relative',
              maxWidth: 900,
              maxHeight: '90vh',
              background: 'var(--panel)',
              borderRadius: 14,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: '10px 16px',
                borderBottom: '1px solid var(--line)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span style={{ fontWeight: 600, fontSize: 13 }}>{previewImage.name}</span>
              <button
                type="button"
                className="icon sm"
                onClick={() => setPreviewImage(null)}
              >
                <X size={15} />
              </button>
            </div>
            <div
              style={{
                padding: 16,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#000',
                overflow: 'auto',
              }}
            >
              <img
                src={previewImage.url}
                alt={previewImage.name}
                style={{
                  maxWidth: '100%',
                  maxHeight: '75vh',
                  objectFit: 'contain',
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
