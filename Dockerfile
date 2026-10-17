FROM node:24-bookworm-slim AS frontend

ENV CI=true
WORKDIR /build/frontend
RUN npm install --global pnpm@11.25.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    REVIEW_DATA_DIR=/data

WORKDIR /app
COPY requirements.txt requirements-local.txt constraints.txt ./
RUN python -m pip install --no-cache-dir -r requirements-local.txt \
    && python -m pip check \
    && groupadd --gid 10001 arsia \
    && useradd --uid 10001 --gid arsia --no-create-home --home-dir /app arsia \
    && mkdir -p /data \
    && chown arsia:arsia /data \
    && chmod 700 /data

COPY --chown=arsia:arsia app/ ./app/
COPY --from=frontend --chown=arsia:arsia /build/frontend/dist/ ./frontend/dist/

USER 10001:10001
VOLUME ["/data"]
EXPOSE 8765
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=3).read()"]

# Supply secrets and a workload IAM role at runtime. Never bake local AWS profiles
# or employee run records into the image. Mount persistent storage at /data.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", "--timeout-graceful-shutdown", "120"]
