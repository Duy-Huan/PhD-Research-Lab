import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import type { Topic, LibraryPaper } from '../../shared/api/types';
import { Plus, Check, Brain, Folder, Search, ShieldCheck, BookOpen } from 'lucide-react';

export const TopicView: React.FC = () => {
  const queryClient = useQueryClient();
  const { t, language } = useI18n();
  const { project, activeTopicId, setActiveTopic, openDrawer } = useUIStore();
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [keywordsText, setKeywordsText] = useState('');
  const [subTab, setSubTab] = useState<'list' | 'papers' | 'ledger'>('list');

  const { data: topicData, isLoading } = useQuery<{ topics: Topic[] }>({
    queryKey: ['topics', project?.data_dir],
    queryFn: () => api.get<{ topics: Topic[] }>('/api/research/topics'),
  });

  const topics = topicData?.topics || [];
  useEffect(() => {
    if (topics.length === 1 && activeTopicId !== topics[0].id) setActiveTopic(topics[0]);
  }, [topicData, activeTopicId, setActiveTopic]);

  // Topic papers
  const { data: papersData } = useQuery<{ papers: LibraryPaper[] }>({
    queryKey: ['topic-papers', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/papers`),
    enabled: !!activeTopicId && subTab === 'papers',
  });

  // Topic append-only ledger audit
  const { data: ledgerData } = useQuery<{ ok: boolean; entries: any[] }>({
    queryKey: ['topic-ledger', activeTopicId],
    queryFn: () => api.get(`/api/research/topics/${activeTopicId}/ledger`),
    enabled: !!activeTopicId && subTab === 'ledger',
  });

  const createMutation = useMutation({
    mutationFn: (newTopic: {
      title: string;
      description: string;
      keywords: string[];
      sources: string[];
    }) => api.post<Topic>('/api/research/topics', newTopic),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['topics'] });
      setActiveTopic(created);
      setShowCreate(false);
      setTitle('');
      setDescription('');
      setKeywordsText('');
    },
  });

  const discoverMutation = useMutation({
    mutationFn: (tid: string) => api.post(`/api/research/topics/${tid}/discover`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['topic-papers', activeTopicId] });
      alert(t('Đã kích hoạt tiến trình tìm kiếm tài liệu khoa học!', 'Academic literature discovery job triggered!'));
    },
  });

  const curateMutation = useMutation({
    mutationFn: ({ pid, level }: { pid: string; level: number }) =>
      api.post(`/api/research/topics/${activeTopicId}/papers/${pid}/curate`, {
        level,
        state: level >= 3 ? 'included' : 'candidate',
        note: 'Curated via React Topic Explorer',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['topic-papers', activeTopicId] });
    },
  });

  return (
    <div className="topic-view" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Brain size={18} color="var(--accent)" />
          <span>{t('Bài báo và kho tri thức của project', 'Project paper and knowledge base')}</span>
        </h4>
        <button
          className="btn sm accent"
          type="button"
          disabled={topics.length > 0}
          title={topics.length ? t('Tạo project khác cho bài báo mới.', 'Create another project for a new paper.') : undefined}
          onClick={() => setShowCreate(!showCreate)}
        >
          <Plus size={14} style={{ marginRight: 4 }} />
          <span>{t('Xác định chủ đề bài báo', 'Define the paper topic')}</span>
        </button>
      </div>
      {topics.length > 0 && <p className="muted">{t('Mỗi project dành cho một bài báo/chủ đề; giữ nhiều thí nghiệm trong code/. Tạo project khác để nghiên cứu chủ đề mới.', 'Each project represents one paper/topic, with multiple experiments in code/. Create another project for a new topic.')}</p>}
      {topics.length > 1 && <p role="alert">{t('Project cũ chứa nhiều chủ đề. Dữ liệu được giữ nguyên; cần xem xét mapping trước khi tách project.', 'This legacy project contains multiple topics. Data is preserved; review ownership mapping before splitting the project.')}</p>}

      {/* Sub-tabs when a topic is active */}
      {activeTopicId && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, borderBottom: '1px solid var(--line)', paddingBottom: 8 }}>
          <button className={`btn sm ${subTab === 'list' ? 'accent' : 'ghost'}`} onClick={() => setSubTab('list')}>
            Danh sách Topics
          </button>
          <button className={`btn sm ${subTab === 'papers' ? 'accent' : 'ghost'}`} onClick={() => setSubTab('papers')}>
            <BookOpen size={13} style={{ marginRight: 4 }} /> {t('Tài liệu SKB', 'SKB documents')}
          </button>
          <button className={`btn sm ${subTab === 'ledger' ? 'accent' : 'ghost'}`} onClick={() => setSubTab('ledger')}>
            <ShieldCheck size={13} style={{ marginRight: 4 }} /> {t('Sổ cái bất biến', 'Immutable ledger')}
          </button>
        </div>
      )}

      {/* Create Topic Form */}
      {showCreate && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (title.trim()) {
              const kw = keywordsText
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);
              createMutation.mutate({
                title: title.trim(),
                description: description.trim(),
                keywords: kw.length > 0 ? kw : [title.trim()],
                sources: ['openalex', 'arxiv', 'semantic_scholar', 'crossref'],
              });
            }
          }}
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--line-2)',
            borderRadius: 8,
            padding: 12,
            display: 'grid',
            gap: 10,
          }}
        >
          <label className="field" style={{ margin: 0 }}>
            <span>Tiêu đề Topic (Title)</span>
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="vd: Diffusion models for medical imaging"
              required
            />
          </label>
          <label className="field" style={{ margin: 0 }}>
            <span>Từ khóa tìm kiếm (cách nhau bởi dấu phẩy)</span>
            <input
              className="input"
              value={keywordsText}
              onChange={(e) => setKeywordsText(e.target.value)}
              placeholder="vd: diffusion, denoising, MRI reconstruction"
            />
          </label>
          <label className="field" style={{ margin: 0 }}>
            <span>Mô tả & Mục tiêu</span>
            <textarea
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Mục tiêu nghiên cứu, giả thuyết chính…"
              rows={2}
            />
          </label>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="btn sm ghost" type="button" onClick={() => setShowCreate(false)}>
              Huỷ
            </button>
            <button className="btn sm accent" type="submit" disabled={createMutation.isPending}>
              Tạo Topic
            </button>
          </div>
        </form>
      )}

      {/* Sub-tab 1: Topic List */}
      {subTab === 'list' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {isLoading && <p className="muted">Đang tải danh sách Topic…</p>}
          {topics.map((t) => {
            const isSelected = activeTopicId === t.id;
            const displayTitle = t.title || t.name || t.id;
            return (
              <div
                key={t.id}
                onClick={() => setActiveTopic(t)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: isSelected ? 'var(--sel)' : 'var(--panel)',
                  border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--line)'}`,
                  cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Folder size={18} color={isSelected ? 'var(--accent)' : 'var(--muted)'} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13.5 }}>{displayTitle}</div>
                    {t.description && (
                      <div className="muted" style={{ fontSize: 12, color: isSelected ? 'var(--ink-2)' : undefined }}>
                        {t.description}
                      </div>
                    )}
                    {t.keywords && t.keywords.length > 0 && (
                      <div className="muted" style={{ fontSize: 11, marginTop: 2, color: isSelected ? 'var(--ink-2)' : undefined }}>
                        {language === 'en' ? 'Keywords' : 'Từ khóa'}: {t.keywords.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {isSelected && (
                    <button
                      className="btn sm ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        discoverMutation.mutate(t.id);
                      }}
                      title="Khám phá bài báo mới từ OpenAlex / arXiv"
                    >
                      <Search size={13} style={{ marginRight: 4 }} /> Khám phá
                    </button>
                  )}
                  {isSelected && <Check size={16} color="var(--accent)" />}
                </div>
              </div>
            );
          })}
          {topics.length === 0 && !isLoading && (
            <p className="muted" style={{ fontSize: 13 }}>
              {t('Chưa có Topic nào trong dự án hiện tại.', 'No topics in this project yet.')}
            </p>
          )}
        </div>
      )}

      {/* Sub-tab 2: Topic Scoped Papers */}
      {subTab === 'papers' && activeTopicId && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b style={{ fontSize: 13 }}>Tài liệu trong SKB của Topic ({papersData?.papers?.length || 0})</b>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn sm ghost" onClick={() => openDrawer('library')} title="Mở Thư viện Bài báo & Tìm kiếm PDF">
                <BookOpen size={13} style={{ marginRight: 4 }} /> Thư viện Toàn cục
              </button>
              <button className="btn sm ghost" onClick={() => discoverMutation.mutate(activeTopicId)}>
                <Search size={13} style={{ marginRight: 4 }} /> Chạy Discovery
              </button>
            </div>
          </div>
          {papersData?.papers?.map((p) => (
            <div
              key={p.id}
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--line)',
                borderRadius: 8,
                padding: 10,
                fontSize: 12.5,
                display: 'grid',
                gap: 4,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <b>{p.title}</b>
                <span className="chip" style={{ fontSize: 11 }}>Cấp độ tin cậy: L{p.level ?? 0}</span>
              </div>
              <div className="muted" style={{ fontSize: 11.5 }}>
                {p.venue || 'Preprint'} · {p.year} · DOI: {p.doi || 'N/A'}
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                <button
                  className="btn sm ghost"
                  onClick={() => p.id && curateMutation.mutate({ pid: p.id, level: 4 })}
                >
                  Xác thực L4 (User Attested)
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Sub-tab 3: Decision Ledger Audit */}
      {subTab === 'ledger' && activeTopicId && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b style={{ fontSize: 13 }}>Chuỗi Băm Sổ cái Quyết định (Hash-Chained Decision Ledger)</b>
            <span className={`chip ${ledgerData?.ok !== false ? 'ok' : 'err'}`} style={{ fontSize: 11 }}>
              {ledgerData?.ok !== false ? 'HASH CHAIN VERIFIED' : 'INTEGRITY ERROR'}
            </span>
          </div>
          <div style={{ maxHeight: 280, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {((ledgerData as any)?.events || ledgerData?.entries)?.map((en: any) => (
              <div
                key={en.seq}
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--line-2)',
                  borderRadius: 6,
                  padding: 8,
                  fontSize: 12,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <b>#{en.seq} {en.kind}</b>
                  <code style={{ fontSize: 10.5 }}>{en.hash?.slice(0, 14)}…</code>
                </div>
                <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                  Entity: {en.entity_id} · {en.at}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
