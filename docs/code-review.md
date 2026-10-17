# Code review and quality checks

Reviewed on October 17, 2026. The review covered all application modules,
frontend behavior, tests, dependency declarations, setup scripts and the
existing AWS deployment code. Three independent passes examined backend/file
operations, AI grounding/evaluation, and frontend/reproducibility. Findings were
reproduced before fixes; this is not a guarantee of production readiness.

## Fixed findings

| Priority | Failure | Fix and regression coverage |
| --- | --- | --- |
| P1 | Reverting report A → B → A could return old saved links even though the reused Box files still contained B | Determine current content from the latest tracked record per Box ID; verify re-versioning after revert and no-op repeat saves |
| P1 | A stale tab could overwrite another tab's edits or approve unseen wording | Require the expected report hash for edit, confirmation and improvement; reject conflicts before mutation, upload or model work |
| P2 | Retrying an uncertain initial upload could leave an untracked file | Send initial POST once; persist upload intentions and recover only an exact content hash, filename, owner and destination match; retain uncertain history on delete |
| P2 | Lost employee-answer upload response could obscure a saved addendum | Verify an exact matching addendum before continuing; otherwise restore the report and explain how to remove an unapplied copy before retrying |
| P2 | A partially successful local upload looked like total failure | Refresh Materials after success, partial failure or uncertainty; show the completed count and retry only remaining files; validate the ten-file limit |
| P2 | Late startup requests could replace the selected or edited draft | Guard initial responses with the user's selection epoch; preserve unsaved text and guidance after conflicts |
| P2 | Home navigation could discard unsaved work | Navigate inside the app while retaining state; register an unload warning for unsaved work |
| P2 | Replacing a compound information-gap sentence could erase an existing accomplishment | Accept only complete, restricted gap statements; use append when factual prose is mixed in |
| P2 | New leadership additions bypassed the initial workflow's behavior checks | Apply the existing leadership guard to new additions only, preserving unrelated employee prose |
| P2 | Percentage matching lost negative signs or partially matched thousands/leading decimals | Parse signed, Unicode-minus, grouped-thousands and leading-decimal values; compare normalized Decimal values |
| P3 | Development setup omitted local backend dependencies and automated checks | Include local dependencies in the dev install, record tested versions, and add Python/frontend CI |

## Verification

- Python regression suite: **197 tests and 15 subtests passed** in a separate
  newly installed Python 3.12 environment.
- Frontend regression suite: **five tests passed**; TypeScript and the production
  build passed.
- Ruff checks cover syntax/name errors, invalid control flow, unused imports
  and unused local variables. Dependency consistency is checked with `pip check`.
- Isolated browser fixtures demonstrated partial uploads, delayed startup
  responses, unsaved editing, conflict handling and same-draft guidance. Browser
  reload behavior varies; the native unload dialog was not claimed as verified.
- Read-only Box verification confirmed that returned SHA1 metadata matches an
  actual downloaded report. Recovery failure paths use offline service fakes.
- Earlier real Box/Bedrock runs and two manual improvement rounds are recorded
  in [development checks](development-checks.md). This review did not silently
  regenerate employee reports or count offline tests as new live model runs.
- GitHub CI performs offline tests, static checks, frontend tests/build, tracked
  content checks and prompt-drift checks without cloud credentials.

## Engineering assessment

The existing adapters and pure evaluation/export routines provide useful seams
for testing. The review favors small fixes at these seams over a deadline-time
rewrite. `Workbench` still combines persistence, orchestration and publishing;
separating a run store and output publisher is sensible later work once the
interface can be checked against these regressions.

Literal quotation, identifier and number checks establish traceability. They
do not prove semantic support, attribution or causality. Evaluation scores are
model judgments about the draft. Human review remains part of the workflow.

The app is intentionally local and single-user. Forced termination is not
durable job orchestration. Unverified uploads retain state rather than claiming
success; an uncertain answer upload may require removing its unapplied material
before retrying. The optional disabled native poller does not have the local
workbench's full durable upload-intent recovery. Public authentication,
multi-user isolation, OCR and long-document benchmarking remain separate work.
