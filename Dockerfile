# Multi-stage Docker build for Lot Zero (Cloud Run + GCS Volume persistent SQLite)

# Stage 1: Build React Frontend (Vite)
FROM node:20-alpine AS frontend-builder
WORKDIR /app/web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

# Stage 2: Python Backend with Frontend Static Assets
FROM python:3.12-slim AS runner
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOT_ZERO_DB_PATH=/app/data/lot_zero.db \
    PATH="/usr/local/bin:/root/.local/bin:${PATH}" \
    PYTHONPATH="/app/apps/api/src:${PYTHONPATH}" \
    PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy API application source & install dependencies
COPY apps/api /app/apps/api
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e /app/apps/api

# Copy built frontend assets to static mount location
COPY --from=frontend-builder /app/web/dist /app/apps/web/dist

# Create storage volume mount directory for Cloud Storage (gcsfuse)
RUN mkdir -p /app/data

EXPOSE 8080

WORKDIR /app/apps/api
CMD ["sh", "-c", "python -m uvicorn lot_zero.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
