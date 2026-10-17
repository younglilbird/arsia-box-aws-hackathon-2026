# Arsia acceptance checks

This checklist follows the requested workflow in implementation order. All
product copy, prompts, code and demo documents are English.

Release verification: 197 offline tests and 15 subtests pass, five frontend
regression tests pass, the production
frontend builds, and two isolated real Box/Bedrock improvement rounds preserve
the same run and output file identities. The final local app is running with
the existing three history records retained.

## 1. Workspace and materials

| Requirement | Implementation and verification |
| --- | --- |
| Use both Box and AWS | Real Developer-account Box inputs/outputs; real Bedrock generation and evaluation |
| Product identity | Arsia — Annual Review Agent |
| Three upload categories | Projects, Peer Feedback, Annual Plans; real Word/PDF files |
| Local upload and Box selection | Both supported; Box imports copy the selected pinned version |
| Independent import snapshot | Original retained; subsequent original edits do not silently update the copy |
| Open the useful Box folder | Materials opens the Annual Review parent; Reports is available at Finish |
| Material removal | Hover/focus trash, touch-visible control, modal confirmation; delete workspace copy only |
| Keep imported originals and reports | File-scope and source protection checks; live isolated deletion verified |
| No internal document IDs in input prose | Readable source headers; real input extraction checked |

## 2. Generation and grounded writing

| Requirement | Implementation and verification |
| --- | --- |
| Four main report sections | Annual Review Summary, Leadership Principles Summary, Next Year Goals, Peer Feedback Summary |
| Accomplishment detail | Personal role, action, measured impact, audience and limitations; no invented count padding |
| Paragraph project narratives | Writing/revision prompts require prose; current two-project report has two paragraphs per project |
| Fuller Leadership Principles | Concrete behavior, principle connection and practical value; supported principles only |
| Amazon guidance | Versioned 16-principle guide used in writing and evaluation |
| Important evidence only | Preferred 15–20 when justified; hard cap 20; current run has 20 |
| Literal evidence quotations | Pinned source text checked; unknown references rejected |
| Targets versus results | Atlas and Beacon design targets distinguished from measured pilot outcomes |
| Team versus personal impact | Contribution and attribution checks; no automatic credit for team ownership |
| Required review loop | First draft → independent evaluation → revision → independent final evaluation |
| Real prompts available | Exported directly from source into prompts.md |
| Restart behavior | Normal shutdown waits; interrupted improvement restores its private checkpoint |

## 3. Review and evaluation interface

| Requirement | Implementation and verification |
| --- | --- |
| Concise layout | Tightened sidebar/content spacing; removed decorative technical captions and Refresh Workspace |
| Interaction motion | Step/panel/modal transitions; keyboard and reduced-motion behavior checked |
| Evidence cards | Short meaningful excerpt, concise claim, tags and Open in Box; optional full quote |
| Source coverage | One short line in Evidence; no repeated Evaluation coverage panel |
| Run activity | Removed from user-facing Evidence and Evaluation |
| Current score only | Final exact-body evaluation; no initial score, delta or before/after comparison |
| Evaluation detail | Summary, Strengths, Improve and six criteria |
| No source clutter in Evaluation | No source chips, evidence buttons or technical source details |
| No severity or raw Box AI block | Removed from Evaluation |
| No separate LP dropdown | Specific supported principles and improvements appear in Leadership Alignment |
| Stale score handling | Editing marks the old assessment stale; no-op save retains valid assessment |

## 4. Employee-guided improvement

| Requirement | Implementation and verification |
| --- | --- |
| Improve the existing draft | /improve patches the same run; no new history row |
| Preserve unrelated writing | Append or replace one information-gap sentence; no whole-report rewrite |
| Keep user edits | Patch receives current saved body; unrelated edited text preserved |
| New answers as evidence | Saved to Box as explicit employee self-report; not independent measured results |
| Evaluate after each round | Fresh separate call with exact report hash |
| Ask again when needed | Remaining meaningful gaps become the next questions; manual repeated rounds |
| Advisory 90/95 target | No fabricated facts, forced score increase or unbounded automatic loop |
| Keep Box file identity | Version existing Word, PDF and evaluation files |
| Failed round preserves report | Private checkpoint restores previous usable draft; partial save is disclosed |

## 5. Finish and report history

| Requirement | Implementation and verification |
| --- | --- |
| Real Word/PDF | Both generated, served as attachments and saved in Box |
| Clean formal report | No evidence markers, IDs or source appendix in Word/PDF; interface retains traceability |
| Report title | Annual Review Summary; employee and year subtitle |
| Two to three pages | Current report is two pages in Word and PDF; all pages visually inspected |
| Human review | Explicit confirmation only; changed text resets approval |
| Draft removal | Hover/focus trash, modal double confirmation explicitly covers Box backups |
| Safe partial deletion | Preserve failed record and retry; normal Box Trash only |
| Clear generation failures | Failed state and concise reason; no unsupported blame on document count |
| All history accessible | Scrollable history; no hidden fixed five-item limit |

## Limits kept explicit

- Single-user loopback application; no public multi-user deployment.
- Input files must be readable Word or text-based PDF; OCR is not implemented.
- Maximum 25 supported input files, 12 MB each, with additional text/call budgets.
  Each improvement round currently adds an answer document and consumes one slot.
- The nine demo sources are short. Long-document retrieval/cache benchmarking
  remains a separate proposal, not a measured production capability.
- Imported snapshots have no dedicated in-place refresh control yet; re-importing
  is explicit and never silently follows the original.
- Scores are model judgments about draft quality. They do not rate employees or
  guarantee promotion, compensation or an increasing score.
- A normal shutdown waits, but force-killing the process can interrupt a job.
- Current local changes have not been redeployed to the historical Lambda worker.
- Browser save-to-disk was not established in the controlled session. Valid
  attachment responses, local output copies and Box Word/PDF files were verified.
