// PhD Research Lab — Typed REST Client with error envelope handling

export class ApiError extends Error {
  status: number;
  code?: string;
  detail?: string;

  constructor(status: number, message: string, code?: string, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  headers.set('X-PhDLab-Client', 'ui');

  const res = await fetch(path, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let code: string | undefined;
    let detail: string | undefined;
    let message = `Request failed: ${res.status} ${res.statusText}`;

    try {
      const data = await res.json();
      if (data && typeof data === 'object') {
        detail = data.detail || data.message;
        code = data.code;
        if (detail) message = detail;
      }
    } catch {
      // Body is not JSON
    }

    throw new ApiError(res.status, message, code, detail);
  }

  if (res.status === 204) {
    return {} as T;
  }

  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json() as Promise<T>;
  }

  return res.text() as unknown as Promise<T>;
}

export const api = {
  get: <T>(url: string, signal?: AbortSignal) =>
    request<T>(url, { method: 'GET', signal }),
  post: <T>(url: string, body?: unknown, signal?: AbortSignal) =>
    request<T>(url, {
      method: 'POST',
      body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    }),
  put: <T>(url: string, body?: unknown, signal?: AbortSignal) =>
    request<T>(url, {
      method: 'PUT',
      body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    }),
  delete: <T>(url: string, signal?: AbortSignal) =>
    request<T>(url, { method: 'DELETE', signal }),
};
