import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { api, json, safeBoxUrl } from './api';
import type { AppStatus, BoxFile, Category, DeleteResult, Evidence, MaterialDeleteResult, Run } from './types';
import EvaluationPanel from './EvaluationPanel';
import { revealSource, useInputModality, useSurfaceMotion } from './motion';
import { useForegroundRefresh } from './useForegroundRefresh';
import BoxPicker from './BoxPicker';
import DeleteDraftDialog from './DeleteDraftDialog';
import { reportBodyForReader } from './document';
import { requestExportDownload, type NativeDownload } from './download';
import { evidencePreview, normalizedEvidenceText } from './evidence';
import GuidancePanel from './GuidancePanel';
import { uploadDocuments } from './uploads';

type Step = 'materials' | 'review' | 'finish';
type Panel = 'evidence' | 'review';
const steps: Array<{ id: Step; title: string }> = [
  { id: 'materials', title: 'Materials' },
  { id: 'review', title: 'Review' },
  { id: 'finish', title: 'Finish' },
];
const stageNames: Record<string, string> = {
  queued: 'Waiting to start', discover: 'Finding your source documents', read: 'Reading Word and PDF documents',
  extract: 'Extracting source-backed evidence', draft: 'Writing your annual review', box_review: 'Checking the original files with Box AI',
  review: 'Reviewing facts and personal contribution', revise: 'Applying a revision', ready: 'Draft ready for your review',
  final_evaluation: 'Evaluating the revised draft',
  improve: 'Improving this review', improve_draft: 'Applying your guidance', improve_evaluate: 'Evaluating the updated review',
  improve_read: 'Rechecking the review sources', improve_patch: 'Applying your guidance', improve_ready: 'Updated review ready',
  save_draft: 'Preparing your documents', completed: 'Draft ready for your review', failed: 'Generation stopped',
};
const running = (run: Run | null) => Boolean(run && ['queued', 'running', 'processing'].includes(run.status));
const referenceNumber = (id: string) => id.match(/\d+$/)?.[0] || id;
const displayReferences = (text: string) => text.replace(/\[E(\d+)\]/g, '[$1]');
const fileExtension = (file: BoxFile) => (file.extension || file.format || file.name.split('.').pop() || '').toLowerCase();
const sourceUrl = (file: { id?: string; url?: string; source_url?: string }) => safeBoxUrl(file.url || file.source_url) || (/^\d+$/.test(file.id || '') ? `https://app.box.com/file/${file.id}` : undefined);
const unwrap = (value: Run | { run: Run }): Run => 'run' in value ? value.run : value;
function dateLabel(value?: string | number) {
  if (value === undefined) return 'Annual self-review';
  const date = new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value);
  return Number.isNaN(date.getTime()) ? 'Annual self-review' : new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(date);
}
function fileSize(size?: number) { return size === undefined ? '' : size < 1024 * 1024 ? `${Math.max(1, Math.round(size / 1024))} KB` : `${(size / 1024 / 1024).toFixed(1)} MB`; }
function getStoredRun() {
  const query = new URLSearchParams(location.search).get('run');
  try { return query || localStorage.getItem('year-in-review:last-run') || ''; } catch { return query || ''; }
}
function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    book: <><path d="M4 3h11l5 5v13H6a3 3 0 0 1-3-3V6a3 3 0 0 1 1-3Z" /><path d="M15 3v6h5M8 12h8M8 16h6" /></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m9 5 7 7-7 7" />,
    link: <><path d="M14 4h6v6M20 4l-9 9M10 4H4v16h16v-6" /></>,
    refresh: <><path d="M20 10a8 8 0 1 0-1 7M20 10V4m0 6h-6" /></>,
    evidence: <><path d="M4 5h16v14H4zM8 9h8M8 13h5" /><path d="m15 18 2 2 4-5" /></>,
    edit: <><path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z" /></>,
    trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6" /></>,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    download: <><path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4" /></>,
    person: <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
    alert: <><path d="M12 3 2 21h20L12 3Z" /><path d="M12 9v5m0 3v1" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.book}</svg>;
}
function BoxLink({ url, children, className = '' }: { url?: string; children: ReactNode; className?: string }) {
  const href = safeBoxUrl(url);
  return href ? <a className={className} href={href} target="_blank" rel="noopener noreferrer">{children}<Icon name="link" size={12} /></a> : null;
}
function Markdown({ text, onReference }: { text: string; onReference: (id: string) => void }) {
  function inline(value: string, prefix: string): ReactNode[] {
    return value.split(/(\[E\d+\]|\*\*[^*\n]+\*\*)/g).filter(Boolean).map((part, i) => {
      const key = `${prefix}-${i}`;
      if (/^\[E\d+\]$/.test(part)) return <button key={key} className="citation" title={`Show source for reference ${referenceNumber(part.slice(1, -1))}`} onClick={() => onReference(part.slice(1, -1))}>[{referenceNumber(part.slice(1, -1))}]</button>;
      if (part.startsWith('**') && part.endsWith('**')) return <strong key={key}>{inline(part.slice(2, -2), key)}</strong>;
      return <Fragment key={key}>{part}</Fragment>;
    });
  }
  const nodes: ReactNode[] = [];
  const lines = text.replace(/\r/g, '').split('\n');
  let paragraph: string[] = [], list: string[] = [], ordered = false;
  const flushParagraph = () => { if (paragraph.length) { const key = nodes.length; nodes.push(<p key={key}>{inline(paragraph.join(' '), String(key))}</p>); paragraph = []; } };
  const flushList = () => { if (list.length) { const key = nodes.length; const items = list.map((item, i) => <li key={i}>{inline(item, `${key}-${i}`)}</li>); nodes.push(ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>); list = []; } };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flushParagraph(); flushList(); continue; }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    const bullet = line.match(/^[-*+]\s+(.+)$/), number = line.match(/^\d+[.)]\s+(.+)$/);
    if (heading) { flushParagraph(); flushList(); const key = nodes.length; const content = inline(heading[2], String(key)); nodes.push(heading[1].length === 1 ? <h1 key={key}>{content}</h1> : heading[1].length === 2 ? <h2 key={key}>{content}</h2> : <h3 key={key}>{content}</h3>); }
    else if (bullet || number) { flushParagraph(); const nextOrdered = Boolean(number); if (list.length && ordered !== nextOrdered) flushList(); ordered = nextOrdered; list.push((bullet || number)![1]); }
    else if (/^[-*_]{3,}$/.test(line)) { flushParagraph(); flushList(); }
    else { flushList(); paragraph.push(line); }
  }
  flushParagraph(); flushList();
  return <>{nodes}</>;
}

