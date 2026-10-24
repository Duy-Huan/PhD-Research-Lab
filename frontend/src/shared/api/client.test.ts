import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api, request, ApiError } from './client';

describe('client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('performs successful GET and parses JSON', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ ok: true, data: 'test' }),
    });

    const res = await api.get<{ ok: boolean; data: string }>('/api/test');
    expect(res).toEqual({ ok: true, data: 'test' });
    expect((globalThis as any).fetch).toHaveBeenCalledWith('/api/test', expect.anything());
  });

  it('handles non-JSON text responses (e.g., BibTeX / plain text)', async () => {
    const bibtex = '@article{test2026, title={AI Lab}}';
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'text/plain' }),
      text: () => Promise.resolve(bibtex),
    });

    const res = await api.get<string>('/api/library/bib');
    expect(res).toBe(bibtex);
  });

  it('handles 204 No Content', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
    });

    const res = await api.delete('/api/delete/1');
    expect(res).toEqual({});
  });

  it('performs PUT with JSON body and FormData body', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ updated: true }),
    });

    const jsonRes = await api.put('/api/topics/1', { title: 'Updated' });
    expect(jsonRes).toEqual({ updated: true });

    const form = new FormData();
    form.append('meta', 'data');
    const formRes = await api.put('/api/topics/1/upload', form);
    expect(formRes).toEqual({ updated: true });
  });

  it('handles FormData on POST without setting Content-Type json header', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: () => Promise.resolve({ id: 'att-1' }),
    });

    const form = new FormData();
    form.append('file', 'abc');
    const res = await api.post('/api/upload', form);
    expect(res).toEqual({ id: 'att-1' });
  });

  it('throws ApiError with detail on non-ok status', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve({ detail: 'Topic title required', code: 'INVALID_INPUT' }),
    });

    await expect(api.post('/api/topics', {})).rejects.toThrow(ApiError);
  });

  it('handles non-JSON error bodies and message property fallback', async () => {
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('Not json')),
    });

    await expect(api.get('/api/fault')).rejects.toThrow('Request failed: 500 Internal Server Error');

    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: () => Promise.resolve({ message: 'Revision conflict detected' }),
    });

    try {
      await api.post('/api/save', {});
    } catch (e: any) {
      expect(e).toBeInstanceOf(ApiError);
      expect(e.status).toBe(409);
      expect(e.message).toBe('Revision conflict detected');
    }
  });
});
