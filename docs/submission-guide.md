# Hackathon submission and presentation guide

## Confirmed requirements

The [organizer's event page](https://luma.com/bqo9xii4) requires work created
during the event, a GitHub source-code link, and use of Box and AWS. The published
judging weights are 50% technical execution, 30% business value and 20% a
three-minute presentation. It lists the submission deadline as October 17,
2026, at 1 PM Pacific, followed by presentations at 2 PM.

The public page does not state a mandatory public website or video upload.
The participant provided the [official submission form](https://docs.google.com/forms/d/e/1FAIpQLSdf1C_K7seI1gIdK0y7drF9nChjZH5wFE4B7N8FfNbuY7gqOQ/viewform).
Fields transcribed by the participant include a one-sentence description, AWS
tools/services, Box APIs/tools and the GitHub link. The form itself was not
submitted by the coding agent. Uploading code to GitHub is not itself submission
to the event.

## GitHub and a running product

| Option | What it provides | Arsia status |
| --- | --- | --- |
| GitHub repository | Source, README, sample outputs and reproducible setup | Primary source-code submission |
| GitHub Actions | Automated tests and frontend builds on temporary runners | Quality checks, not an application server |
| GitHub Pages | Static HTML, CSS and JavaScript hosting | Cannot run Arsia's Python backend |
| Local presentation | Workbench on the presenter's laptop with real Box/AWS calls | Available presentation fallback |
| Public AWS deployment | A reachable application with its own runtime and authorization | Shared-login judge demo on EC2 and CloudFront |

GitHub documents that [Pages does not support server-side Python](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).
[Actions can build and test Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python),
but a passing CI run does not create a public application URL.

The local presentation still needs internet access: Box holds the files and
Amazon Bedrock runs the models. `127.0.0.1` refers to the viewer's own computer;
sharing that URL does not let a judge access the presenter's laptop.

## Submission text

**Project name:** Arsia — Annual Review Agent

**Short description:** Turn Box documents into a grounded annual review with
Amazon Bedrock, independent evaluation and employee-guided improvement.

**Problem:** Employees reconstruct a year of work from scattered project designs,
pilot results, feedback and plans. Important contributions are easy to omit,
while targets and team achievements can accidentally become overstated personal
results.

**Solution:** Arsia selects important source-backed facts, writes a four-section
self-review, evaluates and revises it, then lets the employee add missing context
without replacing the entire draft. Clean Word/PDF reports and the current
evaluation return to Box. Evidence remains available for review in the workbench.

**Box integration:** Categorized input folders, pinned-version imports, source
downloads, Box AI source review, output file versions and recoverable deletion.

**AWS integration:** Amazon Bedrock Nova Pro for extraction, writing, independent
evaluations and improvement. An earlier private Lambda deployment also verified
execution-role access, Secrets Manager and S3 state; current local changes have
not been redeployed to it.

**What is implemented:** Local uploads and Box selection; bounded extraction;
up to 20 selected evidence items; the four-section report; write/evaluate/revise/
evaluate; repeated same-draft improvement; human editing and confirmation;
Word/PDF export; Box versioning; confirmation-based deletion; offline regression
tests and GitHub CI.

**Current scope:** A working single-user prototype. Public authentication,
multi-user authorization, OCR, advanced retrieval and long-document benchmarking
are future work. The quality score evaluates a document, not a person's job
performance.

**Source link:** https://github.com/younglilbird/arsia-box-aws-hackathon-2026

**Hosted demo:** https://d1ty5lyvyyivx6.cloudfront.net

### Concise form answers

**Short Description (1 sentence)**

Arsia turns project documents, peer feedback, and annual plans in Box into evidence-backed annual reviews using Amazon Bedrock, automated evaluation, and guided improvement.

**What AWS tools, SDKs or services did you use?**

Amazon Bedrock (Nova Pro) through the Converse API and Boto3 powers extraction, writing, evaluation, and improvement. EC2, CloudFront, S3, Secrets Manager, IAM, Systems Manager, and CloudFormation support the hosted demo; a separate Lambda worker was also tested.

**What Box APIs or tools did you use?**

Box REST APIs with OAuth 2.0 handle document uploads, folder browsing, version-pinned imports, downloads, and report versioning. Box AI Ask provides an additional source-grounded review.

## Before the three-minute presentation

1. Start the local app and confirm Box connection. Keep the service running and
   prevent the laptop from sleeping during the presentation.
2. Check one completed full report, its actual evaluation and the same files
   in Box. Identify it as a previously generated example.
3. Show Materials, one important source connection, Evaluation, Guidance, and
   the resulting Word/PDF. Use the [timed script](demo-script.md).
4. If starting a new generation, describe its real progress. Do not imply that
   an earlier completed result came from the newly clicked request.
5. Keep the committed fictional [sample reports](../examples/README.md) available
   as a reading fallback. A backup recording is optional preparation unless the
   actual submission form explicitly requires one.
6. Check the final form for repository visibility/access, extra description
   fields, a hosted demo or video requirement, and its final submission button.
   Preserve the submitted Git commit if later development continues.

No credentials or private employee documents belong in the public repository,
README, video, screenshot or submission text. Static samples use fictional data.
