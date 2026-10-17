import { ApiError, api } from './api.js';

/** Reconcile Materials even when Box accepted only part of an upload. */
export async function uploadDocuments(category: string, files: File[], refresh: () => Promise<void>): Promise<void> {
  const form = new FormData();
  form.append('category', category);
  files.forEach(file => form.append('files', file));
  let uploadError: unknown;
  try { await api('/uploads', { method: 'POST', body: form }); }
  catch (cause) { uploadError = cause; }
  let refreshed = true;
  try { await refresh(); } catch { refreshed = false; }
  if (uploadError) {
    const completed = uploadError instanceof ApiError ? uploadError.completedUploads : [];
    const message = uploadError instanceof Error ? uploadError.message : 'The upload did not finish.';
    if (completed.length) throw new Error(`${completed.length} of ${files.length} documents uploaded to Box. ${message} ${refreshed ? 'Check Materials and retry only the remaining files.' : 'The materials list could not be refreshed. Check Box before retrying.'}`);
    throw new Error(`${message} ${refreshed ? 'Check Materials before retrying.' : 'The materials list could not be refreshed. Check Box before retrying.'}`);
  }
  if (!refreshed) throw new Error('The documents were uploaded to Box, but the materials list could not be refreshed. Check Box before retrying.');
}
