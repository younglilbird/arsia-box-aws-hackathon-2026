# Year in Review

Turn an employee's project documents, peer feedback and annual plans in Box into
a source-backed annual self-review draft. Employees work entirely in Box:
upload real Word/PDF inputs, open the generated Word/PDF report, and review it
with Box preview and comments. An AWS background worker handles generation.

Built for the AWS and Box hackathon. Source-code submission:
[younglilbird/aws-box-hackathon-2026](https://github.com/younglilbird/aws-box-hackathon-2026).

**First verified cloud run on October 16, 2026, Pacific time:** the deployed AWS Lambda worker
processed nine real Word/PDF documents in Box, extracted 60 evidence items,
recorded two review findings and performed one revision. Box AI checked all
nine files and returned five citations. The generated Word and PDF reports
were downloaded and visually checked at two pages each. See
[development checks](docs/development-checks.md).

## Employee workflow

```text
Annual Review - Alex Chen - 2026/
  Projects/          Project designs, work records and measured results
  Peer Feedback/     Qualitative feedback with author and role
  Annual Plans/      Review context and proposed future priorities
  Reports/           Generated draft Word, PDF and review-notes Word
```

1. Upload `.docx` or text-based `.pdf` documents into the three input folders.
2. The scheduled worker checks changed files every minute. It records a change,
   waits for at least 20 seconds of quiet, and starts on a subsequent poll once
   the uploads have settled.
3. Amazon Bedrock Nova Pro extracts evidence, writes an approximately two- to
   three-page report, and reviews facts and attribution. Box AI provides an
   additional source-based check when available. At most one automatic revision
   is performed.
4. Open the actual Word/PDF files in `Reports`. Read the separate review-notes
   Word document for source excerpts, review findings and questions requiring
   employee input. Follow report citations back to the original Box files.
5. Review and comment in Box before using the document. Every generated report
   remains a **DRAFT**; automated checks do not record human approval. Uploading
   a changed input document creates a new generation opportunity.

Polling and model generation take additional time; completion within three
minutes is not guaranteed. Two to three pages is a writing target, not a fixed
pagination guarantee. Review notes describe excluded inputs and coverage limits.

## Local setup

Use Python 3.12. No frontend build or separate employee-facing website is
required for the native workflow.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pytest
cp .env.example .env
```

Set `BOX_CLIENT_ID`, `BOX_CLIENT_SECRET` and `BOX_ENTERPRISE_ID` in the ignored
`.env`. `BOX_USER_ID` selects the developer's human Box account when the app has
the required user-token authorization. A blank value uses the separate
application service account. Set the human user ID for this native demo so the
files appear in the account used for Box preview; the cloud configuration
helper requires it. CCG obtains fresh access tokens for repeated runs.

For local AWS calls, sign in using the SDK's developer credential chain. Set
`AWS_PROFILE` only if using a named local profile, plus `AWS_REGION=us-east-2`
and `BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0`. Developer login credentials stay
on the local machine. Lambda uses its execution role with no AWS profile.

Build and seed the synthetic demo:

```sh
.venv/bin/python scripts/build_demo_documents.py
.venv/bin/python scripts/setup_box_demo.py
```

Setup creates the native folder structure, uploads nine real Word/PDF files and
writes `.local/native-config.json` with mode `600`. It contains folder IDs and
employee details, never credentials. Use `--root-folder-id ID` to reuse a
dedicated root; different existing content is left untouched. See the
[demo materials](demo-materials/README.md).

## AWS deployment

The private scheduled entry point is `app.cloud.handler`. CloudFormation
provisions Lambda, a one-minute schedule, a private S3 bucket and Secrets
Manager. A real cloud invocation has completed the full Box-to-report workflow.
Schedule activation and each new deployment should be verified separately.
Follow the
[deployment procedure](docs/architecture.md#deployment-procedure).

There is no public web endpoint or paid Box Automate dependency. The worker's
execution role reads the specific Box secret and state object and invokes
the configured Bedrock model. Source documents remain in Box.

## Human review in Box

Employees preview and comment on the Word/PDF draft in Box and use Box's native
**Add Task** action to request human review. The generator itself never approves
a report.

The optional Relay workflow **Annual Review - Employee Review** is Active and
its details are visible at **Reports → Details → Workflows → Annual Review -
Employee Review**. That opens a read-only details view. The file menus did not
expose the documented **Start a Workflow** action in this account, so Relay
task execution has not been verified and no Relay review task was started.
See the [configuration and verification boundary](docs/architecture.md#optional-box-relay-review).
The demonstrated employee review path uses Box preview, comments and Add Task.

**Question for the organizers:** Can this Developer enterprise be provisioned
for the current Box Automate visual canvas, HTTPS custom connectors and AI
steps? It currently exposes the Relay editor, and the Admin Console has no
Connectors tab. Which entitlement or provisioning change is required for the
hackathon?

## Verification

```sh
.venv/bin/python -m pytest -q
rg -n --pcre2 '\p{Han}' app scripts tests docs README.md .env.example
```

Tests use offline fakes for AWS and Box. They cover source extraction,
evidence quotations, citation IDs, bounded revision, native folder selection,
state handling and actual document exports. For the language check, exit code
`1` means no matching characters were found. The product and demo are English
only.

Keep `.env`, `.local`, credentials and private employee documents out of Git.
Demo documents are identified as fictional in their source README and file
metadata. Use the [three-minute demo script](docs/demo-script.md) for the
presentation; preload a completed run and identify it transparently.