export default function App() {
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [history, setHistory] = useState<Run[]>([]);
  const [step, setStep] = useState<Step>('materials');
  const [run, setRun] = useState<Run | null>(null);
  const [draft, setDraft] = useState('');
  const [dirty, setDirty] = useState(false);
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState('');
  const [answers, setAnswers] = useState('');
  const [targetScore, setTargetScore] = useState(90);
  const [panel, setPanel] = useState<Panel>('evidence');
  const [focusedEvidence, setFocusedEvidence] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [noticeTone, setNoticeTone] = useState<'notice' | 'warning'>('notice');
  const [pollError, setPollError] = useState('');
  const [pollEpoch, setPollEpoch] = useState(0);
  const [pickerCategory, setPickerCategory] = useState('');
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<Run | null>(null);
  const [deleteError, setDeleteError] = useState('');
  const [materialTarget, setMaterialTarget] = useState<BoxFile | null>(null);
  const [materialDeleteError, setMaterialDeleteError] = useState('');
  const [preparedDownload, setPreparedDownload] = useState<(NativeDownload & { runId: string; markdown: string; confirmed: boolean; format: 'docx' | 'pdf' }) | null>(null);
  const [historyOpen, setHistoryOpen] = useState(() => window.matchMedia('(min-width: 901px)').matches);
  const statusSequence = useRef(0), historySequence = useRef(0);
  const actionLock = useRef(false), currentRunId = useRef(''), dirtyRef = useRef(false);
  const selectionEpoch = useRef(0);
  const submittedGuidance = useRef<{ id: string; value: string } | null>(null);
  const evidenceContainer = useRef<HTMLDivElement>(null);
  const stepContainer = useRef<HTMLDivElement>(null);
  const categoryInputs = useRef<Record<string, HTMLInputElement | null>>({});
  const isRunning = running(run);
  const canMutate = !busy && !isRunning;
  const canChangeMaterials = canMutate && !dirty && !history.some(item => running(item));
  const categories: Category[] = status?.categories || [];
  const totalFiles = categories.reduce((count, category) => count + (category.filecount ?? category.files.length), 0);
  const evidence = run?.evidence || [];
  const latestEvaluation = run?.evaluations?.final?.status === 'completed' && !dirty ? run.evaluations.final : undefined;
  const issues = latestEvaluation?.issues || [];
  const questions = latestEvaluation?.missing_information ?? run?.missing_information ?? [];
  const confirmed = run?.reviewer_confirmed === true && !dirty;
  const needsReview = Boolean(draft && run?.status === 'completed' && run.review?.validation_status === 'needs_review');
  const boxFiles = run?.box_files || run?.draft_box_files || [];
  const coveredSources = run?.coverage?.analyzed_files ?? run?.coverage?.read_files ?? run?.sources?.length ?? 0;
  const discoveredSources = run?.coverage?.discovered_files ?? run?.coverage?.discovered ?? run?.sources?.length ?? 0;
  const skippedSources = run?.coverage?.skipped?.length || Math.max(0, discoveredSources - coveredSources);
  const partialText = run?.coverage?.truncated || (typeof run?.coverage?.character_coverage === 'number' && run.coverage.character_coverage < .999);
  const coverageNotes = [skippedSources ? `${skippedSources} ${skippedSources === 1 ? 'file' : 'files'} skipped` : '', partialText ? 'Partial text' : ''].filter(Boolean).join(' · ');
  const wordCount = draft.trim() ? draft.trim().split(/\s+/).length : 0;
  useInputModality();
  useSurfaceMotion(stepContainer, step, 'step');
  useSurfaceMotion(evidenceContainer, panel, 'panel');

  const refreshStatus = useCallback(async () => { const request = ++statusSequence.current; const next = await api<AppStatus>('/status'); if (request === statusSequence.current) setStatus(next); }, []);
  const refreshHistory = useCallback(async () => { const request = ++historySequence.current; const response = await api<{ runs: Run[] } | Run[]>('/runs'); const items = Array.isArray(response) ? response : response.runs || []; if (request === historySequence.current) setHistory(items); return items; }, []);
  const foregroundRefresh = useCallback(async () => {
    if (actionLock.current) return;
    const statusRequest = statusSequence.current + 1;
    const results = await Promise.allSettled([refreshStatus(), refreshHistory()]);
    const failed = results.find(result => result.status === 'rejected');
    if (failed?.status === 'rejected') {
      const message = failed.reason instanceof Error ? failed.reason.message : 'The workspace could not be refreshed.';
      setError(message);
      if (results[0].status === 'rejected' && statusSequence.current === statusRequest) setStatus(previous => previous ? { ...previous, box: { ...previous.box, connected: false, error: message } } : previous);
    }
  }, [refreshStatus, refreshHistory]);
  useForegroundRefresh(foregroundRefresh);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 901px)');
    const update = () => setHistoryOpen(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const acceptRun = useCallback((next: Run, newSelection = false) => {
    const changedRun = currentRunId.current !== next.id;
    currentRunId.current = next.id;
    setRun(next);
    if (changedRun || !dirtyRef.current) { if (changedRun || typeof next.report_markdown === 'string') setDraft(next.report_markdown || ''); setDirty(false); dirtyRef.current = false; }
    if (changedRun) { setEditing(false); setAcknowledged(false); setFocusedEvidence(''); setAnswers(''); }
    if (submittedGuidance.current?.id === next.id && !running(next)) {
      const submitted = submittedGuidance.current;
      if (!next.improvement_error) setAnswers(value => value === submitted.value ? '' : value);
      submittedGuidance.current = null;
    }
    if (newSelection || (next.status === 'completed' && changedRun)) setStep('review');
    try { localStorage.setItem('year-in-review:last-run', next.id); } catch { /* Storage is optional. */ }
    const url = new URL(location.href); url.searchParams.set('run', next.id); window.history.replaceState(null, '', url);
  }, []);

  useEffect(() => {
    let mounted = true;
    const epoch = selectionEpoch.current;
    const canRestoreSelection = () => mounted && selectionEpoch.current === epoch && !dirtyRef.current;
    const previous = getStoredRun();
    Promise.allSettled([refreshStatus(), refreshHistory()]).then(results => {
      if (!mounted) return;
      const rejected = results.find(result => result.status === 'rejected');
      if (rejected?.status === 'rejected') setError(rejected.reason instanceof Error ? rejected.reason.message : 'The local workspace could not be loaded.');
      if (canRestoreSelection() && !previous && !currentRunId.current && results[1].status === 'fulfilled') {
        const items = results[1].value || [];
        const selected = items.find(item => running(item)) || items[0];
        if (selected) api<Run>(`/runs/${selected.id}`).then(value => { if (canRestoreSelection()) acceptRun(unwrap(value), true); }).catch(() => {});
      }
    });
    if (/^[A-Za-z0-9_-]{1,100}$/.test(previous)) api<Run>(`/runs/${previous}`).then(value => { if (canRestoreSelection()) acceptRun(unwrap(value), true); }).catch(() => { /* A removed local draft should not block materials. */ });
    return () => { mounted = false; };
  }, [acceptRun, refreshHistory, refreshStatus]);

  useEffect(() => {
    if (!run?.id || !isRunning) return;
    let alive = true, timer: ReturnType<typeof setTimeout>, failures = 0;
    const poll = async () => {
      try {
        const next = unwrap(await api<Run>(`/runs/${run.id}`));
        if (!alive || currentRunId.current !== run.id) return;
        failures = 0; setPollError(''); acceptRun(next);
        if (!running(next)) { refreshHistory().catch(() => {}); refreshStatus().catch(() => {}); return; }
      } catch (cause) {
        if (!alive) return;
        failures += 1;
        if (failures >= 3) { setPollError(cause instanceof Error ? cause.message : 'Progress updates stopped. Reconnect to check the run.'); return; }
      }
      timer = setTimeout(poll, 1800);
    };
    timer = setTimeout(poll, 700);
    return () => { alive = false; clearTimeout(timer); };
  }, [run?.id, isRunning, pollEpoch, acceptRun, refreshHistory, refreshStatus]);

  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 6500); return () => clearTimeout(timer); }, [notice]);
  useEffect(() => {
    const protectUnsavedWork = (event: BeforeUnloadEvent) => {
      if (!dirty && !answers.trim()) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', protectUnsavedWork);
    return () => window.removeEventListener('beforeunload', protectUnsavedWork);
  }, [dirty, answers]);

  async function act(name: string, operation: () => Promise<void>) {
    if (actionLock.current) return;
    actionLock.current = true; setBusy(name); setError(''); setNoticeTone('notice');
    try { await operation(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'The action did not complete. Try again after checking the local service.'); }
    finally { actionLock.current = false; setBusy(''); }
  }
  async function upload(category: string, files: File[]) {
    if (!files.length || !canChangeMaterials) return;
    if (files.length > 10) { setError('Choose up to 10 documents per upload.'); return; }
    if (files.some(file => !/\.(pdf|docx)$/i.test(file.name))) { setError('Choose Word (.docx) or PDF documents. Other formats are not supported in this review.'); return; }
    if (files.some(file => file.size > 12 * 1024 * 1024)) { setError('Each source document must be 12 MB or smaller.'); return; }
    await act(`upload:${category}`, async () => {
      await uploadDocuments(category, files, refreshStatus);
      setNotice(`${files.length} ${files.length === 1 ? 'document' : 'documents'} uploaded to ${category} in Box.`);
    });
  }
  async function generate() {
    if (!totalFiles || !canMutate) return;
    await act('generate', async () => { selectionEpoch.current += 1; if (run && dirty) await persistEdits(); acceptRun(unwrap(await api<Run>('/runs', json('POST', { notes }))), true); await refreshHistory(); });
  }
  async function persistEdits(): Promise<Run> {
    if (!run) throw new Error('Choose a draft first.');
    if (!dirty) return run;
    const next = unwrap(await api<Run>(`/runs/${run.id}/report`, json('PUT', { report_markdown: draft, reviewer_confirmed: false, expected_report_hash: run.report_hash })));
    dirtyRef.current = false; setDirty(false); setAcknowledged(false); acceptRun(next); return next;
  }
  function editDraft(value: string) {
    selectionEpoch.current += 1;
    const known = new Set(evidence.map(item => item.id));
    const restored = value.replace(/\[(\d+)\]/g, (match, number: string) => known.has(`E${number}`) ? `[E${number}]` : match);
    setDraft(restored); setDirty(true); dirtyRef.current = true; setAcknowledged(false);
  }
  function focusReference(id: string) {
    setFocusedEvidence(id); setPanel('evidence');
    requestAnimationFrame(() => {
      const target = evidenceContainer.current?.querySelector<HTMLElement>(`[data-reference="${id}"]`);
      if (target) revealSource(evidenceContainer.current, target);
    });
  }
  async function download(format: 'docx' | 'pdf') {
    await act(`download:${format}`, async () => {
      setPreparedDownload(null);
      const selected = await persistEdits();
      const prepared = await requestExportDownload(selected.id, format);
      setPreparedDownload({ ...prepared, runId: selected.id, markdown: selected.report_markdown || '', confirmed: selected.reviewer_confirmed === true, format });
      setNotice(`${format === 'docx' ? 'Word' : 'PDF'} download requested. Check your browser’s downloads.`);
    });
  }
  async function improveReview() {
    if (!run || !answers.trim() || !canMutate || dirty || run.status !== 'completed') return;
    const selectedId = run.id, guidance = answers;
    await act('improve', async () => {
      const next = unwrap(await api<Run>(`/runs/${selectedId}/improve`, json('POST', { answers: guidance, target_score: targetScore, expected_report_hash: run.report_hash })));
      if (next.id !== selectedId) throw new Error('The improvement did not return the selected review. Refresh the workspace before retrying.');
      submittedGuidance.current = { id: selectedId, value: guidance };
      setAcknowledged(false); acceptRun(next); await refreshHistory();
    });
  }
  async function deleteDraft() {
    if (!deleteTarget || running(deleteTarget)) return;
    const targetId = deleteTarget.id;
    await act('delete', async () => {
      setDeleteError('');
      let result: DeleteResult;
      try { result = await api<DeleteResult>(`/runs/${targetId}`, { method: 'DELETE' }); }
      catch (cause) { setDeleteError(cause instanceof Error ? cause.message : 'The draft could not be deleted.'); return; }
      if (!result.deleted) {
        setDeleteError(result.warnings?.join(' ') || 'Some generated files could not be deleted. This draft is kept so you can retry.');
        if (result.run && currentRunId.current === targetId) acceptRun(result.run);
        await refreshHistory().catch(() => {});
        return;
      }
      setDeleteTarget(null); setImportWarnings(result.warnings || []);
      setNoticeTone(result.warnings?.length ? 'warning' : 'notice');
      setNotice(result.warnings?.length ? 'Draft deleted. Check the warnings.' : 'Draft deleted.');
      const wasSelected = currentRunId.current === targetId;
      if (wasSelected) {
        selectionEpoch.current += 1;
        currentRunId.current = ''; dirtyRef.current = false;
        setRun(null); setDraft(''); setDirty(false); setEditing(false); setAcknowledged(false); setFocusedEvidence(''); setAnswers(''); setStep('materials');
        try { localStorage.removeItem('year-in-review:last-run'); } catch { /* Storage is optional. */ }
        const url = new URL(location.href); url.searchParams.delete('run'); window.history.replaceState(null, '', url);
      }
      try {
        const items = await refreshHistory();
        if (wasSelected) {
          const next = items.find(item => item.id !== targetId);
          if (next) acceptRun(unwrap(await api<Run>(`/runs/${next.id}`)), true);
        }
        await refreshStatus();
      } catch { setError('The draft was deleted, but the workspace could not be refreshed.'); }
    });
  }
  async function deleteMaterial() {
    const materialId = materialTarget?.material_id;
    if (!materialId || !canChangeMaterials) return;
    await act('delete-material', async () => {
      setMaterialDeleteError('');
      let result: MaterialDeleteResult;
      try { result = await api<MaterialDeleteResult>(`/materials/${encodeURIComponent(materialId)}`, { method: 'DELETE' }); }
      catch (cause) { setMaterialDeleteError(cause instanceof Error ? cause.message : 'The material could not be deleted.'); return; }
      if (!result.deleted) { setMaterialDeleteError(result.warnings?.join(' ') || 'The material was not deleted. Check Box before trying again.'); return; }
      setMaterialTarget(null); setImportWarnings(result.warnings || []);
      setNoticeTone(result.warnings?.length ? 'warning' : 'notice');
      setNotice(result.warnings?.length ? 'Material deleted. Check the warnings.' : 'Material deleted. Existing reports were kept.');
      const selectedId = currentRunId.current;
      const results = await Promise.allSettled([
        refreshStatus(),
        selectedId ? api<Run>(`/runs/${selectedId}`).then(next => { if (currentRunId.current === selectedId) acceptRun(unwrap(next)); }) : Promise.resolve(),
      ]);
      if (results.some(result => result.status === 'rejected')) setError('The material was deleted, but the workspace could not be refreshed.');
    });
  }
  const stageLabel = stageNames[run?.stage || run?.status || ''] || (isRunning ? 'Working on your review' : 'Your annual self-review');
  const runError = typeof run?.error === 'string' ? run.error : run?.error?.message;

  return <div className="app-shell">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="app-header">
      <a href="/" className="brand" aria-label="Arsia home" onClick={event => { if (!event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); setStep('materials'); } }}><span><strong>Arsia</strong><small>Annual Review Agent</small></span></a>
      <div className="header-meta"><span className={`connection ${status?.box.connected ? 'connected' : ''}`}><i />Box {status ? status.box.connected ? 'connected' : 'needs attention' : error ? 'needs attention' : 'connecting'}</span></div>
    </header>

    <aside className="workflow-rail">
      <div className="review-person"><span className="avatar">{status?.employee_name?.split(' ').map(word => word[0]).join('').slice(0, 2) || <Icon name="person" />}</span><div><strong>{status?.employee_name || 'Annual self-review'}</strong>{status?.year && <span>{status.year} review</span>}</div></div>
      <nav className="step-navigation" aria-label="Review steps">{steps.map((item, index) => <button key={item.id} aria-current={step === item.id ? 'step' : undefined} disabled={item.id === 'review' ? !run : item.id === 'finish' ? !draft || isRunning || run?.status === 'failed' : false} className={`step ${step === item.id ? 'active' : ''}`} onClick={() => item.id === 'finish' ? act('finish', async () => { await persistEdits(); setStep('finish'); }) : setStep(item.id)}><span className="step-number">{item.id === 'materials' && totalFiles > 0 && step !== 'materials' ? <Icon name="check" size={13} /> : index + 1}</span><span><strong>{item.title}</strong></span>{step === item.id && <span className="step-position" />}</button>)}</nav>

      <details className="recent-runs" open={historyOpen} onToggle={event => setHistoryOpen(event.currentTarget.open)}><summary>Recent drafts</summary><div className="history-rows">{history.length ? history.map(item => <div className={`history-row ${run?.id === item.id ? 'selected' : ''}`} key={item.id}><button className="history-load" disabled={Boolean(busy) || dirty} title={dirty ? 'Save your edits before switching drafts.' : undefined} onClick={() => act('load', async () => { selectionEpoch.current += 1; acceptRun(unwrap(await api<Run>(`/runs/${item.id}`)), true); })}><Icon name="book" size={15} /><span><strong>{dateLabel(item.created_at || item.updated_at)}</strong><small>{running(item) ? 'In progress' : item.status === 'failed' ? 'Failed' : item.reviewer_confirmed ? 'Human reviewed' : item.review?.validation_status === 'needs_review' ? 'Needs review' : 'Draft'}</small></span></button><button className="icon-button history-delete" aria-label={`Delete draft ${dateLabel(item.created_at || item.updated_at)}`} disabled={Boolean(busy) || dirty || running(item) || item.deletion_preview?.can_delete === false} onClick={() => { setDeleteError(''); setDeleteTarget(item); }}><Icon name="trash" size={15} /></button></div>) : <p>No drafts yet.</p>}</div></details>

    </aside>

    <main id="workspace" className={`workspace step-${step}`}>
      {error && <div className="message error-message" role="alert"><Icon name="alert" /><span>{error}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><Icon name="close" size={15} /></button></div>}
      {status?.box.error && !status.box.connected && <div className="message error-message" role="alert"><Icon name="alert" /><span>{status.box.error}</span></div>}
      {run?.save_warnings?.map((warning, index) => <div key={index} className="message warning-message" role="alert"><Icon name="alert" /><span>{warning}</span></div>)}
      {run?.improvement_error && <div className="message error-message" role="alert"><Icon name="alert" /><span>{run.improvement_error}</span></div>}
      {needsReview && !confirmed && <div className="message warning-message" role="status"><Icon name="alert" /><span>Draft available. Check its facts and sources before using it.</span></div>}
      {importWarnings.map((warning, index) => <div key={index} className="message warning-message" role="alert"><Icon name="alert" /><span>{warning}</span><button className="icon-button" aria-label="Dismiss import warning" onClick={() => setImportWarnings(previous => previous.filter((_, i) => i !== index))}><Icon name="close" size={15} /></button></div>)}

      <div className="step-content" ref={stepContainer}>
      {step === 'materials' && <>
        <div className="page-heading"><h1>Materials</h1><div className="heading-actions"><BoxLink url={status?.workspace_folder_url}>Open in Box</BoxLink><span className="state-tag neutral">{totalFiles} {totalFiles === 1 ? 'document' : 'documents'}</span></div></div>
        <div className="materials-layout"><section className="materials-register" aria-label="Review materials">
          {!status && <div className="loading-state"><span className="spinner" />Connecting to your Box materials…<button className="text-button" onClick={() => act('refresh', refreshStatus)}>Try again</button></div>}
          {categories.map(category => <section key={category.name} className={`category-section ${busy === `upload:${category.name}` ? 'uploading' : ''}`} onDragOver={event => { if (canChangeMaterials) event.preventDefault(); }} onDrop={event => { event.preventDefault(); upload(category.name, Array.from(event.dataTransfer.files)); }}>
            <div className="category-heading"><div><h2>{category.name}<span>{category.filecount ?? category.files.length}</span></h2></div><div className="category-actions"><button className="button subtle small" disabled={!status?.box.connected || !canChangeMaterials} onClick={() => setPickerCategory(category.name)}>Add from Box</button><button className="button subtle small" aria-busy={busy === `upload:${category.name}`} disabled={!status?.box.connected || !canChangeMaterials} onClick={() => categoryInputs.current[category.name]?.click()}>{busy === `upload:${category.name}` ? <span className="spinner" /> : <Icon name="upload" size={14} />}{busy === `upload:${category.name}` ? 'Uploading…' : 'Upload'}</button></div><input ref={element => { categoryInputs.current[category.name] = element; }} className="sr-only" tabIndex={-1} aria-label={`Upload Word or PDF to ${category.name}`} type="file" accept=".docx,.pdf" multiple onChange={event => { upload(category.name, Array.from(event.target.files || [])); event.target.value = ''; }} /></div>
            {category.files.length ? <ul className="file-list">{category.files.map(file => <li key={file.url || file.name}><span className={`file-symbol ${fileExtension(file) === 'pdf' ? 'pdf' : 'word'}`}>{fileExtension(file) === 'pdf' ? 'PDF' : 'W'}</span><span className="file-detail"><BoxLink url={sourceUrl(file)}>{file.name}</BoxLink><small>{fileExtension(file).toUpperCase()}{file.size !== undefined ? ` / ${fileSize(file.size)}` : ''}{file.origin_url && <BoxLink url={file.origin_url} className="original-link">Original</BoxLink>}</small></span><BoxLink url={sourceUrl(file)} className="file-open">Open in Box</BoxLink>{file.material_id && <button className="icon-button material-delete" aria-label={`Delete material ${file.name}`} disabled={!canChangeMaterials} onClick={() => { setMaterialDeleteError(''); setMaterialTarget(file); }}><Icon name="trash" size={15} /></button>}</li>)}</ul> : <div className="category-empty"><Icon name="book" size={20} /><p>Drop Word or PDF here.</p></div>}
          </section>)}
        </section></div>
        <section className="generation-brief"><label htmlFor="generation-notes">Context <span>Optional</span></label><textarea id="generation-notes" value={notes} onChange={event => setNotes(event.target.value)} maxLength={8000} rows={2} placeholder="Add context for this review." disabled={!canMutate} /><div className="generate-row"><span>{totalFiles > 25 ? 'The draft will cover at most 25 documents. Narrow the folders for full coverage.' : totalFiles ? null : 'Upload a document to begin.'}</span><button className="button primary" disabled={!status?.box.connected || !totalFiles || !canMutate} onClick={generate}>{busy === 'generate' ? <><span className="spinner" />Starting…</> : isRunning ? 'Review in progress' : 'Generate review'}</button></div></section>
      </>}

      {step === 'review' && <>
        <div className="page-heading review-heading"><h1>Review</h1><span className={`state-tag ${run?.status === 'failed' ? 'failed' : confirmed ? 'reviewed' : 'draft'}`}>{confirmed ? <Icon name="check" size={13} /> : null}{run?.status === 'failed' ? 'Failed' : confirmed ? 'Human reviewed' : needsReview ? 'Needs review' : 'Draft'}</span></div>
        {isRunning && <section className="progress-section" aria-live="polite"><div className="progress-title"><span className="spinner" /><strong>{stageLabel}</strong><span>{typeof run?.progress === 'number' ? `${Math.min(100, Math.max(0, run.progress))}%` : 'In progress'}</span></div>{typeof run?.progress === 'number' && <progress max={100} value={Math.min(100, Math.max(0, run.progress))} aria-label="Generation progress" />}</section>}
        {pollError && <div className="message warning-message" role="status"><span>{pollError} The server may still be working.</span><button className="text-button" onClick={() => { setPollError(''); setPollEpoch(value => value + 1); }}>Reconnect to progress</button></div>}
        {run?.status === 'failed' && <div className="message error-message" role="alert"><Icon name="alert" /><span>{runError || 'Generation or validation failed. Start a new attempt when ready.'}</span><button className="text-button" onClick={() => setStep('materials')}>Back to materials</button></div>}
        {run?.evaluations?.final?.status === 'stale' && <p className="edited-note">You edited this report. Automated findings refer to the generated draft; verify source support for your changes.</p>}<div className="review-layout"><section className="document-column"><div className="document-toolbar"><div className="view-switch" aria-label="Document view"><button className={!editing ? 'active' : ''} aria-pressed={!editing} onClick={() => setEditing(false)}>Read</button><button className={editing ? 'active' : ''} aria-pressed={editing} disabled={!draft || isRunning} onClick={() => setEditing(true)}><Icon name="edit" size={12} />Edit</button></div><span className="document-save-state">{dirty ? 'Unsaved changes' : draft ? `${wordCount.toLocaleString()} words` : ''}</span>{dirty && <button className="text-button" disabled={!canMutate} onClick={() => act('edit', async () => { await persistEdits(); setNotice('Your edits were saved. Review is needed for the updated wording.'); })}>{busy === 'edit' ? 'Saving…' : 'Save edits'}</button>}</div>
          <div className="document-paper">{draft ? editing ? <textarea className="document-editor" aria-label="Edit annual self-review" disabled={Boolean(busy) || isRunning} value={displayReferences(draft)} onChange={event => editDraft(event.target.value)} spellCheck /> : <article className="document-body"><header className="document-heading"><h1>Annual Review Summary</h1><p>{[run?.employee_name || status?.employee_name, run?.year || status?.year].filter(Boolean).join(' · ')}</p></header><Markdown text={reportBodyForReader(draft)} onReference={focusReference} /></article> : <div className="document-placeholder"><h2>{run?.status === 'failed' ? 'Failed' : isRunning ? 'Generating review' : 'No draft yet'}</h2></div>}</div>
          <div className="document-actions"><button className="button primary" disabled={!draft || isRunning || Boolean(busy) || run?.status === 'failed'} onClick={() => act('finish', async () => { await persistEdits(); setStep('finish'); })}>Continue to finish<Icon name="chevron" size={14} /></button></div>
        </section><aside className="evidence-panel"><div className="panel-tabs" role="group" aria-label="Evidence panel"><button className={panel === 'evidence' ? 'active' : ''} aria-pressed={panel === 'evidence'} onClick={() => setPanel('evidence')}>Evidence <span>{evidence.length}</span></button><button className={panel === 'review' ? 'active' : ''} aria-pressed={panel === 'review'} onClick={() => setPanel('review')}>Evaluation <span>{issues.length + questions.length}</span></button></div>
          <div className="panel-content" ref={evidenceContainer}>{panel === 'review' && <EvaluationPanel evaluations={run?.evaluations} edited={dirty} />}{panel === 'evidence' && run?.coverage && <div className="coverage-summary"><div><span>Source coverage</span><strong>{coveredSources} / {discoveredSources} documents</strong></div>{coverageNotes && <p>{coverageNotes}</p>}</div>}
          {panel === 'evidence' ? evidence.length ? evidence.map(item => <EvidenceCard key={item.id} item={item} source={run?.sources?.find(source => Boolean(item.source_url || item.url) ? source.url === (item.source_url || item.url) : source.name === item.source_name)} focused={focusedEvidence === item.id} />) : <div className="panel-empty"><p>No evidence yet.</p></div> : <>

            {draft && run && <GuidancePanel questions={questions} value={answers} onChange={setAnswers} target={targetScore} onTargetChange={setTargetScore} disabled={!canMutate || dirty || run.status !== 'completed'} working={busy === 'improve' || (isRunning && Boolean(run.improvement))} dirty={dirty} onImprove={improveReview} />}

          </>}
          </div>
        </aside></div>
      </>}

      {step === 'finish' && <>
        <div className="page-heading"><h1>Finish</h1><span className={`state-tag ${confirmed ? 'reviewed' : 'draft'}`}>{confirmed ? <Icon name="check" size={13} /> : null}{confirmed ? 'Human reviewed' : 'Draft'}</span></div>
        <div className="finish-layout"><section className="finish-document"><div className="finish-summary"><h2>{run?.employee_name || status?.employee_name}'s annual review</h2><p>{wordCount.toLocaleString()} words / {evidence.length} source references</p><button className="text-button" onClick={() => { setStep('review'); setEditing(false); }}>Return to the document</button></div></section>
          <section className="finish-controls"><div className="human-review-block"><h2>{confirmed ? 'Reviewed' : 'Human review'}</h2>{confirmed && <p>Edits require a new review.</p>}{!confirmed && <><label className="review-checkbox"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} disabled={!canMutate} /><span>I checked the facts and sources, verified my contribution, and reviewed this wording.</span></label><button className="button subtle" disabled={!acknowledged || !canMutate || dirty} onClick={() => act('confirm', async () => { if (!run) return; acceptRun(unwrap(await api<Run>(`/runs/${run.id}/confirm`, json('POST', { expected_report_hash: run.report_hash })))); await refreshHistory(); setNotice('Your human review was recorded.'); })}>{busy === 'confirm' ? 'Recording review…' : 'Mark as reviewed'}</button></>}</div>
          <div className="export-block"><div><h2>Documents</h2><span className="state-tag neutral">{confirmed ? 'Reviewed version' : 'Draft version'}</span></div><div className="download-options"><button disabled={!canMutate} aria-busy={busy === 'download:docx'} onClick={() => download('docx')}><span className="file-symbol word">W</span><span><strong>{busy === 'download:docx' ? 'Preparing Word…' : 'Word document'}</strong><small>.docx</small></span>{busy === 'download:docx' ? <span className="spinner" /> : <Icon name="download" size={17} />}</button><button disabled={!canMutate} aria-busy={busy === 'download:pdf'} onClick={() => download('pdf')}><span className="file-symbol pdf">PDF</span><span><strong>{busy === 'download:pdf' ? 'Preparing PDF…' : 'PDF document'}</strong><small>.pdf</small></span>{busy === 'download:pdf' ? <span className="spinner" /> : <Icon name="download" size={17} />}</button></div>{preparedDownload && preparedDownload.runId === run?.id && preparedDownload.markdown === draft && preparedDownload.confirmed === confirmed && !dirty && <a className="prepared-download" href={canMutate ? preparedDownload.href : undefined} download={preparedDownload.filename} aria-disabled={!canMutate}>{preparedDownload.format === 'docx' ? 'Download Word' : 'Download PDF'}<Icon name="download" size={14} /></a>}<button className="button primary save-box-button" disabled={!canMutate} onClick={() => act('save', async () => { if (!run) return; const result = await api<{ files: BoxFile[]; run: Run }>(`/runs/${run.id}/save`, json('POST')); acceptRun(result.run); const formats = new Set((result.files || []).map(fileExtension)); if (result.run.save_warnings?.length || !formats.has('docx') || !formats.has('pdf')) { setNoticeTone('warning'); setNotice('Box save needs attention. Check the warnings and returned files.'); } else setNotice(confirmed ? 'Reviewed Word and PDF saved to Box.' : 'Draft Word and PDF saved to Box.'); await refreshStatus(); })}>{busy === 'save' ? <><span className="spinner" />Saving to Box…</> : <>{confirmed ? 'Save reviewed files to Box' : 'Save draft files to Box'}</>}</button></div>
          {boxFiles.length > 0 && <div className="saved-files"><h3>Files in Box</h3>{boxFiles.map(file => <BoxLink key={file.url || file.name} url={sourceUrl(file)}><span className={`file-symbol ${fileExtension(file) === 'pdf' ? 'pdf' : 'word'}`}>{fileExtension(file) === 'pdf' ? 'PDF' : 'W'}</span><span>{file.name}</span></BoxLink>)}<BoxLink url={status?.reports_folder_url}>Open Reports folder</BoxLink></div>}
        </section></div>
      </>}
      </div>
    </main>
    {pickerCategory && <BoxPicker category={pickerCategory} disabled={!canChangeMaterials} onClose={() => setPickerCategory('')} onImported={async (count, warnings) => { setImportWarnings(warnings); setNoticeTone(warnings.length ? 'warning' : 'notice'); setNotice(warnings.length ? `${count} files added. Check the warnings.` : `${count} ${count === 1 ? 'file' : 'files'} added from Box.`); if (count) { try { await refreshStatus(); } catch { setError('Files were copied, but the materials list could not be refreshed.'); } } }} />}
    {deleteTarget && <DeleteDraftDialog label={dateLabel(deleteTarget.created_at || deleteTarget.updated_at)} busy={busy === 'delete'} error={deleteError} onCancel={() => setDeleteTarget(null)} onDelete={deleteDraft} />}
    {materialTarget && <DeleteDraftDialog title="Delete this material?" label={materialTarget.name} description={materialTarget.origin_url ? 'This copy will be deleted from the Annual Review folder in Box. Existing reports and the original imported file will be kept.' : 'This file will be deleted from the Annual Review folder in Box. Existing reports will be kept.'} busy={busy === 'delete-material'} error={materialDeleteError} onCancel={() => setMaterialTarget(null)} onDelete={deleteMaterial} />}
    {notice && <div className={`toast ${noticeTone === 'warning' ? 'warning' : ''}`} role="status"><Icon name={noticeTone === 'warning' ? 'alert' : 'check'} size={16} />{notice}<button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotice('')}><Icon name="close" size={13} /></button></div>}
  </div>;
}

