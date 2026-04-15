#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv/bin"

# Load .env if present
if [ -f "$ROOT/.env" ]; then
    export $(grep -v '^#' "$ROOT/.env" | xargs)
fi

echo "=== IRC Book Bot ==="
echo ""

# Check if frontend is built
if [ ! -d "$ROOT/frontend/dist" ]; then
    echo "Building frontend..."
    cd "$ROOT/frontend" && npm run build && cd "$ROOT"
fi

echo "Starting server on http://localhost:8000"
echo "Default password: ${IRCBOT_PASSWORD:-changeme}"
echo ""

cd "$ROOT/backend"
exec "$VENV/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
