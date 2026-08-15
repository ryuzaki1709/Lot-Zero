# Multi-stage Docker build for Lot Zero

# Stage 1: Build React Frontend
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
    LOT_ZERO_DB_PATH=/app/data/lot_zero.db

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY apps/api/pyproject.toml apps/api/
RUN pip install --no-cache-dir ./apps/api

# Copy API application source
COPY apps/api /app/apps/api

# Copy built frontend assets to static mount
COPY --from=frontend-builder /app/web/dist /app/apps/web/dist

# Create storage volume directory
RUN mkdir -p /app/data

EXPOSE 8000

WORKDIR /app/apps/api
CMD ["uvicorn", "lot_zero.app:app", "--host", "0.0.0.0", "--port", "8000"]
