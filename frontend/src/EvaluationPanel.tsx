import type { Evaluations } from './types';

const validScore = (value: unknown, max: number): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= max;
export const evaluationText = (text: string) => text.replace(/\[(?:E)?\d+(?:\s*[,;]\s*(?:E)?\d+)*\]/g, '').replace(/\s+([.,;:!?])/g, '$1').replace(/ {2,}/g, ' ').trim();
const noteFillers = new Set(['the', 'a', 'an', 'and', 'between', 'could', 'be', 'more', 'explicit', 'explicitly']);
const noteKey = (text: string) => (text.toLowerCase().match(/[a-z0-9']+/g) || [])
  .filter(word => !noteFillers.has(word))
  .map(word => /^(?:distinction|distinguish)$/.test(word) ? 'distinguish' : word).join(' ');
const uniqueNotes = (items: string[], max = 5) => {
  const seen = new Set<string>();
  return items.map(evaluationText).filter(text => { const key = noteKey(text) || text; if (!text || seen.has(key)) return false; seen.add(key); return true; }).slice(0, max);
};
function Notes({ title, items }: { title: string; items?: string[] }) {
  return items?.length ? <div className="evaluation-notes"><strong>{title}</strong><ul>{items.map((item, i) => <li key={i}>{evaluationText(item)}</li>)}</ul></div> : null;
}
export default function EvaluationPanel({ evaluations, edited = false }: { evaluations?: Evaluations; edited?: boolean }) {
  const final = evaluations?.final;
  if (edited || final?.status === 'stale') return <p className="quiet-note">This edited version has not been evaluated.</p>;
  if (!final) return <p className="quiet-note">{evaluations?.initial ? 'Evaluation pending.' : 'Not evaluated with this rubric.'}</p>;
  if (final.status !== 'completed') return <p className="quiet-note">Evaluation unavailable.</p>;
  const strengths = uniqueNotes(final.strengths?.length ? final.strengths : (final.dimensions || []).flatMap(dimension => dimension.strengths || []));
  const issueAdvice = (final.issues || []).map(issue => issue.suggestion ? `${issue.message} ${issue.suggestion}` : issue.message);
  const improvements = uniqueNotes([...issueAdvice, ...(final.improvements?.length ? final.improvements : (final.dimensions || []).flatMap(dimension => dimension.improvements || []))], Math.max(5, issueAdvice.length));
  return <section className="evaluation-summary" aria-label="Current draft evaluation">
    {final.summary && <div className="evaluation-overview"><h2>Summary</h2><p className="evaluation-lead">{evaluationText(final.summary)}</p></div>}
    <div className="evaluation-score-heading"><h2>{evaluations?.score_label || 'Draft quality'}</h2><strong className="current-quality-score">{validScore(final.overall_score, 100) ? Math.round(final.overall_score) : '—'}{validScore(final.overall_score, 100) && <small> / 100</small>}</strong></div>
    {final.dimensions?.length ? <div className="evaluation-dimensions">{final.dimensions.map(dimension => {
      const leadership = dimension.id === 'leadership_alignment';
      const mappings = leadership ? final.leadership_alignment || [] : [];
      const dimensionStrengths = uniqueNotes([...(dimension.strengths || []), ...mappings.map(mapping => `${mapping.principle}: ${mapping.explanation}`)], 12);
      const leadershipIssues = leadership ? (final.issues || []).filter(issue => /leadership|principle|\bLP\b/i.test(issue.message) || mappings.some(mapping => issue.message.toLowerCase().includes(mapping.principle.toLowerCase()))).map(issue => issue.suggestion || issue.message) : [];
      return <details className="evaluation-dimension" key={dimension.id}><summary><span>{evaluationText(dimension.name)}</span><span>{validScore(dimension.score, 5) && dimension.score >= 1 ? `${Number(dimension.score.toFixed(1))} / 5` : '—'}</span></summary><div>{dimension.rationale && <p>{evaluationText(dimension.rationale)}</p>}<Notes title="Strengths" items={dimensionStrengths} /><Notes title="Improve" items={uniqueNotes([...(dimension.improvements || []), ...leadershipIssues], 12)} /></div></details>;
    })}</div> : null}
    <Notes title="Strengths" items={strengths} /><Notes title="Improve" items={improvements} />
  </section>;
}