function EvidenceCard({ item, source, focused }: { item: Evidence; source?: BoxFile; focused: boolean }) {
  const url = safeBoxUrl(item.source_url || item.url) || (source ? sourceUrl(source) : /^\d+$/.test(item.source_id || '') ? `https://app.box.com/file/${item.source_id}` : undefined);
  const preview = evidencePreview(item.quote, item.claim);
  const showClaim = Boolean(item.claim && normalizedEvidenceText(item.claim) !== normalizedEvidenceText(preview.text));
  return <section className={`evidence-card ${focused ? 'focused' : ''}`} data-reference={item.id} tabIndex={-1}>
    <div className="evidence-card-heading"><span className="reference-label">[{referenceNumber(item.id)}]</span><span>{item.project && item.project !== 'Unspecified' ? item.project : item.document_category || source?.document_category || 'Source evidence'}</span></div>
    <blockquote className="evidence-excerpt">{preview.text}</blockquote><div className="evidence-source"><strong>{item.source_name || source?.name || 'Original document'}</strong><BoxLink url={url}>Open in Box</BoxLink></div>
    {showClaim && <p className="evidence-claim">{item.claim}</p>}
    <div className="evidence-tags">{item.status && <span>{item.status.replaceAll('_', ' ')}</span>}{item.attribution && <span>{item.attribution === 'employee' ? 'Individual contribution' : item.attribution === 'team' ? 'Team result' : `${item.attribution} attribution`}</span>}</div>
    {preview.shortened && <details className="full-quote"><summary>Full quote</summary><blockquote>{item.quote}</blockquote></details>}
  </section>;
}
