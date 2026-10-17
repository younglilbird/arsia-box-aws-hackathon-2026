import assert from 'node:assert/strict';
import test from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import EvaluationPanel from '../.test-build/EvaluationPanel.js';

const render = props => renderToStaticMarkup(createElement(EvaluationPanel, props));

test('an unavailable evaluation retains a clear manual-review next step without a score', () => {
  const html = render({ evaluations: { final: { status: 'unavailable' } } });
  assert.match(html, /Evaluation unavailable/);
  assert.match(html, /Check this draft against its sources before marking it reviewed/);
  assert.doesNotMatch(html, /current-quality-score|NaN|\/ 100/);
});

test('an unavailable final evaluation never displays old or stray numeric scores', () => {
  const html = render({ evaluations: { initial: { status: 'completed', overall_score: 71 }, final: { status: 'unavailable', overall_score: 96 }, overall_delta: 25 } });
  assert.match(html, /Evaluation unavailable/);
  assert.doesNotMatch(html, /71|96|25|current-quality-score/);
});

test('a failed assessment offers manual review without rendering a failed draft label', () => {
  const html = render({ evaluations: { final: { status: 'failed', overall_score: Number.NaN } } });
  assert.match(html, /Evaluation unavailable/);
  assert.doesNotMatch(html, /Failed|NaN|current-quality-score/);
});

test('a completed assessment with an invalid score does not render NaN or a fabricated total', () => {
  const html = render({ evaluations: { final: { status: 'completed', overall_score: Number.NaN } } });
  assert.doesNotMatch(html, /NaN|\/ 100/);
  assert.match(html, /—/);
});

test('an edited report hides the preceding completed score', () => {
  const html = render({ edited: true, evaluations: { final: { status: 'completed', overall_score: 84 } } });
  assert.match(html, /has not been evaluated/);
  assert.doesNotMatch(html, /84|current-quality-score/);
});
