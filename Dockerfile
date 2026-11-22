# =====================================================================
# MNB VERITAS — UNIFIED FULL-STACK PRODUCTION CONTAINER (RENDER)
# Builds both Next.js Frontend and FastAPI Backend into a single image
# =====================================================================

# ---------------------------------------------------------------------
# Stage 1: Build Next.js 15 Standalone Frontend
# ---------------------------------------------------------------------
FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
ARG NEXT_PUBLIC_SUPABASE_URL="https://rzgbswkasiddobaaewrq.supabase.co"
ARG NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=""
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL} \
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=${NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY}
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
# Stage 3: Unified Production Runtime (Debian Bookworm)
# ---------------------------------------------------------------------
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME="0.0.0.0"

# Copy Node.js 22 runtime directly from node:22-bookworm-slim (identical glibc)
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/bin/node /usr/bin/node

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
