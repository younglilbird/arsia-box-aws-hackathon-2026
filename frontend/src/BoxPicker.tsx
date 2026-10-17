import { useEffect, useRef, useState } from 'react';
import { ApiError, api, json } from './api';
import type { BoxBrowseEntry, BoxBrowseFolder, BoxFile } from './types';

interface Props {
  category: string;
  disabled: boolean;
  onClose: () => void;
  onImported: (count: number, warnings: string[]) => Promise<void>;
}
const eligible = (file: BoxBrowseEntry) => file.type === 'file' && /\.(docx|pdf)$/i.test(file.name) && (file.size ?? 0) <= 12 * 1024 * 1024 && Boolean(file.version_id);

export default function BoxPicker({ category, disabled, onClose, onImported }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const generation = useRef(0);
  const submitting = useRef(false);
  const [folderId, setFolderId] = useState('0');
  const [folder, setFolder] = useState<BoxBrowseFolder | null>(null);
  const [trail, setTrail] = useState<Array<{ id: string; name: string }>>([{ id: '0', name: 'All files' }]);
  const [selected, setSelected] = useState<Map<string, BoxBrowseEntry>>(new Map());
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');
  const [browseError, setBrowseError] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [addedCount, setAddedCount] = useState(0);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = dialog.current;
    element?.showModal(); heading.current?.focus({ preventScroll: true });
    return () => { element?.close(); if (opener?.isConnected) opener.focus({ preventScroll: true }); };
  }, []);

  useEffect(() => {
    const request = ++generation.current;
    const abort = new AbortController();
    setLoading(true); setError(''); setBrowseError(false); setFolder(null);
    api<BoxBrowseFolder>(`/box/folders/${encodeURIComponent(folderId)}`, { signal: abort.signal }).then(value => {
      if (request === generation.current) setFolder(value);
    }).catch(cause => {
      if (!abort.signal.aborted && request === generation.current) { setError(cause instanceof Error ? cause.message : 'Box files could not be loaded.'); setBrowseError(true); }
    }).finally(() => { if (!abort.signal.aborted && request === generation.current) setLoading(false); });
    return () => abort.abort();
  }, [folderId, retry]);

  function openFolder(entry: { id: string; name: string }, index?: number) {
    if (adding) return;
    setFolderId(entry.id);
    setTrail(previous => index === undefined ? [...previous, entry] : previous.slice(0, index + 1));
  }
  function toggle(file: BoxBrowseEntry) {
    if (adding || !eligible(file)) return;
    setSelected(previous => {
      const next = new Map(previous);
      if (next.has(file.id)) next.delete(file.id);
      else if (next.size < 10) next.set(file.id, file);
      return next;
    });
  }
  async function addFiles() {
    if (submitting.current || disabled || !selected.size) return;
    submitting.current = true; setAdding(true); setError(''); setBrowseError(false); setWarnings([]); setAddedCount(0);
    try {
      const result = await api<{ files: BoxFile[]; warnings?: string[] }>('/imports', json('POST', { category, files: [...selected.values()].map(file => ({ id: file.id, version_id: file.version_id })) }));
      const count = result.files?.length || 0;
      const messages = result.warnings || [];
      setWarnings(messages); setAddedCount(count);
      const copied = new Set(result.files.map(file => file.origin_url).filter(Boolean));
      setSelected(previous => new Map([...previous].filter(([, file]) => !copied.has(file.url))));
      if (count || messages.length) await onImported(count, messages);
      if (count === selected.size && !messages.length) onClose();
      else if (!count && !messages.length) setError('No files were added. Check the selected files and try again.');
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'The copy did not finish. Check the materials before trying again.';
      if (cause instanceof ApiError && cause.status === 409) {
        setSelected(new Map()); setWarnings([message]); setRetry(value => value + 1);
      } else setError(message);
    } finally { submitting.current = false; setAdding(false); }
  }

  return <dialog ref={dialog} className="box-picker" aria-labelledby="box-picker-title" onCancel={event => { event.preventDefault(); if (!adding) onClose(); }}>
    <div className="picker-header"><div><h2 id="box-picker-title" ref={heading} tabIndex={-1}>Add from Box</h2><p>{category}</p></div><button className="icon-button" aria-label="Close Box picker" disabled={adding} onClick={onClose}><span aria-hidden="true">×</span></button></div>
    <nav className="picker-breadcrumbs" aria-label="Box folder path">{trail.map((item, index) => <span key={`${item.id}-${index}`}><button disabled={adding || loading || index === trail.length - 1} aria-current={index === trail.length - 1 ? 'location' : undefined} onClick={() => openFolder(item, index)}>{item.name}</button>{index < trail.length - 1 && <span aria-hidden="true"> / </span>}</span>)}</nav>
    <div className="picker-body" aria-busy={loading || adding}>
      {error && <div className="message error-message" role="alert"><span>{error}</span>{!adding && browseError && <button className="text-button" onClick={() => setRetry(value => value + 1)}>Retry</button>}</div>}
      {warnings.map((warning, index) => <p className="picker-warning" role="alert" key={index}>{warning}</p>)}
      {addedCount > 0 && <p className="picker-added" role="status">{addedCount} {addedCount === 1 ? 'file' : 'files'} added.</p>}
      {loading ? <div className="picker-loading" role="status"><span className="spinner" />Loading files…</div> : folder && <>
        {folder.truncated && <p className="picker-warning">Only part of this folder is listed. Open a subfolder to find more files.</p>}
        {folder.entries.length ? <ul className="picker-files">{folder.entries.map(file => <li key={file.id}>{file.type === 'folder' ? <button className="picker-folder" disabled={adding} onClick={() => openFolder(file)}><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true"><path d="M3 6h7l2 3h9v11H3V6Z" /></svg><span>{file.name}</span><span aria-hidden="true">›</span></button> : <label className="picker-file"><input type="checkbox" checked={selected.has(file.id)} disabled={adding || !eligible(file) || (!selected.has(file.id) && selected.size >= 10)} onChange={() => toggle(file)} /><span><strong>{file.name}</strong><small>{(file.extension || file.name.split('.').pop() || '').toUpperCase()}{file.size !== undefined ? ` · ${Math.max(1, Math.round(file.size / 1024))} KB` : ''}</small></span></label>}</li>)}</ul> : <p className="picker-empty">No Word or PDF files here.</p>}
      </>}
    </div>
    <div className="picker-footer"><div><span>{selected.size} / 10 selected</span>{selected.size > 0 && <button className="text-button" disabled={adding} onClick={() => setSelected(new Map())}>Clear</button>}</div><button className="button primary" disabled={!selected.size || adding || disabled || loading} onClick={addFiles}>{adding ? <><span className="spinner" />Adding…</> : 'Add files'}</button></div>
  </dialog>;
}
