# Development checks

Verified on October 16, 2026, during the hackathon.

## Box

- Account type: Developer; two-step verification enabled.
- Default CCG application: authorized and enabled.
- Client Credentials Grant authentication: passed.
- Current-user lookup and root-folder listing: passed.
- Created an isolated test folder under the app's service account.
- Uploaded a 76-byte synthetic text file, downloaded it, and verified the content matched exactly.

The CCG checks access the application's service account. A human user's Box files are a separate content space and require appropriate access.

Repeat the read-only check using `python3 scripts/check_box.py` after supplying local configuration.

## AWS

- Connected AWS account identity: verified.
- Region: `us-east-2`.
- Model: `amazon.nova-lite-v1:0`.
- A real Bedrock Converse request returned `READY` with `end_turn`.
- Usage for the check: 5 input tokens and 3 output tokens.

The inference check used the connected AWS role. Local application credentials and any future deployment role must be verified when the application stack is selected.

## Source repository

- Public GitHub repository and `main` branch initialized.
- Real credentials are stored in the ignored local `.env` file.
- Configuration examples contain no secrets.

These checks establish development API connectivity. The application and its deployment remain to be implemented.
