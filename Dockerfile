# =====================================================================
# MNB VERITAS — UNIFIED FULL-STACK PRODUCTION CONTAINER (RENDER)
# Builds both Next.js Frontend and FastAPI Backend into a single image
# =====================================================================

# ---------------------------------------------------------------------
# Stage 1: Build Next.js 15 Standalone Frontend
# ---------------------------------------------------------------------
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production
RUN npm run build

# ---------------------------------------------------------------------
# Stage 2: Build Python 3.12 Backend Dependencies
# ---------------------------------------------------------------------
FROM python:3.12-slim AS backend-builder
WORKDIR /build/backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------------
# Stage 3: Unified Production Runtime
# ---------------------------------------------------------------------
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME="0.0.0.0"

# Install Node.js runtime and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python virtual environment & backend source
COPY --from=backend-builder /opt/venv /opt/venv
COPY backend/app /app/backend/app
COPY backend/veritas_engine.py /app/backend/veritas_engine.py

# Copy Next.js standalone build & static assets
COPY --from=frontend-builder /build/frontend/.next/standalone /app/frontend
COPY --from=frontend-builder /build/frontend/.next/static /app/frontend/.next/static

# Copy launcher script
COPY scripts/start_render.sh /app/start_render.sh
RUN chmod +x /app/start_render.sh

# Render binds to $PORT (typically 10000 on free tier)
EXPOSE 10000 3000 8000

CMD ["/app/start_render.sh"]
