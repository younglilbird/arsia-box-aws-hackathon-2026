import { useEffect, useRef } from 'react';

export default function DeleteDraftDialog({ label, title = 'Delete this draft?', description = 'Its generated backup files in Box will also be deleted. Original materials will be kept.', busy, error, onCancel, onDelete }: { label: string; title?: string; description?: string; busy: boolean; error: string; onCancel: () => void; onDelete: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = dialog.current; element?.showModal();
    return () => {
      element?.close();
      const fallback = document.querySelector<HTMLButtonElement>('.step[aria-current="step"]');
      (opener?.isConnected ? opener : fallback)?.focus({ preventScroll: true });
    };
  }, []);
  return <dialog className="box-picker delete-dialog" ref={dialog} aria-labelledby="delete-draft-title" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <div className="picker-header"><div><h2 id="delete-draft-title">{title}</h2><p>{label}</p></div></div>
    <div className="delete-dialog-body"><p>{description}</p>{error && <div className="message error-message" role="alert"><span>{error}</span></div>}</div>
    <div className="delete-dialog-actions"><button className="button subtle" autoFocus disabled={busy} onClick={onCancel}>Cancel</button><button className="button destructive" disabled={busy} onClick={onDelete}>{busy ? <><span className="spinner" />Deleting…</> : 'Delete'}</button></div>
  </dialog>;
}
