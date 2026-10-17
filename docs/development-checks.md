# Development checks

Verified on October 16, 2026, in America/Los_Angeles during the hackathon.
These checks use fictional employee and project information.

## First verified cloud workflow

The deployed private AWS Lambda worker completed an end-to-end generation
against the human-visible Box developer account. This used the Lambda
execution role, rather than a developer's local AWS profile.

| Check | Observed result |
| --- | --- |
| Input documents | Nine real Word/PDF files across Projects, Peer Feedback and Annual Plans |
| Source evidence | 60 extracted evidence items |
| Automated review | Two findings about missing documented contributions |
| Revision | One automatic revision |
| Box AI | Completed against nine source files and returned five citations |
| Box outputs | Draft Word report, draft PDF report and review-notes Word document |
| Main report pagination | Two pages in PDF and two pages when Word was rendered |
| Draft status | Still requires employee confirmation |

The revised report includes the documented validation checks, handover of
queries and checklist, and the consolidated list of Alex's deliverables.
Review notes preserve the original findings and correctly state that a
revision does not certify every issue as resolved.

## Document and fact checks

- All nine real input files were read using the application's extraction
  adapter. Their bodies contain human-readable dates, authors, project names
  and status, with no document-ID field or internal metadata keys.
- The main Word and PDF reports were rendered and every page visually
  inspected. Text, headings and source references are readable with no
  clipping or overlap.
- The Atlas report distinguishes the 30% design target from the 20% observed
  pilot result, from 10 to 8 minutes, with 300 participants.
- The Beacon report preserves the 4.2-to-3.1-minute pilot result, approximately
  26.2%, and distinguishes it from the approximately 35% design target.
- Product results are described as team outcomes, and proposed next-year
  directions remain plans rather than completed achievements.
- Visible citations use conventional numeric markers. File identifiers remain
  in hyperlink targets instead of appearing as technical metadata in prose.
- Review notes contain the actual completed Box AI status, its returned
  findings, source quotations, coverage information and employee questions.

The first verified draft showed opportunities for further editing: a repeated
title, third person in the final planning paragraph, and vague or redundant
employee questions in review notes. These observations were recorded before
the subsequent polish pass. They are not evidence of human approval, and
generation counts above describe the first verified run rather than every run.

## AWS and Box access

- Box Developer account and authorized CCG application were verified.
- API authentication, listing, uploads, downloads and Box AI requests passed.
- Native folder setup used the authorized human Box content context. A CCG
  service account has a separate content space unless a human user is selected.
- The deployed generation used Amazon Bedrock Nova Pro through
  `us.amazon.nova-pro-v1:0` in the configured `us-east-2` environment.
- Box application credentials are retrieved from Secrets Manager. Lambda
  obtains AWS permissions from its execution role.
- CloudFormation checks passed: cfn-lint 1.57.2, the four configured security
  guard rules, and AWS template validation.

The one-minute schedule is part of the template; its active state should be
checked separately from generation success. Box preview, comments and the
native **Add Task** action provide the employee's human-review path.

The optional Box Relay workflow `Annual Review - Employee Review` was activated;
its Active status was confirmed in the UI and API. It is configured for Manual
Start on a selected Reports file, a General Task, assignees specified when
started, and the triggering file as its target. **Reports → Details → Workflows
→ Annual Review - Employee Review** exposes its read-only details. This confirms
configuration visibility, not execution: the file menus did not show **Start a
Workflow**, and multi-file selection did not resolve the missing launch action.
No Relay review task was started or sent, and manual-start execution remains
unverified. The expected official launch path and organizer provisioning
question are recorded in the [architecture notes](architecture.md#optional-box-relay-review).

## Offline verification

The repository has offline tests for bounded folder discovery, source
extraction, exact quotation matching, known citation IDs, review and revision,
native polling state, private cloud configuration and actual document exports.
The focused export suite passes ten tests plus three subtests, including safe
model-text handling, clickable source relationships, compact cited-file grouping,
numeric reference display and duplicate-title removal in Word/PDF. The title
fix was also checked in rendered Word and PDF samples. Run the full suite with:

```sh
.venv/bin/python -m pytest -q
```

The public repository is initialized and can be pushed. Real `.env` values,
native folder configuration, cloud configuration and private test documents
are ignored by Git. The committed demo material is synthetic; no real employee
records are needed to reproduce the demonstration.
