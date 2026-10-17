export class ApiError extends Error {
  constructor(message: string, public readonly status?: number, public readonly completedUploads: string[] = []) { super(message); this.name = 'ApiError'; }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api${path}`, init); }
  catch { throw new ApiError('Cannot reach the local service. Check that the backend is running, then try again.'); }
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json().catch(() => null) : null;
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === 'string' ? detail : typeof body?.error === 'string' ? body.error : typeof body?.message === 'string' ? body.message : null;
    const completedUploads = body?.partial === true && Array.isArray(body.files)
      ? body.files.slice(0, 10).flatMap((file: unknown) => file && typeof file === 'object' && 'name' in file && typeof file.name === 'string' ? [file.name.slice(0, 255)] : []) : [];
    throw new ApiError(message || `The request did not complete (HTTP ${response.status}). Try again after checking the local service.`, response.status, completedUploads);
  }
  return body as T;
}

export function json(method: string, data: unknown = {}): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) };
}

export function safeBoxUrl(value?: string): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' && !url.username && !url.password && (url.hostname === 'box.com' || url.hostname.endsWith('.box.com'))) return url.href;
  } catch { /* Invalid source links are displayed as text only. */ }
  return undefined;
}
