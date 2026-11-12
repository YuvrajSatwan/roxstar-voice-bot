# ==============================================================================
# Multi-Stage Dockerfile for RoxStar Simran STS Lab
# Builds React frontend and bundles Python LiveKit Agent + Token Server
# ==============================================================================

# Stage 1: Build Frontend Assets
FROM node:22-alpine AS frontend-builder
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python 3.11 Runtime for STS Token Server & LiveKit Agent Worker
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code into sts_lab package directory
COPY . /app/sts_lab

# Copy compiled frontend from Stage 1 into sts_lab/web/dist
COPY --from=frontend-builder /app/web/dist /app/sts_lab/web/dist

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV STS_HOST=0.0.0.0
ENV PORT=8001
ENV GOOGLE_GENAI_API_VERSION=v1beta

EXPOSE 8001

# Run as an unprivileged user (it still needs to write the local SQLite fallback and profile store).
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/health || exit 1

CMD ["python", "sts_lab/run_sts.py"]

