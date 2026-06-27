#!/usr/bin/env bash
set -euo pipefail

echo "Starting Synapse backend…"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level "${LOG_LEVEL:-info}"