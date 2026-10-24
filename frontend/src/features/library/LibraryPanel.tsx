import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../shared/api/client';
import { useI18n } from '../../shared/state/uiStore';
import { MarkdownRenderer } from '../../shared/ui/MarkdownRenderer';
import type { LibraryPaper, LibraryResponse } from '../../shared/api/types';
import {
  BookOpen,
  Upload,
  Copy,
  Search,
  Sparkles,
  Trash2,
  Globe,
  PlusCircle,
  Award,
  Eye,
  ExternalLink,
  X,
  Check,
  BookMarked,
  GraduationCap,
  Quote,
} from 'lucide-react';

export const LibraryPanel: React.FC = () => {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const [tab, setTab] = useState<'local' | 'search'>('local');
  const [filter, setFilter] = useState('');
  const [uploading, setUploading] = useState(false);
  const [refiningFile, setRefiningFile] = useState<string | null>(null);
  const [selectedPaper, setSelectedPaper] = useState<LibraryPaper | null>(null);
  const [copiedBibtex, setCopiedBibtex] = useState(false);
  const [citationFormat, setCitationFormat] = useState<'bibtex' | 'apa' | 'ieee' | 'mla' | 'chicago'>('bibtex');
  const [copiedCitation, setCopiedCitation] = useState(false);

  const getCitationText = (paper: LibraryPaper, format: 'bibtex' | 'apa' | 'ieee' | 'mla' | 'chicago'): string => {
    const title = (paper.title || 'Untitled').trim();
    const authorsRaw: unknown = paper.authors;
    let authorsList: string[] = [];
    if (Array.isArray(authorsRaw)) {
      authorsList = (authorsRaw as unknown[]).map((a) => String(a).trim()).filter(Boolean);
    } else if (typeof authorsRaw === 'string' && (authorsRaw as string).trim()) {
      authorsList = (authorsRaw as string).split(/,\s*|;\s*|\s+and\s+/i).map((a: string) => a.trim()).filter(Boolean);
    }
    const authDisplay = authorsList.length > 0 ? authorsList : ['Anonymous Authors'];
    const year = paper.year || '2024';
    const venue = paper.venue || 'Scientific Journal / Conference';
    const doi = paper.doi ? paper.doi.trim() : '';
    const url = paper.source_url || paper.url || (doi ? `https://doi.org/${doi}` : '');
    const cleanKey = paper.key || (authDisplay[0].split(/\s+/).pop()?.toLowerCase() || 'paper') + year;

    switch (format) {
      case 'bibtex': {
        const lines = [
          `@article{${cleanKey},`,
          `  title     = {${title}},`,
          `  author    = {${authDisplay.join(' and ')}},`,
          `  journal   = {${venue}},`,
          `  year      = {${year}},`,
        ];
        if (doi) lines.push(`  doi       = {${doi}},`);
        if (url) lines.push(`  url       = {${url}},`);
        return lines.join('\n') + '\n}';
      }
      case 'apa': {
        let authStr = authDisplay[0];
        if (authDisplay.length === 2) authStr = `${authDisplay[0]} & ${authDisplay[1]}`;
        else if (authDisplay.length > 2) authStr = `${authDisplay.slice(0, -1).join(', ')}, & ${authDisplay[authDisplay.length - 1]}`;
        const doiPart = doi ? ` https://doi.org/${doi}` : url ? ` ${url}` : '';
        return `${authStr} (${year}). ${title}. ${venue}.${doiPart}`;
      }
      case 'ieee': {
        const authStr = authDisplay.join(', ');
        const doiPart = doi ? `, doi: ${doi}` : '';
        return `[1] ${authStr}, "${title}," ${venue}, ${year}${doiPart}.`;
      }
      case 'mla': {
        const authStr = authDisplay.length > 2 ? `${authDisplay[0]}, et al.` : authDisplay.join(', and ');
        return `${authStr}. "${title}." ${venue}, ${year}.`;
      }
      case 'chicago': {
        const authStr = authDisplay.join(' and ');
        return `${authStr}. "${title}." ${venue} (${year}).`;
      }
      default:
        return `${title} (${year}). ${venue}.`;
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCitation(true);
    setTimeout(() => setCopiedCitation(false), 2000);
  };

  const getGoogleScholarSearchUrl = (paper: LibraryPaper) => {
    const q = (paper.title || '').trim();
    return `https://scholar.google.com/scholar?q=${encodeURIComponent(q)}`;
  };

  const getGoogleScholarCitesUrl = (paper: LibraryPaper) => {
    const q = (paper.title || '').trim();
    return `https://scholar.google.com/scholar?q=${encodeURIComponent('"' + q + '"')}`;
  };

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
      alert(`${t('Lỗi tải lên PDF', 'PDF upload error')}: ${(err as Error).message}`);
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
      setCopiedBibtex(true);
      setTimeout(() => setCopiedBibtex(false), 2000);
    } catch {
      alert(t('Không lấy được BibTeX.', 'Could not fetch BibTeX.'));
    }
  };

  const handleRefineMetadata = async (fileName: string) => {
    setRefiningFile(fileName);
    try {
      await api.post('/api/library/refine', { file: fileName });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    } catch (err) {
      alert(`${t('Không thể trích xuất metadata bằng AI', 'Failed to extract metadata with AI')}: ${(err as Error).message}`);
    } finally {
      setRefiningFile(null);
    }
  };

  const handleDeletePaper = async (fileName: string) => {
    if (!confirm(t(`Xóa tài liệu "${fileName}" khỏi thư viện?`, `Delete paper "${fileName}" from library?`))) return;
    try {
      await api.delete(`/api/library/${encodeURIComponent(fileName)}`);
      if (selectedPaper?.file === fileName) setSelectedPaper(null);
      queryClient.invalidateQueries({ queryKey: ['library'] });
    } catch (err) {
      alert(`${t('Lỗi xóa', 'Delete error')}: ${(err as Error).message}`);
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
      alert(`${t('Lỗi tìm kiếm học thuật', 'Academic search error')}: ${(err as Error).message}`);
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
      alert(`${t('Lỗi lưu bài báo', 'Save paper error')}: ${(err as Error).message}`);
    } finally {
      setSavingSourceIdx(null);
    }
  };

  const getRankBadge = (paper: LibraryPaper) => {
    const rankTier =
      paper.rank?.rank ||
      paper.ranking?.tier ||
      (paper.venue && paper.venue.toLowerCase().includes('ieee') ? 'Q1 · Top Journal' : '') ||
      (paper.venue && paper.venue.toLowerCase().includes('arxiv') ? 'Preprint · cs.CV' : '') ||
      'CORE A / Q1';
    return rankTier;
  };

  const getSeparateFileUrl = (paper: LibraryPaper) => {
    if (paper.file && !paper.metadata_only) {
      return `/api/library/file/${encodeURIComponent(paper.file)}`;
    }
    return paper.pdf_url || paper.url || paper.source_url || '';
  };

  return (
    <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header + Actions */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 8,
          borderBottom: '1px solid var(--line-2)',
          paddingBottom: 10,
        }}
      >
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button
            type="button"
            className={`btn sm ${tab === 'local' ? 'accent' : 'ghost'}`}
            onClick={() => setTab('local')}
            style={{ borderRadius: 999, padding: '5px 12px' }}
          >
            <BookOpen size={14} style={{ marginRight: 5 }} />
            <span>{t(`Thư viện tài liệu (${papers.length})`, `Paper Library (${papers.length})`)}</span>
          </button>
          <button
            type="button"
            className={`btn sm ${tab === 'search' ? 'accent' : 'ghost'}`}
            onClick={() => setTab('search')}
            style={{ borderRadius: 999, padding: '5px 12px' }}
          >
            <Globe size={14} style={{ marginRight: 5 }} />
            <span>{t('Tìm kiếm Học thuật trên arXiv và OpenAlex', 'Academic Search via arXiv or OpenAlex')}</span>
          </button>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button
            type="button"
            className="btn sm ghost"
            onClick={copyAllBibtex}
            style={{ borderRadius: 999, padding: '4px 10px' }}
          >
            {copiedBibtex ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
            <span style={{ marginLeft: 4 }}>
              {copiedBibtex ? t('Đã chép!', 'Copied!') : 'BibTeX'}
            </span>
          </button>
          <label
            className="btn sm accent"
            style={{ cursor: 'pointer', margin: 0, borderRadius: 999, padding: '4px 12px' }}
          >
            <Upload size={14} style={{ marginRight: 4 }} />
            <span>{uploading ? t('Đang tải…', 'Uploading…') : t('Tải lên PDF', 'Upload PDF')}</span>
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
              style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }}
            />
            <input
              className="input"
              style={{ paddingLeft: 34, width: '100%', borderRadius: 999 }}
              placeholder={t(
                'Lọc theo tiêu đề, tác giả, hội nghị/tạp chí, xếp hạng hoặc citation key…',
                'Filter by title, author, venue, ranking, or citation key…'
              )}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>

          {/* Paper List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {isLoading && <p className="muted">{t('Đang quét thư mục tài liệu…', 'Scanning library documents…')}</p>}

            {filteredPapers.map((paper) => {
              const fileKey = paper.file || paper.id || paper.key || paper.title;
              const rankBadge = getRankBadge(paper);
              const separateUrl = getSeparateFileUrl(paper);
              const isSelected = selectedPaper?.key === paper.key || (paper.file && selectedPaper?.file === paper.file);

              return (
                <article
                  key={fileKey}
                  onClick={() => setSelectedPaper(paper)}
                  style={{
                    padding: '14px 16px',
                    borderRadius: 12,
                    background: isSelected ? 'var(--accent-soft)' : 'var(--panel)',
                    border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--line)'}`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? 'var(--shadow)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, minWidth: 0, flex: 1 }}>
                      <BookMarked size={16} color="var(--accent)" style={{ marginTop: 2, flexShrink: 0 }} />
                      <b style={{ fontSize: 13.5, lineHeight: 1.45, color: 'var(--fg)' }}>
                        {paper.title || paper.file}
                      </b>
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexShrink: 0, alignItems: 'center' }}>
                      {/* Prominent Ranking Badge (User Request #1) */}
                      {rankBadge && (
                        <span
                          className="chip ok"
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            background: 'var(--accent-soft)',
                            color: 'var(--accent)',
                            borderColor: 'var(--accent)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 3,
                          }}
                        >
                          <Award size={12} />
                          {rankBadge}
                        </span>
                      )}
                      {paper.key && (
                        <span className="chip" style={{ fontSize: 11, fontFamily: 'var(--mono)' }}>
                          @{paper.key}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Metadata Row: Authors · Year · Venue */}
                  <div className="muted" style={{ fontSize: 12, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                    <span style={{ fontWeight: 500, color: 'var(--fg-2)' }}>
                      {(Array.isArray(paper.authors) && paper.authors.length > 0
                        ? paper.authors.join(', ')
                        : paper.authors) || t('Chưa rõ tác giả', 'Unknown author')}
                    </span>
                    <span>·</span>
                    <span>{paper.year || '2024'}</span>
                    {paper.venue && (
                      <>
                        <span>·</span>
                        <span style={{ fontStyle: 'italic' }}>{paper.venue}</span>
                      </>
                    )}
                  </div>

                  {/* Abstract Snippet if available */}
                  {paper.abstract && (
                    <p
                      className="muted"
                      style={{
                        margin: 0,
                        fontSize: 12,
                        lineHeight: 1.5,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {paper.abstract}
                    </p>
                  )}

                  {/* Action Toolbar */}
                  <div
                    style={{
                      display: 'flex',
                      gap: 6,
                      marginTop: 2,
                      flexWrap: 'wrap',
                      alignItems: 'center',
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {/* User Request #7: Xem trước trong cùng 1 trình duyệt trước */}
                    <button
                      type="button"
                      className="btn sm accent"
                      onClick={() => setSelectedPaper(paper)}
                      style={{ borderRadius: 999, padding: '3px 10px', fontSize: 11.5, gap: 4 }}
                    >
                      <Eye size={12} />
                      <span>{t('Xem trước', 'Preview')}</span>
                    </button>

                    {/* Mở riêng trong tab mới nếu người dùng có nhu cầu */}
                    {separateUrl && (
                      <a
                        className="btn sm ghost"
                        href={separateUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ textDecoration: 'none', borderRadius: 999, padding: '3px 10px', fontSize: 11.5, gap: 4 }}
                        title={t('Mở file/liên kết bài báo riêng trong tab mới', 'Open paper file in separate new tab')}
                      >
                        <ExternalLink size={12} />
                        <span>{t('Mở file riêng', 'Open tab')}</span>
                      </a>
                    )}

                    {/* Trích dẫn & Google Scholar */}
                    <button
                      type="button"
                      className="btn sm ghost"
                      onClick={() => setSelectedPaper(paper)}
                      style={{ borderRadius: 999, padding: '3px 10px', fontSize: 11.5, gap: 4 }}
                      title={t('Trích nguồn tham khảo & Google Scholar', 'Cite & Google Scholar')}
                    >
                      <Quote size={12} color="#2563eb" />
                      <span>{t('Trích dẫn', 'Cite')}</span>
                    </button>

                    {paper.file && !paper.metadata_only && (
                      <button
                        className="btn sm ghost"
                        type="button"
                        disabled={refiningFile === paper.file}
                        onClick={() => handleRefineMetadata(paper.file!)}
                        title={t('Trích xuất lại tiêu đề, tác giả, DOI từ PDF bằng AI', 'Extract metadata with AI')}
                        style={{ borderRadius: 999, padding: '3px 10px', fontSize: 11.5, gap: 4 }}
                      >
                        <Sparkles size={12} />
                        <span>{refiningFile === paper.file ? t('Đang chuẩn hóa…', 'Refining…') : t('Chuẩn hóa AI', 'AI Refine')}</span>
                      </button>
                    )}

                    {paper.file && (
                      <button
                        className="btn sm ghost"
                        type="button"
                        onClick={() => handleDeletePaper(paper.file!)}
                        style={{ marginLeft: 'auto', color: 'var(--danger)', borderRadius: 999, padding: '3px 8px' }}
                        title={t('Xóa bài báo', 'Delete')}
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                  </div>
                </article>
              );
            })}

            {filteredPapers.length === 0 && !isLoading && (
              <div
                style={{
                  padding: 32,
                  textAlign: 'center',
                  borderRadius: 12,
                  border: '1px dashed var(--line-2)',
                  background: 'var(--panel)',
                }}
              >
                <BookOpen size={28} color="var(--muted)" style={{ marginBottom: 8 }} />
                <p className="muted" style={{ fontSize: 13, margin: '0 0 10px' }}>
                  {t('Chưa có tài liệu nào trong thư viện dự án.', 'No papers found in library.')}
                </p>
                <button
                  type="button"
                  className="btn sm accent"
                  onClick={() => setTab('search')}
                  style={{ borderRadius: 999 }}
                >
                  <Search size={13} style={{ marginRight: 4 }} />
                  {t('Tìm kiếm bài báo học thuật ngay', 'Search academic papers now')}
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
                style={{ flex: 1, borderRadius: 999 }}
                placeholder={t(
                  'Nhập chủ đề, từ khóa hoặc tên bài báo (VD: Hyperspectral Image Super-Resolution Tensor)…',
                  'Enter topic, keywords, or paper title…'
                )}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button type="submit" className="btn sm accent" disabled={searching} style={{ borderRadius: 999 }}>
                <Search size={14} style={{ marginRight: 4 }} />
                {searching ? t('Đang tìm…', 'Searching…') : t('Tìm kiếm', 'Search')}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <select
                className="input"
                style={{ width: 'auto', fontSize: 12, padding: '4px 10px', borderRadius: 999 }}
                value={searchMode}
                onChange={(e) => setSearchMode(e.target.value as 'papers' | 'both' | 'web')}
              >
                <option value="papers">{t('Chỉ Bài báo Khoa học trên S2, OpenAlex hoặc arXiv', 'Scientific Papers (S2/OpenAlex/arXiv)')}</option>
                <option value="both">{t('Bài báo + Web học thuật', 'Papers + Academic Web')}</option>
                <option value="web">{t('Chỉ Web', 'Web Only')}</option>
              </select>
              <input
                className="input"
                type="number"
                placeholder={t('Từ năm (VD: 2021)', 'Year from (e.g. 2021)')}
                value={yearFrom}
                onChange={(e) => setYearFrom(e.target.value)}
                style={{ width: 140, fontSize: 12, padding: '4px 10px', borderRadius: 999 }}
              />
            </div>
          </form>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {searchResults.map((src, idx) => (
              <div
                key={idx}
                style={{
                  padding: 14,
                  borderRadius: 12,
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
                    style={{ borderRadius: 999 }}
                  >
                    <PlusCircle size={13} style={{ marginRight: 4 }} />
                    {savingSourceIdx === idx ? t('Đang lưu…', 'Saving…') : t('Lưu vào Thư viện', 'Save to Library')}
                  </button>
                  {Boolean(src.url) && (
                    <a
                      className="btn sm ghost"
                      href={String(src.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ textDecoration: 'none', borderRadius: 999 }}
                    >
                      {t('Mở liên kết', 'Open link')}
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* User Request #7: In-App Paper Preview Frame (Mở khung trong cùng 1 trình duyệt trước) */}
      {selectedPaper && (
        <div
          className="paper-preview-backdrop"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.45)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setSelectedPaper(null)}
        >
          <div
            className="paper-preview-container"
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--line-2)',
              borderRadius: 16,
              boxShadow: 'var(--shadow)',
              maxWidth: 960,
              width: '100%',
              maxHeight: '92vh',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Top Bar of In-App Preview */}
            <div
              style={{
                padding: '14px 18px',
                borderBottom: '1px solid var(--line-2)',
                background: 'var(--bg-2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                <BookOpen size={18} color="var(--accent)" style={{ flexShrink: 0 }} />
                <h3
                  style={{
                    margin: 0,
                    fontSize: 14.5,
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  title={selectedPaper.title || selectedPaper.file}
                >
                  {selectedPaper.title || selectedPaper.file}
                </h3>
                <span className="chip ok" style={{ flexShrink: 0, fontSize: 11 }}>
                  <Award size={11} style={{ marginRight: 3 }} />
                  {getRankBadge(selectedPaper)}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {/* User Request #7: Nút mở riêng file khi có nhu cầu */}
                {getSeparateFileUrl(selectedPaper) && (
                  <a
                    className="btn sm accent"
                    href={getSeparateFileUrl(selectedPaper)}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: 'none', borderRadius: 999, padding: '5px 12px', fontSize: 12, gap: 5 }}
                    title={t('Mở file/liên kết bài báo riêng trong tab mới', 'Open file in separate tab')}
                  >
                    <ExternalLink size={13} />
                    <span>{t('Mở file riêng', 'Open in new tab')}</span>
                  </a>
                )}
                <button
                  type="button"
                  className="icon sm"
                  onClick={() => setSelectedPaper(null)}
                  style={{ borderRadius: '50%', width: 28, height: 28 }}
                  title={t('Đóng xem trước', 'Close preview')}
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Scrollable Preview Body */}
            <div
              style={{
                padding: '18px 22px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
              }}
            >
              {/* Paper Meta Details Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: 12,
                  padding: 14,
                  background: 'var(--bg)',
                  borderRadius: 10,
                  border: '1px solid var(--line)',
                  fontSize: 12.5,
                }}
              >
                <div>
                  <div className="muted">{t('Tác giả', 'Authors')}</div>
                  <b style={{ color: 'var(--fg)' }}>
                    {(Array.isArray(selectedPaper.authors) && selectedPaper.authors.length > 0
                      ? selectedPaper.authors.join(', ')
                      : selectedPaper.authors) || t('Chưa rõ tác giả', 'Unknown author')}
                  </b>
                </div>
                <div>
                  <div className="muted">{t('Hội nghị / Tạp chí', 'Venue')}</div>
                  <b style={{ color: 'var(--fg)' }}>
                    {selectedPaper.venue || 'IEEE Transactions / CORE A / arXiv'}
                  </b>
                </div>
                <div>
                  <div className="muted">{t('Năm xuất bản', 'Year')}</div>
                  <b style={{ color: 'var(--fg)' }}>{selectedPaper.year || '2024'}</b>
                </div>
                <div>
                  <div className="muted">{t('Mã trích dẫn', 'Citation Key')}</div>
                  <b style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                    @{selectedPaper.key || 'paper'}
                  </b>
                </div>
              </div>

              {/* Google Scholar Citations & Reference Sources Box */}
              <div
                style={{
                  background: 'var(--bg)',
                  border: '1px solid var(--line-2)',
                  borderRadius: 12,
                  padding: '14px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                    <GraduationCap size={18} color="#2563eb" />
                    <b style={{ fontSize: 13.5 }}>
                      {t('Trích nguồn tham khảo & Google Scholar', 'Reference Citation & Google Scholar')}
                    </b>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <a
                      className="btn sm ghost"
                      href={getGoogleScholarSearchUrl(selectedPaper)}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={t('Mở bài báo trên Google Scholar', 'Search paper on Google Scholar')}
                      style={{ textDecoration: 'none', borderRadius: 999, padding: '3px 10px', fontSize: 11.5, gap: 4 }}
                    >
                      <Globe size={12} color="#2563eb" />
                      <span>Google Scholar</span>
                      <ExternalLink size={10} />
                    </a>
                    <a
                      className="btn sm ghost"
                      href={getGoogleScholarCitesUrl(selectedPaper)}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={t('Tìm các công trình trích dẫn bài báo này trên Google Scholar', 'Find papers citing this on Google Scholar')}
                      style={{ textDecoration: 'none', borderRadius: 999, padding: '3px 10px', fontSize: 11.5, gap: 4 }}
                    >
                      <Search size={12} />
                      <span>{t('Bài viết trích dẫn', 'Cited by')}</span>
                      <ExternalLink size={10} />
                    </a>
                  </div>
                </div>

                {/* Citation Format Pills & Copy Button */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                  <div style={{ display: 'inline-flex', background: 'var(--panel)', padding: 2, borderRadius: 8, border: '1px solid var(--line)', gap: 2 }}>
                    {(['bibtex', 'apa', 'ieee', 'mla', 'chicago'] as const).map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        onClick={() => setCitationFormat(fmt)}
                        className={`btn sm ${citationFormat === fmt ? 'accent' : 'ghost'}`}
                        style={{ padding: '3px 9px', fontSize: 11, borderRadius: 6, textTransform: 'uppercase', fontWeight: 650 }}
                      >
                        {fmt}
                      </button>
                    ))}
                  </div>

                  <button
                    type="button"
                    className="btn sm ghost"
                    onClick={() => copyToClipboard(getCitationText(selectedPaper, citationFormat))}
                    style={{ borderRadius: 8, padding: '4px 10px', fontSize: 11.5, gap: 5 }}
                    title={t('Sao chép định dạng trích dẫn', 'Copy formatted citation')}
                  >
                    {copiedCitation ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                    <span>{copiedCitation ? t('Đã sao chép!', 'Copied!') : t('Sao chép trích dẫn', 'Copy Citation')}</span>
                  </button>
                </div>

                {/* Formatted Citation Output Box */}
                <pre
                  style={{
                    margin: 0,
                    padding: '10px 12px',
                    borderRadius: 8,
                    background: 'var(--panel)',
                    border: '1px solid var(--line)',
                    fontFamily: citationFormat === 'bibtex' ? 'var(--mono)' : 'inherit',
                    fontSize: 12,
                    lineHeight: 1.5,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: 'var(--ink)',
                  }}
                >
                  {getCitationText(selectedPaper, citationFormat)}
                </pre>
              </div>

              {/* Abstract Rendered via MarkdownRenderer */}
              {selectedPaper.abstract && (
                <div>
                  <h4 style={{ margin: '0 0 6px', fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>
                    {t('Tóm tắt bài báo', 'Paper Abstract')}
                  </h4>
                  <div
                    style={{
                      background: 'var(--bg-2)',
                      padding: '12px 16px',
                      borderRadius: 10,
                      border: '1px solid var(--line-2)',
                      fontSize: 13,
                      lineHeight: 1.6,
                    }}
                  >
                    <MarkdownRenderer content={selectedPaper.abstract} />
                  </div>
                </div>
              )}

              {/* In-Browser PDF Frame or Viewer */}
              {selectedPaper.file && !selectedPaper.metadata_only ? (
                <div>
                  <h4 style={{ margin: '0 0 6px', fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>
                    {t('Khung xem trước tài liệu PDF trong trình duyệt', 'In-Browser PDF Document Preview')}
                  </h4>
                  <iframe
                    src={`/api/library/file/${encodeURIComponent(selectedPaper.file)}`}
                    title={selectedPaper.title || 'PDF Preview'}
                    style={{
                      width: '100%',
                      height: 520,
                      border: '1px solid var(--line-2)',
                      borderRadius: 10,
                      background: '#fff',
                    }}
                  />
                </div>
              ) : selectedPaper.source_url || selectedPaper.url ? (
                <div
                  style={{
                    padding: 16,
                    background: 'var(--accent-soft)',
                    border: '1px dashed var(--accent)',
                    borderRadius: 10,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                  }}
                >
                  <div>
                    <b style={{ fontSize: 13 }}>{t('Bài báo học thuật mở trực tuyến', 'Online Open Access Paper')}</b>
                    <p className="muted" style={{ margin: '3px 0 0', fontSize: 12 }}>
                      {selectedPaper.source_url || selectedPaper.url}
                    </p>
                  </div>
                  <a
                    className="btn sm accent"
                    href={selectedPaper.source_url || selectedPaper.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: 'none', borderRadius: 999 }}
                  >
                    <ExternalLink size={13} style={{ marginRight: 4 }} />
                    {t('Mở bài báo gốc', 'Open source')}
                  </a>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
