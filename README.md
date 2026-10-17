# AWS × Box Hackathon

A hackathon project integrating AWS and Box.

**Status:** AWS and Box API connectivity checks passed. Project scope, application implementation, and deployment instructions are pending. See the [development checks](docs/development-checks.md).

## Development

This repository will contain the application source code, integration setup, and development history. Submission implementation must be written during the hackathon.

Setup and run instructions will be added when the application stack is selected.

## Configuration

`.env.example` lists placeholder values for local integration setup. Keep real configuration in an ignored `.env` file. AWS access should use a local authenticated profile during development and an IAM role when deployed.

Keep AWS credentials, Box client secrets, access tokens, and private test documents out of Git.

### Check Box access

For a Server app using Client Credentials Grant, set `BOX_CLIENT_ID`, `BOX_CLIENT_SECRET`, and `BOX_ENTERPRISE_ID` in the local `.env` file. Alternatively, set a short-lived `BOX_ACCESS_TOKEN` for an initial check.

Run with Python 3.9 or later; no additional packages are needed:

```sh
python3 scripts/check_box.py
```

The check requests an access token, verifies the authenticated user, and lists the root folder. It does not modify Box files or print credentials. A CCG check accesses the app's service account by default; files in your personal Box account are a separate content space.

## Demo and submission

The repository URL is the source-code submission link. A live demo link, screenshots, architecture notes, and the three-minute presentation outline will be added as the project develops.
