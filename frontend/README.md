# Arsia local workbench

React, TypeScript and Vite. All application requests use relative `/api` paths.
The backend serves `dist/` at **http://127.0.0.1:8765** after a build.

```sh
pnpm install --frozen-lockfile
pnpm build
```

For frontend development, run the backend on `127.0.0.1:8765`, then `pnpm dev`.
Vite listens on `127.0.0.1:5173` and proxies `/api` to the local backend.

The interface uses actual API progress, exact evidence quotations and Box links.
Source uploads, answer addenda, human confirmation and saving to Box are explicit
actions. It does not start generation on page load. A `?run=RUN_ID` URL or the
last locally viewed run resumes an existing draft; otherwise the latest active
or completed run is opened. Box file IDs and account credentials are not inputs
to this interface.
