# Arsia draft evaluation

The workflow produces two report versions and two separate evaluations:

1. Extract and validate evidence from the selected Box documents.
2. Write the first report using the writing guidance and supported leadership behaviors.
3. Evaluate that draft against the evidence, source text and rubric.
4. Revise the complete report using the evaluation's strengths, weaknesses and recommendations.
5. Apply final quotation and citation checks.
6. Evaluate the resulting report again in a separate model call.
7. Present the revised report and its current evaluation to the employee. Keep the first assessment in private run history.

The second evaluator receives the actual final report and sources. It does not
receive the first evaluation's scores. A higher second score is not guaranteed.
There is one automatic revision; remaining weaknesses are visible for employee
review rather than starting an unbounded loop.

## Employee-guided improvement

After the initial loop, **Questions for you** collects missing reflection,
contribution or proposed goals. **Improve review** patches the existing report;
it does not create another history row or rewrite unrelated paragraphs. New
answers are stored in Box as employee self-report. They do not become independent
measurements or peer testimony.

The patch scope is limited to questions actually answered. Reflection and goal
additions use literal employee wording, so a lesson cannot silently become a new
achievement or next-year commitment. Goals need an actual prospective intention
in the answer; leaving a question unanswered does not create a placeholder patch.

Each manually requested round validates the patch and citations, evaluates the
new exact report in a separate call, and versions the same report and evaluation
files. If another meaningful gap remains, the employee can answer it in another
round. The score target is advisory, and a new score can decrease. Failed patch
or evaluation rounds preserve the preceding usable report. Editing invalidates
the old evaluation until a fresh assessment is available.

## Report template

The employee-facing self-review uses four main sections in order:

1. **Annual Review Summary**: three to five supported accomplishments, with
   personal responsibility, actions, customer impact and documented reflection.
2. **Leadership Principles Summary**: specific experiences connected naturally
   to relevant principles, with source evidence.
3. **Next Year Goals**: specific actions for growth and increased customer
   impact, distinguishing proposals from manager-agreed commitments.
4. **Peer Feedback Summary**: a synthesis of feedback actually supplied to the
   authorized workspace, preserving qualitative attribution.

Subsections can describe each accomplishment. Missing evidence is stated as a
gap rather than inventing accomplishments or assuming access to hidden peer
feedback. Both evaluations check this structure.

The writing set contains at most 20 selected evidence items, normally 15–20
when enough material is available. Selection prioritizes contribution,
customer impact, important measurement context and substantial feedback.
Routine metadata and duplicates do not become accomplishments. Relevant
limitations and conflicting measurements must remain available when they
qualify selected claims.

## Provisional rubric

The rubric evaluates the document's quality and evidence, not an employee's
performance rating. The dimensions can be adjusted when a company template is
provided. They are application choices, not an official Amazon rating system.

| Dimension | Weight | Main question |
| --- | ---: | --- |
| Factual accuracy | 25% | Are claims, quotations and distinctions supported? |
| Individual contribution | 20% | Are the person's role, decisions and actions clear? |
| Impact and metrics | 20% | Are outcomes supported, scoped and distinguished from targets? |
| Leadership alignment | 15% | Do concrete examples support the principles discussed? |
| Structure and clarity | 10% | Is the narrative concise, specific and easy to follow? |
| Reflection and next steps | 10% | Are learning and goals grounded, with honest gaps? |

Each dimension receives 1–5 with an explanation, strengths and improvements.
The application validates the dimensions and computes the weighted total on a
100-point scale. Scores are model judgments. Literal quotation checks, source
version checks and citation-ID checks remain separate deterministic checks.
Evaluations record a hash of the exact report. Editing the report makes its
previous final evaluation stale.

## Writing guidance

The accomplishment narrative explains the project context, personal
responsibility, actions and supported impact. Available metrics include the
baseline, observed outcome, period, audience and limitations. Team achievements
and personal deliverables remain distinct. Missing personal reflection or
agreed goals become employee questions.

This approach follows the emphasis on role, impact, concrete examples,
development and honest self-assessment in [UC Davis Human Resources guidance](https://hr.ucdavis.edu/performance-appraisals/writing-resources/ee).

## Leadership Principles

The default company guidance uses the 16 principles listed by
[Amazon](https://www.amazon.jobs/content/en/our-workplace/leadership-principles).
The names and concise application guidance are versioned in
`app/guidelines.py`. This guide is separate from employee source evidence.

The writer integrates a principle only when a documented action supports the
connection. The evaluation explains that connection and references its source
evidence. Mentioning more principles does not earn a better score. Unsupported
principles are omitted, and no hiring, mentoring, disagreement or personal
learning is invented to fill them.

The interface shows the final summary, strengths, remaining improvements,
current dimension scores and supported leadership connections. It does not
show the first draft, score changes or a before/after comparison. The separate
review-notes Word document contains the current evaluation;
earlier evaluations remain in private run history. The main self-review remains a concise Word/PDF narrative without evidence
markers or a source appendix. Source connections remain in the Review interface.
