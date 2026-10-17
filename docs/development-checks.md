# Development checks

Verified on October 16, 2026, during the hackathon.

## Box

- Account type: Developer; two-step verification enabled.
- Default CCG application: authorized and enabled.
- Client Credentials Grant authentication: passed.
- Current-user lookup and root-folder listing: passed.
- Created an isolated test folder under the app's service account.
- Uploaded a 76-byte synthetic text file, downloaded it, and verified the content matched exactly.
- Box AI Ask on the synthetic file: passed, with a correct answer and one source citation.

The CCG checks access the application's service account. A human user's Box files are a separate content space and require appropriate access.

Repeat the read-only check using `python3 scripts/check_box.py` after supplying local configuration.

## AWS

- Connected AWS account identity: verified.
- Region: `us-east-2`.
- Model: `amazon.nova-lite-v1:0`.
- A real Bedrock Converse request returned `READY` with `end_turn`.
- Usage for the check: 5 input tokens and 3 output tokens.

An additional check used a separate local Python environment with `boto3[crt]` and the existing `aws-toolkit` login profile. Both STS identity verification and a direct Bedrock Converse request passed. Any future cloud deployment role still needs its own permission check.

## Cross-document feasibility probe

Three fictional documents represented a project design, release results, and an employee work log. Box AI multi-document analysis returned three citations. Local Bedrock generated a Chinese draft, and the result was uploaded to Box.

The output correctly separated a 30% design target from a 20% measured result. This verifies a small-scale API pipeline, not report correctness: the first draft omitted one documented contribution and its structured future-plan status was inaccurate. Source-based review and revision remain required product work.

## Source repository

- Public GitHub repository and `main` branch initialized.
- Real credentials are stored in the ignored local `.env` file.
- Configuration examples contain no secrets.

These checks establish development API connectivity. The application and its deployment remain to be implemented.
