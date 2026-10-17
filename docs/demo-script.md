# Arsia three minute demo

Present the local React workbench at **http://127.0.0.1:8765**. Keep a completed
run ready for the document walkthrough and identify it as a previously generated
run. The presentation does not promise that model generation completes within
three minutes. Use the English fictional employee documents.

Scheduled source polling is disabled for this local demo. Generation starts
with **Generate review** or a manual **Improve review** round. Opening the page or
refreshing progress does not start another model run.

## Before presenting

- Open Materials, Review and Finish in the workbench and check their contents.
- Use the actual Projects, Peer Feedback and Annual Plans categories. Check the
  displayed file count and that the source links open the correct Box documents.
- Choose a completed run with two recorded evaluations, a useful source reference and one real review finding.
  Check the report yourself before demonstrating human confirmation.
- Check the short Source coverage count in Evidence and any material warning.
- Locate the Questions for you form. Use fictional answers if submitting it.
- Have a real Word/PDF pair saved in Box and open Reports in another tab. Do not
  describe a successful generation as a successful Box save without checking it.
- Keep the public GitHub repository link ready.

## 0 to 20 seconds

Show Materials in the workbench.

"Annual review preparation starts with information scattered across project
records, feedback and plans. Arsia, our Annual Review Agent, turns them into a
coherent self-review draft, with evidence the employee can inspect and wording
the employee controls."

## 20 to 50 seconds

Show the three category lists, an Upload action and an Open in Box link.
Point to Generate review; if starting a new run, click it only once.

"These are real Word and PDF documents stored in Box. The categories distinguish
project results, qualitative feedback and future plans. Generate review takes
an explicit snapshot of the materials and starts a background job using Amazon Bedrock. Progress
shows the actual stage; the app does not start work just because a file appears."

If showing a running job, show its real progress briefly, then switch to the
prepared completed run. State that the completed run was generated earlier.
Do not imply that it belongs to a new upload or newly submitted answers.

## 50 to 100 seconds

Open Review in read mode. Show the Atlas paragraph, click its numbered reference
and inspect the exact quotation and filename. Open the source in Box if useful.

"The design targeted a 30 percent reduction in setup time. The pilot measured
20 percent, from ten minutes to eight. Alex owned instrumentation and
verification; the measured product result belongs to the team. Clicking a
reference reveals the original excerpt and links back to the Box file."

Show the short Source coverage count and any material warning.

"The workflow checks source quotations and reference IDs. It also reports
excluded or unreadable material. A matching quotation helps verification;
a person still decides whether it supports the claim."

## 100 to 140 seconds

Select Evaluation. Show the current draft-quality score, one dimension,
one useful strength, one remaining improvement and one source-backed Leadership
Principle connection.

"Bedrock writes the first draft, evaluates it, revises it using that feedback,
then independently evaluates the final report again. This panel shows the
assessment of the report you are reading, including its strengths and remaining
improvements. The score describes draft quality. Leadership connections must reference concrete evidence.
Box AI also checks the initial draft against its source files."

Point out the four report sections: accomplishments, Leadership Principles,
next-year goals and supplied peer feedback. Do not claim every principle is
covered or that the second score is always higher.

Show Questions for you and the answer field.

"Personal reflections and individual goals need Alex's input. Improve review
adds that information to this same draft, keeps unrelated writing, then scores
the updated report again. Further questions guide another round when needed."

If submitting answers, identify the improvement as work on the current run.
Continue using a separately identified prepared example rather than implying
that new answers have already finished processing.

## 140 to 180 seconds

Show the Edit toggle briefly, then Finish. Show the separate review checkbox and
Mark as reviewed action. Download or open an already saved real Word/PDF pair.

"The employee can edit the report and explicitly record their review. Editing
again clears that confirmation and marks the previous assessment stale.
Unconfirmed exports remain labelled as drafts. Word stays editable, and
PDF is the reading and sharing copy. Save puts the actual documents back into
Box. AWS handles generation; Box holds the materials, evidence and deliverables."

Show the Word/PDF files in the real Box Reports folder and finish with the
source-code link:
[younglilbird/arsia-box-aws-hackathon-2026](https://github.com/younglilbird/arsia-box-aws-hackathon-2026).

## Optional Relay follow-up

Relay is an optional downstream review integration, not the workbench's primary
interface or generation trigger. A separate API self-test returned HTTP 204 and
created a General Task assigned only to the current Developer user. The task
remains incomplete. Its configuration is visible in Reports / Details /
Workflows; the documented file-menu launch action did not appear in this
account. Do not claim that the missing menu was demonstrated or that a pending
task represents completed human review.
