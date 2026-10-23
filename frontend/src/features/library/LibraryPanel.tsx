import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import type { LibraryPaper, LibraryResponse } from '../../shared/api/types';
import {
  BookOpen,
  Upload,
  FileText,
  Copy,
  Search,
  Sparkles,
  Trash2,
  Globe,
  PlusCircle,
  Award,
} from 'lucide-react';

export const LibraryPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<'local' | 'search'>('local');
  const [filter, setFilter] = useState('');
  const [uploading, setUploading] = useState(false);
  const [refiningFile, setRefiningFile] = useState<string | null>(null);

  // Academic search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchMode, setSearchMode] = useState<'papers' | 'both' | 'web'>('papers');
  const [yearFrom, setYearFrom] = useState<string>('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<Array<Record<string, unknown>>>([]);
  const [savingSourceIdx, setSavingSourceIdx] = useState<number | null>(null);

  const { data: libraryData, isLoading } = useQuery<LibraryResponse>({
    queryKey: ['library'],
    queryFn: () => api.get<LibraryResponse>('/api/library'),
  });

  const papers: LibraryPaper[] = libraryData?.references || libraryData?.papers || [];
  const filteredPapers = filter
    ? papers.filter(
        (p) =>
          (p.title || '').toLowerCase().includes(filter.toLowerCase()) ||
          (p.venue || '').toLowerCase().includes(filter.toLowerCase()) ||
          (p.key || '').toLowerCase().includes(filter.toLowerCase()) ||
          (p.authors && p.authors.some((a) => a.toLowerCase().includes(filter.toLowerCase())))
      )
    : papers;

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    setUploading(true);
    const form = new FormData();
    Array.from(fileList).forEach((f) => form.append('files', f));

    try {
      await api.post('/api/library/upload', form);
      queryClient.invalidateQueries({ queryKey: ['library'] });
    } catch (err) {
      alert(`Lỗi tải lên PDF: ${(err as Error).message}`);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const copyAllBibtex = async () => {
    try {
      const res = await fetch('/api/library/bib');
      const bibtex = await res.text();
      await navigator.clipboard.writeText(bibtex);
      alert('Đã sao chép toàn bộ BibTeX vào clipboard!');
    } catch {
      alert('Không lấy được BibTeX.');
    }
  };

  const handleRefineMetadata = async (fileName: string) => {
    setRefiningFile(fileName);
    try {
      await api.post('/api/library/refine', { file: fileName });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    } catch (err) {
      alert(`Không thể trích xuất metadata bằng AI: ${(err as Error).message}`);
    } finally {
      setRefiningFile(null);
    }
  };

  const handleDeletePaper = async (fileName: string) => {
    if (!confirm(`Xóa tài liệu "${fileName}" khỏi thư viện?`)) return;
    try {
      await api.delete(`/api/library/${encodeURIComponent(fileName)}`);
      queryClient.invalidateQueries({ queryKey: ['library'] });
    } catch (err) {
      alert(`Lỗi xóa: ${(err as Error).message}`);
    }
  };

  const handleAcademicSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await api.post<{ sources?: Array<Record<string, unknown>> }>('/api/search', {
        query: searchQuery.trim(),
        mode: searchMode,
        n_results: 12,
        year_from: yearFrom ? Number(yearFrom) : undefined,
      });
      setSearchResults(res.sources || []);
    } catch (err) {
      alert(`Lỗi tìm kiếm học thuật: ${(err as Error).message}`);
    } finally {
      setSearching(false);
    }
  };

  const handleSaveSource = async (source: Record<string, unknown>, idx: number) => {
    setSavingSourceIdx(idx);
    try {
      await api.post('/api/library/save', { source });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    } catch (err) {
      alert(`Lỗi lưu bài báo: ${(err as Error).message}`);
    } finally {
      setSavingSourceIdx(null);
    }
  };

  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header + Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            type="button"
            className={`btn sm ${tab === 'local' ? 'accent' : 'ghost'}`}
            onClick={() => setTab('local')}
          >
            <BookOpen size={14} style={{ marginRight: 5 }} />
            <span>Thư viện ({papers.length})</span>
          </button>
          <button
            type="button"
            className={`btn sm ${tab === 'search' ? 'accent' : 'ghost'}`}
            onClick={() => setTab('search')}
          >
            <Globe size={14} style={{ marginRight: 5 }} />
            <span>Tìm kiếm Học thuật (OpenAlex/S2/arXiv)</span>
          </button>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          <button type="button" className="btn sm ghost" onClick={copyAllBibtex}>
            <Copy size={13} style={{ marginRight: 4 }} />
            <span>BibTeX</span>
          </button>
          <label className="btn sm accent" style={{ cursor: 'pointer', margin: 0 }}>
            <Upload size={14} style={{ marginRight: 4 }} />
            <span>{uploading ? 'Đang tải…' : 'Tải lên PDF'}</span>
            <input
              type="file"
              accept=".pdf"
              multiple
              onChange={handleFileUpload}
              style={{ display: 'none' }}
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {tab === 'local' ? (
        <>
          {/* Filter Input */}
          <div style={{ position: 'relative' }}>
            <Search
              size={14}
              color="var(--muted)"
              style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }}
            />
            <input
              className="input"
              style={{ paddingLeft: 30, width: '100%' }}
              placeholder="Lọc theo tiêu đề, tác giả, hội nghị/tạp chí, hoặc mã trích dẫn (citation key)…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>

          {/* Paper List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {isLoading && <p className="muted">Đang quét thư mục tài liệu…</p>}
            {filteredPapers.map((paper) => {
              const fileKey = paper.file || paper.id || paper.key || paper.title;
              const rankTier = paper.rank?.rank || paper.ranking?.tier;

              return (
                <article
                  key={fileKey}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 10,
                    background: 'var(--panel)',
                    border: '1px solid var(--line)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start' }}>
                    <b style={{ fontSize: 13.5, lineHeight: 1.4 }}>{paper.title || paper.file}</b>
                    <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                      {rankTier && (
                        <span className="chip ok" style={{ fontSize: 11 }}>
                          <Award size={11} style={{ marginRight: 3 }} />
                          {rankTier}
                        </span>
                      )}
                      {paper.key && (
                        <span className="chip" style={{ fontSize: 11, fontFamily: 'var(--mono)' }}>
                          @{paper.key}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="muted" style={{ fontSize: 12 }}>
                    {paper.authors?.join(', ') || 'Chưa rõ tác giả'} · {paper.year || 'N/A'}
                    {paper.venue ? ` · ${paper.venue}` : ''}
                  </div>

                  <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                    {paper.file && !paper.metadata_only && (
                      <a
                        className="btn sm ghost"
                        href={`/api/library/file/${encodeURIComponent(paper.file)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ textDecoration: 'none' }}
                      >
                        <FileText size={13} style={{ marginRight: 4 }} /> Đọc PDF
                      </a>
                    )}
                    {paper.file && !paper.metadata_only && (
                      <button
                        className="btn sm ghost"
                        type="button"
                        disabled={refiningFile === paper.file}
                        onClick={() => handleRefineMetadata(paper.file!)}
                        title="Trích xuất lại tiêu đề, tác giả, DOI từ trang đầu PDF bằng AI"
                      >
                        <Sparkles size={13} style={{ marginRight: 4 }} />
                        {refiningFile === paper.file ? 'Đang chuẩn hóa…' : 'Chuẩn hóa AI'}
                      </button>
                    )}
                    {paper.file && (
                      <button
                        className="btn sm ghost"
                        type="button"
                        onClick={() => handleDeletePaper(paper.file!)}
                        style={{ marginLeft: 'auto', color: 'var(--danger)' }}
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                </article>
              );
            })}

            {filteredPapers.length === 0 && !isLoading && (
              <div
                style={{
                  padding: 24,
                  textAlign: 'center',
                  borderRadius: 10,
                  border: '1px dashed var(--line-2)',
                }}
              >
                <p className="muted" style={{ fontSize: 13, margin: '0 0 8px' }}>
                  Chưa có tài liệu nào trong thư viện dự án.
                </p>
                <button
                  type="button"
                  className="btn sm accent"
                  onClick={() => setTab('search')}
                >
                  Tìm kiếm bài báo học thuật ngay
                </button>
              </div>
            )}
          </div>
        </>
      ) : (
        /* Academic Literature Search Tab */
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <form
            onSubmit={handleAcademicSearch}
            style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder="Nhập chủ đề, từ khóa hoặc tên bài báo (VD: Graph Neural Networks molecular property)…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button type="submit" className="btn sm accent" disabled={searching}>
                <Search size={14} style={{ marginRight: 4 }} />
                {searching ? 'Đang tìm…' : 'Tìm kiếm'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <select
                className="input"
                style={{ width: 'auto', fontSize: 12, padding: '4px 8px' }}
                value={searchMode}
                onChange={(e) => setSearchMode(e.target.value as 'papers' | 'both' | 'web')}
              >
                <option value="papers">Chỉ Bài báo Khoa học (S2 / OpenAlex / arXiv)</option>
                <option value="both">Bài báo + Web học thuật</option>
                <option value="web">Chỉ Web</option>
              </select>
              <input
                className="input"
                type="number"
                placeholder="Từ năm (VD: 2021)"
                value={yearFrom}
                onChange={(e) => setYearFrom(e.target.value)}
                style={{ width: 140, fontSize: 12, padding: '4px 8px' }}
              />
            </div>
          </form>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {searchResults.map((src, idx) => (
              <div
                key={idx}
                style={{
                  padding: 12,
                  borderRadius: 10,
                  background: 'var(--panel)',
                  border: '1px solid var(--line)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <b style={{ fontSize: 13.5 }}>{String(src.title || 'Untitled')}</b>
                  {Boolean(src.rank) && (
                    <span className="chip ok" style={{ fontSize: 11 }}>
                      {String((src.rank as Record<string, unknown>)?.rank || '')}
                    </span>
                  )}
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {Array.isArray(src.authors) ? src.authors.slice(0, 4).join(', ') : ''} ·{' '}
                  {String(src.year || '')} · {String(src.venue || src.provider || '')}
                </div>
                {Boolean(src.abstract) && (
                  <p
                    className="muted"
                    style={{
                      fontSize: 12,
                      margin: 0,
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {String(src.abstract)}
                  </p>
                )}
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <button
                    type="button"
                    className="btn sm accent"
                    disabled={savingSourceIdx === idx}
                    onClick={() => handleSaveSource(src, idx)}
                  >
                    <PlusCircle size={13} style={{ marginRight: 4 }} />
                    {savingSourceIdx === idx ? 'Đang lưu…' : 'Lưu vào Thư viện'}
                  </button>
                  {Boolean(src.url) && (
                    <a
                      className="btn sm ghost"
                      href={String(src.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ textDecoration: 'none' }}
                    >
                      Mở liên kết
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
