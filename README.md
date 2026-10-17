# Arsia

Annual Review Agent

An English document workbench that turns project records, peer feedback and
annual plans in Box into a source-backed annual self-review draft. Upload or
inspect real Word/PDF inputs, generate a report, check source quotations,
supply missing information, and save editable Word and PDF files back to Box.
Amazon Bedrock Nova Pro writes and reviews the draft; Box AI provides an
additional check against the original files.

Built during the AWS and Box hackathon. Source-code submission:
[younglilbird/aws-box-hackathon-2026](https://github.com/younglilbird/aws-box-hackathon-2026).

## Run the local workbench

Use Python 3.12 and a current Node.js LTS release with pnpm.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-local.txt
cp .env.example .env
pnpm --dir frontend install --frozen-lockfile
bash scripts/start_local.sh
```

Open **http://127.0.0.1:8765/**. Keep the terminal running while using the app.
The startup script builds the React frontend and serves it with the local
Python API. For frontend development, run Vite separately from `frontend/`;
its development proxy forwards `/api` to port 8765.

If Node is outside `PATH`, set `NODE_BIN` to its executable before running the
startup script. `PYTHON_BIN` can select a Python environment; otherwise the
script uses `.venv/bin/python` when available.

Set the following in the ignored `.env` file; never paste credentials into the
webpage or commit them:

- `BOX_CLIENT_ID`, `BOX_CLIENT_SECRET`, `BOX_ENTERPRISE_ID` and `BOX_USER_ID`.
  The configured human Developer user owns the demo files; the application's
  separate service account has a different content space.
- `AWS_PROFILE` when using a named authenticated local profile,
  `AWS_REGION=us-east-2` and `BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0`.

The local application uses real Box and AWS APIs. It is a single-user local
workspace, bound to loopback; it is not a public multi-user deployment.
Credentials stay in the Python process. Source documents and generated files
remain in the configured Box workspace. Private run records are stored under
`.local/workbench/` and excluded from Git.

## Prepare the demo workspace

```sh
.venv/bin/python scripts/build_demo_documents.py
.venv/bin/python scripts/setup_box_demo.py
```

Setup uploads nine fictional documents, creates the folders below, and saves
non-secret folder configuration to `.local/native-config.json`. An existing
configured workspace can be reused; do not reseed it merely to open the app.

```text
Annual Review - Alex Chen - 2026/
  Projects/          Designs, work records and measured results
  Peer Feedback/     Qualitative observations from colleagues
  Annual Plans/      Reporting context and proposed future priorities
  Reports/           Word, PDF and review-notes outputs
```

Read [demo materials](demo-materials/README.md) for the deliberately different
design targets, measured results, ownership boundaries and missing reflections.
The uploaded inputs are real `.docx` and `.pdf` files. Markdown files in the
repository are authoring sources, not the files the employee receives.

## Employee workflow

1. In **Materials**, inspect the three categories, upload local Word/PDF files,
   or use **Add from Box** to copy a selected source version from another folder.
   Each imported file is an independent snapshot; later source edits do not
   silently change the review materials.
2. Click **Generate review** when the input set is ready. The application writes
   a draft, evaluates it, revises it and separately evaluates the revised report.
3. In **Review**, inspect the report, source quotations and **Evaluation** panel.
   Read the current report's score, strengths, improvements and supported
   leadership connections. Source links open the corresponding original files in Box.
4. In **Questions for you**, answer the remaining questions and click
   **Improve review**. The application patches the same draft, keeps unrelated
   prose and edits, updates the existing Box files, and evaluates the resulting
   report again. Repeat when another question remains. Answers are explicitly
   self-reported, distinct from independently measured product results.
5. Save Word/PDF output to Box and open it there. Generated drafts require human
   review; generation success does not record employee confirmation.

Recent drafts include failed attempts with an explicit failure state. Hover or
focus a row to reveal its delete control; deletion requires a confirmation
dialog. Deleting a draft also deletes its tracked generated files from the
configured Box Reports folder, while preserving source materials. If Box cannot
complete deletion, the record remains available for retry. File recovery follows
the Box account's trash policy; the application never purges Box Trash.

Materials have the same confirmation-based delete control. It removes the
workspace copy; an original imported from another Box folder is preserved.
Existing reports remain available after a material is removed, but their source
snapshot must be reviewed before further publishing.

The engine performs one required automatic revision between two evaluations.
Scores assess draft quality using six provisional dimensions; they are not
employee performance ratings or an official Amazon scoring system. Amazon's
16 Leadership Principles guide evidence-backed writing and evaluation without
requiring every principle. The final evaluation is tied to the exact report;
editing makes that score stale. See [evaluation details](docs/evaluation.md).
A report targets two to three pages, with the current evaluation in a separate
review-notes document. Word/PDF exports and Box report files omit evidence
markers and source appendices; source links remain in the Review interface. Earlier evaluation
snapshots remain in private run history.
Employee-guided improvement retains the run ID and versions the same three
Box files. Failed patch or evaluation rounds restore the preceding usable
report. A 90- or 95-point target is an advisory writing goal, not a guarantee
of an increasing score.
The report has four main sections: **Annual Review Summary**, **Leadership
Principles Summary**, **Next Year Goals**, and **Peer Feedback Summary**.
The first section develops three to five supported accomplishments with
subsections; the application does not invent achievements to reach a count.
Writing and source review use at most 20 curated evidence items, prioritizing
personal contribution, measured impact and material feedback over routine
metadata. The complete actual prompts are in [prompts.md](docs/prompts.md).

Long-document extraction, caching and benchmarking improvements are documented
as a separate [design proposal](docs/long-document-design.md); they are not
claimed as implemented or validated by the short-document demo.
Generation uses real model calls and may take several minutes; it is not a
three-minute latency guarantee. Image-only PDFs need OCR before this version
can read them. Coverage limits and omitted files are disclosed in the review.

## Existing AWS deployment

A private Lambda deployment has already generated real Word/PDF reports from
all nine Box documents. The first verified cloud run on October 16, 2026,
Pacific time extracted 60 evidence items, recorded two review findings and
performed one revision. Box AI checked nine files and returned five citations.
The actual main Word and PDF outputs were rendered and inspected at two pages
each. See [development checks](docs/development-checks.md).

The earlier one-minute upload poller is disabled while the manual workbench is
used. Running both triggers would create unexpected duplicate generations.
The local workbench orchestrates its own background tasks and does not expose
the private Lambda as an anonymous public endpoint. Cloud resources and the
optional scheduled deployment are documented in [architecture](docs/architecture.md).

Box Relay is optional. A native General Task has been tested through the Relay
API, but the workbench's generation flow does not depend on Relay or Automate.
The `scripts/start_box_review.py` developer helper starts one self-assigned
General Task on an owned report and avoids an existing pending task.

## Verification

```sh
.venv/bin/python -m pytest -q
pnpm --dir frontend run build
```

Offline tests exercise bounded discovery, exact source quotations, citation
references, review and revision, version-change protection, local task handling
and real document exports. Live Box/AWS verification is separate from offline
tests. The product, source code, demo materials and generated reports are English.
Keep `.env`, `.local`, credentials and private employee records out of Git.
