# Development checks

Verified during the hackathon on October 16–17, 2026, in America/Los_Angeles.
All employee and project records used for these checks are fictional.

## Current local workflow

The React/TypeScript workbench and Python API run at
`http://127.0.0.1:8765/`. A real Box/AWS run reads the nine Word/PDF inputs,
retains 20 selected evidence items, writes and evaluates a draft, revises it,
and evaluates the resulting report independently. The interface presents only
the current assessment. The initial draft and assessment remain private.

The most recent recovered run completed with a genuine final score of 74/100.
Its report has 736 citation-stripped words, four required main sections,
paragraph-based project narratives, and specific Ownership and Dive Deep
connections. Word and PDF each rendered to two pages. Every page was visually
inspected: no clipping, duplicate report title, evidence markers or source
appendix. The separate evaluation document describes the current assessment.
A score measures provisional draft quality, not the employee's performance.

A local service restart had interrupted this run during its initial evaluation.
Recovery reused its pinned source and evidence checkpoint under the same run ID.
The resumed calls, rejected candidates and agent refinements are recorded in
private history; the final evaluation scores the exact resulting report. The
service now waits for active work during a normal shutdown. Forced termination
still can interrupt a job and is not claimed to be durable cloud orchestration.

The source documents are deliberately short. This verifies the functional
workflow, not extraction quality on arbitrary long enterprise documents. The
[long-document design](long-document-design.md) describes proposed retrieval,
chunking, caching and benchmarking improvements separately.

## Facts and report format

- Actual inputs were extracted through the application adapter. Their visible
  contents use readable dates, authors, project names and status, without
  internal document-ID fields.
- Atlas distinguishes the 30% design target from the observed 20% pilot result:
  10 to 8 minutes, with 300 administrators across six organizations. Alex's
  measurement work is distinct from the team result and project leadership.
- Beacon distinguishes the approximately 35% design target from the observed
  26.2% pilot result: 4.2 to 3.1 minutes, with 40 agents and 186 tasks. The
  prototype work is distinct from production ownership.
- Peer feedback is qualitative and attributed. Proposed future work remains
  a proposal; missing reflection or agreed personal goals becomes a question.
- Evidence selection retains at most 20 important supporting facts and keeps
  source quotations literal. Broader candidate coverage is checked separately.
- Word/PDF report files use **Annual Review Summary**, then employee and year.
  Evidence links remain in the interface; exported and Box reports omit them.

## Box operations

Separate live tests used temporary test folders in the authorized Developer
account. They did not delete the nine demo inputs or user reports.

| Operation | Observed result |
| --- | --- |
| Add from Box | Copied a pinned source version; source and copy content hashes matched |
| Import provenance | Private manifest retained original file and version information |
| Draft deletion | Removed all three tracked test outputs; source preserved; repeat request idempotent |
| Material deletion | Removed only the test workspace copy; imported original and report sentinel preserved |
| Failure handling | Offline tests retain a record after partial deletion and permit retry |
| Recovery | Test-only files and folders were moved to normal Box Trash; no purge |
| Exports | Real Word/PDF endpoints returned valid attachments with correct MIME types |

Browser save-to-disk was not established in the controlled browser session.
The backend attachments and separately saved local output files were verified;
the interface reports a download request rather than falsely claiming a saved file.

The Developer account's Trash setting was inspected as enabled, with a 30-day
auto-empty policy. The application does not change that setting or purge Trash.
Deleting a local history entry also deletes its tracked generated Box copies
after confirmation; material deletion preserves existing reports and imported
originals. Confirmations, source-version checks and file-scope checks are tested.

Employee-guided improvement uses a separate patch stage and a fresh evaluation.
Offline checks cover same-run persistence, unrelated-prose preservation,
self-report evidence, exact-body scoring, repeated rounds, output versioning,
source changes, partial publishing and restoration after failure.

A live isolated test completed two manual improvement rounds against one
pinned copy of an actual project source. Both rounds retained the same run ID
and the same three Box output IDs, advanced every file version, preserved
unrelated employee prose byte for byte, and produced fresh exact-body evaluation
hashes. The reflection answer did not create a goal or an unreported outcome;
the next answer added only the proposed, explicitly unagreed goal. Selected
evidence grew from one to three items. Actual downloaded Box Word/PDF files
contained no evidence markers or internal document IDs.

The two genuine scores were 56 and 64 for this intentionally small test draft;
they are not scores for the full demo report. Each round used three model calls,
including a bounded validation retry. Main source version and content hashes
were unchanged. The complete temporary test workspace was moved to normal Trash
and verified. An exact generated gap sentence still remained above the added
reflection in that probe; a subsequent deterministic cleanup is covered by an
offline regression check and runs before evaluation, without removing unrelated
prose or unagreed-goal qualifications.

## Interface checks

The production frontend build passes. Desktop and 390-pixel mobile views were
checked. Step and panel transitions respect reduced motion. Delete buttons
appear on hover or keyboard focus and remain available on touch layouts;
confirmation dialogs default to Cancel.

Evaluation contains current scores, summary, strengths and improvements.
Leadership details appear within Leadership Alignment. It contains no evidence
chips, raw Box AI block, severity badges, run activity or separate Leadership
Principles dropdown. Evidence has compact excerpts and a single short source
coverage line. Materials links to the Annual Review parent folder.

## AWS and historical cloud verification

The authorized Box human Developer context and CCG application passed API
listing, downloads, uploads and Box AI checks. Credentials remain outside Git
and frontend responses. The local app uses the authenticated AWS profile;
Bedrock calls use `us.amazon.nova-pro-v1:0` in `us-east-2`.

An earlier private Lambda deployment completed a real nine-document workflow
using its execution role and Secrets Manager. That historical version extracted
60 facts, made one revision and produced two-page Word/PDF files. It predates
the current 20-item selection and local interface. Current local changes are
not claimed as deployed to Lambda. CloudFormation lint, configured security
guards and AWS template validation passed for that deployment.

The EventBridge poller is disabled, with `ScheduleEnabled=false`, while the
manual workbench is used. The local frontend is not publicly deployed.
Optional Box Relay configuration and one self-assigned General Task were
verified earlier; generation does not depend on Relay. No task completion or
human approval is inferred from those checks.

## Reproduce offline checks

```sh
.venv/bin/python -m pytest -q
pnpm --dir frontend run build
.venv/bin/python scripts/export_prompts.py
git diff --check
```

Tests cover source discovery and versions, literal quotations, known citation
IDs, report structure, evaluation schemas and hashes, improvement patches,
private checkpoints, safe Box mutations and actual document exports. They use
fake external services; live Box/AWS results are distinguished above.
The reviewed offline suite passes **197 tests plus 15 subtests**, including
cross-tab conflicts, current Box version tracking, uncertain-upload recovery
and the grounding regressions in [code review](code-review.md). Five frontend
regression tests and the TypeScript/Vite production build pass.

The public repository contains English source, setup instructions and synthetic
demo materials. `.env`, `.local`, private run bodies and test artifacts remain
ignored. [Acceptance checks](acceptance-checklist.md) track the requested product
behavior and the remaining limits.
