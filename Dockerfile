# Frontend and backend in one image, served from one origin.
#
# One image rather than two services because the study needs one stable URL for the
# whole collection period: the link is baked into the Prolific study and cannot be
# changed once participants start arriving. Same origin also removes cross-origin
# requests entirely, so a CORS misconfiguration can no longer take the study down.

# ── Stage 1: build the frontend ──────────────────────────────────────────────
FROM node:22-alpine AS frontend

WORKDIR /app

# Copy manifests first so the dependency layer is cached across source-only changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Vite inlines VITE_* variables at build time, so the Prolific completion details and
# the API origin have to be present here, not at run time. They are public values —
# never pass a secret this way.
ARG VITE_API_BASE=""
ARG VITE_PROLIFIC_COMPLETION_URL=""
ARG VITE_PROLIFIC_COMPLETION_CODE=""
ENV VITE_API_BASE=$VITE_API_BASE \
    VITE_PROLIFIC_COMPLETION_URL=$VITE_PROLIFIC_COMPLETION_URL \
    VITE_PROLIFIC_COMPLETION_CODE=$VITE_PROLIFIC_COMPLETION_CODE

RUN npm run build

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend /app/dist ./frontend/dist

# Data lives on a mounted volume, never in the image layer: a container filesystem is
# discarded on every restart and redeploy, which would silently destroy collected data.
ENV DATA_DIR=/data \
    FRONTEND_DIST=/app/frontend/dist \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# One worker, deliberately. The assignment ledger, the event log and the questionnaire
# file are appended to by a single process; a second worker would keep its own count of
# assignments and block randomisation would quietly stop balancing the two groups.
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
