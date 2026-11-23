# Hosted demo image (docs/deploy.md): one container serves the API and the built UI on $PORT.
# Synthetic data only; fixture extractor; shared password via DEMO_PASSWORD (set on the host,
# never in git). Local development does not use this file.

# ---- 1. frontend build (same-origin API: VITE_API_BASE=/)
# Base images pinned to exact releases (QA #24); bump on purpose, in a PR.
FROM node:22.23.4-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV VITE_API_BASE=/
RUN npm run build

# ---- 2. runtime: FastAPI + generated sample packages + the UI build
FROM python:3.13.17-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Runtime set only (no pytest/httpx/anthropic: fixture mode never calls Claude), at the exact
# versions the test suite runs with.
COPY backend/requirements-runtime.txt backend/constraints-runtime.txt backend/
RUN pip install -r backend/requirements-runtime.txt -c backend/constraints-runtime.txt
COPY backend/ backend/
COPY samples/generate.py samples/ground_truth.json samples/
# Sample PDFs are not in git; the generator is deterministic and reads backend/app/rules/config.yaml.
RUN python samples/generate.py
COPY --from=web /web/dist frontend/dist

# Demo defaults; DEMO_PASSWORD (and optionally DEMO_USER) come from the host's secret settings.
ENV EXTRACTOR=fixture \
    VYAPAARIQ_TODAY=2026-11-23 \
    VYAPAARIQ_DB=/tmp/vyapaariq-demo.db \
    DEMO_BOOTSTRAP=1 \
    DEMO_PRELOAD=PKG01,PKG20 \
    STATIC_DIR=/app/frontend/dist \
    CORS_ORIGINS=

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
