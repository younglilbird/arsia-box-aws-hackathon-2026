#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${NODE_BIN:-}" ] && ! command -v node >/dev/null 2>&1; then
  bundled_node="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
  if [ -x "$bundled_node" ]; then NODE_BIN="$bundled_node"; fi
fi
if [ -n "${NODE_BIN:-}" ]; then
  export PATH="$(dirname "$NODE_BIN"):$PATH"
fi
if [ -z "${PNPM_BIN:-}" ]; then
  if command -v pnpm >/dev/null 2>&1; then
    PNPM_BIN=$(command -v pnpm)
  elif [ -x "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm" ]; then
    PNPM_BIN="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pnpm"
  fi
fi
if ! command -v node >/dev/null 2>&1 || [ -z "${PNPM_BIN:-}" ]; then
  echo 'Node.js and pnpm are required. Add them to PATH or set NODE_BIN and PNPM_BIN.' >&2
  exit 1
fi
if [ -z "${PYTHON_BIN:-}" ]; then
  if [ -x .venv/bin/python ]; then PYTHON_BIN=.venv/bin/python; else PYTHON_BIN=python3; fi
fi
if ! "$PYTHON_BIN" -c 'import fastapi, uvicorn, multipart' >/dev/null 2>&1; then
  echo 'Install local dependencies first: python -m pip install -r requirements-local.txt' >&2
  exit 1
fi
(cd frontend && if [ ! -d node_modules ]; then "$PNPM_BIN" install --frozen-lockfile; fi && "$PNPM_BIN" run build)
echo 'Open http://127.0.0.1:8765 to use the local workbench. Press Ctrl-C to stop.'
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
