import { api } from './api';

type Format = 'docx' | 'pdf';
interface PreparedExport { download_url: string; filename?: string; }
export interface NativeDownload { href: string; filename: string; }

/** Let the browser handle the server's attachment response instead of a blob URL. */
export async function requestExportDownload(runId: string, format: Format): Promise<NativeDownload> {
  const route = `/api/runs/${encodeURIComponent(runId)}/exports/${format}`;
  const prepared = await api<PreparedExport | null>(`/runs/${encodeURIComponent(runId)}/exports/${format}?prepare=true`);
  // An older local server returns the validated attachment rather than JSON.
  const target = new URL(prepared?.download_url || route, location.origin);
  if (target.origin !== location.origin || target.pathname !== route || target.hash) throw new Error('The export did not return a valid local download link.');
  const anchor = document.createElement('a');
  anchor.href = target.href;
  anchor.download = prepared?.filename || '';
  anchor.hidden = true;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  return { href: target.href, filename: prepared?.filename || '' };
}
