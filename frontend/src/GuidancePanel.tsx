import { evaluationText } from './EvaluationPanel';

interface Props {
  questions: string[]; value: string; onChange: (value: string) => void;
  target: number; onTargetChange: (value: number) => void;
  disabled: boolean; working: boolean; dirty: boolean; error?: string | null;
  onImprove: () => void;
}

export default function GuidancePanel({ questions, value, onChange, target, onTargetChange, disabled, working, dirty, error, onImprove }: Props) {
  return <section className="question-section">
    <h3>Guidance</h3>
    {questions.length > 0 && <ol>{questions.map((question, index) => <li key={index}>{evaluationText(question)}</li>)}</ol>}
    {error && <div className="message error-message" role="alert"><span>{error}</span></div>}
    <label htmlFor="guidance">Your answers or changes</label>
    <textarea id="guidance" rows={5} maxLength={8000} value={value} onChange={event => onChange(event.target.value)} disabled={disabled} placeholder="Answer the questions or describe what to improve." />
    <div className="guidance-actions"><select aria-label="Target score" title="A revision target, not a guaranteed result." value={target} onChange={event => onTargetChange(Number(event.target.value))} disabled={disabled}><option value={90}>Target 90</option><option value={95}>Target 95</option></select><button className="button subtle" disabled={!value.trim() || disabled} onClick={onImprove}>{working ? <><span className="spinner" />Improving…</> : 'Improve review'}</button></div>
    {dirty && <p>Save your edits before improving this review.</p>}
  </section>;
}
