#!/bin/bash
set -e

# Port configuration
export BACKEND_PORT=8000
export FRONTEND_PORT=${PORT:-10000}
export VERITAS_API_URL="http://127.0.0.1:${BACKEND_PORT}"
export PYTHONPATH="/app/backend:${PYTHONPATH}"

echo "============================================================"
echo " MNB VERITAS — FULL-STACK ENGINE STARTUP (RENDER)"
echo "============================================================"
echo "==> Frontend Port: ${FRONTEND_PORT} (Public)"
echo "==> Backend Port:  ${BACKEND_PORT} (Internal 127.0.0.1)"
echo "==> API Proxy:     ${VERITAS_API_URL}"

# Start FastAPI Verification Engine in background
cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --workers 1 &
BACKEND_PID=$!

# Start Next.js Forensic Workbench
cd /app/frontend
PORT=${FRONTEND_PORT} HOSTNAME="0.0.0.0" node server.js &
FRONTEND_PID=$!

trap "kill -TERM $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait -n $BACKEND_PID $FRONTEND_PID
